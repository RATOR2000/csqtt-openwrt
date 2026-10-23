/* Command doubles only: native crypto, solvers and package scripts remain gates. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const [command, ...args] = process.argv.slice(2);
const root = process.env.CSQTT_FAKE_ROOT;
const scenario = process.env.CSQTT_FAKE_SCENARIO;
if (!root || !fs.existsSync(path.join(root, '.portable-fixture'))) throw Error('Missing disposable fixture');
const out = value => process.stdout.write(String(value) + '\n');
const fail = message => { console.error(message); process.exit(1); };
const opt = key => args.includes(key) ? args[args.indexOf(key) + 1] : undefined;
const native = value => process.platform === 'win32' && /^\/[a-z]\//i.test(value) ? value[1] + ':' + value.slice(2) : value;
fs.appendFileSync(path.join(root, 'commands.jsonl'), JSON.stringify({command, args}) + '\n');
if (command === 'id') out(0);
else if (command === 'uname') out('6.6.123');
else if (command === 'df') out('Filesystem 1024-blocks Used Available Capacity Mounted on\nfixture 1000000 1000 ' + (scenario === 'space' ? 1 : 999000) + ' 1% /overlay');
else if (command === 'du') out('100\tfixture');
else if (command === 'uci') {
  const key=args.at(-1);
  if(key==='csqtt.main.enabled') out(scenario==='stopped_upgrade'?'0':'1');
  else if(key==='csqtt.main.lan_device') { if(scenario!=='nonstandard_lan') out('br-lan'); }
  else if(key==='network.lan.device' && scenario==='nonstandard_lan') out('br-trusted');
  else if(key==='uhttpd.main.listen_http') out('0.0.0.0:80');
} else if (command === 'ip') {
  const device=opt('dev'),lan=scenario==='nonstandard_lan'?'br-trusted':'br-lan';
  if(device===lan) out(`3: ${lan}    inet 192.168.73.1/24 brd 192.168.73.255 scope global ${lan}`);
}
else if (command === 'jsonfilter') {
  let values = [JSON.parse(fs.readFileSync(opt('-i') || 0, 'utf8'))];
  const tokens = [...opt('-e').matchAll(/\.([A-Za-z0-9_-]+)|\[(\*|\d+)\]/g)].map(m => m[1] ?? m[2]);
  for (const token of tokens) values = values.flatMap(item => token === '*' ? Array.isArray(item) ? item : [] : item?.[token] === undefined ? [] : [item[token]]);
  for (const value of values) out(typeof value === 'object' ? JSON.stringify(value) : value);
} else if (command === 'uclient-fetch') {
  const name = args.at(-1).split('/').at(-1);
  const file = path.join(root, 'release', name);
  if (!fs.existsSync(file)) fail('Missing release fixture');
  fs.copyFileSync(file, opt('-O'));
} else if (command === 'openssl') {
  if ((['catalogue_signature','bootstrap_bad_project_signature'].includes(scenario) && args.at(-1).endsWith('catalogue.json')) || (scenario === 'manifest_signature' && args.at(-1).endsWith('manifest.json'))) fail('Signature rejected');
} else if (command === 'usign') {
  if (['index_signature','dep_signature'].includes(scenario)) fail('Distribution signature rejected');
} else if (command === 'sha256sum') {
  if (args[0] !== '-c') { for (const file of args) out(crypto.createHash('sha256').update(fs.readFileSync(native(file))).digest('hex') + '  ' + file); }
  else {
    const input = fs.readFileSync(args[1] === '-' ? 0 : native(args[1]), 'utf8').trim();
    for(const line of input.split(/\r?\n/)) {
      const match = line.match(/^([a-f0-9]{64})\s+(.+)$/);
      if (!match || crypto.createHash('sha256').update(fs.readFileSync(native(match[2]))).digest('hex') !== match[1]) fail('Digest rejected');
    }
  }
} else if (command === 'dnsmasq') out('Compile time options: IPv6 ipset nftset');
else if (command.startsWith('service:')) {
  if (['service_failure','module_failure'].includes(scenario) && command === 'service:csqtt-health' && args[0] === 'restart') fail('Service failed');
} else if (command === 'apk' || command === 'opkg') {
  if (args.some(a => ['--allow-untrusted','--nodeps','--force-depends','--force-checksum','--force-signature'].includes(a))) fail('Trust/dependency bypass');
  const staged = args.includes('--root') || args.includes('--offline-root');
  const base = staged ? native(opt(args.includes('--root') ? '--root' : '--offline-root')) : root;
  const dbfile = path.join(base, command === 'apk' ? 'lib/apk/db/installed' : 'usr/lib/opkg/fixture.json');
  const action = args.find(a => ['query','verify','add','del','install','remove','status','list-installed','update'].includes(a));
  // Native APK 3 defaults maintainer scripts to PATH alone. The installer must
  // explicitly retain its verified lifecycle owner for script/init children.
  if(command==='apk' && !staged && ['add','del'].includes(action) && !args.includes('--preserve-env')) fail('APK would strip lifecycle ownership from maintainer scripts');
  if (action === 'update') {
    if(scenario === 'bootstrap_signature') fail('Native feed signature rejected');
    if(command === 'opkg') {
      const lists=native(opt('--lists-dir'));
      fs.mkdirSync(lists,{recursive:true});
      fs.writeFileSync(path.join(lists,'openwrt_base'),'authenticated official fixture index');
      fs.writeFileSync(path.join(lists,'openwrt_base.sig'),'authenticated official fixture signature');
    }
    process.exit(0);
  }
  if (action === 'verify') {
    if (scenario === 'package_signature' && !args.at(-1).includes('index')) fail('Native APK signature rejected');
    if (scenario === 'index_signature' && args.at(-1).includes('index')) fail('Native index signature rejected');
    process.exit(0);
  }
  const db = fs.existsSync(dbfile) ? JSON.parse(fs.readFileSync(dbfile, 'utf8')) : Object.fromEntries(fs.readFileSync(path.join(base, 'usr/lib/opkg/status'), 'utf8').replace(/\r\n/g, '\n').trim().split(/\n\n+/).map(stanza => {
    const name=stanza.match(/^Package: (.+)$/m)?.[1], version=stanza.match(/^Version: (.+)$/m)?.[1]; return [name,version];
  }).filter(([name]) => name));
  const save = () => {
    fs.writeFileSync(dbfile, JSON.stringify(db));
    if (command === 'opkg') fs.writeFileSync(path.join(base, 'usr/lib/opkg/status'), Object.entries(db).map(([name, version]) => `Package: ${name}\nVersion: ${version}\nStatus: install ok installed\nArchitecture: x86_64\n`).join('\n'));
  };
  if (action === 'query') {
    const names = args.at(-1) === '*' ? Object.keys(db) : db[args.at(-1)] ? [args.at(-1)] : [];
    if (opt('--format') === 'default') for(const name of names) out(`Name: ${name}\nVersion: ${db[name]}\n`);
    else out(JSON.stringify(names.map(name => ({name, version:db[name], package:name+'-'+db[name], status:['installed']}))));
  } else if (action === 'status') {
    if (db[args.at(-1)]) out('Package: '+args.at(-1)+'\nVersion: '+db[args.at(-1)]+'\nStatus: install ok installed');
  } else if (action === 'list-installed') {
    for (const [name, version] of Object.entries(db).sort()) out(name+' - '+version);
  } else if (['add','install'].includes(action)) {
    const bootstrap = scenario.startsWith('bootstrap') && args.slice(args.indexOf(action)+1).some(a => ['openssl-util','jsonfilter'].includes(a) || a.startsWith('openssl-util=') || a.includes('/installer-bootstrap/'));
    if (command === 'apk' && !args.includes('--no-network') && !(staged && bootstrap && args.includes('--cache-predownload'))) fail('Online APK mutation');
    if (command === 'opkg' && (!process.env.OPKG_CONF_DIR || fs.readdirSync(native(process.env.OPKG_CONF_DIR)).length)) fail('Inherited opkg feeds');
    if (staged && command === 'apk' && !args.includes('--no-scripts')) fail('Staging scripts enabled');
    if (staged && scenario === 'dependency') fail('Dependency unavailable offline');
    if (staged && bootstrap && scenario === 'bootstrap_signature') fail('Native feed signature rejected');
    if(command === 'opkg' && staged && bootstrap) {
      // Native opkg prefixes even absolute lists_dir paths with offline_root.
      const lists=path.join(base,(opt('--lists-dir') || '').replace(/^\/+/,''));
      for(const [file,content] of [['openwrt_base','authenticated official fixture index'],['openwrt_base.sig','authenticated official fixture signature']]) {
        if(!fs.existsSync(path.join(lists,file)) || fs.readFileSync(path.join(lists,file),'utf8') !== content) fail('Authenticated lists missing from native offline root');
      }
    }
    const packages = args.slice(args.indexOf(action)+1);
    for (const file of packages) {
      if (file.includes('=')) { const [name, version] = file.split('='); db[name]=version; continue; }
      if(bootstrap && !file.includes('/')) {
        const metadata={package:file,version:'1'};
        db[file]='1';
        const cache=native(opt('--cache-dir') || opt('--cache'));
        fs.mkdirSync(cache,{recursive:true});
        fs.writeFileSync(path.join(cache,file+'-1.'+(command === 'apk'?'apk':'ipk')),JSON.stringify(metadata));
        if(command==='opkg' && file==='openssl-util') {
          db['libopenssl3']='1';
          fs.writeFileSync(path.join(cache,'libopenssl3-1.ipk'),JSON.stringify({package:'libopenssl3',version:'1'}));
        }
        continue;
      }
      const metadata = JSON.parse(fs.readFileSync(native(file), 'utf8'));
      db[metadata.package] = scenario === 'wrong_installed_version' && metadata.package === 'csqtt' ? 'broken' : metadata.version;
    }
    if (staged && bootstrap && scenario === 'bootstrap_upgrade') db['ip-full']='unexpected-upgrade';
    if (['unrelated_change','dep_solver_upgrade'].includes(scenario) && staged) db['ip-full']='unexpected-version';
    save();
    if(!staged && scenario==='operation_lock') {
      const owner=process.env.CSQTT_OPERATION_OWNER,ticks=process.env.CSQTT_OPERATION_TICKS;
      const lock=path.join(root,'var/lock/csqtt-operation');
      if(!owner || !ticks || fs.readFileSync(path.join(lock,'pid'),'utf8').trim()!==owner || fs.readFileSync(path.join(lock,'ticks'),'utf8').trim()!==ticks) fail('Installer child lost lifecycle ownership');
      fs.writeFileSync(path.join(root,'transaction-held'),'held');
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,2000);
      if(fs.existsSync(path.join(root,'stop-admitted'))) fail('Competing Stop entered during the transaction');
    }
    if (!staged && scenario.startsWith('bootstrap')) {
      for(const [pkg,cmd] of [['openssl-util','openssl'],['jsonfilter','jsonfilter']]) if(db[pkg]) fs.copyFileSync(path.join(root,cmd+'-wrapper'),path.join(native(process.env.CSQTT_WRAPPER_PATH),cmd));
    }
    const interruption=['powerloss','bootstrap_powerloss_main','module_powerloss'].includes(scenario) && packages.some(p=>p.includes('0.1.0')) || scenario === 'bootstrap_powerloss' && bootstrap;
    if (!staged && interruption && !fs.existsSync(path.join(root,'powerloss-triggered'))) {
      fs.writeFileSync(path.join(root,'powerloss-triggered'),'once');
      process.exit(77);
    }
    if (!staged && scenario === 'install_failure' && packages.some(p => p.includes('0.1.0'))) fail('Partial install failure');
  } else if (['del','remove'].includes(action)) {
    if(command==='opkg') {
      const selected=args.slice(args.indexOf(action)+1);
      if(selected.includes('libopenssl3') && db['openssl-util']) fail('Package libopenssl3 is depended upon by openssl-util');
      if(args.includes('--noaction')) process.exit(0);
    }
    for (const name of args.slice(args.indexOf(action)+1)) delete db[name];
    if(staged && scenario==='bootstrap_orphan') delete db['ip-full'];
    save();
    if(!staged && scenario.startsWith('bootstrap')) for(const [pkg,cmd] of [['openssl-util','openssl'],['jsonfilter','jsonfilter']]) if(!db[pkg]) fs.rmSync(path.join(native(process.env.CSQTT_WRAPPER_PATH),cmd),{force:true});
  } else fail('Unexpected package manager action');
} else if (!['ucode','fw4','fw3','nft','iptables','procd','netifd','tar','chmod','sync'].includes(command)) fail('Unexpected command');
