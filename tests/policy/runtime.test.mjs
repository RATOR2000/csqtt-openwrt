import test from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { runtime, fixture, root } from './harness.mjs';
function packages() {
  return { csqtt: { main: { '.type': 'client', ...fixture.main },
    ...Object.fromEntries(fixture.groups.map(g => [g.id, { '.type': 'group', ...g }])),
    ...Object.fromEntries(fixture.devices.map(g => [g.id, { '.type': 'device', ...g }])),
    ...Object.fromEntries(fixture.rules.map(g => [g.id, { '.type': 'rule', ...g }])) },
    firewall: { defaults: { '.type': 'defaults', flow_offloading: '1' } } };
}

test('runtime compiles private files, canonical local subnets and known client JSON fields', () => {
  const data = packages(); data.csqtt.main.password = randomBytes(24).toString('hex');
  const out = runtime('compile', { packages: data, network: { interface: [{ l3_device: 'br-lan', 'ipv4-address': [{ address: '192.168.1.1', mask: 24 }] }] } });
  const model = JSON.parse(out.files['/var/run/csqtt/apply.42/policy.json']);
  const cfg = JSON.parse(out.files['/var/run/csqtt/apply.42/client.json']);
  assert.equal(cfg.password, data.csqtt.main.password);
  assert.equal(cfg.tun_device, 'csqtt0'); assert.equal(cfg.client_ids, '8202606,6287487');
  assert.equal(cfg.vk_auth_mode, 'vkcalls'); assert.equal(cfg.obfs, 'video');
  assert.equal(cfg.captcha_mode, undefined); assert.equal(cfg.mtu, undefined);
  assert.deepEqual(model.locals, ['192.168.1.0/24']);
  assert.equal(JSON.stringify(model).includes(cfg.password), false);
  assert.ok(out.chmods.every(([, mode]) => mode === 0o600));
});

test('empty disabled config is valid but starting without credentials is rejected', () => {
  const data = packages(); runtime('compile', { packages: data });
  data.csqtt.main.enabled = '1'; assert.throws(() => runtime('compile', { packages: data }), /needs peer/);
  data.csqtt.main.enabled = '0'; data.csqtt.main.turn_host = 'host\nignored'; assert.throws(() => runtime('compile', { packages: data }), /TURN host/);
});

test('runtime enforces original client hash and worker capacities', () => {
  const data = packages();
  const hashes = Array.from({ length: 6 }, (_, i) => 'valid_call_hash_' + String(i).padStart(4, '0'));
  data.csqtt.main.vk_hashes = hashes; data.csqtt.main.workers = '126';
  const out = runtime('compile', { packages: data });
  assert.equal(JSON.parse(out.files['/var/run/csqtt/apply.42/client.json']).workers, 126);
  for (const count of ['1', '10', '127']) {
    data.csqtt.main.workers = count;
    assert.throws(() => runtime('compile', { packages: data }), /[Ww]orkers/);
  }
  data.csqtt.main.workers = '36'; data.csqtt.main.vk_hashes = hashes.slice(0, 1);
  assert.throws(() => runtime('compile', { packages: data }), /hash capacity/);
  data.csqtt.main.workers = '9'; data.csqtt.main.vk_hashes = [...hashes, 'valid_call_hash_0006'];
  assert.throws(() => runtime('compile', { packages: data }), /six VK/);
  data.csqtt.main.vk_hashes = [hashes[0], hashes[0]];
  assert.throws(() => runtime('compile', { packages: data }), /Duplicate VK/);
});

test('runtime rejects malformed peer endpoints before activating policy', () => {
  for (const peer of ['missing-port', 'host:0', 'host:65536', '-bad.example:123', 'host/name:443']) {
    const data = packages(); data.csqtt.main.peer = peer;
    assert.throws(() => runtime('compile', { packages: data }), /[Pp]eer/);
  }
  for (const peer of ['server.example:46000', '192.0.2.1:46000', '[2001:db8::1]:46000']) {
    const data = packages(); data.csqtt.main.peer = peer;
    const out = runtime('compile', { packages: data });
    assert.equal(JSON.parse(out.files['/var/run/csqtt/apply.42/client.json']).peer, peer);
  }
});

