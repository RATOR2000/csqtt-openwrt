// Ignored readonly host preflight. Never print private input or exceptions.
import * as fs from 'fs';
import { cursor } from 'uci';
import { connect } from 'ubus';
// Root runner supplies validated local physical NIC facts in memory only.
let windows_adapters = [];

function command(text) {
	try {
		let p = fs.popen(text + ' 2>/dev/null; printf "\\n__BOOT7_READ_EXIT_%s\\n" "$?"', 'r');
		if (!p) return null;
		let s = p.read('all'); p.close();
		let m = match(s || '', /\n__BOOT7_READ_EXIT_0\n$/);
		return m ? substr(s, 0, length(s) - length(m[0])) : null;
	} catch (e) { return null; }
}
function listed(a, v) { for (let x in a || []) if (x === v) return true; return false; }
function ipv4(v) {
	if (!match(v || '', /^[0-9]{1,3}(\.[0-9]{1,3}){3}$/)) return false;
	for (let p in split(v, '.')) if (+p > 255 || '' + (+p) !== p) return false;
	return true;
}
function mac(v) { return !!match(v || '', /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/) && v !== '00:00:00:00:00:00'; }
function endpoint(ip, port) {
	let p = split(ip, '.');
	return sprintf('%02X%02X%02X%02X:%04X', +p[3], +p[2], +p[1], +p[0], +port);
}
function read(path) { return fs.readfile(path) || ''; }
function init_start(name) {
	let m = match(read('/etc/init.d/' + name), /\nSTART=([0-9]{1,3})(\n|\r)/);
	return m ? +m[1] : 0;
}
function init_enabled(name, start) {
	if (!start) return false;
	let path = '/etc/rc.d/' + sprintf('S%02d', start) + name;
	let target = fs.readlink(path);
	return target === '../init.d/' + name || target === '/etc/init.d/' + name;
}
function test_name(name) {
	return !!match(name, /^(cq[-_]|cqtoggle|csqtt[-_].*(boot|fault|test|probe))/);
}
function marker_count() {
	let total = 0;
	for (let dir in ['/etc/init.d', '/etc/rc.d', '/tmp', '/var/run/csqtt', '/var/lock', '/var/run/netns', '/sys/class/net']) {
		let names = fs.lsdir(dir);
		// A missing netns directory is ordinary; other inventories must be readable.
		if (names == null) { if (dir !== '/var/run/netns') return -1; continue; }
		for (let name in names) {
			let stripped = replace(name, /^[SK][0-9]{2,3}/, '');
			if (test_name(stripped) || name === 'csqtt-policy' || name === 'policy.error' ||
				name === 'dns.stop.json' || match(name, /^apply\.[0-9]+$/)) total++;
		}
	}
	if (fs.stat('/etc/csqtt/deactivated')) total++;
	return total;
}
function preflight() {
	let r = { readonly: true, root: false, ssh_connection_valid: false,
		ssh_tcp_established: false, ssh_server_on_lan: false, ssh_client_route_lan: false,
		ssh_arp_complete: false, ssh_neighbor_complete: false, ssh_client_mac_proven: false,
		active_device_flags_valid: true, ssh_client_active_assignments: 0,
		ssh_client_no_active_assignment: false, ssh_client_lan_unassigned: false,
		uci_pending_configs_checked: 0, uci_pending_edits_absent: false,
		firewall_start: 0, dns_start: 0, csqtt_start: 0, startup_enabled: false,
		startup_order_feasible: false, persistent_hold_include_valid: false,
		fw4_print_succeeded: false, fw4_print_has_hold_include: false,
		installed_first_activation_path_present: false,
		known_fault_test_markers: 0, marker_inventory_complete: false,
		known_fault_test_markers_absent: false,
		independent_management_device_verified: false, protected_probe_source_verified: false,
		persistent_rollback_verified: false, full_boot_probe_gate_pending: true,
		preflight_ok: false, internal_error: false };
	let uid = match(read('/proc/self/status'), /\nUid:\s+([0-9]+)/);
	r.root = !!uid && +uid[1] === 0;
	if (!r.root) return r;
	let c = cursor();
	for (let package in ['csqtt', 'dhcp', 'firewall', 'network']) {
		let result = command('/sbin/uci -q changes ' + package);
		if (result != null && trim(result) === '' && c.get_all(package)) r.uci_pending_configs_checked++;
	}
	r.uci_pending_edits_absent = r.uci_pending_configs_checked === 4;
	let main = c.get_all('csqtt', 'main') || {};
	let lans = type(main.lan_device) === 'array' ? main.lan_device : [main.lan_device || 'br-lan'];
	let conn = split(trim(getenv('SSH_CONNECTION') || ''), /\s+/);
	r.ssh_connection_valid = length(conn) === 4 && ipv4(conn[0]) && ipv4(conn[2]) &&
		!!match(conn[1] || '', /^[0-9]{1,5}$/) && !!match(conn[3] || '', /^[0-9]{1,5}$/) &&
		+conn[1] > 0 && +conn[1] < 65536 && +conn[3] > 0 && +conn[3] < 65536;
	let client_mac = '';
	if (r.ssh_connection_valid) {
		let b = connect(), net = b ? b.call('network.interface', 'dump', {}) : null;
		for (let intf in (net ? net.interface : [])) {
			if (!intf.up || !listed(lans, intf.l3_device || intf.device)) continue;
			for (let address in intf['ipv4-address'] || [])
				if (address.address === conn[2]) r.ssh_server_on_lan = true;
		}
		for (let line in split(read('/proc/net/tcp'), '\n')) {
			let p = split(trim(line), /\s+/);
			if (length(p) > 3 && p[1] === endpoint(conn[2], conn[3]) &&
				p[2] === endpoint(conn[0], conn[1]) && p[3] === '01') r.ssh_tcp_established = true;
		}
		// IPv4 validation makes the only dynamic shell argument numeric dotted text.
		let route = command('/sbin/ip -4 route get ' + conn[0]);
		let route_dev = route == null ? null : match(route, /(^|[[:space:]])dev[[:space:]]+([^[:space:]]+)/);
		let dev = route_dev ? route_dev[2] : '';
		r.ssh_client_route_lan = !!route_dev && listed(lans, dev) && !match(route, /(^|\s)via\s/);
		let arp_mac = '', neigh_mac = '';
		for (let line in split(read('/proc/net/arp'), '\n')) {
			let p = split(trim(line), /\s+/);
			if (length(p) >= 6 && p[0] === conn[0] && p[2] === '0x2' && p[5] === dev && mac(lc(p[3]))) {
				if (arp_mac && arp_mac !== lc(p[3])) return r;
				arp_mac = lc(p[3]); r.ssh_arp_complete = true;
			}
		}
		let neigh = command('/sbin/ip -4 neigh show');
		for (let line in split(neigh || '', '\n')) {
			let p = split(trim(line), /\s+/);
			if (length(p) < 6 || p[0] !== conn[0] || p[1] !== 'dev' || p[2] !== dev || p[3] !== 'lladdr') continue;
			if (!mac(lc(p[4])) || !listed(['REACHABLE', 'STALE', 'DELAY', 'PROBE', 'PERMANENT'], p[5])) continue;
			if (neigh_mac && neigh_mac !== lc(p[4])) return r;
			neigh_mac = lc(p[4]); r.ssh_neighbor_complete = true;
		}
		r.ssh_client_mac_proven = r.ssh_arp_complete && r.ssh_neighbor_complete && arp_mac === neigh_mac;
		if (r.ssh_client_mac_proven) client_mac = arp_mac;
	}
	c.foreach('csqtt', 'device', function(s) {
		if (s.enabled != null && s.enabled !== '0' && s.enabled !== '1') r.active_device_flags_valid = false;
		if (client_mac && lc(s.mac || '') === client_mac && s.enabled !== '0') r.ssh_client_active_assignments++;
	});
	r.ssh_client_no_active_assignment = r.ssh_client_mac_proven && r.active_device_flags_valid &&
		r.ssh_client_active_assignments === 0;
	r.ssh_client_lan_unassigned = r.ssh_tcp_established && r.ssh_server_on_lan &&
		r.ssh_client_route_lan && r.ssh_client_no_active_assignment;
	for (let adapter in windows_adapters) {
		if (r.ssh_client_lan_unassigned && adapter.physical === true &&
			adapter.ip === conn[0] && lc(adapter.mac || '') === client_mac)
			r.independent_management_device_verified = true;
	}
	r.firewall_start = init_start('firewall'); r.dns_start = init_start('csqtt-dns'); r.csqtt_start = init_start('csqtt');
	r.startup_enabled = init_enabled('firewall', r.firewall_start) &&
		init_enabled('csqtt-dns', r.dns_start) && init_enabled('csqtt', r.csqtt_start);
	r.startup_order_feasible = r.startup_enabled && r.firewall_start > 0 &&
		r.firewall_start < r.dns_start && r.dns_start === 94 && r.csqtt_start === 95;
	let hold = c.get_all('firewall', 'csqtt_hold') || {};
	r.persistent_hold_include_valid = hold['.type'] === 'include' && hold.csqtt_owned === '1' &&
		hold.type === 'nftables' && hold.path === '/etc/csqtt/hold.nft' && hold.position === 'ruleset-post' &&
		hold.enabled !== '0' && !!fs.stat('/etc/csqtt/hold.nft');
	let print = command('/sbin/fw4 print');
	r.fw4_print_succeeded = print != null;
	r.fw4_print_has_hold_include = print != null && index(print, 'include "/etc/csqtt/hold.nft"') >= 0;
	let manage = read('/usr/libexec/csqtt/manage'), init = read('/etc/init.d/csqtt');
	let saved_hold = index(manage, 'runtime firewall-hold'), full_check = index(manage, 'nft -c -f "$stage/policy.nft"');
	r.installed_first_activation_path_present = saved_hold >= 0 && full_check > saved_hold &&
		index(init, '/usr/libexec/csqtt/manage prepare') >= 0;
	let count = marker_count(); r.marker_inventory_complete = count >= 0;
	r.known_fault_test_markers = count < 0 ? 0 : count;
	for (let package in ['csqtt', 'firewall', 'network', 'dhcp']) c.foreach(package, null, function(s) {
		if (test_name(s['.name'] || '')) r.known_fault_test_markers++;
	});
	let tables = command('/usr/sbin/nft -j list tables');
	if (tables == null) r.marker_inventory_complete = false;
	else {
		let doc = json(tables);
		if (type(doc.nftables) !== 'array') r.marker_inventory_complete = false;
		else for (let row in doc.nftables) if (row.table && test_name(row.table.name || '')) r.known_fault_test_markers++;
	}
	r.known_fault_test_markers_absent = r.marker_inventory_complete && r.known_fault_test_markers === 0;
	r.preflight_ok = r.uci_pending_edits_absent && r.ssh_client_lan_unassigned && r.startup_order_feasible &&
		r.persistent_hold_include_valid && r.fw4_print_has_hold_include &&
		r.installed_first_activation_path_present && r.known_fault_test_markers_absent;
	return r;
}
try { let result = preflight(); printf('%J\n', result); exit(result.preflight_ok ? 0 : 1); }
catch (e) { printf('{"readonly":true,"preflight_ok":false,"internal_error":true,"full_boot_probe_gate_pending":true}\n'); exit(1); }
