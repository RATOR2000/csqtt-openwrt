# Root-only lifecycle serialization shared by manage and rc.common. A child
# inherits the current owner; prepared starts never recursively acquire a lock.
csqtt_startticks() {
	case "$1" in ''|*[!0-9]*) return 1 ;; esac
	[ -r "/proc/$1/stat" ] || return 1
	sed 's/^[0-9][0-9]* (.*) //' "/proc/$1/stat" | cut -d ' ' -f 20
}
csqtt_operation_owned() {
	[ -n "${CSQTT_OPERATION_OWNER:-}" ] && [ -n "${CSQTT_OPERATION_TICKS:-}" ] || return 1
	[ "$(cat /var/lock/csqtt-operation/pid 2>/dev/null)" = "$CSQTT_OPERATION_OWNER" ] || return 1
	[ "$(cat /var/lock/csqtt-operation/ticks 2>/dev/null)" = "$CSQTT_OPERATION_TICKS" ] || return 1
	[ "$(csqtt_startticks "$CSQTT_OPERATION_OWNER" 2>/dev/null)" = "$CSQTT_OPERATION_TICKS" ]
}
csqtt_intent() {
	mkdir -p /var/run/csqtt
	chmod 0700 /var/run/csqtt
	local intent
	intent=$(mktemp /var/run/csqtt/intent.XXXXXX) || return 1
	printf '%s\n' "${intent##*/}" > "$intent"
	mv "$intent" /var/run/csqtt/intent
}
csqtt_operation_release() {
	[ "${CSQTT_OPERATION_OWNER:-}" = "$$" ] || return 0
	if csqtt_operation_owned; then
		rm -f /var/lock/csqtt-operation/pid /var/lock/csqtt-operation/ticks
		rmdir /var/lock/csqtt-operation 2>/dev/null || true
	fi
}
csqtt_operation_cleanup() {
	if command -v csqtt_extra_cleanup >/dev/null 2>&1; then csqtt_extra_cleanup; fi
	csqtt_operation_release
}
csqtt_operation_enter() {
	csqtt_operation_owned && return 0
	umask 077
	# Publish user intent BEFORE waiting, so an already queued recovery is revoked.
	[ "${1:-normal}" = recovery ] || csqtt_intent || return 1
	mkdir -p /var/lock
	local waits=0 owner ticks current
	while ! mkdir /var/lock/csqtt-operation 2>/dev/null; do
		# Never remove an incomplete freshly-created lock. Its owner will publish
		# both fields immediately; otherwise bounded waiting reports failure.
		# Re-read under a separate reaper mutex: a second stale-lock waiter must
		# never remove the fields of the first waiter's newly acquired live lock.
		if mkdir /var/lock/csqtt-operation-reaper 2>/dev/null; then
			owner=$(cat /var/lock/csqtt-operation/pid 2>/dev/null || true)
			ticks=$(cat /var/lock/csqtt-operation/ticks 2>/dev/null || true)
			current=$(csqtt_startticks "$owner" 2>/dev/null || true)
			if [ -n "$owner" ] && [ -n "$ticks" ] && [ "$current" != "$ticks" ]; then
				rm -f /var/lock/csqtt-operation/pid /var/lock/csqtt-operation/ticks
				rmdir /var/lock/csqtt-operation 2>/dev/null || true
			fi
			rmdir /var/lock/csqtt-operation-reaper 2>/dev/null || true
		fi
		[ "$waits" -lt 90 ] || return 1
		waits=$((waits + 1)); sleep 1
	done
	CSQTT_OPERATION_OWNER=$$
	CSQTT_OPERATION_TICKS=$(csqtt_startticks "$$") || return 1
	export CSQTT_OPERATION_OWNER CSQTT_OPERATION_TICKS
	printf '%s\n' "$CSQTT_OPERATION_OWNER" > /var/lock/csqtt-operation/pid
	printf '%s\n' "$CSQTT_OPERATION_TICKS" > /var/lock/csqtt-operation/ticks
	trap 'csqtt_operation_cleanup' EXIT
	trap 'exit 1' HUP INT TERM
}
csqtt_network_evidence() {
	local source=false fallback=false unreachable=false output=false forward=false
	ip -4 rule show pref 11880 2>/dev/null | grep -Eq 'from 198\.18\.0\.1(/32)? lookup 202$' && source=true
	ip -4 rule show pref 11881 2>/dev/null | grep -Eq 'from 198\.18\.0\.1(/32)? (unreachable|prohibit)$' && fallback=true
	ip -4 route show table 202 2>/dev/null | grep -Eq '^unreachable default( proto [a-z0-9]+)? metric 42760' && unreachable=true
	nft list chain inet csqtt output_guard 2>/dev/null | grep -Fq 'ip saddr 198.18.0.1 oifname != "csqtt0" reject' && output=true
	nft list chain inet csqtt forward_guard >/dev/null 2>&1 && forward=true
	printf '{"source_rule":%s,"fallback_rule":%s,"unreachable_route":%s,"output_guard":%s,"forward_guard":%s}\n' "$source" "$fallback" "$unreachable" "$output" "$forward" > "$RUN/health-network.json"
	[ "$source" = true ] && [ "$fallback" = true ] && [ "$unreachable" = true ] && [ "$output" = true ] && [ "$forward" = true ]
}
