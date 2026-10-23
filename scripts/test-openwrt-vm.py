#!/usr/bin/env python3
"""Boot a disposable pinned stock OpenWrt VM and exercise the signed installer.

Only loopback host forwarding and a new temporary disk/key are used. No physical
router connection is supported. The provisionally qualified fixture is private
to this test; release qualification is generated only after this command passes.
"""
import argparse
import functools
import hashlib
import http.server
import importlib.util
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error

from release_schema import describe, load, require, validate
from openwrt_image import extract_openwrt_image
from vm_disk import expand_disposable_root
from vm_console import prepare_guest_console

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMAGES = {
    '25.12.5': '23e2538e8ab0eb52dfed1c65d608ecdb71ffd432dd54885da138ae67cd9e4461',
    '24.10.8': '23872c64fdb66d0765e0d17f71453a66e7a91e9ecb10606d5f738e6d166e14ae',
    '25.12.6': 'f8538784d0288b4133a99ac2a68443e4922ffde6343e80df56a5882364b9d499',
}
PHASE = 'host_preflight'
SIGNATURE_REJECTION = 'CSQTT: Подпись выпуска недействительна'
DIAGNOSTIC_READ_OK = 'CSQTT_PRIVATE_LOG_READ_OK'
DIAGNOSTIC_LIMIT = 8192
PRIVATE_TRACE = "PS4='+CSQTT_XTRACE:${LINENO:-0}: '; export PS4; sh -x install.sh ci-private"
KNOWN_TOOLS = ('uclient-fetch', 'sha256sum', 'awk', 'tar', 'sync', 'du', 'mktemp', 'wc', 'sed', 'cut',
               'cat', 'cp', 'mkdir', 'rm', 'mv', 'rmdir', 'chmod', 'grep', 'sort', 'tr', 'date', 'sleep',
               'id', 'openssl', 'jsonfilter', 'usign', 'opkg', 'apk', 'uci', 'ubus', 'dd', 'tail')
SHELL_ERRORS = {
    'syntax_error': ('syntax error',),
    'unset_parameter': ('parameter not set', 'unbound variable'),
    'arithmetic_error': ('arithmetic syntax error', 'arithmetic expression'),
    'permission_denied': ('Permission denied',),
    'read_only_filesystem': ('Read-only file system',),
}
PRIVATE_PHASE_LOGS = {
    'bootstrap_and_signature_rejection': 'reject',
    'first_offline_install': 'install',
    'native_runtime_dns_firewall_luci': 'smoke',
    'repeat_install_settings_preserved': 'repeat',
}


def phase(value):
    global PHASE
    PHASE = value
    print('OpenWrt VM phase: ' + value, flush=True)


def failure_message(error):
    # Exception messages, commands, URLs, output and filenames may contain
    # private data. Emit only its class and a bounded numeric HTTP status.
    category = type(error).__name__
    category = category if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', category) else 'Exception'
    status = ''
    if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
        status = ' http_status=' + str(error.code)
    return ('Clean OpenWrt VM acceptance failed at stage=' + PHASE + ' exception=' + category + status +
            '; private diagnostics are not printed or published.')


def free_port():
    with socket.socket() as bound:
        bound.bind(('127.0.0.1', 0))
        return bound.getsockname()[1]


