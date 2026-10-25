#!/usr/bin/env python3
"""Cache a complete official-feed closure, with native index authentication.

This producer never executes target packages. A native offline package-manager
transaction remains a separate mandatory release gate.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request

from platforms import load_registry, select_profile
from release_schema import describe, require, token

LIMIT = 64 * 1024 * 1024
DOWNLOAD_STAGES = {'download', 'rootfs', 'profiles', 'feed_index', 'feed_signature', 'payload'}
FIRMWARE = {'kernel', 'libc', 'base-files', 'busybox', 'procd', 'procd-ujail', 'netifd',
            'firewall4', 'nftables-json', 'nftables-nojson', 'dnsmasq', 'dnsmasq-full'}
ROOTFS = {
    '25.12.5': ('rootfs.tar.gz', '2dae4250b1b742062ed5787adcdc9dd6d26c7f69f94ced46548eb512d5957e8a'),
    '24.10.8': ('rootfs.tar.gz', '6c94190246a54088e3984fc0c4cbbb518972abb2b10a28e30a0c41554eea8b9d'),
    '25.12.6': ('rootfs.tar.gz', '55e52bb34de582a1ebe56bd50f94ff54ac7c77f5bca9cae807656d1930456da4'),
}


def download(url, path, digest=None, *, stage='download', index=None):
    require(stage in DOWNLOAD_STAGES and (index is None or type(index) is int and 0 <= index < 4096),
            'Invalid download diagnostic label')
    label = 'stage=' + stage + ('' if index is None else ' index=' + str(index))
    require(url.startswith('https://downloads.openwrt.org/'), 'Foreign download origin')
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            require(response.url.startswith('https://downloads.openwrt.org/'), 'Foreign redirect')
            data = response.read(LIMIT + 1)
    except urllib.error.HTTPError as error:
        status = ' http_status=' + str(error.code) if type(error.code) is int and 100 <= error.code <= 599 else ' http_error'
        raise ValueError('Download failed ' + label + status) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError('Download failed ' + label + ' transport_error') from None
    require(0 < len(data) <= LIMIT, 'Download exceeds bound')
    require(digest is None or hashlib.sha256(data).hexdigest() == digest, 'Download digest mismatch')
    path.write_bytes(data)
    return data


def kernel_feed(profile, data):
    """Discover a path only; authenticated module metadata must confirm its ABI."""
    require(isinstance(data, bytes) and 0 < len(data) <= LIMIT, 'Invalid target profile metadata size/type')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate target profile metadata key')
            result[key] = value
        return result
    try:
        document = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise ValueError('Invalid target profile metadata JSON') from None
    require(isinstance(document, dict), 'Invalid target profile metadata type')
    for field, expected in (('version_number', profile['openwrt']), ('target', profile['target']),
                            ('arch_packages', profile['architecture'])):
        require(type(document.get(field)) is str and document[field] == expected, 'Target profile tuple mismatch')
    kernel = document.get('linux_kernel')
    require(isinstance(kernel, dict), 'Missing target profile kernel metadata')
    for field, pattern in (('version', r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,5}'),
                           ('release', r'[1-9][0-9]{0,6}'), ('vermagic', r'[0-9a-f]{32}')):
        require(type(kernel.get(field)) is str and re.fullmatch(pattern, kernel[field]), 'Invalid target profile kernel metadata')
    directory = kernel['version'] + '-' + kernel['release'] + '-' + kernel['vermagic']
    abi = kernel['version'] + '~' + kernel['vermagic'] + '-r' + kernel['release']
    return directory, abi


def control(text):
    rows = []
    for block in text.strip().split('\n\n'):
        row = {}
        for line in block.splitlines():
            if line[:1].isspace():
                continue
            key, sep, value = line.partition(': ')
            require(sep and key not in row, 'Malformed distribution index')
            row[key] = value
        if row:
            rows.append(row)
    return rows


def split_deps(value):
    if isinstance(value, list):
        return value
    return [d.strip() for d in value.split(',') if d.strip()]


def dep_identity(value):
    require('|' not in value, 'Alternative dependency requires native resolver review')
    value = value.strip().replace('(', '').replace(')', '').replace(' ', '')
    match = re.fullmatch(r'(!?)([A-Za-z0-9][A-Za-z0-9_.+:-]*)([<>=~]*)([A-Za-z0-9_.+~:-]*)', value)
    require(match is not None, 'Invalid dependency expression')
    return match[2], match[3], match[4], bool(match[1])


def module_kernel(row):
    """Use this module's authenticated dependency metadata, never its version."""
    declarations = [dependency for dependency in map(dep_identity, split_deps(row.get('depends', [])))
                    if dependency[0] == 'kernel']
    require(len(declarations) == 1, 'Kernel module requires one exact kernel ABI: ' + row['name'])
    _, operator, version, conflict = declarations[0]
    require(not conflict and operator == '=' and token(version),
            'Kernel module requires one exact kernel ABI: ' + row['name'])
    return version


