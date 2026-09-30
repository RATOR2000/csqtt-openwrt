/* Isolated shell-harness command doubles; never operates a real router. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const [command, ...args] = process.argv.slice(2);
const root = process.env.CSQTT_FAKE_ROOT;
const scenario = process.env.CSQTT_FAKE_SCENARIO;
if (!root || !fs.existsSync(path.join(root, '.installer-fixture'))) throw Error('Missing isolated fixture');
const log = entry => fs.appendFileSync(path.join(root, 'commands.jsonl'), JSON.stringify(entry) + '\n');
const fail = message => { console.error(message); process.exit(1); };
const output = value => process.stdout.write(String(value) + '\n');
const option = flag => args[args.indexOf(flag) + 1];
const resolve = (base, value) => path.isAbsolute(value) ? value : path.join(base, value);
log({ command, args });
if (command === 'id') output(0);
else if (command === 'df') output('Filesystem 1024-blocks Used Available Capacity Mounted on\nfixture 1000000 1000 ' + (scenario === 'space' ? 1024 : 999000) + ' 1% /overlay');
else if (command === 'chmod') {
  for (const file of args.slice(1)) {
    if (!path.resolve(file).startsWith(path.resolve(root) + path.sep)) fail('chmod escaped fixture');
    fs.chmodSync(file, Number.parseInt(args[0], 8));
  }
} else if (command === 'tar') {
  const directory = path.join(option('-C'), args.at(-1));
  const entries = Object.fromEntries(fs.readdirSync(directory).map(name => [name, fs.readFileSync(path.join(directory, name), 'utf8')]));
  fs.writeFileSync(option('-czf'), zlib.gzipSync(JSON.stringify(entries)));
} else if (command === 'sha256sum') {
  const [expected, file] = fs.readFileSync(0, 'utf8').trim().split(/\s+/, 2);
  const native = process.platform === 'win32' && /^\/[a-z]\//i.test(file) ? file[1] + ':' + file.slice(2) : file;
  const actual = crypto.createHash('sha256').update(fs.readFileSync(native)).digest('hex');
  if (actual !== expected.toLowerCase()) fail('Checksum mismatch');
}
else if (command === 'uclient-fetch') {
  const name = args.at(-1).split('/').at(-1);
  if (scenario === 'download' && name.endsWith('.apk')) fail('fake download failure');
  fs.copyFileSync(path.join(root, 'release', name), option('-O'));
} else if (command === 'jsonfilter') {
  let value = JSON.parse(fs.readFileSync(option('-i'), 'utf8'));
  const tokens = [...option('-e').matchAll(/\.([A-Za-z0-9_-]+)|\[(\*|\d+)\]/g)].map(match => match[1] ?? match[2]);
  let values = [value];
  for (const token of tokens) values = values.flatMap(item => token === '*' ? Array.isArray(item) ? item : [] : item?.[token] === undefined ? [] : [item[token]]);
  for (value of values) output(typeof value === 'object' ? JSON.stringify(value) : value);
} else if (command === 'openssl') {
  if (scenario === 'manifest_signature' || scenario === 'bootstrap_signature') fail('fake manifest signature failure');
} else if (command.startsWith('service:')) {
  if (scenario === command.slice(8) + '_' + args[0]) fail('fake service failure');
} else if (command === 'apk') {
  if (args.includes('--allow-untrusted')) fail('Untrusted APK bypass forbidden');
  if (process.env.APK_CONFIG !== '/dev/null') fail('APK config not isolated');
  // APK 3.0.5 prints its compiled CPU architecture, ignoring /etc/apk/arch.
  if (args.includes('--print-arch')) { output('aarch64'); process.exit(0); }
  const index = args.findIndex(arg => ['query', 'verify', 'fetch', 'info', 'add', 'del'].includes(arg));
  if (index < 0) fail('Unknown apk invocation');
  const action = args[index];
  if (args.includes('--no-scripts') && !['add', 'del'].includes(action)) fail('APK 3.0.5 read applet rejects no-scripts');
  const base = args.includes('--root') ? option('--root') : root;
  if (!path.resolve(base).startsWith(path.resolve(root) + path.sep) && base !== root) fail('APK escaped fixture');
  const staged = base !== root;
  if (staged && ['add', 'del'].includes(action) && !args.includes('--no-scripts')) fail('Staging scripts are enabled');
  const database = path.join(base, 'lib/apk/db/installed');
  const installed = JSON.parse(fs.readFileSync(database, 'utf8'));
  const world = path.join(base, 'etc/apk/world');
  const save = () => fs.writeFileSync(database, JSON.stringify(installed));
  const plain = args.slice(index + 1).filter((arg, i, tail) => !arg.startsWith('--') && !['--output', '--match', '--fields', '--format'].includes(tail[i - 1]));
  if (action === 'query') {
    const name = args.at(-1);
    output(JSON.stringify(installed[name] ? [{ name, version: installed[name], package: name + '-' + installed[name] }] : []));
  } else if (action === 'verify') {
    const file = args.at(-1);
    if (file.includes('packages') && (!option('--keys-dir').endsWith('release-keys') || fs.readdirSync(option('--keys-dir')).length !== 1)) fail('Release APK verification is not pinned to one key');
    if (scenario === 'package_signature' && file.includes('packages')) fail('fake APK signature failure');
  } else if (action === 'fetch') {
    // Read-only APK fetch does not refresh a missing index cache. The rollback
    // fetch must read the remote signed index directly on a stock fresh router.
    if (!args.includes('--no-cache')) fail('dnsmasq: unable to select package (or its dependencies)');
    if (scenario === 'rollback_cache') fail('exact installed version unavailable');
    if (args.at(-1) !== 'dnsmasq=2.91-r2') fail('Rollback fetched a different version');
    fs.writeFileSync(path.join(option('--output'), 'dnsmasq-2.91-r2.apk'), 'official signed original dnsmasq');
  } else if (action === 'info') output(Object.keys(installed).sort().join('\n'));
  else if (action === 'del') {
    if (!args.includes('--simulate')) {
      for (const name of plain) delete installed[name];
      if (staged && scenario === 'remove_other') delete installed['base-files'];
      const removed = new Set(plain);
      fs.writeFileSync(world, fs.readFileSync(world, 'utf8').split('\n').filter(name => !removed.has(name)).join('\n'));
      save();
    }
  } else if (action === 'add') {
    if (plain.includes('openssl-util')) {
      if (staged || !args.includes('--repositories-file')) fail('Unsafe OpenSSL bootstrap');
      const verified = fs.readFileSync(path.join(root, 'commands.jsonl'), 'utf8').split('\n').filter(line => line && JSON.parse(line).args.includes('verify'));
      if (verified.length !== 3) fail('Bootstrap started before three APK signature checks');
      fs.copyFileSync(path.join(root, 'openssl-wrapper'), path.join(process.env.CSQTT_FAKE_BIN, 'openssl'));
      fs.chmodSync(path.join(process.env.CSQTT_FAKE_BIN, 'openssl'), 0o755);
      installed['openssl-util'] = '3.5.0-r1'; save();
      process.exit(0);
    }
    const rollback = plain.length === 1 && plain[0].endsWith('dnsmasq-2.91-r2.apk');
    if (!rollback && plain.length !== 4) fail('Dependencies were added as world roots');
    if (staged && args.includes('--simulate') && scenario === 'dependency') fail('unrelated dependency failure');
    if (staged && !args.includes('--simulate') && action === 'add' && scenario === 'prefetch') fail('prefetch network failure');
    const cache = resolve(base, option('--cache-dir'));
    if (!rollback && args.includes('--no-network') && !fs.existsSync(path.join(cache, 'dependency.apk'))) fail('Required dependency missing from offline cache');
    if (!args.includes('--simulate')) {
      if (rollback) installed.dnsmasq = '2.91-r2';
      else {
        delete installed.dnsmasq;
        Object.assign(installed, { csqtt: '0.1.0-r1', 'csqtt-captcha': '0.1.0-r1', 'luci-app-csqtt': '0.1.0-r1', 'dnsmasq-full': '2.93-r1' });
        fs.mkdirSync(cache, { recursive: true });
        if (scenario !== 'offline_cache') fs.writeFileSync(path.join(cache, 'dependency.apk'), 'signed dependency');
      }
      const roots = rollback ? ['dnsmasq'] : ['csqtt', 'csqtt-captcha', 'luci-app-csqtt', 'dnsmasq-full'];
      const existing = fs.readFileSync(world, 'utf8').split('\n').filter(Boolean);
      fs.writeFileSync(world, [...new Set([...existing, ...roots])].join('\n') + '\n');
      save();
      if (!staged && !rollback && scenario === 'install') fail('partial package install failure');
      if (!staged && !rollback && scenario === 'interrupt') process.exit(143);
    }
  }
} else fail('Unknown fake command: ' + command);
