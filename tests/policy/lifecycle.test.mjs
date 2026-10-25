import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawn } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const git = process.platform === 'win32' ? execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0] : '';
const shell = process.platform === 'win32' ? ['../bin/sh.exe', '../usr/bin/sh.exe']
  .map(p => path.resolve(path.dirname(git), p)).find(p => fs.existsSync(p)) : '/bin/sh';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

function fixture() {
  assert.ok(shell && fs.existsSync(shell), 'A POSIX shell is required');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'csqtt-lifecycle-')).replaceAll('\\', '/');
  const children = [];
  const relocate = source => source.replaceAll('/var/run/csqtt', `${dir}/run`)
    .replaceAll('/var/lock', `${dir}/locks`).replaceAll('/etc/config', `${dir}/config`)
    .replaceAll('/etc/csqtt', `${dir}/state`).replaceAll('/proc/uptime', `${dir}/uptime`)
    .replaceAll('/tmp/.uci', `${dir}/uci`);
  for (const name of ['run', 'locks', 'config', 'state', 'uci']) fs.mkdirSync(`${dir}/${name}`);
  fs.writeFileSync(`${dir}/run/client.json`, '{}');
  fs.writeFileSync(`${dir}/run/intent`, 'initial\n');
  fs.writeFileSync(`${dir}/config/csqtt`, 'enabled=1\n');
  fs.writeFileSync(`${dir}/config/network`, 'stable\n');
  fs.writeFileSync(`${dir}/enabled`, '1\n');
  fs.writeFileSync(`${dir}/uptime`, '100.00 0.00\n');
  fs.writeFileSync(`${dir}/sha.mjs`, `import fs from 'node:fs'; import { createHash } from 'node:crypto';
const args=process.argv.slice(2); for(const name of args.length ? args : ['-']) {
  const bytes=fs.readFileSync(name==='-' ? 0 : name);
  process.stdout.write(createHash('sha256').update(bytes).digest('hex')+'  '+name+'\\n');
}`);
  fs.writeFileSync(`${dir}/lifecycle`, relocate(fs.readFileSync(path.join(root, 'openwrt/csqtt/files/lifecycle.sh'), 'utf8')));
  fs.writeFileSync(`${dir}/init`, relocate(fs.readFileSync(path.join(root, 'openwrt/csqtt/files/csqtt.init'), 'utf8'))
    .replace('. /usr/libexec/csqtt/lifecycle.sh', '')
    .replaceAll('/usr/libexec/csqtt/manage', 'manage')
    .replaceAll('/usr/libexec/csqtt/tun-hook', 'tun_hook'));
  const shellBin = path.dirname(shell).replaceAll('\\', '/').replace(/^([a-zA-Z]):/, (_, drive) => '/' + drive.toLowerCase());
  // Model rc.common's source order and blocking procd service lock. The real
  // lifecycle mkdir/PID/startticks/intent/reaper/traps execute in separate OS
  // processes. mkdir models the flock on platforms without a flock executable.
  fs.writeFileSync(`${dir}/common`, `
PATH='${shellBin}':'${shellBin}/../usr/bin':"$PATH"
cd '${dir}' || exit 99
record() { printf '%s\\n' "$1" >> events; }
if ! command -v sha256sum >/dev/null 2>&1; then
  sha256sum() { '${process.execPath.replaceAll('\\', '/')}' '${dir}/sha.mjs' "$@"; }
fi
if ! command -v sleep >/dev/null 2>&1; then
  sleep() { '${process.execPath.replaceAll('\\', '/')}' -e 'Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, Number(process.argv[1])*1000)' "$1"; }
fi
. ./lifecycle
# MSYS /proc does not publish Linux stat records. Use real process liveness for
# the fixture's stable startticks value; all locking logic remains unchanged.
csqtt_startticks() { kill -0 "$1" 2>/dev/null && printf '1\\n'; }
uci() { cat enabled; }
ucode() { [ ! -f runtime-invalid ]; }
tun_hook() { :; }
manage() {
  record "manage:$1"
  case "$1" in
    transport-stopped)
      : > waiting-stop
      while [ ! -f allow-stopped ]; do sleep 0.02; done ;;
    apply|prepare) : ;;
  esac
}
procd_running() { return 1; }
procd_open_instance() { :; }
procd_set_param() { :; }
procd_close_instance() { :; }
procd_add_reload_trigger() { :; }
rc_procd() { "$@" || return $?; record registered; : > registered; }
stop() { stop_service || return $?; record killed; : > killed; }
acquire_procd() {
  while ! mkdir procd-lock 2>/dev/null; do sleep 0.02; done
  record "procd:$action"
  csqtt_extra_cleanup() { rmdir procd-lock 2>/dev/null || true; }
  trap csqtt_operation_cleanup EXIT
}
`);
  fs.writeFileSync(`${dir}/rc`, `
. '${dir}/common'
action=$1
. ./init || exit $?
# rc.common sources procd.sh only after sourcing the service init file.
acquire_procd
case "$action" in
  stop) stop ;;
  reload) reload_service ;;
  prepared_start) prepared_start ;;
  prepared_restart) prepared_restart ;;
  status|running) record readonly ;;
  *) exit 98 ;;
esac
`);
  function run(script, args = []) {
    const child = spawn(shell, [script, ...args], { cwd: dir, env: { ...process.env }, stdio: ['ignore', 'pipe', 'pipe'] });
    children.push(child);
    let output = '';
    child.stdout.on('data', data => { output += data; });
    child.stderr.on('data', data => { output += data; });
    const result = new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => {
        fs.writeFileSync(`${dir}/process-${child.pid}.result`, `${code}: ${output}`);
        resolve({ code, output });
      });
    });
    return { child, result };
  }
  async function until(predicate, message) {
    const deadline = Date.now() + 6000;
    while (!predicate()) {
      if (Date.now() >= deadline) assert.fail(`${message}; events=${events()}; output=${fs.readdirSync(dir).filter(n => n.endsWith('.result')).map(n => fs.readFileSync(`${dir}/${n}`, 'utf8'))}`);
      await pause(20);
    }
  }
  const events = () => fs.existsSync(`${dir}/events`) ? fs.readFileSync(`${dir}/events`, 'utf8').trim().split('\n') : [];
  async function finish(proc) {
    const timeout = setTimeout(() => proc.child.kill(), 6000);
    try { return await proc.result; } finally { clearTimeout(timeout); }
  }
  async function cleanup() {
    // Let waiters finish normally, preserving their EXIT cleanup traps.
    for (const name of ['allow-stopped', 'allow-holder']) fs.writeFileSync(`${dir}/${name}`, '');
    for (const child of children) if (child.exitCode == null) child.kill();
    await Promise.allSettled(children.map(child => child.exitCode != null ? Promise.resolve() : new Promise(resolve => child.once('exit', resolve))));
    fs.rmSync(dir, { recursive: true, force: true });
  }
  return { dir, run, until, events, finish, cleanup };
}

