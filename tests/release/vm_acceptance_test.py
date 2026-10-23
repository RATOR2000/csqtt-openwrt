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
                   vm_console.ROOT_MARKER + NONCE + '\r\r\n' + private + '\n' + vm_console.READY + NONCE + '\r\r\n')
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
        private = 'ssh-ed25519 public-key-fixture'
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            vm_console.prepare_guest_console(guest, private, phases.append)
        self.assertEqual(phases, ['boot_activation_wait', 'boot_console_activate',
                                 'boot_root_check', 'boot_root_check_wait', 'boot_console_provision', 'boot_console_ready_wait'])
        root_pattern = r'(?m)^' + vm_console.ROOT_MARKER + NONCE + r'\r*$'
        ready_pattern = r'(?m)^' + vm_console.READY + NONCE + r'\r*$'
        self.assertEqual(guest.expect.call_args_list,
                         [mock.call(vm_console.ACTIVATION), mock.call(root_pattern),
                          mock.call(ready_pattern, timeout=90)])
        self.assertEqual(guest.sendline.call_args_list[0], mock.call(''))
        root_command = guest.sendline.call_args_list[1].args[0]
        self.assertTrue(root_command.startswith('test "$(id -u)" = 0 && printf'))
        self.assertNotIn(vm_console.ROOT_MARKER + NONCE, root_command)
        command = guest.sendline.call_args_list[2].args[0]
        self.assertTrue(command.startswith('set -eu;'))
        self.assertIn("printf '%s\\n' '" + private + "' > /etc/dropbear/authorized_keys", command)
        self.assertIn('uci set network.lan.proto=dhcp', command)
        self.assertTrue(command.endswith("printf '%s%s\\n' '" + vm_console.READY + "' '" + NONCE + "'"))
        self.assertNotIn(vm_console.READY + NONCE, command)
        self.assertEqual(output.getvalue(), '')

    def test_each_console_wait_failure_reports_only_fixed_signals_and_reraises(self):
        for failed_wait, stage in enumerate(('boot_activation_wait', 'boot_root_check_wait', 'boot_console_ready_wait')):
            guest, phases = mock.Mock(), []
            private = 'private-console-command-key-https-fixture'
            guest.before = 'Linux version 6.6 ' + private
            error = TimeoutError(private)
            guest.expect.side_effect = [None] * failed_wait + [error]
            with self.subTest(stage=stage), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(TimeoutError) as raised:
                    vm_console.prepare_guest_console(guest, private, phases.append)
            self.assertIs(raised.exception, error)
            self.assertEqual(phases[-1], stage)
            self.assertEqual(output.getvalue(), 'OpenWrt VM boot signals: linux\n')
            self.assertNotIn(private, output.getvalue())
            self.assertEqual(guest.sendline.call_count, (0, 2, 3)[failed_wait])

    def test_only_fresh_marker_output_matches_regardless_of_hostname_and_ansi_prompt(self):
        guest, phases, public_key = mock.Mock(), [], 'ssh-ed25519 key-fixture'
        waits = 0
        def expect(pattern, **options):
            nonlocal waits
            waits += 1
            if waits == 1:
                return 0
            command = guest.sendline.call_args.args[0]
            prefix = vm_console.ROOT_MARKER if waits == 2 else vm_console.READY
            echoed = '\x1b[32mroot@different-host:/#\x1b[0m ' + command + '\r\n'
            self.assertIsNone(re.search(pattern, echoed), 'Echoed command masqueraded as execution')
            for wrong in (prefix + 'b' * 32 + '\r\n', 'prefix-' + prefix + NONCE + '\r\n',
                          prefix + NONCE + '-suffix\r\n'):
                self.assertIsNone(re.search(pattern, wrong))
            for ending in ('\n', '\r\n', '\r\r\n'):
                self.assertIsNotNone(re.search(pattern, echoed + prefix + NONCE + ending))
            return 0
        guest.expect.side_effect = expect
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, public_key, phases.append)
        self.assertEqual(phases[-1], 'boot_console_ready_wait')

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
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None)
        root_command = guest.sendline.call_args_list[1].args[0]
        root_pattern = guest.expect.call_args_list[1].args[0]
        for uid in (0, 65534):
            command = 'id() { printf "%s\\n" ' + str(uid) + '; }; ' + root_command
            result = subprocess.run([SH, '-c', command], capture_output=True, text=True)
            self.assertEqual(bool(re.search(root_pattern, result.stdout)), uid == 0)
            self.assertEqual(result.returncode, 0 if uid == 0 else 1)
        # Execute only its leading errexit setup and trailing marker, replacing
        # disposable guest provisioning with a failure. No host network writes.
        provision = guest.sendline.call_args_list[2].args[0]
        marker_command = provision.rsplit('; ', 1)[1]
        result = subprocess.run([SH, '-c', 'set -eu; false; ' + marker_command], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotRegex(result.stdout, guest.expect.call_args_list[2].args[0])

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
