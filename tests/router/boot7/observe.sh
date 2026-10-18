#!/bin/sh
# Source-only actual-host LAN fixture. The controller owns UCI, fault injection,
# reboot and recovery. This helper creates only its reviewed synthetic objects.
# DNS ports are matched as a union because active policy redirects 53 to 5400
# before INPUT. Per-invocation counter deltas identify each requested port.
# No observer rule changes a verdict, packet mark or route selection.
set -eu
umask 077
export LC_ALL=C
MODE=${1:-}; STATE=${2:-}; PHASE=${3:-preboot}; FAILURE=unspecified
fail() { FAILURE=$1; printf 'observer_failed=%s\n' "$1" >&2; exit 1; }
private() {
    [ ! -L "$1" ] || return 1
    case "$2" in d) [ -d "$1" ] ;; f) [ -f "$1" ] ;; *) return 1 ;; esac || return 1
    ucode -e 'import * as fs from "fs"; let s=fs.stat(ARGV[0]); if(!s || s.uid!==0 || (s.mode & 63)!==0) exit(1);' "$1" 2>/dev/null
}
inputs() {
    [ "$(id -u)" = 0 ] || fail root_required
    case "$MODE" in setup|positive|blocked|cleanup) ;; *) fail mode ;; esac
    case "$PHASE" in preboot|postboot) ;; *) fail phase ;; esac
    printf '%s\n' "$STATE" | grep -Eq '^/etc/csqtt/backups/boot7-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$' || fail state_path
    for path in /etc/csqtt /etc/csqtt/backups "$STATE"; do private "$path" d || fail state_directory; done
    for path in identity fixture.env probe-linux-arm64; do private "$STATE/$path" f || fail state_file; done
    [ "$(cat "$STATE/identity")" = CSQTT-BOOT7 ] && [ -x "$STATE/probe-linux-arm64" ] || fail state_identity
    seen=' '; count=0
    while IFS= read -r line || [ -n "$line" ]; do
        printf '%s\n' "$line" | grep -Eq "^[A-Z_]+='[A-Za-z0-9_.:/-]+'$" || fail fixture_literal
        key=${line%%=*}
        case "$key" in LAN|SERVER|GROUP|MAC|FREE_MAC|NS|FREE_NS|HOST|PEER|FREE_HOST|FREE_PEER|TABLE|ROUTER_IP|CLIENT_IP|FREE_IP|PREFIX|DNS_PORT) ;; *) fail fixture_key ;; esac
        case "$seen" in *" $key "*) fail fixture_duplicate ;; esac
        seen="$seen$key "; count=$((count+1))
    done < "$STATE/fixture.env"
    [ "$count" = 17 ] || fail fixture_incomplete
    # The whitelist and literal grammar above exclude commands and expansions.
    . "$STATE/fixture.env"
    [ "$LAN" = br-lan ] && [ "$NS" = cqboot7p ] && [ "$FREE_NS" = cqboot7u ] &&
        [ "$HOST" = cqboot7hp ] && [ "$PEER" = cqboot7pp ] && [ "$FREE_HOST" = cqboot7hu ] &&
        [ "$FREE_PEER" = cqboot7pu ] && [ "$TABLE" = cq_boot7 ] || fail fixture_object_names
    [ "$ROUTER_IP" = 198.19.7.1 ] && [ "$CLIENT_IP" = 198.19.7.2 ] &&
        [ "$FREE_IP" = 198.19.7.3 ] && [ "$PREFIX" = 198.19.7.0/29 ] || fail fixture_prefix
    [ "$DNS_PORT" = 5400 ] || fail probe_port_unsupported
    printf '%s\n' "$GROUP" | grep -Eq '^[A-Za-z0-9_]+$' || fail group_name
    for value in "$MAC" "$FREE_MAC"; do printf '%s\n' "$value" | grep -Eq '^02(:[0-9a-f]{2}){5}$' || fail fixture_mac; done
    [ "$MAC" != "$FREE_MAC" ] || fail duplicate_mac
    ucode -e 'let p=split(ARGV[0],"."); if(length(p)!==4) exit(1); for(let x in p) if(!match(x,/^[0-9]{1,3}$/) || +x>255 || ""+(+x)!==x) exit(1);' "$SERVER" 2>/dev/null || fail server_ipv4
    TAG=CSQTT-BOOT7-OBSERVE-${STATE##*/}
    for path in "$STATE"/observer.* "$STATE"/observe-*; do
        [ -e "$path" ] || { [ ! -L "$path" ] || fail output_symlink; continue; }
        private "$path" f || fail observer_file
    done
    hash=$(sha256sum "$STATE/fixture.env"); hash=${hash%% *}
    if [ -e "$STATE/observer.fixture.hash" ]; then
        [ "$(cat "$STATE/observer.fixture.hash")" = "$hash" ] || fail fixture_changed
    else
        [ "$MODE" = setup ] || fail fixture_unpinned
        printf '%s\n' "$hash" > "$STATE/observer.fixture.hash"
    fi
}
finish() {
    rc=$?; trap - EXIT INT TERM
    printf 'observer_ok=%s\n' "$([ "$rc" = 0 ] && printf true || printf false)" >> "$PUBLIC"
    [ "$rc" = 0 ] || printf 'observer_failure=%s\n' "$FAILURE" >> "$PUBLIC"
    printf '%s\n' "$rc" > "$STATE/observe-$MODE-$PHASE.exit"
    cat "$PUBLIC"
    exit "$rc"
}
owned_boot() { private "$STATE/observer.boot" f && cmp -s "$STATE/observer.boot" /proc/sys/kernel/random/boot_id || fail observer_boot_changed; }
phase_gate() {
    private "$STATE/observer.preboot.id" f || fail preboot_identity
    if [ "$PHASE" = preboot ]; then
        cmp -s "$STATE/observer.preboot.id" /proc/sys/kernel/random/boot_id || fail unexpected_boot
    else
        ! cmp -s "$STATE/observer.preboot.id" /proc/sys/kernel/random/boot_id || fail actual_reboot_required
        private "$STATE/observer.postboot.id" f && cmp -s "$STATE/observer.postboot.id" /proc/sys/kernel/random/boot_id || fail postboot_identity
    fi
}
uci_membership() {
    ucode -e '
import { cursor } from "uci";
let c=cursor(), group=ARGV[0], mac=ARGV[1], free=ARGV[2], n=0, capable=false;
if(c.get("csqtt",group)!=="group") exit(1);
capable=c.get("csqtt",group,"default_action")==="vpn";
c.foreach("csqtt","rule",function(s){ if(s.group===group && s.enabled!=="0" && s.action==="vpn") capable=true; });
c.foreach("csqtt","device",function(s){
 let m=lc(s.mac || ""); if(m===free) exit(1);
 if(m===mac) { if(s.group!==group || s.enabled==="0") exit(1); n++; }
});
let lans=c.get("csqtt","main","lan_device") || "br-lan";
if(type(lans)!=="array") lans=[lans]; let lan=false; for(let x in lans) if(x==="br-lan") lan=true;
if(!capable || !lan || n!==1) exit(1);
' "$GROUP" "$MAC" "$FREE_MAC" || fail synthetic_membership
}
table_owned() {
    nft -j list table inet "$TABLE" > "$STATE/observer.table.private.json" || return 1
    ucode -e 'import * as fs from "fs"; let d=json(fs.readfile(ARGV[0])), n=0; for(let r in d.nftables || []) if(r.table) { if(r.table.family!=="inet" || r.table.name!==ARGV[1] || r.table.comment!==ARGV[2]) exit(1); n++; } if(n!==1) exit(1);' "$STATE/observer.table.private.json" "$TABLE" "$TAG"
}
host_identity() {
    for field in ifindex address ifalias; do cat "/sys/class/net/$1/$field" || return 1; done
}
namespace_inode() { ucode -e 'import * as fs from "fs"; let s=fs.stat(ARGV[0]); if(!s) exit(1); printf("%d\n",s.ino);' "/var/run/netns/$1"; }
objects_absent() {
    for name in "$NS" "$FREE_NS"; do [ ! -e "/var/run/netns/$name" ] && [ ! -L "/var/run/netns/$name" ] || return 1; done
    for name in "$HOST" "$PEER" "$FREE_HOST" "$FREE_PEER"; do [ ! -e "/sys/class/net/$name" ] || return 1; done
    ! nft list table inet "$TABLE" >/dev/null 2>&1 || return 1
    ip -4 addr show dev "$LAN" | grep -q " $ROUTER_IP/29 " && return 1
    return 0
}
collision_checks() {
    objects_absent || fail fixture_collision
    ip -4 addr show > "$STATE/observer.addresses.private"
    ip -4 route show table all > "$STATE/observer.routes.private"
    ip -4 neigh show > "$STATE/observer.neighbors.private"
    ucode -e '
import * as fs from "fs";
import { cursor } from "uci";
function number(v) { let p=split(v,"."); if(length(p)!==4) return null; let n=0; for(let x in p) { if(!match(x,/^[0-9]{1,3}$/) || +x>255) return null; n=n*256+(+x); } return n; }
let low=number("198.19.7.0"), high=low+7, server=false;
for(let line in split(fs.readfile(ARGV[0]),"\n")) {
 let p=split(trim(line),/[[:space:]]+/); if(p[0]!=="inet") continue;
 let a=split(p[1],"/"), n=number(a[0]); if(a[0]===ARGV[2]) server=true;
 if(n!==null && n>=low && n<=high) exit(1);
}
if(!server) exit(1);
for(let path in [ARGV[3],"/tmp/dhcp.leases"]) for(let line in split(fs.readfile(path) || "","\n")) {
 let p=split(trim(line),/[[:space:]]+/), n=number(path===ARGV[3] ? p[0] : p[2] || "");
 if(n!==null && n>=low && n<=high) exit(1);
}
let c=cursor(); c.foreach("dhcp","host",function(s) { let ips=type(s.ip)==="array" ? s.ip : [s.ip || ""]; for(let ip in ips) { let n=number(ip); if(n!==null && n>=low && n<=high) exit(1); } });
for(let line in split(fs.readfile(ARGV[1]),"\n")) {
 let p=split(trim(line),/[[:space:]]+/); if(p[0]==="unreachable" || p[0]==="blackhole" || p[0]==="prohibit" || p[0]==="local" || p[0]==="broadcast") shift(p);
 let a=split(p[0] || "","/"), n=number(a[0]); if(n===null) continue;
 let bits=length(a)===1 ? 32 : +a[1]; if(bits===0) continue; if(bits<0 || bits>32) exit(1);
 let size=1 << (32-bits), start=n-(n%size); if(start<=high && start+size-1>=low) exit(1);
}
' "$STATE/observer.addresses.private" "$STATE/observer.routes.private" "$SERVER" "$STATE/observer.neighbors.private" || fail benchmark_or_server_collision
    for value in "$MAC" "$FREE_MAC"; do
        ! grep -iq "$value" "$STATE/observer.neighbors.private" || fail neighbor_mac_collision
        ! grep -iq "$value" /tmp/dhcp.leases || fail lease_mac_collision
        for path in /sys/class/net/*/address; do [ "$(cat "$path")" != "$value" ] || fail host_mac_collision; done
    done
    ip -4 addr show dev "$LAN" > "$STATE/observer.lan.private"
    ucode -e 'import * as fs from "fs"; let ok=false; for(let line in split(fs.readfile(ARGV[0]),"\n")) { let p=split(trim(line),/[[:space:]]+/); if(p[0]==="inet" && split(p[1],"/")[0]===ARGV[1]) ok=true; } if(!ok) exit(1);' "$STATE/observer.lan.private" "$SERVER" || fail server_not_lan
}
client_setup() {
    kind=$1; ns=$2; host=$3; peer=$4; address=$5; mac=$6
    ip netns add "$ns" || fail namespace_create
    namespace_inode "$ns" > "$STATE/observer.$kind.ns.ino" || fail namespace_identity
    ip link add "$host" alias "$TAG:$kind" type veth peer name "$peer" address "$mac" || fail link_create
    host_identity "$host" > "$STATE/observer.$kind.link" || fail link_identity
    ip link set "$peer" netns "$ns"; ip link set "$host" master "$LAN"; ip link set "$host" up
    ip -n "$ns" link set lo up; ip -n "$ns" addr add "$address/29" dev "$peer"; ip -n "$ns" link set "$peer" up
    ip -n "$ns" route add default via "$ROUTER_IP"
}
setup() {
    uci_membership
    if [ -e "$STATE/observer.boot" ]; then
        ! cmp -s "$STATE/observer.boot" /proc/sys/kernel/random/boot_id || fail existing_fixture
        objects_absent || fail stale_fixture_objects
        rm -f "$STATE/observer.p.ns.ino" "$STATE/observer.u.ns.ino" "$STATE/observer.p.link" "$STATE/observer.u.link" "$STATE/observer.alias" "$STATE/observer.table"
    fi
    if [ "$PHASE" = preboot ]; then
        [ ! -e "$STATE/observer.preboot.id" ] || cmp -s "$STATE/observer.preboot.id" /proc/sys/kernel/random/boot_id || fail preboot_already_recorded
        cp /proc/sys/kernel/random/boot_id "$STATE/observer.preboot.id"
    else
        private "$STATE/observer.preboot.id" f && ! cmp -s "$STATE/observer.preboot.id" /proc/sys/kernel/random/boot_id || fail actual_reboot_required
        [ ! -e "$STATE/observer.postboot.id" ] || cmp -s "$STATE/observer.postboot.id" /proc/sys/kernel/random/boot_id || fail extra_reboot
        cp /proc/sys/kernel/random/boot_id "$STATE/observer.postboot.id"
    fi
    collision_checks
    cp /proc/sys/kernel/random/boot_id "$STATE/observer.boot"
    client_setup p "$NS" "$HOST" "$PEER" "$CLIENT_IP" "$MAC"
    client_setup u "$FREE_NS" "$FREE_HOST" "$FREE_PEER" "$FREE_IP" "$FREE_MAC"
    ip -4 addr add "$ROUTER_IP/29" dev "$LAN" label "$LAN:b7" || fail alias_create
    printf '%s\n' "$TAG" > "$STATE/observer.alias"
    cat > "$STATE/observer.counters.nft" <<EOF
add table inet $TABLE { comment "$TAG"; }
add chain inet $TABLE input_pre { type filter hook input priority -21; }
add chain inet $TABLE input_post { type filter hook input priority -19; }
add chain inet $TABLE forward_pre { type filter hook forward priority -21; }
add chain inet $TABLE forward_post { type filter hook forward priority -19; }
EOF
    for family in p u; do
        source_ip=$CLIENT_IP; source_mac=$MAC
        [ "$family" = p ] || { source_ip=$FREE_IP; source_mac=$FREE_MAC; }
        for protocol in udp tcp; do
            for side in pre post; do
                printf 'add counter inet %s %s_%s_%s\n' "$TABLE" "$family" "$protocol" "$side" >> "$STATE/observer.counters.nft"
                printf 'add rule inet %s input_%s iifname "%s" ether saddr %s ip saddr %s ip daddr %s meta l4proto %s th dport { 53, 5400 } counter name %s_%s_%s\n' "$TABLE" "$side" "$LAN" "$source_mac" "$source_ip" "$SERVER" "$protocol" "$family" "$protocol" "$side" >> "$STATE/observer.counters.nft"
            done
        done
    done
    for side in pre post; do
        printf 'add counter inet %s p_forward_%s\nadd rule inet %s forward_%s iifname "%s" ether saddr %s ip saddr %s ip daddr 8.8.8.8 tcp dport 443 counter name p_forward_%s\n' "$TABLE" "$side" "$TABLE" "$side" "$LAN" "$MAC" "$CLIENT_IP" "$side" >> "$STATE/observer.counters.nft"
    done
    nft -c -f "$STATE/observer.counters.nft" && nft -f "$STATE/observer.counters.nft" || fail passive_counters_create
    printf '%s\n' "$TAG" > "$STATE/observer.table"
    table_owned || fail passive_table_identity
    printf 'observer_setup=true\n' >> "$PUBLIC"
}
guard_gate() {
    for chain in maintenance_dns maintenance_guard; do
        hook=input; [ "$chain" != maintenance_guard ] || hook=forward
        nft -j list chain inet csqtt "$chain" > "$STATE/observer.guard.private.json" || fail product_guard_missing
        ucode -e '
import * as fs from "fs";
function mentions(v) { if(type(v)==="string") return lc(v)===ARGV[3]; if(type(v)==="array") for(let x in v) { if(mentions(x)) return true; } else if(type(v)==="object") for(let k in v) { if(mentions(v[k])) return true; } return false; }
let d=json(fs.readfile(ARGV[0])), n=0, rules=0, member=false;
for(let r in d.nftables || []) { if(r.chain) { let c=r.chain; if(c.family!=="inet" || c.table!=="csqtt" || c.name!==ARGV[1] || c.hook!==ARGV[2] || c.type!=="filter" || c.prio!==-20) exit(1); n++; } if(r.rule) { rules++; if(mentions(r.rule.expr)) member=true; } }
if(n!==1 || (ARGV[4]==="blocked" ? (!rules || !member) : rules!==0)) exit(1);
' "$STATE/observer.guard.private.json" "$chain" "$hook" "$MAC" "$MODE" || fail product_guard_state
    done
}
snapshot() {
    table_owned || return 1
    nft -j list table inet "$TABLE" > "$STATE/observe-$1.private.json" || return 1
    ucode -e 'import * as fs from "fs"; let d=json(fs.readfile(ARGV[0])), counts={}; for(let r in d.nftables || []) if(r.counter) { let c=r.counter; if(c.family!=="inet" || c.table!==ARGV[1] || type(c.packets)!=="int" || c.packets<0 || c.packets>1000000 || counts[c.name]!=null) exit(1); counts[c.name]=c.packets; } for(let k in [ARGV[2],ARGV[3]]) { if(counts[k]==null) exit(1); printf("%d ",counts[k]); }' "$STATE/observe-$1.private.json" "$TABLE" "$2" "$3"
}
dns_probe() {
    label=$1; ns=$2; protocol=$3; port=$4; expect=$5; family=$6
    values=$(snapshot "$PHASE-$MODE-$label-before" "${family}_${protocol}_pre" "${family}_${protocol}_post") || fail counter_snapshot
    set -- $values; pre0=$1; post0=$2
    ip netns exec "$ns" "$STATE/probe-linux-arm64" -server "$SERVER" -port "$port" -protocol "$protocol" -name example.com -expect "$expect" > "$STATE/observe-$PHASE-$MODE-$label.probe.json" || fail dns_probe_result
    values=$(snapshot "$PHASE-$MODE-$label-after" "${family}_${protocol}_pre" "${family}_${protocol}_post") || fail counter_snapshot
    set -- $values; before=$(( $1-pre0 )); after=$(( $2-post0 ))
    [ "$before" -gt 0 ] || fail actual_dns_ingress_missing
    if [ "$expect" = blocked ]; then [ "$after" = 0 ] || fail protected_dns_passed_guard; else [ "$after" -gt 0 ] || fail dns_control_passed_no_guard; fi
    ucode -e 'import * as fs from "fs"; let d=json(fs.readfile(ARGV[0])); if(d.config_valid!==true || d.connection_attempted!==true || d.probe_attempts!==1 || d.protocol!==ARGV[1] || d.port!==+ARGV[2] || d.expectation!==ARGV[3] || d.expectation_met!==true || d.standalone_blocking_proof!==false) exit(1); if(ARGV[3]==="answer") { if(d.valid_answer!==true || d.answer_count<1 || d.queries_written!==1) exit(1); } else if(d.no_dns_reply!==true || d.dns_reply_received!==false || d.valid_answer!==false || d.blocked_candidate!==true || d.bytes_received!==0 || d.requires_ingress_counter_proof!==true) exit(1);' "$STATE/observe-$PHASE-$MODE-$label.probe.json" "$protocol" "$port" "$expect" || fail dns_probe_evidence
    printf '%s_ingress=%s\n%s_after_guard=%s\n%s_expected_result=true\n' "$label" "$before" "$label" "$after" "$label" >> "$PUBLIC"
}
probes() {
    owned_boot; phase_gate; uci_membership; guard_gate
    if [ "$MODE" = blocked ]; then
        private "$STATE/observe-positive-preboot.ok" f && [ "$(cat "$STATE/observe-positive-preboot.ok")" = CSQTT-BOOT7-POSITIVE ] || fail positive_control_missing
        if [ "$PHASE" = postboot ]; then private "$STATE/observe-blocked-preboot.ok" f && [ "$(cat "$STATE/observe-blocked-preboot.ok")" = CSQTT-BOOT7-BLOCKED ] || fail preboot_blocked_proof_missing; fi
    fi
    protected_expect=answer; [ "$MODE" != blocked ] || protected_expect=blocked
    for protocol in udp tcp; do
        dns_probe "protected_${protocol}53" "$NS" "$protocol" 53 "$protected_expect" p
        dns_probe "protected_${protocol}5400" "$NS" "$protocol" "$DNS_PORT" "$protected_expect" p
        dns_probe "unassigned_${protocol}53" "$FREE_NS" "$protocol" 53 answer u
    done
    ip netns exec "$FREE_NS" curl -4 --noproxy '*' --fail --silent --show-error --connect-timeout 1 --max-time 3 "http://$SERVER/" > "$STATE/observe-$PHASE-$MODE-http.private" || fail unassigned_lan_http
    printf 'unassigned_lan_http=true\n' >> "$PUBLIC"
    values=$(snapshot "$PHASE-$MODE-forward-before" p_forward_pre p_forward_post) || fail counter_snapshot
    set -- $values; pre0=$1; post0=$2; forward_rc=0
    ip netns exec "$NS" curl -4 --noproxy '*' --silent --show-error --connect-timeout 1 --max-time 2 http://8.8.8.8:443/ > "$STATE/observe-$PHASE-$MODE-forward.private" 2>&1 || forward_rc=$?
    values=$(snapshot "$PHASE-$MODE-forward-after" p_forward_pre p_forward_post) || fail counter_snapshot
    set -- $values; before=$(( $1-pre0 )); after=$(( $2-post0 ))
    [ "$before" -gt 0 ] || fail actual_forward_ingress_missing
    if [ "$MODE" = blocked ]; then [ "$after" = 0 ] && [ "$forward_rc" != 0 ] || fail protected_forward_passed_guard; else [ "$after" -gt 0 ] || fail forward_control_missing; fi
    printf 'protected_forward_ingress=%s\nprotected_forward_after_guard=%s\n' "$before" "$after" >> "$PUBLIC"
    printf 'CSQTT-BOOT7-%s\n' "$([ "$MODE" = positive ] && printf POSITIVE || printf BLOCKED)" > "$STATE/observe-$MODE-$PHASE.ok"
}
client_cleanup_check() {
    kind=$1; ns=$2; host=$3
    if [ -e "/sys/class/net/$host" ]; then
        private "$STATE/observer.$kind.link" f || fail cleanup_link_unowned
        host_identity "$host" > "$STATE/observer.link.current"
        cmp -s "$STATE/observer.link.current" "$STATE/observer.$kind.link" || fail cleanup_link_changed
    fi
    if [ -e "/var/run/netns/$ns" ]; then
        private "$STATE/observer.$kind.ns.ino" f || fail cleanup_namespace_unowned
        [ "$(namespace_inode "$ns")" = "$(cat "$STATE/observer.$kind.ns.ino")" ] || fail cleanup_namespace_changed
        [ -z "$(ip netns pids "$ns")" ] || fail cleanup_namespace_busy
    fi
}
cleanup() {
    if [ ! -e "$STATE/observer.boot" ]; then objects_absent || fail cleanup_unowned_objects; return 0; fi
    if ! cmp -s "$STATE/observer.boot" /proc/sys/kernel/random/boot_id; then
        objects_absent || fail cleanup_boot_changed_objects
    else
        client_cleanup_check p "$NS" "$HOST"; client_cleanup_check u "$FREE_NS" "$FREE_HOST"
        if nft list table inet "$TABLE" >/dev/null 2>&1; then
            private "$STATE/observer.table" f && [ "$(cat "$STATE/observer.table")" = "$TAG" ] && table_owned || fail cleanup_table_changed
        fi
        ip -4 addr show dev "$LAN" > "$STATE/observer.alias.current"
        alias_found=$(ucode -e 'import * as fs from "fs"; let n=0; for(let line in split(fs.readfile(ARGV[0]),"\n")) { let p=split(trim(line),/[[:space:]]+/); if(p[0]==="inet" && p[1]===ARGV[1]+"/29") { if(p[length(p)-1]!=="br-lan:b7") exit(1); n++; } } if(n>1) exit(1); printf("%d",n);' "$STATE/observer.alias.current" "$ROUTER_IP") || fail cleanup_alias_changed
        if [ "$alias_found" = 1 ]; then private "$STATE/observer.alias" f && [ "$(cat "$STATE/observer.alias")" = "$TAG" ] || fail cleanup_alias_unowned; fi
        # Validate every existing object first; only then delete the captured objects.
        if nft list table inet "$TABLE" >/dev/null 2>&1; then nft delete table inet "$TABLE" || fail cleanup_table; fi
        for host in "$HOST" "$FREE_HOST"; do [ ! -e "/sys/class/net/$host" ] || ip link delete "$host" || fail cleanup_link; done
        for ns in "$NS" "$FREE_NS"; do [ ! -e "/var/run/netns/$ns" ] || ip netns delete "$ns" || fail cleanup_namespace; done
        [ "$alias_found" != 1 ] || ip -4 addr del "$ROUTER_IP/29" dev "$LAN" || fail cleanup_alias
    fi
    objects_absent || fail cleanup_incomplete
    rm -f "$STATE/observer.p.ns.ino" "$STATE/observer.u.ns.ino" "$STATE/observer.p.link" "$STATE/observer.u.link" "$STATE/observer.alias" "$STATE/observer.table" "$STATE/observer.boot"
    printf 'observer_cleanup=true\n' >> "$PUBLIC"
}
inputs
PUBLIC=$STATE/observe-$MODE-$PHASE.public.log
: > "$PUBLIC"
printf 'observer_mode=%s\nobserver_phase=%s\n' "$MODE" "$PHASE" >> "$PUBLIC"
trap finish EXIT; trap 'FAILURE=interrupted; exit 1' INT TERM
case "$MODE" in setup) setup ;; positive|blocked) probes ;; cleanup) cleanup ;; esac >> "$STATE/observe-$MODE-$PHASE.private.log" 2>&1
