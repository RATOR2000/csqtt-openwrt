#!/usr/bin/env python3
"""Execute the built ARM64 binaries under QEMU without a tunnel or VK calls."""
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile

core, broker = map(lambda p: pathlib.Path(p).resolve(), sys.argv[1:])
for binary in (core, broker):
    with binary.open('rb') as stream:
        header = stream.read(20)
    assert header[:6] == b'\x7fELF\x02\x01' and struct.unpack('<H', header[18:20])[0] == 183, 'Expected ARM64 ELF'


def run(binary, *args):
    return subprocess.run(['qemu-aarch64', '-cpu', 'cortex-a53', str(binary), *args],
                          capture_output=True, text=True, timeout=15)


with tempfile.TemporaryDirectory(prefix='csqtt-arm64-') as directory:
    root = pathlib.Path(directory)
    config = root / 'client.json'
    for body in ('{"peer":', '{"unexpected":"CONFIG_VALUE_MUST_STAY_PRIVATE"}',
                 '{"peer":"invalid-without-port"}'):
        config.write_text(body)
        os.chmod(config, 0o600)
        result = run(core, '--config-file', str(config))
        assert result.returncode == 1 and 'configuration_failed' in result.stderr, 'ARM64 config rejection failed'
        assert 'CONFIG_VALUE_MUST_STAY_PRIVATE' not in result.stdout + result.stderr, 'Config value leaked'
    result = run(broker, 'status', '--socket', str(root / 'absent.sock'))
    assert result.returncode == 0 and json.loads(result.stdout) == {'ok': False, 'error': 'broker_unavailable'}, 'ARM64 broker CLI failed'
    assert {p.name for p in root.iterdir()} == {'client.json'}, 'Rejected config created runtime state'
print('ARM64 Cortex-A53 smoke passed: private config rejection and broker control CLI; no router/VK execution')
