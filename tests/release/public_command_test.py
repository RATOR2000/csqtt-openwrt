#!/usr/bin/env python3
"""Host validation boundaries for public-command acceptance; native VM is CI."""
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('public_command', ROOT / 'scripts/test-public-command.py')
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)
TAG, SHA = 'v0.1.0-preview.10', 'a' * 40
PROFILE = 'official-25.12.6-x86-64-x86_64'
BASE = 'https://github.com/RATOR2000/csqtt-openwrt/releases/download/' + TAG + '/'
COMMAND = 'uclient-fetch -O /tmp/csqtt-install.sh ' + BASE + 'install.sh && sh /tmp/csqtt-install.sh ' + TAG


class PublicCommandTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.source, self.output = self.root / 'source', self.root / 'output'
        (self.source / 'release').mkdir(parents=True)
        self.output.mkdir()
        (self.source / 'release/csqtt-public.pem').write_bytes((ROOT / 'release/csqtt-public.pem').read_bytes())
        (self.source / 'README.md').write_text('```sh\n' + COMMAND + '\n```\n', encoding='utf-8')
        (self.source / 'install.sh').write_bytes(b'public installer fixture\n')
        self.files = {'install.sh': (self.source / 'install.sh').read_bytes(), 'catalogue.sig': b'public signature fixture'}
        packages = []
        for role in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt'):
            name = PROFILE + '--' + role + '-0.1.0-r10.apk'
            self.files[name] = b'public package fixture ' + role.encode()
            packages.append({**self.entry(name), 'role': role, 'version': '0.1.0-r10'})
        proofs = []
        for kind in ('abi', 'vm'):
            name = PROFILE + '-' + kind + '-evidence.json'
            self.files[name] = b'{}'
            proofs.append(self.entry(name))
        self.manifest = {'schema': 2, 'profile_id': PROFILE, 'upstream': 'amurcanov/csqtt@v2.1.9',
                         'platform': {'family': 'official', 'openwrt': '25.12.6', 'target': 'x86/64',
                                      'architecture': 'x86_64', 'package_manager': 'apk', 'package_format': 'apk'},
                         'backend': 'fw4-nft', 'dns_binary': '/usr/libexec/csqtt/dnsmasq', 'packages': packages,
                         'requirements': {'kernel_package': '6.12.112~fixture-r1', 'overlay_free_kib': 1,
                                          'tmp_free_kib': 1, 'mem_available_kib': 1, 'packages': []},
                         'dependency_bundle': {'packages': [], 'indexes': []},
                         'qualification': {'installation': True, 'activation': True, 'preview': True,
                                           'physical_device': False, 'source_commit': SHA,
                                           'reason': 'clean_official_firmware_vm_and_selected_abi_preview',
                                           'evidence': [p['name'] for p in proofs], 'proofs': proofs}}

    def entry(self, name):
        data = self.files[name]
        return {'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def run_bundle(self, mutate_release=None):
        manifest = PROFILE + '-manifest.json'
        signature = PROFILE + '-manifest.sig'
        self.files[manifest] = json.dumps(self.manifest).encode()
        self.files[signature] = b'public manifest signature fixture'
        self.files['catalogue.json'] = json.dumps({'schema': 2, 'upstream': 'amurcanov/csqtt@v2.1.9', 'profiles': [
            {**self.entry(manifest), 'profile_id': PROFILE, 'signature': self.entry(signature)}]}).encode()
        release = {'tag_name': TAG, 'id': 42, 'draft': False, 'published_at': '2026-10-22T12:00:00Z',
                   'assets': [{**self.entry(n), 'digest': 'sha256:' + self.entry(n)['sha256'],
                               'browser_download_url': BASE + n} for n in self.files]}
        if mutate_release:
            mutate_release(release)
        def downloaded(url, maximum=67108864):
            body = json.dumps(release).encode() if '/releases/tags/' in url else self.files[url.removeprefix(BASE)]
            if '/releases/tags/' in url:
                self.release_size, self.release_limit = len(body), maximum
            public.require(len(body) <= maximum, 'Mock HTTP response exceeds the real download bound')
            return body
        def git(args, **unused):
            return subprocess.CompletedProcess(args, 0, stdout=(TAG if 'describe' in args else SHA) + '\n')
        with mock.patch.object(public, 'download', side_effect=downloaded), \
             mock.patch.object(public, 'verify_signature'), mock.patch.object(public.subprocess, 'run', side_effect=git):
            return public.public_bundle(TAG, PROFILE, self.source, self.output)

    def test_exact_readme_tagged_command_and_selected_assets_bind(self):
        manifest, command, release = self.run_bundle()
        self.assertEqual(command, COMMAND)
        self.assertEqual(manifest['qualification']['source_commit'], release['source_commit'])
        self.assertEqual(release['installer']['sha256'], self.entry('install.sh')['sha256'])

    def test_readme_rejects_latest_http_pipes_wrong_tag_or_extra_commands(self):
        for text in (COMMAND.replace('https:', 'http:'), COMMAND.replace(TAG, 'latest'),
                     COMMAND + '; echo unexpected', COMMAND + '\necho unexpected',
                     'curl ' + BASE + 'install.sh | sh', COMMAND.replace('preview.10', 'preview.11')):
            with self.assertRaises(ValueError):
                public.readme_command('```sh\n' + text + '\n```', TAG)

    def test_source_or_publication_mismatch_refuses_before_native_acceptance(self):
        self.manifest['qualification']['source_commit'] = 'b' * 40
        with self.assertRaises(ValueError):
            self.run_bundle()
        self.manifest['qualification']['source_commit'] = SHA
        with self.assertRaises(ValueError):
            self.run_bundle(lambda r: r.update(draft=True))

    def test_changed_payload_and_installer_refuse(self):
        name = self.manifest['packages'][0]['name']
        self.files[name] = b'changed public payload'
        with self.assertRaises(ValueError):
            self.run_bundle()
        self.files[name] = b'public package fixture csqtt'
        self.files['install.sh'] = b'different from frozen source'
        with self.assertRaises(ValueError):
            self.run_bundle()

    def test_duplicate_or_foreign_asset_refuses(self):
        with self.assertRaises(ValueError):
            self.run_bundle(lambda r: r['assets'].append(copy.deepcopy(r['assets'][0])))
        with self.assertRaises(ValueError):
            self.run_bundle(lambda r: r['assets'][0].update(browser_download_url='https://attacker.example/install.sh'))

    def test_foreign_download_and_old_tag_reject_without_network(self):
        with mock.patch.object(public.urllib.request, 'urlopen') as network:
            for url in ('http://github.com/file', 'https://attacker.example/file', 'https://api.github.com/repos/other/repo/file'):
                with self.assertRaises(ValueError):
                    public.download(url)
            network.assert_not_called()
        with self.assertRaises(ValueError):
            public.public_bundle('v0.1.0-preview.9', PROFILE, self.source, self.output)

    def test_large_release_metadata_is_accepted_but_four_mib_limit_is_enforced(self):
        def many_assets(release):
            for i in range(500):
                name = f'extra-public-{i}.json'
                release['assets'].append({'name': name, 'size': 99, 'label': 'public asset metadata ' * 30,
                                          'browser_download_url': BASE + name})
        self.run_bundle(many_assets)
        self.assertGreater(self.release_size, 262144)
        self.assertEqual(self.release_limit, 4 * 1024 * 1024)
        url = 'https://api.github.com/repos/RATOR2000/csqtt-openwrt/releases/tags/' + TAG
        class Response(io.BytesIO):
            pass
        for size, accepted in ((public.RELEASE_METADATA_LIMIT, True), (public.RELEASE_METADATA_LIMIT + 1, False)):
            response = Response(b'x' * size)
            response.url = url
            with mock.patch.object(public.urllib.request, 'urlopen', return_value=response):
                if accepted:
                    self.assertEqual(len(public.download(url, public.RELEASE_METADATA_LIMIT)), size)
                else:
                    with self.assertRaises(ValueError):
                        public.download(url, public.RELEASE_METADATA_LIMIT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
