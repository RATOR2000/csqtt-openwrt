// Deliberately use the JavaScript/ucode common subset: the exact policy compiler
// is also executed by the host test harness, not a reimplementation of it.
const VPN = '0x40000000';
const WAN = '0x20000000';
const MASK = '0x60000000';

function fail(message) { die(message); }
function array(value) {
	if (value == null || value === '') return [];
	return type(value) === 'array' ? value : [value];
}
function clean(value) { return trim('' + (value == null ? '' : value)); }
function id(value) {
	if (!match(value, /^[a-zA-Z0-9_]{1,32}$/)) fail('Invalid UCI section identifier');
	return value;
}
function action(value) {
	if (value !== 'vpn' && value !== 'wan') fail('Action must be vpn or wan');
	return value;
}
function device_enabled(value) {
	if (value == null || value === '1' || value === true) return true;
	if (value === '0' || value === false) return false;
	fail('Device enabled must be 0 or 1');
}
function ipv4(value) {
	let p = split(value, '.');
	if (length(p) !== 4) return false;
	for (let i = 0; i < 4; i++)
		if (!match(p[i], /^(0|[1-9][0-9]{0,2})$/) || +p[i] > 255) return false;
	return true;
}
function destination(value) {
	value = lc(clean(value));
	let p = split(value, '/');
	if (length(p) <= 2 && ipv4(p[0])) {
		if (length(p) === 2 && (!match(p[1], /^(0|[1-9][0-9]?)$/) || +p[1] > 32))
			fail('Invalid IPv4 prefix');
		if (length(p) === 2) {
			let octets = split(p[0], '.'), bits = +p[1], network = [];
			for (let i = 0; i < 4; i++) {
				let count = bits > 8 ? 8 : (bits > 0 ? bits : 0);
				push(network, (+octets[i]) & (256 - (1 << (8 - count)))); bits -= 8;
			}
			value = join('.', network) + '/' + p[1];
		}
		return { kind: 'ip', value: value };
	}
	if (length(value) > 253 || !match(value, /^[a-z0-9][a-z0-9.-]*[a-z0-9]$/))
		fail('Destination must be a domain, IPv4 address or IPv4 CIDR');
	p = split(value, '.');
	if (length(p) < 2) fail('Domain must contain a dot');
	for (let i = 0; i < length(p); i++)
		if (length(p[i]) > 63 || !match(p[i], /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/))
			fail('Invalid domain label');
	return { kind: 'domain', value: value };
}
function quoted(value) { return '"' + value + '"'; }
function setvalues(values, quote) {
	let result = [];
	for (let i = 0; i < length(values); i++) push(result, quote ? quoted(values[i]) : values[i]);
	return '{ ' + join(', ', result) + ' }';
}
function suffix(domain, parent) {
	return domain === parent || (length(domain) > length(parent) &&
		substr(domain, length(domain) - length(parent) - 1) === '.' + parent);
}
function domainkey(value) {
	let hash = 5381;
	for (let i = 0; i < length(value); i++) hash = (hash * 33 + ord(substr(value, i, 1))) % 4294967296;
	return '' + hash;
}
function append(lines, value) { push(lines, value); }
function rule(lines, chain, text) { append(lines, 'add rule inet csqtt ' + chain + ' ' + text); }

