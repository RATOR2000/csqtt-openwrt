#!/bin/sh
# Destructive fixture test for a disposable stock OpenWrt x86 QEMU guest only.
# The driver installs the signed candidate first and destroys the guest later.
# No VK authentication, owner-router access, or qualification flags are written.
set -eu
umask 077
fail() { printf '%s\n' 'CSQTT guest smoke failed; inspect private guest diagnostics.' >&2; exit 1; }
stage() { printf 'CSQTT_GUEST_STAGE=%s\n' "$1"; }
stage prerequisites
stage prerequisites_uid
[ "$(id -u)" = 0 ] || fail
stage prerequisites_cpu
[ "$(uname -m)" = x86_64 ] || fail
stage prerequisites_hypervisor
cat /sys/class/dmi/id/product_name /sys/class/dmi/id/sys_vendor 2>/dev/null | grep -Eqi 'QEMU|Bochs|KVM' || fail
stage prerequisites_vendor
[ ! -f /etc/glversion ] || fail
stage prerequisites_release
. /etc/openwrt_release
case "${DISTRIB_RELEASE:-}" in 24.10.*|25.12.*) ;; *) fail ;; esac
stage prerequisites_tools
for tool in ucode uci ubus nft fw4 ip timeout nslookup sha256sum; do command -v "$tool" >/dev/null || { printf 'CSQTT_GUEST_MISSING_TOOL=%s\n' "$tool"; fail; }; done
stage prerequisites_enabled
[ "$(uci -q get csqtt.main.enabled)" = 0 ] || fail
stage prerequisites_auto_recover
[ "$(uci -q get csqtt.main.auto_recover)" = 0 ] || fail
stage prerequisites_workers
[ "$(uci -q get csqtt.main.workers)" = auto ] || fail
stage prerequisites_ucode_absence
[ ! -x /usr/libexec/csqtt/ucode ] || fail
stage prerequisites_dns_features
DNS=/usr/sbin/dnsmasq
[ ! -x /usr/libexec/csqtt/dnsmasq ] || DNS=/usr/libexec/csqtt/dnsmasq
"$DNS" --version | grep -Eq '(^|[[:space:]])nftset([[:space:]]|$)' || fail
TMP=$(mktemp -d /tmp/csqtt-guest-smoke.XXXXXX)
PIDS=
MUTATED=0
DNS_STOPPED=0
FINISHED=0
LAN_CREATED=0
for config in csqtt dhcp firewall network; do cp -p "/etc/config/$config" "$TMP/$config"; done
sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network > "$TMP/config.sha256"
cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    for pid in $PIDS; do kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; done
    if [ "$DNS_STOPPED" = 1 ]; then /etc/init.d/dnsmasq start > "$TMP/restore-dns.log" 2>&1 || status=1; fi
    if [ "$MUTATED" = 1 ]; then
        /usr/libexec/csqtt/manage deactivate > "$TMP/deactivate.log" 2>&1 || status=1
        for config in csqtt dhcp firewall network; do cp -p "$TMP/$config" "/etc/config/$config" || status=1; done
        rm -f /etc/csqtt/deactivated
        ubus call network reload > "$TMP/restore-network.log" 2>&1 || status=1
        fw4 reload > "$TMP/restore-firewall.log" 2>&1 || status=1
    fi
    if [ "$LAN_CREATED" = 1 ] && ip link show dev br-csqtt-test >/dev/null 2>&1; then
        ip link del br-csqtt-test > "$TMP/remove-lan.log" 2>&1 || status=1
    fi
    nft delete table inet csqtt_guest_dns 2>/dev/null
    ip -4 addr del 198.19.0.1/32 dev lo 2>/dev/null
    ip -4 addr del 198.19.0.2/32 dev lo 2>/dev/null
    if ! sha256sum -c "$TMP/config.sha256" > "$TMP/restore-check.log" 2>&1; then status=1; fi
    [ "$FINISHED" = 1 ] || status=1
    if [ "$status" = 0 ]; then printf '%s\n' CSQTT_GUEST_SMOKE_PASS; fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

# Import the actual installed filesystem modules using this firmware's ucode.
stage native_imports
cat > "$TMP/import.uc" <<'UCODE'
import { compile, hold } from '/usr/share/csqtt/policy.uc';
import { health_assess, health_initial, health_advance, health_reserve, health_complete, health_public } from '/usr/share/csqtt/health.uc';
let policy = compile({ main: { lan_device: ['br-lan'] }, groups: [{ id: 'guest', default_action: 'vpn' }],
    devices: [{ id: 'guestpc', mac: '02:00:00:00:aa:01', group: 'guest' }] });
if (!policy.active || index(policy.nft, 'oifname != "csqtt0" reject') < 0 || index(policy.nft, 'meta nfproto ipv6') < 0)
    die('Native policy guards missing');
