import test from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { health, runtime } from './harness.mjs';

const api = health();
const base = { boot_id: 'boot-one', config_epoch: 'a'.repeat(64), network_epoch: 'path-one',
  process_epoch: '901:1234:0', intent: 'intent-one', automatic: true, process: 'ok', now: 0, gate: null };
const copy = x => JSON.parse(JSON.stringify(x));
const endpoint = (index, https = 'ok', dns = 'ok') => ({ index, state: https, dns, https, reachable: ['ok', 'endpoint_error'].includes(https) });
const probe = (...endpoints) => ({ schema_version: 1, config_valid: true, completed: true, endpoints });
const good = () => probe(endpoint(0), endpoint(1));
const failed = () => probe(endpoint(0, 'fail'), endpoint(1, 'fail'));
function advance(state, now, options = {}, wan = good(), vpn = failed()) {
  return api.health_advance(copy(state), { ...base, now, ...options }, wan, vpn);
}
function until(now, options = {}) {
  let state = null;
  for (let at = 0; at <= now; at += 30) state = advance(state, at, options);
  return state;
}
function reserve(state, now, action, options = {}) {
  return api.health_reserve(copy(state), { ...base, now, wan: good(), vpn: failed(), ...options }, action);
}

test('only 180 seconds of continuous confirmed endpoint transport failure proposes a soft repair', () => {
  assert.equal(until(150).action, undefined);
  const state = until(180);
  assert.equal(state.action, 'soft'); assert.equal(state.failure_since, 0);
  assert.equal(state.attempts.length, 0);
  const reserved = reserve(state, 180, 'soft');
  assert.equal(reserved.stage, 'soft_running'); assert.deepEqual(copy(reserved.attempts), [180]);
});

test('soft repair waits another complete 30 seconds and requires a new confirmed sample before transport restart', () => {
  let state = reserve(until(180), 180, 'soft');
  state = api.health_complete(state, { ...base, now: 200 }, 'soft', true);
  state = advance(state, 210);
  assert.equal(state.action, undefined);
  state = advance(state, 240);
  assert.equal(state.action, 'transport');
  const running = reserve(state, 240, 'transport');
  assert.equal(running.stage, 'transport_running'); assert.equal(running.attempts.length, 1);
  assert.equal(advance(state, 240, {}, good(), good()).action, undefined);
});

test('DNS ambiguity, a failed endpoint control, HTTP service errors and any VPN success reset escalation', () => {
  const pending = until(150);
  const scenarios = [
    [good(), probe(endpoint(0, 'not_attempted', 'fail'), endpoint(1, 'not_attempted', 'fail'))],
    [good(), probe(endpoint(0, 'unknown', 'unknown'), endpoint(1, 'fail'))],
    [probe(endpoint(0), endpoint(1, 'fail')), failed()],
    [good(), probe(endpoint(0, 'endpoint_error'), endpoint(1, 'fail'))],
    [good(), probe(endpoint(0), endpoint(1, 'fail'))],
    [null, failed()], [good(), { ...failed(), completed: false }],
  ];
  for (const [wan, vpn] of scenarios) {
    const state = advance(pending, 180, {}, wan, vpn);
    assert.equal(state.action, undefined, JSON.stringify([wan, vpn]));
    assert.equal(state.failure_since, null);
  }
  assert.equal(api.health_assess(probe(endpoint(0), endpoint(1, 'fail')), failed()).wan, 'ok');
  assert.equal(api.health_assess(probe(endpoint(0, 'endpoint_error'), endpoint(1, 'endpoint_error')), failed()).confirmed, true);
});

test('no traffic counters are needed for healthy idle service and observe mode never schedules actions', () => {
  const healthy = advance(until(150), 180, {}, good(), good());
  assert.equal(healthy.state, 'healthy'); assert.equal(healthy.failure_since, null);
  const observed = until(360, { automatic: false });
  assert.equal(observed.action, undefined); assert.equal(observed.reason, 'observe_only');
  assert.equal(api.health_public(observed, { ...base, now: 360, automatic: false }).recovery.state, 'observing');
});

