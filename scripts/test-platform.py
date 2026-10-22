#!/usr/bin/env python3
"""Run private-input rejection and control smoke on the selected ISA under QEMU."""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile

from binary_abi import emulator_command, validate_elf
from platforms import load_registry, select_profile


def smoke(profile, core, broker):
    core, broker = pathlib.Path(core).resolve(), pathlib.Path(broker).resolve()
    for binary in (core, broker):
        validate_elf(binary, profile)

    def run(binary, *args, input=None):
        return subprocess.run(emulator_command(profile, binary) + list(args), input=input,
                              capture_output=True, text=True, timeout=15)

    with tempfile.TemporaryDirectory(prefix='csqtt-isa-') as directory:
        root = pathlib.Path(directory)
        config = root / 'client.json'
        for body in ('{"peer":', '{"unexpected":"CONFIG_VALUE_MUST_STAY_PRIVATE"}',
                     '{"peer":"invalid-without-port"}'):
            config.write_text(body)
            os.chmod(config, 0o600)
            result = run(core, '--config-file', str(config))
            assert result.returncode == 1 and 'configuration_failed' in result.stderr, 'config rejection failed'
            assert 'CONFIG_VALUE_MUST_STAY_PRIVATE' not in result.stdout + result.stderr, 'config value leaked'
        result = run(broker, 'status', '--socket', str(root / 'absent.sock'))
        assert result.returncode == 0 and json.loads(result.stdout) == {'ok': False, 'error': 'broker_unavailable'}, 'broker control failed'
        result = run(core, '--health-probe', 'vpn', input='{"source_ipv4":"PRIVATE_INVALID_SOURCE","dns_ipv4":"1.1.1.1"}')
        assert result.returncode == 2 and not result.stderr, 'health rejection failed'
        assert 'PRIVATE_INVALID_SOURCE' not in result.stdout, 'health input leaked'
        result = run(core, '--health-probe', 'invalid', input='{}')
        assert result.returncode == 2 and not result.stderr, 'early probe mode failed'
        assert {path.name for path in root.iterdir()} == {'client.json'}, 'invalid input created runtime state'
    print('Selected platform static ELF/ISA smoke passed; no router/VK or runtime qualification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('core')
    parser.add_argument('broker')
    args = parser.parse_args()
    smoke(select_profile(load_registry(), args.profile), args.core, args.broker)


if __name__ == '__main__':
    main()
