#!/usr/bin/env python3
"""Sign already gated tuple/catalogue bytes with the pinned P256 CI secret."""
import argparse
import os
import pathlib
import subprocess
import tempfile

from release_schema import UPSTREAM, artifact, load, require, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]


def verify_signature(path, signature):
    subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(ROOT / 'release/csqtt-public.pem'),
                    '-signature', str(signature), str(path)], check=True, capture_output=True)


def sign(path, key):
    signature = path.with_suffix('.sig')
    subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key), '-out', str(signature), str(path)],
                   check=True, capture_output=True)
    verify_signature(path, signature)


def require_qualified(manifest):
    q = manifest['qualification']
    require(q.get('preview') is True and q.get('physical_device') is False and q.get('proofs') and
            q.get('source_commit') == os.environ.get('GITHUB_SHA'), 'Ungated or foreign-source profile cannot be released')


def verify_catalogue(directory):
    catalogue = directory / 'catalogue.json'
    data = load(catalogue)
    require(isinstance(data, dict), 'Invalid catalogue')
    require(data.get('schema') == 2 and data.get('upstream') == UPSTREAM, 'Unsupported catalogue')
    entries = data.get('profiles')
    require(isinstance(entries, list) and 0 < len(entries) <= 128, 'Invalid catalogue profile count')
    paths = list(directory.rglob('*-manifest.json'))
    by_name = {path.name: path for path in paths}
    require(len(by_name) == len(paths), 'Ambiguous tuple manifest filename')
    seen = set()
    for entry in entries:
        artifact(entry)
        path = by_name.get(entry['name'])
        require(path is not None and path.name not in seen, 'Missing or duplicate catalogue tuple')
        seen.add(path.name)
        artifact(entry, path.parent)
        signature = entry.get('signature')
        artifact(signature, path.parent)
        require(signature['name'] == path.with_suffix('.sig').name, 'Wrong tuple signature filename')
        manifest = validate(load(path))
        require(entry.get('profile_id') == manifest.get('profile_id') and
                path.name == manifest['profile_id'] + '-manifest.json', 'Catalogue profile mismatch')
        require_qualified(manifest)
        q = manifest['qualification']
        require(q.get('installation') is True and q.get('activation') is True and
                q.get('reason') == 'clean_official_firmware_vm_and_selected_abi_preview',
                'Profile lacks successful preview acceptance')
        bundle = manifest.get('dependency_bundle', {'packages': [], 'indexes': []})
        files = [*manifest['packages'], *bundle['packages'], *bundle['indexes'],
                 *q['proofs'], *manifest.get('third_party_sources', [])]
        files.extend(i['signature'] for i in bundle['indexes'] if 'signature' in i)
        for file in files:
            artifact(file, path.parent)
        verify_signature(path, path.parent / signature['name'])
    require(seen == set(by_name), 'Catalogue omits tuple manifests')
    return catalogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--provisional', action='store_true', help='Private CI fixture only; never publish')
    mode.add_argument('--catalogue-only', action='store_true', help='Verify existing tuples and sign only their catalogue')
    mode.add_argument('--verify-only', action='store_true', help='Verify final catalogue, tuples and artifact hashes without a signing key')
    args = parser.parse_args()
    secret = os.environ.pop('CSQTT_SIGNING_KEY', '')
    if args.verify_only:
        catalogue = verify_catalogue(args.directory)
        verify_signature(catalogue, catalogue.with_suffix('.sig'))
        print('Final catalogue, tuple signatures and artifact hashes verified.')
        return
    catalogue = args.directory / 'catalogue.json'
    if args.catalogue_only:
        verify_catalogue(args.directory)
    else:
        require(not catalogue.exists(), 'Existing catalogue requires --catalogue-only; tuple signatures are immutable')
    require(secret, 'Release signing secret is unavailable')
    with tempfile.TemporaryDirectory(prefix='csqtt-sign-') as temporary:
        key = pathlib.Path(temporary) / 'key.pem'
        key.write_text(secret)
        key.chmod(0o600)
        secret = None
        public = subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout'], check=True,
                                capture_output=True).stdout
        require(public == (ROOT / 'release/csqtt-public.pem').read_bytes(), 'Signing public key mismatch')
        for path in ([] if args.catalogue_only else sorted(args.directory.rglob('*-manifest.json'))):
            manifest = validate(load(path), path.parent)
            if args.provisional:
                manifest['qualification'] = {'installation': True, 'activation': True,
                                             'evidence': ['private-ci-pending'], 'preview': True,
                                             'physical_device': False, 'reason': 'private_ci_fixture_only'}
                import json
                path.write_text(json.dumps(manifest, indent=2) + '\n')
                (path.parent / 'manifest.json').write_bytes(path.read_bytes())
            else:
                require_qualified(manifest)
            sign(path, key)
            (path.parent / 'manifest.sig').write_bytes(path.with_suffix('.sig').read_bytes())
        if args.catalogue_only:
            sign(catalogue, key)
    print('Pinned P256 detached signatures verified.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        raise SystemExit('Release signing failed; no key/parser diagnostics are printed.') from None
