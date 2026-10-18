// Test context only. Reads owner data privately; never arms or changes policies.
import * as fs from 'fs';
import { cursor } from 'uci';
import { connect } from 'ubus';
import { hold } from '/usr/share/csqtt/policy.uc';
let state = ARGV[0], c = cursor(), stage = 'path';
function fail() { printf('context_prepare=false\ncontext_failure=%s\n', stage); exit(1); }
function save(name, data) {
 if (fs.writefile(state + '/' + name, data) == null || !fs.chmod(state + '/' + name, 0600)) fail();
}
function word(s) { return !!match(s || '', /^[A-Za-z0-9_]+$/); }
function mac(s) { return !!match(s || '', /^02(:[0-9a-f]{2}){5}$/); }
try {
 if (!match(state || '', /^\/etc\/csqtt\/backups\/boot7-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$/)) fail();
 let st = fs.stat(state);
 if (!st || st.uid !== 0 || st.mode !== 0700 || fs.readlink(state)) fail();
 stage = 'model';
 let m = json(fs.readfile('/etc/csqtt/policy.json'));
 if (!m || !length(m.devices || []) || join(',', m.lans || []) !== 'br-lan') fail();
 stage = 'domain_group';
 let selected = null, set = null;
 for (let group in m.groups || []) {
  if (!group.protected || !length(group.macs || []) || !word(group.id)) continue;
  for (let rule in group.rules || []) {
   if (rule.kind === 'domain' && match(rule.set || '', /^d_[A-Za-z0-9_]+_[0-9]+$/)) {
    selected = group; set = rule.set; break;
   }
  }
  if (selected) break;
 }
 if (!selected || selected.port < 5400 || selected.port > 5415) fail();
 stage = 'synthetic_macs';
 let pair = split(trim(fs.readfile(state + '/synthetic-macs') || ''), '\n');
 if (length(pair) !== 2 || !mac(pair[0]) || !mac(pair[1]) || pair[0] === pair[1]) fail();
 let occupied = lc((fs.readfile('/tmp/dhcp.leases') || '') + (fs.readfile('/proc/net/arp') || ''));
 for (let address in pair) {
  if (index(occupied, address) >= 0) fail();
  for (let dev in m.devices) if (lc(dev.mac || '') === address) fail();
  c.foreach('csqtt', 'device', function(dev) { if (lc(dev.mac || '') === address) fail(); });
 }
 stage = 'proposed_model';
 let extra = json(sprintf('%J', m));
 push(extra.devices, { id: 'cqboot7_device', mac: pair[0], group: selected.id });
 for (let group in extra.groups) if (group.id === selected.id) push(group.macs, pair[0]);
 stage = 'lan_address';
 let connection = split(trim(getenv('SSH_CONNECTION') || ''), /[[:space:]]+/);
 let server = connection[2], confirmed = false, b = connect();
 let net = b ? b.call('network.interface', 'dump', {}) : null;
 for (let intf in (net ? net.interface : [])) {
  if (!intf.up || (intf.l3_device || intf.device) !== 'br-lan') continue;
  for (let address in intf['ipv4-address'] || []) if (address.address === server) confirmed = true;
 }
 if (!confirmed) fail();
 if (type(server) !== 'string' || !match(server, /^[0-9]{1,3}(\.[0-9]{1,3}){3}$/)) fail();
 for (let part in split(server, '.')) if (+part > 255 || '' + (+part) !== part) fail();
 let values = {
  LAN: 'br-lan', SERVER: server, GROUP: selected.id, MAC: pair[0], FREE_MAC: pair[1],
  NS: 'cqboot7p', FREE_NS: 'cqboot7u', HOST: 'cqboot7hp', PEER: 'cqboot7pp',
  FREE_HOST: 'cqboot7hu', FREE_PEER: 'cqboot7pu', TABLE: 'cq_boot7',
  ROUTER_IP: '198.19.7.1', CLIENT_IP: '198.19.7.2', FREE_IP: '198.19.7.3',
  PREFIX: '198.19.7.0/29', DNS_PORT: '' + selected.port
 };
 let env = '';
 for (let key in values) env += key + "='" + values[key] + "'\n";
 stage = 'save';
 save('fixture.env', env);
 save('closed.nft', hold([m, extra], true));
 save('fault-set', set + '\n');
 save('identity', 'CSQTT-BOOT7\n');
 save('init-was-enabled', '1\n');
 print('context_prepare=true\n');
} catch (e) { fail(); }
