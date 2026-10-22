#!/usr/bin/env python3
"""Validate the checked-in build allowlist; never infer a firmware ABI from CPU alone."""
import argparse
import json
import pathlib
import re
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'platforms' / 'registry.json'
RUST_VERSION = '1.97.1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_registry(path=REGISTRY):
    registry = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    require(registry.get('schema') == 1 and isinstance(registry.get('profiles'), list), 'invalid platform registry')
    ids = set()
    for profile in registry['profiles']:
        validate_profile(profile)
        require(profile['id'] not in ids, 'duplicate platform id')
        ids.add(profile['id'])
    require(registry.get('default_profile') in ids, 'missing default profile')
    return registry


def validate_profile(profile):
    require(profile.get('family') == 'official', 'vendor SDK profiles require a separate validated ABI implementation')
    version = profile.get('openwrt', '')
    target = profile.get('target', '')
    arch = profile.get('architecture', '')
    require(re.fullmatch(r'(24\.10|25\.12)\.[0-9]+', version), 'unsupported release family')
    configurations = {
        ('mediatek/filogic', 'aarch64_cortex-a53'): ('aarch64-unknown-linux-musl', 'arm64', 183, 'aarch64', 'qemu-aarch64', 'cortex-a53'),
        ('x86/64', 'x86_64'): ('x86_64-unknown-linux-musl', 'amd64', 62, 'x86_64', 'qemu-x86_64', 'qemu64'),
    }
    require((target, arch) in configurations, 'unsupported CPU/SDK ABI tuple (ARMv7 pending; MIPS32 unsupported)')
    rust, go, machine, compiler, emulator, cpu = configurations[(target, arch)]
    expected_id = f'official-{version}-{target.replace("/", "-")}-{arch}'
    require(profile.get('id') == expected_id, 'platform id does not bind its exact tuple')
    manager, extension = ('opkg', 'ipk') if version.startswith('24.') else ('apk', 'apk')
    require((profile.get('package_manager'), profile.get('package_format')) == (manager, extension), 'package manager/format mismatch')
    require(profile.get('backend') == 'fw4-nft', 'unvalidated firewall backend')
    require((profile.get('rust_target'), profile.get('goarch')) == (rust, go), 'Rust/Go ABI mismatch')
    require(profile.get('elf') == {'class': 64, 'endian': 'little', 'machine': machine}, 'ELF ABI mismatch')
    require(profile.get('emulator') == {'command': emulator, 'cpu': cpu}, 'CPU emulator mismatch')
    sdk = profile.get('sdk', {})
    name = sdk.get('name', '')
    require(re.fullmatch(r'openwrt-sdk-' + re.escape(version + '-' + target.replace('/', '-')) + r'_gcc-[0-9.]+_musl\.Linux-x86_64', name), 'SDK name mismatch')
    base = f'https://downloads.openwrt.org/releases/{version}/targets/{target}/'
    require(sdk.get('url') == base + name + '.tar.zst' and sdk.get('checksum_url') == base + 'sha256sums', 'SDK origin/tuple mismatch')
    require(re.fullmatch(r'[0-9a-f]{64}', sdk.get('sha256', '')), 'missing pinned SDK hash')
    require(sdk.get('toolchain_prefix') == compiler + '-openwrt-linux-musl', 'SDK linker ABI mismatch')
    require(sdk.get('toolchain_dir_glob') == 'toolchain-' + compiler + '*', 'SDK toolchain directory mismatch')
    qualification = profile.get('qualification', {})
    require(all(type(qualification.get(key)) is bool for key in ('installation', 'activation')), 'qualification flags must be explicit booleans')
    require(isinstance(qualification.get('reason'), str) and qualification['reason'], 'missing qualification reason')
    require(not qualification['activation'] or qualification['installation'], 'activation requires installation qualification')
    if qualification['installation']:
        require(bool(qualification.get('evidence')), 'qualification requires reviewed evidence')


def select_profile(registry, profile_id=None):
    wanted = profile_id or registry['default_profile']
    for profile in registry['profiles']:
        if profile['id'] == wanted:
            return profile
    raise ValueError('unknown or held platform profile; no CPU-only fallback is allowed')


def shell_environment(profile):
    sdk = profile['sdk']
    values = {
        'PROFILE_ID': profile['id'], 'SDK_VERSION': profile['openwrt'], 'SDK_NAME': sdk['name'],
        'SDK_SHA': sdk['sha256'], 'SDK_URL': sdk['url'], 'SDK_TOOLCHAIN_GLOB': sdk['toolchain_dir_glob'],
        'SDK_TOOLCHAIN_PREFIX': sdk['toolchain_prefix'], 'RUST_TARGET': profile['rust_target'],
        'RUST_VERSION': RUST_VERSION, 'PACKAGE_FORMAT': profile['package_format'],
        'PACKAGE_ARCH': profile['architecture'], 'GOARCH': profile['goarch'],
        'FIREWALL_BACKEND': profile['backend'], 'EMULATOR': profile['emulator']['command'],
    }
    return ''.join(f'{name}={shlex.quote(value)}\n' for name, value in values.items())


def verify_sdk(profile, sdk, check_compiler=True):
    sdk = pathlib.Path(sdk)
    config = (sdk / '.config').read_text(encoding='utf-8')
    values = dict(re.findall(r'^(CONFIG_[A-Z0-9_]+)="([^"\n]*)"$', config, re.MULTILINE))
    board, subtarget = profile['target'].split('/')
    for key, expected in [('CONFIG_TARGET_BOARD', board), ('CONFIG_TARGET_SUBTARGET', subtarget),
                          ('CONFIG_TARGET_ARCH_PACKAGES', profile['architecture'])]:
        require(values.get(key) == expected, f'SDK {key} differs from allowlisted ABI')
    toolchains = sorted((sdk / 'staging_dir').glob(profile['sdk']['toolchain_dir_glob']))
    require(len(toolchains) == 1 and toolchains[0].is_dir(), 'SDK must contain exactly one matching toolchain')
    toolchain = toolchains[0]
    prefix = profile['sdk']['toolchain_prefix']
    if check_compiler:
        gcc = toolchain / 'bin' / (prefix + '-gcc')
        result = subprocess.run([str(gcc), '-dumpmachine'], check=True, capture_output=True, text=True, timeout=15)
        require(result.stdout.strip() == prefix, 'SDK compiler target differs from allowlisted ABI')
    return toolchain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=pathlib.Path, default=REGISTRY)
    parser.add_argument('--profile')
    parser.add_argument('--format', choices=('json', 'shell', 'ids'), default='json')
    parser.add_argument('--verify-sdk', type=pathlib.Path)
    args = parser.parse_args()
    registry = load_registry(args.registry)
    if args.format == 'ids':
        print('\n'.join(profile['id'] for profile in registry['profiles']))
        return
    profile = select_profile(registry, args.profile)
    if args.verify_sdk:
        print(verify_sdk(profile, args.verify_sdk))
    elif args.format == 'shell':
        print(shell_environment(profile), end='')
    else:
        print(json.dumps(profile, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'platform registry: {error}') from None