test('direct reload waits for lifecycle before taking procd while an inherited operation starts', async () => {
  const f = fixture();
  try {
    fs.writeFileSync(`${f.dir}/holder`, `
. '${f.dir}/common'
csqtt_operation_enter recovery || exit 1
: > holder-ready
while [ ! -f allow-holder ]; do sleep 0.02; done
'${shell}' '${f.dir}/rc' prepared_start || exit $?
`);
    const holder = f.run(`${f.dir}/holder`);
    await f.until(() => fs.existsSync(`${f.dir}/holder-ready`), 'holder did not acquire lifecycle');
    const reload = f.run(`${f.dir}/rc`, ['reload']);
    await f.until(() => fs.readFileSync(`${f.dir}/run/intent`, 'utf8').trim() !== 'initial', 'reload did not publish intent');
    assert.equal(fs.existsSync(`${f.dir}/procd-lock`), false, 'queued reload took procd before lifecycle');
    fs.writeFileSync(`${f.dir}/allow-holder`, '');
    assert.equal((await f.finish(holder)).code, 0);
    assert.equal((await f.finish(reload)).code, 0);
    assert.ok(f.events().indexOf('procd:prepared_start') < f.events().indexOf('procd:reload'), JSON.stringify(f.events()));
    assert.equal(fs.existsSync(`${f.dir}/locks/csqtt-operation`), false);
  } finally { await f.cleanup(); }
});

