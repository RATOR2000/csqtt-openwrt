#!/usr/bin/env python3
"""Check the ARM64 daemon's real Linux TUN lifecycle in an isolated netns.

Run as root with one SDK-built client binary. No interface connects this
namespace to the host, and no server, VK, routing or TUNCONF success is tested.
The private fixture and daemon output are removed without printing their values.
"""
import json
import os
import pathlib
import secrets
import shlex
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time


class CheckFailure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def read_json(path):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise CheckFailure('private runtime JSON unavailable or invalid') from None


def private_mode(path, kind):
    metadata = path.lstat()
    require(kind(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o600
            and metadata.st_uid == os.geteuid(), 'private runtime mode or owner incorrect')


def control(path, command, timeout=2):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(str(path))
        connection.sendall(json.dumps({'command': command}).encode() + b'\n')
        response = bytearray()
        while not response.endswith(b'\n'):
            chunk = connection.recv(4096)
            require(chunk and len(response) + len(chunk) <= 65536,
                    'control reply missing or exceeds its bound')
            response.extend(chunk)
    try:
        return json.loads(response)
    except ValueError:
        raise CheckFailure('control reply is invalid JSON') from None


STATUS_FIELDS = {'schema_version', 'state', 'pid', 'tun_device', 'tunnel_ip', 'dns',
                 'active_workers', 'bytes_up', 'bytes_down', 'captcha', 'error_code', 'updated_at',
                 'process_startticks', 'boot_id', 'updated_boottime_ms', 'uptime_secs', 'health'}
HEALTH_COUNTERS = {'auth_inflight', 'auth_network_inflight', 'auth_attempts', 'auth_successes',
                   'auth_failures', 'auth_cancelled', 'fresh_auth_retries', 'human_epoch',
                   'liveness_probes', 'liveness_replies', 'liveness_misses', 'liveness_timeouts',
                   'network_timeout_events', 'unavailable_calls', 'session_errors'}
HEALTH_AGES = {'auth_progress_age_secs', 'peer_progress_age_secs'}
HEALTH_FIELDS = HEALTH_COUNTERS | HEALTH_AGES | {'auth_phase', 'last_session_error'}


def unsigned(value, maximum=(1 << 64) - 1):
    return type(value) is int and 0 <= value <= maximum


def boottime_ms():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1_000_000


def process_ownership(pid):
    try:
        # Native procfs describes the qemu process, whose PID/startticks are also
        # observed by the emulated daemon. comm can contain spaces and ')'.
        fields = pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        ticks = int(fields[19])
        boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        started = ticks * 1000 // os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, IndexError):
        raise CheckFailure('native process ownership unavailable') from None
    require(ticks > 0 and len(boot) == 36, 'native process ownership invalid')
    return {'process_startticks': ticks, 'boot_id': boot, 'started_boottime_ms': started}


def check_status(value, pid, private_values, stopped=False, ownership=None, now_ms=None):
    require(isinstance(value, dict) and set(value) == STATUS_FIELDS,
            'status fields differ from the private daemon contract')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['pid']) is int and value['pid'] == pid
            and value['tun_device'] == 'csqtt0', 'daemon status identity incorrect')
    ownership = process_ownership(pid) if ownership is None else ownership
    now_ms = boottime_ms() if now_ms is None else now_ms
    require(unsigned(value['process_startticks']) and value['process_startticks'] > 0
            and value['process_startticks'] == ownership['process_startticks']
            and value['boot_id'] == ownership['boot_id'], 'daemon process ownership incorrect')
    updated = value['updated_boottime_ms']
    require(unsigned(updated) and ownership['started_boottime_ms'] <= updated <= now_ms
            and now_ms - updated <= 15_000, 'daemon status boot-clock freshness incorrect')
    require(unsigned(value['uptime_secs'])
            and value['uptime_secs'] <= (now_ms - ownership['started_boottime_ms']) // 1000 + 1
            and unsigned(value['updated_at']) and value['updated_at'] > 0
            and unsigned(value['bytes_up'], (1 << 63) - 1)
            and unsigned(value['bytes_down'], (1 << 63) - 1)
            and unsigned(value['active_workers']), 'daemon status counter type or bound incorrect')
    health = value['health']
    require(isinstance(health, dict) and set(health) == HEALTH_FIELDS,
            'health fields differ from the private daemon contract')
    require(all(unsigned(health[field]) for field in HEALTH_COUNTERS)
            and all(health[field] is None or unsigned(health[field]) for field in HEALTH_AGES),
            'health counter type or bound incorrect')
    require(health['auth_phase'] in ('idle', 'network', 'manual', 'captcha_wait', 'waiting')
            and health['last_session_error'] in (None, 'handshake_timeout', 'handshake_rejected', 'session_failed'),
            'health contains an unrecognized phase or session error')
    require(value['state'] == ('stopped' if stopped else 'connecting')
            and value['tunnel_ip'] is None and value['dns'] == []
            and value['active_workers'] == 0 and value['captcha'] is None
            and value['error_code'] is None, 'isolated daemon status incorrect')
    encoded = json.dumps(value)
    require(all(secret not in encoded for secret in private_values),
            'status contains a private fixture value')


