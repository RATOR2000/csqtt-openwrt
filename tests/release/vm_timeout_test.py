#!/usr/bin/env python3
"""Test disposable guest command bounds independently of native installation."""
import hashlib
import os
import pathlib
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import vm_timeout


class ProvisionTest(unittest.TestCase):
    def test_raw_ssh_transfer_has_checked_hash_private_mode_and_fixed_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = pathlib.Path(temporary) / 'timeout'
            data = b'\x00synthetic-static-tool\xff\n'
            binary.write_bytes(data)
            with mock.patch.object(vm_timeout.subprocess, 'run') as run:
                vm_timeout.provision_timeout(['ssh', 'synthetic-host'], binary, '/tmp/csqtt-native')
            args, options = run.call_args
            self.assertEqual(args[0][:2], ['ssh', 'synthetic-host'])
            self.assertIn(hashlib.sha256(data).hexdigest(), args[0][-1])
            self.assertIn('umask 077', args[0][-1])
            self.assertIn('chmod 700', args[0][-1])
            self.assertIn('test ! -e', args[0][-1])
            self.assertEqual(options['input'], data)
            self.assertTrue(options['check'])
            self.assertEqual(options['timeout'], 30)
            with mock.patch.object(vm_timeout.subprocess, 'run') as run:
                for directory in ('/usr/bin', '/tmp/csqtt-native/../other', '/tmp/csqtt-native; false'):
                    with self.assertRaises(ValueError):
                        vm_timeout.provision_timeout(['ssh'], binary, directory)
                run.assert_not_called()

    def test_compiler_failure_and_dynamic_or_foreign_binary_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            def compiled(*args, **kwargs):
                (directory / 'vm-timeout').write_bytes(self.binary)
            self.binary = b'not-elf'
            with mock.patch.object(vm_timeout.sys, 'platform', 'linux'), \
                 mock.patch.object(vm_timeout.platform, 'machine', return_value='x86_64'), \
                 mock.patch.object(vm_timeout.shutil, 'which', return_value='/usr/bin/cc'), \
                 mock.patch.object(vm_timeout.subprocess, 'run', side_effect=compiled) as run:
                with self.assertRaises(ValueError):
                    vm_timeout.build_timeout(directory)
                data = bytearray(120)
                data[:7] = b'\x7fELF\x02\x01\x01'
                struct.pack_into('<H', data, 18, 62)
                struct.pack_into('<Q', data, 32, 64)
                struct.pack_into('<HH', data, 54, 56, 1)
                for header in (2, 3):
                    struct.pack_into('<I', data, 64, header)
                    self.binary = data
                    with self.assertRaises(ValueError):
                        vm_timeout.build_timeout(directory)
                run.side_effect = subprocess.CalledProcessError(1, ['cc'])
                with self.assertRaises(subprocess.CalledProcessError):
                    vm_timeout.build_timeout(directory)


@unittest.skipUnless(sys.platform == 'linux', 'Native static Linux execution runs in CI')
class NativeTimeoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='csqtt-deadline-test-')
        cls.root = pathlib.Path(cls.temporary.name)
        cls.binary = vm_timeout.build_timeout(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_tool(self, seconds, *command, **kwargs):
        return subprocess.run([str(self.binary), str(seconds), *command], capture_output=True,
                              text=True, timeout=5, **kwargs)

    def alive(self, pid):
        try:
            return pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1][0] != 'Z'
        except FileNotFoundError:
            return False

    def wait_dead(self, pids):
        deadline = time.monotonic() + 1
        while any(self.alive(pid) for pid in pids) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(any(self.alive(pid) for pid in pids), 'Timed command or descendant survived')

    def test_exit_status_stdin_arguments_and_streams_are_preserved(self):
        code = 'import sys; print(sys.argv[1]); print(sys.stdin.read()); print("err", file=sys.stderr); sys.exit(7)'
        result = self.run_tool(2, sys.executable, '-c', code, 'space ; $ argument', input='fixture input')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, 'space ; $ argument\nfixture input\n')
        self.assertEqual(result.stderr, 'err\n')
        self.assertEqual(self.run_tool(1, '/nonexistent-command').returncode, 127)

    def test_invalid_duration_refuses_to_execute(self):
        marker = self.root / 'must-not-run'
        for value in ('', '0', '-1', '1.0', '1s', '3601', '999999999999999999999999', '1;false'):
            self.assertEqual(self.run_tool(value, 'touch', str(marker)).returncode, 125)
        self.assertFalse(marker.exists())

    def test_timeout_sends_term_then_kills_the_entire_group_within_the_bound(self):
        pids, term = self.root / 'pids', self.root / 'term'
        code = ('import os, signal, subprocess, sys, time; '
                'signal.signal(signal.SIGTERM, lambda *args: open(sys.argv[2], "w").write("term")); '
                'child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"]); '
                'open(sys.argv[1], "w").write(str(os.getpid()) + " " + str(child.pid)); time.sleep(30)')
        before = time.monotonic()
        result = self.run_tool(1, sys.executable, '-c', code, str(pids), str(term))
        elapsed = time.monotonic() - before
        self.assertEqual(result.returncode, 124)
        self.assertGreater(elapsed, .8)
        self.assertLess(elapsed, 1.6)
        self.assertEqual(term.read_text(), 'term')
        self.wait_dead([int(pid) for pid in pids.read_text().split()])

    def test_interruption_forwards_signal_then_kills_ignoring_descendants(self):
        pids = self.root / 'interrupted-pids'
        code = ('import os, signal, subprocess, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                'child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"]); '
                'open(sys.argv[1], "w").write(str(os.getpid()) + " " + str(child.pid)); time.sleep(30)')
        process = subprocess.Popen([str(self.binary), '4', sys.executable, '-c', code, str(pids)])
        try:
            deadline = time.monotonic() + 2
            while not pids.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(pids.exists())
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=2), 128 + signal.SIGTERM)
            self.wait_dead([int(pid) for pid in pids.read_text().split()])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_successful_command_keeps_intentionally_started_service(self):
        code = ('import subprocess; child = subprocess.Popen(["sleep", "30"], '
                'stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print(child.pid)')
        result = self.run_tool(2, sys.executable, '-c', code)
        self.assertEqual(result.returncode, 0)
        pid = int(result.stdout)
        try:
            self.assertTrue(self.alive(pid))
        finally:
            os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