export function validate(input) {
	let main = input.main || {};
	let groups = array(input.groups), devices = array(input.devices), rules = array(input.rules);
	if (length(groups) > 16 || length(devices) > 256 || length(rules) > 128)
		fail('Limits: 16 groups, 256 devices, 128 rules');
	let model = { groups: [], devices: [], rules: [], lans: [], locals: [] };
	let lans = array(main.lan_device || 'br-lan');
	for (let i = 0; i < length(lans); i++) {
		if (!match(lans[i], /^[a-zA-Z0-9_.:-]{1,15}$/)) fail('Invalid LAN device');
		push(model.lans, lans[i]);
	}
	if (!length(model.lans)) fail('At least one LAN device is required');
	for (let i = 0; i < length(groups); i++) {
		let g = groups[i];
		id(g.id); action(g.default_action);
		for (let j = 0; j < i; j++) if (groups[j].id === g.id) fail('Duplicate group');
		push(model.groups, { id: g.id, name: clean(g.name), default_action: g.default_action,
			macs: [], rules: [], protected: g.default_action === 'vpn', port: 5400 + i });
	}
	let device_macs = [];
	for (let i = 0; i < length(devices); i++) {
		let d = devices[i], group = null, mac = lc(clean(d.mac));
		id(d.id);
		for (let j = 0; j < i; j++) if (devices[j].id === d.id) fail('Duplicate device identifier');
		if (!match(mac, /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/) || mac === '00:00:00:00:00:00' ||
			(index('13579bdf', substr(mac, 1, 1)) >= 0)) fail('Device MAC must be unicast');
		for (let j = 0; j < length(device_macs); j++) if (device_macs[j] === mac) fail('Device belongs to more than one group');
		push(device_macs, mac);
		for (let j = 0; j < length(model.groups); j++) if (model.groups[j].id === d.group) group = model.groups[j];
		if (!group) fail('Device refers to a missing group');
		if (!device_enabled(d.enabled)) continue;
		push(group.macs, mac);
		push(model.devices, { id: d.id, name: clean(d.name), mac: mac, group: group.id });
	}
	for (let i = 0; i < length(rules); i++) {
		let r = rules[i], group = null;
		id(r.id);
		for (let j = 0; j < i; j++) if (rules[j].id === r.id) fail('Duplicate rule identifier');
		if (r.enabled === '0' || r.enabled === false) continue;
		action(r.action);
		for (let j = 0; j < length(model.groups); j++) if (model.groups[j].id === r.group) group = model.groups[j];
		if (!group) fail('Rule refers to a missing group');
		let dest = destination(r.destination);
		let entry = { id: r.id, action: r.action, kind: dest.kind, value: dest.value, set: 'd_' + r.id + '_' + domainkey(dest.value) };
		push(group.rules, entry); push(model.rules, entry);
		if (r.action === 'vpn') group.protected = true;
	}
	let locals = array(input.local_subnets);
	for (let i = 0; i < length(locals); i++) {
		let d = destination(locals[i]);
		if (d.kind !== 'ip') fail('Local subnet must be IPv4');
		push(model.locals, d.value);
	}
	model.vpn_dns = clean(main.vpn_dns || '1.1.1.1');
	model.wan_dns = clean(main.wan_dns || '9.9.9.9');
	if (!ipv4(model.vpn_dns) || !ipv4(model.wan_dns)) fail('DNS servers must be IPv4 literals');
	model.local_domain = lc(clean(input.local_domain || 'lan'));
	if (length(model.local_domain) > 253) fail('Invalid local DNS domain');
	let local_labels = split(model.local_domain, '.');
	for (let i = 0; i < length(local_labels); i++)
		if (length(local_labels[i]) > 63 || !match(local_labels[i], /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/)) fail('Invalid local DNS domain');
	for (let i = 0; i < length(model.rules); i++)
		if (model.rules[i].kind === 'domain' && suffix(model.rules[i].value, model.local_domain))
			fail('Local DNS domains cannot be internet policy destinations');
	return model;
};

