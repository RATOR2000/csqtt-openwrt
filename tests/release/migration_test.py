#!/usr/bin/env python3
"""Host contracts for the native migration driver; native APK CI is separate."""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('migration', ROOT / 'scripts/test-r9-migration.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='csqtt-migration-contract-')
        self.addCleanup(self.temporary.cleanup)
        self.work = pathlib.Path(self.temporary.name)
        self.guest = self.work / 'root'
        (self.guest / 'etc/apk').mkdir(parents=True)
        self.world = b'csqtt=0.1.0-r9\ncsqtt-captcha=0.1.0-r9\nluci-app-csqtt=0.1.0-r9\ndnsmasq-full\n'
        (self.guest / 'etc/apk/world').write_bytes(self.world)
        self.before = {role: '0.1.0-r9' for role in migration.ROLES}
        self.before.update({'dnsmasq-full': '2.93-r1', 'libc': '1.2.5-r1', 'existing': '2-r1'})
        self.state = dict(self.before)
        self.calls, self.mode = [], ''
        self.manifest = {'packages': [{'role': role, 'version': '0.1.0-r10', 'name': role + '-r10.apk'}
                                      for role in sorted(migration.ROLES)],
                         'dependency_bundle': {'packages': [
                             {'package': 'introduced', 'version': '3-r1', 'name': 'introduced.apk'},
                             {'package': 'existing', 'version': '99-r1', 'name': 'existing.apk'}]}}
        self.old = [self.work / (role + '-r9.apk') for role in sorted(migration.ROLES)]
        silence = contextlib.redirect_stdout(io.StringIO())
        silence.__enter__()
        self.addCleanup(silence.__exit__, None, None, None)

    def apk(self, *arguments):
        args = tuple(map(str, arguments))
        self.calls.append(args)
        if 'query' in args:
            return SimpleNamespace(stdout=json.dumps([{'name': n, 'version': v} for n, v in self.state.items()]).encode())
        self.assertIn('--no-network', args)
        if 'add' in args and any(name.endswith('-r10.apk') for name in args):
            self.assertIn(str(self.work / 'signed-repositories'), args)
            self.assertIn('introduced=3-r1', args)
            self.assertNotIn('existing=99-r1', args)
            self.assertNotIn(str(self.work / 'introduced.apk'), args)
            self.state.update({role: '0.1.0-r10' for role in migration.ROLES})
            self.state['introduced'] = '3-r1'
            (self.guest / 'etc/apk/world').write_bytes(b'candidate temporary roots\n')
            if self.mode == 'provider_changed':
                self.state['dnsmasq-full'] = 'changed'
            elif self.mode == 'extra_package':
                self.state['unexpected'] = '1'
            elif self.mode == 'config_changed':
                (self.guest / 'etc/config/network').write_bytes(b'changed')
        elif 'add' in args and any(name.endswith('-r9.apk') for name in args):
            self.assertIn(str(self.work / 'empty-repositories'), args)
            self.state.update({role: '0.1.0-r9' for role in migration.ROLES})
        elif 'del' in args and self.mode != 'leftover':
            self.assertIn(str(self.work / 'empty-repositories'), args)
            self.state.pop('introduced', None)
        return SimpleNamespace(stdout=b'[]')

    def run_driver(self):
        return migration.run_transactions(self.apk, self.manifest, self.work, self.old, self.guest,
                                          self.work / 'signed-repositories', self.work / 'empty-repositories')

    def test_offline_exact_index_operands_preserve_provider_settings_and_complete_rollback(self):
        result = self.run_driver()
        self.assertEqual(self.state, self.before)
        self.assertEqual((self.guest / 'etc/apk/world').read_bytes(), self.world)
        self.assertEqual(result, {'preserved_dns_provider': 'dnsmasq-full', 'package_inventory_restored': True})
        self.assertTrue(any('del' in command for command in self.calls))

    def test_baseline_dns_provider_is_required_before_mutation(self):
        del self.state['dnsmasq-full']
        with self.assertRaises(ValueError):
            self.run_driver()
        self.assertEqual(len(self.calls), 1)

    def test_provider_change_unbundled_package_and_owner_file_change_refuse(self):
        for mode in ('provider_changed', 'extra_package', 'config_changed'):
            with self.subTest(mode=mode):
                self.state, self.mode = dict(self.before), mode
                with self.assertRaises(ValueError):
                    self.run_driver()

    def test_rollback_cannot_pass_with_introduced_packages_left_installed(self):
        self.mode = 'leftover'
        with self.assertRaisesRegex(ValueError, 'complete package inventory'):
            self.run_driver()
        self.assertNotEqual((self.guest / 'etc/apk/world').read_bytes(), self.world)

    def test_native_mutations_disable_scripts_without_trust_bypass(self):
        with mock.patch.object(migration.subprocess, 'run') as run:
            for operation in ('add', 'del'):
                migration.native_apk(['native-apk', '--root', str(self.guest)], {}, '--no-network', operation, 'fixture')
                args = run.call_args.args[0]
                self.assertIn('--no-scripts', args)
                self.assertNotIn('--allow-untrusted', args)
                self.assertTrue(run.call_args.kwargs['check'])

    def test_native_inventory_duplicates_and_private_diagnostics_refuse(self):
        duplicate = [{'name': 'same', 'version': '1'}, {'name': 'same', 'version': '2'}]
        with self.assertRaises(ValueError):
            migration.installed_versions(lambda *args: SimpleNamespace(stdout=json.dumps(duplicate)))
        migration.phase('offline_upgrade')
        secret = 'private-value-do-not-print'
        error = subprocess.CalledProcessError(1, [secret], stderr=('UNTRUSTED signature ' + secret).encode())
        text = migration.failure_message(error)
        self.assertIn('stage=offline_upgrade', text)
        self.assertIn('native_failure=signature', text)
        self.assertNotIn(secret, text)

    def test_offline_mirror_authenticates_index_pin_and_unsigned_payload_through_native_fetch(self):
        keys = self.work / 'keys'
        keys.mkdir()
        key_body = b'public distribution-key fixture'
        key = migration.store_distribution_key(keys, key_body)
        fingerprint = hashlib.sha256(key_body).hexdigest()
        self.assertEqual(key, keys / fingerprint)
        index = {'id': 'feed0', 'name': 'index.adb', 'key_sha256': fingerprint}
        package = {'package': 'fixture', 'version': '1-r1', 'filename': 'fixture-1-r1.apk',
                   'name': 'scoped-fixture.apk', 'index': 'feed0'}
        (self.work / index['name']).write_bytes(b'signed index fixture')
        (self.work / package['name']).write_bytes(b'unsigned payload fixture')
        manifest = {'dependency_bundle': {'indexes': [index], 'packages': [package]}}
        def native_payload(tool, architecture, row, package, index, actual_keys, work):
            self.assertEqual((actual_keys / index['key_sha256']).read_bytes(), key_body)
        bundle = SimpleNamespace(authenticate=mock.Mock(return_value=fingerprint),
                                 authenticate_apk_payload=mock.Mock(side_effect=native_payload))
        document = {'packages': [{'name': 'fixture', 'version': '1-r1', 'arch': 'aarch64_cortex-a53'}]}
        scratch = self.work / 'scratch'
        scratch.mkdir()
        with mock.patch.object(migration.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(document))):
            repositories = migration.prepare_offline_repository(self.work, manifest, scratch, self.work / 'keys',
                                                                  self.work / 'apk', bundle)
        self.assertTrue(repositories.read_text().startswith('file://'))
        self.assertEqual((scratch / 'offline-mirror/feed0/fixture-1-r1.apk').read_bytes(), b'unsigned payload fixture')
        bundle.authenticate_apk_payload.assert_called_once()
        args = bundle.authenticate_apk_payload.call_args.args
        self.assertEqual(args[2]['index'], 'feed0')
        self.assertEqual(args[3], self.work / 'scoped-fixture.apk')
        bundle.authenticate.return_value = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'signer pin'):
            migration.prepare_offline_repository(self.work, manifest, self.work / 'other-scratch', self.work / 'keys',
                                                 self.work / 'apk', bundle)


if __name__ == '__main__':
    unittest.main(verbosity=2)
