#!/usr/bin/env python3
"""Expand only an offline, disposable OpenWrt MBR/ext4 VM root to 1 GiB.

This is test-image preparation, not evidence that the stock firmware disk has
enough space. No block devices, mounted filesystems, loop devices or root
privileges are used. Native e2fsprogs remain mandatory filesystem validators.
"""
import hashlib
import os
import pathlib
import shutil
import stat
import struct
import subprocess
import tempfile

SECTOR_BYTES = 512
TEST_ROOT_BYTES = 1024 * 1024 * 1024
MAX_BOOT_BYTES = 128 * 1024 * 1024
ROOT_LENGTH_OFFSET = 446 + 16 + 12
CHUNK_BYTES = 1024 * 1024


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def _crc32c(data):
    # ext4 superblock checksums use CRC32C(~0, sb[0:0x3fc]), no final XOR.
    crc = 0xffffffff
    for byte in data:
        crc ^= byte
        for unused in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc


def _superblock(stream, offset, partition_bytes):
    stream.seek(offset + 1024)
    data = stream.read(1024)
    _require(len(data) == 1024 and data[0x38:0x3a] == b'\x53\xef', 'Expected an ext4 root superblock')
    shift = _u32(data, 0x18)
    _require(shift <= 2, 'Unsupported ext4 block size')
    block_bytes = 1024 << shift
    incompat, ro_compat = _u32(data, 0x60), _u32(data, 0x64)
    _require(incompat & 0x40 and not incompat & 0x8 and not ro_compat & 0x200,
             'Expected ordinary ext4 without an external journal or bigalloc')
    _require(not any(data[0xd0:0xe0]) and _u32(data, 0xe4) == 0, 'External ext4 journals are forbidden')
    high = _u32(data, 0x150)
    _require(incompat & 0x80 or high == 0, 'Invalid ext4 high block count')
    blocks = _u32(data, 4) | (high << 32 if incompat & 0x80 else 0)
    filesystem_bytes = blocks * block_bytes
    inodes, free_inodes = _u32(data, 0), _u32(data, 0x10)
    inode_bytes = struct.unpack_from('<H', data, 0x58)[0]
    _require(0 < inodes and free_inodes <= inodes and 128 <= inode_bytes <= block_bytes and
             inode_bytes & (inode_bytes - 1) == 0, 'Invalid ext4 inode geometry')
    _require(0 < _u32(data, 0x20) <= block_bytes * 8 and _u32(data, 0x28) > 0 and
             _u32(data, 0x14) == (1 if block_bytes == 1024 else 0), 'Invalid ext4 block geometry')
    _require(2048 <= filesystem_bytes <= partition_bytes, 'Ext4 filesystem exceeds the root partition')
    if ro_compat & 0x400:
        _require(data[0x175] == 1 and _u32(data, 0x3fc) == _crc32c(data[:0x3fc]),
                 'Invalid ext4 superblock checksum')
    return {'block_bytes': block_bytes, 'filesystem_bytes': filesystem_bytes, 'uuid': data[0x68:0x78]}


def _layout(stream, disk_bytes):
    _require(disk_bytes % SECTOR_BYTES == 0 and 2048 <= disk_bytes <= TEST_ROOT_BYTES + MAX_BOOT_BYTES,
             'Invalid or unaligned disposable raw disk size')
    stream.seek(0)
    mbr = stream.read(SECTOR_BYTES)
    _require(mbr[510:512] == b'\x55\xaa', 'Expected DOS MBR magic')
    _require(stream.read(8) != b'EFI PART', 'GPT disks are not supported')
    entries = [mbr[446 + number * 16:462 + number * 16] for number in range(4)]
    _require(entries[2] == bytes(16) and entries[3] == bytes(16), 'Unexpected additional disk partitions')
    partitions = []
    for entry in entries[:2]:
        _require(entry[0] in (0, 0x80) and entry[4] == 0x83, 'Expected two ordinary Linux MBR partitions')
        start, sectors = _u32(entry, 8), _u32(entry, 12)
        _require(start > 0 and sectors > 0 and (start + sectors) * SECTOR_BYTES <= disk_bytes,
                 'Partition is empty, truncated or outside the raw disk')
        partitions.append((start * SECTOR_BYTES, sectors * SECTOR_BYTES))
    boot, root = partitions
    _require(sum(entry[0] == 0x80 for entry in entries[:2]) <= 1, 'Ambiguous MBR boot flags')
    _require(boot[0] + boot[1] <= root[0] <= MAX_BOOT_BYTES and root[0] + root[1] == disk_bytes,
             'Overlapping partitions or unexpected data after the root partition')
    _require(root[1] <= TEST_ROOT_BYTES, 'Shrinking an existing root partition is forbidden')
    return mbr, boot, root


def _copy_exact(source, target, count):
    zeroes = bytes(CHUNK_BYTES)
    while count:
        data = source.read(min(count, CHUNK_BYTES))
        _require(bool(data), 'Disposable image was truncated during copying')
        # Preserve sparse zero regions in the new private image, including the
        # zero extension made before resize2fs. Never used on an existing file.
        if data == zeroes[:len(data)]:
            target.seek(len(data), os.SEEK_CUR)
        else:
            target.write(data)
        count -= len(data)
    target.truncate(target.tell())


