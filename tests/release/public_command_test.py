#!/usr/bin/env python3
"""Host validation boundaries for public-command acceptance; native VM is CI."""
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
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
    def test_native_opkg_fixture_partial_removal_requires_progress_and_stops_on_refusal(self):
        shell = shutil.which('sh')
        if not shell and shutil.which('git'):
            candidate = pathlib.Path(shutil.which('git')).parents[1] / 'usr/bin/sh.exe'
            shell = str(candidate) if candidate.is_file() else None
        if not shell:
            self.skipTest('POSIX shell unavailable for native fixture command regression')
        binary = self.root / 'bin'
        binary.mkdir()
        fake = binary / 'opkg'
        fake.write_bytes(b'''#!/bin/sh
case "$1" in
list-installed) while IFS= read -r name; do [ -z "$name" ] || printf '%s - 1\\n' "$name"; done < "$FIXTURE_STATE";;
remove)
 printf 'pass\\n' >> "$FIXTURE_CALLS"; shift; status=0
 for name do
  if [ "$FIXTURE_MODE" = blocked ]; then status=255; continue; fi
  if [ "$name" = luci-base ] && grep -qx luci-mod-admin-full "$FIXTURE_STATE"; then
   echo 'Package luci-base is depended upon by packages: luci-mod-admin-full'; status=255; continue
  fi
  grep -vx "$name" "$FIXTURE_STATE" > "$FIXTURE_STATE.next" || true
  mv "$FIXTURE_STATE.next" "$FIXTURE_STATE"
 done
 exit "$status";;
*) exit 99;;
esac
''')
        fake.chmod(0o755)
        state, calls = self.root / 'installed', self.root / 'calls'
        env = {**os.environ, 'PATH': str(binary) + os.pathsep + str(pathlib.Path(shell).parent) + os.pathsep + os.environ['PATH'],
               'FIXTURE_STATE': state.as_posix(), 'FIXTURE_CALLS': calls.as_posix()}
        for mode, expected_passes in (('partial', 2), ('blocked', 1)):
            with self.subTest(mode=mode):
                state.write_bytes(b'luci-base\nluci-mod-admin-full\nuhttpd\nfirewall4\n')
                calls.write_bytes(b'')
                result = subprocess.run([shell, '-c', 'set -eu; ' + public.opkg_fixture_removal()],
                                        env={**env, 'FIXTURE_MODE': mode}, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode == 0, mode == 'partial', result.stderr)
                self.assertEqual(len(calls.read_text().splitlines()), expected_passes)
                if mode == 'partial':
                    self.assertEqual(state.read_text().splitlines(), ['firewall4'])
                else:
                    self.assertIn('CSQTT_FIXTURE_NO_PROGRESS', result.stdout)

    def test_fixture_diagnostics_distinguish_transport_from_opkg_without_raw_logs(self):
        self.assertEqual(public.fixture_failure_classes('ssh: connect to host 127.0.0.1 port 1234: Connection refused', ''),
                         ['ssh_transport'])
        private = 'private-runtime-secret\n* print_dependents_warning: Package luci-base is depended upon by packages: luci-mod-admin-full'
        self.assertEqual(public.fixture_failure_classes('', private), ['fixture_opkg_dependency_refusal'])
        self.assertEqual(public.fixture_failure_classes('', 'private-runtime-secret'), ['fixture_failure_unclassified'])

    def test_ssh_readiness_requires_consecutive_read_only_success_after_disconnect(self):
        now = [0]
        responses = [subprocess.CompletedProcess([], code) for code in (255, 0, 255, 0, 0, 0)]
        remote = mock.Mock(side_effect=[subprocess.TimeoutExpired('ssh', 6), *responses])
        with mock.patch.object(public.time, 'monotonic', side_effect=lambda: now[0]), mock.patch.object(
                public.time, 'sleep', side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)):
            public.await_ssh_ready(remote)
        self.assertEqual(remote.call_count, 7)
        for call in remote.call_args_list:
            self.assertEqual(call.args, ('true',))
            self.assertFalse(call.kwargs['check'])
            self.assertLessEqual(call.kwargs['timeout'], 6)

    def test_ssh_readiness_deadline_fails_without_mutating_fixture(self):
        now = [0]
        remote = mock.Mock(return_value=subprocess.CompletedProcess([], 255))
        with mock.patch.object(public.time, 'monotonic', side_effect=lambda: now[0]), mock.patch.object(
                public.time, 'sleep', side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)):
            with self.assertRaisesRegex(ValueError, 'readiness timeout'):
                public.await_ssh_ready(remote, timeout=5)
        self.assertEqual(now[0], 5)
        self.assertEqual(remote.call_count, 3)
        for call in remote.call_args_list:
            self.assertEqual(call.args, ('true',))
            self.assertFalse(call.kwargs['check'])

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
