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
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import urllib.error

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
ROLES = {'csqtt', 'csqtt-captcha', 'luci-app-csqtt'}
PHASES = {'arguments', 'candidate_manifest', 'rootfs_keys', 'r9_download', 'r9_manifest_signature',
          'r9_manifest_validate', 'native_database_init', 'online_indexes', 'project_package_signatures',
          'seed_signed_r9', 'baseline_inventory', 'offline_repository_index', 'offline_dependency_payload',
          'offline_upgrade', 'upgrade_inventory', 'offline_rollback', 'rollback_cleanup', 'rollback_inventory',
          'world_restore', 'world_simulation', 'evidence_write', 'complete'}
PHASE = 'arguments'


def phase(name):
    global PHASE
    require(name in PHASES, 'Invalid migration phase')
    PHASE = name
    print('Native r9 migration stage=' + name, flush=True)


def failure_message(error):
    # Classify bounded native stderr into fixed enums; never print its text,
    # command arguments, download URLs, paths, keys or exception messages.
    category = type(error).__name__
    category = category if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', category) else 'Exception'
    result = 'Native r9 migration failed stage=' + PHASE + ' exception=' + category
    if isinstance(error, subprocess.CalledProcessError):
        raw = error.stderr or b''
        text = (raw[:8192].decode(errors='replace') if isinstance(raw, bytes) else raw[:8192]).lower()
        kind = 'other'
        if 'signature' in text or 'untrusted' in text:
            kind = 'signature'
        elif 'dnsmasq' in text and any(word in text for word in ('conflict', 'breaks', 'unable to select')):
            kind = 'dns_provider_conflict'
        elif any(word in text for word in ('unable to select', 'conflict', 'breaks', 'no such package')):
            kind = 'dependency_solver'
        result += ' native_failure=' + kind
    if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
        result += ' http_status=' + str(error.code)
    return result + '; qualification was not granted.'


def installed_versions(apk):
    query = json.loads(apk('--no-network', 'query', '--installed', '--all-matches',
                           '--fields', 'name,version', '--format', 'json', '*').stdout)
    require(isinstance(query, list), 'Invalid native installed package inventory')
    result = {}
    for row in query:
        require(isinstance(row, dict) and isinstance(row.get('name'), str) and isinstance(row.get('version'), str)
                and row['name'] not in result, 'Ambiguous native installed package inventory')
        result[row['name']] = row['version']
    return result


def native_apk(base, env, *command):
    scripts = ['--no-scripts'] if 'add' in command or 'del' in command else []
    return subprocess.run([*base, *scripts, *map(str, command)], check=True,
                          capture_output=True, env=env, timeout=300)


def store_distribution_key(keys, body):
    # The shared authenticated-payload verifier resolves official keys by their
    # exact SHA256 filename, without an extension.
    target = keys / hashlib.sha256(body).hexdigest()
    target.write_bytes(body)
    return target


def prepare_offline_repository(directory, manifest, work, distribution_keys, tool, bundle):
    """Authenticate exact signed indexes/payloads before the offline transaction."""
    repositories, indexes, rows = work / 'offline-repositories', {}, {}
    for index in manifest['dependency_bundle']['indexes']:
        phase('offline_repository_index')
        path = directory / index['name']
        fingerprint = bundle.authenticate(str(tool), 'apk', path, None, distribution_keys, work)
        require(fingerprint == index['key_sha256'], 'Dependency index official signer pin mismatch')
        document = json.loads(subprocess.run([str(tool), 'adbdump', '--format', 'json', str(path)],
                                             check=True, capture_output=True, timeout=60).stdout)
        require(document.get('pkgname-spec', '${name}-${version}.apk') == '${name}-${version}.apk',
                'Unexpected signed APK filename pattern')
        mirror = work / 'offline-mirror' / index['id']
        mirror.mkdir(parents=True)
        shutil.copyfile(path, mirror / 'packages.adb')
        indexes[index['id']] = {**index, 'path': path, 'mirror': mirror}
        rows[index['id']] = document['packages']
    for package in manifest['dependency_bundle']['packages']:
        phase('offline_dependency_payload')
        index = indexes[package['index']]
        matches = [row for row in rows[package['index']] if row.get('name') == package['package']
                   and row.get('version') == package['version']
                   and row.get('arch') in ('aarch64_cortex-a53', 'noarch', 'all')]
        require(len(matches) == 1 and package['filename'] == package['package'] + '-' + package['version'] + '.apk',
                'Dependency identity does not select one exact signed index record')
        row = {**matches[0], 'filename': package['filename'], 'index': package['index']}
        # Reuse the producer's native file:// fetch: private pinned signer only,
        # fresh empty output, metadata + every payload hash, exact returned bytes.
        bundle.authenticate_apk_payload(str(tool), 'aarch64_cortex-a53', row, directory / package['name'],
                                        index, distribution_keys, work)
        target = index['mirror'] / package['filename']
        require(not target.exists(), 'Ambiguous offline dependency filename')
        shutil.copyfile(directory / package['name'], target)
    repositories.write_text(''.join((index['mirror'] / 'packages.adb').as_uri() + '\n'
                                   for index in indexes.values()), encoding='utf-8')
    return repositories