test('a queued direct Stop between kill and register revokes prepared recovery', async () => {
  const f = fixture();
  try {
    fs.writeFileSync(`${f.dir}/recover`, `
. '${f.dir}/common'
csqtt_operation_enter recovery || exit 1
CSQTT_RECOVERY_ACTIVE=1
CSQTT_RECOVERY_DEADLINE_BOOTTIME_MS=185000
CSQTT_RECOVERY_CONFIG_EPOCH=$(sha256sum '${f.dir}/config/csqtt' '${f.dir}/config/network' | sha256sum | cut -d ' ' -f 1)
export CSQTT_RECOVERY_ACTIVE CSQTT_RECOVERY_DEADLINE_BOOTTIME_MS CSQTT_RECOVERY_CONFIG_EPOCH
'${shell}' '${f.dir}/rc' prepared_restart
`);
    const recovering = f.run(`${f.dir}/recover`);
    await f.until(() => fs.existsSync(`${f.dir}/waiting-stop`), 'recovery did not stop old process');
    const stopping = f.run(`${f.dir}/rc`, ['stop']);
    await f.until(() => fs.readFileSync(`${f.dir}/run/intent`, 'utf8').trim() !== 'initial', 'Stop did not revoke recovery before waiting');
    fs.writeFileSync(`${f.dir}/allow-stopped`, '');
    assert.equal((await f.finish(recovering)).code, 1);
    assert.equal((await f.finish(stopping)).code, 0);
    assert.equal(fs.existsSync(`${f.dir}/registered`), false, JSON.stringify(f.events()));
  } finally { await f.cleanup(); }
});

for (const change of ['unchanged', 'expired', 'configuration', 'maintenance', 'disabled',
  'pending-csqtt', 'pending-network', 'pending-dhcp', 'pending-firewall']) {
  test(`prepared recovery ${change === 'unchanged' ? 'registers with an unchanged admission snapshot' : `does not register after ${change} changes`} during asynchronous stop`, async () => {
    const f = fixture();
    try {
      fs.writeFileSync(`${f.dir}/recover`, `
. '${f.dir}/common'
csqtt_operation_enter recovery || exit 1
CSQTT_RECOVERY_ACTIVE=1
CSQTT_RECOVERY_DEADLINE_BOOTTIME_MS=185000
CSQTT_RECOVERY_CONFIG_EPOCH=$(sha256sum '${f.dir}/config/csqtt' '${f.dir}/config/network' | sha256sum | cut -d ' ' -f 1)
export CSQTT_RECOVERY_ACTIVE CSQTT_RECOVERY_DEADLINE_BOOTTIME_MS CSQTT_RECOVERY_CONFIG_EPOCH
'${shell}' '${f.dir}/rc' prepared_restart
`);
      const recovering = f.run(`${f.dir}/recover`);
      await f.until(() => fs.existsSync(`${f.dir}/waiting-stop`), 'recovery did not reach asynchronous stop');
      if (change === 'expired') fs.writeFileSync(`${f.dir}/uptime`, '185.01 0.00\n');
      if (change === 'configuration') fs.appendFileSync(`${f.dir}/config/network`, 'changed\n');
      if (change === 'maintenance') fs.mkdirSync(`${f.dir}/locks/csqtt-maintenance`);
      if (change === 'disabled') fs.writeFileSync(`${f.dir}/enabled`, '0\n');
      if (change.startsWith('pending-')) fs.writeFileSync(`${f.dir}/uci/${change.slice(8)}`, 'pending edit\n');
      fs.writeFileSync(`${f.dir}/allow-stopped`, '');
      const expected = change === 'unchanged';
      const result = await f.finish(recovering);
      assert.equal(result.code, expected ? 0 : 1, result.output + JSON.stringify(f.events()));
      assert.equal(fs.existsSync(`${f.dir}/registered`), expected, JSON.stringify(f.events()));
    } finally { await f.cleanup(); }
  });
}

test('read-only init status and running do not publish intent or acquire lifecycle', async () => {
  const f = fixture();
  try {
    for (const action of ['status', 'running']) assert.equal((await f.finish(f.run(`${f.dir}/rc`, [action]))).code, 0);
    assert.equal(fs.readFileSync(`${f.dir}/run/intent`, 'utf8'), 'initial\n');
    assert.equal(fs.existsSync(`${f.dir}/locks/csqtt-operation`), false);
  } finally { await f.cleanup(); }
});
