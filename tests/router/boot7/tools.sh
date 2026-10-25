#!/bin/sh
# Only the official, kernel-matched veth dependency used by test clients.
set -eu
umask 077
MODE=${1:-}; STATE=${2:-}
fail() { printf 'test_tools_failure=%s\n' "$1" >&2; exit 1; }
printf '%s\n' "$STATE" | grep -Eq '^/etc/csqtt/backups/boot7-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$' || fail state_path
[ "$(id -u)" = 0 ] && [ -d "$STATE" ] && [ ! -L "$STATE" ] || fail private_state
[ "$(cat "$STATE/identity")" = CSQTT-BOOT7 ] || fail identity
[ "$(uname -r)" = 6.12.94 ] || fail kernel
for p in csqtt dhcp firewall network; do [ -z "$(uci -q changes "$p")" ] || fail pending_edits; done
maps() {
    ucode -e '
import * as fs from "fs";
let before=json(fs.readfile(ARGV[0])), after=json(fs.readfile(ARGV[1])), b={}, a={};
if(type(before)!=="array" || type(after)!=="array" || length(before)<100 || length(after)<100) exit(1);
for(let p in before) { if(type(p.name)!=="string" || type(p.version)!=="string" || b[p.name]!=null) exit(1); b[p.name]=p.version; }
for(let p in after) { if(type(p.name)!=="string" || type(p.version)!=="string" || a[p.name]!=null) exit(1); a[p.name]=p.version; }
if(ARGV[2]==="added") { if(b["kmod-veth"]!=null || a["kmod-veth"]!=="6.12.94-r1") exit(1); delete a["kmod-veth"]; }
for(let key in b) if(a[key]!==b[key]) exit(1);
for(let key in a) if(b[key]!==a[key]) exit(1);
' "$1" "$2" "$3" || fail package_map
}
case "$MODE" in
 add)
    [ ! -e "$STATE/tools.world.before" ] || fail previous_attempt
    [ -z "$(apk query --installed --match name --fields name --format json kmod-veth | jsonfilter -e '@[0].name')" ] || fail already_installed
    [ ! -d /sys/module/veth ] || fail already_loaded
    cp /etc/apk/world "$STATE/tools.world.before"
    apk query --installed --match name --fields name,version --format json '*' > "$STATE/tools.before.json"
    sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network > "$STATE/tools.config.sha256"
    apk --no-cache --keys-dir /etc/apk/keys add --simulate kmod-veth=6.12.94-r1 > "$STATE/tools.add.sim.private.log" 2>&1 || fail simulate
    apk --no-cache --keys-dir /etc/apk/keys add kmod-veth=6.12.94-r1 > "$STATE/tools.add.private.log" 2>&1 || fail install
    apk query --installed --match name --fields name,version --format json '*' > "$STATE/tools.after.json"
    maps "$STATE/tools.before.json" "$STATE/tools.after.json" added
    sha256sum -c "$STATE/tools.config.sha256" > "$STATE/tools.config.private.log" || fail owner_configs
    modprobe veth; [ -d /sys/module/veth ] || fail module
    echo only_official_kernel_matched_veth_added=true
    ;;
 remove)
    [ -f "$STATE/tools.world.before" ] && [ -f "$STATE/tools.after.json" ] || fail missing_before
    [ "$(apk query --installed --match name --fields version --format json kmod-veth | jsonfilter -e '@[0].version')" = 6.12.94-r1 ] || fail package_version
    [ -z "$(ip -d -o link show type veth)" ] || fail veth_remains
    apk --no-network del --simulate kmod-veth > "$STATE/tools.remove.sim.private.log" 2>&1 || fail simulate
    grep -Eq '^\(1/1\) Purging kmod-veth \(6\.12\.94-r1\)' "$STATE/tools.remove.sim.private.log" || fail removal_scope
    apk --no-network del kmod-veth > "$STATE/tools.remove.private.log" 2>&1 || fail remove
    if [ -d /sys/module/veth ]; then
        [ "$(cat /sys/module/veth/refcnt)" = 0 ] || fail module_in_use
        rmmod veth
    fi
    cmp -s "$STATE/tools.world.before" /etc/apk/world || fail world
    apk query --installed --match name --fields name,version --format json '*' > "$STATE/tools.cleaned.json"
    maps "$STATE/tools.before.json" "$STATE/tools.cleaned.json" equal
    echo only_test_veth_removed=true
    echo apk_world_and_full_package_map_restored=true
    ;;
 *) fail mode ;;
esac
