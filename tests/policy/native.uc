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
if (ARGV[0]) {
	fs.writefile(ARGV[0] + '/native-policy.nft', result.nft);
	fs.writefile(ARGV[0] + '/native-hold.nft', hold([result.model], true));
	fs.writefile(ARGV[0] + '/native-release.nft', hold([], false));
	fs.writefile(ARGV[0] + '/native-model.json', sprintf('%J', result.model));
	for (let i = 0; i < length(result.dns); i++)
		fs.writefile(ARGV[0] + '/native-dns-' + result.dns[i].id + '.conf', result.dns[i].config);
}
print('Native ucode policy assertions passed\n');
