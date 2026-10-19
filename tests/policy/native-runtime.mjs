// Exercise the complete runtime source with real ucode and isolated in-memory adapters.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/runtime.uc'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '');
const health = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/health.uc'), 'utf8').replaceAll('export function', 'function');
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
  rename: function(a,b) { if (!native_allow_write) die('Native runtime test attempted a rename'); native_files[b]=native_files[a]; native_files[a]=null; return true; },
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
let recovery_ctx = { boot_id: 'fixture-boot', config_epoch: 'fixture-config', network_epoch: 'fixture-network',
  process_epoch: 'fixture-process', intent: 'fixture-intent', automatic: true, process: 'ok', now: 0, gate: null };
let wan_fixture = { schema_version: 1, config_valid: true, completed: true, endpoints: [
  { index: 0, dns: 'ok', https: 'ok', reachable: true }, { index: 1, dns: 'ok', https: 'ok', reachable: true } ] };
let vpn_fixture = { schema_version: 1, config_valid: true, completed: true, endpoints: [
  { index: 0, dns: 'ok', https: 'fail', reachable: false }, { index: 1, dns: 'ok', https: 'fail', reachable: false } ] };
let recovery_fixture = null;
for (let elapsed = 0; elapsed <= 180; elapsed += 30) {
  recovery_ctx.now = elapsed;
  recovery_fixture = health_advance(recovery_fixture, recovery_ctx, wan_fixture, vpn_fixture);
  if (elapsed < 180) check(!recovery_fixture.action, 'Native recovery ignored confirmation interval');
}
check(recovery_fixture.action === 'soft', 'Native confirmed failure did not request soft repair');
recovery_ctx.wan = wan_fixture; recovery_ctx.vpn = vpn_fixture;
recovery_fixture = health_reserve(recovery_fixture, recovery_ctx, 'soft');
check(recovery_fixture && length(recovery_fixture.attempts) === 1, 'Native recovery did not reserve budget');
recovery_fixture = health_complete(recovery_fixture, recovery_ctx, 'soft', true);
recovery_ctx.now = 210;
recovery_fixture = health_advance(recovery_fixture, recovery_ctx, wan_fixture, vpn_fixture);
check(recovery_fixture.action === 'transport', 'Native soft repair did not require a fresh later sample');
recovery_ctx.gate = 'disabled';
let stopped_public = health_public(recovery_fixture, recovery_ctx);
check(stopped_public.health.state === 'disabled' && stopped_public.recovery.state === 'paused', 'Native Stop did not invalidate old public health');
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
check(status().core.captcha == null, 'Stopped status exposed an expired challenge');
native_services={ csqtt:{ instances:{ client:{ running:true,pid:777 } } } };
native_files['/proc/uptime']='100.00 0.00'; native_files['/proc/sys/kernel/random/boot_id']='fixture-boot';
native_files['/proc/777/stat']='777 (csqtt test) S 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1234 0';
native_files['/var/run/csqtt/status.json']=sprintf('%J',{state:'captcha_required',active_workers:4,pid:777,
  process_startticks:1234,boot_id:'fixture-boot',updated_boottime_ms:99000,
  captcha:{id:'public-id',state:'pending',expires_at:time()+100,human_active:false}});
