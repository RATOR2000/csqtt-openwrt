#!/bin/sh
# CSQTT installer for official OpenWrt 25.12.5 on GL-MT6000.
set -eu
umask 077
# Do not inherit options such as allow-untrusted from a local APK config.
APK_CONFIG=/dev/null
export APK_CONFIG
REPO=RATOR2000/csqtt-openwrt
VERSION=${1:-latest}
case "$VERSION" in *[!A-Za-z0-9._-]*|'') echo 'Invalid release version' >&2; exit 1 ;; esac
die() { echo "CSQTT: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die 'Run as root on the router.'
[ -f /etc/openwrt_release ] || die 'OpenWrt is required.'
. /etc/openwrt_release
[ "${DISTRIB_RELEASE:-}" = 25.12.5 ] || die 'This release supports OpenWrt 25.12.5.'
[ "${DISTRIB_TARGET:-}" = mediatek/filogic ] || die 'Unsupported OpenWrt target.'
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = glinet,gl-mt6000 ] || die 'Only GL-MT6000 is supported.'
for TOOL in apk uclient-fetch jsonfilter sha256sum tar awk; do
    command -v "$TOOL" >/dev/null || die "Required OpenWrt tool is missing: $TOOL"
done
# APK --print-arch reports its compiled CPU architecture (aarch64), while
# OpenWrt package selection reads the tuned architecture from /etc/apk/arch.
[ "${DISTRIB_ARCH:-}" = aarch64_cortex-a53 ] || die 'Unsupported OpenWrt package architecture.'
[ "$(cat /etc/apk/arch 2>/dev/null)" = aarch64_cortex-a53 ] || die 'Expected aarch64_cortex-a53 in /etc/apk/arch.'
AVAILABLE=$(df -Pk /overlay | awk 'NR==2 { print $4 }')
case "$AVAILABLE" in ''|*[!0-9]*) die 'Cannot determine free overlay space.' ;; esac
[ "$AVAILABLE" -ge 65536 ] || die 'At least 64 MiB of free overlay space is required.'
TMP=$(mktemp -d /tmp/csqtt-install.XXXXXX)
DNS_REMOVED=0
BACKUP=
cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$status" -ne 0 ] && [ "$DNS_REMOVED" = 1 ]; then
        echo 'Restoring the previous DNS package after failed installation.' >&2
        # Replacement is allowed only on a first install, so these roots did
        # not exist before the transaction. Keep configs and fail-closed guards.
        apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/cache" --no-network del csqtt-captcha luci-app-csqtt csqtt dnsmasq-full >> "$TMP/rollback.txt" 2>&1 || true
        if apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/cache" --no-network add "$TMP/rollback/$DNS_PACKAGE.apk" >> "$TMP/rollback.txt" 2>&1; then
            if [ -f "$BACKUP/dhcp" ]; then
                cp -p "$BACKUP/dhcp" /etc/config/dhcp || echo 'Cannot restore the DHCP configuration; inspect the private backup.' >&2
            fi
            cp -p "$BACKUP/world" /etc/apk/world || echo 'Cannot restore APK world; inspect the private backup.' >&2
            /etc/init.d/dnsmasq restart >> "$TMP/rollback.txt" 2>&1 || echo 'DNS service restart failed; inspect rollback.txt.' >&2
        else
            echo "Automatic DNS restore failed. Cached original package: $TMP/rollback/$DNS_PACKAGE.apk" >&2
        fi
    fi
    if [ "$status" -eq 0 ]; then rm -rf "$TMP"; else echo "Installation diagnostics retained in $TMP" >&2; fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
