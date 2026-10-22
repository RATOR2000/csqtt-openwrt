#!/usr/bin/env python3
"""Describe one exact SDK tuple; no flags preserves the signed9 schema1 path."""
import argparse
import json
import pathlib
import re
from release_schema import UPSTREAM, describe, load, require, token, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--profile')
    parser.add_argument('--registry', type=pathlib.Path)
    parser.add_argument('--dependencies', type=pathlib.Path, help='Cached signed-index dependency bundle metadata')
    args = parser.parse_args()
    root = args.directory
    if args.profile:
        require(args.registry is not None and token(args.profile), 'A registry and valid profile are required')
        profiles = load(args.registry)
        require(profiles.get('schema') == 1, 'Unsupported platform registry')
        matches = [p for p in profiles['profiles'] if p['id'] == args.profile]
        require(len(matches) == 1, 'Unknown or duplicate platform profile')
        p = matches[0]
        platform = {k: p[k] for k in ('family', 'openwrt', 'target', 'architecture', 'package_manager', 'package_format')}
        platform.update({k: p[k] for k in ('firmware', 'board') if k in p})
        manifest = {'schema': 2, 'profile_id': p['id'], 'upstream': UPSTREAM, 'platform': platform,
                    'qualification': p.get('qualification', {'installation': False, 'activation': False}),
                    'requirements': p.get('requirements', {'overlay_free_kib': 65536, 'tmp_free_kib': 65536,
                         'mem_available_kib': 32768, 'packages': ['kmod-tun', 'ip-full', 'jsonfilter', 'conntrack', 'ca-bundle']}),
                    'backend': p.get('backend', 'fw4-nft'),
                    'dns_binary': p.get('dns_binary', '/usr/libexec/csqtt/dnsmasq'), 'packages': [],
                    'dependency_bundle': load(args.dependencies) if args.dependencies else {'indexes': [], 'packages': []}}
        fmt = platform['package_format']
        dependency_names = {d['name'] for d in manifest['dependency_bundle']['packages']}
        for path in sorted(root.glob('*.' + fmt)):
            if path.name in dependency_names:
                continue
            native = path.name.removeprefix(p['id'] + '--')
            pattern = (r'(csqtt-captcha|luci-app-csqtt|csqtt)-([0-9][A-Za-z0-9_.+~-]*)\.apk' if fmt == 'apk'
                       else r'(csqtt-captcha|luci-app-csqtt|csqtt)_([0-9][A-Za-z0-9.+~-]*)_[A-Za-z0-9_.+-]+\.ipk')
            match = re.fullmatch(pattern, native)
            require(match is not None, 'Unexpected package filename')
            dest = root / (p['id'] + '--' + native)
            if path != dest:
                require(not dest.exists(), 'Profile artifact already exists')
                path.rename(dest)
            manifest['packages'].append(describe(dest, role=match[1], version=match[2]))
        name = p['id'] + '-manifest.json'
    else:
        require(args.registry is None and args.dependencies is None, 'Profile is required for portable metadata')
        manifest = {'schema': 1, 'openwrt': '25.12.5', 'target': 'mediatek/filogic', 'architecture': 'aarch64_cortex-a53', 'upstream': UPSTREAM,
                    'packages': [describe(p) for p in sorted(root.glob('*.apk'))]}
        name = 'manifest.json'
    validate(manifest, root)
    data = json.dumps(manifest, indent=2) + '\n'
    (root / name).write_text(data, encoding='utf-8')
    if name != 'manifest.json':
        (root / 'manifest.json').write_text(data, encoding='utf-8')
    entries = [*manifest['packages'], describe(root / name)]
    if manifest['schema'] == 2:
        entries.extend(manifest['dependency_bundle']['packages'])
        for index in manifest['dependency_bundle']['indexes']:
            entries.append(index)
            if 'signature' in index:
                entries.append(index['signature'])
    (root / 'SHA256SUMS').write_text(''.join(f"{p['sha256']}  {p['name']}\n" for p in entries), encoding='ascii')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(str(exc))