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
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_schema import validate

spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-dependencies.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class DependencyTest(unittest.TestCase):
    def profile_metadata(self):
        profile = {'openwrt': '24.10.8', 'target': 'x86/64', 'architecture': 'x86_64'}
        document = {'version_number': '24.10.8', 'target': 'x86/64', 'arch_packages': 'x86_64',
                    'linux_kernel': {'version': '6.6.144', 'release': '1',
                                     'vermagic': '50daf8372d971124fb3519e8d87e02ae'}}
        return profile, document

    def test_profiles_metadata_maps_six_exact_tuples_to_feed_directory_and_distinct_package_abi(self):
        kernels = (('24.10.8', '6.6.144', '50daf8372d971124fb3519e8d87e02ae', '43cbcde0affaaf16309bb4ab09799e9a'),
                   ('25.12.5', '6.12.94', 'a7bc15f451f9652701ba04af9cfb0b95', '5a6c1f71be683ae9980b15d3ce73e24d'),
                   ('25.12.6', '6.12.112', 'b4125196ecec75391093e1e2edeba490', 'f0a7348f9cb959e1bf4d0447669b031e'))
        for release, version, x86_hash, arm_hash in kernels:
            for target, arch, vermagic in (('x86/64', 'x86_64', x86_hash),
                                           ('mediatek/filogic', 'aarch64_cortex-a53', arm_hash)):
                profile = {'openwrt': release, 'target': target, 'architecture': arch}
                document = {'version_number': release, 'target': target, 'arch_packages': arch,
                            'linux_kernel': {'version': version, 'release': '1', 'vermagic': vermagic}}
                with self.subTest(release=release, target=target):
                    directory, abi = bundle.kernel_feed(profile, json.dumps(document).encode('utf-8'))
                    self.assertEqual(directory, version + '-1-' + vermagic)
                    self.assertEqual(abi, version + '~' + vermagic + '-r1')
                    self.assertNotEqual(directory, abi)

    def test_profiles_metadata_refuses_wrong_tuple_types_ambiguous_json_and_unsafe_kernel_tokens(self):
        profile, original = self.profile_metadata()
        for field, wrong in (('version_number', '25.12.6'), ('target', 'mediatek/filogic'),
                             ('arch_packages', 'aarch64_cortex-a53'), ('target', ['x86/64']),
                             ('version_number', None), ('linux_kernel', None), ('linux_kernel', [])):
            document = {**original, field: wrong}
            with self.subTest(field=field, wrong=wrong), self.assertRaises(ValueError):
                bundle.kernel_feed(profile, json.dumps(document).encode('utf-8'))
        for field, wrong in (('version', '6.6.144/../other'), ('version', 6), ('version', '6.6.144\n'),
                             ('release', 1), ('release', True), ('release', '0'), ('release', '01'),
                             ('vermagic', 'a' * 31), ('vermagic', 'A' * 32), ('vermagic', '../other')):
            document = {**original, 'linux_kernel': {**original['linux_kernel'], field: wrong}}
            with self.subTest(field=field, wrong=wrong), self.assertRaises(ValueError):
                bundle.kernel_feed(profile, json.dumps(document).encode('utf-8'))
        duplicate = json.dumps(original).replace('"release": "1"', '"release": "1", "release": "2"').encode('utf-8')
        for body in (b'', b'[]', b'null', b'"text"', b'\xff', b'{', duplicate):
            with self.subTest(body=body[:50]), self.assertRaises(ValueError):
                bundle.kernel_feed(profile, body)

    def test_authenticated_module_closure_must_confirm_discovered_kernel_abi(self):
        profile, document = self.profile_metadata()
        _, abi = bundle.kernel_feed(profile, json.dumps(document).encode('utf-8'))
        rows = [{'name': 'kmod-tun', 'version': '6.6.144-r1', 'depends': ['kernel (= ' + abi + ')']},
                {'name': 'kmod-extra', 'version': '6.6.144-r1', 'depends': ['kernel=' + abi]}]
        selected, _, actual = bundle.closure(rows, ['kmod-tun', 'kmod-extra'], expected_kernel=abi)
        self.assertEqual(actual, abi)
        self.assertTrue(all(row['kernel_package'] == abi for row in selected))
        document['linux_kernel']['vermagic'] = 'a' * 32
        _, wrong = bundle.kernel_feed(profile, json.dumps(document).encode('utf-8'))
        with self.assertRaisesRegex(ValueError, 'differs from target profile'):
            bundle.closure(rows, ['kmod-tun', 'kmod-extra'], expected_kernel=wrong)

    def test_download_failure_identifies_only_fixed_stage_index_and_http_status(self):
        private = 'private-url-command-response-fixture'
        url = 'https://downloads.openwrt.org/' + private
        errors = (urllib.error.HTTPError(url, 502, private, None, None), urllib.error.URLError(private), OSError(private))
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / 'not-created'
            for error in errors:
                with self.subTest(error=type(error).__name__), \
                        mock.patch.object(bundle.urllib.request, 'urlopen', side_effect=error):
                    with self.assertRaises(ValueError) as raised:
                        bundle.download(url, output, stage='feed_index', index=1)
                self.assertIn('stage=feed_index index=1', str(raised.exception))
                self.assertNotIn(private, str(raised.exception))
                self.assertNotIn('https:', str(raised.exception))
                self.assertEqual('http_status=502' in str(raised.exception), isinstance(error, urllib.error.HTTPError))
                self.assertFalse(output.exists())
            with mock.patch.object(bundle.urllib.request, 'urlopen', side_effect=errors[0]):
                with self.assertRaisesRegex(ValueError, 'stage=payload index=4095 http_status=502'):
                    bundle.download(url, output, stage='payload', index=4095)
            for stage, index in ((private, 0), ('payload', private), ('payload', True), ('payload', 4096)):
                with self.subTest(stage=stage, index=index), mock.patch.object(bundle.urllib.request, 'urlopen') as read:
                    with self.assertRaises(ValueError):
                        bundle.download(url, output, stage=stage, index=index)
                    read.assert_not_called()

    def test_labeled_download_retains_origin_size_and_digest_checks(self):
        body = b'public pinned metadata bytes'
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.url = 'https://downloads.openwrt.org/public-fixture'
        response.read.return_value = body
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / 'metadata'
            with mock.patch.object(bundle.urllib.request, 'urlopen', return_value=response) as read:
                result = bundle.download(response.url, output, hashlib.sha256(body).hexdigest(), stage='profiles')
            self.assertEqual(result, body)
            self.assertEqual(output.read_bytes(), body)
            read.assert_called_once_with(response.url, timeout=60)
            response.read.assert_called_once_with(bundle.LIMIT + 1)
            output.unlink()
            for invalid in (b'', b'12345'):
                response.read.return_value = invalid
                with mock.patch.object(bundle, 'LIMIT', 4), \
                        mock.patch.object(bundle.urllib.request, 'urlopen', return_value=response):
                    with self.assertRaises(ValueError):
                        bundle.download(response.url, output, stage='profiles')
                self.assertFalse(output.exists())
            response.read.return_value = body
            with mock.patch.object(bundle.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    bundle.download(response.url, output, '0' * 64, stage='rootfs')
            self.assertFalse(output.exists())
            response.url = 'https://foreign.invalid/metadata'
            with mock.patch.object(bundle.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    bundle.download('https://downloads.openwrt.org/metadata', output, stage='profiles')
            self.assertFalse(output.exists())

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