def installer_diagnostics(private):
    """Map bounded private text to trusted source line numbers and fixed enums."""
    private = private[-40960:]
    source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8')
    errors = set()
    for number, line in enumerate(source.splitlines(), 1):
        for match in re.finditer(r"\bcsqtt_portable_die\s+'([^'\r\n]+)'", line):
            # Only complete hardcoded messages qualify, never a dynamic value
            # or a matching prefix taken from configuration/package output.
            if re.search(r'(?m)^CSQTT: ' + re.escape(match[1]) + r'\r?$', private):
                errors.add(number)
    tools = []
    for tool in KNOWN_TOOLS:
        explicit = 'CSQTT: В прошивке отсутствует необходимая команда: ' + tool
        missing = r'(?m)(?:^|[ :])' + re.escape(tool) + r': (?:not found|command not found)\r?$'
        if re.search(r'(?m)^' + re.escape(explicit) + r'\r?$', private) or re.search(missing, private):
            tools.append(tool)
    shell = [name for name, needles in SHELL_ERRORS.items() if any(needle in private for needle in needles)]
    generated_lines = sorted({int(n) for n in re.findall(
        r'(?m)^(?:install\.sh|[^ \r\n]*/install\.sh): (?:line )?([1-9][0-9]{0,4}):', private)
        if int(n) <= len((ROOT / 'install.sh').read_text(encoding='utf-8').splitlines())})
    installer = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
    functions = set(re.findall(r'^(csqtt_[A-Za-z0-9_]+)\(\)', '\n'.join(installer), re.MULTILINE))
    traced_functions, last_line = [], None
    for line in private.splitlines():
        trace = re.match(r'^\++CSQTT_XTRACE:([0-9]{1,6}):\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s|$)', line)
        if not trace:
            continue
        number, name = int(trace[1]), trace[2]
        # Stop before EXIT cleanup obscures the original failure. The emitted
        # names and source numbers are defined by this checkout, never values.
        if name in ('csqtt_portable_cleanup', 'csqtt_operation_cleanup'):
            break
        if 0 < number <= len(installer):
            last_line = number
        if name in functions and (not traced_functions or traced_functions[-1] != name):
            traced_functions.append(name)
    return {'portable_error_lines': sorted(errors), 'missing_tools': tools, 'shell_errors': shell,
            'generated_error_lines': generated_lines, 'trace_functions': traced_functions[-8:],
            'trace_last_source_line': last_line}


def private_log_read_command():
    name = PRIVATE_PHASE_LOGS.get(PHASE)
    if name is None:
        return 'exit 1'
    # Baseline BusyBox wc/dd suffice; tail -c is not a required capability.
    # The byte count and read must both succeed before the sentinel is emitted.
    # No earlier phase log may supply a reason for the current failure.
    return ('f=/tmp/csqtt-native/' + name + '.private.log; [ -f "$f" ] || exit 1; '
            'n=$(wc -c < "$f") || exit 1; set -- $n; [ "$#" = 1 ] || exit 1; n=$1; '
            'case "$n" in ""|*[!0-9]*) exit 1;; esac; '
            'skip=0; [ "$n" -le 8192 ] || skip=$((n-8192)); '
            'dd if="$f" bs=1 skip="$skip" count=8192 2>/dev/null || exit 1; '
            'printf "\\n' + DIAGNOSTIC_READ_OK + '\\n"')


