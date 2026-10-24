#!/usr/bin/env python3
"""Extract pinned OpenWrt gzip images with strictly checked fwtool trailers.

Format: openwrt/fwtool fwimage.h and fwtool.c (FWx0, big-endian fields,
signature <=1024 bytes, INFO <=30KiB plus its zero version/flags header).
This checks framing/CRC only; the complete published image SHA256 is the pin.
"""
import hashlib
import json
import pathlib
import re
import struct
import zlib

from release_schema import require

COMPRESSED_LIMIT = 64 * 1024 * 1024
UNPACKED_LIMIT = 512 * 1024 * 1024
TRAILER = struct.Struct('>IIB3sI')
FWIMAGE_MAGIC = 0x46577830


def fwtool_trailers(data, gzip_end):
    end, seen, trailers = len(data), set(), []
    while end > gzip_end:
        require(end - gzip_end >= TRAILER.size and len(trailers) < 2, 'Unknown or excessive image trailer')
        magic, crc, kind, padding, size = TRAILER.unpack(data[end - TRAILER.size:end])
        require(magic == FWIMAGE_MAGIC and padding == b'\0\0\0' and kind in (0, 1) and kind not in seen,
                'Unknown fwtool trailer magic/type/padding')
        maximum = TRAILER.size + (1024 if kind == 0 else 8 + 30 * 1024)
        require(TRAILER.size < size <= maximum and end - size >= gzip_end, 'Invalid fwtool trailer size')
        require(crc == (zlib.crc32(data[:end - TRAILER.size]) ^ 0xffffffff), 'fwtool trailer CRC mismatch')
        body = data[end - size:end - TRAILER.size]
        if kind == 1:
            require(len(body) > 8 and body[:8] == b'\0' * 8, 'Unsupported fwtool metadata header')
            def unique(pairs):
                result = {}
                for name, value in pairs:
                    require(name not in result, 'Duplicate fwtool metadata key')
                    result[name] = value
                return result
            require(isinstance(json.loads(body[8:], object_pairs_hook=unique), dict), 'fwtool metadata must be an object')
        seen.add(kind)
        trailers.append({'type': 'signature' if kind == 0 else 'info', 'bytes': size})
        end -= size
    require(end == gzip_end, 'Image trailer overlaps compressed member')
    return list(reversed(trailers))


def extract_openwrt_image(compressed, output, expected_sha256, max_unpacked=UNPACKED_LIMIT):
    compressed, output = pathlib.Path(compressed), pathlib.Path(output)
    require(re.fullmatch(r'[0-9a-f]{64}', expected_sha256), 'Full official image SHA256 is required')
    require(compressed.is_file() and 0 < compressed.stat().st_size <= COMPRESSED_LIMIT, 'Compressed image exceeds bound')
    require(not output.exists() and 0 < max_unpacked <= 2 * 1024 * 1024 * 1024, 'Invalid output or unpacked image bound')
    with compressed.open('rb') as stream:
        data = stream.read(COMPRESSED_LIMIT + 1)
    require(0 < len(data) <= COMPRESSED_LIMIT, 'Compressed image exceeds bound')
    require(hashlib.sha256(data).hexdigest() == expected_sha256, 'Full official image SHA256 mismatch')
    decoder, pending, written = zlib.decompressobj(16 + zlib.MAX_WBITS), data, 0
    try:
        with output.open('xb') as stream:
            while True:
                block = decoder.decompress(pending, min(1024 * 1024, max_unpacked - written + 1))
                written += len(block)
                require(written <= max_unpacked, 'Unpacked image exceeds bound')
                stream.write(block)
                if decoder.eof:
                    break
                pending = decoder.unconsumed_tail
                require(pending or block, 'Truncated gzip image or missing gzip checksum')
        require(written > 0, 'Empty image')
        trailers = fwtool_trailers(data, len(data) - len(decoder.unused_data))
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {'compressed_bytes': len(data), 'unpacked_bytes': written, 'gzip_crc_verified': True,
            'fwtool_trailers': trailers}
