// Exercise the complete runtime source with real ucode and isolated in-memory adapters.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/runtime.uc'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '');
const adapters = `
let native_files = {};
let fs = {
  readfile: function(p) { return native_files[p]; },
  stat: function(p) { return native_files[p] != null ? {} : null; },
  writefile: function() { die('Native runtime test attempted a file write'); },
  chmod: function() { die('Native runtime test attempted a permission change'); }
};
function cursor() {
  return { get: function(p, s, option) { return option === 'enabled' ? '0' : null; }, foreach: function() {} };
}
function connect() { return { call: function() { return {}; } }; }
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
print('Native ucode runtime parser, control validation and redaction passed\\n');
`;
const source = adapters + runtime + assertions;
if (process.argv[2]) fs.writeFileSync(process.argv[2], source);
else process.stdout.write(source);