test('Stop, pending edits, maintenance, policy faults and human takeover discard the old failure window', () => {
  for (const gate of ['disabled', 'pending_edits', 'maintenance', 'policy_error', 'guard_missing', 'human_active', 'status_stale', 'operation_active']) {
    const paused = advance(until(150), 180, { gate });
    assert.equal(paused.action, undefined); assert.equal(paused.failure_since, null);
    assert.equal(advance(paused, 210).action, undefined);
    assert.equal(reserve(until(180), 180, 'soft', { gate }), null);
  }
});

test('group DNS failure is visible independently of a reachable tunnel and does not force a transport restart', () => {
  const vpn = { ...good(), group_dns: 'fail' };
  const state = advance(null, 0, {}, good(), vpn);
  assert.equal(state.vpn, 'ok'); assert.equal(state.dns, 'fail');
  assert.equal(state.state, 'degraded'); assert.equal(state.reason, 'group_dns_failed');
  assert.equal(state.action, undefined);
});

test('config, WAN route/source, intent, process and completed human session changes cancel queued actions', () => {
  for (const change of [{ config_epoch: 'b'.repeat(64) }, { network_epoch: 'path-two' },
    { intent: 'intent-stop' }, { process_epoch: '902:5678:0' }, { process_epoch: '901:1234:1' }]) {
    assert.equal(advance(until(150), 180, change).failure_since, null);
    assert.equal(reserve(until(180), 180, 'soft', change), null);
  }
  assert.equal(reserve(until(180), 196, 'soft'), null, 'old decisions expire after15seconds');
});

test('long gaps or a new boot cannot convert old elapsed time to an immediate restart', () => {
  assert.equal(advance(until(150), 300).failure_since, null);
  const newBoot = advance(until(180), 0, { boot_id: 'boot-two' });
  assert.equal(newBoot.action, undefined); assert.equal(newBoot.attempts.length, 0);
});

test('failed actions reserve cycles, enforce300seconds and three per rolling hour across observer restarts', () => {
  let state = reserve(until(180), 180, 'soft');
  state = api.health_complete(state, { ...base, now: 180 }, 'soft', false);
  for (let at = 210; at <= 450; at += 30) state = advance(state, at);
  assert.equal(state.action, undefined); assert.equal(state.reason, 'cooldown');
  state = advance(state, 480);
  assert.equal(state.action, 'soft'); state = reserve(state, 480, 'soft');
  state = api.health_complete(state, { ...base, now: 480 }, 'soft', false);
  for (let at = 510; at <= 780; at += 30) state = advance(state, at);
  state = reserve(state, 780, 'soft');
  state = api.health_complete(state, { ...base, now: 780 }, 'soft', false);
  // Restarting the observer changes neither saved attempts nor their clock.
  state = copy(state);
  for (let at = 810; at <= 1080; at += 30) state = advance(state, at);
  assert.equal(state.reason, 'hourly_limit'); assert.equal(state.action, undefined);
  assert.deepEqual(copy(state.attempts), [180, 480, 780]);
  assert.equal(advance(state, 3780).attempts.length, 2);
});

test('public health and recovery expose only bounded enumerations and counts', () => {
  const secret = randomBytes(32).toString('hex');
  const state = { ...until(180), state: secret, reason: secret, wan: secret, vpn: secret, dns: secret,
    recovery_id: secret, boot_id: base.boot_id, attempts: [1, 2, 3], next_action: 1e30 };
  const view = api.health_public(state, { ...base, now: 180 });
  assert.equal(JSON.stringify(view).includes(secret), false);
  assert.equal(view.health.state, 'unknown'); assert.equal(view.recovery.attempts, 3);
  assert.equal(view.recovery.next_attempt_in_secs, 0);
});

test('public status immediately invalidates a prior healthy sample on Stop, takeover or changed epochs', () => {
  const sample = { ...until(180), state: 'healthy', reason: 'vpn_reachable', wan: 'ok', vpn: 'ok', dns: 'ok' };
  for (const change of [{ gate: 'disabled' }, { gate: 'human_active' }, { gate: 'maintenance' },
    { intent: 'stop-request' }, { config_epoch: 'b'.repeat(64) }, { network_epoch: 'new-path' }, { process_epoch: 'new-process' }]) {
    const view = api.health_public(sample, { ...base, now: 181, ...change });
    assert.notEqual(view.health.state, 'healthy');
    assert.equal(view.health.vpn, 'unknown');
    if (change.gate === 'disabled') assert.equal(view.health.state, 'disabled');
    if (change.gate) assert.equal(view.recovery.state, 'paused');
  }
});