export function compile(input) {
	let m = validate(input), n = ['# Generated by CSQTT. DNS sets deliberately survive reload.', 'add table inet csqtt'];
	let chains = ['classify', 'forward_guard', 'input_guard', 'output_guard', 'dns_redirect', 'nat'];
	append(n, 'add chain inet csqtt classify { type filter hook prerouting priority -160; policy accept; }');
	append(n, 'add chain inet csqtt forward_guard { type filter hook forward priority -10; policy accept; }');
	append(n, 'add chain inet csqtt input_guard { type filter hook input priority -10; policy accept; }');
	append(n, 'add chain inet csqtt output_guard { type filter hook output priority -10; policy accept; }');
	append(n, 'add chain inet csqtt dns_redirect { type nat hook prerouting priority -110; policy accept; }');
	append(n, 'add chain inet csqtt nat { type nat hook postrouting priority 110; policy accept; }');
	for (let i = 0; i < length(chains); i++) append(n, 'flush chain inet csqtt ' + chains[i]);
	let lan = setvalues(m.lans, true);
	rule(n, 'classify', 'iifname != ' + lan + ' return');
	rule(n, 'classify', 'meta mark set meta mark & 0x9fffffff');
	rule(n, 'classify', 'fib daddr type local return');
	if (length(m.locals)) rule(n, 'classify', 'ip daddr ' + setvalues(m.locals, false) + ' return');
	rule(n, 'classify', 'ip daddr { 224.0.0.0/4, 255.255.255.255 } return');
	// Do not classify DNS-to-router as internet, including manually configured public DNS.
	rule(n, 'classify', 'meta l4proto { tcp, udp } th dport 53 return');
	rule(n, 'forward_guard', 'iifname != ' + lan + ' return');
	rule(n, 'forward_guard', 'oifname ' + lan + ' return');
	if (length(m.locals)) rule(n, 'forward_guard', 'ip daddr ' + setvalues(m.locals, false) + ' return');
	// LAN egress was accepted above. Do not exempt all ULA/multicast prefixes:
	// a routed IPv6 destination outside the LAN must remain blocked too.
	rule(n, 'output_guard', 'ip saddr 198.18.0.1 oifname != "csqtt0" reject');
	rule(n, 'nat', 'oifname "csqtt0" meta nfproto ipv4 masquerade');
	rule(n, 'input_guard', 'iifname "lo" return');
	let allmacs = [], dns = [], protectedmacs = [];
	for (let i = 0; i < length(m.groups); i++) {
		let g = m.groups[i];
		if (!length(g.macs)) continue;
		let macs = setvalues(g.macs, false), gc = 'g_' + g.id;
		for (let j = 0; j < length(g.macs); j++) {
			push(allmacs, g.macs[j]);
			if (g.protected) push(protectedmacs, g.macs[j]);
		}
		append(n, 'add chain inet csqtt ' + gc);
		append(n, 'flush chain inet csqtt ' + gc);
		let conf = ['# CSQTT group ' + g.id, 'port=' + g.port, 'bind-dynamic', 'no-resolv', 'no-poll',
			'no-hosts', 'bogus-priv', 'stop-dns-rebind', 'rebind-domain-ok=//',
			'rebind-domain-ok=/' + m.local_domain + '/', 'cache-size=256',
			'pid-file=/var/run/csqtt/dns-' + g.id + '.pid', 'user=root', 'listen-address=127.0.0.1',
			'server=//' + '127.0.0.1', 'server=/' + m.local_domain + '/127.0.0.1',
			'server=/in-addr.arpa/127.0.0.1', 'server=/ip6.arpa/127.0.0.1'];
		for (let j = 0; j < length(m.lans); j++) push(conf, 'interface=' + m.lans[j]);
		// Local answers remain available; VPN queries have exactly one guarded upstream.
		push(conf, 'server=' + (g.default_action === 'vpn' ? m.vpn_dns + '@198.18.0.1' : m.wan_dns));
		for (let j = 0; j < length(g.rules); j++) {
			let r = g.rules[j];
			if (r.kind === 'domain') {
				append(n, 'add set inet csqtt ' + r.set + ' { type ipv4_addr; flags interval; auto-merge; size 16384; }');
				let sets = [], seen = false;
				for (let k = 0; k < j; k++) if (g.rules[k].kind === 'domain' && g.rules[k].value === r.value) seen = true;
				// dnsmasq chooses the longest matching suffix. Populate every matching
				// ancestor set too, so nft rule order remains authoritative.
				for (let k = 0; k < length(g.rules); k++)
					if (g.rules[k].kind === 'domain' && suffix(r.value, g.rules[k].value))
						push(sets, '4#inet#csqtt#' + g.rules[k].set);
				if (!seen) push(conf, 'nftset=/' + r.value + '/' + join(',', sets));
				// Translate ordered suffix rules into dnsmasq's longest-suffix semantics.
				let dnsAction = r.action;
				for (let k = 0; k < j; k++) if (g.rules[k].kind === 'domain' && suffix(r.value, g.rules[k].value)) {
					dnsAction = g.rules[k].action; break;
				}
				if (!seen) push(conf, 'server=/' + r.value + '/' + (dnsAction === 'vpn' ? m.vpn_dns + '@198.18.0.1' : m.wan_dns));
			}
			rule(n, gc, 'ip daddr ' + (r.kind === 'domain' ? '@' + r.set : r.value) +
				' meta mark set (meta mark & 0x9fffffff) | ' + (r.action === 'vpn' ? VPN : WAN) + ' return');
		}
		rule(n, gc, 'meta mark set (meta mark & 0x9fffffff) | ' + (g.default_action === 'vpn' ? VPN : WAN));
		rule(n, 'classify', 'meta nfproto ipv4 ether saddr ' + macs + ' goto ' + gc);
		rule(n, 'dns_redirect', 'iifname ' + lan + ' ether saddr ' + macs +
			' meta l4proto { tcp, udp } th dport 53 redirect to :' + g.port);
		rule(n, 'input_guard', 'iifname ' + lan + ' ether saddr ' + macs +
			' meta l4proto { tcp, udp } th dport ' + g.port + ' return');
		push(dns, { id: g.id, port: g.port, config: join('\n', conf) + '\n' });
	}
	if (length(allmacs)) {
		if (length(protectedmacs)) rule(n, 'forward_guard', 'meta nfproto ipv6 ether saddr ' + setvalues(protectedmacs, false) + ' reject');
		rule(n, 'forward_guard', 'ether saddr ' + setvalues(allmacs, false) + ' meta nfproto ipv4 meta mark & ' + MASK + ' == ' + VPN + ' oifname != "csqtt0" reject');
		// Prevent routing escape during a partially restored routing policy.
		rule(n, 'forward_guard', 'ether saddr ' + setvalues(allmacs, false) + ' meta nfproto ipv4 meta mark & ' + MASK + ' == 0 drop');
	}
	rule(n, 'input_guard', 'meta l4proto { tcp, udp } th dport 5400-5415 drop');
	return { nft: join('\n', n) + '\n', dns: dns, model: m, active: length(allmacs) > 0,
		forward: 'iifname ' + lan + ' oifname "csqtt0" meta nfproto ipv4 meta mark & ' + MASK + ' == ' + VPN + ' accept\n',
		input: 'iifname ' + lan + ' meta l4proto { tcp, udp } th dport 5400-5415 accept\n' };
};

