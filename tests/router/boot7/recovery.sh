#!/bin/sh
# Boot7 recovery. Native apply owns policy replacement and guard release.
# Context manifest pins original CURRENT4 hashes, baseline copies and immutable
# inputs. Optional staged/{csqtt,firewall} fixtures must be pinned before arming.
# Controller writes stage BEFORE each action: armed/config/startup/hold/files/
# fault/apply/failed. Files and later stages require a saved, installed closed hold.
# Recovery checkpoints are write-ahead; sync the private context before reboot.
set -eu
umask 077
MODE=${1:-}; STATE=${2:-}; LOCKED=0; LOGGING=0; FAILURE=unspecified
export LC_ALL=C
fail() { FAILURE=$1; printf 'recovery_failed=%s\n' "$1" >&2; exit 1; }
private() {
    [ ! -L "$1" ] || return 1
    case "$2" in d) [ -d "$1" ] ;; f) [ -f "$1" ] ;; *) return 1 ;; esac || return 1
    ucode -e 'import * as fs from "fs"; let s=fs.stat(ARGV[0]); if(!s || s.uid!==0 || (s.mode & 63)!==0) exit(1);' "$1" 2>/dev/null
}
ticks() { sed -n 's/^[0-9][0-9]* (.*) //p' "/proc/$1/stat" | awk '{print $20}'; }
inputs() {
    [ "$(id -u)" = 0 ] || fail root_required
    printf '%s\n' "$STATE" | grep -Eq '^/etc/csqtt/backups/boot7-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$' || fail state_path
    for p in /etc/csqtt /etc/csqtt/backups "$STATE" "$STATE/baseline"; do private "$p" d || fail private_directory; done
    [ ! -L /etc/config ] && [ -d /etc/config ] || fail config_directory
    for p in identity init-was-enabled armed.sha256 closed.nft fault-set recovery.sh baseline/csqtt baseline/dhcp baseline/firewall baseline/network; do
        private "$STATE/$p" f || fail private_input
    done
    [ "$(cat "$STATE/identity")" = CSQTT-BOOT7 ] || fail identity
    [ "$(cat "$STATE/init-was-enabled")" = 1 ] || fail original_startup_state
    SET=$(cat "$STATE/fault-set")
    case "$SET" in ''|*[!A-Za-z0-9_]*) fail fault_set_name ;; esac
    printf '%s\n' "$SET" | grep -Eq '^d_[A-Za-z0-9_]+_[0-9]+$' || fail fault_set_name
    for p in csqtt dhcp firewall network; do [ -f "/etc/config/$p" ] && [ ! -L "/etc/config/$p" ] || fail config_file; done
    if [ -e "$STATE/staged" ] || [ -L "$STATE/staged" ]; then
        private "$STATE/staged" d || fail private_fixture_directory
        for p in csqtt firewall; do private "$STATE/staged/$p" f || fail private_fixture; done
    fi
    for p in armed stage finished configs-restored recovery.phase recovery.phase.new recovery.public.log recovery.private.log recovery.exit apply.private.log recovery.nft.private.json watchdog.private.log; do
        if [ -e "$STATE/$p" ] || [ -L "$STATE/$p" ]; then private "$STATE/$p" f || fail private_marker; fi
    done
    STAGE=prepared; PHASE=
    [ ! -e "$STATE/armed" ] || STAGE=armed
    [ ! -e "$STATE/stage" ] || STAGE=$(cat "$STATE/stage")
    [ ! -e "$STATE/recovery.phase" ] || PHASE=$(cat "$STATE/recovery.phase")
    case "$STAGE" in prepared|armed|config|startup|hold|files|fault|apply|failed) ;; *) fail stage_identity ;; esac
    case "$PHASE" in ''|restoring|applying|applied|starting|complete) ;; *) fail recovery_phase_identity ;; esac
    if [ -e "$STATE/configs-restored" ]; then
        [ "$(cat "$STATE/configs-restored")" = CSQTT-BOOT7-CONFIGS-RESTORED ] || fail restore_marker
        [ -n "$PHASE" ] || PHASE=applying
    fi
}
manifest() {
    seen=' '; configs=0
    while read -r hash path extra || [ -n "$hash$path$extra" ]; do
        [ -n "$path" ] && [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail armed_manifest
        case "$hash" in *[!a-fA-F0-9]*) fail armed_manifest ;; esac
        case "$seen" in *" $path "*) fail armed_manifest_duplicate ;; esac
        seen="$seen$path "
        case "$path" in
            /etc/config/csqtt|/etc/config/dhcp|/etc/config/firewall|/etc/config/network)
                configs=$((configs+1)); path="$STATE/baseline/${path##*/}" ;;
            "$STATE"/baseline/csqtt|"$STATE"/baseline/dhcp|"$STATE"/baseline/firewall|"$STATE"/baseline/network) private "$path" f || fail manifest_input ;;
            "$STATE"/staged/csqtt|"$STATE"/staged/firewall) private "$path" f || fail manifest_input ;;
            "$STATE"/*)
                name=${path#"$STATE"/}; case "$name" in ''|*[!A-Za-z0-9_.-]*) fail manifest_path ;; esac
                private "$path" f || fail manifest_input
                ;;
            *) fail manifest_path ;;
        esac
        actual=$(sha256sum "$path" 2>/dev/null) || fail manifest_hash
        [ "${actual%% *}" = "$hash" ] || fail armed_hash_changed
    done < "$STATE/armed.sha256"
    [ "$configs" = 4 ] || fail armed_manifest_incomplete
    for p in identity init-was-enabled closed.nft fault-set recovery.sh baseline/csqtt baseline/dhcp baseline/firewall baseline/network; do
        case "$seen" in *" $STATE/$p "*) ;; *) fail immutable_manifest_incomplete ;; esac
    done
    if [ -d "$STATE/staged" ]; then
        for p in csqtt firewall; do case "$seen" in *" $STATE/staged/$p "*) ;; *) fail fixture_manifest_incomplete ;; esac; done
    fi
}
pending_test() {
    for p in csqtt dhcp firewall network; do
        delta=$(uci -q changes "$p" 2>/dev/null) || return 1
        [ -z "$delta" ] || return 1
    done
}
pending() { pending_test || fail owner_pending_edits; }
baseline() { for p in "$@"; do cmp -s "$STATE/baseline/$p" "/etc/config/$p" || fail baseline_changed; done; }
configs() {
    CHANGED=0
    for p in csqtt dhcp firewall network; do
        if cmp -s "$STATE/baseline/$p" "/etc/config/$p"; then continue; fi
        case "$p" in csqtt|firewall) ;; *) fail owner_config_changed ;; esac
        [ -f "$STATE/staged/$p" ] && cmp -s "$STATE/staged/$p" "/etc/config/$p" || fail owner_config_changed
        CHANGED=1
    done
    case "$PHASE" in applying|applied|starting|complete) [ "$CHANGED" = 0 ] || fail recovery_config_changed ;; esac
    if [ -z "$PHASE" ]; then case "$STAGE" in prepared|armed) [ "$CHANGED" = 0 ] || fail undeclared_config_change ;; esac; fi
}
checkpoint() {
    printf '%s\n' "$1" > "$STATE/recovery.phase.new"
    mv "$STATE/recovery.phase.new" "$STATE/recovery.phase" || fail recovery_checkpoint
    PHASE=$1
}
no_writer() { [ ! -e /var/lock/csqtt-policy ] && [ ! -L /var/lock/csqtt-policy ] || fail policy_writer_or_stale_lock; }
init_links() {
    [ -L /etc/rc.d/S95csqtt ] && [ -L /etc/rc.d/K10csqtt ] &&
        [ "$(readlink /etc/rc.d/S95csqtt)" = ../init.d/csqtt ] && [ "$(readlink /etc/rc.d/K10csqtt)" = ../init.d/csqtt ] || fail startup_links
}
chains_test() {
    for chain in maintenance_guard maintenance_dns; do
        hook=forward; [ "$chain" != maintenance_dns ] || hook=input
        nft -j list chain inet csqtt "$chain" | ucode -e '
import * as fs from "fs";
let d=json(fs.readfile("/dev/stdin")), found=0, rules=0;
for(let r in d.nftables || []) {
 if(r.chain) { let c=r.chain; if(c.family!=="inet" || c.table!=="csqtt" || c.name!==ARGV[0] || c.type!=="filter" || c.hook!==ARGV[1] || c.prio!==-20 || c.policy!=="accept") exit(1); found++; }
 if(r.rule) { if(r.rule.family!=="inet" || r.rule.table!=="csqtt" || r.rule.chain!==ARGV[0]) exit(1); rules++; }
}
if(found!==1 || (ARGV[2]==="closed" ? rules<1 : rules!==0)) exit(1);
' "$chain" "$hook" "$1" || return 1
    done
}
chains() { chains_test "$1" || fail maintenance_chain_state; }
hold_include() {
    [ "$(uci -q get firewall.csqtt_hold.csqtt_owned)" = 1 ] &&
        [ "$(uci -q get firewall.csqtt_hold.path)" = /etc/csqtt/hold.nft ] &&
        [ "$(uci -q get firewall.csqtt_hold.position)" = ruleset-post ] &&
        [ "$(uci -q get firewall.csqtt_hold.type)" = nftables ] &&
        [ "$(uci -q get firewall.csqtt_hold.enabled || true)" != 0 ] || fail hold_include
}
closed() {
    hold_include
    private /etc/csqtt/hold.nft f || fail saved_hold
    cmp -s "$STATE/closed.nft" /etc/csqtt/hold.nft || fail saved_hold_changed
    chains closed
}
full_files() { for p in policy.json policy.nft forward.nft input.nft; do private "/etc/csqtt/$p" f && [ -s "/etc/csqtt/$p" ] || return 1; done; }
drop_lock() {
    [ "$LOCKED" = 1 ] || return 0
    private "$STATE/recovery.lock" d && private "$STATE/recovery.lock/pid" f && private "$STATE/recovery.lock/startticks" f &&
        [ "$(cat "$STATE/recovery.lock/pid")" = "$$" ] && [ "$(cat "$STATE/recovery.lock/startticks")" = "$START" ] &&
        [ "$(ticks "$$")" = "$START" ] || return 1
    rm "$STATE/recovery.lock/pid" "$STATE/recovery.lock/startticks" && rmdir "$STATE/recovery.lock" || return 1
    LOCKED=0
}
finish() {
    rc=$?; trap - EXIT INT TERM
    if ! drop_lock; then rc=1; FAILURE=recovery_lock_identity; fi
    if [ "$LOGGING" = 1 ]; then
        printf 'recovery_succeeded=%s\n' "$([ "$rc" = 0 ] && printf true || printf false)" >> "$STATE/recovery.public.log"
        [ "$rc" = 0 ] || printf 'recovery_failure=%s\n' "$FAILURE" >> "$STATE/recovery.public.log"
        printf '%s\n' "$rc" > "$STATE/recovery.exit"
    fi
    exit "$rc"
}
atomic_config() {
    target=/etc/config/$1; tmp=/etc/config/.boot7-$1-$$
    [ ! -e "$tmp" ] && [ ! -L "$tmp" ] || fail config_staging_collision
    mode=$(ucode -e 'import * as fs from "fs"; let s=fs.stat(ARGV[0]); if(!s || s.uid!==0) exit(1); printf("%o",s.mode & 511);' "$target") || fail config_metadata
    cp "$STATE/baseline/$1" "$tmp" && chmod "$mode" "$tmp" && mv "$tmp" "$target" || fail config_restore
}
fault() {
    nft -j list table inet csqtt > "$STATE/recovery.nft.private.json" || fail fault_inventory
    exists=$(ucode -e '
import * as fs from "fs";
let d=json(fs.readfile(ARGV[0])), name=ARGV[1], found=0, wrong=false, refs=false;
function mentions(v) { if(type(v)==="string") return v===name || v==="@"+name; if(type(v)==="array") for(let x in v) { if(mentions(x)) return true; } else if(type(v)==="object") for(let k in v) { if(mentions(v[k])) return true; } return false; }
for(let r in d.nftables || []) {
 if(r.set && r.set.name===name) { let s=r.set; if(s.family!=="inet" || s.table!=="csqtt" || (s.type!=="ipv4_addr" && s.type!=="ipv6_addr")) exit(1); wrong=s.type==="ipv6_addr"; if(wrong && length(s.elem || [])) exit(1); found++; }
 if(r.rule && mentions(r.rule.expr)) refs=true;
}
if(found>1 || (wrong && refs)) exit(1); printf("%d",wrong ? 1 : 0);
' "$STATE/recovery.nft.private.json" "$SET") || fail fault_identity
    case "$exists" in 0) ;; 1) nft delete set inet csqtt "$SET" || fail fault_remove ;; *) fail fault_inventory ;; esac
}
ready_test() {
    [ ! -e /var/lock/csqtt-policy ] && [ ! -L /var/lock/csqtt-policy ] || return 1
    for p in csqtt dhcp firewall network; do cmp -s "$STATE/baseline/$p" "/etc/config/$p" || return 1; done
    pending_test && full_files || return 1
    [ "$(uci -q get csqtt.main.enabled)" = 1 ] || return 1
    ucode -e 'import * as fs from "fs"; let m=json(fs.readfile("/etc/csqtt/policy.json")), ids=split(trim(fs.readfile("/var/run/csqtt/dns.ids") || ""),"\n"), active=0; if(!length(m.devices || []) || !length(ids) || !length(ids[0])) exit(1); for(let g in m.groups || []) if(length(g.macs || [])) active++; if(active<1 || active!==length(ids)) exit(1);' || return 1
    ucode /usr/share/csqtt/runtime.uc dns-ready || return 1
    chains_test empty || return 1
    release=$(ucode -e 'import { hold } from "/usr/share/csqtt/policy.uc"; print(hold([],false));') || return 1
    printf '%s\n' "$release" | cmp -s - /etc/csqtt/hold.nft
}
ready() { ready_test || fail native_readiness_or_release; }
apply_baseline() {
    # Retrying this write-ahead phase is safe even after a prior native release.
    # No config copy or manual guard release occurs here; native apply closes first.
    pending; no_writer; manifest; configs; baseline csqtt dhcp firewall network
    checkpoint applying
    /usr/libexec/csqtt/manage apply >> "$STATE/apply.private.log" 2>&1 || fail native_apply
    ready
    checkpoint applied
}
restore_startup() {
    pending; no_writer; manifest; configs; ready
    checkpoint starting
    if ! init_links >/dev/null 2>&1; then /etc/init.d/csqtt enable || fail startup_enable; fi
    init_links
    if ! /etc/init.d/csqtt running >/dev/null 2>&1; then
        /etc/init.d/csqtt start || fail transport_start
        ready
    fi
}
recover() {
    private "$STATE/armed" f || fail not_armed
    if [ -e "$STATE/finished" ]; then [ "$(cat "$STATE/finished")" = CSQTT-BOOT7 ] || fail finished_identity; return 0; fi
    mkdir "$STATE/recovery.lock" 2>/dev/null || fail recovery_writer_or_stale_lock
    START=$(ticks "$$"); case "$START" in ''|*[!0-9]*) fail process_identity ;; esac
    printf '%s\n' "$$" > "$STATE/recovery.lock/pid"; printf '%s\n' "$START" > "$STATE/recovery.lock/startticks"; LOCKED=1
    pending; no_writer; manifest; configs
    case "$PHASE" in
        applied|starting|complete) if ! ready_test; then apply_baseline; fi ;;
        applying) apply_baseline ;;
        ''|restoring)
            case "$STAGE" in
                files|fault|apply|failed) closed ;;
                *) full_files || fail early_policy_missing ;;
            esac
            if [ "$CHANGED" = 0 ] && ready_test; then
                # An early abort with the healthy original policy needs no apply.
                checkpoint applied
            else
                checkpoint restoring
                case "$STAGE" in fault|apply|failed) fault ;; esac
                pending; no_writer; manifest; configs
                for config in csqtt firewall; do
                    if ! cmp -s "$STATE/baseline/$config" "/etc/config/$config"; then
                        atomic_config "$config"
                        # Each interruption leaves only exact baseline/fixture bytes.
                        pending; no_writer; manifest; configs
                    fi
                done
                baseline csqtt dhcp firewall network
                apply_baseline
            fi ;;
    esac
    restore_startup
    checkpoint complete
    drop_lock || fail recovery_lock_identity
    printf 'CSQTT-BOOT7\n' > "$STATE/finished"
}
case "$MODE" in check|recover|watchdog|init-template) ;; *) fail mode ;; esac
inputs
case "$MODE" in
    check)
        manifest; pending; configs; no_writer
        if [ -e /etc/rc.d/S95csqtt ] || [ -L /etc/rc.d/S95csqtt ] || [ -e /etc/rc.d/K10csqtt ] || [ -L /etc/rc.d/K10csqtt ]; then init_links; fi
        nft -c -f "$STATE/closed.nft" >/dev/null 2>&1 || fail closed_syntax; printf 'recovery_check=true\n' ;;
    recover) LOGGING=1; trap finish EXIT; trap 'FAILURE=interrupted; exit 1' INT TERM; trap '' HUP; recover >> "$STATE/recovery.private.log" 2>&1 ;;
    watchdog)
        trap '' HUP; sleeper=
        trap '[ -z "$sleeper" ] || { kill -TERM "$sleeper" 2>/dev/null || true; wait "$sleeper" 2>/dev/null || true; }; exit 1' INT TERM
        sleep 120 & sleeper=$!; wait "$sleeper"; sleeper=
        if [ -e "$STATE/armed" ] && [ ! -e "$STATE/finished" ]; then exec sh "$STATE/recovery.sh" recover "$STATE"; fi ;;
    init-template)
        cat <<EOF
#!/bin/sh /etc/rc.common
START=20
STOP=9
start() {
    umask 077
    sh '$STATE/recovery.sh' watchdog '$STATE' >> '$STATE/watchdog.private.log' 2>&1 </dev/null &
}
EOF
        ;;
esac
