const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const guest = fs.readFileSync('scripts/test-openwrt-guest.sh', 'utf8');
const source = guest.match(/<<'UCODE_GUARD'\n([\s\S]+?)\nUCODE_GUARD/)[1].replace(/^import .*;\n/, '');
const mac = { match: { op: '==', left: { payload: { protocol: 'ether', field: 'saddr' } }, right: '02:00:00:00:aa:01' } };
const family = { match: { op: '==', left: { meta: { key: 'nfproto' } }, right: 'ipv6' } };
const reject = { reject: { type: 'icmpx', expr: 'port-unreachable' } };
const canonical = { reject: { type: 'icmpv6', expr: 'port-unreachable' } };
const rule = (expr, extra = {}) => ({ rule: { family: 'inet', table: 'csqtt', chain: 'forward_guard', expr, ...extra } });
function check(rows) {
  const context = { fs: { readfile: () => JSON.stringify({ nftables: rows }) }, ARGV: ['fixture'],
    json: JSON.parse, length: x => x.length, type: x => Array.isArray(x) ? 'array' : typeof x,
    index: (a,b) => a.indexOf(b), keys: Object.keys, printf() {}, exit(code) { throw { expectedExit: true, code }; } };
  try { vm.runInNewContext(source, context); } catch (e) { if (e.expectedExit) return e.code; throw e; }
  throw new Error('Guard validator must return a verdict');
}
test('installed IPv6 guard accepts explicit and nft canonical equivalent rules', () => {
  assert.equal(check([rule([family, mac, reject])]), 0);
  assert.equal(check([rule([mac, canonical])]), 0);
  assert.equal(check([rule([{ match: { op: '==', left: { payload: { protocol: 'ether', field: 'type' } }, right: 'ip6' } }, mac, reject])]), 0);
});
test('installed IPv6 guard requires MAC, family and reject in the same owned rule', () => {
  for (const rows of [[], [rule([canonical])], [rule([family, mac])], [rule([mac, reject])],
    [rule([family]), rule([mac, reject])], [rule([mac, canonical], { chain: 'other' })],
    [rule([mac, canonical], { family: 'ip6' })], [rule([mac, canonical], { table: 'other' })],
    [rule([{ match: { ...mac.match, op: '!=' } }, canonical])],
    [rule([{ match: { ...mac.match, right: '02:00:00:00:aa:02' } }, canonical])]]) {
    assert.equal(check(rows), 1, JSON.stringify(rows));
  }
});
