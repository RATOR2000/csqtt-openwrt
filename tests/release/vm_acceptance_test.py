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
SH = shutil.which('sh')
if not SH:
    git = pathlib.Path(shutil.which('git') or '')
    candidate = git.parent.parent / 'usr/bin/sh.exe'
    SH = str(candidate) if candidate.is_file() else None


class VmAcceptanceTest(unittest.TestCase):
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
