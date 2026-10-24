const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const resources = path.resolve(__dirname, '../../openwrt/luci-app-csqtt/htdocs/luci-static/resources');
const extend = { extend: value => value };
function load(file, dependencies) {
  return new Function(...Object.keys(dependencies), fs.readFileSync(path.join(resources, file), 'utf8'))(...Object.values(dependencies));
}
class Node {
  constructor(tag, attrs, children) { this.tag = tag; this.attrs = attrs || {}; this.children = [children].flat(Infinity).filter(v => v != null); this.value = ''; }
  appendChild(node) { this.children.push(node); }
  replaceChildren(...nodes) { this.children = nodes.flat(Infinity); }
  click() { return this.attrs.click?.(); }
}
const E = (tag, attrs, children) => new Node(tag, attrs, children);
const walk = node => node instanceof Node ? [node, ...node.children.flatMap(walk)] : [];
const text = node => node instanceof Node ? node.children.map(text).join(' ') : String(node);
const hash = 'synthetic_call_hash_for_wizard';
function harness({ main = {}, saved = {}, status = { enabled: true, health: { state: 'healthy' } }, statusNever = false, lans = ['br-home'] } = {}) {
  let now = 1000000, idx = 0;
  const timers = new Map(), events = [], handlers = {};
  const clock = { now: () => now };
  const window = {
    setTimeout(fn, delay) { const id = ++idx; timers.set(id, { fn, at: now + delay }); return id; },
    clearTimeout(id) { timers.delete(id); }, addEventListener(name, fn) { handlers[name] = fn; }
  };
  const model = load('csqtt/model.js', { baseclass: extend, Date: clock });
  const config = { main: { '.type': 'client', enabled: '0', workers: 'auto', auto_recover: '0', lan_device: 'auto', ...main }, ...structuredClone(saved) };
  const uci = {
    get(_pkg, id, key) { return key ? config[id]?.[key] : config[id]; },
    sections(_pkg, type) { return Object.entries(config).filter(([, value]) => value['.type'] === type).map(([id, value]) => ({ ...value, '.name': id })); },
    set(_pkg, id, key, value) { events.push(['set', id, key]); config[id][key] = value; },
    add(_pkg, type, name) { name ||= 'new' + (++idx); assert.equal(config[name], undefined); config[name] = { '.type': type }; return name; },
    async save() { events.push('save'); }
  };
  const api = {
    async commitConfig() { events.push('commit:csqtt'); },
    call(method) {
      events.push(method);
      if (method === 'start') { config.main.enabled = '1'; return Promise.resolve({ ok: true }); }
      if (statusNever) return new Promise(() => {});
      return Promise.resolve(status);
    }
  };
  const view = load('view/csqtt/setup.js', { view: extend, uci, api, model, E, window, Date: clock,
    L: { url: path => '/' + path, resource: path => path }, ui: { createHandlerFn: (ctx, fn) => (...args) => fn.apply(ctx, args) } });
  const page = view.render([null, { lan_devices: lans, devices: [
    { name: '<img onerror=attack>', mac: '02:00:00:00:00:01', ip: '192.168.1.5' },
    { name: 'duplicate', mac: '02:00:00:00:00:01' }, { mac: 'ff:ff:ff:ff:ff:ff' }
  ] }]);
  const button = label => walk(page).find(node => node.tag === 'button' && text(node) === label);
  const field = label => walk(page).find(node => node.attrs['aria-label'] === label);
  async function tick(ms) {
    const until = now + ms;
    for (;;) {
      const next = [...timers.entries()].sort((a, b) => a[1].at - b[1].at).find(([, timer]) => timer.at <= until);
      if (!next) break;
      now = next[1].at; timers.delete(next[0]); next[1].fn();
      for (let n = 0; n < 8; n++) await Promise.resolve();
    }
    now = until;
    for (let n = 0; n < 8; n++) await Promise.resolve();
  }
  async function details() {
    field('Адрес сервера').value = 'server.example:443'; field('Пароль подключения').value = 'synthetic-password';
    field('Ссылка на звонок 1').value = 'https://vk.com/call/join/' + hash;
    await button('Далее: устройства').click();
  }
  return { view, page, button, field, events, config, timers, handlers, tick, details, model };
}

