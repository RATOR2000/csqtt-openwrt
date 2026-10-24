#!/usr/bin/env python3
"""Read an official *factory* image; emit bounded, public compatibility evidence.

Never executes firmware or exports configuration/credentials. Optional tooling:
pip install dissect.squashfs==1.0. Runtime dependencies are not project packages.
"""
import argparse
import hashlib
import io
import json
import pathlib
import re
import sys

MAX_IMAGE = 256 * 1024 * 1024
MAX_METADATA = 2 * 1024 * 1024
PACKAGES = (
    'kernel', 'libc', 'firewall', 'firewall4', 'iptables', 'ip6tables', 'ipset',
    'nftables', 'nftables-json', 'nftables-nojson', 'libnftnl11', 'libmnl0',
    'kmod-nft-core', 'ucode', 'libucode', 'ucode-mod-fs',
    'ucode-mod-uci', 'ucode-mod-ubus', 'dnsmasq', 'dnsmasq-full', 'kmod-tun',
    'ip-full', 'conntrack', 'rpcd', 'luci-base', 'openssl-util', 'usign',
    'gl-sdk4-firewall', 'gl-sdk4-dns',
)


def parse_release(text):
    # Data only: never source a firmware file in a host shell.
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(DISTRIB_[A-Z_]+)='([^'\r\n]*)'", line)
        if match:
            if match[1] in result:
                raise ValueError('duplicate release metadata field')
            result[match[1]] = match[2]
    required = ('DISTRIB_ID', 'DISTRIB_RELEASE', 'DISTRIB_TARGET', 'DISTRIB_ARCH')
    if not all(result.get(k) for k in required):
        raise ValueError('incomplete OpenWrt release metadata')
    return result


def parse_packages(text):
    result = {}
    for section in text.split('\n\n'):
        fields = {}
        for line in section.splitlines():
            if line.startswith((' ', '\t')) or ': ' not in line:
                continue
            key, value = line.split(': ', 1)
            if key in fields:
                raise ValueError('duplicate package metadata field')
            fields[key] = value
        name = fields.get('Package')
        if not name:
            continue
        if name in result:
            raise ValueError('duplicate installed package')
        result[name] = {k: fields[k] for k in ('Version', 'Architecture', 'Depends', 'Status') if k in fields}
    return result


def inspect(image, expected_sha256=None):
    if image.stat().st_size > MAX_IMAGE:
        raise ValueError('image exceeds size limit')
    data = image.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError('firmware SHA256 mismatch')
    try:
        from dissect.squashfs.squashfs import SquashFS
    except ImportError as exc:
        raise ValueError('install optional dissect.squashfs==1.0 for image inspection') from exc
    # Firmware may have a FIT kernel before SquashFS. Reject multiple valid roots.
    candidates = []
    offset = 0
    attempts = 0
    while True:
        offset = data.find(b'hsqs', offset)
        if offset < 0:
            break
        attempts += 1
        if attempts > 64:
            raise ValueError('too many filesystem candidates')
        try:
            filesystem = SquashFS(io.BytesIO(data[offset:]))
            filesystem.get('/etc/openwrt_release')
            candidates.append((offset, filesystem))
        except Exception:
            pass
        offset += 4
    if len(candidates) != 1:
        raise ValueError('expected exactly one OpenWrt SquashFS root')
    offset, fs = candidates[0]

    def read(name):
        node = fs.get(name)
        if not node.is_file() or node.size > MAX_METADATA:
            raise ValueError('invalid or oversized firmware metadata')
        content = node.open().read(MAX_METADATA + 1)
        if len(content) > MAX_METADATA:
            raise ValueError('oversized firmware metadata')
        return content.decode('utf-8')

    def exists(name):
        try:
            fs.get(name)
            return True
        except FileNotFoundError:
            return False
        except Exception as exc:
            if exc.__class__.__name__ == 'FileNotFoundError':
                return False
            raise

    release = parse_release(read('/etc/openwrt_release'))
    packages = parse_packages(read('/usr/lib/opkg/status'))
    gl_version = read('/etc/glversion').strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', gl_version):
        raise ValueError('invalid GL firmware version')
    feeds = []
    for line in read('/etc/opkg/distfeeds.conf').splitlines():
        parts = line.split()
        if not parts or parts[0].startswith('#'):
            continue
        if len(parts) != 3 or parts[0] != 'src/gz' or not parts[2].startswith('https://fw.gl-inet.com/'):
            raise ValueError('unrecognised vendor feed')
        feeds.append({'name': parts[1], 'url': parts[2]})
    firewall = read('/etc/init.d/firewall')
    capabilities = {name: exists(path) for name, path in {
        'fw3': '/sbin/fw3', 'fw4': '/sbin/fw4', 'iptables': '/usr/sbin/iptables',
        'ipset': '/usr/sbin/ipset', 'nft': '/usr/sbin/nft', 'ucode': '/usr/bin/ucode',
        'mtk_hnat_service': '/etc/init.d/mtkhnat',
        'mtk_hnat_post_hook': '/etc/init.d/mtk-hwnat-post',
        'luci_bundled': '/etc/luci_ipks',
    }.items()}
    capabilities['firewall_calls_fw3'] = bool(re.search(r'^\s*fw3\s', firewall, re.M))
    return {
        'schema': 1, 'evidence_kind': 'offline_factory_image',
        'image': {'sha256': digest, 'size': len(data), 'squashfs_offset': offset},
        'gl_version': gl_version, 'release': release, 'feeds': feeds,
        'packages': {name: packages.get(name) for name in PACKAGES},
        'capabilities': capabilities,
        'qualification': {'install': False, 'activate': False,
                          'reason': 'image inspection does not prove native installation or routing'},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=pathlib.Path)
    parser.add_argument('--sha256', help='require this previously recorded image digest')
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = inspect(args.image, args.sha256)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Firmware inspection failed: {exc}\n')
    payload = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8', newline='\n')
        print(f'Offline image evidence saved: {args.output}')
    else:
        sys.stdout.write(payload)


if __name__ == '__main__':
    main()
