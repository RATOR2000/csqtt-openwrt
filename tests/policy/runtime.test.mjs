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

test('runtime rejects every ASCII control and delimiter while preserving valid passwords', () => {
  const secret = randomBytes(16).toString('hex');
  for (const code of [...Array.from({ length: 32 }, (_, i) => i), 127]) {
    const data = packages(); data.csqtt.main.password = secret + String.fromCharCode(code);
    assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid password$/);
    data.csqtt.main.password = secret; data.csqtt.main.peer = 'host' + String.fromCharCode(code) + ':443';
    assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid peer$/);
  }
  const data = packages(); data.csqtt.main.password = secret + '|';
  assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid password$/);
  for (const password of [secret + ' space', secret + 'Кафе', 'a'.repeat(128)]) {
    data.csqtt.main.password = password;
    assert.equal(JSON.parse(runtime('compile', { packages: data }).files['/var/run/csqtt/apply.42/client.json']).password, password);
  }
  data.csqtt.main.password = 'a'.repeat(129);
  assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid password$/);
  data.csqtt.main.password = secret; data.csqtt.main.peer = 'host name:443';
  assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid peer$/);
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
  const character = randomBytes(1).toString('hex')[0];
  for (const length of [16, 1024]) {
    data.csqtt.main.vk_hashes = [character.repeat(length)];
    assert.equal(JSON.parse(runtime('compile', { packages: data }).files['/var/run/csqtt/apply.42/client.json']).vk_hashes[0].length, length);
  }
  for (const hash of [character.repeat(15), character.repeat(1025), character.repeat(16) + '!']) {
    data.csqtt.main.vk_hashes = [hash];
    assert.throws(() => runtime('compile', { packages: data }), /^Error: Invalid VK hash$/);
  }
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

test('status exports only known daemon error codes, retaining safe failures after process exit', () => {
  for (const code of ['runtime_failed', 'transport_failed', 'tun_configuration_failed',
    'tun_down_hook_failed', 'control_socket_failed', 'tun_io_failed']) {
    const out = runtime('status', { files: { '/var/run/csqtt/status.json': JSON.stringify({ state: 'error', error_code: code }) } });
    assert.equal(out.output[0].core.error_code, code);
    assert.equal(out.output[0].core.state, 'stopped');
  }
  const secret = randomBytes(24).toString('hex');
  for (const code of [secret, 'unknown_failure', { detail: secret }]) {
    const out = runtime('diagnostics', { files: { '/var/run/csqtt/status.json': JSON.stringify({ state: 'error', error_code: code }) } });
    assert.equal(out.output[0].status.core.error_code, undefined);
    assert.equal(JSON.stringify(out.output).includes(secret), false);
  }
});

