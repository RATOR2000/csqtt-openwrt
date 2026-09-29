#!/usr/bin/env python3
"""Exercise the real shell source with command doubles in disposable roots.

No production test-root option is added to install.sh. This harness rewrites
its literal router paths in a temporary copy, then checks the executed calls.
Native APK solver/crypto/daemon behavior still requires OpenWrt acceptance.
"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
SH = shutil.which('sh')
if not SH:
    git = pathlib.Path(shutil.which('git') or '')
    candidate = git.parent.parent / 'usr/bin/sh.exe'
    SH = str(candidate) if candidate.exists() else None
NODE = shutil.which('node')


def posix(path):
    value = str(path).replace('\\', '/')
    return '/' + value[0].lower() + value[2:] if len(value) > 2 and value[1] == ':' else value


@unittest.skipUnless(SH and NODE, 'POSIX sh and Node are required')
class InstallerTest(unittest.TestCase):
    def run_installer(self, scenario='success', *, repeat=False):
        workspace = REPO / '.work/installer-tests'
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='case-', dir=workspace) as directory:
            base = pathlib.Path(directory)
            root = base / 'router'
            bindir = base / 'bin'
            for relative in ['etc/config', 'etc/apk/keys', 'lib/apk/db', 'tmp/sysinfo', 'overlay', 'release']:
                (root / relative).mkdir(parents=True, exist_ok=True)
            bindir.mkdir()
            (root / '.installer-fixture').touch()
            (root / 'etc/openwrt_release').write_text("DISTRIB_RELEASE='25.12.5'\nDISTRIB_TARGET='mediatek/filogic'\n")
            (root / 'tmp/sysinfo/board_name').write_text('glinet,gl-mt6000\n' if scenario != 'board' else 'other,router\n')
            (root / 'etc/apk/arch').write_text('aarch64_cortex-a53\n')
            (root / 'etc/apk/keys/openwrt.pem').write_text('public fixture key\n')
            (root / 'etc/config/dhcp').write_text('fixture local DNS config\n')
            initial = {'base-files': '1', 'dnsmasq-full' if repeat else 'dnsmasq': '2.91-r2'}
            if repeat:
                initial.update({name: '0.0.9-r1' for name in ['csqtt', 'csqtt-captcha', 'luci-app-csqtt']})
            original_world = '\n'.join(initial) + '\n'
            (root / 'etc/apk/world').write_text(original_world)
            (root / 'lib/apk/db/installed').write_text(json.dumps(initial))
            manifest = {'schema': 1, 'openwrt': '25.12.5', 'target': 'mediatek/filogic', 'architecture': 'aarch64_cortex-a53', 'upstream': 'amurcanov/csqtt@v2.1.9', 'packages': []}
            for name in ['csqtt', 'csqtt-captcha', 'luci-app-csqtt']:
                filename = name + '-0.1.0-r1.apk'
                data = ('fixture signed ' + filename).encode()
                (root / 'release' / filename).write_bytes(data)
                manifest['packages'].append({'name': filename, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
            if scenario == 'checksum':
                manifest['packages'][0]['sha256'] = '0' * 64
            if scenario == 'duplicate':
                manifest['packages'][1] = manifest['packages'][0].copy()
            if scenario == 'filename':
                manifest['packages'][0]['name'] = '../outside.apk'
            if scenario == 'manifest_target':
                manifest['target'] = 'other/target'
            if scenario == 'extra_entry':
                manifest['packages'].append({})
            (root / 'release/manifest.json').write_text(json.dumps(manifest))
            (root / 'release/manifest.sig').write_bytes(b'fixture detached signature')
            wrapper = '#!/bin/sh\n"' + posix(NODE) + '" "' + posix(REPO / 'tests/installer/fake.cjs') + '" "$FAKE_COMMAND" "$@"\nstatus=$?\n[ "$status" != 143 ] || kill -TERM "$PPID"\nexit "$status"\n'
            for command in ['id', 'df', 'apk', 'uclient-fetch', 'jsonfilter', 'openssl', 'sha256sum', 'tar', 'chmod']:
                content = wrapper.replace('$FAKE_COMMAND', command)
                if command == 'openssl' and scenario.startswith('bootstrap'):
                    (root / 'openssl-wrapper').write_text(content, newline='\n')
                    (root / 'openssl-wrapper').chmod(0o755)
                    continue
                executable = bindir / command
                executable.write_text(content, newline='\n')
                executable.chmod(0o755)
            # Keep PATH fully controlled, including on Linux hosts which have
            # system OpenSSL installed. Core file operations remain real.
            for command in ['cat', 'awk', 'wc', 'mktemp', 'mkdir', 'cp', 'date', 'rm']:
                executable = bindir / command
                executable.write_text('#!/bin/sh\nexec /usr/bin/' + command + ' "$@"\n', newline='\n')
                executable.chmod(0o755)
            for service in ['dnsmasq', 'rpcd', 'csqtt', 'csqtt-captcha']:
                executable = root / 'etc/init.d' / service
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_text(wrapper.replace('$FAKE_COMMAND', 'service:' + service), newline='\n')
                executable.chmod(0o755)
            source = (REPO / 'install.sh').read_text()
            for prefix in ['/etc/', '/lib/apk/', '/tmp/', '/overlay']:
                source = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(prefix), posix(root) + prefix, source)
            source = source.replace('-C / etc/config', '-C "' + posix(root) + '" etc/config')
            script = base / 'install.sh'
            script.write_text(source, newline='\n')
            env = os.environ.copy()
            env.update(CSQTT_FAKE_ROOT=str(root), CSQTT_FAKE_SCENARIO=scenario, CSQTT_FAKE_BIN=str(bindir), MSYS2_ENV_CONV_EXCL='APK_CONFIG')
            # MSYS adjusts PATH on startup; set the isolated path inside sh.
            result = subprocess.run([SH, '-c', 'PATH="$CSQTT_WRAPPER_PATH"; export PATH; exec /usr/bin/sh "$CSQTT_WRAPPER_SCRIPT"'], env={**env, 'CSQTT_WRAPPER_PATH': posix(bindir), 'CSQTT_WRAPPER_SCRIPT': posix(script)}, text=True, capture_output=True, timeout=40)
            self.assertTrue((root / 'commands.jsonl').exists(), result.stdout + result.stderr)
            calls = [json.loads(line) for line in (root / 'commands.jsonl').read_text().splitlines()]
            installed = json.loads((root / 'lib/apk/db/installed').read_text())
            backups = list((root / 'etc/csqtt/backups').glob('*/config.tar.gz')) if (root / 'etc/csqtt/backups').exists() else []
            leftovers = list((root / 'tmp').glob('csqtt-install.*'))
            return result, calls, installed, backups, leftovers, (root / 'etc/apk/world').read_text(), original_world

    def test_first_install_and_repeat(self):
        for repeat in [False, True]:
            with self.subTest(repeat=repeat):
                result, calls, installed, backups, leftovers, _, _ = self.run_installer(repeat=repeat)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('dnsmasq-full', installed)
                self.assertNotIn('dnsmasq', installed)
                self.assertEqual(len(backups), 1)
                self.assertFalse(leftovers)
                live_deletes = [call for call in calls if call['command'] == 'apk' and 'del' in call['args'] and '--root' not in call['args']]
                self.assertEqual(len(live_deletes), 0 if repeat else 1)
                self.assertEqual(any(call['command'] == 'service:csqtt' and call['args'] == ['restart'] for call in calls), repeat)
                self.assertTrue(any(call['command'] == 'service:csqtt-captcha' and call['args'] == ['restart'] for call in calls))

    def test_preflight_failures_preserve_dns_and_configs(self):
        for scenario in ['board', 'architecture', 'space', 'manifest_target', 'filename', 'duplicate', 'download', 'package_signature', 'manifest_signature', 'checksum', 'rollback_cache', 'dependency', 'prefetch', 'remove_other']:
            with self.subTest(scenario=scenario):
                result, calls, installed, backups, _, world, original_world = self.run_installer(scenario)
                self.assertNotEqual(result.returncode, 0, scenario)
                self.assertEqual(installed.get('dnsmasq'), '2.91-r2', result.stderr)
                self.assertEqual(world, original_world)
                self.assertFalse(backups)
                self.assertFalse(any(call['command'] == 'apk' and ('del' in call['args'] or 'add' in call['args']) and '--root' not in call['args'] for call in calls))

    def test_extra_manifest_entry_and_missing_offline_cache(self):
        for scenario in ['extra_entry', 'offline_cache']:
            with self.subTest(scenario=scenario):
                result, calls, installed, backups, _, world, original_world = self.run_installer(scenario)
                self.assertNotEqual(result.returncode, 0, scenario)
                self.assertEqual(installed.get('dnsmasq'), '2.91-r2', result.stderr)
                self.assertEqual(world, original_world)
                self.assertFalse(backups)
                self.assertFalse(any(call['command'] == 'apk' and ('del' in call['args'] or 'add' in call['args']) and '--root' not in call['args'] for call in calls))

    def test_install_service_and_signal_failures_restore_exact_dns(self):
        for scenario in ['install', 'dnsmasq_restart', 'rpcd_restart', 'csqtt-captcha_enable', 'csqtt-captcha_restart', 'interrupt']:
            with self.subTest(scenario=scenario):
                result, calls, installed, backups, leftovers, world, original_world = self.run_installer(scenario)
                self.assertNotEqual(result.returncode, 0, scenario)
                self.assertEqual(installed.get('dnsmasq'), '2.91-r2', result.stdout + result.stderr)
                self.assertNotIn('dnsmasq-full', installed)
                self.assertEqual(world, original_world)
                self.assertEqual(len(backups), 1)
                self.assertEqual(len(leftovers), 1)
                self.assertTrue(any(call['command'] == 'apk' and any(arg.endswith('/rollback/dnsmasq-2.91-r2.apk') or arg.endswith('\\rollback\\dnsmasq-2.91-r2.apk') for arg in call['args']) for call in calls))

    def test_upgrade_transport_restart_failure_retains_full_dns(self):
        result, calls, installed, backups, leftovers, _, _ = self.run_installer('csqtt_restart', repeat=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('dnsmasq-full', installed)
        self.assertNotIn('dnsmasq', installed)
        self.assertEqual(len(backups), 1)
        self.assertEqual(len(leftovers), 1)
        self.assertFalse(any(call['command'] == 'apk' and 'del' in call['args'] and '--root' not in call['args'] for call in calls))

    def test_bootstrap_requires_native_signed_packages(self):
        for scenario in ['bootstrap', 'bootstrap_signature']:
            with self.subTest(scenario=scenario):
                result, calls, installed, _, _, _, _ = self.run_installer(scenario)
                self.assertEqual(result.returncode == 0, scenario == 'bootstrap', result.stdout + result.stderr)
                self.assertIn('openssl-util', installed)
                if scenario == 'bootstrap_signature':
                    self.assertIn('dnsmasq', installed)
                    self.assertFalse(any(call['command'].startswith('service:') for call in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
