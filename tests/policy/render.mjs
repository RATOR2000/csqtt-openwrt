// Emit the actual production compiler output for Linux nft/dnsmasq integration.
import fs from 'node:fs';
import path from 'node:path';
import { compiler, fixture } from './harness.mjs';
const out = process.argv[2];
if (!out) throw new Error('Usage: node tests/policy/render.mjs OUTPUT_DIRECTORY');
fs.mkdirSync(out, { recursive: true });
const { compile, hold, compile_legacy, hold_legacy, legacy_guard } = compiler();
const result = compile(fixture);
fs.writeFileSync(path.join(out, 'policy.nft'), result.nft);
fs.writeFileSync(path.join(out, 'hold.nft'), hold([result.model], true));
fs.writeFileSync(path.join(out, 'release.nft'), hold([], false));
fs.writeFileSync(path.join(out, 'model.json'), JSON.stringify(result.model));
for (const dns of result.dns) fs.writeFileSync(path.join(out, `dns-${dns.id}.conf`), dns.config);
const legacy = compile_legacy(fixture);
for (const [name, content] of Object.entries({
  'legacy-policy.v4': legacy.ipv4, 'legacy-policy.v6': legacy.ipv6, 'legacy-policy.ipset': legacy.ipset,
  'legacy-hold.v4': hold_legacy([legacy.model], true, false), 'legacy-hold.v6': hold_legacy([legacy.model], true, true),
  'legacy-release.v4': hold_legacy([], false, false), 'legacy-release.v6': hold_legacy([], false, true),
  'legacy-hold.guard.nft': legacy_guard([legacy.model], true), 'legacy-release.guard.nft': legacy_guard([legacy.model], false),
})) fs.writeFileSync(path.join(out, name), content);
for (const dns of legacy.dns) fs.writeFileSync(path.join(out, `legacy-dns-${dns.id}.conf`), dns.config);
