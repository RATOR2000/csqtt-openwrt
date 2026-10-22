#!/usr/bin/env python3
"""Dependency closure/kernel boundaries and immutable release publication gates."""
import importlib.util
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_schema import validate

spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-dependencies.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class DependencyTest(unittest.TestCase):
    def test_complete_transitive_closure_retains_exact_tun_kernel(self):
        rows = [{'name': 'kmod-tun', 'version': '6.12.112-r1', 'depends': ['kernel=6.12.112~abcd-r1']},
                {'name': 'luci-base', 'version': '1-r1', 'depends': ['ucode-mod-fs', 'libubus>=1']},
                {'name': 'ucode-mod-fs', 'version': '1-r1', 'depends': ['libc']},
                {'name': 'libubus2025', 'version': '1-r1', 'provides': ['libubus=1-r1']},
                {'name': 'libc', 'version': '1-r1'}]
        result, required, kernel = bundle.closure(rows, ['kmod-tun', 'luci-base', 'firewall4', 'procd'])
        self.assertEqual({r['name'] for r in result}, {'kmod-tun', 'luci-base', 'ucode-mod-fs', 'libubus2025'})
        self.assertEqual(required, ['firewall4', 'kernel', 'libc', 'procd'])
        self.assertEqual(kernel, '6.12.112~abcd-r1')

    def test_missing_ambiguous_conflicting_and_nonexact_kernel_refuse(self):
        for rows, roots in [([], ['missing']),
                            ([{'name': 'kmod-tun', 'version': '1', 'depends': ['kernel>=1']}], ['kmod-tun']),
                            ([{'name': 'p', 'version': '1'}, {'name': 'p', 'version': '2'}], ['p']),
                            ([{'name': 'p', 'version': '2'}], ['p=1']),
                            ([{'name': 'p', 'version': '1'}], ['p | other'])]:
            with self.assertRaises(ValueError):
                bundle.closure(rows, roots)

    def test_no_foreign_download_origin_or_unsafe_dependency(self):
        for url in ('http://downloads.openwrt.org/file', 'https://attacker.example/feed'):
            with self.assertRaises(ValueError):
                bundle.download(url, pathlib.Path('never-written'))
        for value in ('../package', '$(echo_secret)', 'name;uname'):
            with self.assertRaises(ValueError):
                bundle.dep_identity(value)

    def test_frozen_tag_and_mismatched_revision_refuse(self):
        for tag, revision, status in [('v0.1.0-preview.9', '9', 1), ('v0.1.0-preview.10', '9', 1),
                                      ('v0.1.0-preview.10', '10', 0), ('bad/tag', '10', 1)]:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/check-preview-tag.py'), tag, revision], capture_output=True)
            self.assertEqual(result.returncode, status)


if __name__ == '__main__':
    unittest.main(verbosity=2)
