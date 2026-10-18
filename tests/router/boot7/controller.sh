#!/bin/sh
# Test-only real-host orchestration. Native apply/recovery owns guard release.
set -eu
umask 077
MODE=${1:-}; STATE=${2:-}; OWN_LOCK=0
fail() { printf 'boot_controller_failure=%s\n' "$1" >&2; exit 1; }
printf '%s\n' "$STATE" | grep -Eq '^/etc/csqtt/backups/boot7-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$' || fail state_path
[ "$(id -u)" = 0 ] && [ -d "$STATE" ] && [ ! -L "$STATE" ] || fail root_state
[ "$(cat "$STATE/identity")" = CSQTT-BOOT7 ] || fail identity
private() { [ -f "$1" ] && [ ! -L "$1" ] && ucode -e 'import * as fs from "fs"; let s=fs.stat(ARGV[0]); if(!s || s.uid!==0 || (s.mode & 63)!==0) exit(1);' "$1"; }
for p in controller.sh recovery.sh observe.sh fixture.env closed.nft fault-set armed.sha256; do private "$STATE/$p" || fail private_input; done
# Only the context generator writes these singlequoted, validated literals.
ucode -e '
import * as fs from "fs";
let data=fs.readfile(ARGV[0]), keys={};
for(let line in split(trim(data || ""),"\n")) {
 let m=match(line,/^([A-Z_]+)=\x27([A-Za-z0-9_.:\/-]+)\x27$/);
 if(!m || keys[m[1]]) exit(1); keys[m[1]]=true;
}
if(length(keys)!==17) exit(1);
' "$STATE/fixture.env" || fail fixture_literals
. "$STATE/fixture.env"
[ "$LAN" = br-lan ] && [ "$NS" = cqboot7p ] && [ "$FREE_NS" = cqboot7u ] && [ "$TABLE" = cq_boot7 ] || fail fixture_scope
pending() { for p in csqtt dhcp firewall network; do [ -z "$(uci -q changes "$p")" ] || fail owner_pending; done; }
baseline() { for p in csqtt dhcp firewall network; do cmp -s "$STATE/baseline/$p" "/etc/config/$p" || fail owner_changed; done; }
no_writer() { [ ! -e /var/lock/csqtt-policy ] && [ ! -L /var/lock/csqtt-policy ] || fail policy_writer; }
stage() { printf '%s\n' "$1" > "$STATE/stage.new"; mv "$STATE/stage.new" "$STATE/stage"; }
lock_policy() {
    no_writer; mkdir /var/lock/csqtt-policy
    printf '%s\n' "$$" > /var/lock/csqtt-policy/pid
    OWN_LOCK=1
}
unlock_policy() {
    [ "$OWN_LOCK" = 1 ] || return 0
    [ "$(cat /var/lock/csqtt-policy/pid)" = "$$" ] || fail policy_lock_identity
    rm /var/lock/csqtt-policy/pid; rmdir /var/lock/csqtt-policy; OWN_LOCK=0
}
finish() {
    rc=$?; trap - EXIT INT TERM
    if [ "$OWN_LOCK" = 1 ]; then unlock_policy || rc=1; fi
    printf '%s\n' "$rc" > "$STATE/controller-$MODE.exit"
    exit "$rc"
}
trap finish EXIT
trap 'exit 1' INT TERM
trap '' HUP
atomic_config() {
    p=$1; tmp=/etc/config/.boot7-controller-$p-$$
    [ ! -e "$tmp" ] && [ ! -L "$tmp" ] || fail staging_collision
    mode=$(ucode -e 'import * as fs from "fs"; printf("%o",fs.stat(ARGV[0]).mode & 511);' "/etc/config/$p")
    cp "$STATE/staged/$p" "$tmp"; chmod "$mode" "$tmp"; mv "$tmp" "/etc/config/$p"
}
pins() { sha256sum -c "$STATE/armed.sha256" > "$STATE/pins.private.log" 2>&1 || fail pins; }
links_disabled() { [ ! -e /etc/rc.d/S95csqtt ] && [ ! -L /etc/rc.d/S95csqtt ] && [ ! -e /etc/rc.d/K10csqtt ] && [ ! -L /etc/rc.d/K10csqtt ]; }
install_hook() {
    name=$1; template=$2
    [ ! -e "/etc/init.d/$name" ] && [ ! -L "/etc/init.d/$name" ] || fail hook_collision
    cp "$STATE/$template" "/etc/init.d/$name"; chmod 700 "/etc/init.d/$name"
    "/etc/init.d/$name" enable
}
closed_check() {
    cmp -s "$STATE/closed.nft" /etc/csqtt/hold.nft || fail hold_bytes
    [ "$(uci -q get firewall.csqtt_hold.path)" = /etc/csqtt/hold.nft ] || fail include
    [ "$(uci -q get firewall.csqtt_hold.csqtt_owned)" = 1 ] || fail include_owner
    for chain in maintenance_guard maintenance_dns; do
        nft -j list chain inet csqtt "$chain" | ucode -e 'import * as fs from "fs"; let d=json(fs.readfile("/dev/stdin")), n=0; for(let r in d.nftables || []) if(r.rule && r.rule.chain===ARGV[0]) n++; if(n<1) exit(1);' "$chain" || fail closed_chains
    done
}
failed_check() {
    pending; no_writer; links_disabled || fail startup_enabled
    for p in csqtt firewall; do cmp -s "$STATE/staged/$p" "/etc/config/$p" || fail fixture_config_changed; done
    for p in dhcp network; do cmp -s "$STATE/baseline/$p" "/etc/config/$p" || fail owner_config_changed; done
    for p in policy.json policy.nft forward.nft input.nft; do [ ! -e "/etc/csqtt/$p" ] && [ ! -L "/etc/csqtt/$p" ] || fail full_policy_present; done
    closed_check
    [ "$(cat /var/run/csqtt/policy.error)" = 'Generated firewall policy was rejected; clients remain guarded' ] || fail rejection_phase
}
case "$MODE" in
 prepare-fixture)
    [ ! -e "$STATE/armed" ] && [ ! -e "$STATE/staged" ] || fail previous_fixture
    pending; baseline; no_writer; pins
    sh "$STATE/recovery.sh" check "$STATE"
    mkdir -m 700 "$STATE/staged"
    for p in csqtt firewall; do cp "$STATE/baseline/$p" "$STATE/staged/$p"; chmod 600 "$STATE/staged/$p"; done
    uci -q get csqtt.cqboot7_device >/dev/null 2>&1 && fail section_collision
    cat >> "$STATE/staged/csqtt" <<EOF

