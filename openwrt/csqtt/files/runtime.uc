import * as fs from 'fs';
import { cursor } from 'uci';
import { connect } from 'ubus';
import { compile, hold } from '/usr/share/csqtt/policy.uc';

const ROOT = '/var/run/csqtt/';
const STATE = '/etc/csqtt/';
let c = cursor();
function readjson(path, fallback) {
	try {
		let value = json(fs.readfile(path));
		return value == null ? fallback : value;
	} catch (e) { return fallback; }
}
function save(path, value) {
	if (fs.writefile(path, value) == null) die('Cannot write ' + path);
	fs.chmod(path, 0600);
}
function output(value) { printf('%J\n', value); }
function call(object, method, args) {
	try { let b = connect(); return b ? b.call(object, method, args || {}) : null; } catch (e) { return null; }
}
function sections(package, kind) {
	let result = [];
	c.foreach(package, kind, function(s) {
		let entry = {};
		for (let k in s) if (substr(k, 0, 1) !== '.') entry[k] = s[k];
		entry.id = s['.name']; push(result, entry);
	});
	return result;
}
function list(v) { return type(v) === 'array' ? v : (v ? [v] : []); }
function includes(a, value) { for (let i = 0; i < length(a); i++) if (a[i] === value) return true; return false; }
function network() { return call('network.interface', 'dump', {}) || { interface: [] }; }
function local_domain() {
	let domain = 'lan';
	c.foreach('dhcp', 'dnsmasq', function(s) { if (s.domain) domain = s.domain; });
	return lc(trim('' + domain));
}
function input() {
	let m = c.get_all('csqtt', 'main') || {}, subnets = [], net = network();
	let lans = list(m.lan_device || 'br-lan');
	for (let i = 0; i < length(net.interface || []); i++) {
		let intf = net.interface[i];
		if (!includes(lans, intf.l3_device || intf.device)) continue;
		for (let j = 0; j < length(intf['ipv4-address'] || []); j++) {
			let addr = intf['ipv4-address'][j];
			// nft normalizes the host bits of a prefix only with explicit interval sets.
			let p = split(addr.address, '.'), bits = +addr.mask, n = [];
			for (let k = 0; k < 4; k++) {
				let b = bits > 8 ? 8 : (bits > 0 ? bits : 0);
				push(n, (+p[k]) & (256 - (1 << (8 - b)))); bits -= 8;
			}
			push(subnets, join('.', n) + '/' + addr.mask);
		}
	}
	return { main: m, groups: sections('csqtt', 'group'), devices: sections('csqtt', 'device'),
		rules: sections('csqtt', 'rule'), local_subnets: subnets, local_domain: local_domain() };
}
function integer(value, fallback, low, high, name) {
	if (value == null || value === '') return fallback;
	if (!match('' + value, /^[0-9]+$/) || +value < low || +value > high) die('Invalid ' + name);
	return +value;
}
function choice(value, fallback, allowed, name) {
	value = value || fallback;
	if (!includes(allowed, value)) die('Invalid ' + name);
	return value;
}
function client(main) {
	let password = main.password || '', peer = main.peer || '', hashes = list(main.vk_hashes);
	if (match(password, /[\x00-\x1f\x7f|]/) || length(password) > 128) die('Invalid password');
	if (match(peer, /[\x00-\x20\x7f]/) || length(peer) > 255) die('Invalid peer');
	if (peer) {
		let endpoint = match(peer, /^(.+):([0-9]{1,5})$/);
		if (!endpoint || +endpoint[2] < 1 || +endpoint[2] > 65535) die('Peer needs a host and port');
		let host = endpoint[1];
		if (substr(host, 0, 1) === '[') {
			if (!match(host, /^\[[0-9a-fA-F:.]+\]$/) || index(host, ':') < 0) die('Invalid IPv6 peer');
		} else {
			if (substr(host, length(host) - 1) === '.') host = substr(host, 0, length(host) - 1);
			let labels = split(host, '.');
			for (let i = 0; i < length(labels); i++)
				if (length(labels[i]) > 63 || !match(labels[i], /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$/)) die('Invalid peer host');
		}
	}
	if (length(hashes) > 6) die('At most six VK hashes are supported');
	for (let i = 0; i < length(hashes); i++)
		if (!match(hashes[i], /^[a-zA-Z0-9_-]{16,1024}$/)) die('Invalid VK hash');
		else for (let j = 0; j < i; j++) if (hashes[i] === hashes[j]) die('Duplicate VK hash');
	if (main.enabled === '1' && (!length(peer) || length(password) < 4 || !length(hashes)))
		die('Enabled client needs peer, password and VK hashes');
	let workers = integer(main.workers, 9, 9, 126, 'workers');
	if (workers % 9 || (length(hashes) && workers > length(hashes) * 27)) die('Workers must be a multiple of nine within hash capacity');
	if (main.tun_device && main.tun_device !== 'csqtt0') die('TUN device must be csqtt0');
	let cfg = { peer: peer, password: password, vk_hashes: hashes,
		workers: workers,
		obfs: choice(main.obfs, 'video', ['video', 'audio'], 'obfs'),
		turn_transport: choice(main.turn_transport, 'udp', ['udp', 'tcp'], 'TURN transport'),
		vk_auth_mode: choice(main.vk_auth_mode, 'vkcalls', ['vkcalls', 'legacy'], 'VK auth mode'),
		fingerprint: choice(main.fingerprint, 'firefox', ['firefox', 'chrome', 'edge', 'safari', 'opera'], 'fingerprint'),
		client_ids: main.client_ids || '8202606,6287487',
		captcha_timeout_secs: integer(main.captcha_timeout_secs, 180, 30, 600, 'CAPTCHA timeout'),
		tun_device: 'csqtt0',
		tun_config_hook: '/usr/libexec/csqtt/tun-hook', status_file: ROOT + 'status.json',
		control_socket: ROOT + 'control.sock', identity_file: STATE + 'device-id' };
	if (length(cfg.client_ids) > 128 || !match(cfg.client_ids, /^[0-9]+(,[0-9]+)*$/)) die('Invalid client IDs');
	if (main.turn_host) {
		if (!match(main.turn_host, /^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$/)) die('Invalid TURN host');
		cfg.turn_host = main.turn_host;
	}
	if (main.turn_port) cfg.turn_port = integer(main.turn_port, 3478, 1, 65535, 'TURN port');
	return cfg;
}
function devices() {
	let found = {};
	let leases = split(fs.readfile('/tmp/dhcp.leases') || '', '\n');
	for (let i = 0; i < length(leases); i++) {
		let p = split(trim(leases[i]), /\s+/);
		if (length(p) < 4 || !match(p[1], /^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$/)) continue;
		found[lc(p[1])] = { mac: lc(p[1]), ip: p[2], name: p[3] === '*' ? '' : p[3], online: false };
	}
	let arp = split(fs.readfile('/proc/net/arp') || '', '\n');
	let lans = list(c.get('csqtt', 'main', 'lan_device') || 'br-lan');
	for (let i = 1; i < length(arp); i++) {
		let p = split(trim(arp[i]), /\s+/);
		if (length(p) < 6 || p[2] !== '0x2' || !includes(lans, p[5])) continue;
		let mac = lc(p[3]);
		if (!found[mac]) found[mac] = { mac: mac, name: '', ip: p[0], online: false };
		// ARP cache presence is an estimate; no unsolicited network probing.
		found[mac].online = true; found[mac].ip = p[0];
	}
	let configured = sections('csqtt', 'device');
	for (let i = 0; i < length(configured); i++) {
		let d = configured[i], mac = lc(d.mac || '');
		if (!found[mac]) found[mac] = { mac: mac, ip: '', name: '', online: false };
		found[mac].group = d.group;
		if (d.name) found[mac].name = d.name;
	}
	let result = [];
	for (let mac in found) push(result, found[mac]);
	return result;
}
function service_running(name, instance) {
	let s = call('service', 'list', { name: name });
	return !!(s && s[name] && s[name].instances && s[name].instances[instance] && s[name].instances[instance].running);
}
function status() {
	let stored = readjson(ROOT + 'status.json', {}), core = {}, running = service_running('csqtt', 'client');
	// Explicit allowlist prevents upstream fields from exposing passwords or challenge answers.
	let fields = ['state', 'tun_device', 'tunnel_ip', 'active_workers', 'bytes_up', 'bytes_down', 'uptime_secs'];
	for (let k = 0; k < length(fields); k++) {
		let field = fields[k];
		if (stored[field] != null) core[field] = stored[field];
	}
	if (stored.captcha) core.captcha = { id: stored.captcha.id, state: stored.captcha.state, expires_at: stored.captcha.expires_at };
	if (!running) core.state = 'stopped';
	let model = readjson(STATE + 'policy.json', { devices: [], groups: [] });
	return { core: core, running: running, enabled: c.get('csqtt', 'main', 'enabled') === '1',
		local_domain: local_domain(),
		policies_active: length(model.devices || []) > 0 && !fs.stat(STATE + 'deactivated'),
		policy_error: trim(fs.readfile(ROOT + 'policy.error') || ''),
		groups: length(model.groups || []), devices: length(model.devices || []) };
}
function firewall(on) {
	let names = ['csqtt_guard', 'csqtt_hold', 'csqtt_forward', 'csqtt_input'];
	let files = ['policy.nft', 'hold.nft', 'forward.nft', 'input.nft'];
	let old = readjson(STATE + 'offload.json', null);
	if (on) {
		if (!old) {
			old = [];
			c.foreach('firewall', 'defaults', function(s) {
				push(old, { id: s['.name'], flow_offloading: s.flow_offloading, flow_offloading_hw: s.flow_offloading_hw });
			});
			save(STATE + 'offload.json', sprintf('%J', old));
		}
		c.foreach('firewall', 'defaults', function(s) {
			c.set('firewall', s['.name'], 'flow_offloading', '0');
			c.set('firewall', s['.name'], 'flow_offloading_hw', '0');
		});
		for (let i = 0; i < length(names); i++) {
			if (c.get('firewall', names[i]) && c.get('firewall', names[i], 'csqtt_owned') !== '1') die('Firewall section collision');
			c.set('firewall', names[i], 'include');
			c.set('firewall', names[i], 'type', 'nftables');
			c.set('firewall', names[i], 'path', STATE + files[i]);
			c.set('firewall', names[i], 'position', i < 2 ? 'ruleset-post' : 'chain-pre');
			c.set('firewall', names[i], 'csqtt_owned', '1');
			if (i >= 2) c.set('firewall', names[i], 'chain', i === 2 ? 'forward' : 'input');
		}
	} else {
		for (let i = 0; i < length(names); i++)
			if (c.get('firewall', names[i], 'csqtt_owned') === '1') c.delete('firewall', names[i]);
		for (let i = 0; i < length(old || []); i++) {
			let s = old[i];
			if (c.get('firewall', s.id) !== 'defaults') continue;
			for (let j = 0; j < 2; j++) {
				let key = j === 0 ? 'flow_offloading' : 'flow_offloading_hw';
				// Preserve an explicit administrator change made after activation.
				if (c.get('firewall', s.id, key) !== '0') continue;
				if (s[key] == null) c.delete('firewall', s.id, key); else c.set('firewall', s.id, key, s[key]);
			}
		}
	}
	if (!c.save('firewall') || !c.commit('firewall')) die('Cannot save firewall configuration');
}

