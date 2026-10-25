import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execFileSync, spawnSync } from 'node:child_process';
import { compiler, fixture, runtime, root } from './harness.mjs';

function qualified() {
  const probe = { schema: 1, family: 'official', firmware: '25.12.6', openwrt: '25.12.6',
    board: 'generic,x86-64', target: 'x86/64', architecture: 'x86_64', package_manager: 'apk',
    backend: 'fw4-nft', kernel: '6.12.94', capabilities: { ucode: true, procd: true, netifd: true,
      nft: true, fw4: true, dnsmasq_nftset: true }, resource: { mem_total_kib: 1000000, cpu_count: 2 } };
  const installed = { ...probe, schema: 1, profile_id: 'test-x86-64',
    qualification: { activation: true }, dns_binary: '/usr/sbin/dnsmasq' };
  return { probe, installed };
}
function files({ probe, installed }) {
  return { '/var/run/csqtt/platform-probe.json': JSON.stringify(probe),
    '/etc/csqtt/platform.json': JSON.stringify(installed), '/usr/sbin/dnsmasq': 'ELF' };
}

test('activation requires exact authenticated qualification and actual local capabilities', () => {
  const good = qualified(); runtime('platform-check', { files: files(good) });
  for (const change of [
    f => { f.installed.qualification.activation = false; },
    f => { f.probe.kernel = 'new-kernel'; },
    f => { f.probe.family = 'glinet'; },
    f => { f.probe.capabilities.fw4 = false; },
    f => { f.probe.capabilities.ucode = false; },
    f => { f.probe.capabilities.ucode = 'true'; },
    f => { f.probe.capabilities.dnsmasq_nftset = false; },
    f => { f.installed.dns_binary = '/tmp/untrusted'; },
    f => { f.installed.profile_id = '../untrusted'; },
    f => { f.probe.family = f.installed.family = 'glinet'; },
    f => { f.probe.openwrt = f.installed.openwrt = '26.01.0'; },
    f => { f.probe.openwrt = f.installed.openwrt = '25.12-SNAPSHOT'; },
    f => { f.probe.package_manager = f.installed.package_manager = 'opkg'; },
  ]) {
    const data = qualified(); change(data);
    assert.throws(() => runtime('platform-check', { files: files(data) }), /Exit 1/);
  }
  assert.throws(() => runtime('platform-check'), /Exit 1/);
});

test('official ABI profiles do not use the router model as an activation lock', () => {
  const data = qualified(); data.probe.board = 'another-vendor,another-router';
  assert.equal(runtime('platform', { files: files(data) }).output[0].state, 'qualified');
  data.probe.openwrt = data.installed.openwrt = '24.10.5';
  data.probe.firmware = data.installed.firmware = '24.10.5';
  data.probe.package_manager = data.installed.package_manager = 'opkg';
  assert.equal(runtime('platform', { files: files(data) }).output[0].state, 'qualified');
  data.probe.architecture = 'arm_cortex-a7_neon-vfpv4';
  assert.throws(() => runtime('platform-check', { files: files(data) }), /Exit 1/, 'ABI changes still require the signed installer');
});

test('new runtime package has no active private ucode or legacy firewall path', () => {
  const makefile = fs.readFileSync(path.join(root, 'openwrt/csqtt/Makefile'), 'utf8');
  assert.doesNotMatch(makefile, /CSQTT_RUNTIME_DIR|legacy-backend/);
  assert.match(makefile, /CSQTT_DNSMASQ_LICENSE/);
  assert.match(makefile, /CSQTT_DNSMASQ_NOTICE/);
  const policy = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/policy.uc'), 'utf8');
  assert.doesNotMatch(policy, /compile_legacy|hold_legacy|legacy_guard|iptables|ipset=/);
  for (const file of ['manage', 'csqtt.init', 'monitor'])
    assert.doesNotMatch(fs.readFileSync(path.join(root, 'openwrt/csqtt/files', file), 'utf8'), /libexec\/csqtt\/ucode/);
  const data = qualified(); data.probe.backend = data.installed.backend = 'legacy-xtables';
  assert.throws(() => runtime('platform-backend', { files: files(data) }), /Exit 1/);
  const compiled = runtime('compile', { files: files(data) });
  assert.ok(compiled.files['/var/run/csqtt/apply.42/policy.nft']);
  assert.equal(compiled.files['/var/run/csqtt/apply.42/policy.v4'], undefined);
});

test('first-run public flag preserves stopped existing configurations and contains no credentials', () => {
  for (const workers of ['auto', '9', '72']) {
    const main = { '.type': 'client', enabled: '0', workers, peer: 'server.example:443', password: 'not-a-real-password', vk_hashes: ['not_a_real_call_hash'] };
    const result = runtime('status', { packages: { csqtt: { main } } });
    assert.equal(result.output[0].setup_required, false);
    assert.equal(result.packages.csqtt.main.workers, workers);
    assert.doesNotMatch(JSON.stringify(result.output), /not-a-real-password|not_a_real_call_hash|server\.example/);
  }
  assert.equal(runtime('status').output[0].setup_required, true);
  assert.equal(runtime('status', { packages: { csqtt: { main: { '.type': 'client', setup_complete: '1' } } } }).output[0].setup_required, false);
});

