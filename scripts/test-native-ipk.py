#!/usr/bin/env python3
"""Inspect SDK IPKs without executing package scripts; smoke static payloads in isolation."""
import argparse
import io
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile

from platforms import ROOT, load_registry, select_profile

LIMIT = 128 * 1024 * 1024


def tar_members(data):
    result = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        for member in archive:
            name = member.name.removeprefix('./').rstrip('/')
            if not name:
                continue
            if name.startswith('/') or '..' in pathlib.PurePosixPath(name).parts or name in result:
                raise ValueError('unsafe or duplicate package path')
            if member.isdir():
                continue
            if not member.isfile() or member.size < 0 or member.size > LIMIT:
                raise ValueError('non-regular or oversized package member')
            total += member.size
            if total > LIMIT:
                raise ValueError('package uncompressed data exceeds limit')
            result[name] = (archive.extractfile(member).read(), member.mode & 0o7777)
    return result


def outer_members(data):
    if not data.startswith(b'!<arch>\n'):
        return tar_members(data)
    result = {}
    offset = 8
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b'`\n':
            raise ValueError('invalid IPK ar header')
        name = header[:16].decode('ascii').strip().rstrip('/')
        size = int(header[48:58].strip())
        offset += 60
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', name) or name in result or size < 0 or offset + size > len(data):
            raise ValueError('unsafe or truncated IPK ar member')
        result[name] = (data[offset:offset + size], 0)
        offset += size + size % 2
    return result


def read_ipk(path):
    path = pathlib.Path(path)
    if not 1 <= path.stat().st_size <= LIMIT:
        raise ValueError('IPK exceeds size bound')
    outer = outer_members(path.read_bytes())
    if outer.get('debian-binary', (None,))[0] != b'2.0\n':
        raise ValueError('invalid IPK format marker')
    controls = [body for name, (body, _) in outer.items() if re.fullmatch(r'control\.tar\.(gz|xz|bz2)', name)]
    payloads = [body for name, (body, _) in outer.items() if re.fullmatch(r'data\.tar\.(gz|xz|bz2)', name)]
    if len(controls) != 1 or len(payloads) != 1 or len(outer) != 3:
        raise ValueError('IPK must contain exactly control/data/format marker')
    control = tar_members(controls[0])
    if 'control' not in control:
        raise ValueError('missing IPK control metadata')
    metadata = {}
    for line in control['control'][0].decode('utf-8').splitlines():
        if not line or line[0].isspace():
            continue
        key, separator, value = line.partition(':')
        if not separator or key in metadata:
            raise ValueError('duplicate or malformed IPK metadata')
        metadata[key] = value.strip()
    return metadata, tar_members(payloads[0])


def inspect(directory, profile):
    expected = {'csqtt', 'csqtt-captcha', 'luci-app-csqtt'}
    found = {}
    paths = sorted(pathlib.Path(directory).glob('*.ipk'))
    if len(paths) != 3:
        raise ValueError('expected exactly three SDK IPKs')
    for path in paths:
        metadata, payload = read_ipk(path)
        name = metadata.get('Package')
        if name not in expected or name in found:
            raise ValueError('duplicate or unexpected IPK role')
        architecture = metadata.get('Architecture')
        if architecture != (profile['architecture'] if name != 'luci-app-csqtt' else 'all'):
            raise ValueError('IPK architecture differs from selected SDK tuple')
        if not re.fullmatch(r'[A-Za-z0-9.+~_-]+', metadata.get('Version', '')):
            raise ValueError('invalid IPK version')
        found[name] = payload
    for name, required in {
        'csqtt': {'usr/bin/csqtt-client': 0o755, 'etc/config/csqtt': 0o600,
                  'usr/libexec/csqtt/platform-probe': 0o755, 'usr/libexec/csqtt/dnsmasq': 0o755,
                  'usr/share/csqtt/policy.uc': 0o644, 'usr/share/csqtt/runtime.uc': 0o644,
                  'usr/share/csqtt/health.uc': 0o644, 'etc/init.d/csqtt': 0o755,
                  'usr/share/licenses/csqtt/LICENSE': 0o644},
        'csqtt-captcha': {'usr/bin/csqtt-captcha': 0o755, 'etc/init.d/csqtt-captcha': 0o755},
        'luci-app-csqtt': {'usr/libexec/rpcd/csqtt': 0o755, 'usr/share/rpcd/acl.d/luci-app-csqtt.json': 0o644},
    }.items():
        for relative, mode in required.items():
            if relative not in found[name] or found[name][relative][1] != mode or not found[name][relative][0]:
                raise ValueError('required IPK payload or permissions differ')
    if found['csqtt']['usr/share/licenses/csqtt/LICENSE'][0] != (ROOT / 'vendor/csqtt/LICENSE').read_bytes():
        raise ValueError('upstream license payload differs')
    if found['csqtt']['etc/config/csqtt'][0] != (ROOT / 'openwrt/csqtt/files/csqtt.config').read_bytes():
        raise ValueError('private default UCI payload differs')
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('directory')
    args = parser.parse_args()
    profile = select_profile(load_registry(), args.profile)
    if profile['package_format'] != 'ipk':
        raise ValueError('selected profile is not an IPK ABI')
    found = inspect(args.directory, profile)
    with tempfile.TemporaryDirectory(prefix='csqtt-native-ipk-') as directory:
        root = pathlib.Path(directory)
        for name, role, path in [('client', 'csqtt', 'usr/bin/csqtt-client'),
                                  ('broker', 'csqtt-captcha', 'usr/bin/csqtt-captcha')]:
            binary = root / name
            binary.write_bytes(found[role][path][0])
            binary.chmod(0o700)
        subprocess.run([sys.executable, str(ROOT / 'scripts/test-platform.py'), '--profile', profile['id'],
                        str(root / 'client'), str(root / 'broker')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts/test-arm64-tun.py'), str(root / 'client'),
                        '--profile', profile['id']], check=True)
    print('Native IPK payload/ISA/TUN checks passed; package scripts not executed; no opkg transaction or router acceptance.')


if __name__ == '__main__':
    main()
