#!/usr/bin/env python3
"""Repackage verified signed bytes for GitHub's tilde-free asset filenames."""
import argparse
import copy
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

from release_schema import UPSTREAM, artifact, describe, load, require, token, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVENANCE = 'publication-provenance.json'


def node(code, *args, secret=None):
    executable = shutil.which('node')
    require(executable is not None, 'Node.js is required')
    environment = dict(os.environ)
    environment.pop('CSQTT_SIGNING_KEY', None)
    if secret is not None:
        environment['CSQTT_SIGNING_KEY'] = secret
    result = subprocess.run([executable, '-e', code, *map(str, args)], env=environment,
                            capture_output=True, timeout=60)
    require(result.returncode == 0, 'Pinned publication signature operation failed')


def verify_signature(document, signature):
    node("const fs=require('node:fs'),c=require('node:crypto');"
         "const [key,doc,sig]=process.argv.slice(1);"
         "process.exit(c.verify('sha256',fs.readFileSync(doc),fs.readFileSync(key),fs.readFileSync(sig))?0:1)",
         ROOT / 'release/csqtt-public.pem', document, signature)


def sign_documents(documents, secret):
    require(secret, 'Publication signing key is unavailable')
    node("const fs=require('node:fs'),c=require('node:crypto');"
         "const [pin,...docs]=process.argv.slice(1),pem=process.env.CSQTT_SIGNING_KEY;"
         "delete process.env.CSQTT_SIGNING_KEY;const key=c.createPrivateKey(pem);"
         "const pub=c.createPublicKey(key).export({type:'spki',format:'pem'});"
         "if(pub!==fs.readFileSync(pin,'utf8'))process.exit(1);"
         "for(const doc of docs)fs.writeFileSync(doc.replace(/\\.json$/,'.sig'),c.sign('sha256',fs.readFileSync(doc),key));",
         ROOT / 'release/csqtt-public.pem', *documents, secret=secret)


def source_installer(source_commit):
    result = subprocess.run(['git', 'show', source_commit + ':install.sh'], cwd=ROOT,
                            capture_output=True, timeout=30)
    require(result.returncode == 0, 'Qualified source installer is unavailable locally')
    return result.stdout


def descriptors(value):
    if isinstance(value, dict):
        if {'name', 'size', 'sha256'} <= value.keys():
            yield value
        for child in value.values():
            yield from descriptors(child)
    elif isinstance(value, list):
        for child in value:
            yield from descriptors(child)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def checksums(directory, verify=False):
    paths = sorted((p for p in directory.iterdir() if p.name != 'SHA256SUMS'), key=lambda path: path.name)
    text = ''.join(f"{describe(path)['sha256']}  {path.name}\n" for path in paths)
    if verify:
        require((directory / 'SHA256SUMS').read_text(encoding='ascii') == text, 'Source SHA256SUMS mismatch')
    else:
        (directory / 'SHA256SUMS').write_text(text, encoding='ascii')


def verify_directory(directory, source_commit, canonical=False):
    require(directory.is_dir() and not directory.is_symlink(), 'A regular flat input directory is required')
    files = list(directory.iterdir())
    require(files and all(p.is_file() and not p.is_symlink() and token(p.name) for p in files),
            'Only flat regular public assets are allowed')
    require(not canonical or all('~' not in p.name for p in files), 'Noncanonical publication filename')
    require((directory / 'csqtt-public.pem').read_bytes() == (ROOT / 'release/csqtt-public.pem').read_bytes(),
            'Bundled public key differs from project pin')
    require((directory / 'install.sh').read_bytes() == source_installer(source_commit), 'Installer differs from qualified source')
    verify_signature(directory / 'catalogue.json', directory / 'catalogue.sig')
    catalogue = load(directory / 'catalogue.json')
    require(isinstance(catalogue, dict) and catalogue.get('schema') == 2 and catalogue.get('upstream') == UPSTREAM,
            'Unsupported publication catalogue')
    entries = catalogue.get('profiles')
    require(isinstance(entries, list) and 0 < len(entries) <= 128, 'Invalid publication profile count')
    manifests, seen, packages = {}, set(), set()
    for entry in entries:
        artifact(entry, directory)
        identity = entry.get('profile_id')
        require(token(identity) and identity not in seen and entry['name'] == identity + '-manifest.json',
                'Invalid or duplicate publication profile')
        seen.add(identity)
        signature = entry.get('signature')
        artifact(signature, directory)
        require(signature['name'] == pathlib.Path(entry['name']).with_suffix('.sig').name, 'Wrong manifest signature name')
        verify_signature(directory / entry['name'], directory / signature['name'])
        manifest = validate(load(directory / entry['name']))
        require(manifest.get('profile_id') == identity, 'Manifest profile mismatch')
        q = manifest['qualification']
        require(q.get('source_commit') == source_commit and q.get('installation') is True and
                q.get('activation') is True and q.get('preview') is True and q.get('physical_device') is False and
                q.get('reason') == 'clean_official_firmware_vm_and_selected_abi_preview', 'Foreign or unqualified publication source')
        for descriptor in descriptors(manifest):
            artifact(descriptor, directory)
            if descriptor['name'].endswith(('.apk', '.ipk')):
                packages.add(descriptor['name'])
            require(not canonical or '~' not in descriptor['name'], 'Noncanonical descriptor filename')
        for proof in q['proofs']:
            require(load(directory / proof['name']).get('source_commit') == source_commit, 'Proof/source mismatch')
        manifests[entry['name']] = manifest
    require(set(manifests) == {p.name for p in files if p.name.endswith('-manifest.json')}, 'Unlisted manifest')
    require(packages == {p.name for p in files if p.suffix in ('.apk', '.ipk')}, 'Unexpected publication packages')
    if 'publication_provenance' in catalogue:
        provenance = catalogue['publication_provenance']
        artifact(provenance, directory)
        require(provenance['name'] == PROVENANCE and load(directory / PROVENANCE).get('source_commit') == source_commit,
                'Publication provenance/source mismatch')
    checksums(directory, verify=True)
    return catalogue, manifests