test('public recovery displays an admitted running stage while its own lifecycle lock gates decisions', () => {
  for (const stage of ['soft_running', 'transport_running']) {
    const state = { ...reserve(until(180), 180, 'soft'), stage,
      reason: stage === 'soft_running' ? 'repairing_policy' : 'restarting_transport' };
    const ctx = { ...base, now: 181, gate: 'operation_active' };
    const view = api.health_public(state, ctx);
    assert.equal(view.health.state, 'recovering');
    assert.equal(view.recovery.state, 'recovering');
    assert.equal(view.health.reason, state.reason);
    assert.equal(view.recovery.attempts, 1);
    assert.equal(advance(state, 181, { gate: 'operation_active' }).action, undefined);
    assert.equal(reserve(state, 181, 'soft', { gate: 'operation_active' }), null);
    for (const change of [{ gate: 'disabled' }, { gate: 'maintenance' }, { gate: 'human_active' },
      { gate: 'pending_edits' }, { gate: 'status_stale' }, { intent: 'stop-request' },
      { config_epoch: 'b'.repeat(64) }, { network_epoch: 'new-path' }, { process_epoch: 'new-process' },
      { process: 'unknown' }, { process: 'fail' }, { now: 226 }, { now: 179 }]) {
      const changed = api.health_public(state, { ...ctx, ...change });
      assert.notEqual(changed.health.state, 'recovering', JSON.stringify(change));
      assert.equal(changed.recovery.state, 'paused', JSON.stringify(change));
    }
  }
  const idle = api.health_public(until(180), { ...base, now: 181, gate: 'operation_active' });
  assert.equal(idle.health.state, 'unknown');
  assert.equal(idle.recovery.state, 'paused');
});

function live(status = {}) {
  return { packages: { csqtt: { main: { '.type': 'client', enabled: '1' } } },
    services: { csqtt: { instances: { client: { running: true, pid: 901 } } } }, files: {
      '/proc/uptime': '100.00 0.00', '/proc/sys/kernel/random/boot_id': 'test-boot',
      '/proc/901/stat': '901 (name with ) spaces) S ' + Array(18).fill('0').join(' ') + ' 1234 0\n',
      '/var/run/csqtt/health-config.current': 'a'.repeat(64),
      '/var/run/csqtt/status.json': JSON.stringify({ state: 'connected', active_workers: 72,
        pid: 901, process_startticks: 1234, boot_id: 'test-boot', updated_boottime_ms: 99000, ...status }),
    } };
}
test('status rejects wrong PID, recycled PID, previous boot, stale/future/missing monotonic metadata', () => {
  assert.equal(runtime('status', live()).output[0].core.state, 'connected');
  for (const change of [{ pid: 902 }, { process_startticks: 1235 }, { boot_id: 'old-boot' },
    { updated_boottime_ms: 84999 }, { updated_boottime_ms: 100010 }, { updated_boottime_ms: null }]) {
    const core = runtime('status', live(change)).output[0].core;
    assert.equal(core.state, 'starting'); assert.equal(core.active_workers, undefined);
  }
});