test('status allowlist redacts new upstream fields and stale connected state', () => {
  const secret = randomBytes(32).toString('hex');
  const out = runtime('status', { packages: packages(), files: { '/var/run/csqtt/status.json': JSON.stringify({ state: 'connected', password: secret, unknown: secret, captcha: { id: 'public-id', state: 'pending', expires_at: 123, session_token: secret } }) } });
  assert.equal(out.output[0].core.state, 'stopped');
  assert.equal(JSON.stringify(out.output).includes(secret), false);
  assert.equal(out.output[0].core.captcha.id, 'public-id');
});

test('missing, null and malformed private state have safe status defaults', () => {
  for (const contents of [null, 'null', '{broken']) {
    const files = contents === null ? {} : { '/etc/csqtt/policy.json': contents, '/var/run/csqtt/status.json': contents };
    const out = runtime('status', { packages: packages(), files });
    assert.equal(out.output[0].policies_active, false);
    assert.equal(out.output[0].groups, 0);
    assert.equal(out.output[0].core.state, 'stopped');
  }
});

test('group DNS readiness requires every configured procd instance', () => {
  const files = { '/var/run/csqtt/dns.ids': 'private\ndirect\n' };
  assert.throws(() => runtime('dns-ready', { files, services: { 'csqtt-dns': { instances: { dns_private: { running: true } } } } }), /Exit 1/);
  runtime('dns-ready', { files, services: { 'csqtt-dns': { instances: { dns_private: { running: true }, dns_direct: { running: true } } } } });
});

test('firewall activation snapshots offload once and deactivation restores absent options', () => {
  const first = runtime('firewall-on', { packages: packages() });
  assert.equal(first.packages.firewall.defaults.flow_offloading, '0');
  assert.equal(first.packages.firewall.csqtt_guard.position, 'ruleset-post');
  assert.equal(first.packages.firewall.csqtt_forward.chain, 'forward');
  const second = runtime('firewall-on', first);
  assert.equal(second.files['/etc/csqtt/offload.json'], first.files['/etc/csqtt/offload.json']);
  const off = runtime('firewall-off', second);
  assert.equal(off.packages.firewall.defaults.flow_offloading, '1');
  assert.equal(off.packages.firewall.defaults.flow_offloading_hw, undefined);
  assert.equal(off.packages.firewall.csqtt_guard, undefined);
});

test('offload restoration preserves a later explicit administrator change', () => {
  const state = runtime('firewall-on', { packages: packages() });
  state.packages.firewall.defaults.flow_offloading_hw = '1';
  const off = runtime('firewall-off', state);
  assert.equal(off.packages.firewall.defaults.flow_offloading_hw, '1');
});

test('foreign firewall section cannot be overwritten', () => {
  const data = packages(); data.firewall.csqtt_guard = { '.type': 'rule', target: 'DROP' };
  assert.throws(() => runtime('firewall-on', { packages: data }), /collision/);
});

test('maintenance-only firewall include persists without changing offload or requiring policy files', () => {
  const held = runtime('firewall-hold', { packages: packages() });
  assert.deepEqual(held.packages.firewall.csqtt_hold, { '.type': 'include', type: 'nftables',
    path: '/etc/csqtt/hold.nft', position: 'ruleset-post', csqtt_owned: '1' });
  assert.equal(held.packages.firewall.defaults.flow_offloading, '1');
  assert.equal(held.packages.firewall.csqtt_guard, undefined);
  assert.equal(held.files['/etc/csqtt/offload.json'], undefined);
  assert.equal(runtime('firewall-off', held).packages.firewall.csqtt_hold, undefined);
  const data = packages(); data.firewall.csqtt_hold = { '.type': 'rule', target: 'DROP' };
  assert.throws(() => runtime('firewall-hold', { packages: data }), /collision/);
});