def check_schema_regressions():
    """Exercise private schema rejection without requiring Linux, root or qemu."""
    owner = {'process_startticks': 1234, 'boot_id': 'test-boot', 'started_boottime_ms': 80_000}
    health = dict.fromkeys(HEALTH_COUNTERS, 0)
    health.update(dict.fromkeys(HEALTH_AGES))
    health.update(auth_phase='idle', last_session_error=None)
    sample = dict(schema_version=1, state='connecting', pid=42, tun_device='csqtt0',
                  tunnel_ip=None, dns=[], active_workers=0, bytes_up=0, bytes_down=0,
                  captcha=None, error_code=None, updated_at=1_900_000_000,
                  process_startticks=1234, boot_id='test-boot', updated_boottime_ms=99_000,
                  uptime_secs=19, health=health)
    check = lambda value, stopped=False: check_status(value, 42, ('fixture-secret',), stopped,
                                                     ownership=owner, now_ms=100_000)
    check(sample)
    check(dict(sample, state='stopped'), stopped=True)
    bad = [dict(sample, process_startticks=1235), dict(sample, boot_id='previous-boot'),
           dict(sample, updated_boottime_ms=100_001), dict(sample, updated_boottime_ms=84_999),
           dict(sample, updated_boottime_ms=79_999), dict(sample, process_startticks=True),
           dict(sample, uptime_secs=True), dict(sample, uptime_secs=22), dict(sample, bytes_up=-1),
           {key: value for key, value in sample.items() if key != 'health'},
           dict(sample, health=dict(health, unexpected='fixture-secret')),
           dict(sample, health=dict(health, auth_phase='fixture-secret')),
           dict(sample, health=dict(health, last_session_error='fixture-secret'))]
    for field in HEALTH_COUNTERS:
        for value in (True, -1, 1.5, 1 << 64, 'fixture-secret'):
            bad.append(dict(sample, health=dict(health, **{field: value})))
    for field in HEALTH_AGES:
        bad.append(dict(sample, health=dict(health, **{field: True})))
    for value in bad:
        try:
            check(value)
        except CheckFailure:
            continue
        raise CheckFailure('private schema regression accepted invalid metadata or health')


