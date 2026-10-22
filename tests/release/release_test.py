#!/usr/bin/env python3
"""Exercise the manifest producer and workflow verifier across real files."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='csqtt-manifest-')
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        for role in ['csqtt', 'csqtt-captcha', 'luci-app-csqtt']:
            (self.root / f'{role}-0.1.0-r1.apk').write_bytes(b'fixture package bytes')
        self.assertEqual(self.command('release-manifest.py').returncode, 0)

    def command(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / 'scripts' / script), str(self.root), *map(str,args)],
                              capture_output=True, text=True)

    def change_manifest(self, change):
        path = self.root / 'manifest.json'
        manifest = json.loads(path.read_text())
        change(manifest)
        path.write_text(json.dumps(manifest))

    def test_produced_manifest_and_exact_artifacts(self):
        result = self.command('verify-release.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len((self.root / 'SHA256SUMS').read_text().splitlines()), 4)

    def test_modified_package_is_rejected(self):
        (self.root / 'csqtt-0.1.0-r1.apk').write_bytes(b'changed package bytes')
        self.assertNotEqual(self.command('verify-release.py').returncode, 0)

    def test_extra_package_is_rejected_by_both_commands(self):
        (self.root / 'extra-1.apk').write_bytes(b'extra fixture')
        self.assertNotEqual(self.command('verify-release.py').returncode, 0)
        self.assertNotEqual(self.command('release-manifest.py').returncode, 0)

    def test_wrong_target_duplicate_role_and_path_escape(self):
        for change in [lambda m: m.update(target='other/target'),
                       lambda m: m['packages'][0].update(name=m['packages'][1]['name']),
                       lambda m: m['packages'][0].update(name='../outside.apk')]:
            self.assertEqual(self.command('release-manifest.py').returncode, 0)
            self.change_manifest(change)
            self.assertNotEqual(self.command('verify-release.py').returncode, 0)

    def portable_registry(self, fmt='apk', **changes):
        profile={'id':'official-24.10.8-x86-64-x86_64','family':'official','openwrt':'24.10.8','target':'x86/64',
                 'architecture':'x86_64','package_manager':'apk' if fmt=='apk' else 'opkg','package_format':fmt,
                 'backend':'fw4-nft','qualification':{'installation':False,'activation':False,'reason':'unverified'}}
        profile.update(changes)
        path=self.root/'registry.json'
        path.write_text(json.dumps({'schema':1,'profiles':[profile]}))
        return profile,path

    def test_portable_apk_and_ipk_exact_tuple_assets(self):
        profile,registry=self.portable_registry()
        result=self.command('release-manifest.py','--profile',profile['id'],'--registry',registry)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.command('verify-release.py').returncode,0)
        manifest=json.loads((self.root/'manifest.json').read_text())
        self.assertEqual(manifest['schema'],2)
        self.assertFalse(manifest['qualification']['activation'])
        self.assertTrue(all(p['name'].startswith(profile['id']+'--') for p in manifest['packages']))
        for file in self.root.glob('*.apk'): file.unlink()
        for role in ['csqtt','csqtt-captcha','luci-app-csqtt']:
            (self.root/f'{role}_0.1.0-r2_x86_64.ipk').write_bytes(b'ipk fixture')
        profile,registry=self.portable_registry('ipk')
        result=self.command('release-manifest.py','--profile',profile['id'],'--registry',registry)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.command('verify-release.py').returncode,0)

    def test_qualification_cannot_be_invented_without_evidence_and_kernel(self):
        profile,registry=self.portable_registry(qualification={'installation':True,'activation':True})
        self.assertNotEqual(self.command('release-manifest.py','--profile',profile['id'],'--registry',registry).returncode,0)
        profile,registry=self.portable_registry(qualification={'installation':True,'activation':True,'evidence':['fixture']})
        self.assertNotEqual(self.command('release-manifest.py','--profile',profile['id'],'--registry',registry).returncode,0)

    def test_duplicate_json_keys_are_rejected(self):
        path=self.root/'manifest.json'
        path.write_text(path.read_text().replace('"schema": 1','"schema": 1, "schema": 1'))
        self.assertNotEqual(self.command('verify-release.py').returncode,0)

    def test_catalogue_requires_unique_scoped_manifests_and_signature_assets(self):
        profile,registry=self.portable_registry()
        self.assertEqual(self.command('release-manifest.py','--profile',profile['id'],'--registry',registry).returncode,0)
        manifest=self.root/(profile['id']+'-manifest.json')
        self.assertNotEqual(self.command('release-catalogue.py',manifest).returncode,0)
        manifest.with_suffix('.sig').write_bytes(b'fixture detached signature')
        self.assertEqual(self.command('release-catalogue.py',manifest).returncode,0)
        catalogue=json.loads((self.root/'catalogue.json').read_text())
        self.assertEqual(catalogue['profiles'][0]['profile_id'],profile['id'])
        self.assertNotEqual(self.command('release-catalogue.py',manifest,manifest).returncode,0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
