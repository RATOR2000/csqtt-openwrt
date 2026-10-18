import * as fs from 'fs';
import { cursor } from 'uci';
import { connect } from 'ubus';
import { compile, hold } from '/usr/share/csqtt/policy.uc';
import { health_initial, health_advance, health_reserve, health_complete, health_public } from '/usr/share/csqtt/health.uc';

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
function save_atomic(path, value) {
	save(path + '.new', value);
	if (!fs.rename(path + '.new', path)) die('Cannot replace private state');
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
function transport_instance() {
	let s = call('service', 'list', { name: 'csqtt' });
	return s && s.csqtt && s.csqtt.instances ? s.csqtt.instances.client : null;
}
function boottime() {
	let value = split(trim(fs.readfile('/proc/uptime') || ''), ' ')[0];
	return match(value, /^[0-9]+(\.[0-9]+)?$/) ? +value : null;
}
function process_id(value) {
	return match('' + (value || ''), /^[1-9][0-9]*$/) ? '' + value : null;
}

function process_startticks(pid) {
	if (!process_id(pid)) return null;
	let line = fs.readfile('/proc/' + pid + '/stat') || '';
	// comm may contain whitespace and ')'; split after its final closing ')'.
	let end = -1;
	for (let i = 0; i < length(line); i++) if (substr(line, i, 1) === ')') end = i;
	if (end < 0) return null;
	let fields = split(trim(substr(line, end + 1)), /\s+/), value = fields[19];
	return match(value || '', /^[0-9]+$/) ? value : null;
}
function current_status() {
	let stored = readjson(ROOT + 'status.json', {}), instance = transport_instance(), pid = instance && process_id(instance.pid);
	let now = boottime(), boot = trim(fs.readfile('/proc/sys/kernel/random/boot_id') || ''), ticks = process_startticks(pid);
	let running = !!(instance && instance.running), current = running && pid && ticks && boot && now != null &&
		('' + stored.pid) === pid && ('' + stored.process_startticks) === ticks && stored.boot_id === boot &&
		stored.updated_boottime_ms != null && stored.updated_boottime_ms <= now * 1000 &&
		now * 1000 - stored.updated_boottime_ms <= 15000;
	return { stored: stored, running: running, current: !!current, pid: pid, ticks: ticks, boot_id: boot, now: now };
}
function transport_snapshot() {
	let live = current_status();
	save(ROOT + 'transport.stop.json', sprintf('%J', { pid: live.pid, ticks: live.ticks }));
}
function transport_stopped() {
	let old = readjson(ROOT + 'transport.stop.json', null);
	if (!old) return false;
	if (old.pid && (!old.ticks || process_startticks(old.pid) === old.ticks)) return false;
	let instance = transport_instance();
	return !(instance && instance.running);
}
function dns_instances() {
	let s = call('service', 'list', { name: 'csqtt-dns' });
	return s == null ? null : ((s['csqtt-dns'] && s['csqtt-dns'].instances) || {});
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
function network_epoch() {
	let net = network(), paths = [];
	for (let i = 0; i < length(net.interface || []); i++) {
		let intf = net.interface[i], addresses = [], routes = [];
		for (let j = 0; j < length(intf['ipv4-address'] || []); j++)
			push(addresses, { address: intf['ipv4-address'][j].address, mask: intf['ipv4-address'][j].mask });
		for (let j = 0; j < length(intf.route || []); j++) {
			let r = intf.route[j];
			push(routes, { target: r.target, mask: r.mask, nexthop: r.nexthop, table: r.table, metric: r.metric });
		}
		push(paths, { up: intf.up, device: intf.l3_device || intf.device, addresses: addresses, routes: routes });
	}
	return sprintf('%J', paths);
}

function health_context(ignore_operation) {
	let live = current_status(), ctx = { boot_id: live.boot_id, now: live.now == null ? 0 : live.now,
		config_epoch: trim(fs.readfile(ROOT + 'health-config.current') || ''), intent: trim(fs.readfile(ROOT + 'intent') || ''),
		network_epoch: network_epoch(),
		process_epoch: (live.pid || '') + ':' + (live.ticks || '') + ':' +
			(live.current && live.stored.health ? ('' + (live.stored.health.human_epoch || 0)) : '0'),
		automatic: c.get('csqtt', 'main', 'auto_recover') === '1',
		process: live.running ? (live.current ? 'ok' : 'unknown') : 'fail', gate: null };
	if (!ctx.boot_id || live.now == null || !match(ctx.config_epoch, /^[a-f0-9]{64}$/)) ctx.gate = 'probe_uncertain';
	if (c.get('csqtt', 'main', 'enabled') !== '1' || fs.stat(STATE + 'deactivated')) ctx.gate = 'disabled';
	else if (fs.stat('/var/lock/csqtt-maintenance')) ctx.gate = 'maintenance';
	else if (fs.stat(ROOT + 'policy.error')) ctx.gate = 'policy_error';
	else if (fs.stat(ROOT + 'health-guard.blocked')) ctx.gate = 'guard_missing';
	else if (length(trim(fs.readfile('/tmp/.uci/csqtt') || '')) || length(trim(fs.readfile('/tmp/.uci/network') || '')) ||
		length(trim(fs.readfile('/tmp/.uci/dhcp') || '')) || length(trim(fs.readfile('/tmp/.uci/firewall') || ''))) ctx.gate = 'pending_edits';
	else if (!ignore_operation && fs.stat('/var/lock/csqtt-operation')) ctx.gate = 'operation_active';
	else if (live.running && !live.current) ctx.gate = 'status_stale';
	else if (!live.running && process_id(live.stored.pid) &&
		process_startticks(live.stored.pid) === ('' + live.stored.process_startticks)) ctx.gate = 'status_stale';
	else if (live.current && live.stored.captcha && live.stored.captcha.human_active === true &&
		live.stored.captcha.expires_at > time()) ctx.gate = 'human_active';
	return ctx;
}

function status() {
	let live = current_status(), stored = live.current ? live.stored : {}, core = {}, running = live.running;
	// Explicit allowlist prevents upstream fields from exposing passwords or challenge answers.
	if (includes(['starting', 'connecting', 'connected', 'captcha_required', 'error', 'stopped'], stored.state)) core.state = stored.state;
	if (stored.tun_device === 'csqtt0') core.tun_device = 'csqtt0';
	if (match(stored.tunnel_ip || '', /^[0-9]{1,3}(\.[0-9]{1,3}){3}$/)) core.tunnel_ip = stored.tunnel_ip;
	let fields = ['active_workers', 'bytes_up', 'bytes_down', 'uptime_secs'];
	for (let k = 0; k < length(fields); k++) {
		let field = fields[k];
		if (stored[field] != null && match('' + stored[field], /^[0-9]+$/) && stored[field] <= 9007199254740991) core[field] = stored[field];
	}
	// These codes are emitted by the original client adapter, never error text.
	let errors = ['runtime_failed', 'transport_failed', 'tun_configuration_failed',
		'tun_down_hook_failed', 'control_socket_failed', 'tun_io_failed'];
	if (includes(errors, stored.error_code)) core.error_code = stored.error_code;
	if (stored.captcha && match(stored.captcha.id || '', /^[a-zA-Z0-9_-]{1,80}$/) &&
		includes(['auto', 'manual', 'pending', 'manual_required', 'solving', 'human_active'], stored.captcha.state) &&
		stored.captcha.expires_at > time())
		core.captcha = { id: stored.captcha.id, state: stored.captcha.state, expires_at: stored.captcha.expires_at,
			human_active: stored.captcha.human_active === true };
	if (!running) core.state = 'stopped';
	else if (!live.current) core.state = 'starting';
	// A challenge on one allocation is a warning while useful workers remain.
	if (core.state === 'captcha_required' && core.active_workers > 0) core.state = 'connected';
	if (core.state === 'captcha_required' && !core.captcha) core.state = core.active_workers > 0 ? 'connected' : 'connecting';
	let model = readjson(STATE + 'policy.json', { devices: [], groups: [] });
	let ctx = health_context(false), public_health = health_public(readjson(ROOT + 'health-state.json', null), ctx);
	return { core: core, running: running, enabled: c.get('csqtt', 'main', 'enabled') === '1',
		health: public_health.health, recovery: public_health.recovery,
		local_domain: local_domain(),
		policies_active: length(model.devices || []) > 0 && !fs.stat(STATE + 'deactivated'),
		policy_error: length(trim(fs.readfile(ROOT + 'policy.error') || '')) ? 'Policy operation failed; inspect root-only diagnostics' : '',
		groups: length(model.groups || []), devices: length(model.devices || []) };
}
function health_input() {
	let ctx = health_context(false), model = readjson(STATE + 'policy.json', {}), net = network();
	let source = null, metric = 2147483647;
	for (let i = 0; i < length(net.interface || []); i++) {
		let intf = net.interface[i];
		if (intf.up === false || (intf.l3_device || intf.device) === 'csqtt0') continue;
		let address = intf['ipv4-address'] && intf['ipv4-address'][0] && intf['ipv4-address'][0].address;
		if (!match(address || '', /^[0-9]{1,3}(\.[0-9]{1,3}){3}$/)) continue;
		for (let j = 0; j < length(intf.route || []); j++) {
			let route = intf.route[j], cost = +(route.metric || intf.metric || 0);
			if (route.target === '0.0.0.0' && +route.mask === 0 &&
				(route.table == null || +route.table === 254) && cost < metric) { source = address; metric = cost; }
		}
	}
	if (!source && !ctx.gate) ctx.gate = 'probe_uncertain';
	let ports = [];
	for (let i = 0; i < length(model.groups || []); i++) {
		let group = model.groups[i];
		if (length(group.macs || []) && group.port >= 5400 && group.port <= 5415 && !includes(ports, group.port)) push(ports, group.port);
	}
	save(ROOT + 'health-context.json', sprintf('%J', ctx));
	if (ctx.gate) exit(1);
	save(ROOT + 'health-wan.input.json', sprintf('%J', { source_ipv4: source, dns_ipv4: model.wan_dns || '9.9.9.9', group_ports: [] }));
	save(ROOT + 'health-vpn.input.json', sprintf('%J', { source_ipv4: '198.18.0.1', dns_ipv4: model.vpn_dns || '1.1.1.1', group_ports: ports }));
}
function health_incident(action, reason) {
	if (!includes(['soft', 'transport', 'observation', 'manual'], action)) return;
	if (!includes(['vpn_transport_failed', 'probe_uncertain', 'group_dns_failed', 'manual_reconnect'], reason)) reason = 'vpn_transport_failed';
	// Construct a new allowlisted snapshot. Never copy probe bodies, config,
	// logs, auth/group identities, URLs, runtime addresses or socket metadata.
	let live = current_status(), ctx = health_context(true), public_state = health_public(readjson(ROOT + 'health-state.json', null), ctx);
	let counts = { auth_attempts: 0, auth_successes: 0, auth_failures: 0, auth_cancelled: 0,
		fresh_auth_retries: 0, liveness_probes: 0, liveness_replies: 0, liveness_misses: 0, liveness_timeouts: 0 };
	let auth = live.current && live.stored.health ? live.stored.health : {};
	for (let key in counts) if (match('' + auth[key], /^[0-9]+$/) && auth[key] <= 1000000000) counts[key] = auth[key];
	if (includes(['idle', 'network', 'manual', 'captcha_wait', 'waiting'], auth.auth_phase)) counts.phase = auth.auth_phase;
	for (let key in ['auth_progress_age_secs', 'peer_progress_age_secs'])
		if (auth[key] != null && match('' + auth[key], /^[0-9]+$/) && auth[key] <= 86400) counts[key] = auth[key];
	let model = readjson(STATE + 'policy.json', { groups: [] }), dns_count = 0;
	for (let i = 0; i < length(model.groups || []); i++) if (length(model.groups[i].macs || [])) dns_count++;
	let rows = readjson(ROOT + 'incidents.json', []), kept = [];
	if (type(rows) === 'array') for (let i = 0; i < length(rows); i++) {
		// Only retain snapshots generated in this boot, and re-redact old rows.
		let row = rows[i];
		if (row && row.version === 1 && row.boot_secs <= ctx.now && ctx.now - row.boot_secs <= 86400 &&
			includes(['soft', 'transport', 'observation', 'manual'], row.action) &&
			includes(['vpn_transport_failed', 'probe_uncertain', 'group_dns_failed', 'manual_reconnect'], row.reason) && length(kept) < 7)
			push(kept, { version: 1, boot_secs: row.boot_secs, action: row.action, reason: row.reason,
				workers: integer(row.workers, 0, 0, 126, 'snapshot workers'), dns_groups: integer(row.dns_groups, 0, 0, 16, 'snapshot DNS groups') });
	}
	push(kept, { version: 1, boot_secs: ctx.now, action: action, reason: reason,
		workers: live.current ? integer(live.stored.active_workers, 0, 0, 126, 'snapshot workers') : 0,
		dns_groups: dns_count, dns_ready: dns_ready(), auth: counts,
		wan: public_state.health.wan, vpn: public_state.health.vpn });
	let network_counts = readjson(ROOT + 'health-network.json', {}), newest = kept[length(kept) - 1];
	newest.routes = { source_rule: network_counts.source_rule === true, fallback_rule: network_counts.fallback_rule === true, unreachable_route: network_counts.unreachable_route === true };
	newest.guards = { output: network_counts.output_guard === true, forward: network_counts.forward_guard === true };
	save_atomic(ROOT + 'incidents.json', sprintf('%J', kept));
}

function health_update(owned) {
	let previous = readjson(ROOT + 'health-state.json', null), sampled = readjson(ROOT + 'health-context.json', {}), ctx = health_context(owned);
	if (sampled.config_epoch !== ctx.config_epoch || sampled.network_epoch !== ctx.network_epoch || sampled.intent !== ctx.intent || sampled.boot_id !== ctx.boot_id ||
		sampled.now > ctx.now || ctx.now - sampled.now > 15) ctx.gate = 'configuration_changed';
	else if (sampled.gate) ctx.gate = sampled.gate;
	let next = health_advance(previous, ctx, readjson(ROOT + 'health-wan.json', null), readjson(ROOT + 'health-vpn.json', null));
	save_atomic(ROOT + 'health-state.json', sprintf('%J', next));
	if (previous && previous.state === 'healthy' && includes(['degraded', 'wan_down'], next.state))
		health_incident('observation', next.reason);
}
function health_authorize(action) {
	let ctx = health_context(true);
	ctx.wan = readjson(ROOT + 'health-wan.json', null); ctx.vpn = readjson(ROOT + 'health-vpn.json', null);
	let state = health_reserve(readjson(ROOT + 'health-state.json', null), ctx, action);
	if (!state) exit(1);
	save_atomic(ROOT + 'health-state.json', sprintf('%J', state));
}
function health_finish(action, success) {
	let ctx = health_context(true), state = health_complete(readjson(ROOT + 'health-state.json', null), ctx, action, success);
	save_atomic(ROOT + 'health-state.json', sprintf('%J', state));
}
function health_lease_valid() {
	let lease = readjson(ROOT + 'recovery-lease.json', {}), live = current_status();
	return live.current && lease.ok === true && lease.boot_id === live.boot_id &&
		('' + lease.pid) === live.pid && ('' + lease.process_startticks) === live.ticks &&
		lease.human_epoch === (live.stored.health ? (live.stored.health.human_epoch || 0) : 0) &&
		match(lease.recovery_id || '', /^[a-zA-Z0-9_-]{1,80}$/) && lease.lease_secs === 90 &&
		lease.updated_boottime_ms <= live.now * 1000 && live.now * 1000 - lease.updated_boottime_ms < 85000;
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
} else if (mode === 'transport-snapshot') transport_snapshot();
else if (mode === 'transport-stopped') { if (!transport_stopped()) exit(1); }
else if (mode === 'transport-active') { if (!current_status().running) exit(1); }
else if (mode === 'health-input') health_input();
else if (mode === 'health-update') health_update(ARGV[1] === 'owned');
else if (mode === 'health-authorize') health_authorize(ARGV[1]);
else if (mode === 'health-current') {
	let ctx = health_context(true), state = readjson(ROOT + 'health-state.json', {});
	if (ctx.gate || !ctx.automatic || state.boot_id !== ctx.boot_id || state.config_epoch !== ctx.config_epoch || state.network_epoch !== ctx.network_epoch ||
		state.intent !== ctx.intent || state.process_epoch !== ctx.process_epoch) exit(1);
}
else if (mode === 'health-finish') health_finish(ARGV[1], ARGV[2] === 'ok');
else if (mode === 'health-action') {
	let state = readjson(ROOT + 'health-state.json', {});
	if (includes(['soft', 'transport'], state.action)) printf('%s\n', state.action);
} else if (mode === 'health-lease-valid') { if (!health_lease_valid()) exit(1); }
else if (mode === 'health-deadline') {
	if (!health_lease_valid()) exit(1);
	let lease = readjson(ROOT + 'recovery-lease.json', {});
	printf('%.0f\n', lease.updated_boottime_ms + 85000);
}
else if (mode === 'health-lease-end') {
	let lease = readjson(ROOT + 'recovery-lease.json', {});
	if (match(lease.recovery_id || '', /^[a-zA-Z0-9_-]{1,80}$/)) output({ command: 'recovery_end', id: lease.recovery_id });
	else exit(1);
} else if (mode === 'health-incident') health_incident(ARGV[1], ARGV[2]);
else die('Unknown runtime command');