test('private DNS leaves vendor DHCP/DNS configuration untouched and is independently checked', () => {
  const data = qualified(); data.installed.dns_binary = '/usr/libexec/csqtt/dnsmasq';
  data.probe.capabilities.dnsmasq_nftset = false;
  data.probe.capabilities.private_dnsmasq_nftset = true;
  const original = { dhcp: { vendor: { '.type': 'dnsmasq', port: '53', server: 'vendor-dns' } } };
  const inputs = files(data); inputs['/usr/libexec/csqtt/dnsmasq'] = 'ELF';
  const out = runtime('platform', { files: inputs, packages: original });
  assert.equal(out.output[0].state, 'qualified');
  assert.equal(out.output[0].dns_mode, 'private');
  assert.deepEqual(out.packages, original);
  data.probe.capabilities.private_dnsmasq_nftset = false;
  assert.throws(() => runtime('platform-check', { files: { ...inputs, '/var/run/csqtt/platform-probe.json': JSON.stringify(data.probe) } }), /Exit 1/);
  delete inputs['/usr/libexec/csqtt/dnsmasq'];
  assert.throws(() => runtime('platform-check', { files: inputs }), /Exit 1/);
});

test('new automatic worker profile keeps protocol minimum and never changes explicit existing choices', () => {
  for (const selected of ['auto', '9', '72', '126']) {
    const data = { csqtt: { main: { '.type': 'client', enabled: '0', workers: selected,
      vk_hashes: Array.from({ length: 6 }, (_, i) => 'test_call_hash_1234_' + i) } } };
    const out = runtime('compile', { packages: data });
    assert.equal(JSON.parse(out.files['/var/run/csqtt/apply.42/client.json']).workers, selected === 'auto' ? 9 : +selected);
    assert.equal(out.packages.csqtt.main.workers, selected);
  }
});

test('Helper selects configured physical LAN rather than logical interface named lan', () => {
  const network = { interface: [
    { interface: 'lan', l3_device: 'br-other', 'ipv4-address': [{ address: '192.0.2.1' }] },
    { interface: 'management', l3_device: 'br-private', 'ipv4-address': [{ address: '192.168.8.1' }] },
  ] };
  const packages = { csqtt: { main: { '.type': 'client', lan_device: ['br-private'] } } };
  assert.equal(runtime('helper-address', { packages, network }).output[0], '192.168.8.1');
  network.interface[1].up = false;
  assert.throws(() => runtime('helper-address', { packages, network }), /Exit 1/);
  for (const file of ['csqtt-captcha.init', '91-csqtt-captcha'])
    assert.doesNotMatch(fs.readFileSync(path.join(root, 'openwrt/csqtt-captcha/files', file), 'utf8'), /network\.interface\.lan|\[ "\$INTERFACE" = lan \]/);
});

test('automatic LAN scope uses trusted static netifd networks and excludes WAN without names or board assumptions', () => {
  const packages = { csqtt: { main: { '.type': 'client', enabled: '0', lan_device: 'auto' } },
    firewall: {
      private: { '.type': 'zone', input: 'ACCEPT', network: ['home', 'management', 'uplink', 'dynamic', 'down'] },
      guest: { '.type': 'zone', input: 'REJECT', network: ['guests'] },
      wan: { '.type': 'zone', input: 'ACCEPT', masq: '1', network: ['outside'] }
    } };
  const local = (name, device, extra = {}) => ({ interface: name, l3_device: device, up: true, proto: 'static',
    'ipv4-address': [{ address: '192.168.8.1', mask: 24 }], ...extra });
  const network = { interface: [local('home', 'br-private'), local('management', 'eth1.20'), local('guests', 'br-guest'),
    local('outside', 'eth0'), local('uplink', 'eth2', { route: [{ target: '0.0.0.0', mask: 0 }] }),
    local('dynamic', 'eth3', { proto: 'dhcp' }), local('down', 'eth4', { up: false })] };
  const result = runtime('devices', { packages, network, files: { '/tmp/dhcp.leases':
    '0 02:00:00:00:00:01 192.168.8.10 home *\n0 02:00:00:00:00:02 192.168.9.10 guest *\n' } }).output[0];
  assert.deepEqual(result.lan_devices, ['br-private', 'eth1.20']);
  assert.deepEqual(result.devices.map(device => device.mac), ['02:00:00:00:00:01'], 'unprotected DHCP networks are not offered as VPN devices');
  const compiled = runtime('compile', { packages, network });
  const policy = JSON.parse(compiled.files['/var/run/csqtt/apply.42/policy.json']);
  assert.deepEqual(policy.lans, ['br-private', 'eth1.20']);
  assert.equal(compiled.packages.csqtt.main.lan_device, 'auto', 'read/compile never rewrites saved settings');
  assert.equal(runtime('helper-address', { packages, network }).output[0], '192.168.8.1');
  assert.throws(() => runtime('compile', { packages, network: { interface: [] } }), /At least one LAN device/);
  packages.csqtt.main.lan_device = ['br-fixed'];
  assert.deepEqual(runtime('devices', { packages, network }).output[0].lan_devices, ['br-fixed']);
});

