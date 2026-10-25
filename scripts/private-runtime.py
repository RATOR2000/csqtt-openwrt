#!/usr/bin/env python3
"""Assemble and exercise a private loader closure; never claim firmware compatibility."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

from binary_abi import validate_elf

ROOT = pathlib.Path(__file__).resolve().parents[1]


def needed(path, readelf):
    data = subprocess.run([str(readelf), '-d', str(path)], capture_output=True, text=True,
                          check=True, timeout=15).stdout
    names = re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', data)
    if any(not re.fullmatch(r'[A-Za-z0-9_.+-]+', name) for name in names):
        raise ValueError('unsafe shared library name')
    return names


def copy_file(source, destination):
    if not source.is_file():
        raise ValueError('missing private runtime build output: ' + source.name)
    validate_elf(source, {'elf': {'class': 64, 'endian': 'little', 'machine': 183}}, require_static=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755)


def assemble(build, target, toolchain, out, musl_license=None):
    build, target, toolchain, out = map(pathlib.Path, (build, target, toolchain, out))
    (out / 'bundle.json').unlink(missing_ok=True)
    base = out / 'usr/libexec/csqtt/ucode-runtime'
    if base.exists():
        shutil.rmtree(base)
    readelf = toolchain / 'bin/aarch64-openwrt-linux-musl-readelf'
    copy_file(build / 'ucode', base / 'bin/ucode')
    for name in ('fs', 'uci', 'ubus'):
        copy_file(build / (name + '.so'), base / 'modules' / (name + '.so'))
    # The ELF interpreter is deliberately a private file, invoked explicitly by
    # the wrapper. No dynamic loader, libuci or libubus is installed in /lib.
    libc = toolchain / 'lib/libc.so'
    copy_file(libc, base / 'lib/ld-musl-aarch64.so.1')
    search = [build, target / 'usr/lib', target / 'lib', toolchain / 'lib', toolchain / 'usr/lib']
    pending = [base / 'bin/ucode', *(base / 'modules').glob('*.so')]
    done = set()
    while pending:
        binary = pending.pop()
        for name in needed(binary, readelf):
            if name in done:
                continue
            done.add(name)
            destination = base / 'lib' / name
            if name in ('libc.so', 'libc.so.6'):
                copy_file(libc, destination)
            else:
                matches = [directory / name for directory in search if (directory / name).is_file()]
                if not matches:
                    raise ValueError('private runtime dependency unresolved: ' + name)
                copy_file(matches[0], destination)
                pending.append(destination)
    wrapper = out / 'usr/libexec/csqtt/ucode'
    wrapper.write_text('#!/bin/sh\nset -eu\nBASE=/usr/libexec/csqtt/ucode-runtime\n'
                       'exec "$BASE/lib/ld-musl-aarch64.so.1" --library-path "$BASE/lib" '
                       '"$BASE/bin/ucode" -L "$BASE/modules/*.so" "$@"\n', encoding='utf-8', newline='\n')
    wrapper.chmod(0o755)
    licenses = out / 'usr/share/licenses/csqtt-private-runtime'
    licenses.mkdir(parents=True, exist_ok=True)
    # Distribute the original licenses from every source used to build private
    # shared objects. Preserve full corresponding-source pins in the manifest.
    source = build.parent / ('ucode-' + json.loads((ROOT / 'platforms/private-runtime-experiment.json').read_text())['ucode']['revision'])
    candidates = [source / 'LICENSE']
    for name in ('libubox', 'ubus', 'uci', 'json-c'):
        sources = list((target.parent.parent / 'build_dir').glob(f'**/{name}-*'))
        found = [path for directory in sources if directory.is_dir()
                 for pattern in ('COPYING*', 'LICENSE*') for path in directory.glob(pattern) if path.is_file()]
        if not found:
            raise ValueError('missing corresponding private runtime license: ' + name)
        candidates.extend(found)
    musl_sources = [directory for parent in (toolchain / 'info', target.parent.parent / 'build_dir')
                    for directory in parent.glob('**/musl*') if directory.is_dir()]
    musl_licenses = [path for directory in musl_sources for name in ('COPYRIGHT', 'COPYING', 'LICENSE')
                     for path in [directory / name] if path.is_file()]
    if musl_license:
        pin = json.loads((ROOT / 'platforms/private-runtime-experiment.json').read_text())['musl_license']
        data = pathlib.Path(musl_license).read_bytes()
        if hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('musl copyright differs from pinned source')
        destination = licenses / 'musl-COPYRIGHT'
        destination.write_bytes(data)
        musl_licenses.append(destination)
    # The SDK may retain only the musl source archive rather than its unpacked
    # tree. Do not silently omit the loader license in an output artifact.
    if not musl_licenses:
        import tarfile
        archives = list((target.parent.parent / 'dl').glob('musl-*.tar.*'))
        for archive in archives:
            with tarfile.open(archive, 'r:*') as data:
                for member in data:
                    if member.name.endswith('/COPYRIGHT') and member.isfile() and member.size < 65536:
                        license_path = licenses / 'musl-COPYRIGHT'
                        license_path.write_bytes(data.extractfile(member).read())
                        musl_licenses.append(license_path)
    if not musl_licenses:
        raise ValueError('missing corresponding musl loader copyright')
    candidates.extend(path for path in musl_licenses if path.parent != licenses)
    for sequence, path in enumerate(candidates):
        if path.is_file():
            shutil.copyfile(path, licenses / f'{sequence}-{path.parent.name}-{path.name}')
    if 'libgcc_s.so.1' in done:
        raise ValueError('libgcc runtime dependency requires its corresponding-source license bundle before distribution')
    metadata = json.loads((ROOT / 'platforms/private-runtime-experiment.json').read_text())
    metadata['files'] = [{'path': path.relative_to(out).as_posix(), 'size': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in sorted((out / 'usr').rglob('*')) if path.is_file()]
    (out / 'bundle.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')


def smoke(out, ubusd=None):
    out = pathlib.Path(out).resolve()
    base = out / 'usr/libexec/csqtt/ucode-runtime'
    command = ['qemu-aarch64', '-cpu', 'cortex-a53', str(base / 'lib/ld-musl-aarch64.so.1'),
               '--library-path', str(base / 'lib'), str(base / 'bin/ucode'), '-L', str(base / 'modules/*.so')]
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C'}
    loader_version = subprocess.run(command[:4], capture_output=True, text=True,
                                    env=environment, timeout=10)
    if 'Version 1.1.24' not in loader_version.stderr:
        raise ValueError('experimental loader does not match pinned musl license/version')
    # Only private modules/libraries are loaded; UCI writes stay in a disposable
    # directory, and ubus connects to an absent socket (no router/server access).
    with tempfile.TemporaryDirectory(prefix='csqtt-private-ucode-') as directory:
        root = pathlib.Path(directory)
        (root / 'fixture').write_text("config test 'main'\n option value 'preserved'\n")
        (root / 'save').mkdir()
        script = ('import * as fs from "fs"; import * as uci from "uci"; import * as ubus from "ubus"; '
                  f'let c = uci.cursor({json.dumps(str(root))}, {json.dumps(str(root / "save"))}); '
                  'if (c.get("fixture", "main", "value") != "preserved") die("private UCI read failed"); '
                  'c.set("fixture", "main", "value", "changed"); c.save("fixture"); c.commit("fixture"); '
                  'if (c.get("fixture", "main", "value") != "changed") die("private UCI write failed"); '
                  'if (ubus.connect("/nonexistent-csqtt-private-ubus.sock") != null) die("unexpected ubus connection"); '
                  'if (type(fs.readfile) != "function") die("missing private fs"); '
                  'print("private-runtime-module-smoke-pass\\n");')
        daemon = None
        try:
            if ubusd:
                socket = root / 'ubus.sock'
                daemon = subprocess.Popen(command[:6] + [str(pathlib.Path(ubusd).resolve()), '-s', str(socket)],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
                deadline = time.monotonic() + 10
                while not socket.exists():
                    if daemon.poll() is not None or time.monotonic() >= deadline:
                        raise ValueError('isolated legacy ubusd failed to start')
                    time.sleep(0.05)
                script += (f'let conn = ubus.connect({json.dumps(str(socket))}); '
                           'if (!conn) die("legacy ubus handshake failed"); '
                           'let objects = conn.list(); '
                           'if (objects == null) die("legacy ubus lookup failed"); conn.disconnect();')
            result = subprocess.run(command + ['-e', script], capture_output=True, text=True,
                                    env=environment, timeout=20, check=True)
            if result.stdout != 'private-runtime-module-smoke-pass\n' or result.stderr:
                raise ValueError('private runtime smoke emitted unexpected output')
        finally:
            if daemon is not None:
                daemon.terminate()
                try:
                    daemon.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait(timeout=5)
    print('Private ARM64 loader/fs/UCI/ubus module smoke passed; GL kernel/vendor ubusd/firewall acceptance remains unverified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('assemble')
    for name in ('build', 'target', 'toolchain', 'out'):
        build.add_argument(name)
    build.add_argument('--musl-license')
    smoke_parser = sub.add_parser('smoke')
    smoke_parser.add_argument('out')
    smoke_parser.add_argument('--ubusd')
    args = parser.parse_args()
    if args.command == 'assemble':
        assemble(args.build, args.target, args.toolchain, args.out, args.musl_license)
    else:
        smoke(args.out, args.ubusd)


if __name__ == '__main__':
    main()