// Separate persistent chain: a failed apply keeps old and proposed clients closed.
export function hold(models, closed) {
	let lines = ['add table inet csqtt', 'add chain inet csqtt maintenance_guard { type filter hook forward priority -20; policy accept; }',
		'flush chain inet csqtt maintenance_guard',
		'add chain inet csqtt maintenance_dns { type filter hook input priority -20; policy accept; }',
		'flush chain inet csqtt maintenance_dns'];
	let macs = [], lans = [], locals = [];
	for (let i = 0; i < length(models); i++) {
		let m = models[i];
		if (!m) continue;
		for (let j = 0; j < length(m.devices); j++) if (index(macs, m.devices[j].mac) < 0) push(macs, m.devices[j].mac);
		for (let j = 0; j < length(m.lans); j++) if (index(lans, m.lans[j]) < 0) push(lans, m.lans[j]);
		for (let j = 0; j < length(m.locals); j++) if (index(locals, m.locals[j]) < 0) push(locals, m.locals[j]);
	}
	if (closed && length(macs)) {
		rule(lines, 'maintenance_guard', 'iifname != ' + setvalues(lans, true) + ' return');
		rule(lines, 'maintenance_guard', 'oifname ' + setvalues(lans, true) + ' return');
		if (length(locals)) rule(lines, 'maintenance_guard', 'ip daddr ' + setvalues(locals, false) + ' return');
		rule(lines, 'maintenance_guard', 'ether saddr ' + setvalues(macs, false) + ' reject');
		// Before first publication, router DNS can still recurse over WAN. Old
		// group listeners may also use WAN while their replacement is staged.
		// Pause DNS, including local names, until the ready transaction releases
		// both guards. Other LAN management and router-origin DNS stay available.
		rule(lines, 'maintenance_dns', 'iifname ' + setvalues(lans, true) + ' ether saddr ' + setvalues(macs, false) +
			' meta l4proto { tcp, udp } th dport { 53, 5400-5415 } reject');
	}
	return join('\n', lines) + '\n';
};

