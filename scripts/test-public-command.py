#!/usr/bin/env python3
"""Post-publication acceptance of the literal released README HTTPS command.

No signing secrets, private fixture, installer substitution or router access.
The output is independent evidence; it cannot qualify or modify release assets.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

from release_schema import artifact, describe, load, require, token, validate
from openwrt_image import extract_openwrt_image
from vm_disk import expand_disposable_root
from vm_console import prepare_guest_console

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOSITORY = 'RATOR2000/csqtt-openwrt'
RELEASE_METADATA_LIMIT = 4 * 1024 * 1024
PHASE = 'public_metadata'


def phase(name):
    global PHASE
    PHASE = name
    print('Public command VM phase: ' + name, flush=True)


def import_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def readme_command(text, tag):
    blocks = re.findall(r'^```sh\r?\n(.*?)\r?\n```', text, flags=re.MULTILINE | re.DOTALL)
    require(blocks, 'Released README contains no installation shell block')
    command = blocks[0].strip()
    expected = ('uclient-fetch -O /tmp/csqtt-install.sh https://github.com/' + REPOSITORY +
                '/releases/download/' + tag + '/install.sh && sh /tmp/csqtt-install.sh ' + tag)
    require(command == expected, 'Released README command is not the exact pinned HTTPS/tempfile command')
    return command


def download(url, maximum=67108864):
    require(url.startswith(('https://api.github.com/repos/' + REPOSITORY + '/',
                            'https://github.com/' + REPOSITORY + '/releases/download/')), 'Foreign download URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'CSQTT-public-acceptance'})
    with urllib.request.urlopen(request, timeout=90) as response:
        require(response.url.startswith(('https://api.github.com/', 'https://github.com/',
                                         'https://release-assets.githubusercontent.com/')), 'Foreign asset redirect')
        data = response.read(maximum + 1)
    require(0 < len(data) <= maximum, 'Public asset exceeds bound')
    return data


def verify_signature(path, signature, key):
    subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(key), '-signature', str(signature), str(path)],
                   check=True, capture_output=True, timeout=30)


def public_bundle(tag, profile, source, directory):
    require(re.fullmatch(r'v0\.1\.0-preview\.[1-9][0-9]*', tag) and int(tag.rsplit('.', 1)[1]) >= 10,
            'An exact new published preview tag is required')
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], check=True,
                            capture_output=True, text=True).stdout.strip()
    actual_tag = subprocess.run(['git', '-C', str(source), 'describe', '--exact-match', '--tags', 'HEAD'],
                                check=True, capture_output=True, text=True).stdout.strip()
    require(actual_tag == tag and re.fullmatch('[0-9a-f]{40}', commit), 'Source checkout is not the exact release tag')
    key = ROOT / 'release/csqtt-public.pem'
    require(key.read_bytes() == (source / 'release/csqtt-public.pem').read_bytes(), 'Release public key differs from the pinned key')
    command = readme_command((source / 'README.md').read_text(encoding='utf-8'), tag)
    release = json.loads(download('https://api.github.com/repos/' + REPOSITORY + '/releases/tags/' + tag, RELEASE_METADATA_LIMIT))
    require(release.get('tag_name') == tag and release.get('draft') is False and release.get('published_at'),
            'Release is not publicly published')
    assets = {}
    for asset in release.get('assets', []):
        name = asset.get('name')
        require(token(name) and name not in assets, 'Invalid or duplicate public asset')
        assets[name] = asset
    base = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/'

    def fetch(name, entry=None, maximum=67108864):
        require(token(name) and name in assets and assets[name].get('browser_download_url') == base + name,
                'Signed artifact is missing from the exact public release')
        path = directory / name
        path.write_bytes(download(base + name, maximum))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(assets[name].get('size') == path.stat().st_size, 'Public asset size differs from GitHub metadata')
        api_digest = assets[name].get('digest')
        require(api_digest is None or api_digest == 'sha256:' + digest, 'Public asset digest differs from GitHub metadata')
        if entry:
            artifact(entry, directory)
        return path

    catalogue_path = fetch('catalogue.json', maximum=262144)
    catalogue_signature = fetch('catalogue.sig', maximum=1024)
    verify_signature(catalogue_path, catalogue_signature, key)
    catalogue = load(catalogue_path)
    require(catalogue.get('schema') == 2 and catalogue.get('upstream') == 'amurcanov/csqtt@v2.1.9', 'Invalid signed catalogue')
    profiles = catalogue.get('profiles')
    require(isinstance(profiles, list) and 0 < len(profiles) <= 128, 'Invalid catalogue profile count')
    selected = None
    seen = set()
    for entry in profiles:
        ident = entry.get('profile_id')
        require(token(ident) and ident not in seen and entry.get('name') == ident + '-manifest.json', 'Ambiguous signed profile')
        seen.add(ident)
        path = fetch(entry['name'], entry, 262144)
        sig = fetch(entry['signature']['name'], entry['signature'], 1024)
        verify_signature(path, sig, key)
        manifest = validate(load(path))
        q = manifest['qualification']
        require(manifest['profile_id'] == ident and q.get('source_commit') == commit and
                q.get('installation') is True and q.get('activation') is True and q.get('preview') is True and
                q.get('reason') == 'clean_official_firmware_vm_and_selected_abi_preview', 'Public profile does not bind the released source/acceptance')
        if ident == profile:
            selected = manifest
    require(selected is not None, 'Selected native VM tuple is absent from the public catalogue')
    entries = [*selected['packages'], *selected['dependency_bundle']['packages'], *selected['dependency_bundle']['indexes'],
               *selected['qualification']['proofs'], *selected.get('third_party_sources', [])]
    entries.extend(i['signature'] for i in selected['dependency_bundle']['indexes'] if 'signature' in i)
    for entry in entries:
        fetch(entry['name'], entry)
    validate(selected, directory)
    installer = fetch('install.sh', maximum=1048576)
    require(installer.read_bytes() == (source / 'install.sh').read_bytes(), 'Published installer differs from the tagged source')
    return selected, command, {'tag': tag, 'id': release['id'], 'published_at': release['published_at'],
            'source_commit': commit, 'installer': describe(installer), 'catalogue': describe(catalogue_path),
            'verification_scope': 'signed_catalogue_all_manifests_and_selected_profile_assets'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-tag', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--released-source', required=True, type=pathlib.Path)
    parser.add_argument('--directory', required=True, type=pathlib.Path)
    args = parser.parse_args()
    require(not os.environ.get('CSQTT_SIGNING_KEY'), 'Public acceptance must not receive a signing secret')
    require(not args.directory.exists(), 'Public acceptance output directory must be new')
    args.directory.mkdir(parents=True)
    manifest, command, released = public_bundle(args.public_tag, args.profile, args.released_source, args.directory)
    platform = manifest['platform']
    require(platform['family'] == 'official' and platform['target'] == 'x86/64' and platform['architecture'] == 'x86_64',
            'Public VM requires the exact official x86 package/kernel tuple')
    vm, bundle, evidence = import_script('vm', 'test-openwrt-vm.py'), import_script('bundle', 'bundle-dependencies.py'), import_script('evidence', 'release-evidence.py')
    version = platform['openwrt']
    require(version in vm.IMAGES, 'No pinned public acceptance firmware image')
    import pexpect
    with tempfile.TemporaryDirectory(prefix='csqtt-public-vm-') as temporary:
        work = pathlib.Path(temporary)
        image_name = f'openwrt-{version}-x86-64-generic-ext4-combined.img.gz'
        compressed = work / image_name
        bundle.download(f'https://downloads.openwrt.org/releases/{version}/targets/x86/64/' + image_name, compressed, vm.IMAGES[version])
        disk = work / 'guest.img'
        image_extraction = extract_openwrt_image(compressed, disk, vm.IMAGES[version])
        phase('disk_prepare')
        test_disk = expand_disposable_root(disk, work)
        private_key = work / 'ssh-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(private_key)], check=True, capture_output=True)
        public_key = private_key.with_suffix('.pub').read_text().strip()
        port = vm.free_port()
        phase('clean_firmware_boot')
        guest = pexpect.spawn('qemu-system-x86_64', ['-accel', 'tcg', '-m', '768', '-smp', '2',
            '-drive', f'file={disk},format=raw,if=virtio', '-nographic', '-no-reboot',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22', '-device', 'virtio-net-pci,netdev=net0'],
            encoding='utf-8', timeout=180)
        try:
            prepare_guest_console(guest, public_key, phase)
            ssh = ['ssh', '-i', str(private_key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=' + str(work / 'known_hosts'),
                   '-o', 'ConnectTimeout=3', '-p', str(port), 'root@127.0.0.1']

            def remote(script, timeout=600, check=True, input_text=None):
                result = subprocess.run(ssh + ['set -eu; ' + script], input=input_text, capture_output=True, text=True, timeout=timeout)
                if check and result.returncode:
                    print(f'Public command failure: stage={PHASE} exit={result.returncode}', flush=True)
                    diagnostics = subprocess.run(ssh + ['for f in /tmp/csqtt-public/*.private.log; do [ ! -f "$f" ] || tail -c 8192 "$f"; done'],
                                                 capture_output=True, text=True, timeout=15)
                    private = diagnostics.stdout
                    markers = re.findall(r'CSQTT_GUEST_STAGE=([a-z_]{1,50})(?:\s|$)', private)
                    if markers:
                        print('Public guest substage: ' + markers[-1], flush=True)
                    reasons = {'resource_limit': ('Недостаточно', 'No space left'),
                               'dependency_solver': ('unable to select packages', 'unsatisfiable', 'изолированной базе'),
                               'signature_rejected': ('UNTRUSTED signature', 'Verification failure', 'подпись'),
                               'https_download': ('Connection failed', 'Failed to download', 'certificate', 'Не удалось скачать')}
                    for reason, needles in reasons.items():
                        if any(needle in private for needle in needles):
                            print('Public guest reason: ' + reason, flush=True)
                    raise ValueError('Public README command acceptance failed')
                return result

            deadline = time.monotonic() + 90
            while remote('true', timeout=6, check=False).returncode:
                require(time.monotonic() < deadline, 'Public VM SSH readiness timeout')
                time.sleep(1)
            phase('missing_dependencies_fixture')
            remote('mkdir -p /tmp/csqtt-public; test ! -x /usr/bin/csqtt-client; '
                   'if command -v apk >/dev/null; then names=$(apk --no-network info --from installed); '
                   'else names=$(opkg list-installed | cut -d " " -f 1); fi; '
                   'remove=$(printf "%s\\n" "$names" | awk \'/^luci($|-)|^uhttpd($|-)|^openssl-util$|^kmod-tun$/ {print}\'); '
                   'if [ -n "$remove" ]; then if command -v apk >/dev/null; then apk --no-network del $remove; '
                   'else opkg remove $remove; fi; fi > /tmp/csqtt-public/fixture.private.log 2>&1; '
                   'rmmod tun >/dev/null 2>&1 || true; '
                   'test ! -x /usr/bin/openssl; test ! -x /usr/sbin/uhttpd; test ! -f /www/luci-static/resources/ui.js; '
                   '! grep -q "^tun " /proc/modules; '
                   'sha256sum /etc/config/dhcp /etc/config/firewall /etc/config/network > /tmp/csqtt-public/before.sha256')
            remote('cat > /tmp/csqtt-public/guest.sh', input_text=(args.released_source / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8'))
            phase('literal_readme_https_install')
            remote('cd /tmp/csqtt-public; (' + command + ') > install.private.log 2>&1', timeout=1200)
            installed_hash = remote('sha256sum /tmp/csqtt-install.sh').stdout.split()[0]
            require(installed_hash == released['installer']['sha256'], 'Guest ran different public installer bytes')
            phase('native_runtime_dns_firewall_luci')
            smoke = remote('cd /tmp/csqtt-public; sh guest.sh > smoke.private.log 2>&1; tail -n 1 smoke.private.log')
            require(smoke.stdout.strip() == 'CSQTT_GUEST_SMOKE_PASS', 'Released native guest smoke did not pass')
            phase('literal_readme_repeat_settings_preserved')
            remote('cd /tmp/csqtt-public; sha256sum -c before.sha256 >/dev/null; uci set csqtt.main.workers=18; uci commit csqtt; '
                   'sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network > repeat.sha256; '
                   '(' + command + ') > repeat.private.log 2>&1; sha256sum -c repeat.sha256 >/dev/null', timeout=1200)
            phase('native_application_removal')
            remote('cd /tmp/csqtt-public; test "$(uci -q get csqtt.main.enabled)" = 0; '
                   '! uci show csqtt | grep -q "=device$"; '
                   'if command -v apk >/dev/null; then apk --no-network del luci-app-csqtt csqtt-captcha csqtt; '
                   'else opkg remove luci-app-csqtt csqtt-captcha csqtt; fi > uninstall.private.log 2>&1; '
                   'sha256sum -c repeat.sha256 >/dev/null; '
                   'test ! -x /usr/bin/csqtt-client; test ! -x /usr/bin/csqtt-captcha; '
                   'test ! -f /usr/share/luci/menu.d/luci-app-csqtt.json; '
                   'wget -q -O luci-after http://127.0.0.1/cgi-bin/luci/; test -s luci-after; '
                   'nslookup -type=A example.com 127.0.0.1 > dns-after.private.log 2>&1; '
                   'ubus call network.interface.lan status > lan-after.private.log; '
                   'jsonfilter -i lan-after.private.log -e "@.up" | grep -qx true')
            result = {'schema': 1, 'kind': 'published_readme_command_vm', 'result': 'pass',
                      'release': released, 'acceptance_source_commit': evidence.source(), 'profile_id': args.profile,
                      'openwrt': version, 'package_manager': platform['package_manager'], 'physical_device': False,
                      'image': {'name': image_name, 'sha256': vm.IMAGES[version], 'root_partition': 'expanded_disposable_vm',
                                'extraction': image_extraction, 'test_disk': test_disk},
                      'fixture': 'native_removal_of_luci_uhttpd_openssl_tool_tun_before_install',
                      'command': command, 'packages': evidence.package_binding(manifest),
                      'checks': ['public_signed_metadata_and_selected_assets', 'released_installer_source_equality',
                                 'literal_readme_https_command', 'native_missing_dependencies_install',
                                 'native_runtime_dns_firewall_luci', 'literal_readme_repeat_settings_preserved',
                                 'native_three_application_removal', 'four_configs_lan_luci_system_dns_preserved'],
                      'removal_scope': 'wizard_disabled_no_assigned_devices_no_protected_wan_deactivation_test'}
            (args.directory / (args.profile + '-public-command-evidence.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        finally:
            guest.terminate(force=True)
            guest.close(force=True)
    print('Published README HTTPS command and native install/repeat/removal passed in isolated OpenWrt VM; physical router/VK unverified.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Public command acceptance failed at stage=' + PHASE + '; no release assets were modified and private logs are omitted.') from None
