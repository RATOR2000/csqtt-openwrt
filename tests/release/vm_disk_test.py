#!/usr/bin/env python3
"""Disposable regular-file disk contracts; native e2fsprogs proof runs on Linux."""
import os
import pathlib
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import vm_disk

MOCK_ROOT_BYTES = 2 * 1024 * 1024
ORIGINAL_ROOT_BYTES = 64 * 1024
ROOT_OFFSET = 8 * 1024


def fixture(path, root_bytes=ORIGINAL_ROOT_BYTES, checksum=False):
    """Synthetic ext4 geometry for mocked commands, never native filesystem proof."""
    prefix = bytearray((bytes(range(256)) * (ROOT_OFFSET // 256)))
    prefix[446:510] = bytes(64)
    prefix[510:512] = b'\x55\xaa'
    for number, start, sectors in ((0, 4, 8), (1, ROOT_OFFSET // 512, root_bytes // 512)):
        offset = 446 + number * 16
        prefix[offset] = 0x80 if number == 0 else 0
        prefix[offset + 4] = 0x83
        struct.pack_into('<II', prefix, offset + 8, start, sectors)
    sb = bytearray(1024)
    for offset, value in ((0, 16), (4, root_bytes // 1024), (0x10, 8), (0x14, 1),
                          (0x20, 8192), (0x28, 16), (0x60, 0x40)):
        struct.pack_into('<I', sb, offset, value)
    struct.pack_into('<H', sb, 0x58, 128)
    sb[0x38:0x3a] = b'\x53\xef'
    sb[0x68:0x78] = bytes(range(16))
    if checksum:
        struct.pack_into('<I', sb, 0x64, 0x400)
        sb[0x175] = 1
        struct.pack_into('<I', sb, 0x3fc, vm_disk._crc32c(sb[:0x3fc]))
    with path.open('wb') as disk:
        disk.write(prefix)
        disk.truncate(ROOT_OFFSET + root_bytes)
        disk.seek(ROOT_OFFSET + 1024)
        disk.write(sb)
        disk.seek(ROOT_OFFSET + 4096)
        disk.write(b'root-data-preserved-fixture')


class VmDiskTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='csqtt-vm-disk-test-')
        self.addCleanup(temporary.cleanup)
        self.boundary = pathlib.Path(temporary.name).resolve()
        self.image = self.boundary / 'firmware.img'
        fixture(self.image)
        self.calls = []
        self.target_patch = mock.patch.object(vm_disk, 'TEST_ROOT_BYTES', MOCK_ROOT_BYTES)
        self.target_patch.start()
        self.addCleanup(self.target_patch.stop)
        self.which_patch = mock.patch.object(vm_disk.shutil, 'which', side_effect=lambda name: name)
        self.which_patch.start()
        self.addCleanup(self.which_patch.stop)
        self.run_patch = mock.patch.object(vm_disk.subprocess, 'run', side_effect=self.native_command)
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)

    def native_command(self, args, **options):
        self.calls.append((args, options))
        self.assertIn(args[0], ('e2fsck', 'resize2fs'))
        partition = pathlib.Path(args[2] if args[0] == 'e2fsck' else args[1])
        self.assertEqual(partition.name, 'root.ext4')
        self.assertEqual(partition.parent.parent, self.boundary)
        self.assertNotEqual(partition, self.image)
        self.assertTrue(partition.is_file())
        self.assertEqual(options['timeout'], 180)
        self.assertTrue(options['capture_output'])
        if args[0] == 'e2fsck':
            self.assertEqual(args[1], '-pf')
        else:
            self.assertTrue(options['check'])
            self.assertEqual(args[2], str(MOCK_ROOT_BYTES // 1024))
            with partition.open('r+b') as target:
                target.seek(1024 + 4)
                target.write(struct.pack('<I', MOCK_ROOT_BYTES // 1024))
        return subprocess.CompletedProcess(args, 0)

    def expand(self):
        return vm_disk.expand_disposable_root(self.image, self.boundary)

    def assert_atomic_refusal(self, action, exception=ValueError):
        before = self.image.read_bytes()
        with self.assertRaises(exception):
            action()
        self.assertEqual(self.image.read_bytes(), before, 'Refusal changed the original disk')
        self.assertFalse(list(self.boundary.glob('.csqtt-root-*')), 'Private work was not cleaned up')

    def test_mocked_expansion_preserves_boot_mbr_partition_one_and_root_data(self):
        before = self.image.read_bytes()
        evidence = self.expand()
        after = self.image.read_bytes()
        self.assertEqual(evidence, {'original_root_bytes': ORIGINAL_ROOT_BYTES,
                                   'test_root_bytes': MOCK_ROOT_BYTES,
                                   'disk_expanded': True, 'physical_device': False})
        amended = bytearray(before[:ROOT_OFFSET])
        struct.pack_into('<I', amended, vm_disk.ROOT_LENGTH_OFFSET, MOCK_ROOT_BYTES // 512)
        self.assertEqual(after[:ROOT_OFFSET], amended)
        self.assertEqual(after[ROOT_OFFSET + 4096:ROOT_OFFSET + 4123],
                         before[ROOT_OFFSET + 4096:ROOT_OFFSET + 4123])
        self.assertEqual(len(after), ROOT_OFFSET + MOCK_ROOT_BYTES)
        self.assertEqual([call[0][0] for call in self.calls], ['e2fsck', 'resize2fs', 'e2fsck'])
        self.assertFalse(list(self.boundary.glob('.csqtt-root-*')))

    def test_already_target_size_is_reported_without_claiming_expansion(self):
        fixture(self.image, root_bytes=MOCK_ROOT_BYTES)
        self.assertFalse(self.expand()['disk_expanded'])

    def test_gpt_overlap_extra_partition_truncation_and_unaligned_disk_refuse(self):
        mutations = ((512, b'EFI PART'), (446 + 16 + 8, struct.pack('<I', 6)),
                     (446 + 32 + 4, b'\x83'), (446 + 16 + 12, struct.pack('<I', 99999)),
                     (510, b'\0\0'))
        for offset, data in mutations:
            with self.subTest(offset=offset):
                fixture(self.image)
                with self.image.open('r+b') as disk:
                    disk.seek(offset)
                    disk.write(data)
                self.assert_atomic_refusal(self.expand)
        fixture(self.image)
        with self.image.open('ab') as disk:
            disk.write(b'X')
        self.assert_atomic_refusal(self.expand)
        self.assertEqual(self.calls, [])

    def test_shrinking_and_unexpected_data_after_root_refuse(self):
        fixture(self.image, root_bytes=MOCK_ROOT_BYTES + 512)
        self.assert_atomic_refusal(self.expand)
        fixture(self.image)
        with self.image.open('ab') as disk:
            disk.write(bytes(512))
        self.assert_atomic_refusal(self.expand)

    def test_bad_ext4_magic_geometry_external_journal_and_checksum_refuse(self):
        mutations = ((0x38, b'\0\0'), (4, struct.pack('<I', 99999)),
                     (0x18, struct.pack('<I', 3)), (0x60, struct.pack('<I', 0x48)),
                     (0x64, struct.pack('<I', 0x200)), (0xd0, b'X'),
                     (0xe4, struct.pack('<I', 1)), (0x58, struct.pack('<H', 129)))
        for offset, data in mutations:
            with self.subTest(offset=offset):
                fixture(self.image)
                with self.image.open('r+b') as disk:
                    disk.seek(ROOT_OFFSET + 1024 + offset)
                    disk.write(data)
                self.assert_atomic_refusal(self.expand)
        fixture(self.image, checksum=True)
        with self.image.open('r+b') as disk:
            disk.seek(ROOT_OFFSET + 1024 + 0x3fc)
            disk.write(bytes(4))
        self.assert_atomic_refusal(self.expand)
        self.assertEqual(self.calls, [])

    def test_missing_native_tools_refuses_before_work(self):
        with mock.patch.object(vm_disk.shutil, 'which', return_value=None):
            self.assert_atomic_refusal(self.expand)
        self.assertEqual(self.calls, [])

    def test_block_device_mode_refuses_without_running_native_commands(self):
        actual_stat = pathlib.Path.stat
        def device_stat(path, *args, **options):
            if path == self.image:
                return SimpleNamespace(st_mode=stat.S_IFBLK, st_nlink=1)
            return actual_stat(path, *args, **options)
        with mock.patch.object(pathlib.Path, 'stat', autospec=True, side_effect=device_stat):
            self.assert_atomic_refusal(self.expand)
        self.assertEqual(self.calls, [])

    def test_native_fsck_failure_before_and_after_resize_is_atomic(self):
        for failing_check in (1, 2):
            for returncode in (2, 4, 8, 16, 32, 128, -9):
                fixture(self.image)
                count = 0
                def command(args, **options):
                    nonlocal count
                    if args[0] == 'e2fsck':
                        count += 1
                        if count == failing_check:
                            return subprocess.CompletedProcess(args, returncode)
                    return self.native_command(args, **options)
                with self.subTest(check=failing_check, code=returncode), \
                        mock.patch.object(vm_disk.subprocess, 'run', side_effect=command):
                    self.assert_atomic_refusal(self.expand)

    def test_fsck_corrected_exit_one_is_accepted(self):
        def corrected(args, **options):
            result = self.native_command(args, **options)
            result.returncode = 1 if args[0] == 'e2fsck' else 0
            return result
        with mock.patch.object(vm_disk.subprocess, 'run', side_effect=corrected):
            self.assertTrue(self.expand()['disk_expanded'])

    def test_resize_failure_timeout_or_wrong_geometry_cannot_replace_original(self):
        for failure in ('command', 'timeout', 'geometry', 'identity'):
            fixture(self.image)
            def command(args, **options):
                if args[0] == 'resize2fs':
                    if failure == 'command':
                        raise subprocess.CalledProcessError(1, args)
                    if failure == 'timeout':
                        raise subprocess.TimeoutExpired(args, 180)
                    if failure == 'geometry':
                        return subprocess.CompletedProcess(args, 0)
                    result = self.native_command(args, **options)
                    with pathlib.Path(args[1]).open('r+b') as partition:
                        partition.seek(1024 + 0x68)
                        partition.write(b'X' * 16)
                    return result
                return self.native_command(args, **options)
            exception = {'command': subprocess.CalledProcessError, 'timeout': subprocess.TimeoutExpired}.get(failure, ValueError)
            with self.subTest(failure=failure), mock.patch.object(vm_disk.subprocess, 'run', side_effect=command):
                self.assert_atomic_refusal(self.expand, exception)

    def test_failed_atomic_replacement_preserves_original(self):
        with mock.patch.object(vm_disk.os, 'replace', side_effect=OSError('replacement refused')):
            self.assert_atomic_refusal(self.expand, OSError)

    def test_boundary_escape_root_boundary_wrong_suffix_and_directory_refuse(self):
        outside = self.boundary.parent / (self.boundary.name + '-outside.img')
        shutil.copyfile(self.image, outside)
        self.addCleanup(outside.unlink, missing_ok=True)
        before = outside.read_bytes()
        with self.assertRaises(ValueError):
            vm_disk.expand_disposable_root(outside, self.boundary)
        self.assertEqual(outside.read_bytes(), before)
        self.assert_atomic_refusal(lambda: vm_disk.expand_disposable_root(self.image, tempfile.gettempdir()))
        wrong = self.boundary / 'disk.bin'
        shutil.copyfile(self.image, wrong)
        with self.assertRaises(ValueError):
            vm_disk.expand_disposable_root(wrong, self.boundary)
        directory = self.boundary / 'directory.img'
        directory.mkdir()
        with self.assertRaises(ValueError):
            vm_disk.expand_disposable_root(directory, self.boundary)
        self.assertEqual(self.calls, [])

    def test_hardlinks_refuse(self):
        hardlink = self.boundary / 'shared.img'
        try:
            os.link(self.image, hardlink)
        except OSError:
            self.skipTest('Hardlink creation unavailable on this host')
        self.assert_atomic_refusal(self.expand)
        hardlink.unlink()

    def test_linked_ancestor_and_windows_reparse_point_refuse_before_resolving(self):
        actual_lstat = pathlib.Path.lstat
        for kind in ('symlink', 'reparse'):
            def linked_stat(path):
                info = actual_lstat(path)
                if path == self.boundary:
                    return SimpleNamespace(st_mode=stat.S_IFLNK if kind == 'symlink' else info.st_mode,
                                           st_file_attributes=1024 if kind == 'reparse' else 0)
                return info
            with self.subTest(kind=kind), \
                    mock.patch.object(vm_disk.stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024, create=True), \
                    mock.patch.object(pathlib.Path, 'lstat', autospec=True, side_effect=linked_stat):
                self.assert_atomic_refusal(self.expand)
        self.assertEqual(self.calls, [])

    def test_actual_direct_and_ancestor_symlinks_refuse(self):
        linked = self.boundary / 'linked.img'
        linked_boundary = self.boundary / 'linked-directory'
        try:
            linked.symlink_to(self.image)
            linked_boundary.symlink_to(self.boundary, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation needs host privileges; native Linux CI exercises refusal')
        for image, boundary in ((linked, self.boundary), (self.image, linked_boundary),
                                (linked_boundary / self.image.name, self.boundary)):
            self.assert_atomic_refusal(lambda: vm_disk.expand_disposable_root(image, boundary))
        self.assertEqual(self.calls, [])


class NativeVmDiskTest(unittest.TestCase):
    def test_production_target_is_fixed_one_gib(self):
        self.assertEqual(vm_disk.TEST_ROOT_BYTES, 1024 ** 3)

    @unittest.skipUnless(os.name == 'posix' and all(shutil.which(tool) for tool in
                          ('mke2fs', 'e2fsck', 'resize2fs', 'debugfs')),
                         'Actual regular-file ext4 expansion requires Linux/native e2fsprogs')
    def test_actual_unmounted_ext4_expansion_preserves_boot_and_root_identity(self):
        with tempfile.TemporaryDirectory(prefix='csqtt-native-vm-disk-') as temporary:
            boundary = pathlib.Path(temporary)
            partition, image = boundary / 'source.ext4', boundary / 'native.img'
            payload = boundary / 'payload'
            payload.mkdir()
            content = b'Public native ext4 data preservation fixture.\n'
            (payload / 'keep.txt').write_bytes(content)
            root_bytes = 16 * 1024 * 1024
            with partition.open('wb') as target:
                target.truncate(root_bytes)
            subprocess.run([shutil.which('mke2fs'), '-q', '-t', 'ext4', '-F', '-b', '4096',
                            '-d', str(payload), str(partition)],
                           check=True, capture_output=True, timeout=60)
            fixture(image, root_bytes=root_bytes)
            prefix = image.read_bytes()[:ROOT_OFFSET]
            with partition.open('rb') as source, image.open('r+b') as target:
                original = vm_disk._superblock(source, 0, root_bytes)
                target.seek(ROOT_OFFSET)
                shutil.copyfileobj(source, target)
            evidence = vm_disk.expand_disposable_root(image, boundary)
            self.assertEqual(evidence, {'original_root_bytes': root_bytes, 'test_root_bytes': 1024 ** 3,
                                       'disk_expanded': True, 'physical_device': False})
            expected = bytearray(prefix)
            struct.pack_into('<I', expected, vm_disk.ROOT_LENGTH_OFFSET, 1024 ** 3 // 512)
            with image.open('rb') as source:
                self.assertEqual(source.read(ROOT_OFFSET), expected)
                grown = vm_disk._superblock(source, ROOT_OFFSET, 1024 ** 3)
            self.assertEqual(grown['filesystem_bytes'], 1024 ** 3)
            self.assertEqual(grown['uuid'], original['uuid'])
            self.assertEqual(image.stat().st_size, ROOT_OFFSET + 1024 ** 3)
            verified = boundary / 'verified.ext4'
            with image.open('rb') as source, verified.open('wb') as target:
                source.seek(ROOT_OFFSET)
                vm_disk._copy_exact(source, target, 1024 ** 3)
            readback = subprocess.run([shutil.which('debugfs'), '-R', 'cat /keep.txt', str(verified)],
                                      check=True, capture_output=True, timeout=60)
            self.assertEqual(readback.stdout, content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