def preserved_inventory(before, after, introduced):
    require(all(after.get(name) == version for name, version in before.items() if name not in ROLES),
            'Migration changed an existing non-project package or DNS provider')
    require(set(after) <= set(before) | set(introduced) | ROLES, 'Migration installed an unbundled dependency')


def run_transactions(apk, manifest, directory, old_packages, guest, repositories, empty_repositories):
    phase('baseline_inventory')
    before = installed_versions(apk)
    require(all(before.get(role) == '0.1.0-r9' for role in ROLES) and before.get('dnsmasq-full'),
            'Signed r9 baseline or its existing full DNS provider is missing')
    world = (guest / 'etc/apk/world').read_bytes()
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
    introduced = {p['package']: p['version'] for p in manifest['dependency_bundle']['packages']
                  if p['package'] not in before}
    phase('offline_upgrade')
    apk('--repositories-file', repositories, '--no-network', 'add',
        *(directory / p['name'] for p in manifest['packages']),
        *(name + '=' + version for name, version in introduced.items()))
    phase('upgrade_inventory')
    upgraded = installed_versions(apk)
    require(all(upgraded.get(p['role']) == p['version'] for p in manifest['packages']), 'Candidate versions not installed')
    require(all(upgraded.get(name) == version for name, version in introduced.items()), 'Exact new dependency versions not installed')
    preserved_inventory(before, upgraded, introduced)
    require(all((guest / path).read_bytes() == body for path, body in configs.items()), 'Upgrade changed persistent owner data')
    phase('offline_rollback')
    apk('--repositories-file', empty_repositories, '--no-network', 'add', *old_packages)
    phase('rollback_cleanup')
    if introduced:
        apk('--repositories-file', empty_repositories, '--no-network', 'del', *introduced)
    phase('rollback_inventory')
    require(installed_versions(apk) == before, 'r9 rollback did not restore the complete package inventory')
    require(all((guest / path).read_bytes() == body for path, body in configs.items()), 'Rollback changed persistent owner data')
    phase('world_restore')
    (guest / 'etc/apk/world').write_bytes(world)
    phase('world_simulation')
    apk('--repositories-file', empty_repositories, '--no-network', 'add', '--simulate')
    require((guest / 'etc/apk/world').read_bytes() == world and installed_versions(apk) == before,
            'Final world proof changed restored state')
    return {'preserved_dns_provider': 'dnsmasq-full', 'package_inventory_restored': True}


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    phase('arguments')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=pathlib.Path)
    parser.add_argument('--apk', required=True, type=pathlib.Path)
    parser.add_argument('--source-commit', required=True, help='Caller binds the checked-out source before sudo changes user')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Disposable native APK transactions require CI root')
    require(re.fullmatch('[0-9a-f]{40}', args.source_commit), 'Invalid checked-out source commit')
    directory = args.directory.resolve()
    phase('candidate_manifest')
    manifest = validate(load(directory / (PROFILE + '-manifest.json')), directory)
    require(manifest['profile_id'] == PROFILE, 'Only the original exact r9 tuple is valid')
    output = directory / (PROFILE + '-migration-evidence.json')
    output.unlink(missing_ok=True)
    bundle, evidence = module('bundle', 'bundle-dependencies.py'), module('evidence', 'release-evidence.py')
    with tempfile.TemporaryDirectory(prefix='csqtt-r9-migration-') as temporary:
        work = pathlib.Path(temporary)
        guest = work / 'root'
        keys = guest / 'etc/apk/keys'
        keys.mkdir(parents=True)
        archive = work / 'rootfs.tar.gz'
        phase('rootfs_keys')
        suffix, digest = bundle.ROOTFS['25.12.5']
        bundle.download('https://downloads.openwrt.org/releases/25.12.5/targets/x86/64/openwrt-25.12.5-x86-64-' + suffix, archive, digest)
        with tarfile.open(archive, 'r:gz') as stream:
            for entry in stream:
                name = entry.name.removeprefix('./')
                if name.startswith(('etc/apk/keys/', 'lib/apk/keys/')) and entry.isfile():
                    require(0 < entry.size <= 8192, 'Invalid public key')
                    body = stream.extractfile(entry).read()
                    store_distribution_key(keys, body)
        require(any(keys.iterdir()), 'Missing authenticated distribution keys')
        (keys / 'csqtt.pem').write_bytes((ROOT / 'release/csqtt-public.pem').read_bytes())
        old = work / 'r9'
        old.mkdir()
        phase('r9_download')
        for name, digest in ASSETS.items():
            url = 'https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.9/' + name
            with urllib.request.urlopen(url, timeout=60) as response:
                require(response.url.startswith(('https://github.com/', 'https://release-assets.githubusercontent.com/')), 'Foreign asset redirect')
                data = response.read(16 * 1024 * 1024 + 1)
            require(0 < len(data) <= 16 * 1024 * 1024 and hashlib.sha256(data).hexdigest() == digest, 'Frozen r9 asset digest mismatch')
            (old / name).write_bytes(data)
        phase('r9_manifest_signature')
        subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(ROOT / 'release/csqtt-public.pem'),
                        '-signature', str(old / 'manifest.sig'), str(old / 'manifest.json')], check=True, capture_output=True)
        phase('r9_manifest_validate')
        validate(load(old / 'manifest.json'), old)
        repositories = guest / 'etc/apk/repositories'
        repositories.write_text(''.join(i['repository'] + '/packages.adb\n' for i in manifest['dependency_bundle']['indexes']))
        (guest / 'var/cache/apk').mkdir(parents=True)
        env = {**os.environ, 'APK_CONFIG': '/dev/null'}
        base = [str(args.apk.resolve()), '--root', str(guest), '--arch', 'aarch64_cortex-a53',
                '--keys-dir', 'etc/apk/keys', '--cache-dir', 'var/cache/apk']

        def apk(*command):
            return native_apk(base, env, *command)

        old_packages = sorted(old.glob('*.apk'))
        phase('native_database_init')
        apk('--no-network', 'add', '--initdb')
        phase('online_indexes')
        apk('update')
        phase('project_package_signatures')
        for path in [*old_packages, *(directory / p['name'] for p in manifest['packages'])]:
            apk('verify', path)
        phase('seed_signed_r9')
        # Historical r9 installation explicitly rooted its system DNS provider.
        apk('--cache-predownload', 'add', '--initdb', *old_packages, 'dnsmasq-full')
        offline = prepare_offline_repository(directory, manifest, work, keys, args.apk.resolve(), bundle)
        empty = work / 'empty-repositories'
        empty.write_text('', encoding='ascii')
        migration = run_transactions(apk, manifest, directory, old_packages, guest, offline, empty)
        phase('evidence_write')
        result = {'schema': 1, 'kind': 'native_r9_migration', 'result': 'pass',
                  'source_commit': args.source_commit, 'profile_id': PROFILE,
                  'physical_device': False, 'package_scripts': False,
                  'scope': 'disposable_native_apk_transaction_only', 'checks': sorted(CHECKS),
                  'old_assets': ASSETS, 'packages': evidence.package_binding(manifest), **migration}
        output.write_text(json.dumps(result, indent=2) + '\n')
    phase('complete')
    print('Signed ARM r9/candidate/r9 native APK transactions and persistent files passed; package scripts and real services were not executed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(failure_message(error)) from None