// The legacy backend has no rules in vendor-owned chains in its restore
// payload. The adapter owns explicit jumps only; native qualification is a
// separate gate, never inferred from successfully rendering these files.
export function compile_legacy(input) {
	let base = compile(input), m = base.model, sets = [], dns = [], names = {}, used = {};
	for (let i = 0; i < length(m.rules); i++) {
		let r = m.rules[i];
		if (r.kind !== 'domain') continue;
		let name = 'csq_' + domainkey(r.id + ':' + r.value);
		if (used[name] && used[name] !== r.set) fail('Legacy DNS set collision');
		used[name] = r.set; names[r.set] = name;
		push(sets, 'create ' + name + ' hash:net family inet hashsize 1024 maxelem 16384 -exist');
	}
	for (let i = 0; i < length(base.dns); i++) {
		let d = base.dns[i], rows = split(d.config, '\n'), converted = [];
		for (let j = 0; j < length(rows); j++) {
			let line = rows[j];
			if (substr(line, 0, 7) === 'nftset=') {
				let parts = split(substr(line, 7), '/'), nftsets = split(parts[2], ','), target = [];
				for (let k = 0; k < length(nftsets); k++) {
					let fields = split(nftsets[k], '#'), mapped = names[fields[3]];
					if (!mapped) fail('Invalid legacy DNS set');
					push(target, mapped);
				}
				line = 'ipset=/' + parts[1] + '/' + join(',', target);
			}
			push(converted, line);
		}
		push(dns, { id: d.id, port: d.port, config: join('\n', converted) });
	}
	let v4 = ['*mangle', ':CSQ_CLASS - [0:0]', ':CSQ_LAN - [0:0]', '-F CSQ_CLASS', '-F CSQ_LAN'];
	for (let i = 0; i < length(m.lans); i++) push(v4, '-A CSQ_CLASS -i ' + m.lans[i] + ' -g CSQ_LAN');
	for (let i = 0; i < length(m.groups); i++) if (length(m.groups[i].macs)) {
		push(v4, ':CSQ_G' + i + ' - [0:0]'); push(v4, '-F CSQ_G' + i);
	}
	// Clear only our two bits. Every forwarded packet is classified, including
	// established connections, so stale connmarks cannot overrule new policies.
	push(v4, '-A CSQ_LAN -j MARK --set-xmark 0x0/' + MASK);
	push(v4, '-A CSQ_LAN -m addrtype --dst-type LOCAL -j RETURN');
	for (let i = 0; i < length(m.locals); i++) push(v4, '-A CSQ_LAN -d ' + m.locals[i] + ' -j RETURN');
	for (let i = 0; i < length(['224.0.0.0/4', '255.255.255.255/32']); i++)
		push(v4, '-A CSQ_LAN -d ' + ['224.0.0.0/4', '255.255.255.255/32'][i] + ' -j RETURN');
	for (let i = 0; i < 2; i++) push(v4, '-A CSQ_LAN -p ' + (i ? 'tcp' : 'udp') + ' --dport 53 -j RETURN');
	for (let i = 0; i < length(m.groups); i++) {
		let g = m.groups[i]; if (!length(g.macs)) continue;
		let chain = 'CSQ_G' + i;
		for (let j = 0; j < length(g.rules); j++) {
			let r = g.rules[j], criterion = r.kind === 'domain' ? '-m set --match-set ' + names[r.set] + ' dst' : '-d ' + r.value;
			push(v4, '-A ' + chain + ' ' + criterion + ' -j MARK --set-xmark ' + (r.action === 'vpn' ? VPN : WAN) + '/' + MASK);
			push(v4, '-A ' + chain + ' ' + criterion + ' -j RETURN');
		}
		push(v4, '-A ' + chain + ' -j MARK --set-xmark ' + (g.default_action === 'vpn' ? VPN : WAN) + '/' + MASK);
		for (let j = 0; j < length(m.lans); j++) for (let k = 0; k < length(g.macs); k++)
			push(v4, '-A CSQ_LAN -i ' + m.lans[j] + ' -m mac --mac-source ' + g.macs[k] + ' -g ' + chain);
	}
	push(v4, 'COMMIT');
	let filter = ['*filter', ':CSQ_FORWARD - [0:0]', ':CSQ_INPUT - [0:0]', ':CSQ_OUTPUT - [0:0]', '-F CSQ_FORWARD', '-F CSQ_INPUT', '-F CSQ_OUTPUT'];
	let v6 = ['*filter', ':CSQ_FORWARD - [0:0]', ':CSQ_INPUT - [0:0]', '-F CSQ_FORWARD', '-F CSQ_INPUT'];
	for (let i = 0; i < length(m.lans); i++) {
		push(filter, '-A CSQ_FORWARD -o ' + m.lans[i] + ' -j RETURN');
		push(v6, '-A CSQ_FORWARD -o ' + m.lans[i] + ' -j RETURN');
	}
	for (let i = 0; i < length(m.locals); i++) push(filter, '-A CSQ_FORWARD -d ' + m.locals[i] + ' -j RETURN');
	push(filter, '-A CSQ_OUTPUT -s 198.18.0.1/32 ! -o csqtt0 -j REJECT');
	let nat = ['*nat', ':CSQ_DNS - [0:0]', ':CSQ_NAT - [0:0]', '-F CSQ_DNS', '-F CSQ_NAT', '-A CSQ_NAT -o csqtt0 -j MASQUERADE'];
	for (let i = 0; i < length(m.groups); i++) {
		let g = m.groups[i];
		for (let j = 0; j < length(m.lans); j++) for (let k = 0; k < length(g.macs); k++) {
			let client = '-i ' + m.lans[j] + ' -m mac --mac-source ' + g.macs[k];
			push(filter, '-A CSQ_FORWARD ' + client + ' -m mark --mark ' + VPN + '/' + MASK + ' ! -o csqtt0 -j REJECT');
			push(filter, '-A CSQ_FORWARD ' + client + ' -m mark --mark 0x0/' + MASK + ' -j DROP');
			push(filter, '-A CSQ_FORWARD ' + client + ' -m mark --mark ' + VPN + '/' + MASK + ' -o csqtt0 -j ACCEPT');
			if (g.protected) {
				push(v6, '-A CSQ_FORWARD ' + client + ' -j REJECT');
				// The guarded resolver path is IPv4; never let IPv6 DNS recurse
				// through the vendor router's ordinary WAN resolver instead.
				for (let p = 0; p < 2; p++) push(v6, '-A CSQ_INPUT ' + client + ' -p ' + (p ? 'tcp' : 'udp') + ' --dport 53 -j REJECT');
			}
			for (let p = 0; p < 2; p++) {
				let protocol = p ? 'tcp' : 'udp';
				push(nat, '-A CSQ_DNS ' + client + ' -p ' + protocol + ' --dport 53 -j REDIRECT --to-ports ' + g.port);
				push(filter, '-A CSQ_INPUT ' + client + ' -p ' + protocol + ' --dport ' + g.port + ' -j ACCEPT');
			}
		}
	}
	push(filter, '-A CSQ_INPUT -i lo -j RETURN'); push(v6, '-A CSQ_INPUT -i lo -j RETURN');
	for (let p = 0; p < 2; p++) {
		let tail = '-p ' + (p ? 'tcp' : 'udp') + ' --dport 5400:5415 -j DROP';
		push(filter, '-A CSQ_INPUT ' + tail); push(v6, '-A CSQ_INPUT ' + tail);
	}
	push(filter, 'COMMIT'); push(v6, 'COMMIT'); push(nat, 'COMMIT');
	return { model: m, active: base.active, dns: dns, ipset: join('\n', sets) + '\n',
		ipv4: join('\n', v4) + '\n' + join('\n', filter) + '\n' + join('\n', nat) + '\n', ipv6: join('\n', v6) + '\n' };
};