def closure(rows, roots, *, expected_kernel=None):
    """Select exact identities; conflicting constraints fail before downloads.

    Version range satisfaction is decided by the native offline solver gate,
    never by an approximate Python version ordering.
    """
    names, providers = {}, {}
    for row in rows:
        require(token(row['name']) and token(row['version']), 'Invalid feed package identity')
        existing = names.get(row['name'])
        require(existing is None or existing['version'] == row['version'], 'Ambiguous feed package version')
        if existing is None:
            names[row['name']] = row
        for provided in row.get('provides', []):
            name, _, _, conflict = dep_identity(provided)
            if not conflict:
                providers.setdefault(name, []).append(row)
    selected, required, pending = {}, set(), list(roots)
    kernel = None
    while pending:
        name, operator, version, conflict = dep_identity(pending.pop())
        if conflict or name in {'csqtt', 'csqtt-captcha', 'luci-app-csqtt'}:
            continue
        if name == 'kernel':
            require(operator == '=' and token(version), 'Kernel dependency requires exact ABI')
            require(kernel in (None, version), 'Conflicting kernel ABIs')
            kernel = version
        if name in FIRMWARE:
            required.add(name)
            continue
        row = names.get(name)
        if row is None:
            candidates = providers.get(name, [])
            require(len(candidates) == 1, 'Missing or ambiguous virtual dependency: ' + name)
            row = candidates[0]
        if operator == '=':
            require(row['version'] == version or any(p == name + '=' + version for p in row.get('provides', [])),
                    'Exact dependency version mismatch: ' + name)
        if row['name'] in selected:
            continue
        if row['name'].startswith('kmod-'):
            abi = module_kernel(row)
            require(all(module_kernel(candidate) == abi for candidate in rows if candidate['name'] == row['name']),
                    'Ambiguous feed kernel ABI: ' + row['name'])
            require(kernel in (None, abi), 'Conflicting kernel ABIs')
            kernel = abi
            row = {**row, 'kernel_package': abi}
        selected[row['name']] = row
        require(len(selected) <= 64, 'Dependency closure exceeds bound')
        pending.extend(split_deps(row.get('depends', [])))
    require('kmod-tun' in selected and kernel is not None, 'Missing exact kmod-tun kernel dependency')
    require(expected_kernel is None or token(expected_kernel) and kernel == expected_kernel,
            'Authenticated module kernel ABI differs from target profile metadata')
    return sorted(selected.values(), key=lambda r: r['name']), sorted(required), kernel


def authenticate(tool, fmt, index, signature, keys, work):
    accepted = []
    for key in sorted(keys.iterdir()):
        if fmt == 'apk':
            keyroot = work / 'one-key'
            keyroot.mkdir(exist_ok=True)
            for prior in keyroot.iterdir():
                prior.unlink()
            (keyroot / 'source.pem').write_bytes(key.read_bytes())
            command = [tool, '--keys-dir', str(keyroot), 'verify', str(index)]
        else:
            command = [tool, '-V', '-p', str(key), '-m', str(index), '-x', str(signature)]
        result = subprocess.run(command, capture_output=True, timeout=30)
        if result.returncode == 0:
            accepted.append(key)
    require(len(accepted) == 1, 'Distribution index signer is missing or ambiguous')
    return hashlib.sha256(accepted[0].read_bytes()).hexdigest()


