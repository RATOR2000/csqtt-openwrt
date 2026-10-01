import test from 'node:test';
import assert from 'node:assert/strict';
import { compiler, fixture } from './harness.mjs';
const { compile, validate, hold } = compiler();
const input = () => structuredClone(fixture);

test('VPN and WAN marks are disjoint; ordered rules precede the default', () => {
  const { nft, model, active } = compile(input());
  assert.equal(active, true);
  const parent = nft.indexOf(`ip daddr @${model.rules[0].set}`);
  const child = nft.indexOf(`ip daddr @${model.rules[1].set}`);
  const ip = nft.indexOf('ip daddr 203.0.113.0/24');
  const fallback = nft.indexOf('add rule inet csqtt g_private meta mark');
  assert.ok(parent < child && child < ip && ip < fallback);
  assert.match(nft, /0x40000000 oifname != "csqtt0" reject/);
  assert.match(nft, /0x60000000 == 0 drop/);
  assert.match(nft, /meta mark set meta mark & 0x9fffffff/);
  assert.doesNotMatch(nft, /ct mark|flow add|flush ruleset/);
});

test('overlapping domain rules populate ancestor sets and use the first DNS action', () => {
  const { dns, model } = compile(input());
  const conf = dns[0].config;
  assert.ok(conf.includes(`nftset=/secure.example.org/4#inet#csqtt#${model.rules[0].set},4#inet#csqtt#${model.rules[1].set}`));
  assert.ok(conf.includes('server=/secure.example.org/9.9.9.9'));
  assert.ok(conf.includes('server=1.1.1.1@198.18.0.1'));
  assert.ok(dns[1].config.includes('server=9.9.9.9\n'));
  assert.ok(dns[1].config.includes('server=/example.net/1.1.1.1@198.18.0.1'));
});

test('same suffix has one dnsmasq directive with every ordered rule set', () => {
  const data = input();
  data.rules.push({ id: 'duplicate_suffix', group: 'private', destination: 'example.org', action: 'vpn' });
  const { dns } = compile(data);
  assert.equal(dns[0].config.split('\n').filter(s => s.startsWith('nftset=/example.org/')).length, 1);
  assert.equal(dns[0].config.split('\n').filter(s => s.startsWith('server=/example.org/')).length, 1);
});

test('domain set names remain stable on reload and change with destinations', () => {
  const before = compile(input());
  assert.doesNotMatch(before.nft, /flush set|delete table/);
  assert.equal(before.model.rules[0].set, compile(input()).model.rules[0].set);
  const next = input(); next.rules[0].destination = 'different.example';
  assert.notEqual(before.model.rules[0].set, compile(next).model.rules[0].set);
});

test('local access precedes fail-closed guards; external IPv6 is blocked for protected groups', () => {
  const { nft } = compile(input());
  assert.ok(nft.indexOf('fib daddr type local return') < nft.indexOf('goto g_private'));
  assert.ok(nft.indexOf('oifname { "br-lan" } return') < nft.indexOf('meta nfproto ipv6 ether saddr'));
  assert.doesNotMatch(nft, /ip6 daddr .* return/);
  assert.match(nft, /meta nfproto ipv6 ether saddr \{ 02:00:00:00:00:01, 02:00:00:00:00:02 \} reject/);
});

