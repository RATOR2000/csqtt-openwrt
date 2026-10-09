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
function has_control(value, limit) {
	// ucode uses POSIX regex; an escaped NUL cannot form a regex range.
	for (let i = 0; i < length(value); i++) {
		let code = ord(substr(value, i, 1));
		if (code <= limit || code === 127) return true;
	}
	return false;
}
function client(main) {
	let password = main.password || '', peer = main.peer || '', hashes = list(main.vk_hashes);
	if (has_control(password, 31) || index(password, '|') >= 0 || length(password) > 128) die('Invalid password');
	if (has_control(peer, 32) || length(peer) > 255) die('Invalid peer');
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
		if (length(hashes[i]) < 16 || length(hashes[i]) > 1024 || !match(hashes[i], /^[a-zA-Z0-9_-]+$/)) die('Invalid VK hash');
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
		if (d.enabled === '0' || d.enabled === false) found[mac].enabled = false;
		else if (d.enabled == null || d.enabled === '1' || d.enabled === true) found[mac].group = d.group;
		else die('Device enabled must be 0 or 1');
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
function dns_instances() {
	let s = call('service', 'list', { name: 'csqtt-dns' });
	return s == null ? null : ((s['csqtt-dns'] && s['csqtt-dns'].instances) || {});
}
function process_id(value) {
	return match('' + (value || ''), /^[1-9][0-9]*$/) ? '' + value : null;
}
function dns_snapshot() {
	let instances = dns_instances(), pids = [];
	if (instances == null) die('Cannot inspect group DNS processes');
	for (let name in instances) {
		let s = instances[name], pid = process_id(s.pid);
		if (s.running && !pid) die('Cannot identify group DNS process');
		if (pid && !includes(pids, pid)) push(pids, pid);
	}
	save(ROOT + 'dns.stop.json', sprintf('%J', pids));
}
function dns_stopped() {
	let pids = readjson(ROOT + 'dns.stop.json', null), instances = dns_instances();
	if (type(pids) !== 'array' || instances == null) return false;
	for (let i = 0; i < length(pids); i++)
		if (!process_id(pids[i]) || fs.stat('/proc/' + pids[i])) return false;
	for (let name in instances) {
		let s = instances[name], pid = process_id(s.pid);
		if (s.running || (pid && fs.stat('/proc/' + pid))) return false;
	}
	return true;
}
function hex(value, digits) {
	let result = '', alphabet = '0123456789abcdef';
	for (let shift = (digits - 1) * 4; shift >= 0; shift -= 4)
		result += substr(alphabet, (value >> shift) & 15, 1);
	return result;
}
function dns_addresses(model) {
	let addresses = [], net = network(), lans = list(model.lans || 'br-lan');
	for (let i = 0; i < length(net.interface || []); i++) {
		let s = net.interface[i];
		if (!includes(lans, s.l3_device || s.device)) continue;
		for (let j = 0; j < length(s['ipv4-address'] || []); j++) {
			let p = split(s['ipv4-address'][j].address || '', '.'), address = '';
			if (length(p) !== 4) continue;
			for (let k = 3; k >= 0; k--) {
				if (!match(p[k], /^[0-9]{1,3}$/) || +p[k] > 255) { address = ''; break; }
				address += hex(+p[k], 2);
			}
			if (length(address) && !includes(addresses, address)) push(addresses, address);
		}
	}
	return addresses;
}
function dns_process_ready(id, port, addresses, instances) {
	let s = instances && instances['dns_' + id], pid = s && process_id(s.pid);
	if (!s || !s.running || !pid || !length(addresses) || port < 5400 || port > 5415) return false;
	let descriptors = fs.lsdir('/proc/' + pid + '/fd'), owned = {};
	if (descriptors == null) return false;
	for (let i = 0; i < length(descriptors); i++) {
		let target = fs.readlink('/proc/' + pid + '/fd/' + descriptors[i]);
		let socket = match(target || '', /^socket:\[([0-9]+)\]$/);
		if (socket) owned[socket[1]] = true;
	}
	let protocols = ['udp', 'tcp'];
	for (let p = 0; p < length(protocols); p++) {
		let protocol = protocols[p];
		let text = fs.readfile('/proc/net/' + protocol), listeners = [];
		if (text == null) return false;
		let rows = split(text, '\n');
		for (let i = 1; i < length(rows); i++) {
			let fields = split(trim(rows[i]), /\s+/);
			if (length(fields) < 10 || !owned[fields[9]] ||
				lc(fields[3]) !== (protocol === 'tcp' ? '0a' : '07')) continue;
			let local = split(lc(fields[1]), ':');
			if (length(local) === 2 && local[1] === hex(port, 4)) push(listeners, local[0]);
		}
		for (let i = 0; i < length(addresses); i++)
			if (!includes(listeners, addresses[i]) && !includes(listeners, '00000000')) return false;
	}
	return true;
}
function dns_ready() {
	let lines = split(trim(fs.readfile(ROOT + 'dns.ids') || ''), '\n'), ids = [], expected = [];
	let model = readjson(STATE + 'policy.json', { groups: [] });
	for (let i = 0; i < length(lines); i++) if (lines[i]) push(ids, lines[i]);
	for (let i = 0; i < length(model.groups || []); i++)
		if (length(model.groups[i].macs || [])) push(expected, model.groups[i].id);
	if (length(ids) !== length(expected)) return false;
	let instances = dns_instances(), addresses = dns_addresses(model);
	if (length(expected) && instances == null) return false;
	for (let i = 0; i < length(ids); i++) {
		if (!includes(expected, ids[i])) return false;
		for (let j = 0; j < i; j++) if (ids[j] === ids[i]) return false;
		let group = null;
		for (let j = 0; j < length(model.groups || []); j++)
			if (model.groups[j].id === ids[i]) group = model.groups[j];
		if (!group || !dns_process_ready(ids[i], group.port, addresses, instances)) return false;
	}
	return true;
}
function status() {
	let stored = readjson(ROOT + 'status.json', {}), core = {}, running = service_running('csqtt', 'client');
	// Explicit allowlist prevents upstream fields from exposing passwords or challenge answers.
	let fields = ['state', 'tun_device', 'tunnel_ip', 'active_workers', 'bytes_up', 'bytes_down', 'uptime_secs'];
	for (let k = 0; k < length(fields); k++) {
		let field = fields[k];
		if (stored[field] != null) core[field] = stored[field];
	}
	// These codes are emitted by the original client adapter, never error text.
	let errors = ['runtime_failed', 'transport_failed', 'tun_configuration_failed',
		'tun_down_hook_failed', 'control_socket_failed', 'tun_io_failed'];
	if (includes(errors, stored.error_code)) core.error_code = stored.error_code;
	if (stored.captcha) core.captcha = { id: stored.captcha.id, state: stored.captcha.state, expires_at: stored.captcha.expires_at };
	if (!running) core.state = 'stopped';
	let model = readjson(STATE + 'policy.json', { devices: [], groups: [] });
	return { core: core, running: running, enabled: c.get('csqtt', 'main', 'enabled') === '1',
		local_domain: local_domain(),
		policies_active: length(model.devices || []) > 0 && !fs.stat(STATE + 'deactivated'),
		policy_error: trim(fs.readfile(ROOT + 'policy.error') || ''),
		groups: length(model.groups || []), devices: length(model.devices || []) };
}
function firewall_include(name, file, position, chain) {
	if (c.get('firewall', name) && c.get('firewall', name, 'csqtt_owned') !== '1') die('Firewall section collision');
	c.set('firewall', name, 'include');
	c.set('firewall', name, 'type', 'nftables');
	c.set('firewall', name, 'path', STATE + file);
	c.set('firewall', name, 'position', position);
	c.set('firewall', name, 'csqtt_owned', '1');
	if (chain) c.set('firewall', name, 'chain', chain);
}
function firewall_hold() {
	// First activation can fail before the complete policy is persisted. Commit
	// the saved maintenance guard now so an intervening reboot keeps it closed.
	firewall_include('csqtt_hold', 'hold.nft', 'ruleset-post', null);
	if (!c.save('firewall') || !c.commit('firewall')) die('Cannot save firewall configuration');
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
			firewall_include(names[i], files[i], i < 2 ? 'ruleset-post' : 'chain-pre',
				i < 2 ? null : (i === 2 ? 'forward' : 'input'));
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
else if (mode === 'firewall-hold') firewall_hold();
else if (mode === 'status') output(status());
else if (mode === 'devices') output({ devices: devices() });
else if (mode === 'diagnostics') {
	let s = status(), model = readjson(STATE + 'policy.json', { groups: [] }), checks = [];
	push(checks, { name: 'policy', ok: !length(s.policy_error), detail: s.policy_error || 'Policy configuration loaded' });
	push(checks, { name: 'tun', ok: s.running && s.core.state === 'connected' && !s.core.error_code,
		detail: s.core.error_code || s.core.state || 'stopped' });
	let instances = dns_instances(), addresses = dns_addresses(model);
	for (let i = 0; i < length(model.groups); i++) if (length(model.groups[i].macs))
		push(checks, { name: 'dnsmasq', ok: dns_process_ready(model.groups[i].id, model.groups[i].port, addresses, instances), detail: 'Guarded group DNS listeners' });
	output({ status: s, checks: checks, domain_limitations: 'DNS caches, shared destination IPs and independent DoH limit hostname classification. Online status is estimated from ARP.' });
} else if (mode === 'dns-ready') {
	if (!dns_ready()) exit(1);
} else if (mode === 'dns-snapshot') dns_snapshot();
else if (mode === 'dns-stopped') {
	if (!dns_stopped()) exit(1);
} else die('Unknown runtime command');