test('wizard navigates without writes, validates secrets and enables only after final user action', async () => {
  const h = harness();
  await h.button('Далее: устройства').click();
  assert.match(text(h.page), /Проверьте адрес/); assert.deepEqual(h.events, []);
  await h.details();
  const check = walk(h.page).find(node => node.attrs.type === 'checkbox');
  assert.equal(walk(h.page).filter(node => node.attrs.type === 'checkbox').length, 1, 'invalid/duplicate device identities are excluded');
  check.attrs.change({ target: { checked: true } });
  await h.button('Далее: подключение').click();
  assert.equal(h.config.main.enabled, '0'); assert.deepEqual(h.events, []);
  await h.button('Завершить и подключить').click();
  assert.deepEqual(h.events.filter(value => typeof value === 'string'), ['save', 'commit:csqtt', 'start', 'status']);
  assert.equal(h.config.main.enabled, '1'); assert.equal(h.config.main.setup_complete, '1');
  assert.equal(h.config.main.workers, 'auto'); assert.equal(h.config.main.auto_recover, '0');
  assert.deepEqual(h.config.main.lan_device, ['br-home']);
  assert.equal(h.config.setupvpn.default_action, 'vpn');
  const device = Object.values(h.config).find(value => value['.type'] === 'device');
  assert.equal(device.group, 'setupvpn'); assert.equal(device.mac, '02:00:00:00:00:01');
  assert.equal(h.config.main.vk_hashes[0], hash);
  assert.match(text(h.page), /DNS и HTTPS через VPN доступны/);
  assert.doesNotMatch(text(h.page), /synthetic-password|synthetic_call_hash/);
  const { compiler } = await import('../policy/harness.mjs');
  const policy = compiler().compile({ main: { lan_device: ['br-lan'] }, groups: [{ id: 'setupvpn', ...h.config.setupvpn }], devices: [{ id: 'device1', ...device }] });
  assert.equal(policy.active, true); assert.match(policy.nft, /oifname != "csqtt0" reject/);
  assert.match(policy.nft, /meta nfproto ipv6.*reject/);
  assert.doesNotMatch(policy.nft, /02:00:00:00:00:02/, 'unassigned clients stay outside VPN membership');
});

test('already configured stopped r9 bypasses wizard and preserves explicit parameters and policies', () => {
  const h = harness({ main: { peer: 'existing.example:443', password: 'old-password', vk_hashes: [hash], workers: '72', auto_recover: '1' }, saved: { office: { '.type': 'group', name: 'Работа', default_action: 'wan' } } });
  assert.match(text(h.page), /уже настроен/); assert.equal(h.button('Завершить и подключить'), undefined);
  assert.equal(h.config.main.enabled, '0'); assert.equal(h.config.main.workers, '72'); assert.equal(h.config.main.auto_recover, '1');
  assert.equal(h.config.office.default_action, 'wan'); assert.deepEqual(h.events, []);
});

test('CAPTCHA is explicit and only confirmed health completes the check', async () => {
  const h = harness({ status: { enabled: true, core: { state: 'captcha_required', captcha: { id: 'public-challenge', expires_at: 2000 } }, health: { state: 'unknown' } } });
  await h.details(); await h.button('Далее: подключение').click(); await h.button('Завершить и подключить').click();
  assert.match(text(h.page), /ВКонтакте запросил CAPTCHA/);
  assert.match(text(h.page), /не считает подключение проверенным/);
  assert.ok(walk(h.page).some(node => node.tag === 'a' && text(node) === 'Открыть обзор и CAPTCHA'));
  assert.equal(h.events.includes('captcha_begin'), false, 'no pairing grant is minted without a separate human action');
  assert.equal(h.model.setupCheck({ enabled: true, core: { state: 'connected', active_workers: 9 } }), 'waiting');
});