if (index(hold([policy.model], true), 'maintenance_dns') < 0) die('Native DNS hold missing');
if (type(health_assess) !== 'function' || type(health_initial) !== 'function' || type(health_advance) !== 'function' || type(health_reserve) !== 'function' ||
    type(health_complete) !== 'function' || type(health_public) !== 'function') die('Native health exports missing');
UCODE
ucode "$TMP/import.uc" > "$TMP/import.log" 2>&1 || fail
/usr/libexec/csqtt/manage status > "$TMP/status.json" 2> "$TMP/status.log" || fail
jsonfilter -i "$TMP/status.json" -e '@.setup_required' | grep -qx true || fail
jsonfilter -i "$TMP/status.json" -e '@.running' | grep -qx false || fail
/usr/libexec/rpcd/csqtt list > "$TMP/rpc.json" || fail
for method in status devices start stop apply diagnostics captcha_begin captcha_cancel; do
    jsonfilter -i "$TMP/rpc.json" -e "@.$method" >/dev/null || fail
done
for asset in view/csqtt/setup.js view/csqtt/overview.js view/csqtt/settings.js view/csqtt/policies.js csqtt/api.js csqtt/model.js csqtt/style.css; do
    [ -s "/www/luci-static/resources/$asset" ] || fail
done
[ -s /usr/share/rpcd/acl.d/luci-app-csqtt.json ] || fail
[ -s /usr/share/luci/menu.d/luci-app-csqtt.json ] || fail
if [ -x /usr/libexec/csqtt/dnsmasq ]; then
    [ -s /usr/share/licenses/csqtt/dnsmasq-COPYING ] || fail
    [ -s /usr/share/licenses/csqtt/dnsmasq-NOTICE ] || fail
fi
timeout 10 wget -q -O "$TMP/luci-before" http://127.0.0.1/cgi-bin/luci/ || fail
[ -s "$TMP/luci-before" ] || fail

# Exercise dnsmasq forwarding into nftsets over both UDP and TCP, with a
# synthetic loopback upstream. No Internet or VK response can make this pass.
stage private_dns
DNS_STOPPED=1
/etc/init.d/dnsmasq stop > "$TMP/stop-dns.log" 2>&1 || fail
nft add table inet csqtt_guest_dns
nft 'add set inet csqtt_guest_dns answers { type ipv4_addr; }'
ip -4 addr add 198.19.0.1/32 dev lo
ip -4 addr add 198.19.0.2/32 dev lo
cat > "$TMP/upstream.conf" <<EOF
port=5401
listen-address=127.0.0.1
bind-interfaces
no-resolv
no-hosts
address=/example.com/198.51.100.77
address=/printer.lan/192.168.111.9
EOF
cat > "$TMP/group.conf" <<EOF
port=5400
listen-address=127.0.0.1
bind-interfaces
no-resolv
no-hosts
server=127.0.0.1#5401
nftset=/example.com/4#inet#csqtt_guest_dns#answers
EOF
cat > "$TMP/local.conf" <<EOF
port=53
listen-address=198.19.0.1
bind-interfaces
no-resolv
no-hosts
server=/lan/127.0.0.1#5401
EOF
for name in upstream group local; do
    "$DNS" --test --conf-file="$TMP/$name.conf" > "$TMP/$name-test.log" 2>&1 || fail
    "$DNS" --keep-in-foreground --conf-file="$TMP/$name.conf" > "$TMP/$name.log" 2>&1 &
    PIDS="$PIDS $!"
done
sleep 1
for pid in $PIDS; do kill -0 "$pid" || fail; done
# Endpoint DNS goes to an unused local address and fails promptly. Only the
# loopback group result is asserted; this is not a real VPN/Internet check.
printf '%s\n' '{"source_ipv4":"198.19.0.2","dns_ipv4":"198.19.0.2","group_ports":[5400]}' |
    timeout 12 /usr/bin/csqtt-client --health-probe wan > "$TMP/dns-probe.json" 2> "$TMP/dns-probe.log" || fail
jsonfilter -i "$TMP/dns-probe.json" -e '@.config_valid' | grep -qx true || fail
jsonfilter -i "$TMP/dns-probe.json" -e '@.completed' | grep -qx true || fail
jsonfilter -i "$TMP/dns-probe.json" -e '@.groups[0].udp' | grep -qx ok || fail
jsonfilter -i "$TMP/dns-probe.json" -e '@.groups[0].tcp' | grep -qx ok || fail
nft list set inet csqtt_guest_dns answers > "$TMP/nftset.txt"
grep -q '198.51.100.77' "$TMP/nftset.txt" || fail
timeout 5 nslookup -type=A printer.lan 198.19.0.1 > "$TMP/local-query.log" 2>&1 || fail
grep -q '192.168.111.9' "$TMP/local-query.log" || fail
for pid in $PIDS; do kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; done
PIDS=
/etc/init.d/dnsmasq start > "$TMP/start-dns.log" 2>&1 || fail
DNS_STOPPED=0