test('legacy rendering preserves ordered marks, private DNS, IPv6 and output guards without replacing vendor chains', () => {
  const { compile_legacy } = compiler(), result = compile_legacy(fixture);
  assert.match(result.ipv4, /-A CSQ_OUTPUT -s 198\.18\.0\.1\/32 ! -o csqtt0 -j REJECT/);
  assert.match(result.ipv4, /--mark 0x40000000\/0x60000000 ! -o csqtt0 -j REJECT/);
  assert.match(result.ipv4, /--mark 0x0\/0x60000000 -j DROP/);
  assert.match(result.ipv4, /--set-xmark 0x20000000\/0x60000000/);
  assert.match(result.ipv6, /-A CSQ_FORWARD .* -j REJECT/);
  assert.match(result.ipv6, /-A CSQ_INPUT .* --dport 53 -j REJECT/);
  assert.doesNotMatch(result.ipv4 + result.ipv6, /^:(FORWARD|INPUT|OUTPUT|PREROUTING|POSTROUTING)|^-F (FORWARD|INPUT|OUTPUT|PREROUTING|POSTROUTING)$/m);
  assert.match(result.ipset, /create csq_[0-9]+ hash:net family inet/);
  for (const dns of result.dns) {
    assert.doesNotMatch(dns.config, /nftset=|dhcp-range=/);
    assert.match(dns.config, /no-resolv/);
  }
  assert.ok(result.dns.some(d => /ipset=\/.+\/csq_[0-9]+/.test(d.config)));
  assert.ok(result.dns.some(d => /server=.*@198\.18\.0\.1/.test(d.config)));
});

test('legacy maintenance guards cover old and proposed clients while preserving LAN management', () => {
  const { compile_legacy, hold_legacy } = compiler(), model = compile_legacy(fixture).model;
  for (const ipv6 of [true, false]) {
    const closed = hold_legacy([model], true, ipv6);
    assert.match(closed, /-A CSQ_HOLD -o br-lan -j RETURN/);
    assert.match(closed, /-A CSQ_HOLD .*--mac-source .* -j REJECT/);
    assert.match(closed, /-A CSQ_HOLD_DNS .*--dports 53,5400:5415 -j REJECT/);
    assert.doesNotMatch(hold_legacy([], false, ipv6), /-A CSQ_HOLD/);
  }
  const data = qualified(); data.probe.backend = data.installed.backend = 'legacy-xtables';
  assert.throws(() => runtime('platform-check', { files: files(data) }), /Exit 1/, 'Rendered rules alone never qualify a native backend');
});

test('platform status redacts unknown fields and malformed input values', () => {
  const data = qualified(); data.probe.secret = 'MUST_NOT_EXPORT'; data.probe.family = 'MUST_NOT_EXPORT\n';
  data.probe.resource.secret = 'MUST_NOT_EXPORT'; data.probe.resource.mem_total_kib = 'MUST_NOT_EXPORT';
  const out = runtime('status', { files: files(data) });
  assert.equal(JSON.stringify(out.output).includes('MUST_NOT_EXPORT'), false);
});

test('legacy backend admission rejects unqualified activation before touching hardware or firewall', () => {
  const git = process.platform === 'win32' ? execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0] : '';
  const shell = process.platform === 'win32' ? ['../bin/sh.exe', '../usr/bin/sh.exe']
    .map(p => path.resolve(path.dirname(git), p)).find(p => fs.existsSync(p)) : '/bin/sh';
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'csqtt-legacy-gate-')).replaceAll('\\', '/');
  try {
    const source = fs.readFileSync(path.join(root, 'experiments/glinet/legacy-backend'), 'utf8')
      .replace('umask 077', `umask 077\nlogger() { :; }\nuci() { printf 'unexpected\\n' >> '${dir}/effects'; }\niptables() { printf 'unexpected\\n' >> '${dir}/effects'; }\nip6tables() { printf 'unexpected\\n' >> '${dir}/effects'; }`)
      .replace('. /usr/libexec/csqtt/lifecycle.sh', 'csqtt_operation_owned() { return 0; }')
      .replace('runtime() { "$UCODE" /usr/share/csqtt/runtime.uc "$@"; }', 'runtime() { return 1; }');
    fs.writeFileSync(`${dir}/backend`, source);
    const result = spawnSync(shell, [`${dir}/backend`, 'stage', '/var/run/csqtt/apply.123'], { encoding: 'utf8' });
    assert.equal(result.status, 1, result.stdout + result.stderr);
    assert.equal(fs.existsSync(`${dir}/effects`), false);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
