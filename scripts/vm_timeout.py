"""Compile and privately provision a static test-only disposable-VM deadline tool."""
import hashlib
import pathlib
import platform
import shlex
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build_timeout(directory, source=ROOT):
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('VM deadline tool requires a native Linux x86_64 build host')
    compiler = shutil.which('cc')
    if not compiler:
        raise ValueError('Host C compiler required for the test-only VM deadline tool')
    output = directory / 'vm-timeout'
    subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-static', '-s',
                    '-o', str(output), str(source / 'scripts/vm-timeout.c')],
                   capture_output=True, check=True, timeout=60)
    data = output.read_bytes()
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 62:
        raise ValueError('VM deadline tool is not a Linux x86_64 ELF executable')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if size != 56 or not 1 <= count <= 128 or offset + size * count > len(data):
        raise ValueError('VM deadline tool has invalid ELF program headers')
    if any(struct.unpack_from('<I', data, offset + size * n)[0] in (2, 3) for n in range(count)):
        raise ValueError('VM deadline tool must be static without a dynamic loader')
    return output


def provision_timeout(ssh, binary, directory):
    """Copy only after the clean installer succeeds; never touch native packages."""
    if directory not in ('/tmp/csqtt-native', '/tmp/csqtt-public'):
        raise ValueError('VM deadline tool destination must be a disposable test directory')
    data = binary.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    target = shlex.quote(directory + '/vm-timeout')
    command = ('set -eu; umask 077; test -d ' + shlex.quote(directory) + '; test ! -e ' + target +
               '; cat > ' + target + '; chmod 700 ' + target +
               '; test "$(sha256sum ' + target + ' | cut -d " " -f 1)" = ' + digest +
               '; ' + target + ' 1 true')
    subprocess.run(ssh + [command], input=data, capture_output=True, check=True, timeout=30)
