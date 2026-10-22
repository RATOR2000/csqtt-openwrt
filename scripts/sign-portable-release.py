#!/usr/bin/env python3
"""Sign already gated tuple/catalogue bytes with the pinned P256 CI secret."""
import argparse
import os
import pathlib
import subprocess
import tempfile

from release_schema import load, require, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sign(path, key):
    signature = path.with_suffix('.sig')
    subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key), '-out', str(signature), str(path)],
                   check=True, capture_output=True)
    subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(ROOT / 'release/csqtt-public.pem'),
                    '-signature', str(signature), str(path)], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--provisional', action='store_true', help='Private CI fixture only; never publish')
    args = parser.parse_args()
    secret = os.environ.pop('CSQTT_SIGNING_KEY', '')
    require(secret, 'Release signing secret is unavailable')
    with tempfile.TemporaryDirectory(prefix='csqtt-sign-') as temporary:
        key = pathlib.Path(temporary) / 'key.pem'
        key.write_text(secret)
        key.chmod(0o600)
        secret = None
        public = subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout'], check=True,
                                capture_output=True).stdout
        require(public == (ROOT / 'release/csqtt-public.pem').read_bytes(), 'Signing public key mismatch')
        for path in sorted(args.directory.rglob('*-manifest.json')):
            manifest = validate(load(path), path.parent)
            if args.provisional:
                manifest['qualification'] = {'installation': True, 'activation': True,
                                             'evidence': ['private-ci-pending'], 'preview': True,
                                             'physical_device': False, 'reason': 'private_ci_fixture_only'}
                import json
                path.write_text(json.dumps(manifest, indent=2) + '\n')
                (path.parent / 'manifest.json').write_bytes(path.read_bytes())
            else:
                q = manifest['qualification']
                require(q.get('preview') is True and q.get('physical_device') is False and q.get('proofs') and
                        q.get('source_commit') == os.environ.get('GITHUB_SHA'), 'Ungated or foreign-source profile cannot be released')
            sign(path, key)
            (path.parent / 'manifest.sig').write_bytes(path.with_suffix('.sig').read_bytes())
        catalogue = args.directory / 'catalogue.json'
        if catalogue.exists():
            require(not args.provisional, 'Private fixture catalogue must never be published')
            sign(catalogue, key)
    print('Pinned P256 detached signatures verified.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        raise SystemExit('Release signing failed; no key/parser diagnostics are printed.') from None