test('status accepts only timestamps inside the uptime tick and expires against its upper bound', () => {
  // This decimal also catches conversion through floating-point seconds.
  for (const [uptime, lower] of [['100.00', 100000], ['100.01', 100010], ['100.08', 100080],
    ['100.09', 100090], ['100.12', 100120], ['1048.57', 1048570], ['1234567.89', 1234567890]]) {
    for (const offset of [0, 1, 9]) {
      const f = live({ updated_boottime_ms: lower + offset }); f.files['/proc/uptime'] = uptime + '\t0.00';
      assert.equal(runtime('status', f).output[0].core.state, 'connected', `${uptime}/${offset}`);
    }
    for (const [offset, expected] of [[10, 'starting'], [-14990, 'connected'], [-14991, 'starting'], [-15000, 'starting']]) {
      const f = live({ updated_boottime_ms: lower + offset }); f.files['/proc/uptime'] = uptime + ' 0.00';
      assert.equal(runtime('status', f).output[0].core.state, expected, `${uptime}/${offset}`);
    }
  }
  for (const change of [{ pid: 902 }, { process_startticks: 1235 }, { boot_id: 'old-boot' }]) {
    assert.equal(runtime('status', live({ updated_boottime_ms: 100009, ...change })).output[0].core.state, 'starting');
  }
  const stopped = live({ updated_boottime_ms: 100009 }); stopped.services.csqtt.instances.client.running = false;
  assert.equal(runtime('status', stopped).output[0].core.state, 'stopped');
});

test('status fails closed on malformed uptime or nonnumeric, fractional and unsafe timestamps', () => {
  for (const value of ['', '100', '100.0', '100.000', '-100.00', '1e2.00', '100.00x', '9007199254740.00']) {
    const f = live(); f.files['/proc/uptime'] = value;
    assert.equal(runtime('status', f).output[0].core.state, 'starting', value);
  }
  for (const value of [null, true, false, '100001', [], {}, -1, 100000.5, 9007199254740992]) {
    assert.equal(runtime('status', live({ updated_boottime_ms: value })).output[0].core.state, 'starting', JSON.stringify(value));
  }
});

function leaseFixture(lease = {}, status = {}) {
  const f = live({ health: { human_epoch: 7 }, ...status });
  f.files['/var/run/csqtt/recovery-lease.json'] = JSON.stringify({ ok: true, pid: 901,
    process_startticks: 1234, boot_id: 'test-boot', human_epoch: 7, recovery_id: 'fixture-recovery',
    lease_secs: 90, updated_boottime_ms: 99000, ...lease });
  return f;
}

test('recovery lease shares uptime interval handling and keeps its strict conservative expiry', () => {
  for (const value of [100000, 100001, 100009, 15011]) {
    runtime('health-lease-valid', leaseFixture({ updated_boottime_ms: value }));
  }
  for (const value of [100010, 15010, 15000, null, true, '99000', -1, 99000.5, 9007199254740992]) {
    assert.throws(() => runtime('health-lease-valid', leaseFixture({ updated_boottime_ms: value })), /Exit 1/, JSON.stringify(value));
  }
  for (const change of [{ ok: false }, { pid: 902 }, { process_startticks: 1235 }, { boot_id: 'old-boot' },
    { human_epoch: 8 }, { recovery_id: 'invalid id' }, { lease_secs: 91 }]) {
    assert.throws(() => runtime('health-lease-valid', leaseFixture({ updated_boottime_ms: 100009, ...change })), /Exit 1/);
  }
  for (const status of [{ pid: 902 }, { process_startticks: 1235 }, { boot_id: 'old-boot' },
    { updated_boottime_ms: 85009 }, { health: { human_epoch: 8 } }]) {
    assert.throws(() => runtime('health-lease-valid', leaseFixture({}, status)), /Exit 1/);
  }
  const malformed = leaseFixture(); malformed.files['/proc/uptime'] = '100.000 0.00';
  assert.throws(() => runtime('health-lease-valid', malformed), /Exit 1/);
});

test('current unexpired CAPTCHA is a warning alongside healthy allocations; expired CAPTCHA disappears', () => {
  const challenge = { id: 'safe-id', state: 'manual', expires_at: 1900000100, human_active: false };
  const healthy = runtime('status', live({ state: 'captcha_required', captcha: challenge })).output[0];
  assert.equal(healthy.core.state, 'connected'); assert.equal(healthy.core.captcha.id, challenge.id);
  assert.equal(runtime('status', live({ state: 'captcha_required', active_workers: 0, captcha: challenge })).output[0].core.state, 'captcha_required');
  const expired = runtime('status', live({ state: 'captcha_required', active_workers: 0,
    captcha: { ...challenge, expires_at: 1899999999 } })).output[0].core;
  assert.equal(expired.captcha, undefined); assert.equal(expired.state, 'connecting');
});
