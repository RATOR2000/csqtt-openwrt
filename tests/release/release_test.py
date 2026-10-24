#!/usr/bin/env python3
"""Exercise the manifest producer and workflow verifier across real files."""
import json
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

from signing_test import PortableSigningTest

REPO = pathlib.Path(__file__).resolve().parents[2]


class ReleaseTest(unittest.TestCase):
    def test_vm_scope_cannot_hide_expanded_disk_or_claim_physical_storage(self):
        sys.path.insert(0, str(REPO / 'scripts'))
        spec = importlib.util.spec_from_file_location('release_evidence', REPO / 'scripts/release-evidence.py')
        evidence = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evidence)
        disk = {'original_root_bytes': 104 * 1024 * 1024, 'test_root_bytes': 1073741824,
                'disk_expanded': True, 'physical_device': False}
        evidence.validate_vm_test_disk(disk)
        for change in ({'physical_device': True}, {'disk_expanded': False},
                       {'original_root_bytes': 1073741824}, {'original_root_bytes': 0},
                       {'test_root_bytes': 104 * 1024 * 1024}, {'test_root_bytes': True}):
            with self.assertRaises(ValueError):
                evidence.validate_vm_test_disk({**disk, **change})
        with self.assertRaises(ValueError):
            evidence.validate_vm_test_disk(None)

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

    def test_additional_modules_keep_exact_abi_through_apk_and_ipk_manifest_production(self):
        sys.path.insert(0, str(REPO / 'scripts'))
        from release_schema import describe, validate
        abi = '6.12.112~abcd-r1'
        for fmt in ('apk', 'ipk'):
            with self.subTest(format=fmt):
                case = self.root / fmt
                case.mkdir()
                profile, registry = self.portable_registry(fmt)
                for role in ('csqtt', 'csqtt-captcha', 'luci-app-csqtt'):
                    name = role + ('-0.1.0-r1.apk' if fmt == 'apk' else '_0.1.0-r1_x86_64.ipk')
                    (case / name).write_bytes(b'public project package fixture')
                index = case / (profile['id'] + '--feed1.' + ('adb' if fmt == 'apk' else 'Packages'))
                index.write_bytes(b'public signed-index fixture; no native signature proof')
                entry = describe(index, id='feed1', format='apk-adb' if fmt == 'apk' else 'opkg',
                                 repository='https://downloads.openwrt.org/releases/24.10.8/targets/x86/64/kmods/6.6.123-abcd-1',
                                 key_sha256='a' * 64)
                if fmt == 'ipk':
                    signature = index.with_suffix('.sig')
                    signature.write_bytes(b'public signature fixture; not a real signature')
                    entry['signature'] = describe(signature)
                modules = []
                for name in ('kmod-tun', 'kmod-nf-conntrack-netlink'):
                    filename = name + ('-1-r1.apk' if fmt == 'apk' else '_1-r1_x86_64.ipk')
                    package = case / (profile['id'] + '--dep--' + filename)
                    package.write_bytes(b'public module payload fixture')
                    modules.append(describe(package, package=name, version='1-r1', filename=filename,
                                            index='feed1', kernel_package=abi))
                dependencies = case / 'dependencies.json'
                dependencies.write_text(json.dumps({'indexes': [entry], 'packages': modules,
                    'requirements': {'kernel_package': abi, 'packages': ['kernel', 'kmod-tun', 'kmod-nf-conntrack-netlink']}}))
                result = subprocess.run([sys.executable, str(REPO / 'scripts/release-manifest.py'), str(case),
                                         '--profile', profile['id'], '--registry', str(registry),
                                         '--dependencies', str(dependencies)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = json.loads((case / 'manifest.json').read_text())
                validate(manifest, case)
                self.assertEqual([dep['kernel_package'] for dep in manifest['dependency_bundle']['packages']], [abi, abi])
                for index in range(2):
                    for changed in (None, '6.12.112~different-r1'):
                        invalid = json.loads(json.dumps(manifest))
                        dep = invalid['dependency_bundle']['packages'][index]
                        if changed is None:
                            dep.pop('kernel_package')
                        else:
                            dep['kernel_package'] = changed
                        with self.assertRaises(ValueError):
                            validate(invalid, case)
                for protected in ('kernel', 'procd', 'netifd', 'dnsmasq-full', 'firewall4'):
                    invalid = json.loads(json.dumps(manifest))
                    invalid['dependency_bundle']['packages'][1]['package'] = protected
                    with self.assertRaises(ValueError):
                        validate(invalid, case)

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