export function hold_legacy(models, closed, ipv6) {
	let lines = ['*filter', ':CSQ_HOLD - [0:0]', ':CSQ_HOLD_DNS - [0:0]', '-F CSQ_HOLD', '-F CSQ_HOLD_DNS'];
	if (closed) for (let i = 0; i < length(models); i++) {
		let m = models[i]; if (!m) continue;
		for (let j = 0; j < length(m.lans); j++) push(lines, '-A CSQ_HOLD -o ' + m.lans[j] + ' -j RETURN');
		if (!ipv6) for (let j = 0; j < length(m.locals); j++) push(lines, '-A CSQ_HOLD -d ' + m.locals[j] + ' -j RETURN');
	}
	if (closed) for (let i = 0; i < length(models); i++) {
		let m = models[i]; if (!m) continue;
		for (let j = 0; j < length(m.lans); j++) for (let k = 0; k < length(m.devices); k++) {
			let client = '-i ' + m.lans[j] + ' -m mac --mac-source ' + m.devices[k].mac;
			push(lines, '-A CSQ_HOLD ' + client + ' -j REJECT');
			for (let p = 0; p < 2; p++) push(lines, '-A CSQ_HOLD_DNS ' + client + ' -p ' + (p ? 'tcp' : 'udp') + ' -m multiport --dports 53,5400:5415 -j REJECT');
		}
	}
	push(lines, 'COMMIT'); return join('\n', lines) + '\n';
};