def run_remote(ssh, command, timeout=600, check=True):
    result = subprocess.run(ssh + ['set -eu; ' + command], capture_output=True, text=True, timeout=timeout)
    # Private native diagnostics never enter public evidence/logs.
    if check and result.returncode:
        print(f'OpenWrt VM failure: stage={PHASE} exit={result.returncode}', flush=True)
        # Capture only bounded private diagnostics into host memory;
        # emit fixed enums, never package logs or configuration text.
        try:
            diagnostics = subprocess.run(ssh + [private_log_read_command()],
                capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            diagnostics = None
        sentinel = ('\n' + DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        if (diagnostics is None or diagnostics.returncode != 0 or
                not diagnostics.stdout.endswith(sentinel) or
                len(diagnostics.stdout) > DIAGNOSTIC_LIMIT + len(sentinel)):
            print('OpenWrt guest diagnostics: diagnostic_unavailable', flush=True)
            private = result.stderr[-DIAGNOSTIC_LIMIT:]
        else:
            print('OpenWrt guest diagnostics: bounded_read_ok', flush=True)
            # A bounded byte tail may begin inside a UTF-8 character. Validate
            # transport framing before decoding so replacement cannot inflate
            # the measured byte count and reject an otherwise valid read.
            log = diagnostics.stdout[:-len(sentinel)].decode('utf-8', errors='replace')
            private = (log + result.stderr[-DIAGNOSTIC_LIMIT:])[-DIAGNOSTIC_LIMIT:]
        classified = installer_diagnostics(private)
        for line in classified['portable_error_lines']:
            print('OpenWrt installer error: portable_source_line=' + str(line), flush=True)
        for line in classified['generated_error_lines']:
            print('OpenWrt installer shell location: generated_line=' + str(line), flush=True)
        for tool in classified['missing_tools']:
            print('OpenWrt missing tool: ' + tool, flush=True)
        for category in classified['shell_errors']:
            print('OpenWrt shell error: ' + category, flush=True)
        for name in classified['trace_functions']:
            print('OpenWrt installer trace function: ' + name, flush=True)
        if classified['trace_last_source_line'] is not None:
            print('OpenWrt installer trace: generated_source_line=' + str(classified['trace_last_source_line']), flush=True)
        allowed_stages = set(re.findall(r'^stage ([a-z_]{1,50})$',
                            (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8'), re.MULTILINE))
        markers = [m for m in re.findall(r'CSQTT_GUEST_STAGE=([a-z_]{1,50})(?:\s|$)', private) if m in allowed_stages]
        if markers:
            print('OpenWrt guest substage: ' + markers[-1], flush=True)
        reasons = {
            'signature_rejected': ('UNTRUSTED signature', 'BAD signature', 'Verification failure', 'подпись'),
            'dependency_solver': ('unable to select packages', 'unsatisfiable', 'Неполный набор зависимостей', 'не прошла в изолированной базе'),
            'resource_limit': ('Недостаточно', 'No space left'),
            'network_fetch': ('Connection failed', 'Failed to download', 'не удалось скачать', 'Не удалось скачать'),
            'kernel_abi': ('ядра не совпадает', 'kernel mismatch'),
        }
        for reason, needles in reasons.items():
            if any(needle in private for needle in needles):
                print('OpenWrt guest reason: ' + reason, flush=True)
        raise ValueError('Disposable guest command failed; native acceptance was not granted')
    return result


def require_signature_rejection(remote, rejected):
    require(rejected.returncode != 0, 'Wrong project signature was accepted')
    # A missing tool or other early refusal cannot count as signature evidence.
    remote("cd /tmp/csqtt-native; grep -Fqx '" + SIGNATURE_REJECTION +
           "' reject.private.log; sha256sum -c before.sha256 >/dev/null; test ! -x /usr/bin/csqtt-client")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=pathlib.Path, required=True)
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    phase('validation')
    manifest = validate(load(args.directory / (args.profile + '-manifest.json')), args.directory)
    platform = manifest['platform']
    require(platform['target'] == 'x86/64' and platform['architecture'] == 'x86_64', 'VM guest must use its own exact x86 package/kernel tuple')
    version = platform['openwrt']
    require(version in IMAGES, 'No pinned clean firmware image')
    require(manifest['qualification'].get('reason') == 'private_ci_fixture_only', 'Use an isolated signed provisional fixture')
    phase('imports')
    import pexpect  # CI installs this small host-only console driver.
    spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-dependencies.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    evidence_spec = importlib.util.spec_from_file_location('evidence', ROOT / 'scripts/release-evidence.py')
    evidence = importlib.util.module_from_spec(evidence_spec)
    evidence_spec.loader.exec_module(evidence)
    output = args.directory / (args.profile + '-vm-evidence.json')
    phase('fixture_copy')
    with tempfile.TemporaryDirectory(prefix='csqtt-vm-') as temporary:
        work = pathlib.Path(temporary)
        web = work / 'web'
        web.mkdir()
        fixture = web / 'ci-private'
        shutil.copytree(args.directory, fixture)
        catalogue = {'schema': 2, 'upstream': manifest['upstream'], 'profiles': [{
            **describe(fixture / (args.profile + '-manifest.json')), 'profile_id': args.profile,
            'signature': describe(fixture / (args.profile + '-manifest.sig'))}]}
        (fixture / 'catalogue.json').write_text(json.dumps(catalogue, indent=2) + '\n')
        # sign-portable-release refuses a provisional catalogue by design. Sign
        # only this test's exact private catalogue with a short-lived key file.
        phase('catalogue_signing')
        secret = os.environ.pop('CSQTT_SIGNING_KEY', '')
        require(secret, 'Private CI fixture signing key unavailable')
        key = work / 'fixture-signing.pem'
        key.write_text(secret)
        key.chmod(0o600)
        secret = None
        subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key), '-out', str(fixture / 'catalogue.sig'),
                        str(fixture / 'catalogue.json')], check=True, capture_output=True)
        key.unlink()
        phase('fixture_server')
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *unused):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(web)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://10.0.2.2:{server.server_port}'
        installer = (ROOT / 'install.sh').read_text()
        original = 'https://github.com/RATOR2000/csqtt-openwrt/releases/download/'
        require(original in installer, 'Installer fixture URL seam changed')
        installer = installer.replace(original, url + '/')
        installer = installer.replace('https://github.com/RATOR2000/csqtt-openwrt/releases/latest/download', url + '/ci-private')
        (web / 'install.sh').write_text(installer, newline='\n')
        shutil.copyfile(ROOT / 'scripts/test-openwrt-guest.sh', web / 'guest.sh')
        image_name = f'openwrt-{version}-x86-64-generic-ext4-combined.img.gz'
        compressed = work / image_name
        phase('image_download')
        bundle.download(f'https://downloads.openwrt.org/releases/{version}/targets/x86/64/' + image_name,
                        compressed, IMAGES[version])
        disk = work / 'guest.img'
        phase('image_extract')
        image_extraction = extract_openwrt_image(compressed, disk, IMAGES[version])
        phase('disk_prepare')
        test_disk = expand_disposable_root(disk, work)
        private_key = work / 'ssh-key'
        phase('ssh_key')
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(private_key)], check=True, capture_output=True)
        public_key = private_key.with_suffix('.pub').read_text().strip()
        port = free_port()
        phase('clean_firmware_boot')
        guest = pexpect.spawn('qemu-system-x86_64', ['-accel', 'tcg', '-m', '768', '-smp', '2',
            '-drive', f'file={disk},format=raw,if=virtio', '-nographic', '-no-reboot',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22',
            '-device', 'virtio-net-pci,netdev=net0'], encoding='utf-8', timeout=180)
        try:
            prepare_guest_console(guest, public_key, phase)
            ssh = ['ssh', '-i', str(private_key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=' + str(work / 'known_hosts'),
                   '-o', 'ConnectTimeout=3', '-p', str(port), 'root@127.0.0.1']
            remote = functools.partial(run_remote, ssh)
            deadline = time.monotonic() + 90
            while remote('true', timeout=6, check=False).returncode:
                require(time.monotonic() < deadline, 'Disposable VM SSH readiness timed out')
                time.sleep(1)
            phase('bootstrap_and_signature_rejection')
            remote(f'mkdir -p /tmp/csqtt-native; cd /tmp/csqtt-native; wget -q {url}/install.sh -O install.sh; wget -q {url}/guest.sh -O guest.sh; test -s install.sh; test -s guest.sh; sha256sum /etc/config/dhcp /etc/config/firewall /etc/config/network > before.sha256')
            signature = fixture / 'catalogue.sig'
            valid_signature = signature.read_bytes()
            signature.write_bytes(b'wrong signature fixture')
            rejected = remote('cd /tmp/csqtt-native; ' + PRIVATE_TRACE + ' > reject.private.log 2>&1', check=False)
            require_signature_rejection(remote, rejected)
            signature.write_bytes(valid_signature)
            phase('first_offline_install')
            remote('cd /tmp/csqtt-native; ' + PRIVATE_TRACE + ' > install.private.log 2>&1')
            phase('native_runtime_dns_firewall_luci')
            smoke = remote('cd /tmp/csqtt-native; sh guest.sh > smoke.private.log 2>&1 && tail -n 1 smoke.private.log')
            require(smoke.stdout.strip() == 'CSQTT_GUEST_SMOKE_PASS', 'Native runtime/DNS/firewall/LuCI guest proof missing')
            # The actual production installer mandates native --no-network
            # staging and install; only authenticated release assets use HTTP.
            phase('repeat_install_settings_preserved')
            remote('cd /tmp/csqtt-native; sha256sum -c before.sha256 >/dev/null; uci set csqtt.main.workers=18; uci commit csqtt; sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network > repeat.sha256; sh install.sh ci-private > repeat.private.log 2>&1; sha256sum -c repeat.sha256 >/dev/null')
            result = {'schema': 1, 'kind': 'clean_openwrt_vm', 'result': 'pass',
                      'source_commit': evidence.source(), 'profile_id': args.profile, 'openwrt': version,
                      'package_manager': platform['package_manager'], 'physical_device': False,
                      'image': {'name': image_name, 'sha256': IMAGES[version], 'extraction': image_extraction,
                                'test_disk': test_disk},
                      'packages': evidence.package_binding(manifest), 'checks': sorted(evidence.VM_CHECKS)}
            output.write_text(json.dumps(result, indent=2) + '\n')
        finally:
            guest.terminate(force=True)
            guest.close(force=True)
            server.shutdown()
            server.server_close()
    print('Clean OpenWrt VM signed installer/offline dependencies/reinstall/native runtime acceptance passed; no physical router or VK proof.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(failure_message(error)) from None
