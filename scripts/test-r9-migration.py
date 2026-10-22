#!/usr/bin/env python3
"""Native signed ARM r9 -> candidate -> r9 transactions in a disposable root.

Package scripts are intentionally disabled: this proves APK solving, payloads,
offline rollback and persistent-file preservation, not real router services/VK.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import tarfile
import tempfile
import urllib.request

from release_schema import load, require, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILE = 'official-25.12.5-mediatek-filogic-aarch64_cortex-a53'
ASSETS = {
    'csqtt-0.1.0-r9.apk': 'aa84382367156b4f97ce292ff166336f62ee2f30da3324e93ddc00835b6d36d9',
    'csqtt-captcha-0.1.0-r9.apk': 'dd3281ddecf26d33662f33352d7125a217325cb96f22b0b22f8838900d02a69c',
    'luci-app-csqtt-0.1.0-r9.apk': '2eb828c43fc1c24b4c0da3274294adb79eca50f709ffb67ae5190bfbb03c86c9',
    'manifest.json': '783a28411c37477bc5e766ab085a79a872908a74aacf6285041e005fc73376e5',
    'manifest.sig': '6ad047b63679adbfa5b6d30b61a13963129b5cfb53c65a65f2c7db17dff8544d',
}
CHECKS = {'public_signed_r9', 'native_apk_upgrade', 'native_apk_rollback',
          'settings_identity_budget_preserved', 'offline_upgrade_rollback', 'package_scripts_disabled'}


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=pathlib.Path)
    parser.add_argument('--apk', required=True, type=pathlib.Path)
    parser.add_argument('--source-commit', required=True, help='Caller binds the checked-out source before sudo changes user')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Disposable native APK transactions require CI root')
    require(re.fullmatch('[0-9a-f]{40}', args.source_commit), 'Invalid checked-out source commit')
    directory = args.directory.resolve()
    manifest = validate(load(directory / (PROFILE + '-manifest.json')), directory)
    require(manifest['profile_id'] == PROFILE, 'Only the original exact r9 tuple is valid')
    bundle, evidence = module('bundle', 'bundle-dependencies.py'), module('evidence', 'release-evidence.py')
    with tempfile.TemporaryDirectory(prefix='csqtt-r9-migration-') as temporary:
        work = pathlib.Path(temporary)
        guest = work / 'root'
        keys = guest / 'etc/apk/keys'
        keys.mkdir(parents=True)
        archive = work / 'rootfs.tar.gz'
        suffix, digest = bundle.ROOTFS['25.12.5']
        bundle.download('https://downloads.openwrt.org/releases/25.12.5/targets/x86/64/openwrt-25.12.5-x86-64-' + suffix, archive, digest)
        with tarfile.open(archive, 'r:gz') as stream:
            for entry in stream:
                name = entry.name.removeprefix('./')
                if name.startswith(('etc/apk/keys/', 'lib/apk/keys/')) and entry.isfile():
                    require(0 < entry.size <= 8192, 'Invalid public key')
                    body = stream.extractfile(entry).read()
                    (keys / (hashlib.sha256(body).hexdigest() + '.pem')).write_bytes(body)
        require(any(keys.iterdir()), 'Missing authenticated distribution keys')
        (keys / 'csqtt.pem').write_bytes((ROOT / 'release/csqtt-public.pem').read_bytes())
        old = work / 'r9'
        old.mkdir()
        for name, digest in ASSETS.items():
            url = 'https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.9/' + name
            with urllib.request.urlopen(url, timeout=60) as response:
                require(response.url.startswith(('https://github.com/', 'https://release-assets.githubusercontent.com/')), 'Foreign asset redirect')
                data = response.read(16 * 1024 * 1024 + 1)
            require(0 < len(data) <= 16 * 1024 * 1024 and hashlib.sha256(data).hexdigest() == digest, 'Frozen r9 asset digest mismatch')
            (old / name).write_bytes(data)
        subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(ROOT / 'release/csqtt-public.pem'),
                        '-signature', str(old / 'manifest.sig'), str(old / 'manifest.json')], check=True, capture_output=True)
        validate(load(old / 'manifest.json'), old)
        repositories = guest / 'etc/apk/repositories'
        repositories.write_text(''.join(i['repository'] + '/packages.adb\n' for i in manifest['dependency_bundle']['indexes']))
        (guest / 'var/cache/apk').mkdir(parents=True)
        env = {**os.environ, 'APK_CONFIG': '/dev/null'}
        base = [str(args.apk.resolve()), '--root', str(guest), '--arch', 'aarch64_cortex-a53',
                '--keys-dir', 'etc/apk/keys', '--cache-dir', 'var/cache/apk']

        def apk(*command):
            scripts = ['--no-scripts'] if 'add' in command or 'del' in command else []
            return subprocess.run([*base, *scripts, *map(str, command)], check=True, capture_output=True, env=env, timeout=300)

        old_packages = sorted(old.glob('*.apk'))
        apk('--no-network', 'add', '--initdb')
        apk('update')
        for path in [*old_packages, *(directory / p['name'] for p in manifest['packages'])]:
            apk('verify', path)
        apk('--cache-predownload', 'add', '--initdb', *old_packages)
        configs = {
            'etc/config/csqtt': b"config client 'main'\n option enabled '0'\n option workers '72'\n option auto_recover '1'\n",
            'etc/csqtt/device-id': b'public synthetic identity fixture\n',
            'var/run/csqtt/health-state.json': b'{"schema":1,"attempts":[1,2]}\n',
            'etc/config/dhcp': b'public unchanged DHCP fixture\n',
            'etc/config/network': b'public unchanged LAN fixture\n',
            'etc/config/firewall': b'public unchanged firewall fixture\n',
        }
        for name, body in configs.items():
            path = guest / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        world = (guest / 'etc/apk/world').read_bytes()
        new_packages = [directory / p['name'] for p in manifest['packages']]
        dependencies = [directory / p['name'] for p in manifest['dependency_bundle']['packages']]
        apk('--no-network', 'add', *new_packages, *dependencies)
        query = json.loads(apk('--no-network', 'query', '--installed', '--all-matches', '--fields', 'name,version', '--format', 'json', '*').stdout)
        versions = {p['name']: p['version'] for p in query}
        require(all(versions.get(p['role']) == p['version'] for p in manifest['packages']), 'Candidate versions not installed')
        require(all((guest / p).read_bytes() == body for p, body in configs.items()), 'Upgrade changed persistent owner data')
        apk('--no-network', 'add', *old_packages)
        query = json.loads(apk('--no-network', 'query', '--installed', '--all-matches', '--fields', 'name,version', '--format', 'json', '*').stdout)
        versions = {p['name']: p['version'] for p in query}
        require(all(versions.get(p) == '0.1.0-r9' for p in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt')), 'r9 rollback versions not restored')
        require(all((guest / p).read_bytes() == body for p, body in configs.items()), 'Rollback changed persistent owner data')
        # Explicit dependency operands are temporary transaction roots. Restore
        # the exact original world only after native rollback has succeeded.
        (guest / 'etc/apk/world').write_bytes(world)
        apk('--no-network', 'add', '--simulate')
        result = {'schema': 1, 'kind': 'native_r9_migration', 'result': 'pass',
                  'source_commit': args.source_commit, 'profile_id': PROFILE,
                  'physical_device': False, 'package_scripts': False,
                  'scope': 'disposable_native_apk_transaction_only', 'checks': sorted(CHECKS),
                  'old_assets': ASSETS, 'packages': evidence.package_binding(manifest)}
        (directory / (PROFILE + '-migration-evidence.json')).write_text(json.dumps(result, indent=2) + '\n')
    print('Signed ARM r9/candidate/r9 native APK transactions and persistent files passed; package scripts and real services were not executed.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Native r9 migration transaction failed; qualification was not granted (private native diagnostics omitted).') from None