test('managed IPv4 and IPv6 DNS are redirected, each listener checks its own MACs', () => {
  const { nft, dns } = compile(input());
  const redirect = nft.split('\n').filter(s => s.includes('add rule inet csqtt dns_redirect'));
  assert.equal(redirect.length, 2);
  assert.ok(redirect.every(s => !s.includes('nfproto ipv4')));
  assert.match(nft, /ether saddr \{ 02:00:00:00:00:01 \} meta l4proto \{ tcp, udp \} th dport 5400 return/);
  assert.match(nft, /th dport 5400-5415 drop/);
  assert.match(nft, /ip saddr 198.18.0.1 oifname != "csqtt0" reject/);
  assert.match(dns[0].config, /server=\/lan\/127.0.0.1/);
  assert.match(dns[0].config, /rebind-domain-ok=\/lan\//);
  assert.match(dns[0].config, /rebind-domain-ok=\/\//);
  assert.doesNotMatch(dns[0].config, /domain-needed/);
  assert.match(dns[0].config, /no-resolv/);
});

test('unassigned clients are not classified or blocked', () => {
  const { nft } = compile({ main: {}, groups: [], devices: [], rules: [] });
  assert.doesNotMatch(nft, /goto g_|ether saddr|nfproto ipv6.*reject/);
  assert.equal(compile({}).active, false);
});

test('maintenance guard closes both old and new clients and retains local routes', () => {
  const old = validate(input()); const next = input(); next.devices[0].mac = '02:00:00:00:00:03';
  const closed = hold([old, validate(next)], true);
  assert.match(closed, /02:00:00:00:00:01/); assert.match(closed, /02:00:00:00:00:03/);
  assert.ok(closed.indexOf('192.168.1.0/24') < closed.indexOf('ether saddr'));
  assert.match(closed, /priority -20/);
  assert.doesNotMatch(closed, /ip6 daddr .* return/);
  assert.doesNotMatch(hold([], false), /reject/);
});

test('invalid UCI values cannot inject nft or DNS configuration', () => {
  for (const value of ['example.org\nserver=8.8.8.8', 'example.org; accept', '../bad', 'bad..example', '-bad.example', '256.1.1.1/32', '1.1.1.1/33']) {
    const data = input(); data.rules[0].destination = value;
    assert.throws(() => compile(data), undefined, value);
  }
  for (const value of ['br-lan"; accept', 'br-lan\nserver=1', 'abcdefghijklmnop']) {
    const data = input(); data.main.lan_device = value; assert.throws(() => compile(data));
  }
  for (const value of ['01:00:00:00:00:01', '00:00:00:00:00:00', 'bad']) {
    const data = input(); data.devices[0].mac = value; assert.throws(() => compile(data));
  }
});

test('IPv4 prefixes are canonical before being emitted to nftables', () => {
  const data = input(); data.rules[2].destination = '203.0.113.177/24';
  data.local_subnets = ['192.168.1.255/24'];
  const out = compile(data);
  assert.equal(out.model.rules[2].value, '203.0.113.0/24');
  assert.deepEqual([...out.model.locals], ['192.168.1.0/24']);
  assert.ok(out.nft.includes('ip daddr 203.0.113.0/24'));
});

test('local DNS suffix stays delegated and cannot be replaced by internet rules', () => {
  for (const [localDomain, destination] of [['lan', 'printer.lan'], ['Home.Example', 'home.example'], ['Home.Example', 'printer.home.example']]) {
    const data = input(); data.local_domain = localDomain; data.rules[0].destination = destination;
    assert.throws(() => compile(data), /Local DNS domains/);
  }
  const data = input(); data.local_domain = 'Home.Example';
  assert.equal(compile(data).model.local_domain, 'home.example');
  for (const localDomain of ['-lan', 'lan-', 'bad..lan', 'lan\nserver=8.8.8.8']) {
    data.local_domain = localDomain;
    assert.throws(() => compile(data), /local DNS domain/);
  }
});

test('duplicate membership, unknown groups, rule IDs and resource excess are rejected', () => {
  const duplicate = input(); duplicate.devices[1].mac = duplicate.devices[0].mac; assert.throws(() => compile(duplicate));
  const missing = input(); missing.rules[0].group = 'missing'; assert.throws(() => compile(missing));
  const duplicateId = input(); duplicateId.rules[1].id = duplicateId.rules[0].id; assert.throws(() => compile(duplicateId));
  const excess = input(); excess.rules = Array.from({ length: 129 }, (_, i) => ({ id: `r${i}` })); assert.throws(() => compile(excess));
  const disabled = input(); disabled.rules[0].enabled = '0'; assert.equal(compile(disabled).model.rules.length, 3);
});
