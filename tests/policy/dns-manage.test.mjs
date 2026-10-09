import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { root } from './harness.mjs';

function posixShell() {
  if (process.platform !== 'win32') return '/bin/sh';
  const git = execFileSync('where.exe', ['git'], { encoding: 'utf8' }).trim().split(/\r?\n/)[0];
  return ['../bin/sh.exe', '../usr/bin/sh.exe']
    .map(relative => path.resolve(path.dirname(git), relative)).find(candidate => fs.existsSync(candidate));
}

const shell = posixShell();
assert.ok(shell && fs.existsSync(shell), 'A POSIX shell is required for the DNS manage regressions');
const shellPath = path.dirname(shell).replaceAll('\\', '/').replace(/^([a-zA-Z]):/, (_, drive) => '/' + drive.toLowerCase());
const quote = value => "'" + value.replaceAll("'", "'\\''") + "'";

function runApply(scenario) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'csqtt-dns-manage-')).replaceAll('\\', '/');
  fs.mkdirSync(`${dir}/state`);
  fs.writeFileSync(`${dir}/state/policy.nft`, 'previous policy\n');
  if (scenario !== 'absent-service') fs.writeFileSync(`${dir}/old-process`, '4242\n');
  const stubs = `
PATH=${quote(shellPath)}:"$PATH"
fixture=${quote(dir)}
scenario=${quote(scenario)}
event() { printf '%s\\n' "$*" >> "$fixture/events"; }
chmod() { :; }
logger() { :; }
uci() { printf '0\\n'; }
dnsmasq() { case "$1" in --version) printf 'nftset\\n' ;; esac; }
ip() { case "$1 $2" in 'link show') return 1 ;; esac; }
fw4() { event firewall-reload; }
conntrack() { :; }
cp() {
  case "$2" in "$STATE/policy.nft.new") event policy-copy ;; esac
  command cp "$@"
}
nft() {
  case "$1" in
    list) return 1 ;;
    -c) event policy-validated ;;
    -f)
      case "$2" in
        "$STATE/hold.nft") event guard-installed ;;
        "$STATE/policy.nft") event policy-installed ;;
        */release.nft) event guard-released ;;
      esac ;;
  esac
}
dns_service() {
  case "$1" in
    stop)
      event stop-requested
      : > "$fixture/stop-requested"
      [ "$scenario" != absent-service ] || return 1 ;;
    start)
      event dns-start
      [ ! -f "$fixture/old-process" ] || return 1
      printf '4243\\n' > "$fixture/new-process"
      if [ "$scenario" != missing-ports ]; then : > "$fixture/listening-ports"; fi ;;
    *) return 99 ;;
  esac
}
sleep() {
  if [ -f "$fixture/stop-requested" ] && [ -f "$fixture/old-process" ] && [ "$scenario" != stuck ]; then
    ticks=$(cat "$fixture/ticks" 2>/dev/null || printf 0)
    ticks=$((ticks + 1))
    printf '%s\\n' "$ticks" > "$fixture/ticks"
    if [ "$ticks" -eq 2 ]; then rm "$fixture/old-process"; event old-process-exited; fi
  fi
}
ucode() {
  case "$2" in
    compile)
      printf 1 > "$3/active"
      printf 'closed guard\\n' > "$3/hold.nft"
      printf 'released guard\\n' > "$3/release.nft"
      printf 'new policy\\n' > "$3/policy.nft"
      printf '{}\\n' > "$3/policy.json"
      printf 'forward policy\\n' > "$3/forward.nft"
      printf 'input policy\\n' > "$3/input.nft"
      printf 'port=5400\\n' > "$3/dns-private.conf"
      printf 'private\\n' > "$3/dns.ids"
      printf '{}\\n' > "$3/client.json"
      : > "$3/flush.ips" ;;
    firewall-hold|firewall-on|firewall-off) event "$2" ;;
    dns-snapshot)
      event dns-snapshot
      if [ -f "$fixture/old-process" ]; then
        cp "$fixture/old-process" "$fixture/captured-process"
      else
        : > "$fixture/captured-process"
      fi ;;
    dns-stopped)
      event dns-stop-check
      [ -f "$fixture/captured-process" ] || return 99
      [ ! -f "$fixture/old-process" ] || return 1
      event dns-stop-confirmed ;;
    dns-ready)
      event dns-ready-check
      [ -f "$fixture/new-process" ] && [ -f "$fixture/listening-ports" ] ;;
    *) return 99 ;;
  esac
}
`;
  const manage = fs.readFileSync(path.join(root, 'openwrt/csqtt/files/manage'), 'utf8')
    .replace('umask 077', 'umask 077\n' + stubs)
    .replace('RUN=/var/run/csqtt', `RUN=${quote(`${dir}/run`)}`)
    .replace('STATE=/etc/csqtt', `STATE=${quote(`${dir}/state`)}`)
    .replaceAll('/var/lock', quote(`${dir}/lock`))
    .replaceAll('/etc/init.d/csqtt-dns', 'dns_service');
  try {
    const script = `${dir}/manage`;
    fs.writeFileSync(script, manage);
    const result = spawnSync(shell, [script, 'apply'], { encoding: 'utf8', timeout: 15_000 });
    assert.equal(result.error, undefined, result.error?.message);
    return {
      ...result,
      events: fs.readFileSync(`${dir}/events`, 'utf8').trim().split('\n'),
      policy: fs.readFileSync(`${dir}/state/policy.nft`, 'utf8'),
      hold: fs.readFileSync(`${dir}/state/hold.nft`, 'utf8'),
      oldAlive: fs.existsSync(`${dir}/old-process`),
      newAlive: fs.existsSync(`${dir}/new-process`),
      portsListening: fs.existsSync(`${dir}/listening-ports`),
      error: fs.existsSync(`${dir}/run/policy.error`) ? fs.readFileSync(`${dir}/run/policy.error`, 'utf8') : '',
    };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function before(events, first, second) {
  assert.ok(events.includes(first), `Missing event: ${first}`);
  assert.ok(events.includes(second), `Missing event: ${second}`);
  assert.ok(events.indexOf(first) < events.indexOf(second), `${first} must precede ${second}: ${events.join(', ')}`);
}

test('manage waits for captured old DNS processes before replacing policy or starting DNS', () => {
  const result = runApply('delayed');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.ok(result.events.filter(event => event === 'dns-stop-check').length >= 3, result.events.join(', '));
  before(result.events, 'guard-installed', 'dns-snapshot');
  before(result.events, 'dns-snapshot', 'stop-requested');
  before(result.events, 'stop-requested', 'old-process-exited');
  before(result.events, 'old-process-exited', 'dns-stop-confirmed');
  before(result.events, 'dns-stop-confirmed', 'policy-copy');
  before(result.events, 'policy-installed', 'dns-start');
  before(result.events, 'dns-ready-check', 'guard-released');
  assert.equal(result.policy, 'new policy\n');
  assert.equal(result.hold, 'released guard\n');
  assert.equal(result.oldAlive, false);
  assert.equal(result.newAlive, true);
});

test('manage retains the guard and previous policy when an old DNS process never exits', () => {
  const result = runApply('stuck');
  assert.equal(result.status, 1, result.stdout + result.stderr);
  before(result.events, 'dns-snapshot', 'stop-requested');
  assert.ok(result.events.includes('dns-stop-check'), result.events.join(', '));
  for (const event of ['policy-copy', 'policy-installed', 'dns-start', 'guard-released'])
    assert.equal(result.events.includes(event), false, `Unexpected event: ${event}`);
  assert.equal(result.policy, 'previous policy\n');
  assert.equal(result.hold, 'closed guard\n');
  assert.equal(result.oldAlive, true);
  assert.equal(result.newAlive, false);
  assert.match(result.error, /DNS.*(?:stop|exit)|(?:stop|exit).*DNS/i);
});

test('manage keeps clients guarded when the replacement DNS process has no listening ports', () => {
  const result = runApply('missing-ports');
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.equal(result.oldAlive, false);
  assert.equal(result.newAlive, true);
  assert.equal(result.portsListening, false);
  before(result.events, 'dns-stop-confirmed', 'dns-start');
  assert.ok(result.events.includes('dns-ready-check'), result.events.join(', '));
  assert.equal(result.events.includes('guard-released'), false);
  assert.equal(result.hold, 'closed guard\n');
  assert.match(result.error, /Group DNS failed to start/);
});

test('manage activates DNS when stopping an absent service fails but no old processes exist', () => {
  const result = runApply('absent-service');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  before(result.events, 'guard-installed', 'dns-snapshot');
  before(result.events, 'dns-snapshot', 'stop-requested');
  before(result.events, 'stop-requested', 'dns-stop-confirmed');
  before(result.events, 'dns-stop-confirmed', 'policy-copy');
  before(result.events, 'policy-installed', 'dns-start');
  before(result.events, 'dns-ready-check', 'guard-released');
  assert.equal(result.events.includes('old-process-exited'), false);
  assert.equal(result.policy, 'new policy\n');
  assert.equal(result.hold, 'released guard\n');
  assert.equal(result.oldAlive, false);
  assert.equal(result.newAlive, true);
  assert.equal(result.portsListening, true);
  assert.equal(result.error, '');
});
