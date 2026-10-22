#!/usr/bin/env python3
"""Bounded ELF ABI checks for static OpenWrt payloads before execution."""
import pathlib
import struct


def validate_elf(path, profile, require_static=True):
    path = pathlib.Path(path)
    with path.open('rb') as stream:
        header = stream.read(64)
        expected = profile['elf']
        endian = '<' if expected['endian'] == 'little' else '>'
        if (len(header) != 64 or header[:4] != b'\x7fELF'
                or header[4] != (2 if expected['class'] == 64 else 1)
                or header[5] != (1 if expected['endian'] == 'little' else 2)
                or header[6] != 1
                or struct.unpack_from(endian + 'H', header, 18)[0] != expected['machine']):
            raise ValueError('ELF class, byte order or machine differs from selected platform')
        # The initial allowlist contains only ELF64. Reject extensions until their
        # headers, float ABI and instruction baseline receive explicit tests.
        if expected['class'] != 64:
            raise ValueError('ELF32 requires a separately validated ABI profile')
        kind = struct.unpack_from(endian + 'H', header, 16)[0]
        offset = struct.unpack_from(endian + 'Q', header, 32)[0]
        entry_size, count = struct.unpack_from(endian + 'HH', header, 54)
        if kind not in (2, 3) or entry_size != 56 or not 1 <= count <= 128:
            raise ValueError('invalid ELF program header table')
        size = path.stat().st_size
        if offset < 64 or offset + entry_size * count > size:
            raise ValueError('ELF program header table exceeds file')
        stream.seek(offset)
        entries = stream.read(entry_size * count)
        loaded = False
        for position in range(0, len(entries), entry_size):
            tag = struct.unpack_from(endian + 'I', entries, position)[0]
            file_offset, file_size = struct.unpack_from(endian + 'Q16xQ', entries, position + 8)
            if file_offset + file_size > size:
                raise ValueError('ELF segment exceeds file')
            if tag == 3 and require_static:
                raise ValueError('ELF interpreter is forbidden: payload must be static')
            loaded |= tag == 1
            if tag == 2:
                if file_size > 1024 * 1024 or file_size % 16:
                    raise ValueError('invalid ELF dynamic table')
                stream.seek(file_offset)
                dynamic = stream.read(file_size)
                for at in range(0, len(dynamic), 16):
                    dynamic_tag = struct.unpack_from(endian + 'q', dynamic, at)[0]
                    if dynamic_tag == 1 and require_static:
                        raise ValueError('ELF DT_NEEDED is forbidden: payload must be static')
                    if dynamic_tag == 0:
                        break
        if not loaded:
            raise ValueError('ELF has no loadable segment')


def emulator_command(profile, binary):
    emulator = profile['emulator']
    return [emulator['command'], '-cpu', emulator['cpu'], str(binary)]
