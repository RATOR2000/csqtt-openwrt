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
    f => { f.probe.board = 'other-board'; },
    f => { f.probe.family = 'glinet'; },
    f => { f.probe.capabilities.fw4 = false; },
    f => { f.probe.capabilities.ucode = false; },
    f => { f.probe.capabilities.ucode = 'true'; },
    f => { f.probe.capabilities.dnsmasq_nftset = false; },
    f => { f.installed.dns_binary = '/tmp/untrusted'; },
    f => { f.installed.profile_id = '../untrusted'; },
  ]) {
    const data = qualified(); change(data);
    assert.throws(() => runtime('platform-check', { files: files(data) }), /Exit 1/);
  }
  assert.throws(() => runtime('platform-check'), /Exit 1/);
});

test('private DNS leaves vendor DHCP/DNS configuration untouched and is independently checked', () => {
  const data = qualified(); data.installed.dns_binary = '/usr/libexec/csqtt/dnsmasq';
  data.probe.capabilities.dnsmasq_nftset = false;
  const original = { dhcp: { vendor: { '.type': 'dnsmasq', port: '53', server: 'vendor-dns' } } };
  const inputs = files(data); inputs['/usr/libexec/csqtt/dnsmasq'] = 'ELF';
  const out = runtime('platform', { files: inputs, packages: original });
  assert.equal(out.output[0].state, 'qualified');
  assert.equal(out.output[0].dns_mode, 'private');
  assert.deepEqual(out.packages, original);
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
    const source = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/legacy-backend'), 'utf8')
      .replace('umask 077', `umask 077\nlogger() { :; }\nuci() { printf 'unexpected\\n' >> '${dir}/effects'; }\niptables() { printf 'unexpected\\n' >> '${dir}/effects'; }\nip6tables() { printf 'unexpected\\n' >> '${dir}/effects'; }`)
      .replace('. /usr/libexec/csqtt/lifecycle.sh', 'csqtt_operation_owned() { return 0; }')
      .replace('runtime() { "$UCODE" /usr/share/csqtt/runtime.uc "$@"; }', 'runtime() { return 1; }');
    fs.writeFileSync(`${dir}/backend`, source);
    const result = spawnSync(shell, [`${dir}/backend`, 'stage', '/var/run/csqtt/apply.123'], { encoding: 'utf8' });
    assert.equal(result.status, 1, result.stdout + result.stderr);
    assert.equal(fs.existsSync(`${dir}/effects`), false);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
