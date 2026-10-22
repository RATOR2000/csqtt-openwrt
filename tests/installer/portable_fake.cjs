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
  if ((scenario === 'catalogue_signature' && args.at(-1).endsWith('catalogue.json')) || (scenario === 'manifest_signature' && args.at(-1).endsWith('manifest.json'))) fail('Signature rejected');
} else if (command === 'usign') {
  if (scenario === 'index_signature') fail('Distribution signature rejected');
} else if (command === 'sha256sum') {
  if (args[0] !== '-c') { for (const file of args) out(crypto.createHash('sha256').update(fs.readFileSync(native(file))).digest('hex') + '  ' + file); }
  else {
    const input = fs.readFileSync(0, 'utf8').trim();
    const match = input.match(/^([a-f0-9]{64})\s+(.+)$/);
    if (!match || crypto.createHash('sha256').update(fs.readFileSync(native(match[2]))).digest('hex') !== match[1]) fail('Digest rejected');
  }
} else if (command === 'dnsmasq') out('Compile time options: IPv6 ipset nftset');
else if (command.startsWith('service:')) {
  if (scenario === 'service_failure' && command === 'service:csqtt-health' && args[0] === 'restart') fail('Service failed');
} else if (command === 'apk' || command === 'opkg') {
  if (args.some(a => ['--allow-untrusted','--nodeps','--force-depends','--force-checksum','--force-signature'].includes(a))) fail('Trust/dependency bypass');
  const staged = args.includes('--root') || args.includes('--offline-root');
  const base = staged ? native(opt(args.includes('--root') ? '--root' : '--offline-root')) : root;
  const dbfile = path.join(base, command === 'apk' ? 'lib/apk/db/installed' : 'usr/lib/opkg/fixture.json');
  const action = args.find(a => ['query','verify','add','del','install','remove','status','list-installed'].includes(a));
  if (action === 'verify') {
    if (scenario === 'package_signature' && !args.at(-1).includes('index')) fail('Native APK signature rejected');
    if (scenario === 'index_signature' && args.at(-1).includes('index')) fail('Native index signature rejected');
    process.exit(0);
  }
  const db = fs.existsSync(dbfile) ? JSON.parse(fs.readFileSync(dbfile, 'utf8')) : Object.fromEntries(fs.readFileSync(path.join(base, 'usr/lib/opkg/status'), 'utf8').trim().split(/\n\n+/).map(stanza => {
    const name=stanza.match(/^Package: (.+)$/m)?.[1], version=stanza.match(/^Version: (.+)$/m)?.[1]; return [name,version];
  }).filter(([name]) => name));
  const save = () => {
    fs.writeFileSync(dbfile, JSON.stringify(db));
    if (command === 'opkg') fs.writeFileSync(path.join(base, 'usr/lib/opkg/status'), Object.entries(db).map(([name, version]) => `Package: ${name}\nVersion: ${version}\nStatus: install ok installed\nArchitecture: x86_64\n`).join('\n'));
  };
  if (action === 'query') {
    const names = args.at(-1) === '*' ? Object.keys(db) : db[args.at(-1)] ? [args.at(-1)] : [];
    out(JSON.stringify(names.map(name => ({name, version:db[name], package:name+'-'+db[name], status:['installed']}))));
  } else if (action === 'status') {
    if (db[args.at(-1)]) out('Package: '+args.at(-1)+'\nVersion: '+db[args.at(-1)]+'\nStatus: install ok installed');
  } else if (action === 'list-installed') {
    for (const [name, version] of Object.entries(db).sort()) out(name+' - '+version);
  } else if (['add','install'].includes(action)) {
    if (command === 'apk' && !args.includes('--no-network')) fail('Online APK mutation');
    if (command === 'opkg' && (!process.env.OPKG_CONF_DIR || fs.readdirSync(native(process.env.OPKG_CONF_DIR)).length)) fail('Inherited opkg feeds');
    if (staged && command === 'apk' && !args.includes('--no-scripts')) fail('Staging scripts enabled');
    if (staged && scenario === 'dependency') fail('Dependency unavailable offline');
    const packages = args.slice(args.indexOf(action)+1);
    for (const file of packages) {
      if (file.includes('=')) { const [name, version] = file.split('='); db[name]=version; continue; }
      const metadata = JSON.parse(fs.readFileSync(native(file), 'utf8'));
      db[metadata.package] = scenario === 'wrong_installed_version' && metadata.package === 'csqtt' ? 'broken' : metadata.version;
    }
    if (scenario === 'unrelated_change' && staged) db['ip-full']='unexpected-version';
    save();
    if (!staged && scenario === 'install_failure' && packages.some(p => p.includes('0.1.0'))) fail('Partial install failure');
  } else if (['del','remove'].includes(action)) {
    for (const name of args.slice(args.indexOf(action)+1)) delete db[name];
    save();
  } else fail('Unexpected package manager action');
} else if (!['ucode','fw4','fw3','nft','iptables','procd','netifd','tar'].includes(command)) fail('Unexpected command');
