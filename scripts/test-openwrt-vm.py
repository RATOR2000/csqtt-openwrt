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

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMAGES = {
    '25.12.5': '23e2538e8ab0eb52dfed1c65d608ecdb71ffd432dd54885da138ae67cd9e4461',
    '24.10.8': '23872c64fdb66d0765e0d17f71453a66e7a91e9ecb10606d5f738e6d166e14ae',
    '25.12.6': 'f8538784d0288b4133a99ac2a68443e4922ffde6343e80df56a5882364b9d499',
}
PHASE = 'host_preflight'


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


def run_remote(ssh, command, timeout=600, check=True):
    result = subprocess.run(ssh + ['set -eu; ' + command], capture_output=True, text=True, timeout=timeout)
    # Private native diagnostics never enter public evidence/logs.
    if check and result.returncode:
        print(f'OpenWrt VM failure: stage={PHASE} exit={result.returncode}', flush=True)
        # Capture only bounded private diagnostics into host memory;
        # emit fixed enums, never package logs or configuration text.
        diagnostics = subprocess.run(ssh + [
            'for f in /tmp/csqtt-native/*.private.log; do [ ! -f "$f" ] || tail -c 8192 "$f"; done'],
            capture_output=True, text=True, timeout=15)
        private = diagnostics.stdout
        markers = re.findall(r'CSQTT_GUEST_STAGE=([a-z_]{1,50})(?:\s|$)', private)
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
            guest.expect('Please press Enter to activate this console')
            guest.sendline('')
            guest.expect(r'root@OpenWrt:.*#')
            guest.sendline("stty -echo; mkdir -p /etc/dropbear; printf '%s\\n' '" + public_key + "' > /etc/dropbear/authorized_keys; chmod 600 /etc/dropbear/authorized_keys; uci set network.lan.proto=dhcp; uci commit network; /etc/init.d/dropbear restart; /etc/init.d/network restart; echo CSQTT_CONSOLE_READY")
            guest.expect('CSQTT_CONSOLE_READY', timeout=90)
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
            rejected = remote('cd /tmp/csqtt-native; sh install.sh ci-private > reject.private.log 2>&1', check=False)
            require(rejected.returncode != 0, 'Wrong project signature was accepted')
            remote('cd /tmp/csqtt-native; sha256sum -c before.sha256 >/dev/null; test ! -x /usr/bin/csqtt-client')
            signature.write_bytes(valid_signature)
            phase('first_offline_install')
            remote('cd /tmp/csqtt-native; sh install.sh ci-private > install.private.log 2>&1')
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