config device 'cqboot7_device'
 option name 'Temporary boot acceptance'
 option mac '$MAC'
 option group '$GROUP'
 option enabled '1'
EOF
    sh "$STATE/recovery.sh" init-template "$STATE" > "$STATE/recovery.init"
    sh "$STATE/controller.sh" boot-template "$STATE" > "$STATE/observer.init"
    chmod 600 "$STATE/recovery.init" "$STATE/observer.init"
    sha256sum "$STATE/staged/csqtt" "$STATE/staged/firewall" "$STATE/recovery.init" "$STATE/observer.init" >> "$STATE/armed.sha256"
    stage prepared
    echo exact_fixture_prepared_unarmed=true
    ;;
 arm)
    pending; baseline; no_writer; pins
    [ "$(cat "$STATE/stage")" = prepared ] && [ ! -e "$STATE/armed" ] || fail arm_phase
    sh "$STATE/recovery.sh" check "$STATE"
    install_hook cqboot7-recovery recovery.init
    install_hook cqboot7-observe observer.init
    cat /proc/sys/kernel/random/boot_id > "$STATE/boot.before.id"
    stage armed
    printf 'CSQTT-BOOT7\n' > "$STATE/armed"
    sh "$STATE/recovery.sh" watchdog "$STATE" > "$STATE/watchdog.private.log" 2>&1 </dev/null &
    pid=$!; printf '%s\n' "$pid" > "$STATE/watchdog.pid"
    sed -n 's/^[0-9][0-9]* (.*) //p' "/proc/$pid/stat" | awk '{print $20}' > "$STATE/watchdog.startticks"
    echo persistent_recovery_armed=true
    ;;
 assign)
    [ "$(cat "$STATE/stage")" = armed ] && [ ! -e "$STATE/finished" ] || fail assign_phase
    pending; baseline; no_writer; pins
    stage config; lock_policy; atomic_config csqtt; unlock_policy
    /usr/libexec/csqtt/manage apply > "$STATE/assign.private.log" 2>&1 || fail fixture_apply
    for p in csqtt firewall; do cmp -s "$STATE/staged/$p" "/etc/config/$p" || fail unexpected_fixture_bytes; done
    ucode /usr/share/csqtt/runtime.uc dns-ready || fail fixture_dns_ready
    echo synthetic_assignment_applied=true
    ;;
 fault)
    [ "$(cat "$STATE/stage")" = config ] && [ ! -e "$STATE/finished" ] || fail fault_phase
    pending; no_writer
    for p in csqtt firewall; do cmp -s "$STATE/staged/$p" "/etc/config/$p" || fail changed_fixture; done
    stage startup; /etc/init.d/csqtt disable; links_disabled || fail disable
    stage hold; lock_policy
    cp "$STATE/closed.nft" /etc/csqtt/hold.nft.new; chmod 600 /etc/csqtt/hold.nft.new; mv /etc/csqtt/hold.nft.new /etc/csqtt/hold.nft
    ucode /usr/share/csqtt/runtime.uc firewall-hold > "$STATE/hold.private.log" 2>&1 || fail hold_include
    nft -f /etc/csqtt/hold.nft > "$STATE/hold-nft.private.log" 2>&1 || fail hold_load
    closed_check
    mkdir -m 700 "$STATE/full.before"
    stage files
    for p in policy.json policy.nft forward.nft input.nft; do
        private "/etc/csqtt/$p" || fail full_before
        mv "/etc/csqtt/$p" "$STATE/full.before/$p"
    done
    setname=$(cat "$STATE/fault-set")
    printf '%s\n' "$setname" | grep -Eq '^d_[A-Za-z0-9_]+_[0-9]+$' || fail fault_name
    {
        printf 'delete table inet csqtt\n'
        cat "$STATE/closed.nft"
        printf 'add set inet csqtt %s { type ipv6_addr; }\n' "$setname"
    } > "$STATE/fault.nft"
    nft -c -f "$STATE/fault.nft" > "$STATE/fault-check.private.log" 2>&1 || fail fault_syntax
    stage fault; nft -f "$STATE/fault.nft" > "$STATE/fault-load.private.log" 2>&1 || fail fault_load
    if nft list flowtable inet fw4 ft >/dev/null 2>&1; then nft flush flowtable inet fw4 ft; fi
    unlock_policy
    stage apply
    if /usr/libexec/csqtt/manage apply > "$STATE/rejected-apply.private.log" 2>&1; then fail no_genuine_rejection; fi
    failed_check; stage failed
    echo genuine_failed_first_apply_guarded=true
    ;;
 before-boot)
    [ "$(cat "$STATE/stage")" = failed ] && [ ! -e "$STATE/finished" ] || fail boot_phase
    failed_check
    sh "$STATE/observe.sh" blocked "$STATE" preboot
    echo ready_for_actual_reboot=true
    ;;
 after-boot)
    # Always attempt persistent recovery after the bounded observer, even on FAIL.
    result=1
    if [ "$(cat "$STATE/stage")" = failed ] && [ ! -e "$STATE/finished" ] &&
        ! cmp -s "$STATE/boot.before.id" /proc/sys/kernel/random/boot_id; then
        if sh "$STATE/observe.sh" blocked "$STATE" postboot > "$STATE/boot-observe.public.log" 2> "$STATE/boot-observe.private.log"; then result=0; fi
    fi
    printf '%s\n' "$result" > "$STATE/boot-observe.exit"
    sh "$STATE/recovery.sh" recover "$STATE" || fail boot_recovery
    exit "$result"
    ;;
 boot-template)
    cat <<EOF
