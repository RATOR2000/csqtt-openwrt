#!/usr/bin/env python3
"""Real P256 regression: catalogue signing must retain authenticated tuple bytes."""
import hashlib
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
SOURCE = 'a' * 40


def describe(path, **fields):
    return {**fields, 'name': path.name, 'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@unittest.skipUnless(shutil.which('openssl'), 'Real OpenSSL is required for the ephemeral P256 signing regression')
class PortableSigningTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='csqtt-signing-test-')
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'release').mkdir()
        for name in ('sign-portable-release.py', 'release-catalogue.py', 'release_schema.py'):
            shutil.copyfile(REPO / 'scripts' / name, self.root / 'scripts' / name)
        self.key = self.root / 'ephemeral-key.pem'
        self.openssl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', self.key)
        self.openssl('pkey', '-in', self.key, '-pubout', '-out', self.root / 'release/csqtt-public.pem')
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.manifests = []
        for version in ('24.10.8', '25.12.5', '25.12.6'):
            for target, architecture in (('mediatek/filogic', 'aarch64_cortex-a53'), ('x86/64', 'x86_64')):
                self.manifests.append(self.manifest(version, target, architecture))

    def openssl(self, *args):
        return subprocess.run(['openssl', *map(str, args)], check=True, capture_output=True)

    def manifest(self, version, target, architecture):
        profile = 'official-' + version + '-' + target.replace('/', '-') + '-' + architecture
        directory = self.inputs / ('candidate-' + profile)
        directory.mkdir()
        fmt = 'ipk' if version.startswith('24.') else 'apk'
        packages = []
        for role in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt'):
            path = directory / (profile + '--' + role + '-1.' + fmt)
            path.write_bytes(b'public package fixture')
            packages.append(describe(path, role=role, version='1'))
        proofs = []
        for name in ('abi', 'vm'):
            path = directory / (profile + '-' + name + '-evidence.json')
            path.write_text('{"public_test_fixture": true}\n')
            proofs.append(describe(path))
        data = {'schema': 2, 'upstream': 'amurcanov/csqtt@v2.1.9', 'profile_id': profile,
                'platform': {'family': 'official', 'openwrt': version, 'target': target,
                             'architecture': architecture, 'package_manager': 'opkg' if fmt == 'ipk' else 'apk',
                             'package_format': fmt}, 'backend': 'fw4-nft',
                'dns_binary': '/usr/libexec/csqtt/dnsmasq', 'packages': packages,
                'dependency_bundle': {'packages': [], 'indexes': []},
                'requirements': {'overlay_free_kib': 1, 'tmp_free_kib': 1, 'mem_available_kib': 1,
                                 'packages': [], 'kernel_package': 'kernel-1'},
                'qualification': {'installation': True, 'activation': True, 'preview': True,
                                  'physical_device': False, 'source_commit': SOURCE, 'proofs': proofs,
                                  'evidence': [p['name'] for p in proofs],
                                  'reason': 'clean_official_firmware_vm_and_selected_abi_preview'}}
        path = directory / (profile + '-manifest.json')
        path.write_text(json.dumps(data) + '\n')
        return path

    def command(self, script, *args, success=True, **environment):
        env = {**os.environ, 'GITHUB_SHA': SOURCE, 'CSQTT_SIGNING_KEY': self.key.read_text(), **environment}
        result = subprocess.run([sys.executable, str(self.root / 'scripts' / script), *map(str, args)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertNotIn(self.key.read_text().strip(), result.stdout + result.stderr)
        return result

    def tuples_and_catalogue(self):
        self.command('sign-portable-release.py', self.inputs)
        before = {path: path.with_suffix('.sig').read_bytes() for path in self.manifests}
        self.command('release-catalogue.py', self.inputs, *self.manifests, '--require-qualified')
        return before

    def test_catalogue_only_preserves_real_ecdsa_tuple_signatures(self):
        before = self.tuples_and_catalogue()
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only')
        for path, signature in before.items():
            self.assertEqual(path.with_suffix('.sig').read_bytes(), signature)
            self.assertEqual((path.parent / 'manifest.sig').read_bytes(), signature)
        self.command('sign-portable-release.py', self.inputs, '--verify-only', CSQTT_SIGNING_KEY='')
        self.command('sign-portable-release.py', self.inputs, success=False)
        for path, signature in before.items():
            self.assertEqual(path.with_suffix('.sig').read_bytes(), signature)

    def test_randomized_resigning_after_catalogue_creation_is_rejected(self):
        before = self.tuples_and_catalogue()
        path = self.manifests[0]
        self.openssl('dgst', '-sha256', '-sign', self.key, '-out', path.with_suffix('.sig'), path)
        self.assertNotEqual(path.with_suffix('.sig').read_bytes(), before[path])
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only', success=False)
        self.assertFalse((self.inputs / 'catalogue.sig').exists())

    def test_wrong_key_foreign_source_and_invalid_signature_are_rejected(self):
        self.tuples_and_catalogue()
        other = self.root / 'other-ephemeral-key.pem'
        self.openssl('ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', other)
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only',
                     CSQTT_SIGNING_KEY=other.read_text(), success=False)
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only',
                     GITHUB_SHA='b' * 40, success=False)
        path = self.manifests[0]
        path.with_suffix('.sig').write_bytes(b'invalid public signature fixture')
        catalogue = self.inputs / 'catalogue.json'
        data = json.loads(catalogue.read_text())
        next(entry for entry in data['profiles'] if entry['name'] == path.name)['signature'] = describe(path.with_suffix('.sig'))
        catalogue.write_text(json.dumps(data))
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only', success=False)

    def test_final_verification_rejects_tampered_catalogue_and_package(self):
        self.tuples_and_catalogue()
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only')
        catalogue = self.inputs / 'catalogue.json'
        original = catalogue.read_bytes()
        catalogue.write_bytes(original + b' ')
        self.command('sign-portable-release.py', self.inputs, '--verify-only', success=False)
        catalogue.write_bytes(original)
        package = next(self.manifests[0].parent.glob('*.ipk'))
        package.write_bytes(b'changed public package fixture')
        self.command('sign-portable-release.py', self.inputs, '--verify-only', success=False)

    def test_catalogue_only_rejects_cryptographically_signed_unqualified_profile(self):
        self.tuples_and_catalogue()
        path = self.manifests[0]
        manifest = json.loads(path.read_text())
        manifest['qualification']['activation'] = False
        path.write_text(json.dumps(manifest))
        self.openssl('dgst', '-sha256', '-sign', self.key, '-out', path.with_suffix('.sig'), path)
        catalogue = self.inputs / 'catalogue.json'
        data = json.loads(catalogue.read_text())
        entry = next(entry for entry in data['profiles'] if entry['name'] == path.name)
        entry.update(describe(path), signature=describe(path.with_suffix('.sig')))
        catalogue.write_text(json.dumps(data))
        self.command('sign-portable-release.py', self.inputs, '--catalogue-only', success=False)

    def test_prepare_verifies_all_six_copied_profiles_without_resigning(self):
        sys.path.insert(0, str(REPO / 'scripts'))
        self.addCleanup(sys.path.remove, str(REPO / 'scripts'))
        spec = importlib.util.spec_from_file_location('prepare_portable_signing_test', REPO / 'scripts/prepare-portable-release.py')
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        prepare.ROOT = self.root
        (self.root / 'install.sh').write_text('#!/bin/sh\n# public installer fixture\n')
        for version in ('24.10.8', '25.12.5', '25.12.6'):
            proof = self.inputs / ('native-vm-' + version)
            proof.mkdir()
            (proof / (version + '-vm-evidence.json')).write_text('{}')
        snapshots = {}
        qualified = []

        def command(script, *args):
            if script == 'release-evidence.py':
                # Fixtures are already qualified; real evidence qualification has its own suite.
                qualified.append(args)
                return
            self.command(script, *args)
            if script == 'sign-portable-release.py' and len(args) == 1:
                snapshots.update({path.name: path.with_suffix('.sig').read_bytes() for path in self.manifests})

        output = self.root / 'published'
        with mock.patch.object(prepare, 'command', command), mock.patch.object(
                sys, 'argv', ['prepare-portable-release.py', str(self.inputs), str(output)]):
            prepare.main()
        self.assertEqual(len(qualified), 6)
        self.assertEqual(len(snapshots), 6)
        for name, signature in snapshots.items():
            self.assertEqual((output / pathlib.Path(name).with_suffix('.sig')).read_bytes(), signature)
        self.command('sign-portable-release.py', output, '--verify-only', CSQTT_SIGNING_KEY='')


if __name__ == '__main__':
    unittest.main(verbosity=2)
