#!/usr/bin/env python3
"""DIAGNOSTIC ONLY: execute pinned public target APK against a fresh public DB.

Inputs are fixed official firmware bytes, the repository PUBLIC key and only
hash-bound build assets from .work/diagnostic-vm. No router files or identities.
The native add has --no-network --no-scripts. This never qualifies a release.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_schema import require

PROFILE = 'official-25.12.6-x86-64-x86_64'
PROJECT_KEY_SHA = '39259baf94d83602c784b103506445cd7e26ec9c3635cc277b90ff31fe4d4bac'
LIMIT = 64 * 1024 * 1024
PUBLIC_ENV = {'APK_CONFIG': '/dev/null', 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TERM': 'dumb', 'NO_COLOR': '1',
              'OPENSSL_CONF': '/dev/null', 'SSL_CERT_FILE': '/dev/null'}


def name(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+~-]{0,250}', value),
            'Unsafe public asset identity')
    return value


def archive_path(value, base=''):
    require(type(value) is str and '\\' not in value and '\x00' not in value,
            'Unsafe archive path')
    parts = [] if value.startswith('/') else list(pathlib.PurePosixPath(base).parts)
    for part in value.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            require(parts, 'Archive path escapes root')
            parts.pop()
        else:
            parts.append(part)
    return '/'.join(parts)


class PublicArchive:
    def __init__(self, archive):
        self.stream = tarfile.open(archive, 'r:gz')
        self.members = {}
        for member in self.stream:
            key = archive_path(member.name)
            require(key not in self.members, 'Duplicate public archive path')
            self.members[key] = member
            require(len(self.members) <= 20000, 'Public archive entry bound exceeded')

    def read(self, key):
        key = archive_path(key)
        seen = set()
        while True:
            require(key in self.members and key not in seen and len(seen) < 20,
                    'Missing or cyclic public archive dependency')
            seen.add(key)
            member = self.members[key]
            if member.issym():
                key = archive_path(member.linkname, str(pathlib.PurePosixPath(key).parent))
            elif member.islnk():
                key = archive_path(member.linkname)
            else:
                require(member.isfile() and 0 <= member.size <= LIMIT, 'Invalid public archive file')
                data = self.stream.extractfile(member).read(LIMIT + 1)
                require(len(data) == member.size, 'Public archive file read failed')
                return data


def elf_dependencies(data):
    require(len(data) >= 64 and data[:7] == b'\x7fELF\x02\x01\x01' and
            struct.unpack_from('<H', data, 18)[0] == 62, 'Public runtime ELF must be x86_64')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    require(size == 56 and 1 <= count <= 128 and offset + size * count <= len(data), 'Invalid ELF headers')
    headers = [struct.unpack_from('<IIQQQQQQ', data, offset + size * n) for n in range(count)]
    dynamic, interpreter = [], []
    for kind, flags, begin, virtual, physical, length, memory, align in headers:
        require(begin + length <= len(data), 'ELF segment exceeds public file')
        if kind == 3:
            interpreter.append(data[begin:begin + length].rstrip(b'\0').decode('ascii'))
        if kind == 2:
            require(length % 16 == 0, 'Invalid ELF dynamic segment')
            dynamic = [struct.unpack_from('<qQ', data, n) for n in range(begin, begin + length, 16)]
    needed = [value for tag, value in dynamic if tag == 1]
    strings = [value for tag, value in dynamic if tag == 5]
    if needed:
        require(len(strings) == 1, 'Missing ELF dependency strings')
        locations = [begin + strings[0] - virtual for kind, flags, begin, virtual, physical, length, memory, align
                     in headers if kind == 1 and virtual <= strings[0] < virtual + length]
        require(len(locations) == 1, 'Ambiguous ELF dependency strings')
        for value in needed:
            begin = locations[0] + value
            require(begin < len(data) and b'\0' in data[begin:begin + 256], 'Invalid ELF dependency name')
            dependency = data[begin:data.index(b'\0', begin)].decode('ascii')
            interpreter.append(name(dependency))
    return interpreter


def put(root, relative, data, mode=0o644):
    target = root / relative
    require(not target.exists(), 'Duplicate public fixture destination')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(mode)


def extract_public_runtime(archive, root, stage):
    source = PublicArchive(archive)
    try:
        pending, copied = ['usr/bin/apk'], set()
        while pending:
            relative = pending.pop()
            if relative in copied:
                continue
            require(relative == 'usr/bin/apk' or re.fullmatch(r'(?:usr/)?lib/[^/]+', relative),
                    'Non-runtime archive input refused')
            data = source.read(relative)
            put(root, relative, data, 0o755)
            copied.add(relative)
            require(len(copied) <= 32, 'Public ELF closure bound exceeded')
            for dependency in elf_dependencies(data):
                if dependency.startswith('/'):
                    pending.append(archive_path(dependency))
                else:
                    candidates = [directory + '/' + dependency for directory in ('lib', 'usr/lib')
                                  if directory + '/' + dependency in source.members]
                    require(candidates, 'Public ELF dependency missing')
                    pending.append(candidates[0])
        for relative, member in source.members.items():
            if relative.startswith('lib/apk/db/') and member.isfile():
                put(stage, relative, source.read(relative))
            elif re.fullmatch(r'(?:etc|lib)/apk/keys/[^/]+', relative) and member.isfile():
                data = source.read(relative)
                require(0 < len(data) <= 8192 and b'PUBLIC KEY' in data and b'PRIVATE' not in data,
                        'Non-public distribution key refused')
                put(stage, 'etc/apk/keys/' + pathlib.PurePosixPath(relative).name, data)
        put(stage, 'etc/apk/world', source.read('etc/apk/world'))
        require((stage / 'lib/apk/db/installed').is_file(), 'Public installed database missing')
        (stage / 'var/lock').mkdir(parents=True)
        (stage / 'tmp').mkdir()
        return len(copied)
    finally:
        source.stream.close()


def bounded_public_output(path):
    with path.open('rb') as stream:
        head = stream.read(4096)
        size = path.stat().st_size
        if size > 8192:
            stream.seek(-4096, 2)
            data = head + b'\n[public diagnostic middle omitted]\n' + stream.read(4096)
        else:
            data = head + stream.read(4096)
    return data.decode('utf-8', errors='replace')


def main():
    require(sys.platform == 'linux' and not sys.argv[1:], 'Run this fixed public fixture on Linux without arguments')
    bundle = ROOT / '.work/diagnostic-vm'
    require(bundle.is_dir() and not bundle.is_symlink(), 'Expected public build bundle is missing')
    def public_file(filename, entry=None):
        path = bundle / name(filename)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= LIMIT,
                'Unsafe public bundle file')
        data = path.read_bytes()
        if entry:
            require(len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'],
                    'Public bundle hash or size mismatch')
        return data
    manifest = json.loads(public_file(PROFILE + '-manifest.json'))
    require(manifest['profile_id'] == PROFILE and manifest['platform'] == {
        'family': 'official', 'openwrt': '25.12.6', 'target': 'x86/64', 'architecture': 'x86_64',
        'package_manager': 'apk', 'package_format': 'apk'}, 'Wrong public build tuple')
    deps = manifest['dependency_bundle']
    require(1 <= len(deps['indexes']) <= 16 and 1 <= len(deps['packages']) <= 64, 'Invalid public closure size')
    require({p['role'] for p in manifest['packages']} == {'csqtt', 'csqtt-captcha', 'luci-app-csqtt'} and
            len(manifest['packages']) == 3, 'Expected exact three public project APKs')
    qemu = shutil.which('qemu-x86_64')
    require(qemu, 'Install the host-only qemu-user package')
    spec = importlib.util.spec_from_file_location('public_bundle', ROOT / 'scripts/bundle-dependencies.py')
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    with tempfile.TemporaryDirectory(prefix='native-apk-public-', dir=ROOT / '.work/preview.10') as temporary:
        work = pathlib.Path(temporary)
        root, stage = work / 'runtime', work / 'stage'
        archive = work / 'rootfs.tar.gz'
        suffix, digest = producer.ROOTFS['25.12.6']
        producer.download('https://downloads.openwrt.org/releases/25.12.6/targets/x86/64/' +
                          'openwrt-25.12.6-x86-64-' + suffix, archive, digest, stage='rootfs')
        closure_count = extract_public_runtime(archive, root, stage)
        project_key = (ROOT / 'release/csqtt-public.pem').read_bytes()
        require(hashlib.sha256(project_key).hexdigest() == PROJECT_KEY_SHA and b'PRIVATE' not in project_key,
                'Pinned repository PUBLIC key mismatch')
        put(stage, 'etc/apk/keys/csqtt-public.pem', project_key)
        keys = {hashlib.sha256(p.read_bytes()).hexdigest() for p in (stage / 'etc/apk/keys').iterdir()}
        repos, ids = [], set()
        for entry in deps['indexes']:
            ident = name(entry['id'])
            require(ident not in ids and entry['format'] == 'apk-adb' and entry['key_sha256'] in keys and
                    entry['repository'].startswith('https://downloads.openwrt.org/releases/25.12.6/'),
                    'Public authenticated index identity mismatch')
            ids.add(ident)
            path = work / 'repos' / ident / 'packages.adb'
            put(work, 'repos/' + ident + '/packages.adb', public_file(entry['name'], entry))
            repos.append(path.as_uri())
        for entry in deps['packages']:
            require(entry['index'] in ids and entry['name'] == PROFILE + '--dep--' + name(entry['filename']) and
                    entry['filename'] == name(entry['package']) + '-' + name(entry['version']) + '.apk',
                    'Public dependency filename mismatch')
            put(work, 'repos/' + entry['index'] + '/' + entry['filename'], public_file(entry['name'], entry))
        repository_file = work / 'repositories'
        repository_file.write_text('\n'.join(repos) + '\n')
        projects = []
        for entry in manifest['packages']:
            require(entry['name'] == PROFILE + '--' + entry['role'] + '-' + name(entry['version']) + '.apk',
                    'Unexpected public project package filename')
            put(work, 'assets/' + entry['name'], public_file(entry['name'], entry))
            projects.append(str(work / 'assets' / entry['name']))
        env = {**PUBLIC_ENV, 'HOME': str(work / 'empty-home'), 'TMPDIR': str(work / 'tmp')}
        pathlib.Path(env['HOME']).mkdir()
        pathlib.Path(env['TMPDIR']).mkdir()
        base = [qemu, '-L', str(root), '-E', 'LD_LIBRARY_PATH=/lib:/usr/lib', str(root / 'usr/bin/apk')]
        def run(label, arguments, show=False):
            stdout, stderr = work / (label + '.stdout'), work / (label + '.stderr')
            with stdout.open('wb') as out, stderr.open('wb') as err:
                result = subprocess.run(base + arguments, stdout=out, stderr=err, timeout=120, env=env, cwd=work)
            if show or result.returncode:
                print('PUBLIC_FIXTURE_NATIVE_APK ' + label + ' exit=' + str(result.returncode), flush=True)
                for channel, path in (('stdout', stdout), ('stderr', stderr)):
                    print(channel + ' first/tail <=8192B bytes=' + str(path.stat().st_size), flush=True)
                    print(bounded_public_output(path), flush=True)
            return result.returncode, stdout
        for ident in sorted(ids):
            code, unused = run('verify-' + ident, ['--keys-dir', str(stage / 'etc/apk/keys'), 'verify',
                                                   str(work / 'repos' / ident / 'packages.adb')])
            require(code == 0, 'Public index target-native verification failed')
        for index, project in enumerate(projects):
            code, unused = run('verify-project-' + str(index), ['--keys-dir', str(stage / 'etc/apk/keys'), 'verify', project])
            require(code == 0, 'Public project target-native verification failed')
        code, installed = run('installed', ['--root', str(stage), '--arch', 'x86_64', '--no-network',
            'query', '--installed', '--all-matches', '--fields', 'name,version', '--format', 'json', '*'])
        require(code == 0 and installed.stat().st_size <= 1024 * 1024, 'Public baseline query failed')
        records = json.loads(installed.read_bytes())
        require(type(records) is list and all(type(row) is dict and type(row.get('name')) is str for row in records),
                'Invalid public baseline records')
        present = {row['name'] for row in records}
        missing = [name(p['package']) + '=' + name(p['version']) for p in deps['packages'] if p['package'] not in present]
        print('Public fixture: pinned25.12.6 x86_64 ELF closure=' + str(closure_count) +
              ' missing_dependencies=' + str(len(missing)) + '; no scripts/network/private inputs', flush=True)
        code, unused = run('staged-add', ['--root', str(stage), '--arch', 'x86_64', '--repositories-file',
            str(repository_file), '--keys-dir', 'etc/apk/keys', '--no-network', '--no-scripts', 'add', *projects, *missing], show=True)
        print('DIAGNOSTIC_ONLY_NO_RELEASE_QUALIFICATION', flush=True)
        return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print('Public native APK probe refused: ' + type(error).__name__, flush=True)
        raise SystemExit(1) from None
