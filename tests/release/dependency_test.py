#!/usr/bin/env python3
"""Dependency closure/kernel boundaries and immutable release publication gates."""
import importlib.util
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_schema import validate

spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-dependencies.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class DependencyTest(unittest.TestCase):
    def native_fixture(self, directory):
        root = pathlib.Path(directory)
        keys = root / 'keys'
        keys.mkdir()
        body = b'public official key fixture'
        fingerprint = hashlib.sha256(body).hexdigest()
        (keys / fingerprint).write_bytes(body)
        package = root / 'unsigned.apk'
        package.write_bytes(b'public unsigned package fixture')
        index = root / 'packages.adb'
        index.write_bytes(b'public signed index fixture')
        return ({'name': 'dependency', 'version': '1-r1', 'filename': 'dependency-1-r1.apk', 'index': 'feed0',
                 'arch': 'x86_64', 'hashes': 'public index-added digest fixture'},
                package, {'key_sha256': fingerprint, 'path': index}, keys)

    def test_unsigned_apk_is_natively_fetched_from_exact_signed_file_index_in_fresh_output(self):
        with tempfile.TemporaryDirectory() as directory:
            row, package, index, keys = self.native_fixture(directory)
            def native(args, **options):
                if 'adbdump' in args:
                    # Some producers omit hashes in raw info. Native signed
                    # index verification must remain authoritative.
                    info = {field: row[field] for field in ('name', 'version', 'arch')}
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({'info': info}).encode(), stderr=b'')
                self.assertIn('--no-network', args)
                self.assertNotIn('--allow-untrusted', args)
                self.assertNotIn('--link', args)
                self.assertNotIn('--recursive', args)
                self.assertEqual(args[-1], row['name'])
                fetched = pathlib.Path(args[args.index('--output') + 1])
                self.assertEqual(list(fetched.iterdir()), [])
                target = pathlib.Path(args[args.index('--root') + 1])
                self.assertEqual((target / 'etc/apk/keys/source.pem').read_bytes(), (keys / index['key_sha256']).read_bytes())
                repositories = pathlib.Path(args[args.index('--repositories-file') + 1])
                self.assertEqual(repositories.read_text().strip(), (fetched.parent / 'mirror/packages.adb').as_uri())
                self.assertEqual((fetched.parent / 'mirror/packages.adb').read_bytes(), index['path'].read_bytes())
                shutil.copyfile(package, fetched / row['filename'])
                return subprocess.CompletedProcess(args, 0, stdout=b'', stderr=b'')
            with mock.patch.object(bundle.subprocess, 'run', side_effect=native):
                bundle.authenticate_apk_payload('native-apk', 'x86_64', row, package, index, keys, pathlib.Path(directory) / 'work')

    def test_raw_apk_hash_representation_does_not_replace_native_index_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            row, package, index, keys = self.native_fixture(directory)
            calls = []
            def native(args, **options):
                calls.append(args)
                if 'adbdump' in args:
                    info = {field: row[field] for field in ('name', 'version', 'arch')}
                    info['hashes'] = 'raw producer metadata digest'
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({'info': info}).encode())
                fetched = pathlib.Path(args[args.index('--output') + 1])
                shutil.copyfile(package, fetched / row['filename'])
                return subprocess.CompletedProcess(args, 0)
            with mock.patch.object(bundle.subprocess, 'run', side_effect=native):
                bundle.authenticate_apk_payload('native-apk', 'x86_64', row, package, index, keys,
                                                pathlib.Path(directory) / 'work')
            self.assertEqual(len(calls), 2)
            self.assertIn('fetch', calls[-1])
            self.assertIn('--no-network', calls[-1])

    def test_native_apk_missing_output_corruption_rejection_and_wrong_key_pin_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            row, package, index, keys = self.native_fixture(directory)
            for mode in ('missing', 'changed', 'native_rejection'):
                def native(args, **options):
                    if 'adbdump' in args:
                        info = {field: row[field] for field in ('name', 'version', 'arch')}
                        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({'info': info}).encode(), stderr=b'')
                    if mode == 'native_rejection':
                        raise subprocess.CalledProcessError(1, args)
                    if mode == 'changed':
                        fetched = pathlib.Path(args[args.index('--output') + 1])
                        (fetched / row['filename']).write_bytes(b'X' * package.stat().st_size)
                    return subprocess.CompletedProcess(args, 0, stdout=b'', stderr=b'')
                with mock.patch.object(bundle.subprocess, 'run', side_effect=native):
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        bundle.authenticate_apk_payload('native-apk', 'x86_64', row, package, index, keys,
                                                        pathlib.Path(directory) / mode)
            (keys / index['key_sha256']).write_bytes(b'changed public key')
            with mock.patch.object(bundle.subprocess, 'run') as native:
                with self.assertRaises(ValueError):
                    bundle.authenticate_apk_payload('native-apk', 'x86_64', row, package, index, keys,
                                                    pathlib.Path(directory) / 'wrong-key')
                native.assert_not_called()

    def test_raw_apk_wrong_name_version_or_arch_refuses_before_native_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            row, package, index, keys = self.native_fixture(directory)
            for field, wrong in (('name', 'other'), ('version', '2-r1'), ('arch', 'other_arch')):
                info = {f: row[f] for f in ('name', 'version', 'arch')}
                info[field] = wrong
                result = subprocess.CompletedProcess([], 0, stdout=json.dumps({'info': info}).encode(), stderr=b'')
                with mock.patch.object(bundle.subprocess, 'run', return_value=result) as native:
                    with self.assertRaisesRegex(ValueError, 'identity differs'):
                        bundle.authenticate_apk_payload('native-apk', 'x86_64', row, package, index, keys,
                                                        pathlib.Path(directory) / field)
                    self.assertEqual(native.call_count, 1)
                    self.assertIn('adbdump', native.call_args.args[0])

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
        self.assertEqual(next(row for row in result if row['name'] == 'kmod-tun')['kernel_package'], kernel)

    def test_conntrack_modules_are_cached_transitively_with_their_own_exact_kernel(self):
        abi = '6.12.112~abcd-r1'
        rows = [{'name': 'kmod-tun', 'version': '1-r1', 'depends': ['kernel=' + abi]},
                {'name': 'conntrack', 'version': '1-r1', 'depends': ['kmod-nf-conntrack-netlink']},
                {'name': 'kmod-nf-conntrack-netlink', 'version': '2-r1',
                 'depends': ['kernel (= ' + abi + ')', 'kmod-nf-netlink']},
                {'name': 'kmod-nf-netlink', 'version': '3-r1', 'depends': ['kernel=' + abi, 'libc']}]
        result, required, kernel = bundle.closure(rows, ['kmod-tun', 'conntrack', 'firewall4'])
        self.assertEqual({row['name'] for row in result},
                         {'kmod-tun', 'conntrack', 'kmod-nf-conntrack-netlink', 'kmod-nf-netlink'})
        self.assertEqual(required, ['firewall4', 'kernel', 'libc'])
        self.assertEqual(kernel, abi)
        for row in result:
            if row['name'].startswith('kmod-'):
                self.assertEqual(row['kernel_package'], abi)
        self.assertTrue(all('kernel_package' not in row for row in rows), 'Do not rewrite authenticated feed rows')

    def test_every_module_requires_one_own_exact_abi_even_when_tun_is_valid(self):
        abi = '6.12.112~abcd-r1'
        for dependencies in ([], ['kernel'], ['kernel>=1'], ['kernel='], ['!kernel=' + abi],
                             ['kernel=' + abi, 'kernel=' + abi],
                             ['kernel=' + abi, 'kernel=6.12.112~other-r1'],
                             ['kernel=6.12.112~other-r1']):
            rows = [{'name': 'kmod-tun', 'version': '1-r1', 'depends': ['kernel=' + abi]},
                    {'name': 'kmod-nf-conntrack-netlink', 'version': '1-r1', 'depends': dependencies}]
            for roots in (['kmod-tun', 'kmod-nf-conntrack-netlink'],
                          ['kmod-nf-conntrack-netlink', 'kmod-tun']):
                with self.subTest(dependencies=dependencies, roots=roots), self.assertRaises(ValueError):
                    bundle.closure(rows, roots)

    def test_firmware_stays_required_only_and_another_module_cannot_replace_tun(self):
        abi = '6.12.112~abcd-r1'
        rows = [{'name': 'kmod-tun', 'version': '1-r1', 'depends': ['kernel=' + abi]},
                *({'name': name, 'version': '1-r1'} for name in bundle.FIRMWARE)]
        selected, required, _ = bundle.closure(rows, ['kmod-tun', *sorted(bundle.FIRMWARE - {'kernel'})])
        self.assertEqual([row['name'] for row in selected], ['kmod-tun'])
        self.assertEqual(set(required), bundle.FIRMWARE)
        with self.assertRaises(ValueError):
            bundle.closure([{'name': 'kmod-other', 'version': '1-r1', 'depends': ['kernel=' + abi]}], ['kmod-other'])

    def test_same_version_duplicate_feed_module_cannot_hide_another_kernel_abi(self):
        abi = '6.12.112~abcd-r1'
        rows = [{'name': 'kmod-tun', 'version': '1-r1', 'depends': ['kernel=' + abi]},
                {'name': 'kmod-extra', 'version': '1-r1', 'depends': ['kernel=' + abi]},
                {'name': 'kmod-extra', 'version': '1-r1', 'depends': ['kernel=6.12.112~other-r1']}]
        for ordered in (rows, list(reversed(rows))):
            with self.subTest(reverse=ordered is not rows), self.assertRaises(ValueError):
                bundle.closure(ordered, ['kmod-tun', 'kmod-extra'])

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
