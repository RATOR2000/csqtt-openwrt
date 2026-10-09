const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Match LuCI's module factory argument scope; URL remains the browser builtin.
const source = fs.readFileSync(path.resolve(__dirname, '../../openwrt/luci-app-csqtt/htdocs/luci-static/resources/csqtt/model.js'), 'utf8');
const model = new Function('window', 'document', 'L', 'baseclass', source)(
  { URL }, {}, {}, { extend: value => value }
);
const hash = 'Dummy_call_hash_0123456789abcdef';

test('full VK call links normalize both VK domains without changing their hash', () => {
  for (const host of ['vk.com', 'm.vk.com', 'vk.ru', 'm.vk.ru']) {
    for (const suffix of ['', '?source=test', '#test']) {
      const link = `https://${host}/call/join/${hash}${suffix}`;
      assert.equal(model.validCallLink(link), true);
      assert.equal(model.normalizeHash(link), hash);
      assert.equal(model.callLink(link), `https://vk.com/call/join/${hash}`);
    }
  }
  assert.equal(model.validCallLink(`  HTTPS://VK.RU/call/join/${hash}  `), true);
  assert.equal(model.validCallLink(`http://m.vk.ru/call/join/${hash}`), true);
  assert.equal(model.normalizeHash(hash), hash, 'existing UCI stores the raw hash');
  assert.equal(model.validCallLink(hash), false, 'full-link fields require a complete URL');
});

test('VK call links retain host, credential, port and path guards', () => {
  for (const link of [
    `https://vk.ru.evil.example/call/join/${hash}`, `https://evilvk.ru/call/join/${hash}`,
    `https://vk.com@evil.example/call/join/${hash}`, `https://name@vk.ru/call/join/${hash}`,
    `https://name:credential@vk.ru/call/join/${hash}`, `https://vk.ru:444/call/join/${hash}`,
    `ftp://vk.ru/call/join/${hash}`, `https://vk.ru/call/join/${hash}/extra`,
    `https://vk.ru/call/join/short`, `https://vk.ru/call/join/${'a'.repeat(1025)}`,
    `https://vk.ru/call/join/${hash}!`, `https://vk.ru/other/${hash}`
  ]) assert.equal(model.validCallLink(link), false);
});

test('traffic uses familiar decimal byte units at the exact 1000 boundaries', () => {
  for (const [bytes, label] of [
    [0, '0 Б'], [1, '1 Б'], [999, '999 Б'], [1000, '1.0 Кб'], [1024, '1.0 Кб'],
    [1500, '1.5 Кб'], [999999, '1000.0 Кб'], [1000000, '1.0 Мб'], [1250000, '1.3 Мб'],
    [999999999, '1000.0 Мб'], [1000000000, '1.0 Гб'], [1500000000, '1.5 Гб'],
    [1000000000000, '1000.0 Гб']
  ]) assert.equal(model.bytes(bytes), label, `${bytes} bytes`);
  assert.equal(model.bytes('2500000'), '2.5 Мб');
  assert.equal(model.bytes(undefined), '0 Б');
  assert.equal(model.bytes(null), '0 Б');
  for (const invalid of [-1, NaN, Infinity, -Infinity, 'not a number', 'Infinity'])
    assert.equal(model.bytes(invalid), '—');
});