#!/bin/sh /etc/rc.common
START=90
STOP=9
start() {
    umask 077
    sh '$STATE/controller.sh' after-boot '$STATE' > '$STATE/boot-controller.private.log' 2>&1
    return 0
}
EOF
    ;;
 cleanup-hooks)
    [ "$(cat "$STATE/finished")" = CSQTT-BOOT7 ] || fail recovery_incomplete
    pending; baseline; no_writer
    for pair in 'cqboot7-recovery recovery.init' 'cqboot7-observe observer.init'; do
        set -- $pair; name=$1; template=$2
        cmp -s "$STATE/$template" "/etc/init.d/$name" || fail hook_changed
        "/etc/init.d/$name" disable
        rm "/etc/init.d/$name"
    done
    if [ -f "$STATE/watchdog.pid" ] && [ -f "$STATE/watchdog.startticks" ]; then
        pid=$(cat "$STATE/watchdog.pid"); case "$pid" in ''|*[!0-9]*) fail watchdog_pid ;; esac
        if [ -f "/proc/$pid/stat" ]; then
            ticks=$(sed -n 's/^[0-9][0-9]* (.*) //p' "/proc/$pid/stat" | awk '{print $20}')
            [ "$ticks" = "$(cat "$STATE/watchdog.startticks")" ] || fail watchdog_reused_pid
            grep -Fq "$STATE/recovery.sh" "/proc/$pid/cmdline" || fail watchdog_identity
            kill -TERM "$pid"
        fi
    fi
    echo only_owned_boot_hooks_removed=true
    ;;
 *) fail mode ;;
esac