test('tunnel diagnostics require a running connected client without a reported failure', () => {
  for (const [running, state, error, ok, detail] of [
    [true, 'starting', null, false, 'starting'],
    [true, 'connecting', null, false, 'connecting'],
    [true, 'captcha_required', null, false, 'captcha_required'],
    [true, 'error', 'tun_io_failed', false, 'tun_io_failed'],
    [true, 'connected', null, true, 'connected'],
    [true, 'connected', 'transport_failed', false, 'transport_failed'],
    [false, 'connected', null, false, 'stopped'],
    [false, 'error', 'transport_failed', false, 'transport_failed'],
  ]) {
    const out = runtime('diagnostics', { services: { csqtt: { instances: { client: { running } } } },
      files: { '/var/run/csqtt/status.json': JSON.stringify({ state, error_code: error }) } });
    const tun = out.output[0].checks.find(check => check.name === 'tun');
    assert.equal(tun.ok, ok, `${running}/${state}/${error}`);
    assert.equal(tun.detail, detail);
  }
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

function dnsFixture() {
  const network = { interface: [{ l3_device: 'br-lan', 'ipv4-address': [{ address: '192.168.1.1', mask: 24 }] }] };
  const files = {
    '/var/run/csqtt/dns.ids': 'private\ndirect\n',
    '/etc/csqtt/policy.json': JSON.stringify({ lans: ['br-lan'], groups: [
      { id: 'private', port: 5400, macs: ['02:00:00:00:00:01'] },
      { id: 'direct', port: 5401, macs: ['02:00:00:00:00:02'] },
    ] }),
    '/proc/901/fd/4': 'socket:[1101]', '/proc/901/fd/5': 'socket:[2101]',
    '/proc/902/fd/4': 'socket:[1102]', '/proc/902/fd/5': 'socket:[2102]',
    '/proc/net/udp': 'sl local_address rem_address st tx_queue rx_queue uid timeout inode\n' +
      '0: 0101A8C0:1518 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 1101\n' +
      '1: 0101A8C0:1519 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 1102\n',
    '/proc/net/tcp': 'sl local_address rem_address st tx_queue rx_queue uid timeout inode\n' +
      '0: 0101A8C0:1518 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 2101\n' +
      '1: 0101A8C0:1519 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 2102\n',
  };
  const services = { 'csqtt-dns': { instances: {
    dns_private: { running: true, pid: 901 }, dns_direct: { running: true, pid: 902 },
  } } };
  return { files, services, network };
}

test('group DNS readiness waits for both LAN listeners owned by every current procd PID', () => {
  runtime('dns-ready', dnsFixture());
  for (const change of [
    f => { delete f.services['csqtt-dns'].instances.dns_direct; },
    f => { delete f.files['/proc/net/udp']; delete f.files['/proc/net/tcp']; },
    f => { f.files['/proc/net/tcp'] = ''; },
    f => { f.files['/proc/net/tcp'] = f.files['/proc/net/tcp'].replaceAll('0A ', '01 '); },
    f => { f.files['/proc/net/udp'] = f.files['/proc/net/udp'].replaceAll('0101A8C0', '0100007F'); },
    f => { f.files['/proc/901/fd/4'] = 'socket:[9999]'; },
    f => { f.services['csqtt-dns'].instances.dns_private.pid = 903; },
    f => { f.network.interface = []; },
    f => { delete f.files['/var/run/csqtt/dns.ids']; },
    f => { f.files['/var/run/csqtt/dns.ids'] = ''; },
    f => { f.files['/var/run/csqtt/dns.ids'] = 'private\nunknown\n'; },
    f => { f.files['/var/run/csqtt/dns.ids'] = 'private\nprivate\n'; },
    f => { f.services = null; },
  ]) {
    const fixture = dnsFixture(); change(fixture);
    assert.throws(() => runtime('dns-ready', fixture), /Exit 1/);
  }
  const wildcard = dnsFixture();
  wildcard.files['/proc/net/udp'] = wildcard.files['/proc/net/udp'].replaceAll('0101A8C0', '00000000');
  wildcard.files['/proc/net/tcp'] = wildcard.files['/proc/net/tcp'].replaceAll('0101A8C0', '00000000');
  runtime('dns-ready', wildcard);
  runtime('dns-ready', { files: { '/etc/csqtt/policy.json': '{"groups":[]}' } });
});

test('DNS diagnostics do not call a running process ready before its LAN sockets bind', () => {
  const fixture = dnsFixture(); fixture.files['/proc/net/udp'] = '';
  const out = runtime('diagnostics', fixture);
  assert.deepEqual(out.output[0].checks.filter(c => c.name === 'dnsmasq').map(c => c.ok), [false, false]);
});

test('DNS stop waits for snapshotted old PIDs even after procd removes their instances', () => {
  const old = dnsFixture();
  const snapshot = runtime('dns-snapshot', old);
  assert.deepEqual(JSON.parse(snapshot.files['/var/run/csqtt/dns.stop.json']), ['901', '902']);
  assert.ok(snapshot.chmods.some(([p, mode]) => p.endsWith('dns.stop.json') && mode === 0o600));
  const stopping = { ...old, files: snapshot.files, services: {} };
  assert.throws(() => runtime('dns-stopped', stopping), /Exit 1/);
  for (const file of Object.keys(stopping.files)) if (file.startsWith('/proc/901/') || file.startsWith('/proc/902/')) delete stopping.files[file];
  runtime('dns-stopped', stopping);
  stopping.services = { 'csqtt-dns': { instances: { dns_private: { running: true, pid: 903 } } } };
  assert.throws(() => runtime('dns-stopped', stopping), /Exit 1/);
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

test('device RPC retains disabled saved devices without reporting active group membership', () => {
  const data = packages(); const first = fixture.devices[0], second = fixture.devices[1];
  data.csqtt[first.id].enabled = '0';
  data.csqtt[first.id].name = 'Saved device';
  const out = runtime('devices', { packages: data, files: {
    '/tmp/dhcp.leases': `0 ${first.mac} 192.168.1.10 desktop *\n`,
    '/proc/net/arp': `IP address HW type Flags HW address Mask Device\n192.168.1.10 0x1 0x2 ${first.mac} * br-lan\n`,
  } });
  const disabled = out.output[0].devices.find(d => d.mac === first.mac);
  assert.equal(disabled.enabled, false); assert.equal(disabled.group, undefined);
  assert.equal(disabled.ip, '192.168.1.10'); assert.equal(disabled.online, true);
  assert.equal(disabled.name, 'Saved device');
  const active = out.output[0].devices.find(d => d.mac === second.mac);
  assert.equal(active.group, second.group); assert.equal(active.enabled, undefined);
  assert.equal(out.packages.csqtt[first.id].group, first.group);
  assert.equal(out.packages.csqtt[first.id].mac, first.mac);
  data.csqtt[first.id].enabled = '1';
  assert.equal(runtime('devices', { packages: data }).output[0].devices.find(d => d.mac === first.mac).group, first.group);
});

test('runtime stages active device counts, only active DNS listeners and unchanged saved UCI rows', () => {
  const data = packages();
  for (const device of fixture.devices) data.csqtt[device.id].enabled = '0';
  const compiled = runtime('compile', { packages: data });
  const model = JSON.parse(compiled.files['/var/run/csqtt/apply.42/policy.json']);
  assert.equal(model.devices.length, 0);
  assert.equal(compiled.files['/var/run/csqtt/apply.42/active'], '0');
  assert.equal(compiled.files['/var/run/csqtt/apply.42/dns.ids'], '\n');
  assert.ok(!Object.keys(compiled.files).some(p => /\/dns-.*\.conf$/.test(p)));
  for (const device of fixture.devices) assert.deepEqual(compiled.packages.csqtt[device.id], data.csqtt[device.id]);
  const files = { '/etc/csqtt/policy.json': JSON.stringify(model), '/var/run/csqtt/dns.ids': '\n' };
  const status = runtime('status', { packages: data, files }).output[0];
  assert.equal(status.devices, 0); assert.equal(status.policies_active, false);
  assert.equal(status.groups, fixture.groups.length);
  runtime('dns-ready', { packages: data, files });
  assert.equal(runtime('diagnostics', { packages: data, files }).output[0].checks.filter(c => c.name === 'dnsmasq').length, 0);
  data.csqtt[fixture.devices[1].id].enabled = '1';
  const one = runtime('compile', { packages: data });
  const oneModel = JSON.parse(one.files['/var/run/csqtt/apply.42/policy.json']);
  const oneStatus = runtime('status', { packages: data, files: { '/etc/csqtt/policy.json': JSON.stringify(oneModel) } }).output[0];
  assert.equal(oneStatus.devices, 1); assert.equal(oneStatus.policies_active, true);
  assert.equal(one.files['/var/run/csqtt/apply.42/dns.ids'], fixture.devices[1].group + '\n');
});

test('device disable and re-enable retain previous/current conntrack flush scope', () => {
  const data = packages();
  const previous = JSON.parse(runtime('compile', { packages: data }).files['/var/run/csqtt/apply.42/policy.json']);
  const files = {
    '/etc/csqtt/policy.json': JSON.stringify(previous),
    '/tmp/dhcp.leases': fixture.devices.map((d, i) => `0 ${d.mac} 192.168.1.${10 + i} client${i} *`).join('\n') + '\n',
  };
  data.csqtt[fixture.devices[0].id].enabled = '0';
  const disabled = runtime('compile', { packages: data, files });
  assert.equal(disabled.files['/var/run/csqtt/apply.42/flush.ips'], '192.168.1.10\n192.168.1.11\n');
  assert.match(disabled.files['/var/run/csqtt/apply.42/hold.nft'], new RegExp(fixture.devices[0].mac));
  assert.doesNotMatch(disabled.files['/var/run/csqtt/apply.42/policy.nft'], new RegExp(fixture.devices[0].mac));
  const disabledModel = JSON.parse(disabled.files['/var/run/csqtt/apply.42/policy.json']);
  data.csqtt[fixture.devices[0].id].enabled = '1';
  const restored = runtime('compile', { packages: data, files: { ...files, '/etc/csqtt/policy.json': JSON.stringify(disabledModel) } });
  assert.equal(restored.files['/var/run/csqtt/apply.42/flush.ips'], '192.168.1.10\n192.168.1.11\n');
  assert.equal(restored.files['/var/run/csqtt/apply.42/policy.json'], JSON.stringify(previous));
});

test('runtime rejects invalid device enabled flags before staging any apply', () => {
  for (const enabled of ['', 'true', 'false', 'yes', '2', 0, 1]) {
    const data = packages(); data.csqtt[fixture.devices[0].id].enabled = enabled;
    assert.throws(() => runtime('compile', { packages: data }), /Device enabled must be 0 or 1/);
    assert.throws(() => runtime('devices', { packages: data }), /Device enabled must be 0 or 1/);
  }
});
