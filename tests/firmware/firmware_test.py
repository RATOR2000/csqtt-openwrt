#!/usr/bin/env python3
"""Security and evidence checks without downloading/executing firmware."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('firmware_inspector', ROOT / 'scripts/inspect-glinet-firmware.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class FirmwareEvidence(unittest.TestCase):
    def test_release_is_data_not_shell(self):
        text = "DISTRIB_ID='OpenWrt'\nDISTRIB_RELEASE='21.02-SNAPSHOT'\nDISTRIB_TARGET='mediatek/mt7986'\nDISTRIB_ARCH='aarch64_cortex-a53'\n"
        self.assertEqual(inspector.parse_release(text)['DISTRIB_RELEASE'], '21.02-SNAPSHOT')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            inspector.parse_release(text + "DISTRIB_RELEASE='25.12.5'\n")
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            inspector.parse_release(text.replace("DISTRIB_RELEASE='21.02-SNAPSHOT'", "DISTRIB_RELEASE=$(touch unexpected)"))

    def test_ambiguous_package_inventory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate installed'):
            inspector.parse_packages('Package: firewall\nVersion: 1\n\nPackage: firewall\nVersion: 2\n')
        with self.assertRaisesRegex(ValueError, 'duplicate package metadata'):
            inspector.parse_packages('Package: firewall\nVersion: 1\nVersion: 2\n')

    def test_oversized_image_not_read(self):
        image = Mock()
        image.stat.return_value.st_size = inspector.MAX_IMAGE + 1
        with self.assertRaisesRegex(ValueError, 'size limit'):
            inspector.inspect(image)
        image.read_bytes.assert_not_called()

    def test_digest_mismatch_rejected_before_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            image = pathlib.Path(directory) / 'firmware.bin'
            image.write_bytes(b'not the authenticated firmware')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                inspector.inspect(image, '0' * 64)

    def test_vendor_reference_never_implies_activation(self):
        evidence = json.loads((ROOT / 'docs/evidence/glinet-flint2-4.11.0.json').read_text())
        self.assertEqual(evidence['gl_version'], '4.11.0')
        self.assertEqual(evidence['packages']['kmod-tun']['Depends'],
                         'kernel (= ' + evidence['packages']['kernel']['Version'] + ')')
        self.assertTrue(evidence['capabilities']['firewall_calls_fw3'])
        self.assertFalse(evidence['capabilities']['fw4'])
        self.assertIsNone(evidence['packages']['ucode'])
        self.assertFalse(evidence['qualification']['install'])
        self.assertFalse(evidence['qualification']['activate'])
        self.assertTrue(all(f['url'].startswith('https://fw.gl-inet.com/') for f in evidence['feeds']))


if __name__ == '__main__':
    unittest.main()
