import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const git = process.platform === 'win32' ? execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0] : '';
const shell = process.platform === 'win32' ? ['../bin/sh.exe', '../usr/bin/sh.exe']
  .map(p => path.resolve(path.dirname(git), p)).find(p => fs.existsSync(p)) : '/bin/sh';

function reload({ enabled = '1', running = true, previous = '{"workers":9}', next = previous, applyFails = false, stopFails = false } = {}) {
  assert.ok(shell && fs.existsSync(shell), 'A POSIX shell is required for service reload behavior tests');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'csqtt-reload-')).replaceAll('\\', '/');
  const shellBin = path.dirname(shell).replaceAll('\\', '/').replace(/^([a-zA-Z]):/, (_, drive) => '/' + drive.toLowerCase());
  try {
    fs.mkdirSync(`${dir}/run`);
    fs.writeFileSync(`${dir}/next.json`, next);
    fs.writeFileSync(`${dir}/deactivated`, '');
    if (previous != null) fs.writeFileSync(`${dir}/run/client.json`, previous);
    const source = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/csqtt.init'), 'utf8')
      .replaceAll('/usr/libexec/csqtt/manage', 'manage')
      .replaceAll('/var/run/csqtt', `${dir}/run`);
    fs.writeFileSync(`${dir}/init`, source);
    const driver = `
PATH='${shellBin}':"$PATH"
cd '${dir}' || exit 99
client_pid=
initial_pid=
trap '[ -z "$client_pid" ] || { kill "$client_pid" 2>/dev/null; wait "$client_pid" 2>/dev/null; }; :' EXIT
record() { printf '%s\\n' "$1" >> events; }
uci() { printf '%s\\n' '${enabled}'; }
manage() {
  record "$1"
  [ "$1" = apply ] || return 98
  # The old config snapshot must be private before any apply writes occur.
  for file in run/reload-client.*; do
    [ -f "$file" ] || continue
    if command -v stat >/dev/null 2>&1; then stat -c '%a' "$file" > snapshot-mode; fi
    cmp -s "$file" run/client.json || return 97
  done
  : > guard
  [ '${applyFails ? '1' : '0'}' = 0 ] || return 1
  cp next.json run/client.json || return 96
  rm -f deactivated
}
procd_running() { record running-check; [ -n "$client_pid" ] && kill -0 "$client_pid" 2>/dev/null; }
stop() {
  record stop
  [ '${stopFails ? '1' : '0'}' = 0 ] || return 1
  if [ -n "$client_pid" ]; then kill "$client_pid"; wait "$client_pid" 2>/dev/null; fi
  client_pid=
  rm -f current-pid
}
rc_procd() { record register; "$@"; }
procd_open_instance() { :; }
procd_set_param() { :; }
procd_close_instance() { record start; tail -f /dev/null >/dev/null 2>&1 & client_pid=$!; printf '%s\\n' "$client_pid" > current-pid; }
. ./init
if [ '${running ? '1' : '0'}' = 1 ]; then tail -f /dev/null >/dev/null 2>&1 & client_pid=$!; fi
initial_pid=$client_pid
[ -z "$client_pid" ] || printf '%s\\n' "$client_pid" > current-pid
# Model the rc.common wrapper: reload_service runs inside its own subshell.
# Record lifecycle mutations there so the outer cleanup can kill the new PID.
reload_service
result=$?
# The subshell cannot update the outer variable; get the current test process
# from the PID written by the registration stub instead.
client_pid=$(cat current-pid 2>/dev/null || true)
printf '%s\\n' "$result" > result
printf '%s\\n' "$initial_pid" > initial-pid
`;
    fs.writeFileSync(`${dir}/driver`, driver);
    const out = spawnSync(shell, [`${dir}/driver`], { encoding: 'utf8', timeout: 10000 });
    assert.equal(out.status, 0, out.error?.message || out.stdout + out.stderr);
    assert.ok(fs.existsSync(`${dir}/events`), out.stdout + out.stderr);
    return {
      result: Number(fs.readFileSync(`${dir}/result`, 'utf8').trim()),
      before: fs.readFileSync(`${dir}/initial-pid`, 'utf8').trim(),
      after: fs.existsSync(`${dir}/current-pid`) ? fs.readFileSync(`${dir}/current-pid`, 'utf8').trim() : '',
      events: fs.readFileSync(`${dir}/events`, 'utf8').trim().split('\n'),
      snapshotMode: fs.existsSync(`${dir}/snapshot-mode`) ? fs.readFileSync(`${dir}/snapshot-mode`, 'utf8').trim() : null,
      snapshots: fs.readdirSync(`${dir}/run`).filter(f => f.startsWith('reload-client.')),
      guard: fs.existsSync(`${dir}/guard`),
      deactivated: fs.existsSync(`${dir}/deactivated`),
    };
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}

test('unchanged transport keeps the same running process after one policy apply', () => {
  const out = reload();
  assert.equal(out.result, 0);
  assert.equal(out.after, out.before, JSON.stringify(out.events));
  assert.notEqual(out.before, '');
  assert.deepEqual(out.events, ['apply', 'running-check']);
  if (process.platform !== 'win32') assert.equal(out.snapshotMode, '600');
  assert.deepEqual(out.snapshots, []);
  assert.equal(out.deactivated, false);
});

test('changed effective transport config restarts after apply without repeating prepare', () => {
  const out = reload({ next: '{"workers":18}' });
  assert.equal(out.result, 0);
  assert.notEqual(out.after, out.before);
  assert.notEqual(out.after, '');
  assert.deepEqual(out.events, ['apply', 'stop', 'register', 'start']);
  assert.deepEqual(out.snapshots, []);
});

test('failed policy apply retains transport and guards and cleans private snapshot', () => {
  const out = reload({ next: '{"workers":18}', applyFails: true });
  assert.equal(out.result, 1);
  assert.equal(out.after, out.before);
  assert.deepEqual(out.events, ['apply']);
  assert.equal(out.guard, true);
  assert.equal(out.deactivated, true);
  assert.deepEqual(out.snapshots, []);
});

test('disabled transport stops after successful policy apply while retaining policy guards', () => {
  const out = reload({ enabled: '0' });
  assert.equal(out.result, 0);
  assert.equal(out.after, '');
  assert.deepEqual(out.events, ['apply', 'stop']);
  assert.equal(out.guard, true);
  assert.deepEqual(out.snapshots, []);
});

test('missing or stopped transport starts from the already applied config', () => {
  for (const previous of [null, '{"workers":9}']) {
    const out = reload({ running: false, previous, next: '{"workers":9}' });
    assert.equal(out.result, 0);
    assert.notEqual(out.after, '');
    assert.deepEqual(out.events, ['apply', ...(previous == null ? [] : ['running-check']), 'stop', 'register', 'start']);
    assert.deepEqual(out.snapshots, []);
  }
});

test('stop failure does not register a competing transport process', () => {
  const out = reload({ next: '{"workers":18}', stopFails: true });
  assert.equal(out.result, 1);
  assert.equal(out.after, out.before);
  assert.deepEqual(out.events, ['apply', 'stop']);
  assert.deepEqual(out.snapshots, []);
});