# The driver's DHCP interface is its WAN/SSH path. A separate real static LAN
# fixture exercises first-run auto discovery without misclassifying that path.
stage automatic_lan
MUTATED=1
[ -z "$(uci -q get network.csqtt_test || true)" ] || fail
[ -z "$(uci -q get firewall.csqtt_test || true)" ] || fail
ip link add br-csqtt-test type bridge || fail
LAN_CREATED=1
ip link set br-csqtt-test up || fail
uci set network.csqtt_test=interface
uci set network.csqtt_test.proto=static
uci set network.csqtt_test.device=br-csqtt-test
uci set network.csqtt_test.ipaddr=192.168.111.1
uci set network.csqtt_test.netmask=255.255.255.0
uci set firewall.csqtt_test=zone
uci set firewall.csqtt_test.name=csqtt_test
uci set firewall.csqtt_test.input=ACCEPT
uci set firewall.csqtt_test.output=ACCEPT
uci set firewall.csqtt_test.forward=REJECT
uci add_list firewall.csqtt_test.network=csqtt_test
uci commit network
uci commit firewall
ubus call network reload > "$TMP/fixture-network.log" 2>&1 || fail
scope_ready=0
for n in 1 2 3 4 5; do
    /usr/libexec/csqtt/manage devices > "$TMP/devices.json" 2> "$TMP/devices.log" || fail
    if jsonfilter -i "$TMP/devices.json" -e '@.lan_devices[*]' | grep -qx br-csqtt-test; then scope_ready=1; break; fi
    sleep 1
done
[ "$scope_ready" = 1 ] || fail
! jsonfilter -i "$TMP/devices.json" -e '@.lan_devices[*]' | grep -qx br-lan || fail
/usr/libexec/csqtt/manage helper-address > "$TMP/helper-address" 2> "$TMP/helper.log" || fail
grep -qx 192.168.111.1 "$TMP/helper-address" || fail

# Production apply, procd DNS ownership, fw4 reload and policy Stop. The sole
# synthetic MAC is never the guest management interface. Transport stays off.
stage guarded_apply
uci set csqtt.guest=group
uci set csqtt.guest.name=Guest
uci set csqtt.guest.default_action=vpn
uci set csqtt.guestpc=device
uci set csqtt.guestpc.mac=02:00:00:00:aa:01
uci set csqtt.guestpc.group=guest
uci commit csqtt
timeout 60 /usr/libexec/csqtt/manage apply > "$TMP/apply.log" 2>&1 || fail
ucode /usr/share/csqtt/runtime.uc dns-ready > "$TMP/dns-ready.log" 2>&1 || fail
guard_checks() {
    nft list table inet csqtt > "$TMP/guards.txt"
    grep -q 'oifname != "csqtt0" reject' "$TMP/guards.txt" || fail
    grep -q 'meta nfproto ipv6' "$TMP/guards.txt" || fail
    grep -q '02:00:00:00:aa:01' "$TMP/guards.txt" || fail
    ip -4 route show table 202 | grep -q 'unreachable default' || fail
    ip -4 rule show pref 11900 | grep -q 'unreachable' || fail
    # The guard retains configured LAN destinations before internet policy.
    grep -q 'oifname.*br-csqtt-test.*return' "$TMP/guards.txt" || fail
    timeout 10 wget -q -O "$TMP/luci-after" http://127.0.0.1/cgi-bin/luci/ || fail
    [ -s "$TMP/luci-after" ] || fail
    [ "$(uci -q get csqtt.main.enabled)" = 0 ] || fail
}
guard_checks
stage firewall_reload
timeout 30 fw4 reload > "$TMP/reload.log" 2>&1 || fail
guard_checks
stage manual_stop
timeout 30 /usr/libexec/csqtt/manage stop > "$TMP/stop.log" 2>&1 || fail
guard_checks
# Upgrade compatibility: an explicit worker setting and configured stopped
# connection bypass first-run detection without starting the client.
stage migration_state
uci set csqtt.main.peer=synthetic.invalid:443
uci set csqtt.main.password=synthetic-fixture-only
uci add_list csqtt.main.vk_hashes=synthetic_call_fixture_only
uci set csqtt.main.workers=9
uci commit csqtt
/usr/libexec/csqtt/manage status > "$TMP/configured.json" 2> "$TMP/configured.log" || fail
jsonfilter -i "$TMP/configured.json" -e '@.setup_required' | grep -qx false || fail
[ "$(uci -q get csqtt.main.workers)" = 9 ] || fail
grep -q 'synthetic-fixture-only\|synthetic_call_fixture_only\|synthetic.invalid' "$TMP/configured.json" && fail
FINISHED=1
