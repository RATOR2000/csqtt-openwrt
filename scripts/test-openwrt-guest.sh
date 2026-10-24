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
for tool in ucode uci ubus nft fw4 ip nslookup sha256sum nc mkfifo; do command -v "$tool" >/dev/null || { printf 'CSQTT_GUEST_MISSING_TOOL=%s\n' "$tool"; fail; }; done
# The host provisions this static test-only tool after the clean install. It
# lives beside this script on the disposable disk, outside the package database.
stage prerequisites_timeout
case "$0" in */*) TEST_TIMEOUT="${0%/*}/vm-timeout" ;; *) TEST_TIMEOUT=./vm-timeout ;; esac
[ -f "$TEST_TIMEOUT" ] && [ ! -L "$TEST_TIMEOUT" ] && [ -x "$TEST_TIMEOUT" ] || fail
timeout() { "$TEST_TIMEOUT" "$@"; }
timeout 1 true || fail
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
status_diagnostics() {
    case "${1:-status.log}" in status.log|apply.log|dns-ready.log|devices.log|helper.log) diagnostic_file="$TMP/${1:-status.log}" ;; *) return 0 ;; esac
    [ -f "$diagnostic_file" ] && [ ! -L "$diagnostic_file" ] || return 0
    dd if="$diagnostic_file" of="$TMP/status.checked" bs=1 count=8193 2>/dev/null || return 0
    count=$(wc -c < "$TMP/status.checked") || return 0
    case "$count" in ''|*[!0-9]*) return 0 ;; esac
    [ "$count" -le 8192 ] || return 0
    awk '
      BEGIN { files["runtime.uc"]=1; files["policy.uc"]=1; files["health.uc"]=1 }
      index($0,"Syntax error:") { classes["syntax_error"]=1 }
      index($0,"Reference error:") { classes["reference_error"]=1 }
      index($0,"Type error:") { classes["type_error"]=1 }
      index($0,"Unable to resolve module") || index($0,"Unable to load module") ||
        index($0,"Unable to compile module") { classes["module_error"]=1 }
      { for (file in files) {
          needle="/usr/share/csqtt/" file ", line "; at=index($0,needle)
          if (at) {
            value=substr($0,at+length(needle))
            if (match(value,/^[1-9][0-9]*,/)) {
              number=substr(value,1,RLENGTH-1)
              if (length(number)<=6) locations[file ":" number]=1
            }
          }
        } }
      END {
        for (kind in classes) print "CSQTT_GUEST_UCODE_CLASS=" kind
        count=0; for (where in locations) if (count++<8) print "CSQTT_GUEST_UCODE_SOURCE=" where
      }' "$TMP/status.checked" > "$TMP/status.markers" || return 0
    cat "$TMP/status.markers"
}
/usr/libexec/csqtt/manage status > "$TMP/status.json" 2> "$TMP/status.log" || { status_diagnostics; fail; }
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
# Keep HTTP failures useful without copying private HTML, headers or system logs.
# This runs only in a disposable clean guest, before synthetic user configuration.
web_filter() {
    awk '
      BEGIN {
        paths["/www/cgi-bin/luci"]="luci.cgi"
        paths["/usr/share/ucode/luci/dispatcher.uc"]="luci.dispatcher"
        paths["/usr/share/ucode/luci/runtime.uc"]="luci.runtime"
        paths["/usr/share/ucode/luci/template.uc"]="luci.template"
        paths["/usr/share/ucode/luci/http.uc"]="luci.http"
        paths["/usr/share/csqtt/runtime.uc"]="csqtt.runtime"
        paths["/usr/share/csqtt/policy.uc"]="csqtt.policy"
        paths["/usr/share/csqtt/health.uc"]="csqtt.health"
      }
      match($0,/HTTP\/[0-9][.][0-9][ \t]+[1-5][0-9][0-9]/) {
        value=substr($0,RSTART,RLENGTH); sub(/^HTTP\/[^ \t]+[ \t]+/,"",value); status[value]=1
      }
      match($0,/HTTP error [1-5][0-9][0-9]/) { status[substr($0,RSTART+11,3)]=1 }
      index($0,"Connection refused") { classes["connection_refused"]=1 }
      index($0,"Invalid SSL certificate") || index($0,"SSL verify error") { classes["tls_certificate"]=1 }
      index($0,"hostname does not match SSL certificate") { classes["tls_hostname"]=1 }
      index($0,"SSL support not available") { classes["tls_unavailable"]=1 }
      index($0,"Redirected to https://127.0.0.1/") { classes["local_https_redirect"]=1 }
      index($0,"timed out") { classes["timeout"]=1 }
      index($0,"Permission denied") { classes["permission_denied"]=1 }
      index($0,"Exec format error") || index($0,"Failed to execute") || index($0,"Unable to execute") { classes["cgi_execute"]=1 }
      index($0,"Bad Gateway") { classes["cgi_gateway"]=1 }
      index($0,"unrecognized option") || index($0,"invalid option") { classes["option_unsupported"]=1 }
      index($0,"Syntax error:") { classes["syntax_error"]=1 }
      index($0,"Reference error:") { classes["reference_error"]=1 }
      index($0,"Type error:") { classes["type_error"]=1 }
      index($0,"Runtime error:") { classes["runtime_error"]=1 }
      index($0,"Unable to resolve module") || index($0,"Unable to load module") ||
        index($0,"Unable to compile module") || index($0,"Error loading module") { classes["module_error"]=1 }
      { for (path in paths) {
          needle=path ", line "; at=index($0,needle)
          if (at) {
            value=substr($0,at+length(needle))
            if (match(value,/^[1-9][0-9]*,/)) {
              number=substr(value,1,RLENGTH-1)
              if (length(number)<=5 && number<=20000) locations[paths[path] ":" number]=1
            }
          }
        } }
      END {
        for (value in status) print "CSQTT_GUEST_WEB_STATUS=" value
        for (kind in classes) print "CSQTT_GUEST_WEB_CLASS=" kind
        count=0; for (where in locations) if (count++<8) print "CSQTT_GUEST_WEB_SOURCE=" where
      }'
}
web_file_diagnostics() {
    [ -f "$1" ] && [ ! -L "$1" ] || return 0
    dd if="$1" of="$TMP/web.checked" bs=1 count=8192 2>/dev/null || return 0
    web_filter < "$TMP/web.checked"
}
luci_diagnostics() {
    # Avoid xtrace of probes and filter programs crowding the bounded marker tail.
    (
        set +x
        printf 'CSQTT_GUEST_WEB_EXIT=%s\n' "$1"
        if timeout 2 /etc/init.d/uhttpd running > "$TMP/web-service.log" 2>&1; then service_status=0
        else service_status=$?; fi
        printf 'CSQTT_GUEST_WEB_SERVICE_EXIT=%s\n' "$service_status"
        if pidof uhttpd >/dev/null 2>&1; then printf '%s\n' CSQTT_GUEST_WEB_CHECK=uhttpd_running
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=uhttpd_stopped; fi
        if awk '$2 ~ /:0050$/ && $4=="0A" { found=1 } END { exit !found }' /proc/net/tcp /proc/net/tcp6 2>/dev/null; then
            printf '%s\n' CSQTT_GUEST_WEB_CHECK=port80_listening
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=port80_closed; fi
        if awk '$2 ~ /:01BB$/ && $4=="0A" { found=1 } END { exit !found }' /proc/net/tcp /proc/net/tcp6 2>/dev/null; then
            printf '%s\n' CSQTT_GUEST_WEB_CHECK=port443_listening
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=port443_closed; fi
        for item in cgi dispatcher runtime template http; do
            case "$item" in cgi) file=/www/cgi-bin/luci ;; *) file=/usr/share/ucode/luci/$item.uc ;; esac
            if [ -s "$file" ]; then printf 'CSQTT_GUEST_WEB_FILE=%s:present\n' "$item"
            else printf 'CSQTT_GUEST_WEB_FILE=%s:missing\n' "$item"; fi
        done
        if [ -x /www/cgi-bin/luci ]; then printf '%s\n' CSQTT_GUEST_WEB_CHECK=cgi_executable
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=cgi_not_executable; fi
        if [ -s /usr/lib/uhttpd_ucode.so ]; then printf '%s\n' CSQTT_GUEST_WEB_CHECK=uhttpd_ucode_present
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=uhttpd_ucode_missing; fi
        for module in fs ubus uci uloop math html; do
            if timeout 2 ucode -e "import * as probe from '$module';" > "$TMP/web-module" 2>&1; then
                printf 'CSQTT_GUEST_WEB_MODULE=%s:loaded\n' "$module"
            else printf 'CSQTT_GUEST_WEB_MODULE=%s:failed\n' "$module"; web_file_diagnostics "$TMP/web-module"; fi
        done
        web_file_diagnostics "$TMP/luci-before.log"
        web_file_diagnostics "$TMP/luci-before"
        if timeout 3 env REQUEST_METHOD=GET SCRIPT_NAME=/cgi-bin/luci PATH_INFO=/ SERVER_NAME=127.0.0.1 SERVER_PORT=80 REMOTE_ADDR=127.0.0.1 /www/cgi-bin/luci > "$TMP/web-cgi.log" 2>&1; then cgi_status=0
        else cgi_status=$?; fi
        printf 'CSQTT_GUEST_WEB_CGI_EXIT=%s\n' "$cgi_status"
        web_file_diagnostics "$TMP/web-cgi.log"
        if timeout 3 wget -O "$TMP/web-root" http://127.0.0.1/ > "$TMP/web-root.log" 2>&1; then
            printf '%s\n' CSQTT_GUEST_WEB_CHECK=root_http_ok
        else printf '%s\n' CSQTT_GUEST_WEB_CHECK=root_http_failed; fi
        web_file_diagnostics "$TMP/web-root.log"
        timeout 3 logread -l 60 > "$TMP/web-system.log" 2>/dev/null || :
        web_file_diagnostics "$TMP/web-system.log"
    )
}
login_response() {
    LC_ALL=C awk -v response_bytes="$1" '
      BEGIN { quote="[\"" sprintf("%c",39) "]" }
      !body {
        header_bytes+=length($0)+1
        if ($0 !~ /\r$/) bad["header_format"]=1
        sub(/\r$/, "")
        if (NR==1) { if ($0 !~ /^HTTP\/1[.][01] 403( [^\r]*)?$/) bad["status_line"]=1; next }
        if ($0=="") { body=1; next }
        if ($0 !~ /^[A-Za-z0-9!#$%&*+.^_`|~-]+:[ \t]*[^\r]*$/) { bad["header_format"]=1; next }
        at=index($0,":"); key=tolower(substr($0,1,at-1)); value=substr($0,at+1)
        sub(/^[ \t]+/,"",value); sub(/[ \t]+$/,"",value)
        if (key=="x-luci-login-required") { login++; if (tolower(value)!="yes") bad["auth_header"]=1 }
        if (key=="content-type") { html++; if (tolower(value) !~ /^text\/html([ \t]*;.*)?$/) bad["content_type"]=1 }
        if (key=="content-length") { lengths++; if (value !~ /^[0-9]+$/ || value+0>131072) bad["content_length"]=1; declared=value+0 }
        if (key=="transfer-encoding") bad["transfer_encoding"]=1
        next
      }
      { content=content tolower($0) "\n" }
      END {
        if (!body) bad["header_format"]=1
        if (login!=1) bad["auth_header"]=1
        if (html!=1) bad["content_type"]=1
        if (response_bytes<=header_bytes || response_bytes>131072) bad["body_size"]=1
        if (lengths>1 || (lengths && declared!=response_bytes-header_bytes)) bad["content_length"]=1
        username="<input[[:space:]][^>]*name[[:space:]]*=[[:space:]]*" quote "luci_username" quote "[^>]*>"
        password="<input[[:space:]][^>]*name[[:space:]]*=[[:space:]]*" quote "luci_password" quote "[^>]*>"
        form="<form[[:space:]][^>]*method[[:space:]]*=[[:space:]]*" quote "post" quote
        # HTML permits omitted html/body end tags; require a document marker
        # and the complete authenticated-login form below, not a closing literal.
        if (content !~ /<(html([[:space:]>])|!doctype[[:space:]]+html([[:space:]>]))/) bad["html_document"]=1
        if (!match(content,form)) bad["login_form"]=1
        else {
          form_content=substr(content,RSTART); closing=index(form_content,"</form>")
          if (!closing) bad["login_form"]=1
          else {
            form_content=substr(form_content,1,closing)
            if (form_content !~ username) bad["username_input"]=1
            if (!match(form_content,password)) bad["password_input"]=1
            else {
              password_input=substr(form_content,RSTART,RLENGTH)
              if (password_input !~ ("type[[:space:]]*=[[:space:]]*" quote "password" quote)) bad["password_type"]=1
            }
          }
        }
        failed=0; for (reason in bad) { print "CSQTT_GUEST_WEB_PARSE=" reason; failed=1 }
        exit failed
      }' "$TMP/luci-before"
}
luci_http() {
    # Stock LuCI24/25 deliberately returns403 + its login header and rendered
    # form for an anonymous request. uclient discards403 bodies. Read that exact
    # unauthenticated HTTP contract using stock nc, without credentials or TLS
    # overrides. A generic403, redirect,500 or successful unrelated page fails.
    rm -f "$TMP/web-input" "$TMP/web-nc.exit"
    mkfifo "$TMP/web-input" || { luci_diagnostics 125; fail; }
    # Keep stdin open until the server closes the HTTP1.0 response. Some HTTP
    # servers abort a request when nc half-closes after consuming a regular file.
    # Linux FIFO O_RDWR needs no writer subprocess, sleeps or optional nc flags.
    exec 3<> "$TMP/web-input"
    printf 'GET /cgi-bin/luci/ HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n' >&3
    read_status=0
    { if timeout 10 nc 127.0.0.1 80 <&3 3>&- 2> "$TMP/luci-before.log"; then
          printf '%s\n' 0 > "$TMP/web-nc.exit"
      else printf '%s\n' "$?" > "$TMP/web-nc.exit"; fi
    } | dd bs=1 count=131073 > "$TMP/luci-before" 2> "$TMP/web-read.log" || read_status=$?
    exec 3>&-
    rm -f "$TMP/web-input"
    web_status=$(cat "$TMP/web-nc.exit" 2>/dev/null) || web_status=125
    case "$web_status" in ''|*[!0-9]*|????*) web_status=125 ;; esac
    [ "$web_status" -le 255 ] || web_status=125
    size=$(wc -c < "$TMP/luci-before") || size=0
    parse_status=0
    login_response "$size" > "$TMP/web-parse.markers" || parse_status=$?
    if [ "$read_status" = 0 ] && [ "$web_status" = 0 ] && [ "$size" -le 131072 ] && [ "$parse_status" = 0 ]; then return 0; fi
    printf 'CSQTT_GUEST_WEB_BYTES=%s\nCSQTT_GUEST_WEB_READ_EXIT=%s\n' "$size" "$read_status"
    cat "$TMP/web-parse.markers"
    luci_diagnostics "$web_status"
    fail
}
stage luci_http
luci_http

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
# netifd clears unmanaged bridges when adopting a simple device. Declare the
# real bridge and permit the intentionally portless disposable LAN fixture.
[ -z "$(uci -q get network.csqtt_test_bridge || true)" ] || fail
LAN_CREATED=1
uci set network.csqtt_test_bridge=device
uci set network.csqtt_test_bridge.name=br-csqtt-test
uci set network.csqtt_test_bridge.type=bridge
uci set network.csqtt_test_bridge.bridge_empty=1
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
    /usr/libexec/csqtt/manage devices > "$TMP/devices.json" 2> "$TMP/devices.log" || { status_diagnostics devices.log; fail; }
    if jsonfilter -i "$TMP/devices.json" -e '@.lan_devices[*]' | grep -qx br-csqtt-test; then scope_ready=1; break; fi
    sleep 1
done
[ "$scope_ready" = 1 ] || {
    # Fixed booleans only: distinguish fixture readiness from auto-discovery.
    (
        set +x
        ucode -e '
            import { cursor } from "uci";
            import { connect } from "ubus";
            let c=cursor(), b=connect(), dump=b.call("network.interface", "dump", {}) || {};
            let found=null;
            for (let item in (dump.interface || [])) if (item.interface === "csqtt_test") found=item;
            let n=found || {}, routes=n.route || [], gateway=false;
            for (let route in routes) if ((route.target === "0.0.0.0" || route.target === "::") && +route.mask === 0) gateway=true;
            let networks=c.get("firewall", "csqtt_test", "network");
            let trusted=type(networks)==="array" ? index(networks,"csqtt_test")>=0 : networks==="csqtt_test";
            let flags={ auto:c.get("csqtt","main","lan_device")==="auto", present:found!=null,
                up:n.up===true, proto:n.proto==="static", device:(n.l3_device||n.device)==="br-csqtt-test",
                address:length(n["ipv4-address"]||[])>0, no_default:!gateway,
                trusted:trusted && c.get("firewall","csqtt_test","input")==="ACCEPT" && c.get("firewall","csqtt_test","masq")!=="1" };
            for (let key in flags) printf("CSQTT_GUEST_LAN_CHECK=%s:%d\n", key, flags[key]?1:0);
        ' > "$TMP/lan.markers" 2> "$TMP/lan.log" && cat "$TMP/lan.markers"
    ) || :
    fail
}
! jsonfilter -i "$TMP/devices.json" -e '@.lan_devices[*]' | grep -qx br-lan || fail
/usr/libexec/csqtt/manage helper-address > "$TMP/helper-address" 2> "$TMP/helper.log" || { status_diagnostics helper.log; fail; }
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
timeout 60 /usr/libexec/csqtt/manage apply > "$TMP/apply.log" 2>&1 || { status_diagnostics apply.log; fail; }
ucode /usr/share/csqtt/runtime.uc dns-ready > "$TMP/dns-ready.log" 2>&1 || { status_diagnostics dns-ready.log; fail; }
# nft canonically replaces explicit IPv6 + reject with icmpv6 reject. Check
# the installed rule meaning, including the managed MAC, rather than formatting.
cat > "$TMP/guard-v6.uc" <<'UCODE_GUARD'
import * as fs from 'fs';
let doc=json(fs.readfile(ARGV[0])), rules=doc.nftables || [];
let seen=false, any_family=false, any_mac=false, any_reject=false;
for (let i=0; i<length(rules); i++) {
    let r=rules[i].rule;
    if (!r || r.family!=="inet" || r.table!=="csqtt" || r.chain!=="forward_guard") continue;
    seen=true;
    let family=false, mac=false, rejected=false, expr=r.expr || [];
    for (let j=0; j<length(expr); j++) {
        let e=expr[j], m=e.match || {}, l=m.left || {}, right=m.right;
        if (m.op==="==") {
            if (l.meta && l.meta.key==="nfproto" && (right==="ipv6" || right===10)) family=true;
            if (l.payload && l.payload.protocol==="ether" && l.payload.field==="type" && (right==="ip6" || right===34525)) family=true;
            if (l.payload && l.payload.protocol==="ether" && l.payload.field==="saddr" &&
                (right==="02:00:00:00:aa:01" || (right && type(right)==="object" && type(right.set)==="array" && index(right.set,"02:00:00:00:aa:01")>=0))) mac=true;
        }
        if (index(keys(e),"reject")>=0) {
            rejected=true;
            if (e.reject && e.reject.type==="icmpv6") family=true;
        }
    }
    if (family && mac && rejected) exit(0);
    any_family=any_family || family; any_mac=any_mac || mac; any_reject=any_reject || rejected;
}
printf("CSQTT_GUEST_GUARD_CHECK=chain:%d\nCSQTT_GUEST_GUARD_CHECK=ipv6:%d\nCSQTT_GUEST_GUARD_CHECK=mac:%d\nCSQTT_GUEST_GUARD_CHECK=reject:%d\n", seen?1:0, any_family?1:0, any_mac?1:0, any_reject?1:0);
exit(1);
UCODE_GUARD
guard_checks() {
    nft list table inet csqtt > "$TMP/guards.txt"
    grep -q 'oifname != "csqtt0" reject' "$TMP/guards.txt" || fail
    nft -j list table inet csqtt > "$TMP/guards.json" || fail
    ucode "$TMP/guard-v6.uc" "$TMP/guards.json" || fail
    grep -q '02:00:00:00:aa:01' "$TMP/guards.txt" || fail
    ip -4 route show table 202 | grep -q 'unreachable default' || fail
    ip -4 rule show pref 11900 | grep -q 'unreachable' || fail
    # The guard retains configured LAN destinations before internet policy.
    grep -q 'oifname.*br-csqtt-test.*return' "$TMP/guards.txt" || fail
    luci_http
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