fetch() { uclient-fetch -q -O "$2" "$1" || die "Download failed: ${1##*/}"; }
field() { jsonfilter -i "$TMP/manifest.json" -e "$1"; }
if [ "$VERSION" = latest ]; then BASE="https://github.com/$REPO/releases/latest/download"; else BASE="https://github.com/$REPO/releases/download/$VERSION"; fi
mkdir -p "$TMP/packages" "$TMP/release-keys" "$TMP/keys" "$TMP/rollback" "$TMP/cache"
fetch "$BASE/manifest.json" "$TMP/manifest.json"
[ "$(wc -c < "$TMP/manifest.json")" -le 65536 ] || die 'Manifest is too large.'
fetch "$BASE/manifest.sig" "$TMP/manifest.sig"
[ "$(wc -c < "$TMP/manifest.sig")" -le 1024 ] || die 'Manifest signature is too large.'
cat > "$TMP/release-keys/csqtt-public.pem" <<'CSQTT_PUBLIC_KEY'
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETbV/mfygOtiJtOEqpvRlAazQEvb+
a2Y1lNcDNcPmDYDRB45yTNUvn6Ree4/eg+bWWf5kQeavIZvOLDB8iIcP4w==
-----END PUBLIC KEY-----
CSQTT_PUBLIC_KEY
# Bound unsigned fields before using them. Native APK signatures establish the
# pinned release signer before optional OpenSSL bootstrap from official feeds.
[ "$(field '@.schema')" = 1 ] || die 'Unknown manifest schema.'
[ "$(field '@.openwrt')" = "$DISTRIB_RELEASE" ] || die 'Manifest release mismatch.'
[ "$(field '@.target')" = "$DISTRIB_TARGET" ] || die 'Manifest target mismatch.'
[ "$(field '@.architecture')" = aarch64_cortex-a53 ] || die 'Manifest architecture mismatch.'
[ "$(field '@.upstream')" = amurcanov/csqtt@v2.1.9 ] || die 'Manifest upstream mismatch.'
NAMES=$(field '@.packages[*].name')
set -f
set -- $NAMES
set +f
[ "$#" -eq 3 ] || die 'Expected exactly three packages.'
[ -z "$(field '@.packages[3]')" ] || die 'Expected exactly three manifest entries.'
CORE= CAPTCHA= LUCI=
INDEX=0
for NAME in "$@"; do
    case "$NAME" in *[!A-Za-z0-9._+-]*|.*) die 'Invalid package filename.' ;; esac
    case "$NAME" in
        csqtt-captcha-[0-9]*.apk) [ -z "$CAPTCHA" ] || die 'Duplicate CAPTCHA package.'; CAPTCHA=$NAME ;;
        luci-app-csqtt-[0-9]*.apk) [ -z "$LUCI" ] || die 'Duplicate LuCI package.'; LUCI=$NAME ;;
        csqtt-[0-9]*.apk) [ -z "$CORE" ] || die 'Duplicate core package.'; CORE=$NAME ;;
        *) die 'Unexpected package.' ;;
    esac
    HASH=$(field "@.packages[$INDEX].sha256")
    case "$HASH" in *[!A-Fa-f0-9]*) die 'Invalid package checksum.' ;; esac
    [ "${#HASH}" -eq 64 ] || die 'Invalid package checksum.'
    SIZE=$(field "@.packages[$INDEX].size")
    case "$SIZE" in ''|*[!0-9]*) die 'Invalid package size.' ;; esac
    [ "$SIZE" -ge 1 ] && [ "$SIZE" -le 67108864 ] || die 'Package size is out of bounds.'
    fetch "$BASE/$NAME" "$TMP/packages/$NAME"
    [ "$(wc -c < "$TMP/packages/$NAME")" -eq "$SIZE" ] || die 'Package size mismatch.'
    apk --keys-dir "$TMP/release-keys" verify "$TMP/packages/$NAME" >/dev/null || die 'Package signature verification failed.'
    INDEX=$((INDEX + 1))
done
[ -n "$CORE" ] && [ -n "$CAPTCHA" ] && [ -n "$LUCI" ] || die 'Incomplete release packages.'
# Pin official feeds and kernel ABI instead of using arbitrary custom feeds.
cat > "$TMP/repositories" <<'CSQTT_REPOSITORIES'
https://downloads.openwrt.org/releases/25.12.5/targets/mediatek/filogic/packages/packages.adb
https://downloads.openwrt.org/releases/25.12.5/targets/mediatek/filogic/kmods/6.12.94-1-5a6c1f71be683ae9980b15d3ce73e24d/packages.adb
https://downloads.openwrt.org/releases/25.12.5/packages/aarch64_cortex-a53/base/packages.adb
https://downloads.openwrt.org/releases/25.12.5/packages/aarch64_cortex-a53/luci/packages.adb
https://downloads.openwrt.org/releases/25.12.5/packages/aarch64_cortex-a53/packages/packages.adb
https://downloads.openwrt.org/releases/25.12.5/packages/aarch64_cortex-a53/routing/packages.adb
https://downloads.openwrt.org/releases/25.12.5/packages/aarch64_cortex-a53/telephony/packages.adb
CSQTT_REPOSITORIES
if ! command -v openssl >/dev/null; then
    echo 'Installing OpenSSL from signed OpenWrt feeds to verify the manifest.'
    # This official dependency/cache may remain if later verification fails.
    # CSQTT, DHCP, DNS and persistent trust have not been changed at this point.
    apk --repositories-file "$TMP/repositories" --cache-dir "$TMP/cache" --cache-predownload add openssl-util || die 'Cannot install the manifest verifier.'
