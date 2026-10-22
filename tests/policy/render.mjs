// Emit the actual production compiler output for Linux nft/dnsmasq integration.
import fs from 'node:fs';
import path from 'node:path';
import { compiler, fixture } from './harness.mjs';
const out = process.argv[2];
if (!out) throw new Error('Usage: node tests/policy/render.mjs OUTPUT_DIRECTORY');
fs.mkdirSync(out, { recursive: true });
const { compile, hold } = compiler();
const result = compile(fixture);
fs.writeFileSync(path.join(out, 'policy.nft'), result.nft);
fs.writeFileSync(path.join(out, 'hold.nft'), hold([result.model], true));
fs.writeFileSync(path.join(out, 'release.nft'), hold([], false));
fs.writeFileSync(path.join(out, 'model.json'), JSON.stringify(result.model));
for (const dns of result.dns) fs.writeFileSync(path.join(out, `dns-${dns.id}.conf`), dns.config);
