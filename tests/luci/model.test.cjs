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