let mode = ARGV[0];
if (mode === 'compile') {
	let path = ARGV[1];
	if (!match(path || '', /^\/var\/run\/csqtt\/apply\.[0-9]+$/)) die('Invalid staging path');
	let data = input(), result = compile(data), cfg = client(data.main), previous = readjson(STATE + 'policy.json', null);
	save(path + '/policy.nft', result.nft);
	save(path + '/hold.nft', hold([previous, result.model], true));
	save(path + '/release.nft', hold([], false));
	save(path + '/forward.nft', result.forward);
	save(path + '/input.nft', result.input);
	save(path + '/policy.json', sprintf('%J', result.model));
	save(path + '/client.json', sprintf('%J', cfg));
	save(path + '/active', result.active ? '1' : '0');
	let ids = [];
	for (let i = 0; i < length(result.dns); i++) {
		let d = result.dns[i]; save(path + '/dns-' + d.id + '.conf', d.config); push(ids, d.id);
	}
	save(path + '/dns.ids', join('\n', ids) + '\n');
	let addresses = [], devs = devices(), macs = [];
	for (let i = 0; i < length(result.model.devices); i++) push(macs, result.model.devices[i].mac);
	for (let i = 0; i < length(previous ? previous.devices : []); i++) push(macs, previous.devices[i].mac);
	for (let i = 0; i < length(devs); i++)
		if (includes(macs, devs[i].mac) && match(devs[i].ip, /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/)) push(addresses, devs[i].ip);
	save(path + '/flush.ips', join('\n', addresses) + '\n');
} else if (mode === 'firewall-on') firewall(true);
else if (mode === 'firewall-off') firewall(false);
else if (mode === 'status') output(status());
else if (mode === 'devices') output({ devices: devices() });
else if (mode === 'diagnostics') {
	let s = status(), model = readjson(STATE + 'policy.json', { groups: [] }), checks = [];
	push(checks, { name: 'policy', ok: !length(s.policy_error), detail: s.policy_error || 'Policy configuration loaded' });
	push(checks, { name: 'tun', ok: s.running, detail: s.core.state || 'stopped' });
	for (let i = 0; i < length(model.groups); i++) if (length(model.groups[i].macs))
		push(checks, { name: 'dnsmasq', ok: service_running('csqtt-dns', 'dns_' + model.groups[i].id), detail: 'Guarded group DNS process' });
	output({ status: s, checks: checks, domain_limitations: 'DNS caches, shared destination IPs and independent DoH limit hostname classification. Online status is estimated from ARP.' });
} else if (mode === 'dns-ready') {
	let ids = split(trim(fs.readfile(ROOT + 'dns.ids') || ''), '\n');
	for (let i = 0; i < length(ids); i++) if (ids[i] && !service_running('csqtt-dns', 'dns_' + ids[i])) exit(1);
} else die('Unknown runtime command');