def _region_hash(stream, offset, count):
    result = hashlib.sha256()
    stream.seek(offset)
    while count:
        data = stream.read(min(count, CHUNK_BYTES))
        _require(bool(data), 'Disposable image was truncated during verification')
        result.update(data)
        count -= len(data)
    return result.digest()


def _check_filesystem(tool, image):
    result = subprocess.run([tool, '-pf', str(image)], capture_output=True, timeout=180)
    # e2fsck uses bit flags: 1 means corrected; reboot-required (2), uncorrected
    # errors (4), operational failure and all other combinations are refusals.
    _require(result.returncode in (0, 1), 'Native offline filesystem check failed')


def _require_plain_path(path):
    # Resolving first would hide a linked ancestor. Windows junctions/reparse
    # points are also forbidden, so the disposable boundary cannot redirect IO.
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        info = component.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and
                 not getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0),
                 'Symlink or reparse-point VM paths are forbidden')


def expand_disposable_root(image, boundary):
    """Atomically replace one regular raw image inside a dedicated test folder.

    ``boundary`` must be a proper subdirectory of this repository or the host
    temporary directory. The caller owns that disposable folder; filesystem
    commands receive only a newly extracted private partition, never ``image``.
    """
    given_image, given_boundary = pathlib.Path(image), pathlib.Path(boundary)
    _require_plain_path(given_image)
    _require_plain_path(given_boundary)
    image, boundary = given_image.resolve(strict=True), given_boundary.resolve(strict=True)
    safe_bases = (pathlib.Path(tempfile.gettempdir()).resolve(), pathlib.Path(__file__).resolve().parents[1])
    _require(boundary.is_dir() and any(boundary != base and boundary.is_relative_to(base) for base in safe_bases),
             'A dedicated workspace or temporary test boundary is required')
    _require(image.is_relative_to(boundary) and image.suffix in ('.img', '.raw'), 'Image is outside its disposable test boundary')
    before = image.stat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'Only an unshared regular raw image is supported')
    e2fsck, resize2fs = shutil.which('e2fsck'), shutil.which('resize2fs')
    _require(e2fsck and resize2fs, 'Native e2fsprogs e2fsck and resize2fs are required')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(image, flags), 'rb') as source:
        opened = os.fstat(source.fileno())
        _require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                 (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns), 'Disposable image changed before opening')
        mbr, boot, root = _layout(source, before.st_size)
        original = _superblock(source, root[0], root[1])
        boot_hash = _region_hash(source, boot[0], boot[1])
        prefix_hash = _region_hash(source, SECTOR_BYTES, root[0] - SECTOR_BYTES)
        with tempfile.TemporaryDirectory(prefix='.csqtt-root-', dir=boundary) as temporary:
            private = pathlib.Path(temporary)
            filesystem, replacement = private / 'root.ext4', private / 'expanded.img'
            with filesystem.open('xb') as target:
                source.seek(root[0])
                _copy_exact(source, target, root[1])
            _check_filesystem(e2fsck, filesystem)
            with filesystem.open('r+b') as target:
                checked = _superblock(target, 0, root[1])
                _require(checked['block_bytes'] == original['block_bytes'] and checked['uuid'] == original['uuid'],
                         'Filesystem check changed the root identity')
                target.truncate(TEST_ROOT_BYTES)
            subprocess.run([resize2fs, str(filesystem), str(TEST_ROOT_BYTES // original['block_bytes'])],
                           check=True, capture_output=True, timeout=180)
            _check_filesystem(e2fsck, filesystem)
            with filesystem.open('rb') as target:
                grown = _superblock(target, 0, TEST_ROOT_BYTES)
                _require(grown['filesystem_bytes'] == TEST_ROOT_BYTES and grown['block_bytes'] == original['block_bytes'] and
                         grown['uuid'] == original['uuid'] and filesystem.stat().st_size == TEST_ROOT_BYTES,
                         'Resized ext4 root does not match the fixed test geometry')
            amended = bytearray(mbr)
            struct.pack_into('<I', amended, ROOT_LENGTH_OFFSET, TEST_ROOT_BYTES // SECTOR_BYTES)
            with replacement.open('xb') as target, filesystem.open('rb') as partition:
                target.write(amended)
                source.seek(SECTOR_BYTES)
                _copy_exact(source, target, root[0] - SECTOR_BYTES)
                _copy_exact(partition, target, TEST_ROOT_BYTES)
                target.flush()
                os.fsync(target.fileno())
            with replacement.open('rb') as target:
                _require(target.read(SECTOR_BYTES) == amended and
                         _region_hash(target, SECTOR_BYTES, root[0] - SECTOR_BYTES) == prefix_hash and
                         _region_hash(target, boot[0], boot[1]) == boot_hash,
                         'Expanded image changed its boot region or first partition')
                _layout(target, replacement.stat().st_size)
                _superblock(target, root[0], TEST_ROOT_BYTES)
            current = image.stat()
            _require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) ==
                     (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns), 'Disposable image changed during resizing')
            shutil.copymode(image, replacement)
            # Close the original before replacement, also supporting Windows.
            source.close()
            os.replace(replacement, image)
    return {'original_root_bytes': root[1], 'test_root_bytes': TEST_ROOT_BYTES,
            'disk_expanded': root[1] < TEST_ROOT_BYTES, 'physical_device': False}
