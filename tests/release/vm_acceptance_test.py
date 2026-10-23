#!/usr/bin/env python3
"""Mock the SSH transport while executing the real local POSIX shell contract."""
import contextlib
import importlib.util
import io
import pathlib
import re
import shutil
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('native_vm', ROOT / 'scripts/test-openwrt-vm.py')
native_vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_vm)
import vm_console
NONCE = 'a' * 32
STEP_PHASES = ['boot_network_config_wait', 'boot_authorized_key', 'boot_network_uci',
               'boot_dropbear_restart', 'boot_network_restart']
SH = shutil.which('sh')
if not SH:
    git = pathlib.Path(shutil.which('git') or '')
    candidate = git.parent.parent / 'usr/bin/sh.exe'
    SH = str(candidate) if candidate.is_file() else None


class VmAcceptanceTest(unittest.TestCase):
    def test_boot_signals_report_fixed_categories_without_console_content(self):
        private = 'private-key-command-url-fixture'
        console = ('GRUB Linux version 6.6 OpenWrt 24.10.8\n'
                   'VFS: Mounted root (ext4 filesystem)\n'
                   'Waiting for root device PARTUUID=private-value\n'
                   'Kernel panic - not syncing: private-value\n'
                   'Boot failed: No bootable device\n' + vm_console.ACTIVATION + '\n' +
                   vm_console.ROOT_MARKER + NONCE + '\r\r\n' + private + '\n' + vm_console.READY + NONCE + '\r\r\n' +
                   vm_console.STEP_OK + NONCE + '\n' + vm_console.STEP_FAIL + NONCE + '\n')
        signals = vm_console.boot_signals(console)
        self.assertEqual(set(signals), {name for name, pattern in vm_console.SIGNALS})
        self.assertNotIn(private, ','.join(signals))
        self.assertEqual(vm_console.boot_signals(console.encode()), signals)
        self.assertEqual(vm_console.boot_signals(None), ['no_output'])
        self.assertEqual(vm_console.boot_signals('opaque ' + private), ['unclassified_output'])

    def test_boot_signal_scan_is_bounded_to_last_64_kib(self):
        for value in ('Kernel panic ' + 'x' * vm_console.CONSOLE_LIMIT,
                      b'GRUB ' + b'x' * vm_console.CONSOLE_LIMIT,
                      'Linux version ' + '\u0430' * vm_console.CONSOLE_LIMIT):
            self.assertEqual(vm_console.boot_signals(value), ['unclassified_output'])
        self.assertEqual(vm_console.boot_signals('x' * vm_console.CONSOLE_LIMIT + '\nGRUB'), ['grub'])

    def test_console_boot_retains_handshake_command_and_distinct_phases(self):
        guest, phases = mock.Mock(), []
        guest.expect.return_value = 0
        private = 'ssh-ed25519 public-key-fixture'
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE) as nonce_source, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            vm_console.prepare_guest_console(guest, private, phases.append)
        self.assertEqual(nonce_source.call_args_list, [mock.call(16)] * 6)
        self.assertEqual(phases, ['boot_activation_wait', 'boot_console_activate',
                                 'boot_root_check', 'boot_root_check_wait', *STEP_PHASES])
        root_pattern = r'(?m)^' + vm_console.ROOT_MARKER + NONCE + r'\r*$'
        ready_pattern = r'(?m)^' + vm_console.READY + NONCE + r'\r*$'
        ok_pattern = r'(?m)^' + vm_console.STEP_OK + NONCE + r'\r*$'
        fail_pattern = r'(?m)^' + vm_console.STEP_FAIL + NONCE + r'\r*$'
        self.assertEqual(guest.expect.call_args_list,
                         [mock.call(vm_console.ACTIVATION), mock.call(root_pattern),
                          *[mock.call([ok_pattern, fail_pattern], timeout=90) for _ in range(4)],
                          mock.call([ready_pattern, fail_pattern], timeout=90)])
        self.assertEqual(guest.sendline.call_args_list[0], mock.call(''))
        root_command = guest.sendline.call_args_list[1].args[0]
        self.assertTrue(root_command.startswith('test "$(id -u)" = 0 && printf'))
        self.assertNotIn(vm_console.ROOT_MARKER + NONCE, root_command)
        commands = [call.args[0] for call in guest.sendline.call_args_list[2:]]
        self.assertIn('while [ "$(uci -q get network.lan 2>/dev/null)" != interface ]', commands[0])
        command = commands[1]
        self.assertIn("printf '%s\\n' '" + private + "' > /etc/dropbear/authorized_keys", command)
        self.assertIn('&& chmod 600 /etc/dropbear/authorized_keys', command)
        self.assertIn('uci set network.lan.proto=dhcp && uci commit network', commands[2])
        self.assertIn('/etc/init.d/dropbear restart', commands[3])
        self.assertIn('/etc/init.d/network restart', commands[4])
        for command in commands:
            self.assertTrue(command.startswith('if test "$(id -u)" = 0 && ('))
            self.assertNotIn('stty', command)
            self.assertNotIn(vm_console.READY + NONCE, command)
            self.assertNotIn(vm_console.STEP_FAIL + NONCE, command)
        self.assertEqual(output.getvalue(), '')

    def test_each_console_wait_failure_reports_only_fixed_signals_and_reraises(self):
        for failed_wait, stage in enumerate(('boot_activation_wait', 'boot_root_check_wait', *STEP_PHASES)):
            guest, phases = mock.Mock(), []
            private = 'private-console-command-key-https-fixture'
            guest.before = 'Linux version 6.6 ' + private
            error = TimeoutError(private)
            guest.expect.side_effect = [0] * failed_wait + [error]
            with self.subTest(stage=stage), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(TimeoutError) as raised:
                    vm_console.prepare_guest_console(guest, private, phases.append)
            self.assertIs(raised.exception, error)
            self.assertEqual(phases[-1], stage)
            self.assertEqual(output.getvalue(), 'OpenWrt VM boot signals: linux\n')
            self.assertNotIn(private, output.getvalue())
            self.assertEqual(guest.sendline.call_count, 0 if failed_wait == 0 else failed_wait + 1)

    def test_only_fresh_marker_output_matches_regardless_of_hostname_and_ansi_prompt(self):
        guest, phases, public_key = mock.Mock(), [], 'ssh-ed25519 key-fixture'
        waits = 0
        def expect(pattern, **options):
            nonlocal waits
            waits += 1
            if waits == 1:
                return 0
            command = guest.sendline.call_args.args[0]
            echoed = '\x1b[32mroot@different-host:/#\x1b[0m ' + command + '\r\n'
            patterns = pattern if isinstance(pattern, list) else [pattern]
            prefixes = ([vm_console.ROOT_MARKER] if waits == 2 else
                        [vm_console.READY if waits == 7 else vm_console.STEP_OK, vm_console.STEP_FAIL])
            for check, prefix in zip(patterns, prefixes):
                self.assertIsNone(re.search(check, echoed), 'Echoed command masqueraded as execution')
                for wrong in (prefix + 'b' * 32 + '\r\n', 'prefix-' + prefix + NONCE + '\r\n',
                              prefix + NONCE + '-suffix\r\n'):
                    self.assertIsNone(re.search(check, wrong))
                for ending in ('\n', '\r\n', '\r\r\n'):
                    self.assertIsNotNone(re.search(check, echoed + prefix + NONCE + ending))
            return 0
        guest.expect.side_effect = expect
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, public_key, phases.append)
        self.assertEqual(phases[-1], 'boot_network_restart')

    def test_echo_only_root_check_cannot_trigger_provisioning(self):
        guest, phases = mock.Mock(), []
        private = 'private-echo-command-fixture'
        def expect(pattern, **options):
            if pattern == vm_console.ACTIVATION:
                return 0
            guest.before = guest.sendline.call_args.args[0] + '\r\n' + private
            self.assertIsNone(re.search(pattern, guest.before))
            raise TimeoutError(private)
        guest.expect.side_effect = expect
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(TimeoutError):
                vm_console.prepare_guest_console(guest, private, phases.append)
        self.assertEqual(phases[-1], 'boot_root_check_wait')
        self.assertEqual(guest.sendline.call_count, 2)
        self.assertNotIn(private, output.getvalue())
        self.assertNotIn(NONCE, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the UID0/errexit contract')
    def test_uid0_and_successful_provision_are_required_for_marker_output(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None)
        root_command = guest.sendline.call_args_list[1].args[0]
        root_pattern = guest.expect.call_args_list[1].args[0]
        for uid in (0, 65534):
            command = 'id() { printf "%s\\n" ' + str(uid) + '; }; ' + root_command
            result = subprocess.run([SH, '-c', command], capture_output=True, text=True)
            self.assertEqual(bool(re.search(root_pattern, result.stdout)), uid == 0)
            self.assertEqual(result.returncode, 0 if uid == 0 else 1)
        # Execute the real per-step wrapper with harmless bodies only. Failure
        # must produce its fresh fixed FAIL marker while keeping the shell alive.
        for uid, body, success in ((0, 'true', True), (65534, 'true', False),
                                   (0, 'false && printf should-not-run', False)):
            guest = mock.Mock()
            guest.expect.return_value = 0
            with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
                vm_console._console_step(guest, lambda stage: None, 'synthetic_step', body)
            command = 'id() { printf "%s\\n" ' + str(uid) + '; }; ' + guest.sendline.call_args.args[0]
            result = subprocess.run([SH, '-c', command], capture_output=True, text=True, check=True)
            ok, fail = guest.expect.call_args.args[0]
            self.assertEqual(bool(re.search(ok, result.stdout)), success)
            self.assertEqual(bool(re.search(fail, result.stdout)), not success)
            self.assertNotIn('should-not-run', result.stdout)

    def test_each_explicit_step_failure_stops_without_proceeding_and_keeps_diagnostics_safe(self):
        for index, stage in enumerate(STEP_PHASES):
            guest, phases = mock.Mock(), []
            guest.before = vm_console.STEP_FAIL + NONCE + '\r\n'
            guest.expect.side_effect = [0] * (index + 2) + [1]
            with self.subTest(stage=stage), mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(ValueError, 'provisioning step failed'):
                    vm_console.prepare_guest_console(guest, 'private-key-fixture', phases.append)
            self.assertEqual(phases[-1], stage)
            self.assertEqual(guest.sendline.call_count, index + 3)
            self.assertEqual(output.getvalue(), 'OpenWrt VM boot signals: provision_step_failed\n')
            self.assertNotIn(NONCE, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the generated network readiness contract')
    def test_generated_lan_must_exist_before_any_network_mutation(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None)
        command = guest.sendline.call_args_list[2].args[0]
        ok, fail = guest.expect.call_args_list[2].args[0]
        for network_type in ('interface', 'device', ''):
            script = ('id() { printf "0\\n"; }; sleep() { :; }; '
                      'uci() { [ "$*" = "-q get network.lan" ] || exit 99; '
                      'printf "%s\\n" "' + network_type + '"; }; ' + command)
            result = subprocess.run([SH, '-c', script], capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(bool(re.search(ok, result.stdout)), network_type == 'interface')
            self.assertEqual(bool(re.search(fail, result.stdout)), network_type != 'interface')

    @unittest.skipUnless(SH, 'A real POSIX shell is required for multi-command failure propagation')
    def test_real_key_and_uci_stages_cannot_mask_the_first_failure(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None)
        fixtures = (
            (3, 'mkdir() { return 1; }; chmod() { printf "unexpected-later-command\\n"; }; '),
            (4, 'uci() { case "$*" in "-q get network.lan") printf "interface\\n";; '
                '"set network.lan.proto=dhcp") return 1;; *) printf "unexpected-later-command\\n";; esac; }; '),
        )
        for call_index, functions in fixtures:
            # mkdir fails before key writes; UCI is entirely stubbed. None of
            # these actual-shell tests touch host settings, keys or services.
            script = 'id() { printf "0\\n"; }; ' + functions + guest.sendline.call_args_list[call_index].args[0]
            result = subprocess.run([SH, '-c', script], capture_output=True, text=True, check=True, timeout=10)
            ok, fail = guest.expect.call_args_list[call_index].args[0]
            self.assertNotRegex(result.stdout, ok)
            self.assertRegex(result.stdout, fail)
            self.assertNotIn('unexpected-later-command', result.stdout)

    def test_both_drivers_use_shared_console_handshake_inside_guest_cleanup(self):
        for filename in ('test-openwrt-vm.py', 'test-public-command.py'):
            source = (ROOT / 'scripts' / filename).read_text(encoding='utf-8')
            self.assertIn('from vm_console import prepare_guest_console', source)
            self.assertIn('try:\n            prepare_guest_console(guest, public_key, phase)', source)
            self.assertIn('finally:\n            guest.terminate(force=True)\n            guest.close(force=True)', source)

    def test_failure_diagnostics_expose_only_stage_class_and_http_status(self):
        private = 'private-command-url-key-output-fixture'
        errors = [ValueError(private), ModuleNotFoundError(private),
                  subprocess.CalledProcessError(1, private, output=private, stderr=private),
                  urllib.error.HTTPError('https://invalid.example/' + private, 403, private, None, None)]
        with mock.patch.object(native_vm, 'PHASE', 'image_download'):
            for error in errors:
                message = native_vm.failure_message(error)
                self.assertIn('stage=image_download', message)
                self.assertIn('exception=' + type(error).__name__, message)
                self.assertNotIn(private, message)
                self.assertNotIn('https:', message)
                self.assertEqual('http_status=403' in message, isinstance(error, urllib.error.HTTPError))

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the mocked SSH contract')
    def test_failed_intermediate_command_cannot_be_masked_by_successful_tail(self):
        shell = subprocess.run
        command = "false; printf '%s\\n' 'tail-success'"
        control = shell([SH, '-c', command], capture_output=True, text=True, check=True)
        self.assertEqual(control.stdout.strip(), 'tail-success')
        transported = []
        def transport(args, **options):
            self.assertEqual(args[:2], ['ssh', 'synthetic-acceptance-host'])
            if len(transported) == 0:
                result = shell([SH, '-c', args[-1]], **options)
                transported.append(result)
                return result
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        with mock.patch.object(native_vm.subprocess, 'run', side_effect=transport), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'native acceptance was not granted'):
                native_vm.run_remote(['ssh', 'synthetic-acceptance-host'], command)
        self.assertNotEqual(transported[0].returncode, 0)
        self.assertNotIn('tail-success', transported[0].stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
