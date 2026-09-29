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
	for (let i = 0; i < length(devices); i++) {
		let d = devices[i], group = null, mac = lc(clean(d.mac));
		id(d.id);
		for (let j = 0; j < i; j++) if (devices[j].id === d.id) fail('Duplicate device identifier');
		if (!match(mac, /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/) || mac === '00:00:00:00:00:00' ||
			(index('13579bdf', substr(mac, 1, 1)) >= 0)) fail('Device MAC must be unicast');
		for (let j = 0; j < i; j++) if (model.devices[j].mac === mac) fail('Device belongs to more than one group');
		for (let j = 0; j < length(model.groups); j++) if (model.groups[j].id === d.group) group = model.groups[j];
		if (!group) fail('Device refers to a missing group');
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
	model.local_domain = clean(input.local_domain || 'lan');
	if (!match(model.local_domain, /^[a-zA-Z0-9][a-zA-Z0-9.-]*$/)) fail('Invalid local DNS domain');
	return model;
}

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
	rule(n, 'forward_guard', 'ip6 daddr { fe80::/10, fc00::/7, ff00::/8 } return');
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
			'no-hosts', 'domain-needed', 'bogus-priv', 'stop-dns-rebind', 'cache-size=256',
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
}

// Separate persistent chain: a failed apply keeps old and proposed clients closed.
export function hold(models, closed) {
	let lines = ['add table inet csqtt', 'add chain inet csqtt maintenance_guard { type filter hook forward priority -20; policy accept; }',
		'flush chain inet csqtt maintenance_guard'];
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
		rule(lines, 'maintenance_guard', 'ip6 daddr { fe80::/10, fc00::/7, ff00::/8 } return');
		rule(lines, 'maintenance_guard', 'ether saddr ' + setvalues(macs, false) + ' reject');
	}
	return join('\n', lines) + '\n';
}
