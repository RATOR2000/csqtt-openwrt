#!/usr/bin/env python3
"""Real POSIX installer/probe with disposable package/crypto command doubles."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from installer_test import NODE, REPO, SH, posix


def artifact(path, **fields):
    return {**fields, 'name': path.name, 'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@unittest.skipUnless(SH and NODE, 'POSIX sh and Node required')
class PortableTest(unittest.TestCase):
    def run_case(self, pm='opkg', scenario='success', upgrade=False, check=False):
        workspace = REPO / '.work/portable-tests'
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='case-', dir=workspace) as directory:
            base = pathlib.Path(directory)
            root, bindir = base / 'router', base / 'bin'
            for name in ['etc/config','etc/apk/keys','lib/apk/db','usr/lib/opkg/info','etc/opkg/keys','tmp/sysinfo','var/lock','overlay','release','proc']:
                (root/name).mkdir(parents=True, exist_ok=True)
            bindir.mkdir()
            (root/'.portable-fixture').touch()
            (root/'etc/openwrt_release').write_text("DISTRIB_ID='OpenWrt'\nDISTRIB_RELEASE='24.10.8'\nDISTRIB_TARGET='x86/64'\nDISTRIB_ARCH='x86_64'\n")
            (root/'etc/os-release').write_text('ID=openwrt\n')
            (root/'tmp/sysinfo/board_name').write_text('pc,generic\n')
            (root/'etc/apk/arch').write_text('x86_64\n')
            (root/'etc/opkg/arch.conf').write_text('arch all 1\narch x86_64 10\n')
            (root/'etc/opkg.conf').write_text('dest root /\n')
            (root/'proc/meminfo').write_text('MemTotal: 262144 kB\nMemAvailable: 180000 kB\n')
            (root/'proc/cpuinfo').write_text('processor : 0\nprocessor : 1\n')
            for name in ['csqtt','dhcp','firewall','network']:
                (root/'etc/config'/name).write_text('private fixture '+name+'\n')
            db = {'kernel':'6.6.123-1-abi','kmod-tun':'6.6.123-1','ip-full':'1','jsonfilter':'1','conntrack':'1','ca-bundle':'1'}
            if upgrade: db.update({name:'0.0.9-r1' for name in ['csqtt','csqtt-captcha','luci-app-csqtt']})
            before = db.copy()
            (root/'lib/apk/db/installed').write_text(json.dumps(db))
            (root/'etc/apk/world').write_text('\n'.join(db)+'\n')
            (root/'usr/lib/opkg/fixture.json').write_text(json.dumps(db))
            (root/'usr/lib/opkg/status').write_text('\n'.join(f'Package: {n}\nVersion: {v}\nStatus: install ok installed\n' for n,v in db.items()))
            profile='official-24.10.8-x86-64-x86_64'
            def bundle(dest, version):
                dest.mkdir(parents=True, exist_ok=True)
                fmt='apk' if pm=='apk' else 'ipk'
                manifest={'schema':2,'profile_id':profile,'upstream':'amurcanov/csqtt@v2.1.9',
                  'platform':{'family':'official','openwrt':'24.10.8','target':'x86/64','architecture':'x86_64','package_manager':pm,'package_format':fmt},
                  'backend':'fw4-nft','dns_binary':'/usr/libexec/csqtt/dnsmasq',
                  'qualification':{'installation':True,'activation':True,'evidence':['fixture-only']},
                  'requirements':{'kernel_package':'6.6.123-1-abi','overlay_free_kib':100,'tmp_free_kib':100,'mem_available_kib':100,'packages':['kmod-tun','ip-full']},
                  'dependency_bundle':{'indexes':[],'packages':[]},'packages':[]}
                for role in ['csqtt','csqtt-captcha','luci-app-csqtt']:
                    file=dest/f'{profile}--{role}-{version}.{fmt}'
                    file.write_text(json.dumps({'package':role,'version':version}))
                    manifest['packages'].append(artifact(file,role=role,version=version))
                return manifest
            release=root/'release'
            manifest=bundle(release,'0.1.0-r1')
            if scenario=='unqualified': manifest['qualification']['activation']=False
            if scenario=='kernel': manifest['requirements']['kernel_package']='other-kernel'
            if scenario=='tuple': manifest['platform']['target']='other/target'
            if scenario=='duplicate_role': manifest['packages'][1]['role']='csqtt'
            if scenario=='path': manifest['packages'][0]['name']='../outside.ipk'
            if scenario=='missing_required': manifest['requirements']['packages'].append('missing-package')
            if scenario=='checksum': manifest['packages'][0]['sha256']='0'*64
            mfile=release/f'{profile}-manifest.json'; mfile.write_text(json.dumps(manifest))
            sig=release/f'{profile}-manifest.sig'; sig.write_bytes(b'fixture signature')
            catalogue={'schema':2,'upstream':'amurcanov/csqtt@v2.1.9','profiles':[{**artifact(mfile),'profile_id':profile,'signature':artifact(sig)}]}
            if scenario=='ambiguous': catalogue['profiles'].append(catalogue['profiles'][0])
            (release/'catalogue.json').write_text(json.dumps(catalogue))
            (release/'catalogue.sig').write_bytes(b'fixture catalogue signature')
            if upgrade:
                previous=root/'etc/csqtt/releases/current'
                old=bundle(previous/'assets','0.0.9-r1')
                (previous/'manifest.json').write_text(json.dumps(old))
                (previous/'manifest.sig').write_bytes(b'fixture previous signature')
                (previous/'repositories').write_text('')
                if scenario=='rollback_missing': next((previous/'assets').iterdir()).unlink()
            if scenario=='release_code':
                (root/'etc/openwrt_release').write_text("DISTRIB_ID='OpenWrt'\nDISTRIB_RELEASE='$(touch /tmp/executed)'\nDISTRIB_TARGET='x86/64'\nDISTRIB_ARCH='x86_64'\n")
            wrapper='#!/bin/sh\n"'+posix(NODE)+'" "'+posix(REPO/'tests/installer/portable_fake.cjs')+'" "COMMAND" "$@"\n'
            commands=['id','uname','df','jsonfilter','openssl','uclient-fetch','sha256sum','dnsmasq',pm,'fw4','nft','ucode','procd','netifd','tar','usign']
            for command in commands:
                (bindir/command).write_text(wrapper.replace('COMMAND',command),newline='\n')
                (bindir/command).chmod(0o755)
            for command in ['cat','awk','wc','mktemp','mkdir','rmdir','cp','date','rm','tr','chmod','mv']:
                (bindir/command).write_text('#!/bin/sh\nexec /usr/bin/'+command+' "$@"\n',newline='\n')
                (bindir/command).chmod(0o755)
            for service in ['rpcd','csqtt','csqtt-captcha','csqtt-health']:
                file=root/'etc/init.d'/service;file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(wrapper.replace('COMMAND','service:'+service),newline='\n');file.chmod(0o755)
            source=(REPO/'install.sh').read_text().replace('/usr/libexec/csqtt/dnsmasq','CSQTT_FIXTURE_DNS_LITERAL')
            for prefix in ['/etc/','/lib/apk/','/usr/lib/opkg/','/usr/libexec/','/tmp/','/var/','/overlay','/proc/meminfo','/proc/cpuinfo']:
                source=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(prefix),posix(root)+prefix,source)
            source=source.replace('CSQTT_FIXTURE_DNS_LITERAL','/usr/libexec/csqtt/dnsmasq')
            script=base/'install.sh';script.write_text(source,newline='\n')
            env={**os.environ,'CSQTT_FAKE_ROOT':str(root),'CSQTT_FAKE_SCENARIO':scenario,'CSQTT_WRAPPER_PATH':posix(bindir),'CSQTT_WRAPPER_SCRIPT':posix(script),'MSYS2_ENV_CONV_EXCL':'APK_CONFIG'}
            arg='--check' if check else '--portable fixture'
            result=subprocess.run([SH,'-c','PATH="$CSQTT_WRAPPER_PATH"; export PATH; exec /usr/bin/sh "$CSQTT_WRAPPER_SCRIPT" '+arg],env=env,capture_output=True,text=True,timeout=100)
            calls=[json.loads(line) for line in (root/'commands.jsonl').read_text().splitlines()] if (root/'commands.jsonl').exists() else []
            dbpath=root/('lib/apk/db/installed' if pm=='apk' else 'usr/lib/opkg/fixture.json')
            after=json.loads(dbpath.read_text())
            return result,calls,before,after,(root/'tmp/executed').exists(),(root/'etc/config/csqtt').read_text()

    def test_probe_is_read_only_and_does_not_evaluate_release(self):
        for pm in ['apk','opkg']:
            result,calls,_,_,executed,_=self.run_case(pm,'release_code',check=True)
            self.assertEqual(result.returncode,0,result.stderr)
            probe=json.loads(result.stdout)
            self.assertEqual(probe['openwrt'],'')
            self.assertFalse(executed)
            self.assertFalse(any(c['command']=='opkg' or c['command']=='uclient-fetch' for c in calls))

    def test_install_both_package_backends(self):
        for pm in ['apk','opkg']:
            result,calls,_,after,_,config=self.run_case(pm)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(after['csqtt'],'0.1.0-r1')
            self.assertEqual(config,'private fixture csqtt\n')
            self.assertTrue(any('--root' in c['args'] or '--offline-root' in c['args'] for c in calls))

    def test_failures_are_before_live_mutation(self):
        for scenario in ['catalogue_signature','manifest_signature','unqualified','tuple','kernel','path','checksum','duplicate_role','ambiguous','missing_required','space','dependency','wrong_installed_version','unrelated_change']:
            with self.subTest(scenario=scenario):
                result,calls,before,after,_,_=self.run_case('opkg',scenario)
                self.assertNotEqual(result.returncode,0,scenario)
                self.assertEqual(before,after,result.stderr)
                self.assertFalse(any(c['command']=='opkg' and 'install' in c['args'] and '--offline-root' not in c['args'] for c in calls))

    def test_partial_install_and_service_failure_roll_back(self):
        for pm in ['apk','opkg']:
            for upgrade in [False,True]:
                for scenario in ['install_failure','service_failure']:
                    with self.subTest(pm=pm,upgrade=upgrade,scenario=scenario):
                        result,calls,before,after,_,config=self.run_case(pm,scenario,upgrade)
                        self.assertNotEqual(result.returncode,0)
                        self.assertTrue(any(c['command']==pm and ('install' in c['args'] or 'add' in c['args']) and '--root' not in c['args'] and '--offline-root' not in c['args'] for c in calls),result.stderr)
                        self.assertEqual(after,before,result.stdout+result.stderr)
                        self.assertEqual(config,'private fixture csqtt\n')

    def test_missing_previous_bundle_refuses_upgrade(self):
        result,_,before,after,_,_=self.run_case('opkg','rollback_missing',True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,after)


if __name__=='__main__': unittest.main(verbosity=2)