test('a partial CAPTCHA remains visible alongside confirmed VPN availability', async () => {
  const h = harness({ status: { enabled: true, core: { state: 'connected', active_workers: 9,
    captcha: { id: 'public-challenge', expires_at: 2000 } }, health: { state: 'healthy' } } });
  await h.details(); await h.button('Далее: подключение').click(); await h.button('Завершить и подключить').click();
  assert.match(text(h.page), /DNS и HTTPS через VPN доступны/);
  assert.match(text(h.page), /Для части соединений VK запрашивает CAPTCHA/);
  assert.ok(walk(h.page).some(node => node.tag === 'a' && text(node) === 'Открыть обзор и CAPTCHA'));
});

test('status checks stop after 90 seconds even if RPC never replies, and leaving page cancels future checks', async () => {
  const h = harness({ statusNever: true });
  await h.details(); await h.button('Далее: подключение').click();
  const finishing = h.button('Завершить и подключить').click();
  for (let i = 0; i < 12; i++) await Promise.resolve();
  await h.tick(90000); await finishing;
  assert.match(text(h.page), /За 90 секунд/); const count = h.events.filter(value => value === 'status').length;
  await h.tick(120000); assert.equal(h.events.filter(value => value === 'status').length, count);
  const leaving = harness({ status: { enabled: true, core: { state: 'connecting' } } });
  await leaving.details(); await leaving.button('Далее: подключение').click(); await leaving.button('Завершить и подключить').click();
  leaving.handlers.pagehide(); await leaving.tick(120000);
  assert.equal(leaving.events.filter(value => value === 'status').length, 1);
});

test('partial saved assignments stay unchanged and safe stable group IDs avoid collisions', async () => {
  const saved = { setupvpn: { '.type': 'group', name: 'Работа', default_action: 'wan' }, old: { '.type': 'device', name: 'Телефон', mac: '02:00:00:00:00:09', group: 'setupvpn', enabled: '0' } };
  const h = harness({ saved, main: { workers: '9' } });
  await h.details(); walk(h.page).find(node => node.attrs.type === 'checkbox').attrs.change({ target: { checked: true } });
  await h.button('Далее: подключение').click(); await h.button('Завершить и подключить').click();
  assert.deepEqual(h.config.setupvpn, saved.setupvpn); assert.deepEqual(h.config.old, saved.old);
  assert.equal(h.config.setupvpn1.default_action, 'vpn'); assert.equal(h.config.main.workers, '9');
});

test('first setup refuses unresolved LAN before writing or starting and preserves explicit LAN choices', async () => {
  const unknown = harness({ lans: [] });
  await unknown.details(); await unknown.button('Далее: подключение').click(); await unknown.button('Завершить и подключить').click();
  assert.match(text(unknown.page), /Не удалось определить локальную сеть/); assert.deepEqual(unknown.events, []);
  assert.equal(unknown.config.main.enabled, '0');
  const manual = harness({ main: { lan_device: ['br-office', 'eth1.20'] }, lans: ['br-home'] });
  await manual.details(); await manual.button('Далее: подключение').click(); await manual.button('Завершить и подключить').click();
  assert.deepEqual(manual.config.main.lan_device, ['br-office', 'eth1.20']);
  assert.equal(manual.config.main.enabled, '1');
});

test('config commit helper has one fixed package and does not broaden the custom RPC ACL', async () => {
  const declarations = [], calls = [];
  const api = load('csqtt/api.js', { baseclass: extend, rpc: { declare(spec) { declarations.push(spec); return async (...args) => { calls.push({ spec, args }); return {}; }; } } });
  await api.commitConfig();
  assert.equal(calls[0].spec.object, 'uci'); assert.equal(calls[0].spec.method, 'commit'); assert.deepEqual(calls[0].args, ['csqtt']);
  assert.equal(declarations.filter(spec => spec.object === 'uci').length, 1);
  const acl = JSON.parse(fs.readFileSync(path.resolve(resources, '../../../root/usr/share/rpcd/acl.d/luci-app-csqtt.json')))['luci-app-csqtt'];
  assert.deepEqual(acl.write.uci, ['csqtt']); assert.equal(acl.write.ubus.csqtt.includes('exec'), false);
});
