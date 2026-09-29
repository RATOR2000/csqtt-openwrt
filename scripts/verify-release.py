#!/usr/bin/env python3
"""Check an already authenticated manifest against the downloaded package bytes."""
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
expected = {'schema': 1, 'openwrt': '25.12.5', 'target': 'mediatek/filogic',
            'architecture': 'aarch64_cortex-a53', 'upstream': 'amurcanov/csqtt@v2.1.9'}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f'Unsupported manifest {key}')
packages = manifest.get('packages')
if not isinstance(packages, list) or len(packages) != 3:
    raise SystemExit('Expected three router packages')
seen = set()
for package in packages:
    name = package.get('name', '')
    match = re.fullmatch(r'(csqtt-captcha|luci-app-csqtt|csqtt)-[0-9][A-Za-z0-9_.+~-]*\.apk', name)
    if not match or match[1] in seen:
        raise SystemExit('Invalid or duplicate package role')
    seen.add(match[1])
    data = (root / name).read_bytes()
    if len(data) != package.get('size') or hashlib.sha256(data).hexdigest() != package.get('sha256'):
        raise SystemExit(f'Package checksum or size mismatch: {name}')
if {p.name for p in root.glob('*.apk')} != {p['name'] for p in packages}:
    raise SystemExit('Package directory differs from manifest')
print('Release package hashes and target verified')
