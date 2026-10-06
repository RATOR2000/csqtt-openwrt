// Exercise the complete runtime source with real ucode and isolated in-memory adapters.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/runtime.uc'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '');
const adapters = `
let native_files = {};
let native_sections = {};
let native_services = {}, native_network = { interface: [] }, native_allow_write = false, native_service_unavailable = false;
let fs = {
  readfile: function(p) { return native_files[p]; },
  readlink: function(p) { return native_files[p]; },
  lsdir: function(p) {
    let entries=[];
    for (let f in native_files) {
      if (native_files[f] == null || substr(f,0,length(p)+1) !== p+'/') continue;
      let entry=split(substr(f,length(p)+1),'/')[0];
      let seen=false; for (let i=0; i<length(entries); i++) if (entries[i] === entry) seen=true;
      if (!seen) push(entries,entry);
    }
    return length(entries) || native_files[p] != null ? entries : null;
  },
  stat: function(p) {
    if (native_files[p] != null) return {};
    for (let f in native_files) if (native_files[f] != null && substr(f,0,length(p)+1) === p+'/') return {};
    return null;
  },
  writefile: function(p,v) { if (!native_allow_write) die('Native runtime test attempted a file write'); native_files[p]=v; return length(v); },
  chmod: function() { if (!native_allow_write) die('Native runtime test attempted a permission change'); }
};
function cursor() {
  return {
    get: function(p, s, option) { return option === 'enabled' ? '0' : null; },
    foreach: function(p, kind, callback) {
      for (let section in native_sections[p + '/' + kind] || []) callback(section);
    }
  };
}
function connect() { return { call: function(object,method,args) { return object === 'network.interface' ? native_network : (native_service_unavailable ? null : { [args.name]: native_services[args.name] }); } }; }
function compile() { die('Unexpected native runtime compile call'); }
function hold() { die('Unexpected native runtime hold call'); }
`;
const assertions = `
function check(ok, message) { if (!ok) die(message); }
function rejects(main, expected) {
  let message = null;
  try { client(main); } catch (e) { message = e.message; }
  check(message === expected, 'Native runtime rejected with the wrong error');
}
let secret = sprintf('%032x', time());
let hash = sprintf('%032x', time() + 1);
check(client({ enabled: '0' }).password === '', 'Disabled empty client failed');
for (let code = 0; code <= 32; code++) {
  if (code < 32) rejects({ password: secret + chr(code) }, 'Invalid password');
  rejects({ peer: 'host' + chr(code) + ':443' }, 'Invalid peer');
}
rejects({ password: secret + chr(127) }, 'Invalid password');
rejects({ peer: 'host' + chr(127) + ':443' }, 'Invalid peer');
rejects({ password: secret + '|' }, 'Invalid password');
let accepted = secret + ' space Кафе';
check(client({ password: accepted }).password === accepted, 'Valid password changed');
let boundary = '';
for (let i = 0; i < 128; i++) boundary += 'a';
check(client({ password: boundary }).password === boundary, 'Password boundary rejected');
rejects({ password: boundary + 'a' }, 'Invalid password');
for (let peer in ['server.example:443', '192.0.2.1:443', '[2001:db8::1]:443'])
  check(client({ peer: peer }).peer === peer, 'Valid peer rejected');
rejects({ enabled: '1' }, 'Enabled client needs peer, password and VK hashes');
check(length(client({ enabled: '1', peer: 'host:443', password: secret, vk_hashes: [hash] }).vk_hashes) === 1, 'Valid enabled client rejected');
let long_hash = '';
for (let i = 0; i < 1024; i++) long_hash += 'a';
check(length(client({ vk_hashes: [substr(long_hash, 0, 16)] }).vk_hashes[0]) === 16, 'Minimum VK hash rejected');
check(length(client({ vk_hashes: [long_hash] }).vk_hashes[0]) === 1024, 'Maximum VK hash rejected');
rejects({ vk_hashes: [substr(long_hash, 0, 15)] }, 'Invalid VK hash');
rejects({ vk_hashes: [long_hash + 'a'] }, 'Invalid VK hash');
rejects({ vk_hashes: [hash + '!'] }, 'Invalid VK hash');
native_files['/var/run/csqtt/status.json'] = sprintf('%J', {
  state: 'connected', password: secret, vk_hashes: [hash], pairing_grant: secret,
  error_code: secret, captcha: { id: 'public-id', state: 'pending', expires_at: 1, session_token: secret }
});
let redacted = sprintf('%J', status());
check(index(redacted, secret) < 0 && index(redacted, hash) < 0, 'Status exposed private fields');
check(status().core.captcha.id === 'public-id', 'Status lost safe CAPTCHA metadata');
native_files['/tmp/dhcp.leases'] = '0 02:00:00:00:00:01 192.0.2.10 desktop *\\n';
native_files['/proc/net/arp'] = 'IP address HW type Flags HW address Mask Device\\n192.0.2.10 0x1 0x2 02:00:00:00:00:01 * br-lan\\n';
let discovered = devices();
check(length(discovered) === 1 && discovered[0].online && discovered[0].ip === '192.0.2.10', 'Native whitespace lease parsing failed');
native_sections['csqtt/device'] = [
  { '.name': 'legacy', mac: '02:00:00:00:00:01', group: 'private' },
  { '.name': 'parked', mac: '02:00:00:00:00:02', group: 'private', name: 'Saved device', enabled: '0' },
  { '.name': 'explicit', mac: '02:00:00:00:00:03', group: 'direct', enabled: '1' }
];
function by_mac(rows, mac) {
  for (let row in rows) if (row.mac === mac) return row;
  return null;
}
for (let flag in ['0', false]) {
  native_sections['csqtt/device'][1].enabled = flag;
  discovered = devices();
  let parked = by_mac(discovered, '02:00:00:00:00:02');
  check(length(discovered) === 3 && parked.enabled === false && parked.group == null && parked.name === 'Saved device', 'Native device RPC exposed inactive group or lost saved row');
  check(by_mac(discovered, '02:00:00:00:00:01').group === 'private' && by_mac(discovered, '02:00:00:00:00:03').group === 'direct', 'Native device RPC lost active assignments');
}
for (let flag in ['1', true]) {
  native_sections['csqtt/device'][1].enabled = flag;
  let restored = by_mac(devices(), '02:00:00:00:00:02');
  check(restored.group === 'private' && restored.enabled == null, 'Native device RPC did not restore active membership');
}
for (let flag in ['', 'false', 'true', 'yes', '2', 0, 1]) {
  native_sections['csqtt/device'][1].enabled = flag;
  let rejected = false;
  try { devices(); } catch (e) { rejected = e.message === 'Device enabled must be 0 or 1'; }
  check(rejected, 'Native device RPC accepted malformed device flag');
}
native_sections['csqtt/device'][1].enabled = '0';
for (let count in [0, 1, 2]) {
  let active = [];
  for (let i = 0; i < count; i++) push(active, { id: 'active' + i });
  native_files['/etc/csqtt/policy.json'] = sprintf('%J', { groups: [{ id: 'private' }], devices: active, rules: [] });
  check(status().devices === count && status().policies_active === (count > 0), 'Native status counted saved rows instead of active policy assignments');
}
native_sections = {};
native_network={ interface:[{ l3_device:'br-lan', 'ipv4-address':[{ address:'192.168.1.1', mask:24 }] }] };
native_services={ 'csqtt-dns':{ instances:{ dns_private:{ running:true,pid:901 } } } };
native_files['/etc/csqtt/policy.json']=sprintf('%J',{ lans:['br-lan'],groups:[{ id:'private',port:5400,macs:['02:00:00:00:00:01'] }] });
native_files['/var/run/csqtt/dns.ids']='private\\n';
check(!dns_ready(), 'Native DNS readiness accepted a process without listeners');
native_files['/proc/901/fd/4']='socket:[1101]';
native_files['/proc/901/fd/5']='socket:[2101]';
let header='sl local_address rem_address st tx_queue rx_queue uid timeout inode\\n';
native_files['/proc/net/udp']=header+'0: 0101A8C0:1518 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 1101\\n';
native_files['/proc/net/tcp']=header+'0: 0101A8C0:1518 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 2101\\n';
check(dns_ready(), 'Native DNS readiness rejected owned UDP/TCP LAN listeners');
for (let ids in [null,'','unknown\\n','private\\nprivate\\n']) {
  native_files['/var/run/csqtt/dns.ids']=ids;
  check(!dns_ready(), 'Native DNS readiness accepted incomplete or invalid active group IDs');
}
native_files['/var/run/csqtt/dns.ids']='private\\n';
native_service_unavailable=true;
check(!dns_ready(), 'Native DNS readiness accepted unavailable service inspection');
native_service_unavailable=false;
native_files['/proc/901/fd/4']='socket:[9999]';
check(!dns_ready(), 'Native DNS readiness accepted another process socket');
native_files['/proc/901/fd/4']='socket:[1101]';
native_services['csqtt-dns'].instances.dns_private.pid=902;
check(!dns_ready(), 'Native DNS readiness accepted stale PID sockets');
native_services['csqtt-dns'].instances.dns_private.pid=901;
native_allow_write=true; dns_snapshot(); native_allow_write=false;
native_services={};
check(!dns_stopped(), 'Native DNS stop ignored a surviving captured PID');
native_files['/proc/901/fd/4']=null; native_files['/proc/901/fd/5']=null;
check(dns_stopped(), 'Native DNS stop did not recognize old process exit');
print('Native ucode runtime parser, control validation, redaction and DNS lifecycle passed\\n');
`;
const source = adapters + runtime + assertions;
if (process.argv[2]) fs.writeFileSync(process.argv[2], source);
else process.stdout.write(source);
