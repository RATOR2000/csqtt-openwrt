import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('published', ROOT / 'scripts/verify-published-release.py')
published = importlib.util.module_from_spec(spec)
spec.loader.exec_module(published)


class PublishedTest(unittest.TestCase):
    def flat_release(self, root):
        source_commit = 'a' * 40
        source = root / 'public-assets'
        source.mkdir()
        manifests = []
        for version, fmt in (('24.10.8', 'ipk'), ('25.12.6', 'apk')):
            identity = 'official-' + version + '-x86-64-x86_64'
            packages, proofs = [], []
            for role in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt'):
                path = source / (identity + '--' + role + '-1.' + fmt)
                path.write_bytes(b'public test package ' + role.encode())
                packages.append(published.describe(path, role=role, version='1'))
            for kind in ('abi', 'vm'):
                path = source / (identity + '-' + kind + '-evidence.json')
                path.write_text(json.dumps({'source_commit': source_commit}))
                proofs.append(published.describe(path))
            manifest = {'schema': 2, 'upstream': published.UPSTREAM, 'profile_id': identity,
                        'platform': {'family': 'official', 'openwrt': version, 'target': 'x86/64',
                                     'architecture': 'x86_64', 'package_manager': 'opkg' if fmt == 'ipk' else 'apk',
                                     'package_format': fmt}, 'backend': 'fw4-nft',
                        'dns_binary': '/usr/libexec/csqtt/dnsmasq', 'packages': packages,
                        'dependency_bundle': {'indexes': [], 'packages': []},
                        'requirements': {'overlay_free_kib': 1, 'tmp_free_kib': 1, 'mem_available_kib': 1,
                                         'packages': [], 'kernel_package': 'kernel-1'},
                        'qualification': {'installation': True, 'activation': True, 'preview': True,
                                          'physical_device': False, 'source_commit': source_commit,
                                          'proofs': proofs, 'evidence': [p['name'] for p in proofs],
                                          'reason': 'clean_official_firmware_vm_and_selected_abi_preview'}}
            path = source / (identity + '-manifest.json')
            path.write_text(json.dumps(manifest))
            manifests.append(path)
        # The private test key exists only in this Node process, never on disk or in output.
        code = ("const fs=require('node:fs'),c=require('node:crypto'),p=require('node:path');"
                "const [root,...names]=process.argv.slice(1),key=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'});"
                "fs.writeFileSync(p.join(root,'public.pem'),key.publicKey.export({type:'spki',format:'pem'}));"
                "const read=n=>fs.readFileSync(p.join(root,n));"
                "const describe=n=>({name:n,size:read(n).length,sha256:c.createHash('sha256').update(read(n)).digest('hex')});"
                "const profiles=names.map(n=>{const sig=n.replace(/\\.json$/,'.sig');"
                "fs.writeFileSync(p.join(root,sig),c.sign('sha256',read(n),key.privateKey));"
                "return {...describe(n),profile_id:JSON.parse(read(n)).profile_id,signature:describe(sig)}});"
                "fs.writeFileSync(p.join(root,'catalogue.json'),JSON.stringify({schema:2,upstream:'amurcanov/csqtt@v2.1.9',profiles}));"
                "fs.writeFileSync(p.join(root,'catalogue.sig'),c.sign('sha256',read('catalogue.json'),key.privateKey));")
        subprocess.run([shutil.which('node'), '-e', code, str(source), *[p.name for p in manifests]],
                       check=True, capture_output=True)
        (source / 'install.sh').write_bytes(b'#!/bin/sh\n# public installer test fixture\n')

        def download(url, destination, limit=67108864):
            if '/git/ref/tags/' in url:
                destination.write_text(json.dumps({'object': {'type': 'commit', 'sha': source_commit}}))
            else:
                body = (source / url.rsplit('/', 1)[-1]).read_bytes()
                self.assertLessEqual(len(body), limit)
                destination.write_bytes(body)

        original_verify_signature = published.verify_signature

        def verify_signature(document, signature):
            original_verify_signature(document, signature, source / 'public.pem')

        return source_commit, source, manifests, download, verify_signature

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_flat_multi_profile_release_and_scoped_profile_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            commit, source, manifests, download, verify_signature = self.flat_release(root)
            with mock.patch.object(published, 'download', side_effect=download), mock.patch.object(
                    published, 'verify_signature', side_effect=verify_signature):
                output = root / 'all-profiles'
                report = published.verify('v0.1.0-preview.10', commit, output)
                self.assertEqual(len(report['profiles']), 2)
                self.assertEqual(len(list(output.glob('*.apk'))), 3)
                self.assertEqual(len(list(output.glob('*.ipk'))), 3)
                profile = json.loads(manifests[0].read_text())['profile_id']
                scoped = root / 'one-profile'
                report = published.verify('v0.1.0-preview.10', commit, scoped, [profile])
                self.assertEqual(report['profiles'], [profile])
                self.assertEqual(len(list(scoped.glob('*.ipk'))), 3)
                self.assertFalse(list(scoped.glob('*.apk')))

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_flat_multi_profile_release_rejects_tampered_and_extra_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            commit, source, manifests, download, verify_signature = self.flat_release(root)
            with mock.patch.object(published, 'download', side_effect=download), mock.patch.object(
                    published, 'verify_signature', side_effect=verify_signature):
                for suffix in ('apk', 'ipk'):
                    with self.subTest(extra=suffix):
                        output = root / ('extra-' + suffix)
                        output.mkdir()
                        (output / ('unexpected.' + suffix)).write_bytes(b'public extra package fixture')
                        with self.assertRaisesRegex(ValueError, 'differs from selected profiles'):
                            published.verify('v0.1.0-preview.10', commit, output)
                package = next(source.glob('*.apk'))
                package.write_bytes(b'X' * package.stat().st_size)
                with self.assertRaisesRegex(ValueError, 'checksum or size mismatch'):
                    published.verify('v0.1.0-preview.10', commit, root / 'tampered')

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_signature_rejects_tampered_bytes_and_wrong_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            code = ("const c=require('node:crypto'),fs=require('node:fs'),p=require('node:path');"
                    "const d=process.argv[1],a=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'}),"
                    "b=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'});"
                    "fs.writeFileSync(p.join(d,'key.pem'),a.publicKey.export({type:'spki',format:'pem'}));"
                    "fs.writeFileSync(p.join(d,'other.pem'),b.publicKey.export({type:'spki',format:'pem'}));"
                    "fs.writeFileSync(p.join(d,'doc'),'{\"public\":true}');"
                    "fs.writeFileSync(p.join(d,'sig'),c.sign('sha256',fs.readFileSync(p.join(d,'doc')),a.privateKey));")
            subprocess.run([shutil.which('node'), '-e', code, str(root)], check=True, capture_output=True)
            published.verify_signature(root / 'doc', root / 'sig', root / 'key.pem')
            with self.assertRaises(ValueError):
                published.verify_signature(root / 'doc', root / 'sig', root / 'other.pem')
            (root / 'doc').write_bytes(b'{"public":false}')
            with self.assertRaises(ValueError):
                published.verify_signature(root / 'doc', root / 'sig', root / 'key.pem')

    def test_cached_bytes_cannot_bypass_signed_size_or_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'public.apk').write_bytes(b'original')
            descriptor = published.describe(root / 'public.apk')
            (root / 'public.apk').write_bytes(b'corrupted')
            with mock.patch.object(published, 'download', side_effect=lambda url, path, limit: path.write_bytes(b'bad')):
                with self.assertRaises(ValueError):
                    published.checked_asset(descriptor, 'https://github.com/', root)
            with self.assertRaises(ValueError):
                published.checked_asset({**descriptor, 'name': '../outside'}, 'https://github.com/', root)

    def test_foreign_origins_redirects_and_oversize_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'asset'
            with self.assertRaises(ValueError):
                published.download('http://github.com/asset', path)
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.url = 'https://unapproved.example/asset'
            with mock.patch.object(published.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    published.download('https://github.com/asset', path)
            response.url = 'https://release-assets.githubusercontent.com/asset'
            response.read.return_value = b'12345'
            with mock.patch.object(published.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    published.download('https://github.com/asset', path, 4)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
