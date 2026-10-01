/* Run: node --test tests/luci/luci.test.cjs. No browser or npm packages needed. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../openwrt/luci-app-csqtt');
const resources = path.join(root, 'htdocs/luci-static/resources');
const extend = { extend: value => value };
function load(file, dependencies = {}) {
	const names = Object.keys(dependencies);
	return new Function(...names, fs.readFileSync(path.join(resources, file), 'utf8'))(...names.map(name => dependencies[name]));
}
const model = load('csqtt/model.js', { baseclass: extend });
const hash = 'Abcdefghijklmnopqrstuvwxyz_012345';
const hash2 = 'Another_abcdefghijklmnopqrstuv99';
const link = (extra = '') => `csqtt://connect?v=2&host=vpn.example&peer=046000&password=a%2Bb%26c${extra}`;

test('Android import preserves encoded credentials, normalizes port and VK link hashes', () => {
	assert.deepEqual(model.parseLink(link('&hashes=' + encodeURIComponent('https://vk.com/call/join/' + hash + '?source=test') + '+' + hash2)), {
		peer: 'vpn.example:46000', password: 'a+b&c', vk_hashes: [hash, hash2]
	});
	assert.equal(model.parseLink(link().replaceAll('&', '&amp;')).password, 'a+b&c');
	assert.equal(model.parseLink(link().replaceAll('&', ';')).peer, 'vpn.example:46000');
	assert.equal(model.parseLink(link().replace('vpn.example', '%5B2001%3Adb8%3A%3A1%5D')).peer, '[2001:db8::1]:46000');
	assert.equal(model.parseLink(link()).vk_hashes, null, 'an import without hashes must preserve form hashes');
	assert.equal(model.parseLink(`csqtt://connect?v=2host=vpn.examplepeer=46000password=abcdhashes=${hash}`).vk_hashes[0], hash);
});

test('malformed imports fail with a generic error without echoing secrets', () => {
	const bad = [
		link('&host=other.example'), link('&unknown=secret'), link('&__proto__=secret'),
		link().replace('v=2', 'v=1'), link().replace('v=2', 'v=2%'),
		link().replace('046000', '0'), link().replace('046000', '65536'),
		link().replace('vpn.example', 'bad%0Ahost'), link().replace('vpn.example', '127.1'),
		link().replace('vpn.example', 'evil.example%2Fpath'), link().replace('vpn.example', 'user%40host'),
		link().replace('a%2Bb%26c', 'supersecret%7Cpassword'), link().replace('a%2Bb%26c', 'abc'),
		link('&hashes=' + hash + '+' + hash), link('&hashes=short'), link('&hashes=%3Cscript%3Esecret'),
		link('&hashes=' + Array(7).fill(hash).join('+')), link('&hashes=' + 'a'.repeat(1025)),
		link() + '#secret', 'javascript:alert(1)', 'csqtt://connect?v=2&password=secret', 'x'.repeat(16385)
	];
	for (const input of bad) assert.throws(() => model.parseLink(input), error => {
		assert.doesNotMatch(error.message, /supersecret|javascript|script|a%2B|vpn\.example/);
		return /Некорректная ссылка/.test(error.message);
	});
});

test('settings enforce core capacity, password bytes and valid addresses', () => {
	assert.equal(model.workerLimit(1), 27);
	assert.equal(model.workerLimit(4), 108);
	assert.equal(model.workerLimit(6), 126);
	assert.equal(model.workerLimit(0), 0);
	assert.equal(model.validHashes([hash, hash2]), true);
	assert.equal(model.validHashes([hash, hash]), false);
	assert.equal(model.validHashes([]), false);
	assert.equal(model.validPassword('valid space'), true);
	assert.equal(model.validPassword('я'.repeat(64)), true);
	assert.equal(model.validPassword('я'.repeat(65)), false);
	for (const value of ['abc', 'abc\nsecret', 'abc|secret', 'abc\0secret', 'abc\u0085secret']) assert.equal(model.validPassword(value), false);
	for (const value of ['example.org:443', '203.0.113.7:65535', '[2001:db8::1]:123']) assert.equal(model.validPeer(value), true);
	for (const value of ['https://example.org:443', 'example.org', 'example.org:0', '999.1.1.1:4', 'a..b:43']) assert.equal(model.validPeer(value), false);
	for (const value of ['example.org', 'sub.example.org.', '203.0.113.7', '203.0.113.0/24', '0.0.0.0/0']) assert.equal(model.validDestination(value), true);
	for (const value of ['*.example.org', 'https://example.org', 'example.org/path', '::1', '203.0.113.0/33', 'example.org/24']) assert.equal(model.validDestination(value), false);
	for (const value of ['printer.lab.lan', 'LAB.LAN.', 'host.lab.lan.']) assert.equal(model.validDestination(value, 'lab.lan'), false);
	for (const value of ['example.org', '203.0.113.7', '203.0.113.0/24', 'other.lan']) assert.equal(model.validDestination(value, 'lab.lan'), true);
	assert.equal(model.validMac('02:12:34:56:78:9a'), true);
	for (const value of ['ff:ff:ff:ff:ff:ff', '00:00:00:00:00:00', '01:00:00:00:00:01', '<script>']) assert.equal(model.validMac(value), false);
});

function pairing(expires = Math.floor(Date.now() / 1000) + 180, id = 'challenge-1') {
	return { ok: true, expires_at: expires, uri: `csqtt-helper://pair?host=192.168.1.1&port=9443&grant=${'a'.repeat(64)}&pin=${'b'.repeat(64)}&id=${id}` };
}

test('pairing accepts only the broker schema, unique fields, expiry and safe deep links', () => {
	const pair = pairing();
	assert.equal(model.validPairing(pair, Date.now() / 1000), true);
	assert.equal(model.validPairing(pairing(1), Date.now() / 1000), false);
	for (const uri of ['javascript:alert(1)', pair.uri.replace('csqtt-helper:', 'https:'), pair.uri + '&grant=other', pair.uri + '#secret', pair.uri.replace('pair?', 'attacker@pair?'), pair.uri.replace('9443', '0'), pair.uri.replace('id=challenge-1', 'id=%3Cscript%3E')]) {
		assert.equal(model.validPairing({ ...pair, uri }, Date.now() / 1000), false);
	}
});

class Node {
	constructor(tag, attrs = {}, children = []) { this.tag = tag; this.attrs = attrs || {}; this.children = [children].flat(Infinity).filter(v => v != null); this.value = ''; }
	replaceChildren(...children) { this.children = children; }
	appendChild(child) { this.children.push(child); return child; }
	removeAttribute(key) { delete this.attrs[key]; }
	focus() { this.focused = true; }
	select() { this.selected = true; }
	click() { return this.attrs.click?.(); }
	set innerHTML(value) { throw Error('Unsafe HTML assignment'); }
}
const E = (tag, attrs, children) => {
	// LuCI parses scalar string children as HTML; array children become text nodes.
	if (typeof children === 'string' && /<[^>]+>/.test(children)) throw Error('Untrusted scalar HTML children');
	return new Node(tag, attrs, children);
};
function walk(node) { return node instanceof Node ? [node, ...node.children.flatMap(walk)] : []; }
function text(node) { return node instanceof Node ? node.children.map(text).join(' ') : String(node); }
const L = { resource: v => '/resources/' + v, url: v => '/' + v };
function uiStub() {
	return { notifications: [], modal: null,
		createHandlerFn: (context, fn) => (...args) => fn.apply(context, args),
		addNotification: function(_title, content) { this.notifications.push(content); },
		showModal: function(title, content) { this.modal = E('modal', {}, [title, content]); },
		hideModal: function() { this.modal = null; }
	};
}

test('CAPTCHA grants appear only after a user action and are wiped on challenge change', async () => {
	const ui = uiStub(), calls = [], polls = [], window = { clearTimeout() {}, setTimeout() { return 1; }, navigator: {} };
	const challenge = { id: 'challenge-1', state: 'manual', expires_at: pairing().expires_at };
	let status = { core: { state: 'captcha_required', captcha: challenge, password: 'HIDDEN_PASSWORD', tunnel_ip: '<img onerror=evil>', tun_device: '<script>evil</script>' }, uri: 'HIDDEN_LINK' };
	const api = { call: async method => { calls.push(method); return method === 'captcha_begin' ? pairing() : status; } };
	const view = load('view/csqtt/overview.js', { view: extend, E, L, ui, api, model, window, poll: { add: fn => polls.push(fn) } });
	const page = view.render(status);
	assert.deepEqual(calls, []);
	assert.equal(ui.modal, null);
	assert.doesNotMatch(text(page), /HIDDEN_|grant=/);
	await walk(page).find(n => n.tag === 'button' && text(n) === 'Решить на Android').click();
	assert.equal(calls[0], 'captcha_begin');
	const field = walk(ui.modal).find(n => n.tag === 'textarea');
	const anchor = walk(ui.modal).find(n => n.tag === 'a');
	assert.match(field.value, /csqtt-helper:/);
	assert.doesNotMatch(text(page), /grant=/);
	status = { core: { state: 'captcha_required', captcha: { ...challenge, id: 'challenge-2' } } };
	await polls[0]();
	assert.equal(ui.modal, null);
	assert.equal(field.value, '');
	assert.equal(anchor.attrs.href, undefined);
});

test('diagnostics render and download only allowlisted facts, never raw logs or credentials', () => {
	const ui = uiStub();
	const view = load('view/csqtt/diagnostics.js', { view: extend, E, L, ui, api: {}, model });
	const page = view.render({ status: { core: { state: 'connected', password: 'SECRET' }, policies_active: true }, logs: 'SECRET', checks: [{ name: 'config', ok: false, detail: '<img onerror=SECRET>' }, { name: 'SECRET', ok: true }], uri: 'csqtt-helper://SECRET' });
	assert.match(text(page), /Требует внимания/);
	assert.doesNotMatch(text(page), /SECRET|onerror|csqtt-helper/);
	assert.equal(walk(page).some(n => n.tag === 'img' || n.tag === 'script'), false);
});

function formStub() {
	class Option {
		constructor(key) { this.key = key; this.keylist = []; this.vallist = []; }
		value(key, label) { this.keylist.push(key); this.vallist.push(label); }
		formvalue() { return this.current; }
		getUIElement() { return { setValue: value => { this.current = value; } }; }
		renderWidget() { return E('select'); }
	}
	class Section {
		constructor(type) { this.type = type; this.options = []; }
		tab() {}
		option(_type, key) { const o = new Option(key); this.options.push(o); return o; }
		taboption(_tab, ...args) { return this.option(...args); }
	}
	class Map {
		constructor() { this.sections = []; this.saves = 0; }
		section(_type, name) { const s = new Section(name); this.sections.push(s); return s; }
		render() { return Promise.resolve(E('form')); }
		save() { this.saves++; return Promise.resolve(); }
	}
	return { Map, GridSection: Section, NamedSection: Section, Value: Option, Flag: Option, ListValue: Option, DynamicList: Option };
}

test('rendered TURN choices compile into supported native client transport values', async () => {
	const { runtime } = await import('../policy/harness.mjs');
	const view = load('view/csqtt/settings.js', { view: extend, E, L, ui: uiStub(), form: formStub(), uci: {}, model });
	await view.render();
	const transport = view.map.sections[0].options.find(option => option.key === 'turn_transport');
	assert.equal(transport.default, 'udp');
	for (const value of transport.keylist) {
		transport.getUIElement('main').setValue(value);
		const selected = transport.formvalue('main');
		const compiled = runtime('compile', { packages: { csqtt: { main: { '.type': 'client', enabled: '0', turn_transport: selected } } } });
		const config = JSON.parse(compiled.files['/var/run/csqtt/apply.42/client.json']);
		assert.equal(config.turn_transport, selected, 'the selected form value must survive runtime compilation');
	}
	assert.deepEqual(transport.keylist, ['udp', 'tcp']);
	assert.deepEqual(transport.vallist, ['UDP', 'TCP / TLS']);
});

test('saving settings rejects over-capacity workers and duplicate hashes before saving UCI', async () => {
	const ui = uiStub(), form = formStub(), uci = { load: async () => {}, set() {} };
	const view = load('view/csqtt/settings.js', { view: extend, E, L, ui, form, uci, model });
	await view.render();
	view.lanOption.current = ['br-lan'];
	view.callOptions[0].current = model.callLink(hash); view.workersOption.current = '36';
	await assert.rejects(view.handleSave());
	assert.equal(view.map.saves, 0);
	view.callOptions[1].current = model.callLink(hash); view.workersOption.current = '9';
	await assert.rejects(view.handleSave());
	assert.equal(view.map.saves, 0);
	view.callOptions[1].current = model.callLink(hash2); view.workersOption.current = '54';
	await view.handleSave();
	assert.equal(view.map.saves, 1);
});

test('LAN DynamicList accepts an empty add field but requires valid saved interfaces', async () => {
	const view = load('view/csqtt/settings.js', { view: extend, E, L, ui: uiStub(), form: formStub(), uci: {}, model });
	await view.render();
	assert.equal(view.lanOption.validate('main', ''), true);
	assert.equal(view.lanOption.validate('main', ['br-lan']), true);
	for (const value of [[], ['lo'], ['csqtt0'], ['bad interface']]) {
		assert.notEqual(view.lanOption.validate('main', value), true);
		view.lanOption.current = value;
		await assert.rejects(view.handleSave(), /локальные интерфейсы/);
	}
	assert.equal(view.map.saves, 0);
});

test('six separate call fields display full links and save compatible hashes', async () => {
	const writes = [], uci = { get: () => [hash, hash2], set: (...args) => writes.push(args) };
	const view = load('view/csqtt/settings.js', { view: extend, E, L, ui: uiStub(), form: formStub(), uci, model });
	await view.render();
	assert.equal(view.callOptions.length, 6);
	assert.equal(view.callOptions[0].cfgvalue('main'), model.callLink(hash));
	assert.equal(view.callOptions[1].cfgvalue('main'), model.callLink(hash2));
	assert.equal(view.callOptions[2].cfgvalue('main'), '');
	view.callOptions[0].current = model.callLink(hash) + '?source=share';
	view.callOptions[2].current = model.callLink(hash2);
	view.callOptions[0].write('main');
	view.callOptions.slice(1).forEach(option => { option.write('main'); option.remove('main'); });
	assert.deepEqual(writes, [['csqtt', 'main', 'vk_hashes', [hash, hash2]]]);
	for (const value of [hash, 'https://evil.example/call/join/' + hash, 'https://vk.com.evil.example/call/join/' + hash, 'https://user@vk.com/call/join/' + hash, 'https://vk.com/call/join/short']) assert.equal(model.validCallLink(value), false);
	assert.equal(model.validCallLink('https://m.vk.com/call/join/' + hash + '?source=share'), true);
});

test('policy device validator rejects duplicate membership and preserves rule ordering', async () => {
	const ui = uiStub(), form = formStub();
	const entries = { group: [{ '.name': 'home', name: 'Дом' }], device: [{ '.name': 'a', mac: '02:12:34:56:78:9A', group: 'home' }, { '.name': 'b', mac: '02:12:34:56:78:9B', group: 'home' }] };
	const uci = { sections: (_package, type) => entries[type] || [] };
	const view = load('view/csqtt/policies.js', { view: extend, E, L, ui, form, uci, model, api: {} });
	await view.render([null, { devices: [{ name: '<img onerror=evil>', mac: '02:12:34:56:78:9A', ip: '192.168.1.3' }] }, { local_domain: 'lab.lan' }]);
	const devices = view.map.sections.find(s => s.type === 'device');
	const mac = devices.options.find(o => o.key === 'mac');
	assert.notEqual(mac.validate('b', '02:12:34:56:78:9a'), true);
	assert.equal(mac.validate('b', '02:12:34:56:78:9b'), true);
	assert.equal(view.map.sections.find(s => s.type === 'rule').sortable, true);
	const destination = view.map.sections.find(s => s.type === 'rule').options.find(o => o.key === 'destination');
	assert.notEqual(destination.validate('r', 'printer.lab.lan'), true);
	assert.equal(destination.validate('r', 'example.org'), true);
	await view.map.sections.find(s => s.type === 'group').handleRemove('home');
	assert.match(text(ui.notifications[0]), /Сначала/);
});

test('package menu resolves, JS parses, and RPC has only fixed commands with narrow ACL', () => {
	const menu = JSON.parse(fs.readFileSync(path.join(root, 'root/usr/share/luci/menu.d/luci-app-csqtt.json')));
	for (const entry of Object.values(menu)) if (entry.action.type === 'view') assert.equal(fs.existsSync(path.join(resources, 'view', entry.action.path + '.js')), true);
	for (const dir of ['csqtt', 'view/csqtt']) for (const file of fs.readdirSync(path.join(resources, dir))) if (file.endsWith('.js')) {
		const source = fs.readFileSync(path.join(resources, dir, file), 'utf8');
		assert.doesNotThrow(() => new Function(source));
		assert.doesNotMatch(source, /innerHTML|insertAdjacentHTML|console\.(log|warn|error)|localStorage|sessionStorage/);
	}
	const acl = JSON.parse(fs.readFileSync(path.join(root, 'root/usr/share/rpcd/acl.d/luci-app-csqtt.json')))['luci-app-csqtt'];
	assert.deepEqual(acl.read.uci, ['csqtt']); assert.deepEqual(acl.write.uci, ['csqtt']);
	assert.deepEqual(Object.keys(acl.read.ubus), ['csqtt']); assert.deepEqual(Object.keys(acl.write.ubus), ['csqtt']);
	assert.deepEqual(acl.read.ubus.csqtt, ['status', 'diagnostics', 'devices']);
	const dispatcher = fs.readFileSync(path.join(root, 'root/usr/libexec/rpcd/csqtt'), 'utf8');
	assert.doesNotMatch(dispatcher, /\beval\b|sh -c|\$3|\$\*|\$@/);
	for (const method of [...acl.read.ubus.csqtt, ...acl.write.ubus.csqtt]) assert.match(dispatcher, new RegExp('\\b' + method + '\\) exec /usr/(?:libexec/csqtt/manage|bin/csqtt-captcha) [a-z]+ ;;'));
});
