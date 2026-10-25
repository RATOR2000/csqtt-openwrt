#!/usr/bin/env python3
"""Independently verify public preview bytes, signatures and tagged source.

This host-only checker never connects to a router or changes release assets.
"""
import argparse
import concurrent.futures
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

from release_schema import UPSTREAM, artifact, describe, load, require, token, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = 'RATOR2000/csqtt-openwrt'
HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com',
         'raw.githubusercontent.com', 'api.github.com'}


def download(url, destination, limit=67108864):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname in HOSTS, 'Unapproved HTTPS origin')
    request = urllib.request.Request(url, headers={'User-Agent': 'CSQTT-public-release-verifier'})
    with urllib.request.urlopen(request, timeout=60) as response:
        final = urllib.parse.urlsplit(response.url)
        require(final.scheme == 'https' and final.hostname in HOSTS, 'Unapproved download redirect')
        body = response.read(limit + 1)
    require(0 < len(body) <= limit, 'Public download exceeds bound or is empty')
    require(not destination.is_symlink(), 'Linked output is forbidden')
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary.write(body)
        name = pathlib.Path(temporary.name)
    name.replace(destination)


def verify_signature(document, signature, public_key=ROOT / 'release/csqtt-public.pem'):
    node = shutil.which('node')
    require(node is not None, 'Node.js is required for host signature verification')
    code = ("const fs=require('node:fs'),c=require('node:crypto');"
            "const [key,data,sig]=process.argv.slice(1);"
            "process.exit(c.verify('sha256',fs.readFileSync(data),fs.readFileSync(key),fs.readFileSync(sig))?0:1)")
    result = subprocess.run([node, '-e', code, str(public_key), str(document), str(signature)],
                            capture_output=True, timeout=30)
    require(result.returncode == 0, 'Public detached signature is invalid')


def checked_asset(entry, base, output):
    artifact(entry)
    path = output / entry['name']
    if path.exists():
        try:
            artifact(entry, output)
            return
        except ValueError:
            pass
    download(base + entry['name'], path, entry['size'])
    artifact(entry, output)


def verify(tag, source_commit, output, profiles=None):
    require(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+-preview\.[1-9][0-9]*', tag), 'Explicit preview tag required')
    require(re.fullmatch(r'[0-9a-f]{40}', source_commit), 'Exact source commit required')
    require(not profiles or all(token(p) for p in profiles), 'Invalid requested profile')
    output = pathlib.Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base = f'https://github.com/{REPO}/releases/download/{tag}/'
    for name in ('catalogue.json', 'catalogue.sig'):
        download(base + name, output / name, 262144)
    verify_signature(output / 'catalogue.json', output / 'catalogue.sig')
    catalogue = load(output / 'catalogue.json')
    require(isinstance(catalogue, dict) and catalogue.get('schema') == 2 and catalogue.get('upstream') == UPSTREAM,
            'Unsupported public catalogue')
    entries = catalogue.get('profiles')
    require(isinstance(entries, list) and 0 < len(entries) <= 128, 'Invalid public profile count')
    seen, selected, assets = set(), [], {}
    for entry in entries:
        require(isinstance(entry, dict), 'Invalid catalogue entry')
        identity = entry.get('profile_id')
        require(token(identity) and identity not in seen, 'Invalid or duplicate public profile')
        seen.add(identity)
        if profiles and identity not in profiles:
            continue
        require(entry.get('name') == identity + '-manifest.json', 'Public manifest name mismatch')
        for descriptor in (entry, entry.get('signature')):
            checked_asset(descriptor, base, output)
        path = output / entry['name']
        verify_signature(path, output / entry['signature']['name'])
        manifest = validate(load(path))
        require(manifest['profile_id'] == identity, 'Public profile identity mismatch')
        q = manifest['qualification']
        require(q.get('source_commit') == source_commit and q.get('installation') is True and
                q.get('activation') is True and q.get('preview') is True and
                q.get('physical_device') is False and q.get('proofs') and
                q.get('reason') == 'clean_official_firmware_vm_and_selected_abi_preview',
                'Public preview lacks matching source/evidence')
        descriptors = [*manifest['packages'], *manifest['dependency_bundle']['packages'],
                       *manifest['dependency_bundle']['indexes'], *q['proofs'],
                       *manifest.get('third_party_sources', [])]
        descriptors.extend(i['signature'] for i in manifest['dependency_bundle']['indexes'] if 'signature' in i)
        for descriptor in descriptors:
            artifact(descriptor)
            prior = assets.get(descriptor['name'])
            require(prior is None or (prior['sha256'], prior['size']) == (descriptor['sha256'], descriptor['size']),
                    'Conflicting public artifact identities')
            assets[descriptor['name']] = descriptor
        selected.append((path, manifest))
    require(selected and (not profiles or set(profiles) <= seen), 'Requested public profile is missing')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda entry: checked_asset(entry, base, output), assets.values()))
    for descriptor in assets.values():
        artifact(descriptor, output)
    expected_packages = {name for name in assets if name.endswith(('.apk', '.ipk'))}
    actual_packages = {path.name for path in output.iterdir() if path.suffix in ('.apk', '.ipk')}
    require(actual_packages == expected_packages, 'Public package directory differs from selected profiles')
    for path, manifest in selected:
        for proof in manifest['qualification']['proofs']:
            document = load(output / proof['name'])
            require(document.get('source_commit') == source_commit, 'Public proof/source mismatch')
    download(base + 'install.sh', output / 'install.sh', 1048576)
    download(f'https://raw.githubusercontent.com/{REPO}/{source_commit}/install.sh', output / '.source-installer', 1048576)
    download(f'https://raw.githubusercontent.com/{REPO}/{tag}/install.sh', output / '.tag-installer', 1048576)
    require((output / 'install.sh').read_bytes() == (output / '.source-installer').read_bytes() ==
            (output / '.tag-installer').read_bytes(), 'Published installer differs from tagged/qualified source')
    download(f'https://api.github.com/repos/{REPO}/git/ref/tags/{tag}', output / '.tag-ref', 262144)
    reference = load(output / '.tag-ref')['object']
    if reference.get('type') == 'tag':
        require(re.fullmatch('[0-9a-f]{40}', reference.get('sha', '')), 'Invalid annotated tag')
        download(f'https://api.github.com/repos/{REPO}/git/tags/' + reference['sha'], output / '.tag-object', 262144)
        reference = load(output / '.tag-object')['object']
    require(reference.get('type') == 'commit' and reference.get('sha') == source_commit, 'Published tag points to another commit')
    result = {'schema': 1, 'tag': tag, 'source_commit': source_commit,
              'profiles': sorted(m['profile_id'] for _, m in selected),
              'verified_referenced_assets': len(assets), 'installer': describe(output / 'install.sh'),
              'catalogue': describe(output / 'catalogue.json'),
              'signatures': 'pinned_project_p256', 'router_modified': False}
    (output / '.verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--profile', action='append')
    args = parser.parse_args()
    report = verify(args.tag, args.source_commit, args.output, args.profile)
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        raise SystemExit('Public release verification failed; no router or release assets were changed.') from None