def authenticate_apk_payload(tool, architecture, row, package, index, keys, work):
    """Let native APK extract/verify an unsigned package against its signed index.

    Standalone APK signatures are not required by OpenWrt's index trust model.
    fetch verifies the index identity and every payload hash. Its output MUST be
    new and empty: APK otherwise skips verification for a same-size existing file.
    """
    require(token(row['name']) and token(row['version']) and token(row['filename']), 'Invalid native APK identity')
    require(row.get('arch') in (architecture, 'noarch', 'all') and row.get('hashes'), 'Signed APK index lacks matching architecture/digest')
    keyhash = index['key_sha256']
    key = keys / keyhash
    require(key.is_file() and hashlib.sha256(key.read_bytes()).hexdigest() == keyhash, 'Official signer key pin mismatch')
    info = json.loads(subprocess.run([tool, 'adbdump', '--format', 'json', str(package)],
                                    check=True, capture_output=True, timeout=30).stdout)['info']
    require(all(info.get(field) == row.get(field) for field in ('name', 'version', 'arch')),
            'APK identity differs from authenticated index')
    # The index digest and any hashes exposed by raw package metadata need not
    # share a representation across APK producers. Native fetch binds the
    # signed index identity and then checks every file payload hash.
    root = work / 'native-apk' / row['index'] / row['name']
    require(not root.exists(), 'Native APK verification root must be fresh')
    mirror, fetched, target = root / 'mirror', root / 'fetched', root / 'root'
    for directory in (mirror, fetched, target / 'etc/apk/keys', target / 'var/cache/apk'):
        directory.mkdir(parents=True, exist_ok=False)
    (target / 'etc/apk/keys/source.pem').write_bytes(key.read_bytes())
    shutil.copyfile(package, mirror / row['filename'])
    shutil.copyfile(index['path'], mirror / 'packages.adb')
    repositories = root / 'repositories'
    repositories.write_text((mirror / 'packages.adb').as_uri() + '\n', encoding='utf-8')
    # One authenticated source index has one unambiguous version for this name;
    # closure() rejected version ambiguity already. Bare names avoid APK 3.0.5's
    # ordinary name=version query bug without recursively fetching firmware.
    subprocess.run([tool, '--root', str(target), '--arch', architecture,
                    '--keys-dir', 'etc/apk/keys', '--cache-dir', 'var/cache/apk',
                    '--repositories-file', str(repositories), '--no-network',
                    'fetch', '--output', str(fetched), row['name']],
                   check=True, capture_output=True, timeout=60)
    expected = fetched / row['filename']
    require(list(fetched.iterdir()) == [expected] and expected.is_file() and not expected.is_symlink(),
            'Native authenticated APK fetch returned no exact package or ambiguous output')
    require(expected.read_bytes() == package.read_bytes(), 'Native authenticated APK bytes differ from downloaded package')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--directory', type=pathlib.Path, required=True)
    parser.add_argument('--apk', help='Native SDK apk executable')
    parser.add_argument('--usign', help='Native SDK usign executable')
    args = parser.parse_args()
    profile = select_profile(load_registry(), args.profile)
    fmt, version, arch = (profile[k] for k in ('package_format', 'openwrt', 'architecture'))
    tool = args.apk if fmt == 'apk' else args.usign
    require(tool, 'Native distribution signature verifier is required')
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = f'https://downloads.openwrt.org/releases/{version}/'
    target = base + 'targets/' + profile['target'] + '/'
    with tempfile.TemporaryDirectory(prefix='csqtt-feed-') as temporary:
        work = pathlib.Path(temporary)
        # The same release's pinned x86 rootfs supplies distro public keys only;
        # no x86 runtime/library is ever bundled into another architecture.
        suffix, digest = ROOTFS[version]
        archive = work / 'rootfs.tar.gz'
        download(base + f'targets/x86/64/openwrt-{version}-x86-64-' + suffix, archive, digest, stage='rootfs')
        keys = work / 'keys'
        keys.mkdir()
        with tarfile.open(archive, 'r:gz') as stream:
            for member in stream:
                name = member.name.removeprefix('./')
                keypath = ('etc/apk/keys/', 'lib/apk/keys/') if fmt == 'apk' else ('etc/opkg/keys/',)
                if any(name.startswith(prefix) for prefix in keypath) and member.isfile():
                    require(0 < member.size <= 8192, 'Invalid distribution public key')
                    body = stream.extractfile(member).read()
                    (keys / hashlib.sha256(body).hexdigest()).write_bytes(body)
        require(any(keys.iterdir()), 'Pinned rootfs has no distribution keys')
        metadata = download(target + 'profiles.json', work / 'profiles.json', stage='profiles')
        kernel_directory, expected_kernel = kernel_feed(profile, metadata)
        repositories = [target + 'packages/', target + 'kmods/' + kernel_directory + '/',
                        *(base + f'packages/{arch}/{feed}/' for feed in ('base', 'luci', 'packages', 'routing'))]
        indexes, rows = [], []
        for number, repository in enumerate(repositories):
            ident = 'feed' + str(number)
            name = profile['id'] + '--' + ident + ('.adb' if fmt == 'apk' else '.Packages')
            path = out / name
            download(repository + ('packages.adb' if fmt == 'apk' else 'Packages'), path, stage='feed_index', index=number)
            sig = None
            if fmt == 'ipk':
                sig = out / (name + '.sig')
                download(repository + 'Packages.sig', sig, stage='feed_signature', index=number)
            fingerprint = authenticate(tool, fmt, path, sig, keys, work)
            index = describe(path, id=ident, repository=repository.rstrip('/'),
                             format='apk-adb' if fmt == 'apk' else 'opkg', key_sha256=fingerprint)
            if sig:
                index['signature'] = describe(sig)
            indexes.append(index)
            if fmt == 'apk':
                result = subprocess.run([tool, 'adbdump', '--format', 'json', str(path)],
                                        check=True, capture_output=True, timeout=60)
                document = json.loads(result.stdout)
                require(document.get('pkgname-spec', '${name}-${version}.apk') == '${name}-${version}.apk', 'Unexpected native APK filename pattern')
                records = document['packages']
                for row in records:
                    if row.get('arch') in (arch, 'noarch', 'all'):
                        rows.append({**row, 'index': ident, 'repository': repository,
                                     'filename': row['name'] + '-' + row['version'] + '.apk'})
            else:
                for row in control(path.read_text()):
                    if row.get('Architecture') in (arch, 'all'):
                        rows.append({'name': row['Package'], 'version': row['Version'], 'index': ident,
                                     'repository': repository, 'filename': row['Filename'],
                                     'digest': row['SHA256sum'], 'size': int(row['Size']),
                                     'depends': split_deps(row.get('Depends', '')),
                                     'provides': split_deps(row.get('Provides', ''))})
        roots = []
        if fmt == 'apk':
            for package in sorted(out.glob('*.apk')):
                info = json.loads(subprocess.run([tool, 'adbdump', '--format', 'json', str(package)],
                                                check=True, capture_output=True, timeout=30).stdout)['info']
                roots.extend(info.get('depends', []))
        else:
            spec = importlib.util.spec_from_file_location('native_ipk', pathlib.Path(__file__).with_name('test-native-ipk.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for package in sorted(out.glob('*.ipk')):
                roots.extend(split_deps(module.read_ipk(package)[0].get('Depends', '')))
        require(roots, 'No application dependency metadata')
        selected, required, kernel = closure(rows, roots, expected_kernel=expected_kernel)
        packages = []
        for number, row in enumerate(selected):
            require(token(row['filename']), 'Unsafe upstream package filename')
            path = out / (profile['id'] + '--dep--' + row['filename'])
            download(row['repository'] + row['filename'], path, row.get('digest'), stage='payload', index=number)
            if fmt == 'ipk':
                require(path.stat().st_size == row['size'], 'Distribution package size mismatch')
            else:
                # OpenWrt signs the index; packages may legitimately be unsigned.
                # Exact metadata equality is necessary but cannot verify payload
                # contents by itself. Native fetch below verifies both through
                # this same immutable signed source index and official key.
                index = indexes[int(row['index'][4:])]
                authenticate_apk_payload(tool, arch, row, path,
                                         {**index, 'path': out / index['name']}, keys, work)
            entry = describe(path, package=row['name'], version=row['version'], index=row['index'], filename=row['filename'])
            if row['name'].startswith('kmod-'):
                entry['kernel_package'] = row['kernel_package']
            packages.append(entry)
        bundle = {'indexes': indexes, 'packages': packages,
                  'requirements': {'kernel_package': kernel, 'packages': sorted(set(required) | {r['name'] for r in selected})}}
        (out / 'dependencies.json').write_text(json.dumps(bundle, indent=2) + '\n')
        print(f'Authenticated {len(indexes)} native feed indexes; cached {len(packages)} exact dependencies. Offline native transaction still required.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('dependency bundle: ' + str(error)) from None
