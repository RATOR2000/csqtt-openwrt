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
import time
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
            release_version='25.12.6' if pm=='apk' else '24.10.8'
            target,arch='x86/64','x86_64'
            if scenario.startswith('migration'): release_version,target,arch='25.12.5','mediatek/filogic','aarch64_cortex-a53'
            (root/'etc/openwrt_release').write_text(f"DISTRIB_ID='OpenWrt'\nDISTRIB_RELEASE='{release_version}'\nDISTRIB_TARGET='{target}'\nDISTRIB_ARCH='{arch}'\n")
            (root/'etc/os-release').write_text('ID=openwrt\n')
            (root/'tmp/sysinfo/board_name').write_text('pc,generic\n')
            (root/'etc/apk/arch').write_text(arch+'\n')
            (root/'etc/opkg/arch.conf').write_text(f'arch all 1\narch {arch} 10\n')
            (root/'etc/opkg.conf').write_text('dest root /\n')
            (root/'etc/opkg/distfeeds.conf').write_text(f'src/gz base https://downloads.openwrt.org/releases/{release_version}/packages/x86_64/base\n')
            (root/'etc/apk/repositories').write_text(f'https://downloads.openwrt.org/releases/{release_version}/packages/x86_64/base/packages.adb\n')
            distrokey=root/('etc/apk/keys/openwrt.pem' if pm=='apk' else 'etc/opkg/keys/openwrt.pub')
            distrokey.write_text('public distribution fixture key\n')
            (root/'proc/meminfo').write_text('MemTotal: 262144 kB\nMemAvailable: 180000 kB\n')
            (root/'proc/cpuinfo').write_text('processor : 0\nprocessor : 1\n')
            for name in ['csqtt','dhcp','firewall','network']:
                (root/'etc/config'/name).write_text('private fixture '+name+'\n')
            db = {'kernel':'6.6.123-1-abi','kmod-tun':'6.6.123-1','ip-full':'1','jsonfilter':'1','conntrack':'1','ca-bundle':'1'}
            if upgrade: db.update({name:'0.0.9-r1' for name in ['csqtt','csqtt-captcha','luci-app-csqtt']})
            if scenario.startswith('migration'): db.update({name:'0.1.0-r9' for name in ['csqtt','csqtt-captcha','luci-app-csqtt']})
            if scenario.startswith('bootstrap'): db.pop('jsonfilter')
            if scenario.startswith('tun'): db.pop('kmod-tun')
            before = db.copy()
            (root/'lib/apk/db/installed').write_text(json.dumps(db))
            (root/'etc/apk/world').write_text('\n'.join(db)+'\n')
            (root/'usr/lib/opkg/fixture.json').write_text(json.dumps(db))
            (root/'usr/lib/opkg/status').write_text('\n'.join(f'Package: {n}\nVersion: {v}\nStatus: install ok installed\n' for n,v in db.items()))
            profile=f'official-{release_version}-{target.replace("/","-")}-{arch}'
            def bundle(dest, version):
                dest.mkdir(parents=True, exist_ok=True)
                fmt='apk' if pm=='apk' else 'ipk'
                manifest={'schema':2,'profile_id':profile,'upstream':'amurcanov/csqtt@v2.1.9',
                  'platform':{'family':'official','openwrt':release_version,'target':target,'architecture':arch,'package_manager':pm,'package_format':fmt},
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
            if scenario.startswith('dep_') or scenario.startswith('tun'):
                dep='kmod-tun' if scenario.startswith('tun') else 'liblucihttp0'
                if scenario=='dep_upgrade': dep='ip-full'
                if scenario=='dep_protected': dep='firewall4'
                version='1' if dep!='ip-full' else 'unexpected-upgrade'
                file=release/f'{profile}--dependency-{dep}.{ "apk" if pm=="apk" else "ipk" }'
                file.write_text(json.dumps({'package':dep,'version':version}))
                entry=artifact(file,package=dep,version=version,index='base',filename=f'{dep}_{version}.{"apk" if pm=="apk" else "ipk"}')
                if dep=='kmod-tun': entry['kernel_package']='other-kernel' if scenario=='tun_kernel' else db['kernel']
                manifest['dependency_bundle']['packages']=[entry]
                manifest['requirements']['packages'].append(dep)
                index=release/f'{profile}--base-index'
                index.write_text(f'Package: {dep}\nVersion: {version}\nArchitecture: x86_64\nFilename: {entry["filename"]}\nSHA256sum: {entry["sha256"]}\nSize: {entry["size"]}\n\n')
                ix=artifact(index,id='base',repository=f'https://downloads.openwrt.org/releases/{release_version}/packages/x86_64/base',format='apk-adb' if pm=='apk' else 'opkg',key_sha256=hashlib.sha256(distrokey.read_bytes()).hexdigest())
                if scenario=='dep_foreign': ix['repository']='https://untrusted.example/feed'
                if scenario=='dep_release': ix['repository']='https://downloads.openwrt.org/releases/other/packages'
                if scenario=='dep_key': ix['key_sha256']='0'*64
                if scenario=='dep_binding':
                    index.write_text(index.read_text().replace(entry['sha256'],'0'*64)); ix.update(artifact(index))
                if pm=='opkg':
                    isig=release/f'{profile}--base-index.sig'; isig.write_text('fixture signature')
                    ix['signature']=artifact(isig)
                manifest['dependency_bundle']['indexes']=[ix]
            mfile=release/f'{profile}-manifest.json'; mfile.write_text(json.dumps(manifest))
            sig=release/f'{profile}-manifest.sig'; sig.write_bytes(b'fixture signature')
            catalogue={'schema':2,'upstream':'amurcanov/csqtt@v2.1.9','profiles':[{**artifact(mfile),'profile_id':profile,'signature':artifact(sig)}]}
            if scenario=='ambiguous': catalogue['profiles'].append(catalogue['profiles'][0])
            (release/'catalogue.json').write_text(json.dumps(catalogue))
            (release/'catalogue.sig').write_bytes(b'fixture catalogue signature')
            if scenario.startswith('migration'):
                old={'schema':1,'openwrt':release_version,'target':target,'architecture':arch,'upstream':'amurcanov/csqtt@v2.1.9','packages':[]}
                for role in ['csqtt','csqtt-captcha','luci-app-csqtt']:
                    oldfile=release/f'{role}-0.1.0-r9.apk'; oldfile.write_text(json.dumps({'package':role,'version':'0.1.0-r9'}))
                    old['packages'].append(artifact(oldfile))
                if scenario=='migration_bad_manifest': old['packages'][0]['name']='csqtt-0.1.0-r8.apk'
                if scenario=='migration_corrupt': old['packages'][0]['sha256']='0'*64
                (release/'manifest.json').write_text(json.dumps(old))
                (release/'manifest.sig').write_bytes(b'fixture old signature')
            if upgrade:
                previous=root/'etc/csqtt/releases/current'
                old=bundle(previous/'assets','0.0.9-r1')
                (previous/'manifest.json').write_text(json.dumps(old))
                (previous/'manifest.sig').write_bytes(b'fixture previous signature')
                (previous/'repositories').write_text('')
                if scenario=='rollback_missing': next((previous/'assets').iterdir()).unlink()
            if scenario=='release_code':
                (root/'etc/openwrt_release').write_text("DISTRIB_ID='OpenWrt'\nDISTRIB_RELEASE='$(touch /tmp/executed)'\nDISTRIB_TARGET='x86/64'\nDISTRIB_ARCH='x86_64'\n")
            wrapper='#!/bin/sh\n"'+posix(NODE)+'" "'+posix(REPO/'tests/installer/portable_fake.cjs')+'" "COMMAND" "$@"\nstatus=$?\n[ "$status" != 77 ] || kill -KILL "$PPID"\nexit "$status"\n'
            commands=['id','uname','df','jsonfilter','openssl','uclient-fetch','sha256sum','dnsmasq',pm,'fw4','nft','ucode','procd','netifd','tar','usign','uci','ip','chmod','sync','du']
            for command in commands:
                if scenario.startswith('bootstrap') and command in ['openssl','jsonfilter']:
                    (root/(command+'-wrapper')).write_text(wrapper.replace('COMMAND',command),newline='\n')
                    (root/(command+'-wrapper')).chmod(0o755)
                    continue
                (bindir/command).write_text(wrapper.replace('COMMAND',command),newline='\n')
                (bindir/command).chmod(0o755)
            for command in ['cat','awk','wc','mktemp','mkdir','rmdir','cp','date','rm','tr','mv','sed','cut']:
                (bindir/command).write_text('#!/bin/sh\nexec /usr/bin/'+command+' "$@"\n',newline='\n')
                (bindir/command).chmod(0o755)
            (bindir/'sleep').write_text('#!/bin/sh\n"'+posix(NODE)+'" -e "Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100)"\n',newline='\n')
            (bindir/'sleep').chmod(0o755)
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
            invocation=[SH,'-c','PATH="$CSQTT_WRAPPER_PATH"; export PATH; exec /usr/bin/sh "$CSQTT_WRAPPER_SCRIPT" '+arg]
            if scenario=='operation_lock':
                running=subprocess.Popen(invocation,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                deadline=time.monotonic()+80
                while not (root/'transaction-held').exists() and running.poll() is None and time.monotonic()<deadline: time.sleep(.05)
                self.assertTrue((root/'transaction-held').exists(),'Installer must reach the live transaction')
                lifecycle=(REPO/'openwrt/csqtt/files/lifecycle.sh').read_text().replace('/var/',posix(root)+'/var/')
                competitor=base/'stop.sh';competitor.write_text(lifecycle+'\ncsqtt_operation_enter || exit 1\nprintf admitted > "'+posix(root)+'/stop-admitted"\n',newline='\n')
                stopping=subprocess.Popen([SH,'-c','PATH="$CSQTT_WRAPPER_PATH"; export PATH; exec /usr/bin/sh "'+posix(competitor)+'"'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                stdout,stderr=running.communicate(timeout=100)
                result=subprocess.CompletedProcess(invocation,running.returncode,stdout,stderr)
                _,stop_error=stopping.communicate(timeout=30)
                self.assertEqual(stopping.returncode,0,stop_error)
                self.assertTrue((root/'stop-admitted').exists(),'Stop must be admitted after installer cleanup')
            else:
                result=subprocess.run(invocation,env=env,capture_output=True,text=True,timeout=100)
            if scenario in ['powerloss','bootstrap_powerloss','bootstrap_powerloss_main']:
                self.assertNotEqual(result.returncode,0,'First install must be interrupted without a cleanup trap')
                journal=root/('etc/csqtt/installer-bootstrap' if scenario=='bootstrap_powerloss' else 'etc/csqtt/installer-transaction')
                self.assertTrue(journal.exists(),'Power loss must leave a persistent journal')
                if scenario!='bootstrap_powerloss': self.assertEqual((journal/'phase').read_text().strip(),'installing')
                result=subprocess.run([SH,'-c','PATH="$CSQTT_WRAPPER_PATH"; export PATH; exec /usr/bin/sh "$CSQTT_WRAPPER_SCRIPT" '+arg],env=env,capture_output=True,text=True,timeout=100)
            if os.environ.get('CSQTT_INSTALLER_DEBUG') and result.returncode:
                for debug in (root/'tmp').glob('csqtt-portable.*/packages-*'):
                    print(debug.name, debug.read_text())
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
            self.assertIn('http://192.168.73.1/cgi-bin/luci/admin/services/csqtt',result.stdout)

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

    def test_upgrade_preserves_stopped_transport(self):
        result,calls,_,after,_,config=self.run_case('apk','stopped_upgrade',True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(after['csqtt'],'0.1.0-r1')
        self.assertEqual(config,'private fixture csqtt\n')
        self.assertFalse(any(c['command']=='service:csqtt' and c['args']==['restart'] for c in calls))

    def test_fresh_nonstandard_lan_url(self):
        result,calls,_,_,_,_=self.run_case('apk','nonstandard_lan')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('http://192.168.73.1/cgi-bin/luci/admin/services/csqtt',result.stdout)
        self.assertTrue(any(c['command']=='ip' and 'br-trusted' in c['args'] for c in calls))
        self.assertFalse(any(c['command']=='uci' and any(x in c['args'] for x in ['set','commit','import']) for c in calls))

    def test_install_holds_lifecycle_and_exports_owner_to_children(self):
        result,_,_,after,_,_=self.run_case('apk','operation_lock')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(after['csqtt'],'0.1.0-r1')

    def test_distribution_dependency_and_exact_kernel_tun(self):
        for pm in ['opkg','apk']:
            for scenario in ['dep_success','tun_success','dep_upgrade']:
                with self.subTest(pm=pm,scenario=scenario):
                    result,_,_,after,_,_=self.run_case(pm,scenario)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    if scenario=='dep_upgrade': self.assertEqual(after['ip-full'],'1','Compatible installed dependency must never be upgraded')
                    else: self.assertIn('kmod-tun' if scenario.startswith('tun') else 'liblucihttp0',after)

    def test_distribution_dependency_rejections_precede_live_mutation(self):
        for scenario in ['dep_foreign','dep_release','dep_key','dep_binding','dep_solver_upgrade','dep_protected','dep_signature','tun_kernel']:
            with self.subTest(scenario=scenario):
                result,calls,before,after,_,_=self.run_case('opkg',scenario)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(before,after,result.stdout+result.stderr)
                self.assertFalse(any(c['command']=='opkg' and 'install' in c['args'] and '--offline-root' not in c['args'] for c in calls))

    def test_signed_bootstrap_and_powerloss_resume(self):
        for pm in ['opkg','apk']:
            for scenario in ['bootstrap_success','bootstrap_powerloss','bootstrap_powerloss_main','powerloss']:
                with self.subTest(pm=pm,scenario=scenario):
                    result,_,_,after,_,_=self.run_case(pm,scenario)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertEqual(after['csqtt'],'0.1.0-r1')
                    if scenario.startswith('bootstrap'): self.assertIn('openssl-util',after)

    def test_bootstrap_signature_or_upgrade_never_changes_live_packages(self):
        for pm in ['opkg','apk']:
            for scenario in ['bootstrap_signature','bootstrap_upgrade','bootstrap_bad_project_signature','bootstrap_orphan']:
                with self.subTest(pm=pm,scenario=scenario):
                    result,_,before,after,_,_=self.run_case(pm,scenario)
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual(before,after,result.stdout+result.stderr)

    def test_immutable_schema1_r9_migration(self):
        result,calls,_,after,_,config=self.run_case('apk','migration_success')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(after['csqtt'],'0.1.0-r1')
        self.assertEqual(config,'private fixture csqtt\n')
        self.assertTrue(any(c['command']=='uclient-fetch' and '/v0.1.0-preview.9/' in c['args'][-1] for c in calls))
        self.assertTrue(any(c['command']=='apk' and '--root' in c['args'] and any('csqtt-0.1.0-r9.apk' in a for a in c['args']) for c in calls))
        for scenario in ['migration_bad_manifest','migration_corrupt']:
            result,_,before,after,_,_=self.run_case('apk',scenario)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,after,result.stdout+result.stderr)


if __name__=='__main__': unittest.main(verbosity=2)
