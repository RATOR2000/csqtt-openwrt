#!/usr/bin/env python3
"""Real P256 tests for metadata-only GitHub asset name normalization."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
spec = importlib.util.spec_from_file_location('normalize_publication', REPO / 'scripts/normalize-publication-assets.py')
normalization = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalization)
SOURCE, PACKAGING = 'a' * 40, 'b' * 40


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for real P256 crypto')
class NormalizationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='csqtt-normalization-test-')
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        (self.root / 'release').mkdir()
        code = ("const fs=require('node:fs'),c=require('node:crypto'),p=require('node:path');"
                "const root=process.argv[1],key=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'});"
                "fs.writeFileSync(p.join(root,'release/csqtt-public.pem'),key.publicKey.export({type:'spki',format:'pem'}));"
                "fs.writeFileSync(p.join(root,'ephemeral-key.pem'),key.privateKey.export({type:'pkcs8',format:'pem'}));")
        subprocess.run([shutil.which('node'), '-e', code, str(self.root)], check=True, capture_output=True)
        self.secret = (self.root / 'ephemeral-key.pem').read_text()
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.output = self.root / 'published'
        self.installer = b'#!/bin/sh\n# original qualified source fixture\n'
        root_patch = mock.patch.object(normalization, 'ROOT', self.root)
        installer_patch = mock.patch.object(normalization, 'source_installer', return_value=self.installer)
        root_patch.start()
        installer_patch.start()
        self.addCleanup(root_patch.stop)
        self.addCleanup(installer_patch.stop)
        self.profile = 'official-25.12.6-x86-64-x86_64'
        packages = []
        for role in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt'):
            path = self.asset(self.profile + '--' + role + '-1~rc.apk', b'original package bytes ' + role.encode())
            packages.append(normalization.describe(path, role=role, version='1~rc'))
        index = normalization.describe(self.asset(self.profile + '--feed~1.adb', b'original signed feed bytes'),
                                        id='feed1', format='apk-adb', repository='https://downloads.openwrt.org/releases/25.12.6/packages',
                                        key_sha256='c' * 64)
        dep = normalization.describe(self.asset(self.profile + '--dep--libtest-2~rc.apk', b'original dependency bytes'),
                                      package='libtest', version='2~rc', filename='libtest-2~rc.apk', index='feed1')
        proofs = [normalization.describe(self.asset(self.profile + '-' + kind + '-evidence.json',
                                                   json.dumps({'source_commit': SOURCE}).encode())) for kind in ('abi', 'vm')]
        third_party = normalization.describe(self.asset('dnsmasq~source.tar.gz', b'original GPL corresponding source'),
                                              component='dnsmasq', license='GPL-2.0')
        self.manifest = {'schema': 2, 'upstream': normalization.UPSTREAM, 'profile_id': self.profile,
                         'platform': {'family': 'official', 'openwrt': '25.12.6', 'target': 'x86/64', 'architecture': 'x86_64',
                                      'package_manager': 'apk', 'package_format': 'apk'}, 'backend': 'fw4-nft',
                         'dns_binary': '/usr/libexec/csqtt/dnsmasq', 'packages': packages,
                         'dependency_bundle': {'indexes': [index], 'packages': [dep]}, 'third_party_sources': [third_party],
                         'requirements': {'overlay_free_kib': 1, 'tmp_free_kib': 1, 'mem_available_kib': 1,
                                          'packages': [], 'kernel_package': 'kernel-1'},
                         'qualification': {'installation': True, 'activation': True, 'preview': True, 'physical_device': False,
                                           'source_commit': SOURCE, 'proofs': proofs, 'evidence': [p['name'] for p in proofs],
                                           'reason': 'clean_official_firmware_vm_and_selected_abi_preview'}}
        manifest_path = self.inputs / (self.profile + '-manifest.json')
        normalization.write_json(manifest_path, self.manifest)
        normalization.sign_documents([manifest_path], self.secret)
        normalization.write_json(self.inputs / 'catalogue.json', {'schema': 2, 'upstream': normalization.UPSTREAM,
            'profiles': [{**normalization.describe(manifest_path), 'profile_id': self.profile,
                          'signature': normalization.describe(manifest_path.with_suffix('.sig'))}]})
        normalization.sign_documents([self.inputs / 'catalogue.json'], self.secret)
        self.asset('install.sh', self.installer)
        self.asset('csqtt-public.pem', (self.root / 'release/csqtt-public.pem').read_bytes())
        self.asset('RELEASE_NOTES.md', b'Original release notes')
        normalization.checksums(self.inputs)

    def asset(self, name, body):
        path = self.inputs / name
        path.write_bytes(body)
        return path

    def normalize(self, source=SOURCE):
        with mock.patch.dict(os.environ, {'GITHUB_SHA': PACKAGING, 'CSQTT_SIGNING_KEY': self.secret}):
            result = normalization.normalize(self.inputs, self.output, source, '40139753900', '12579223101', 'd' * 64)
            self.assertEqual(os.environ['GITHUB_SHA'], PACKAGING)
            return result

    def test_canonical_names_keep_payload_and_native_identity_bytes(self):
        original = {p.name: p.read_bytes() for p in self.inputs.iterdir()}
        self.normalize()
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.inputs.iterdir()})
        self.assertTrue(all('~' not in p.name for p in self.output.iterdir()))
        catalogue, manifests = normalization.verify_directory(self.output, SOURCE, canonical=True)
        manifest = manifests[self.profile + '-manifest.json']
        self.assertEqual(manifest['qualification'], self.manifest['qualification'])
        self.assertEqual([p['version'] for p in manifest['packages']], ['1~rc'] * 3)
        self.assertEqual(manifest['dependency_bundle']['packages'][0]['filename'], 'libtest-2~rc.apk')
        for descriptor in normalization.descriptors(manifest):
            self.assertNotIn('~', descriptor['name'])
        for descriptor in normalization.descriptors(self.manifest):
            self.assertEqual(original[descriptor['name']], (self.output / descriptor['name'].replace('~', '.')).read_bytes())
        provenance = normalization.load(self.output / catalogue['publication_provenance']['name'])
        self.assertEqual((provenance['source_commit'], provenance['packaging_commit']), (SOURCE, PACKAGING))
        self.assertEqual(provenance['source_artifact_id'], '12579223101')
        self.assertEqual((self.output / 'install.sh').read_bytes(), self.installer)

    def test_wrong_source_and_tampered_payload_refuse_without_output(self):
        with self.assertRaises(ValueError):
            self.normalize('e' * 40)
        self.assertFalse(self.output.exists())
        package = next(self.inputs.glob('*.apk'))
        package.write_bytes(b'X' * package.stat().st_size)
        with self.assertRaises(ValueError):
            self.normalize()
        self.assertFalse(self.output.exists())

    def test_name_collision_refuses_before_staging(self):
        self.asset('dnsmasq.source.tar.gz', b'collision fixture')
        normalization.checksums(self.inputs)
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.normalize()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.csqtt-publication-*')))

    def test_wrong_installer_and_existing_output_refuse(self):
        self.asset('install.sh', b'changed installer')
        normalization.checksums(self.inputs)
        with self.assertRaisesRegex(ValueError, 'Installer differs'):
            self.normalize()
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'new directory'):
            self.normalize()


if __name__ == '__main__':
    unittest.main(verbosity=2)