fi
openssl dgst -sha256 -verify "$TMP/release-keys/csqtt-public.pem" -signature "$TMP/manifest.sig" "$TMP/manifest.json" >/dev/null || die 'Release signature verification failed.'
INDEX=0
for NAME in "$@"; do
    HASH=$(field "@.packages[$INDEX].sha256")
    printf '%s  %s\n' "$HASH" "$TMP/packages/$NAME" | sha256sum -c - >/dev/null || die 'Package checksum mismatch.'
    INDEX=$((INDEX + 1))
done
for KEY in /lib/apk/keys/* /etc/apk/keys/*; do [ ! -f "$KEY" ] || cp "$KEY" "$TMP/keys/"; done
cp "$TMP/release-keys/csqtt-public.pem" "$TMP/keys/"
# Clone package state into an isolated root. Scripts are disabled throughout
# staging; dependency errors and downloads cannot remove the live DNS package.
STAGE="$TMP/stage"
mkdir -p "$STAGE/lib/apk/db" "$STAGE/etc/apk/keys" "$STAGE/var/cache/apk"
cp -aL /lib/apk/db/. "$STAGE/lib/apk/db/"
cp /etc/apk/world "$STAGE/etc/apk/world"
[ ! -f /etc/apk/arch ] || cp /etc/apk/arch "$STAGE/etc/apk/arch"
cp "$TMP/keys/"* "$STAGE/etc/apk/keys/"
cp "$TMP/repositories" "$STAGE/etc/apk/repositories"
stage_apk() { apk --root "$STAGE" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-scripts "$@"; }
# Read applets do not accept the mutation-only --no-scripts option in APK 3.0.5.
stage_info() { apk --root "$STAGE" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-network info --from installed; }
UPGRADE=0
apk query --installed --match name --fields name --format json csqtt > "$TMP/core-installed.json"
[ "$(jsonfilter -i "$TMP/core-installed.json" -e '@[*].name')" != csqtt ] || UPGRADE=1
REPLACE_DNS=0
if apk query --installed --match name --fields name --format json dnsmasq > "$TMP/dns.json"; then
    [ "$(jsonfilter -i "$TMP/dns.json" -e '@[*].name')" != dnsmasq ] || REPLACE_DNS=1
fi
if [ "$REPLACE_DNS" = 1 ]; then
    for PACKAGE in csqtt csqtt-captcha luci-app-csqtt; do
        apk query --installed --match name --fields name --format json "$PACKAGE" > "$TMP/installed.json"
        [ -z "$(jsonfilter -i "$TMP/installed.json" -e '@[*].name')" ] || die 'Existing CSQTT with plain dnsmasq is inconsistent; repair it before upgrading.'
    done
    apk query --installed --match name --fields package,version --format json dnsmasq > "$TMP/dns.json"
    DNS_PACKAGE=$(jsonfilter -i "$TMP/dns.json" -e '@[0].package')
    DNS_VERSION=$(jsonfilter -i "$TMP/dns.json" -e '@[0].version')
    case "$DNS_PACKAGE:$DNS_VERSION" in *[!A-Za-z0-9._+:-]*|:|*:|:*) die 'Cannot identify the installed DNS package.' ;; esac
    apk --repositories-file "$TMP/repositories" fetch --output "$TMP/rollback" "dnsmasq=$DNS_VERSION" || die 'The exact original DNS package must be cached before replacement.'
    [ -f "$TMP/rollback/$DNS_PACKAGE.apk" ] || die 'Original DNS package cache is missing.'
    apk verify "$TMP/rollback/$DNS_PACKAGE.apk" >/dev/null || die 'Original DNS package signature verification failed.'
    stage_info > "$TMP/installed-before.txt"
    stage_apk del --simulate dnsmasq > "$TMP/dns-remove.txt" 2>&1 || die 'Cannot safely replace the current DNS package.'
    stage_apk del dnsmasq >> "$TMP/dns-remove.txt" 2>&1 || die 'DNS replacement preflight failed.'
    stage_info > "$TMP/installed-after.txt"
    awk 'NR==FNR { kept[$0]=1; next } $0 != "dnsmasq" && !($0 in kept) { bad=1 } END { exit bad }' "$TMP/installed-after.txt" "$TMP/installed-before.txt" || die 'DNS replacement would remove other installed packages.'
fi
stage_apk add --simulate "$TMP/packages/$CORE" "$TMP/packages/$CAPTCHA" "$TMP/packages/$LUCI" dnsmasq-full > "$TMP/transaction.txt" 2>&1 || die 'Dependency check failed; DNS and configuration are unchanged.'
# Cache the selected dependencies, then prove the add works without networking.
# Only the three release files and DNS are added as world roots.
stage_apk --cache-predownload add "$TMP/packages/$CORE" "$TMP/packages/$CAPTCHA" "$TMP/packages/$LUCI" dnsmasq-full >> "$TMP/transaction.txt" 2>&1 || die 'Dependency prefetch failed; DNS and configuration are unchanged.'
cp -a "$STAGE/var/cache/apk/." "$TMP/cache/"
# Recreate the starting state: checking an already installed staging root
# would not prove that the cache can satisfy the live transaction.
STAGE="$TMP/offline"
mkdir -p "$STAGE/lib/apk/db" "$STAGE/etc/apk/keys" "$STAGE/var/cache/apk"
cp -aL /lib/apk/db/. "$STAGE/lib/apk/db/"
cp /etc/apk/world "$STAGE/etc/apk/world"
[ ! -f /etc/apk/arch ] || cp /etc/apk/arch "$STAGE/etc/apk/arch"
cp "$TMP/keys/"* "$STAGE/etc/apk/keys/"
cp "$TMP/repositories" "$STAGE/etc/apk/repositories"
cp -a "$TMP/cache/." "$STAGE/var/cache/apk/"
[ "$REPLACE_DNS" != 1 ] || stage_apk --no-network del dnsmasq >> "$TMP/transaction.txt" 2>&1
stage_apk --no-network add --simulate "$TMP/packages/$CORE" "$TMP/packages/$CAPTCHA" "$TMP/packages/$LUCI" dnsmasq-full >> "$TMP/transaction.txt" 2>&1 || die 'Offline dependency check failed.'
AVAILABLE=$(df -Pk /overlay | awk 'NR==2 { print $4 }')
case "$AVAILABLE" in ''|*[!0-9]*) die 'Cannot determine free overlay space.' ;; esac
[ "$AVAILABLE" -ge 65536 ] || die 'Overlay space changed; at least 64 MiB is required.'
# Private backup contains UCI credentials and must remain on this router.
BACKUP="/etc/csqtt/backups/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$BACKUP"
chmod 0700 /etc/csqtt /etc/csqtt/backups "$BACKUP"
tar -czf "$BACKUP/config.tar.gz" -C / etc/config
cp -p /etc/apk/world "$BACKUP/world"
[ ! -f /etc/config/dhcp ] || cp -p /etc/config/dhcp "$BACKUP/dhcp"
cp "$TMP/manifest.json" "$BACKUP/manifest.json"
if [ "$REPLACE_DNS" = 1 ]; then
    DNS_REMOVED=1
    apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/cache" --no-network del dnsmasq || die 'DNS package replacement failed.'
fi
apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/cache" --no-network add "$TMP/packages/$CORE" "$TMP/packages/$CAPTCHA" "$TMP/packages/$LUCI" dnsmasq-full || die 'Package installation failed.'
/etc/init.d/dnsmasq restart || die 'DNS service restart failed.'
/etc/init.d/rpcd restart || die 'LuCI RPC service restart failed.'
if [ "$UPGRADE" = 1 ]; then
    /etc/init.d/csqtt restart || die 'CSQTT service restart failed.'
fi
/etc/init.d/csqtt-captcha enable || die 'CAPTCHA service enable failed.'
/etc/init.d/csqtt-captcha restart || die 'CAPTCHA service restart failed.'
# Persist the public key for future package operations only after success.
mkdir -p /etc/apk/keys
cp "$TMP/release-keys/csqtt-public.pem" /etc/apk/keys/csqtt-public.pem
DNS_REMOVED=0
echo "CSQTT installed. Open Services → CSQTT in LuCI. Configuration backup: $BACKUP"
