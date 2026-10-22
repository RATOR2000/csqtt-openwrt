#!/usr/bin/env python3
"""Run private-input rejection and control smoke on the selected ISA under QEMU."""
import argparse
import json
import os
import pathlib
import socket
import subprocess
import tempfile

from binary_abi import emulator_command, validate_elf
from platforms import load_registry, require, select_profile, verify_sdk


def private_dns_smoke(profile, binary, sdk):
    """Execute the packaged resolver with this SDK's musl and target libraries."""
    binary, sdk = pathlib.Path(binary).resolve(), pathlib.Path(sdk).resolve()
    toolchain = verify_sdk(profile, sdk, check_compiler=False)
    targets = [path for path in (sdk / 'staging_dir').glob('target-*') if path.is_dir()]
    require(len(targets) == 1, 'Private DNS requires exactly one SDK target staging directory')
    loader = toolchain / 'lib/libc.so'
    for payload in (binary, loader):
        validate_elf(payload, profile, require_static=False)
    libraries = ':'.join(str(path) for path in
                         (targets[0] / 'usr/lib', targets[0] / 'lib', toolchain / 'lib'))
    command = emulator_command(profile, loader) + ['--library-path', libraries, str(binary)]
    env = {key: value for key, value in os.environ.items()
           if key not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'QEMU_LD_PREFIX')}

    def run(*args):
        return subprocess.run(command + list(args), capture_output=True, text=True, timeout=15, env=env)

    version = run('--version')
    require(version.returncode == 0 and 'nftset' in version.stdout.split(),
            'Packaged private DNS startup or nftset capability failed')
    with tempfile.TemporaryDirectory(prefix='csqtt-private-dns-') as directory:
        config = pathlib.Path(directory) / 'dns-private.conf'
        config.write_text('port=5400\nno-resolv\nno-hosts\nbind-dynamic\nlisten-address=127.0.0.1\n'
                          'server=//127.0.0.1\nserver=/lan/127.0.0.1\n'
                          'server=192.0.2.53@198.18.0.1\n'
                          'nftset=/csqtt-test.invalid/4#inet#csqtt#d_test\n')
        result = run('--test', '--conf-file=' + str(config))
        require(result.returncode == 0 and 'syntax check OK' in result.stderr,
                'Packaged private DNS managed nftset configuration failed')
        require({path.name for path in config.parent.iterdir()} == {config.name},
                'Private DNS syntax check created runtime state')
    print('Packaged private DNS selected CPU startup and nftset syntax passed; no daemon or router services started.')


def smoke(profile, core, broker, require_tls=False):
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
        if require_tls:
            resolvers = [line.split()[1] for line in pathlib.Path('/etc/resolv.conf').read_text().splitlines()
                         if line.startswith('nameserver ') and '.' in line.split()[1] and not line.split()[1].startswith('127.')]
            dns = resolvers[0] if resolvers else '1.1.1.1'
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect((dns, 53))
                source = route.getsockname()[0]
            result = run(core, '--health-probe', 'wan', input=json.dumps({'source_ipv4': source, 'dns_ipv4': dns}))
            observation = json.loads(result.stdout)
            assert result.returncode == 0 and observation['completed'] and observation['config_valid'], 'native TLS probe did not complete'
            assert len(observation['endpoints']) == 2 and all(e['reachable'] and e['dns'] == 'ok' for e in observation['endpoints']), 'native DNS/TLS reachability failed'
            assert {path.name for path in root.iterdir()} == {'client.json'}, 'probe created runtime state'
    print('Selected platform static ELF/ISA smoke passed; no router/VK or runtime qualification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--require-tls', action='store_true', help='Require native selected-ABI DNS and verified HTTPS controls')
    parser.add_argument('--dnsmasq', type=pathlib.Path, help='Private DNS payload extracted from the candidate package')
    parser.add_argument('--sdk', type=pathlib.Path, help='Matching SDK supplying the private DNS loader and libraries')
    parser.add_argument('core', nargs='?')
    parser.add_argument('broker', nargs='?')
    args = parser.parse_args()
    if bool(args.core) != bool(args.broker) or bool(args.dnsmasq) != bool(args.sdk):
        parser.error('Pass both core/broker and both --dnsmasq/--sdk when selecting those checks')
    if not (args.core or args.dnsmasq) or (args.require_tls and not args.core):
        parser.error('Select a payload check; --require-tls requires core/broker')
    profile = select_profile(load_registry(), args.profile)
    if args.core:
        smoke(profile, args.core, args.broker, args.require_tls)
    if args.dnsmasq:
        private_dns_smoke(profile, args.dnsmasq, args.sdk)


if __name__ == '__main__':
    main()
