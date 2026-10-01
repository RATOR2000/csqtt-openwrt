import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const globals = {
  type: v => Array.isArray(v) ? 'array' : typeof v,
  trim: v => String(v).trim(), lc: v => String(v).toLowerCase(),
  split: (v, delimiter) => String(v).split(delimiter),
  join: (delimiter, v) => v.join(delimiter), length: v => v?.length ?? 0,
  substr: (v, start, count) => String(v).substr(start, count),
  match: (v, pattern) => String(v).match(pattern),
  index: (v, needle) => v.indexOf(needle), push: (v, item) => v.push(item),
  ord: v => v.codePointAt(0), die: v => { throw new Error(v); },
};
const source = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/policy.uc'), 'utf8');
export function compiler() {
  const context = vm.createContext({ ...globals });
  vm.runInContext(source.replaceAll('export function', 'function') + '\nthis.api = {validate, compile, hold};', context);
  return context.api;
}
export const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/policy/fixture.json'), 'utf8'));

export function runtime(mode, { packages = {}, files = {}, services = {}, network = { interface: [] }, stage = '/var/run/csqtt/apply.42' } = {}) {
  packages = structuredClone(packages); files = { ...files };
  const output = [], chmods = [];
  const cursor = {
    foreach(pkg, kind, cb) { for (const [id, s] of Object.entries(packages[pkg] || {})) if (s['.type'] === kind) cb({ ...s, '.name': id }); },
    get_all(pkg, id) { return packages[pkg]?.[id]; },
    get(pkg, id, option) { const s = packages[pkg]?.[id]; return option ? s?.[option] : s?.['.type']; },
    set(pkg, id, option, value) { packages[pkg] ||= {}; packages[pkg][id] ||= {}; if (value === undefined) packages[pkg][id]['.type'] = option; else packages[pkg][id][option] = value; },
    delete(pkg, id, option) { if (option) delete packages[pkg]?.[id]?.[option]; else delete packages[pkg]?.[id]; },
    save() { return true; }, commit() { return true; },
  };
  const context = vm.createContext({ ...globals, ...compiler(), ARGV: [mode, stage],
    fs: { readfile: p => files[p] ?? null, readlink: p => files[p] ?? null,
      lsdir: p => { const entries = Object.keys(files).filter(f => f.startsWith(p + '/')).map(f => f.slice(p.length + 1).split('/')[0]); return entries.length || p in files ? [...new Set(entries)] : null; },
      writefile(p, v) { files[p] = v; return v.length; }, chmod: (p, mode) => chmods.push([p, mode]),
      stat: p => p in files || Object.keys(files).some(f => f.startsWith(p + '/')) ? {} : null },
    cursor: () => cursor,
    connect: () => ({ call: (object, method, args) => object === 'network.interface' ? network : { [args.name]: services[args.name] } }),
    json: JSON.parse, sprintf: (_, v) => JSON.stringify(v),
    printf: (_, v) => output.push(JSON.parse(JSON.stringify(v))),
    exit: code => { if (code) throw new Error(`Exit ${code}`); },
  });
  const code = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/runtime.uc'), 'utf8').replace(/^import .*;\r?\n/gm, '');
  vm.runInContext(code, context);
  return { output, files, packages, chmods };
}
