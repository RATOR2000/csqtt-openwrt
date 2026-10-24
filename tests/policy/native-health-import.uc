// Import the unchanged filesystem module. Flattened Node/native adapters do not
// exercise ucode's export grammar and must not replace this parser regression.
import { health_assess, health_initial, health_advance, health_reserve, health_complete, health_public }
	from '../../openwrt/csqtt/files/health.uc';

function check(ok, message) { if (!ok) die(message); }
let ctx = { boot_id: 'module-test', config_epoch: 'config-one', network_epoch: 'network-one',
	intent: 'intent-one', process_epoch: 'process-one', automatic: true, process: 'ok', now: 0, gate: null };
let wan = { schema_version: 1, config_valid: true, completed: true, endpoints: [
	{ index: 0, dns: 'ok', https: 'ok', reachable: true },
	{ index: 1, dns: 'ok', https: 'ok', reachable: true }] };
let vpn = { schema_version: 1, config_valid: true, completed: true, endpoints: [
	{ index: 0, dns: 'ok', https: 'fail', reachable: false },
	{ index: 1, dns: 'ok', https: 'fail', reachable: false }] };
check(health_assess(wan, vpn).confirmed === true, 'Imported health assessment failed');
let state = health_initial(ctx);
check(state.stage === 'idle' && state.failure_since == null, 'Imported health initial state failed');
for (let now = 0; now <= 180; now += 30) {
	ctx.now = now;
	state = health_advance(state, ctx, wan, vpn);
}
check(state.action === 'soft', 'Imported health advance did not preserve the failure window');
ctx.wan = wan; ctx.vpn = vpn;
state = health_reserve(state, ctx, 'soft');
check(state && state.stage === 'soft_running' && length(state.attempts) === 1,
	'Imported health reserve failed');
ctx.gate = 'operation_active';
let visible = health_public(state, ctx);
check(visible.health.state === 'recovering' && visible.recovery.state === 'recovering',
	'Imported health public display lost an admitted recovery');
ctx.gate = null;
state = health_complete(state, ctx, 'soft', true);
check(state.stage === 'soft_complete' && state.next_action === 210, 'Imported health complete failed');
ctx.gate = 'disabled';
visible = health_public(state, ctx);
check(visible.health.state === 'disabled' && visible.recovery.state === 'paused',
	'Imported health public display ignored Stop');
print('Native ucode health module import and exported recovery API passed\n');
