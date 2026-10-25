#!/usr/bin/env python3
"""Real gzip/fwtool framing fixtures and corrupt/truncated/oversized rejection."""
import gzip
import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from openwrt_image import extract_openwrt_image, TRAILER, FWIMAGE_MAGIC


def fwtool(image, body, kind):
    content = image + body
    return content + TRAILER.pack(FWIMAGE_MAGIC, zlib.crc32(content) ^ 0xffffffff, kind, b'\0' * 3,
                                  len(body) + TRAILER.size)


class OpenwrtImageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.raw = b'public disk image fixture\0' * 1000
        self.gzip = gzip.compress(self.raw, mtime=0)

    def extract(self, data, pin=None, **options):
        compressed, output = self.root / 'image.gz', self.root / 'disk.img'
        compressed.write_bytes(data)
        output.unlink(missing_ok=True)
        try:
            result = extract_openwrt_image(compressed, output, pin or hashlib.sha256(data).hexdigest(), **options)
        except Exception:
            self.assertFalse(output.exists(), 'Failed extraction left an image that could be booted')
            raise
        self.assertEqual(output.read_bytes(), self.raw)
        return result

    def test_plain_gzip_and_actual_openwrt_fake_certificate_signature_frame(self):
        plain = self.extract(self.gzip)
        self.assertTrue(plain['gzip_crc_verified'])
        self.assertEqual(plain['fwtool_trailers'], [])
        signed = self.extract(fwtool(self.gzip, b'# fake certificate', 0))
        self.assertEqual(signed['fwtool_trailers'], [{'type': 'signature', 'bytes': 34}])

    def test_metadata_and_signature_frames_preserve_full_pinned_image(self):
        metadata = fwtool(self.gzip, b'\0' * 8 + b'{"metadata_version":"1.1","supported_devices":["x86"]}', 1)
        result = self.extract(fwtool(metadata, b'public signature fixture', 0))
        self.assertEqual([p['type'] for p in result['fwtool_trailers']], ['info', 'signature'])
        with self.assertRaises(ValueError):
            self.extract(metadata, pin=hashlib.sha256(self.gzip).hexdigest())

    def test_gzip_crc_truncation_and_unpacked_limit_refuse(self):
        corrupted = bytearray(self.gzip)
        corrupted[-8] ^= 1
        for data, options in ((bytes(corrupted), {}), (self.gzip[:-1], {}),
                              (self.gzip, {'max_unpacked': len(self.raw) - 1})):
            with self.assertRaises((ValueError, zlib.error)):
                self.extract(data, **options)

    def test_highly_compressed_image_streams_across_output_block_boundaries(self):
        self.raw = b'\0' * (3 * 1024 * 1024 + 17)
        result = self.extract(gzip.compress(self.raw, mtime=0), max_unpacked=len(self.raw))
        self.assertEqual(result['unpacked_bytes'], len(self.raw))

    def test_unknown_appended_data_or_second_gzip_member_refuse(self):
        for tail in (b'unknown trailer', b'\0' * 16, gzip.compress(b'another member')):
            with self.assertRaises(ValueError):
                self.extract(self.gzip + tail)

    def test_fwtool_crc_size_type_padding_metadata_and_duplicate_frames_refuse(self):
        valid = fwtool(self.gzip, b'# fake certificate', 0)
        crc = bytearray(valid)
        crc[-12] ^= 1
        size = valid[:-4] + struct.pack('>I', 1)
        padding = valid[:-7] + b'X' + valid[-6:]
        for data in (bytes(crc), size, padding, fwtool(self.gzip, b'data', 2),
                     fwtool(self.gzip, b'\0' * 8 + b'not JSON', 1),
                     fwtool(self.gzip, b'\1' + b'\0' * 7 + b'{}', 1),
                     fwtool(self.gzip, b'\0' * 8 + b'{"a":1,"a":2}', 1),
                     fwtool(self.gzip, b'X' * 1025, 0), fwtool(valid, b'another signature', 0)):
            with self.assertRaises(ValueError):
                self.extract(data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
