// Pure bounded recovery state machine. All clocks are seconds since this boot;
// a different boot/config/intent or uncertain observation cancels escalation.
function h_has(items, item) {
	for (let i = 0; i < length(items); i++) if (items[i] === item) return true;
	return false;
}
function h_number(value, maximum) {
	return type(value) === 'int' || type(value) === 'double' || type(value) === 'number'
		? (value >= 0 && value <= maximum ? value : 0) : 0;
}
function h_endpoint(probe, index) {
	if (!probe || probe.schema_version !== 1 || probe.config_valid !== true || probe.completed !== true) return null;
	let entries = probe.endpoints || [];
	for (let i = 0; i < length(entries); i++) if (entries[i].index === index) return entries[i];
	return null;
}
function h_reachable(endpoint) {
	return !!(endpoint && endpoint.dns === 'ok' && endpoint.reachable === true &&
		h_has(['ok', 'endpoint_error'], endpoint.https));
}
export function health_assess(wan, vpn) {
	let wan_ok = 0, vpn_ok = 0, vpn_fail = 0, vpn_dns = 0, wan_dns = 0, matched = 0;
	for (let i = 0; i < 2; i++) {
		let w = h_endpoint(wan, i), v = h_endpoint(vpn, i), good = h_reachable(w);
		if (good) wan_ok++;
		if (h_reachable(v)) vpn_ok++;
		if (v && v.dns === 'ok') vpn_dns++;
		if (w && w.dns === 'ok') wan_dns++;
		// A DNS timeout or a reachable HTTP error is never proof of a dead VPN.
		if (v && v.dns === 'ok' && v.https === 'fail' && v.reachable === false) {
			vpn_fail++;
			if (good) matched++;
		}
	}
	let confirmed = vpn_fail === 2 && matched === 2;
	let group_dns = vpn && vpn.group_dns;
	return { wan: wan_ok ? 'ok' : (wan_dns === 2 ? 'fail' : 'unknown'),
		vpn: vpn_ok ? 'ok' : (vpn_fail === 2 ? 'fail' : 'unknown'),
		dns: group_dns === 'fail' ? 'fail' : (group_dns === 'unknown' ? 'unknown' : (vpn_dns === 2 ? 'ok' : 'unknown')),
		confirmed: confirmed };
}
export function health_initial(ctx) {
	return { version: 1, boot_id: ctx.boot_id, config_epoch: ctx.config_epoch,
		intent: ctx.intent, process_epoch: ctx.process_epoch, network_epoch: ctx.network_epoch, attempts: [], failure_since: null, stage: 'idle',
		last_sample: ctx.now, last_action: null, next_action: null,
		state: 'unknown', reason: 'awaiting_sample', wan: 'unknown', vpn: 'unknown', dns: 'unknown' };
}
export function health_advance(previous, ctx, wan, vpn) {
	let old = previous && previous.version === 1 && previous.boot_id === ctx.boot_id ? previous : health_initial(ctx);
	let result = health_initial(ctx), attempts = [];
	for (let i = 0; i < length(old.attempts || []); i++) {
		let at = old.attempts[i];
		if (at >= 0 && at <= ctx.now && ctx.now - at < 3600 && length(attempts) < 3) push(attempts, at);
	}
	result.attempts = attempts;
	result.last_action = old.last_action != null && old.last_action <= ctx.now ? old.last_action : null;
	let changed = old.config_epoch !== ctx.config_epoch || old.network_epoch !== ctx.network_epoch || old.intent !== ctx.intent || old.process_epoch !== ctx.process_epoch;
	let gap = old.last_sample == null || ctx.now < old.last_sample || ctx.now - old.last_sample > 45;
	if (ctx.gate) {
		result.state = ctx.gate === 'disabled' ? 'disabled' : (ctx.gate === 'human_active' ? 'captcha_required' : 'unknown');
		result.reason = ctx.gate;
		return result;
	}
	let assessment = health_assess(wan, vpn);
	result.wan = assessment.wan; result.vpn = assessment.vpn; result.dns = assessment.dns;
	result.state = assessment.vpn === 'ok' && assessment.dns === 'ok' ? 'healthy' : (assessment.wan === 'fail' ? 'wan_down' : 'degraded');
	result.reason = assessment.dns === 'fail' ? 'group_dns_failed' : (assessment.vpn === 'ok' ? 'vpn_reachable' : (assessment.confirmed ? 'vpn_transport_failed' : 'probe_uncertain'));
	if (!assessment.confirmed || changed || gap) return result;
	result.failure_since = old.failure_since == null ? ctx.now : old.failure_since;
	result.stage = old.stage || 'idle';
	// An action only survives the immediately following valid samples from the
	// same desired configuration. A stopped observer cannot catch up on history.
	if (result.stage === 'soft_complete' && old.next_action != null) {
		result.next_action = old.next_action;
		if (ctx.now >= old.next_action && ctx.automatic) result.action = 'transport';
		return result;
	}
	if (result.stage !== 'idle') result.stage = 'idle';
	if (ctx.now - result.failure_since < 180) return result;
	if (!ctx.automatic) { result.reason = 'observe_only'; return result; }
	if (length(attempts) >= 3) { result.reason = 'hourly_limit'; return result; }
	if (result.last_action != null && ctx.now - result.last_action < 300) {
		result.reason = 'cooldown'; result.next_action = result.last_action + 300; return result;
	}
	result.action = 'soft';
	return result;
}
export function health_reserve(state, ctx, action) {
	if (!state || state.boot_id !== ctx.boot_id || state.config_epoch !== ctx.config_epoch || state.network_epoch !== ctx.network_epoch || state.intent !== ctx.intent || state.process_epoch !== ctx.process_epoch ||
		ctx.gate || !ctx.automatic || state.action !== action || state.last_sample > ctx.now || ctx.now - state.last_sample > 15)
		return null;
	let assessment = health_assess(ctx.wan, ctx.vpn);
	if (!assessment.confirmed) return null;
	if (action === 'soft') {
		if (length(state.attempts || []) >= 3 || (state.last_action != null && ctx.now - state.last_action < 300)) return null;
		push(state.attempts, ctx.now);
		state.last_action = ctx.now;
	} else if (action !== 'transport' || state.stage !== 'soft_complete' || ctx.now < state.next_action) return null;
	state.stage = action === 'soft' ? 'soft_running' : 'transport_running';
	state.state = 'recovering'; state.reason = action === 'soft' ? 'repairing_policy' : 'restarting_transport';
	state.action = null;
	return state;
}
export function health_complete(state, ctx, action, success) {
	if (!state || state.boot_id !== ctx.boot_id) return health_initial(ctx);
	state.last_sample = ctx.now;
	state.action = null;
	if (state.config_epoch !== ctx.config_epoch || state.network_epoch !== ctx.network_epoch || state.intent !== ctx.intent || ctx.gate) {
		state.stage = 'idle'; state.failure_since = null; state.reason = 'intent_changed'; return state;
	}
	if (action === 'soft' && success) {
		state.stage = 'soft_complete'; state.next_action = ctx.now + 30;
		state.reason = 'waiting_after_policy';
	} else {
		state.stage = 'idle'; state.failure_since = null; state.next_action = null;
		state.reason = success ? 'transport_restarted' : 'recovery_failed';
	}
	state.state = 'degraded';
	return state;
}
export function health_public(state, ctx) {
	let fresh = state && state.version === 1 && state.boot_id === ctx.boot_id &&
		state.config_epoch === ctx.config_epoch && state.network_epoch === ctx.network_epoch &&
		state.intent === ctx.intent && state.process_epoch === ctx.process_epoch &&
		state.last_sample <= ctx.now && ctx.now - state.last_sample <= 45;
	// The admitted action itself owns the lifecycle lock. Show its saved stage
	// while that is the only gate; admission and escalation still use ctx.gate.
	let active = fresh && ctx.automatic && ctx.process === 'ok' && ctx.gate === 'operation_active' &&
		state.state === 'recovering' && (state.stage === 'soft_running' || state.stage === 'transport_running');
	let gate = active ? null : ctx.gate, good = fresh && !gate;
	let states = ['healthy', 'degraded', 'wan_down', 'unknown', 'disabled', 'recovering', 'captcha_required'];
	let reasons = ['awaiting_sample', 'disabled', 'human_active', 'maintenance', 'policy_error', 'guard_missing', 'pending_edits',
		'operation_active', 'status_stale', 'configuration_changed', 'probe_uncertain', 'vpn_reachable', 'group_dns_failed',
		'vpn_transport_failed', 'observe_only', 'hourly_limit', 'cooldown', 'repairing_policy',
		'restarting_transport', 'waiting_after_policy', 'intent_changed', 'transport_restarted', 'recovery_failed'];
	let reason = gate && h_has(reasons, gate) ? gate :
		(good && h_has(reasons, state.reason) ? state.reason : 'awaiting_sample');
	let phase = !ctx.automatic ? 'observing' : 'idle';
	if (gate && ctx.automatic) phase = 'paused';
	if (good && ctx.automatic) {
		if (state.stage === 'soft_running' || state.stage === 'transport_running') phase = 'recovering';
		else if (reason === 'cooldown') phase = 'cooldown';
		else if (reason === 'hourly_limit') phase = 'limited';
		else if (reason === 'waiting_after_policy' || state.failure_since != null) phase = 'waiting';
		else if (gate) phase = 'paused';
	}
	let age = good ? ctx.now - state.last_sample : 0;
	let visible_state = ctx.gate === 'disabled' ? 'disabled' :
		(ctx.gate === 'human_active' ? 'captcha_required' : (good && h_has(states, state.state) ? state.state : 'unknown'));
	return { health: { state: visible_state, reason: reason,
		wan: good && h_has(['ok', 'fail', 'unknown'], state.wan) ? state.wan : 'unknown',
		vpn: good && h_has(['ok', 'fail', 'unknown'], state.vpn) ? state.vpn : 'unknown',
		dns: good && h_has(['ok', 'fail', 'unknown'], state.dns) ? state.dns : 'unknown',
		process: ctx.process, sample_age_secs: h_number(age, 86400) },
		recovery: { state: phase, reason: reason, automatic: !!ctx.automatic,
			attempts: good ? length(state.attempts || []) : 0,
			next_attempt_in_secs: good && state.next_action > ctx.now ? h_number(state.next_action - ctx.now, 3600) : 0 } };
}
