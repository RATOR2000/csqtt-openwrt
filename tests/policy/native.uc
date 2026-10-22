// Run with the real ucode interpreter on Linux, independent of Node compatibility.
import * as fs from 'fs';
import { compile, validate, hold } from '../../openwrt/csqtt/files/policy.uc';
let data = json(fs.readfile('tests/policy/fixture.json'));
let result = compile(data);
function check(ok, message) { if (!ok) die(message); }
check(result.active && length(result.dns) === 2, 'expected two active DNS contexts');
check(index(result.nft, '0x40000000 oifname != "csqtt0" reject') >= 0, 'missing VPN guard');
check(index(result.dns[0].config, 'server=/secure.example.org/9.9.9.9') >= 0, 'DNS rule order changed');
check(index(hold([result.model], true), 'maintenance_guard') >= 0, 'missing maintenance guard');
check(index(result.nft, 'flush set') < 0, 'reload would flush domain sets');
check(index(result.dns[0].config, 'rebind-domain-ok=//') >= 0 && index(result.dns[0].config, 'rebind-domain-ok=/lan/') >= 0, 'local DNS reply exemptions missing');
check(index(result.dns[0].config, 'domain-needed') < 0, 'plain local names would be rejected');
check(index(result.nft, 'ip6 daddr') < 0, 'routed IPv6 would escape the guard');
check(index(result.nft, 'ip daddr @' + result.model.rules[0].set) < index(result.nft, 'ip daddr @' + result.model.rules[1].set), 'rule order changed');
let changed = json(fs.readfile('tests/policy/fixture.json'));
changed.rules[2].destination = '203.0.113.177/24';
check(compile(changed).model.rules[2].value === '203.0.113.0/24', 'CIDR host bits were not normalized');
changed.rules[0].destination = 'bad..example';
let rejected = false;
try { validate(changed); } catch (e) { rejected = true; }
check(rejected, 'invalid domain was accepted');
changed = json(fs.readfile('tests/policy/fixture.json'));
changed.devices[1].mac = changed.devices[0].mac;
rejected = false;
try { validate(changed); } catch (e) { rejected = true; }
check(rejected, 'duplicate device membership was accepted');
changed = json(fs.readfile('tests/policy/fixture.json'));
changed.rules[0].destination = 'printer.lan';
rejected = false;
try { validate(changed); } catch (e) { rejected = true; }
check(rejected, 'internet rule replaced local DNS delegation');
// Device flags must behave the same in native ucode as in the Node adapter.
for (let enabled in ['1', true]) {
	changed = json(fs.readfile('tests/policy/fixture.json'));
	for (let device in changed.devices) device.enabled = enabled;
	check(sprintf('%J', compile(changed)) === sprintf('%J', result), 'active flag changed legacy policy');
}
changed = json(fs.readfile('tests/policy/fixture.json'));
changed.devices[0].enabled = '0';
let inactive = compile(changed);
check(length(inactive.model.devices) === 1 && inactive.model.devices[0].id === 'b', 'disabled device stayed in active model');
check(length(inactive.model.groups[0].macs) === 0 && length(inactive.model.groups[1].macs) === 1, 'disabled group MAC membership leaked');
check(length(inactive.dns) === 1 && inactive.dns[0].id === 'direct', 'disabled group retained DNS redirect context');
check(index(inactive.nft, changed.devices[0].mac) < 0 && index(inactive.nft, 'goto g_private') < 0, 'disabled device retained routing or IPv6 guard');
check(index(inactive.nft, changed.devices[1].mac) >= 0 && index(inactive.nft, 'meta nfproto ipv6') >= 0, 'remaining active device lost protection');
check(index(hold([result.model, inactive.model], true), changed.devices[0].mac) >= 0, 'disable transaction lost previous device guard');
changed.devices[1].enabled = false;
inactive = compile(changed);
let unassigned = json(fs.readfile('tests/policy/fixture.json'));
unassigned.devices = [];
check(!inactive.active && length(inactive.model.devices) === 0 && length(inactive.dns) === 0, 'all disabled devices still activated policies');
check(sprintf('%J', inactive) === sprintf('%J', compile(unassigned)), 'all disabled policy differs from unassigned WAN clients');
changed.devices[0].enabled = '1'; changed.devices[1].enabled = true;
check(sprintf('%J', compile(changed)) === sprintf('%J', result), 'reenabling did not restore original policy');
for (let invalid in ['id', 'mac', 'group', 'duplicate_id', 'duplicate_mac']) {
	changed = json(fs.readfile('tests/policy/fixture.json'));
	changed.devices[0].enabled = '0'; changed.devices[1].enabled = false;
	if (invalid === 'id') changed.devices[0].id = '../bad';
	if (invalid === 'mac') changed.devices[0].mac = '01:00:00:00:00:01';
	if (invalid === 'group') changed.devices[0].group = 'missing';
	if (invalid === 'duplicate_id') changed.devices[1].id = changed.devices[0].id;
	if (invalid === 'duplicate_mac') {
		changed.devices[0].mac = '02:AA:BB:CC:DD:01';
		changed.devices[1].mac = '02:aa:bb:cc:dd:01';
	}
	rejected = false;
	try { validate(changed); } catch (e) { rejected = true; }
	check(rejected, 'disabled stored device bypassed ' + invalid + ' validation');
}
for (let enabled in ['', 'false', 'true', 'yes', '2', 0, 1, [], {}, '0\n']) {
	changed = json(fs.readfile('tests/policy/fixture.json'));
	changed.devices[0].enabled = enabled;
	rejected = false;
	try { validate(changed); } catch (e) { rejected = true; }
	check(rejected, 'malformed native device flag was accepted');
}
if (ARGV[0]) {
	fs.writefile(ARGV[0] + '/native-policy.nft', result.nft);
	fs.writefile(ARGV[0] + '/native-hold.nft', hold([result.model], true));
	fs.writefile(ARGV[0] + '/native-release.nft', hold([], false));
	fs.writefile(ARGV[0] + '/native-model.json', sprintf('%J', result.model));
	for (let i = 0; i < length(result.dns); i++)
		fs.writefile(ARGV[0] + '/native-dns-' + result.dns[i].id + '.conf', result.dns[i].config);
}
print('Native ucode policy assertions passed\n');
