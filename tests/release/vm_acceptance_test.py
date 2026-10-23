#!/usr/bin/env python3
"""Mock the SSH transport while executing the real local POSIX shell contract."""
import contextlib
import importlib.util
import io
import pathlib
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
                   'Boot failed: No bootable device\n' + vm_console.ACTIVATION + '\n'
                   'root@OpenWrt:/# ' + private + '\n' + vm_console.READY)
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
        with contextlib.redirect_stdout(io.StringIO()) as output:
            vm_console.prepare_guest_console(guest, private, phases.append)
        self.assertEqual(phases, ['boot_activation_wait', 'boot_console_activate',
                                 'boot_root_prompt_wait', 'boot_console_provision', 'boot_console_ready_wait'])
        self.assertEqual(guest.expect.call_args_list,
                         [mock.call(vm_console.ACTIVATION), mock.call(vm_console.ROOT_PROMPT),
                          mock.call(vm_console.READY, timeout=90)])
        self.assertEqual(guest.sendline.call_args_list[0], mock.call(''))
        command = guest.sendline.call_args_list[1].args[0]
        self.assertIn("printf '%s\\n' '" + private + "' > /etc/dropbear/authorized_keys", command)
        self.assertIn('uci set network.lan.proto=dhcp', command)
        self.assertTrue(command.endswith('echo ' + vm_console.READY))
        self.assertEqual(output.getvalue(), '')

    def test_each_console_wait_failure_reports_only_fixed_signals_and_reraises(self):
        for failed_wait, stage in enumerate(('boot_activation_wait', 'boot_root_prompt_wait', 'boot_console_ready_wait')):
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