// fw3 flush removes xtables chains. This independent nft table deliberately
// survives that operation: lost classification/redirects fail closed until the
// owned xtables policy is restored. It does not replace the vendor firewall.
export function legacy_guard(models, closed) {
	let n = ['add table inet csqtt_legacy'];
	for (let i = 0; i < 3; i++) {
		let chain = ['forward', 'input', 'output'][i];
		push(n, 'add chain inet csqtt_legacy ' + chain + ' { type filter hook ' + chain + ' priority -30; policy accept; }');
		push(n, 'flush chain inet csqtt_legacy ' + chain);
	}
	push(n, 'add rule inet csqtt_legacy output ip saddr 198.18.0.1 oifname != "csqtt0" reject');
	let lans = [], locals = [];
	for (let i = 0; i < length(models); i++) {
		let m = models[i]; if (!m) continue;
		for (let j = 0; j < length(m.lans); j++) if (index(lans, m.lans[j]) < 0) push(lans, m.lans[j]);
		for (let j = 0; j < length(m.locals); j++) if (index(locals, m.locals[j]) < 0) push(locals, m.locals[j]);
	}
	if (length(lans)) {
		push(n, 'add rule inet csqtt_legacy forward iifname != ' + setvalues(lans, true) + ' return');
		push(n, 'add rule inet csqtt_legacy forward oifname ' + setvalues(lans, true) + ' return');
		if (length(locals)) push(n, 'add rule inet csqtt_legacy forward ip daddr ' + setvalues(locals, false) + ' return');
		for (let i = 0; i < length(models); i++) {
			let m = models[i]; if (!m) continue;
			for (let j = 0; j < length(m.groups); j++) {
				let g = m.groups[j]; if (!length(g.macs)) continue;
				let client = 'ether saddr ' + setvalues(g.macs, false);
				if (closed) push(n, 'add rule inet csqtt_legacy forward ' + client + ' reject');
				else {
					if (g.protected) push(n, 'add rule inet csqtt_legacy forward meta nfproto ipv6 ' + client + ' reject');
					push(n, 'add rule inet csqtt_legacy forward meta nfproto ipv4 ' + client + ' meta mark & ' + MASK + ' == ' + VPN + ' oifname != "csqtt0" reject');
					push(n, 'add rule inet csqtt_legacy forward meta nfproto ipv4 ' + client + ' meta mark & ' + MASK + ' == 0 drop');
				}
				// Normal IPv4 DNS has already been redirected to its group port.
				// On fw3 flush the redirect vanishes; block router/WAN recursion.
				push(n, 'add rule inet csqtt_legacy input iifname ' + setvalues(m.lans, true) + ' ' + client +
					' meta l4proto { tcp, udp } th dport ' + (closed ? '{ 53, 5400-5415 }' : '53') + ' reject');
			}
		}
	}
	return join('\n', n) + '\n';
};