test('first apply saves a boot firewall include before nft validation can fail', () => {
  const git = process.platform === 'win32' ? execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0] : '';
  const shell = process.platform === 'win32' ? ['../bin/sh.exe', '../usr/bin/sh.exe']
    .map(p => path.resolve(path.dirname(git), p)).find(p => fs.existsSync(p)) : '/bin/sh';
  assert.ok(shell && fs.existsSync(shell), 'A POSIX shell is required for the manage failure regression');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'csqtt-hold-')).replaceAll('\\', '/');
  const shellBin = path.dirname(shell).replaceAll('\\', '/').replace(/^([a-zA-Z]):/, (_, drive) => '/' + drive.toLowerCase());
  try {
    const driver = `${dir}/hold-driver.mjs`;
    fs.writeFileSync(driver, `import fs from 'node:fs';\nimport { runtime } from ${JSON.stringify(pathToFileURL(path.join(root, 'tests/policy/harness.mjs')).href)};\n` +
      `fs.writeFileSync(${JSON.stringify(`${dir}/firewall.json`)}, JSON.stringify(runtime('firewall-hold', { packages: { firewall: { defaults: { '.type': 'defaults', flow_offloading: '1' } } } }).packages.firewall));\n`);
    const stubs = `
PATH='${shellBin}':"$PATH"
chmod() { :; }
uci() { printf '0\\n'; }
dnsmasq() { printf 'nftset\\n'; }
logger() { :; }
nft() { case "$1" in -c|list) return 1 ;; *) return 0 ;; esac; }
ucode() {
  case "$2" in
    compile)
      printf 1 > "$3/active"
      printf 'saved maintenance guard\\n' > "$3/hold.nft"
      printf 'invalid nft fixture\\n' > "$3/policy.nft" ;;
    firewall-hold) node '${driver}' ;;
    *) return 99 ;;
  esac
}
`;
    const manage = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/manage'), 'utf8')
      .replace('umask 077', 'umask 077\n' + stubs)
      .replace('RUN=/var/run/csqtt', `RUN='${dir}/run'`)
      .replace('STATE=/etc/csqtt', `STATE='${dir}/state'`)
      .replaceAll('/var/lock', `${dir}/lock`);
    const script = `${dir}/manage`; fs.writeFileSync(script, manage);
    const failed = spawnSync(shell, [script, 'apply'], { encoding: 'utf8' });
    assert.equal(failed.status, 1, failed.stdout + failed.stderr);
    assert.match(failed.stderr, /Generated firewall policy was rejected/);
    const firewall = JSON.parse(fs.readFileSync(`${dir}/firewall.json`, 'utf8'));
    assert.equal(firewall.csqtt_hold.path, '/etc/csqtt/hold.nft');
    assert.equal(fs.readFileSync(`${dir}/state/hold.nft`, 'utf8'), 'saved maintenance guard\n');
    assert.equal(firewall.defaults.flow_offloading, '1');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('device discovery combines leases, ARP and configured membership', () => {
  const out = runtime('devices', { packages: packages(), files: {
    '/tmp/dhcp.leases': '0 02:00:00:00:00:01 192.168.1.10 desktop *\n',
    '/proc/net/arp': 'IP address HW type Flags HW address Mask Device\n192.168.1.10 0x1 0x2 02:00:00:00:00:01 * br-lan\n',
  } });
  const first = out.output[0].devices.find(d => d.mac.endsWith(':01'));
  assert.equal(first.ip, '192.168.1.10'); assert.equal(first.group, 'private'); assert.equal(first.online, true);
  assert.equal(out.output[0].devices.length, 2);
});

test('status exposes the local DNS domain without requiring DHCP UCI access', () => {
  const data = packages(); data.dhcp = { dns: { '.type': 'dnsmasq', domain: 'lab.lan' } };
  const out = runtime('status', { packages: data });
  assert.equal(out.output[0].local_domain, 'lab.lan');
});