def main():
    check_schema_regressions()
    require(sys.platform == 'linux' and os.geteuid() == 0, 'requires Linux root and network namespaces')
    require(len(sys.argv) == 2, 'usage: test-arm64-tun.py SDK_CLIENT')
    binary = pathlib.Path(sys.argv[1]).resolve(strict=True)
    with binary.open('rb') as stream:
        header = stream.read(20)
    require(header[:6] == b'\x7fELF\x02\x01' and len(header) == 20
            and struct.unpack('<H', header[18:20])[0] == 183, 'expected ARM64 ELF')
    qemu, ip = shutil.which('qemu-aarch64'), shutil.which('ip')
    require(qemu and ip and pathlib.Path('/dev/net/tun').exists(),
            'requires qemu-aarch64, iproute2 and /dev/net/tun')
    namespace = 'csqtt-arm64-' + secrets.token_hex(5)
    owned_namespace = False
    processes = []

    def network(*args, check=True):
        result = subprocess.run([ip, *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=5, check=False)
        require(not check or result.returncode == 0, 'network namespace command failed')
        return result

    def tunnel_present():
        result = network('-n', namespace, '-j', '-d', 'link', 'show', 'dev', 'csqtt0', check=False)
        if result.returncode:
            return False
        links = json.loads(result.stdout)
        require(len(links) == 1 and links[0]['linkinfo']['info_kind'] == 'tun',
                'daemon interface is not a native TUN')
        return True

    try:
        network('netns', 'add', namespace)
        owned_namespace = True
        network('-n', namespace, 'link', 'set', 'lo', 'up')
        links = json.loads(network('-n', namespace, '-j', 'link', 'show').stdout)
        require([link['ifname'] for link in links] == ['lo'], 'namespace has an external interface')
        for family in ('-4', '-6'):
            routes = json.loads(network('-n', namespace, family, '-j', 'route', 'show').stdout)
            require(routes == [], 'namespace has a nonlocal route')

        with tempfile.TemporaryDirectory(prefix='csqtt-arm64-tun-') as temporary:
            root = pathlib.Path(temporary)
            os.chmod(root, 0o700)
            config = root / 'client.json'
            runtime = root / 'run'
            identity_path = root / 'identity' / 'identity.json'
            status_path, control_path = runtime / 'status.json', runtime / 'control.sock'
            down_marker, hook = root / 'down', root / 'tun-hook'
            hook.write_text('#!/bin/sh\nset -eu\n[ "$#" = 1 ]\n[ "$1" = down ]\n'
                            '[ "$CSQTT_TUN_DEVICE" = csqtt0 ]\n'
                            'umask 077\nprintf "down\\n" >> ' + shlex.quote(str(down_marker)) + '\n')
            os.chmod(hook, 0o700)
            # Fresh random strings are deliberately synthetic, never real credentials.
            password, call_hash = secrets.token_hex(16), secrets.token_hex(20)
            body = {'peer': '198.18.0.1:9000', 'password': password, 'vk_hashes': [call_hash],
                    'workers': 9, 'turn_host': '198.18.0.2', 'turn_port': 3478,
                    'tun_device': 'csqtt0', 'tun_config_hook': str(hook),
                    'status_file': str(status_path), 'control_socket': str(control_path),
                    'identity_file': str(identity_path)}
            config.write_text(json.dumps(body))
            os.chmod(config, 0o600)
            # Avoid proxy settings, VK credential overrides and unrelated runtime input.
            environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'HOME': str(root)}
            previous_identity = None
            for sequence, action in enumerate(('control', 'term', 'kill', 'restart'), 1):
                require(not tunnel_present(), 'previous daemon left its TUN behind')
                down_marker.unlink(missing_ok=True)
                with (root / 'output').open('w+b') as output:
                    os.chmod(output.name, 0o600)
                    process = subprocess.Popen([ip, 'netns', 'exec', namespace, qemu,
                                                '-cpu', 'cortex-a53', str(binary),
                                                '--config-file', str(config)],
                                               stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                               env=environment, start_new_session=True)
                    processes.append(process)
                    deadline = time.monotonic() + 25
                    while True:
                        exit_status = process.poll()
                        if exit_status is not None:
                            output.seek(0)
                            diagnostic = output.read(65536)
                            # Only predefined categories reach CI, never an upstream error string.
                            categories = [marker for marker in ('configuration_failed', 'runtime_failed',
                                          'open /dev/net/tun', 'create exclusive TUN interface',
                                          'tun_io_failed', 'PANIC') if marker.encode() in diagnostic]
                            raise CheckFailure(f'daemon exited before TUN/control readiness (exit {exit_status}; '
                                               + ', '.join(categories or ['uncategorized']) + ')')
                        require(output.seek(0, os.SEEK_END) <= 65536, 'daemon diagnostic output exceeded bound')
                        require(time.monotonic() < deadline, 'daemon TUN/control readiness timed out')
                        if tunnel_present() and control_path.exists():
                            try:
                                response = control(control_path, 'status', timeout=0.5)
                            except (OSError, CheckFailure):
                                response = None
                            if response and response.get('ok') is True and response.get('status', {}).get('state') == 'connecting':
                                break
                        time.sleep(0.1)
                    for path in (config, status_path, identity_path, identity_path.with_suffix('.lock')):
                        private_mode(path, stat.S_ISREG)
                    private_mode(control_path, stat.S_ISSOCK)
                    for directory in (root, runtime, identity_path.parent):
                        require(stat.S_IMODE(directory.stat().st_mode) == 0o700,
                                'private runtime directory is not mode 0700')
                    identity = read_json(identity_path)
                    require(set(identity) == {'device_id', 'generation'} and identity['generation'] == sequence,
                            'persistent generation did not advance exactly once')
                    require(isinstance(identity['device_id'], str) and bool(identity['device_id']),
                            'persistent identity missing')
                    require(previous_identity is None or identity['device_id'] == previous_identity,
                            'persistent identity changed on restart')
                    previous_identity = identity['device_id']
                    private_values = (password, call_hash, previous_identity)
                    ownership = process_ownership(process.pid)
                    check_status(response['status'], process.pid, private_values, ownership=ownership)
                    check_status(read_json(status_path), process.pid, private_values, ownership=ownership)
                    if action in ('control', 'restart'):
                        require(control(control_path, 'stop') == {'ok': True}, 'stop reply was not flushed')
                    else:
                        process.send_signal(signal.SIGTERM if action == 'term' else signal.SIGKILL)
                    try:
                        result = process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        raise CheckFailure('daemon shutdown timed out') from None
                    require(result == (-signal.SIGKILL if action == 'kill' else 0),
                            'daemon exit status incorrect')
                    deadline = time.monotonic() + 3
                    while tunnel_present() and time.monotonic() < deadline:
                        time.sleep(0.1)
                    require(not tunnel_present(), 'nonpersistent TUN survived daemon termination')
                    if action != 'kill':
                        require(not control_path.exists(), 'graceful shutdown left control socket')
                        require(down_marker.read_bytes() == b'down\n', 'down hook did not run exactly once')
                        check_status(read_json(status_path), process.pid, private_values, stopped=True,
                                     ownership=ownership)
                    else:
                        # SIGKILL cannot unlink filesystem sockets; the next daemon must reclaim it.
                        private_mode(control_path, stat.S_ISSOCK)
                        require(not down_marker.exists(), 'SIGKILL unexpectedly executed shutdown hook')
                    output.seek(0)
                    diagnostics = output.read(65537)
                    require(len(diagnostics) <= 65536 and all(value.encode() not in diagnostics for value in private_values),
                            'diagnostics exceed bound or contain a private fixture value')
        print('ARM64 Linux TUN lifecycle passed: private control/status, stop, SIGTERM, SIGKILL removal and stale socket restart; isolated namespace, no server/VK acceptance')
    finally:
        for process in processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
        if owned_namespace:
            for raw_pid in network('netns', 'pids', namespace, check=False).stdout.split():
                try:
                    os.kill(int(raw_pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            network('netns', 'delete', namespace)


if __name__ == '__main__':
    try:
        main()
    except CheckFailure as error:
        print('ARM64 TUN lifecycle failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Exception details can contain paths or runtime data. Keep CI diagnostics bounded.
        print('ARM64 TUN lifecycle failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