def normalize(inputs, output, source_commit, source_run, source_artifact, source_artifact_sha256):
    inputs, output = pathlib.Path(inputs), pathlib.Path(output)
    secret = os.environ.pop('CSQTT_SIGNING_KEY', '')
    packaging_commit = os.environ.get('GITHUB_SHA', '')
    require(re.fullmatch(r'[0-9a-f]{40}', source_commit) and re.fullmatch(r'[0-9a-f]{40}', packaging_commit),
            'Exact qualified source and packaging commits are required')
    require(re.fullmatch(r'[1-9][0-9]*', str(source_run)) and re.fullmatch(r'[1-9][0-9]*', str(source_artifact)) and
            re.fullmatch(r'[0-9a-f]{64}', source_artifact_sha256), 'Exact original artifact provenance is required')
    require(not output.exists() and output.parent.is_dir(), 'Publication output must be a new directory')
    catalogue, manifests = verify_directory(inputs, source_commit)
    require('publication_provenance' not in catalogue and not (inputs / PROVENANCE).exists(), 'Input was already repackaged')
    renamed = {p.name: p.name.replace('~', '.') for p in inputs.iterdir()}
    require(len(set(renamed.values())) == len(renamed), 'Publication filename normalization collision')
    sign_documents([], secret)  # Check the secret against the pin before creating output files.
    with tempfile.TemporaryDirectory(prefix='.csqtt-publication-', dir=output.parent) as temporary:
        staged = pathlib.Path(temporary) / 'assets'
        staged.mkdir()
        for original, canonical in renamed.items():
            shutil.copyfile(inputs / original, staged / canonical)
        for name, original in manifests.items():
            manifest = copy.deepcopy(original)
            for descriptor in descriptors(manifest):
                descriptor['name'] = descriptor['name'].replace('~', '.')
            write_json(staged / renamed[name], manifest)
        sign_documents([staged / renamed[name] for name in manifests], secret)
        updated = copy.deepcopy(catalogue)
        for entry in updated['profiles']:
            path = staged / renamed[entry['name']]
            entry.update(describe(path), signature=describe(path.with_suffix('.sig')))
        provenance = {'schema': 1, 'source_commit': source_commit, 'packaging_commit': packaging_commit,
                      'source_workflow_run': str(source_run), 'source_artifact_id': str(source_artifact),
                      'source_artifact_sha256': source_artifact_sha256,
                      'original_catalogue': describe(inputs / 'catalogue.json'),
                      'transformation': 'github_asset_filename_tilde_to_dot',
                      'renamed_assets': [{'original': name, 'published': canonical,
                                          'sha256': describe(inputs / name)['sha256']}
                                         for name, canonical in sorted(renamed.items()) if name != canonical]}
        write_json(staged / PROVENANCE, provenance)
        updated['publication_provenance'] = describe(staged / PROVENANCE)
        write_json(staged / 'catalogue.json', updated)
        sign_documents([staged / 'catalogue.json'], secret)
        checksums(staged)
        verify_directory(staged, source_commit, canonical=True)
        # Every original payload, proof, installer and corresponding source remains byte-identical.
        metadata = {'catalogue.json', 'catalogue.sig', 'SHA256SUMS', *manifests,
                    *(str(pathlib.Path(name).with_suffix('.sig')) for name in manifests)}
        for name, canonical in renamed.items():
            if name not in metadata:
                require((inputs / name).read_bytes() == (staged / canonical).read_bytes(), 'Original payload bytes changed')
        require(not output.exists(), 'Publication output appeared during staging')
        staged.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--source-run', required=True)
    parser.add_argument('--source-artifact', required=True)
    parser.add_argument('--source-artifact-sha256', required=True)
    args = parser.parse_args()
    normalize(args.inputs, args.output, args.source_commit, args.source_run,
              args.source_artifact, args.source_artifact_sha256)
    print('Canonical publication assets verified; qualified payload bytes and source binding are unchanged.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        raise SystemExit('Publication normalization refused; no key diagnostics or partial output are published.') from None