check(status().core.state === 'connected' && status().core.captcha.id === 'public-id', 'Current useful workers lost to a CAPTCHA warning');
native_files['/proc/uptime']='116.00 0.00';
check(status().core.state === 'starting' && status().core.captcha == null, 'Stale process status survived monotonic expiry');
let clock_status=json(native_files['/var/run/csqtt/status.json']);
clock_status.health={human_epoch:7};
for (let clock in [{text:'100.00',lower:100000},{text:'100.01',lower:100010},{text:'100.08',lower:100080},
  {text:'100.09',lower:100090},{text:'100.12',lower:100120},{text:'1048.57',lower:1048570},{text:'1234567.89',lower:1234567890}]) {
  native_files['/proc/uptime']=clock.text+' 0.00';
  check(boottime_ms() === clock.lower, 'Native uptime milliseconds lost precision');
  for (let sample in [{offset:0,current:true},{offset:1,current:true},{offset:9,current:true},
    {offset:10,current:false},{offset:-14990,current:true},{offset:-14991,current:false},{offset:-15000,current:false}]) {
    clock_status.updated_boottime_ms=clock.lower+sample.offset;
    native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
    check(current_status().current === sample.current, 'Native status interval or conservative expiry failed');
  }
}
native_files['/proc/uptime']='100.00 0.00';
clock_status.updated_boottime_ms=100009;
native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
for (let owner in [{key:'pid',value:778},{key:'process_startticks',value:1235},{key:'boot_id',value:'old-boot'}]) {
  let previous=clock_status[owner.key]; clock_status[owner.key]=owner.value;
  native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
  check(!current_status().current, 'Native status interval bypassed process ownership');
  clock_status[owner.key]=previous;
}
native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
let clock_lease={ok:true,pid:777,process_startticks:1234,boot_id:'fixture-boot',human_epoch:7,
  recovery_id:'fixture-recovery',lease_secs:90,updated_boottime_ms:99000};
for (let sample in [{stamp:100000,valid:true},{stamp:100001,valid:true},{stamp:100009,valid:true},
  {stamp:100010,valid:false},{stamp:15011,valid:true},{stamp:15010,valid:false},{stamp:15000,valid:false}]) {
  clock_lease.updated_boottime_ms=sample.stamp;
  native_files['/var/run/csqtt/recovery-lease.json']=sprintf('%J',clock_lease);
  check(health_lease_valid() === sample.valid, 'Native lease interval or strict expiry failed');
}
clock_lease.updated_boottime_ms=100009;
for (let owner in [{key:'pid',value:778},{key:'process_startticks',value:1235},{key:'boot_id',value:'old-boot'},
  {key:'human_epoch',value:8},{key:'lease_secs',value:91},{key:'recovery_id',value:'invalid id'},{key:'ok',value:false}]) {
  let previous=clock_lease[owner.key]; clock_lease[owner.key]=owner.value;
  native_files['/var/run/csqtt/recovery-lease.json']=sprintf('%J',clock_lease);
  check(!health_lease_valid(), 'Native lease interval bypassed ownership or admission');
  clock_lease[owner.key]=previous;
}
native_files['/var/run/csqtt/recovery-lease.json']=sprintf('%J',clock_lease);
for (let invalid in [null,true,false,'100001',[],{},-1,100000.5,9007199254740992]) {
  clock_status.updated_boottime_ms=invalid;
  native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
  check(!current_status().current && !health_lease_valid(), 'Native malformed status time passed freshness');
  clock_status.updated_boottime_ms=100009;
  native_files['/var/run/csqtt/status.json']=sprintf('%J',clock_status);
  clock_lease.updated_boottime_ms=invalid;
  native_files['/var/run/csqtt/recovery-lease.json']=sprintf('%J',clock_lease);
  check(!health_lease_valid(), 'Native malformed lease time passed freshness');
}
clock_lease.updated_boottime_ms=100009;
native_files['/var/run/csqtt/recovery-lease.json']=sprintf('%J',clock_lease);
for (let invalid in ['', '100', '100.0', '100.000', '-100.00', '1e2.00', '100.00x', '9007199254740.00']) {
  native_files['/proc/uptime']=invalid;
  check(!current_status().current && !health_lease_valid(), 'Native malformed uptime passed freshness');
}
native_files['/proc/uptime']='100.00 0.00';
native_services={};
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
print('Native ucode boot-clock freshness interval and conservative expiry passed\\n');
print('Native ucode runtime parser, control validation, redaction and DNS lifecycle passed\\n');
`;
const source = adapters + health + runtime + assertions;
if (process.argv[2]) fs.writeFileSync(process.argv[2], source);
else process.stdout.write(source);
