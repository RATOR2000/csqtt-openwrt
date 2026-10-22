#!/bin/sh
# BEGIN PORTABLE INSTALLER (generated; edit scripts helpers)
# Public, read-only platform facts. Never evaluate firmware-owned release files.
csqtt_release_value() {
    [ -r "$1" ] || return 0
    awk -v wanted="$2" '
      { line=$0; sub(/\r$/, "", line); p=index(line,"="); if (!p) next;
        key=substr(line,1,p-1); gsub(/^[ \t]+|[ \t]+$/, "", key);
        if (key != wanted) next;
        value=substr(line,p+1); gsub(/^[ \t]+|[ \t]+$/, "", value);
        if (value ~ /^\047.*\047$/ || value ~ /^".*"$/) value=substr(value,2,length(value)-2);
        if (value ~ /^[A-Za-z0-9_.+:/,@-]+$/ && length(value)<=160) print value;
        exit;
      }' "$1"
}
csqtt_metadata_line() {
    [ -r "$1" ] || return 0
    awk 'NR==1 { sub(/\r$/, ""); if ($0 ~ /^[A-Za-z0-9_.+:/,@-]+$/ && length($0)<=160) print; exit }' "$1"
}
csqtt_has() { if command -v "$1" >/dev/null 2>&1; then printf true; else printf false; fi; }
csqtt_free_kib() {
    df -Pk "$1" 2>/dev/null | awk 'NR==2 && $4 ~ /^[0-9]+$/ { print $4; found=1 } END { if (!found) print 0 }'
}
csqtt_probe_main() (
    set -eu
    CS_OPENWRT=$(csqtt_release_value /etc/openwrt_release DISTRIB_RELEASE)
    CS_TARGET=$(csqtt_release_value /etc/openwrt_release DISTRIB_TARGET)
    CS_ARCH=$(csqtt_release_value /etc/openwrt_release DISTRIB_ARCH)
    CS_ID=$(csqtt_release_value /etc/openwrt_release DISTRIB_ID)
    CS_OS_ID=$(csqtt_release_value /etc/os-release ID)
    CS_BOARD=$(csqtt_metadata_line /tmp/sysinfo/board_name)
    CS_FIRMWARE=$(csqtt_metadata_line /etc/glversion)
    CS_KERNEL=$(uname -r 2>/dev/null | awk 'NR==1 && /^[A-Za-z0-9_.+-]+$/ { print; exit }')
    CS_FAMILY=unknown
    if [ -n "$CS_FIRMWARE" ]; then
        case "$CS_BOARD" in glinet,*) CS_FAMILY=glinet ;; esac
    elif [ "$CS_ID" = OpenWrt ] && [ "$CS_OS_ID" = openwrt ]; then
        case "$CS_OPENWRT" in 24.10.[0-9]*|25.12.[0-9]*) CS_FAMILY=official ;; esac
    fi
    CS_PM=unknown CS_FORMAT=unknown CS_KERNEL_PACKAGE=
    CS_APK=$(csqtt_has apk) CS_OPKG=$(csqtt_has opkg)
    if [ "$CS_APK:$CS_OPKG" = true:false ]; then
        CS_PM=apk CS_FORMAT=apk
        CS_APK_ARCH=$(csqtt_metadata_line /etc/apk/arch)
        [ "$CS_APK_ARCH" = "$CS_ARCH" ] || CS_ARCH=
        if command -v jsonfilter >/dev/null 2>&1; then
            CS_KERNEL_PACKAGE=$(apk query --installed --match name --fields version --format json kernel 2>/dev/null | jsonfilter -e '@[0].version' 2>/dev/null || true)
        fi
    elif [ "$CS_APK:$CS_OPKG" = false:true ]; then
        CS_PM=opkg CS_FORMAT=ipk
        CS_KERNEL_PACKAGE=$(awk 'BEGIN { RS=""; FS="\n" } /(^|\n)Package: kernel(\n|$)/ { for(i=1;i<=NF;i++) if($i ~ /^Version: [A-Za-z0-9_.+~-]+$/) { print substr($i,10); exit } }' /usr/lib/opkg/status 2>/dev/null || true)
        CS_OPKG_ARCH=$(awk -v wanted="$CS_ARCH" '$1=="arch" && $2==wanted { print $2; exit }' /etc/opkg.conf /etc/opkg/arch.conf 2>/dev/null || true)
        [ "$CS_OPKG_ARCH" = "$CS_ARCH" ] || CS_ARCH=
    fi
    case "$CS_KERNEL_PACKAGE" in *[!A-Za-z0-9_.+~-]*) CS_KERNEL_PACKAGE= ;; esac
    CS_NFT=$(csqtt_has nft) CS_FW4=$(csqtt_has fw4) CS_FW3=$(csqtt_has fw3)
    CS_IPTABLES=$(csqtt_has iptables) CS_UCODE=$(csqtt_has ucode)
    [ ! -x /usr/libexec/csqtt/ucode ] || CS_UCODE=true
    CS_PROCD=$(csqtt_has procd) CS_NETIFD=$(csqtt_has netifd)
    CS_BACKEND=unknown
    if [ "$CS_NFT:$CS_FW4" = true:true ]; then CS_BACKEND=fw4-nft
    elif [ "$CS_FW3:$CS_IPTABLES" = true:true ]; then CS_BACKEND=legacy-xtables; fi
    CS_NFTSET=false CS_IPSET=false
    if command -v dnsmasq >/dev/null 2>&1; then
        CS_DNS_FEATURES=$(dnsmasq --version 2>/dev/null || true)
        if printf '%s\n' "$CS_DNS_FEATURES" | awk ' /(^|[[:space:]])nftset([[:space:]]|$)/ { found=1 } END { exit !found }'; then CS_NFTSET=true; fi
        if printf '%s\n' "$CS_DNS_FEATURES" | awk ' /(^|[[:space:]])ipset([[:space:]]|$)/ { found=1 } END { exit !found }'; then CS_IPSET=true; fi
    fi
    CS_MEM_TOTAL=$(awk '$1=="MemTotal:" && $2 ~ /^[0-9]+$/ { print $2; exit }' /proc/meminfo 2>/dev/null || true)
    CS_MEM_AVAILABLE=$(awk '$1=="MemAvailable:" && $2 ~ /^[0-9]+$/ { print $2; found=1; exit } $1=="MemFree:" { fallback=$2 } END { if (!found) print fallback+0 }' /proc/meminfo 2>/dev/null || true)
    CS_CPUS=$(awk '/^processor[[:space:]]*:/ { n++ } END { print n ? n : 1 }' /proc/cpuinfo 2>/dev/null || true)
    CS_OVERLAY=$(csqtt_free_kib /overlay) CS_TMP=$(csqtt_free_kib /tmp)
    CS_PROFILE=
    if [ -n "$CS_ARCH" ] && [ -n "$CS_TARGET" ]; then
        CS_PROFILE_VERSION=$CS_OPENWRT
        [ "$CS_FAMILY" != glinet ] || CS_PROFILE_VERSION=$CS_FIRMWARE
        CS_PROFILE=$(printf '%s-%s-%s-%s' "$CS_FAMILY" "$CS_PROFILE_VERSION" "$CS_TARGET" "$CS_ARCH" | tr / -)
    fi
    printf '{"schema":1,"profile_id":"%s","family":"%s","firmware":"%s","openwrt":"%s","board":"%s","target":"%s","architecture":"%s","package_manager":"%s","package_format":"%s","kernel":"%s","kernel_package":"%s","backend":"%s","readiness":"unqualified","resource":{"mem_total_kib":%s,"mem_available_kib":%s,"overlay_free_kib":%s,"tmp_free_kib":%s,"cpu_count":%s},"capabilities":{"ucode":%s,"nft":%s,"fw4":%s,"fw3":%s,"procd":%s,"netifd":%s,"dnsmasq_nftset":%s,"dnsmasq_ipset":%s},"reasons":["signed_profile_and_acceptance_required"]}\n' \
      "$CS_PROFILE" "$CS_FAMILY" "$CS_FIRMWARE" "$CS_OPENWRT" "$CS_BOARD" "$CS_TARGET" "$CS_ARCH" "$CS_PM" "$CS_FORMAT" "$CS_KERNEL" "$CS_KERNEL_PACKAGE" "$CS_BACKEND" \
      "${CS_MEM_TOTAL:-0}" "${CS_MEM_AVAILABLE:-0}" "$CS_OVERLAY" "$CS_TMP" "${CS_CPUS:-1}" \
      "$CS_UCODE" "$CS_NFT" "$CS_FW4" "$CS_FW3" "$CS_PROCD" "$CS_NETIFD" "$CS_NFTSET" "$CS_IPSET"
)
case "${0##*/}" in platform-probe|platform-probe.sh) csqtt_probe_main "$@" ;; esac
# Embedded into install.sh by assemble-installer.py. No downloaded code is run.
csqtt_portable_die() { printf 'CSQTT: %s\n' "$*" >&2; exit 1; }
csqtt_j() { jsonfilter -i "$1" -e "$2" 2>/dev/null; }
csqtt_token() { case "$1" in ''|*[!A-Za-z0-9_.+~-]*|.*|-*) return 1 ;; esac; [ "${#1}" -le 200 ]; }
csqtt_hash() { case "$1" in *[!a-f0-9]*) return 1 ;; esac; [ "${#1}" -eq 64 ]; }
csqtt_uint() { case "$1" in ''|*[!0-9]*) return 1 ;; esac; [ "${#1}" -le 9 ]; }
csqtt_fetch() { uclient-fetch -q -O "$2" "$CS_BASE/$1" || csqtt_portable_die 'Release download failed'; }
csqtt_bytes() {
    csqtt_hash "$2" && csqtt_uint "$3" && [ "$3" -gt 0 ] && [ "$3" -le 67108864 ] || csqtt_portable_die 'Invalid artifact bounds'
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(wc -c < "$1")" -eq "$3" ] || csqtt_portable_die 'Artifact size mismatch'
    printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null || csqtt_portable_die 'Artifact digest mismatch'
}
csqtt_asset() {
    CS_ASSET_NAME=$(csqtt_j "$CS_MANIFEST" "$1.name")
    csqtt_token "$CS_ASSET_NAME" || csqtt_portable_die 'Unsafe artifact name'
    [ ! -e "$CS_TMP/assets/$CS_ASSET_NAME" ] || csqtt_portable_die 'Duplicate artifact name'
    csqtt_fetch "$CS_ASSET_NAME" "$CS_TMP/assets/$CS_ASSET_NAME"
    csqtt_bytes "$CS_TMP/assets/$CS_ASSET_NAME" "$(csqtt_j "$CS_MANIFEST" "$1.sha256")" "$(csqtt_j "$CS_MANIFEST" "$1.size")"
}
csqtt_signature() {
    [ "$(wc -c < "$2")" -le 1024 ] || csqtt_portable_die 'Signature is too large'
    openssl dgst -sha256 -verify "$CS_TMP/project.pem" -signature "$2" "$1" >/dev/null 2>&1 || csqtt_portable_die 'Release signature verification failed'
}
csqtt_installed_version() {
    if [ "$CS_PM" = apk ]; then
        apk query --installed --match name --fields version --format json "$1" 2>/dev/null | jsonfilter -e '@[0].version' 2>/dev/null || true
    else
        OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg -f "$CS_TMP/opkg.conf" status "$1" 2>/dev/null | awk '/^Version: / { print $2; exit }' || true
    fi
}
csqtt_opkg() { OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_TMP/opkg.conf" --lists-dir "$CS_TMP/no-repositories" "$@"; }
csqtt_clone() {
    mkdir -p "$1/var/lock" "$1/tmp"
    if [ "$CS_PM" = apk ]; then
        mkdir -p "$1/lib/apk/db" "$1/etc/apk/keys"
        cp -aL /lib/apk/db/. "$1/lib/apk/db/"
        cp /etc/apk/world "$1/etc/apk/world"
        cp "$CS_TMP/keys/"* "$1/etc/apk/keys/"
    else
        mkdir -p "$1/usr/lib/opkg/info" "$1/etc/opkg"
        cp /usr/lib/opkg/status "$1/usr/lib/opkg/status"
        cp -a /usr/lib/opkg/info/. "$1/usr/lib/opkg/info/"
    fi
}
csqtt_check_versions() {
    CS_CHECK_ROOT=$1; CS_CHECK_BUNDLE=$2; CS_CHECK_N=0
    while [ "$CS_CHECK_N" -lt 3 ]; do
        CS_CHECK_ROLE=$(csqtt_j "$CS_CHECK_BUNDLE/manifest.json" "@.packages[$CS_CHECK_N].role")
        CS_CHECK_VERSION=$(csqtt_j "$CS_CHECK_BUNDLE/manifest.json" "@.packages[$CS_CHECK_N].version")
        if [ "$CS_CHECK_ROOT" = - ]; then CS_CHECK_ACTUAL=$(csqtt_installed_version "$CS_CHECK_ROLE")
        elif [ "$CS_PM" = apk ]; then CS_CHECK_ACTUAL=$(apk --root "$CS_CHECK_ROOT" --arch "$CS_ARCH" --keys-dir etc/apk/keys --no-network query --installed --match name --fields version --format json "$CS_CHECK_ROLE" | jsonfilter -e '@[0].version')
        else CS_CHECK_ACTUAL=$(awk -v wanted="$CS_CHECK_ROLE" 'BEGIN { RS=""; FS="\n" } { name=""; version=""; state=""; for(i=1;i<=NF;i++){if($i ~ /^Package: /) name=substr($i,10); if($i ~ /^Version: /) version=substr($i,10); if($i ~ /^Status: /) state=substr($i,9)} if(name==wanted && state=="install ok installed") print version }' "$CS_CHECK_ROOT/usr/lib/opkg/status"); fi
        [ "$CS_CHECK_ACTUAL" = "$CS_CHECK_VERSION" ] || return 1
        CS_CHECK_N=$((CS_CHECK_N + 1))
    done
}
csqtt_snapshot() {
    if [ "$CS_PM" = apk ]; then
        if [ "$1" = - ]; then apk --no-network query --installed --all-matches --fields name,version --format json '*' | jsonfilter -e '@[*]'
        else apk --root "$1" --arch "$CS_ARCH" --keys-dir etc/apk/keys --no-network query --installed --all-matches --fields name,version --format json '*' | jsonfilter -e '@[*]'; fi
    else
        CS_STATUS=/usr/lib/opkg/status
        [ "$1" = - ] || CS_STATUS="$1/usr/lib/opkg/status"
        awk 'BEGIN { RS=""; FS="\n" } { name=""; version=""; state=""; for(i=1;i<=NF;i++){if($i ~ /^Package: /) name=substr($i,10); if($i ~ /^Version: /) version=substr($i,10); if($i ~ /^Status: /) state=substr($i,9)} if(state=="install ok installed") printf "{\"name\":\"%s\",\"version\":\"%s\"}\n",name,version }' "$CS_STATUS"
    fi
}
csqtt_unchanged_packages() {
    awk '
      FILENAME==ARGV[1] { allowed[$0]=1; next }
      { name=$0; sub(/^.*"name"[ ]*:[ ]*"/,"",name); sub(/".*$/,"",name) }
      name=="csqtt" || name=="csqtt-captcha" || name=="luci-app-csqtt" { next }
      FILENAME==ARGV[2] { original[name]=$0; next }
      { if(name in original) { if(original[name]!=$0) bad=1; delete original[name] } else if(!(name in allowed)) bad=1 }
      END { for(name in original) bad=1; exit bad }' "$CS_TMP/new-dependencies" "$1" "$2"
}
csqtt_exact_packages() {
    awk 'NR==FNR { rows[$0]++; next } { if(!rows[$0]) bad=1; else rows[$0]-- } END { for(row in rows) if(rows[row]) bad=1; exit bad }' "$1" "$2"
}
csqtt_copy_bundle() {
    mkdir -p "$1/assets" "$1/repos"
    cp "$CS_TMP/manifest.json" "$CS_TMP/manifest.sig" "$CS_TMP/repositories" "$1/"
    cp -a "$CS_TMP/assets/." "$1/assets/"
    cp -a "$CS_TMP/repos/." "$1/repos/"
}
csqtt_pm_install() {
    # First argument is an isolated root, or '-' for the live package database.
    CS_PM_ROOT=$1; CS_PM_BUNDLE=$2; CS_PM_DOWNGRADE=$3
    set --
    CS_N=0
    while [ "$CS_N" -lt 3 ]; do
        CS_FILE=$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.packages[$CS_N].name")
        set -- "$@" "$CS_PM_BUNDLE/assets/$CS_FILE"
        CS_N=$((CS_N + 1))
    done
    if [ "$CS_PM" = opkg ]; then
        CS_N=0
        while [ "$CS_PM_DOWNGRADE" = 0 ] && [ -n "$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N]")" ]; do
            CS_FILE=$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N].name")
            set -- "$@" "$CS_PM_BUNDLE/assets/$CS_FILE"; CS_N=$((CS_N + 1))
        done
        if [ "$CS_PM_ROOT" = - ]; then
            if [ "$CS_PM_DOWNGRADE" = 1 ]; then csqtt_opkg --force-downgrade install "$@"; else csqtt_opkg install "$@"; fi
        else
            # Native opkg skips all maintainer scripts for an offline root.
            if [ "$CS_PM_DOWNGRADE" = 1 ]; then csqtt_opkg --offline-root "$CS_PM_ROOT" --force-downgrade install "$@"; else csqtt_opkg --offline-root "$CS_PM_ROOT" install "$@"; fi
        fi
    else
        CS_N=0
        while [ "$CS_PM_DOWNGRADE" = 0 ] && [ -n "$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N]")" ]; do
            CS_DEP=$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N].package")
            CS_VERSION=$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N].version")
            set -- "$@" "$CS_DEP=$CS_VERSION"; CS_N=$((CS_N + 1))
        done
        CS_REPOSITORIES="$CS_PM_BUNDLE/repositories"
        [ "$CS_PM_DOWNGRADE" = 0 ] || CS_REPOSITORIES="$CS_TMP/empty-repositories"
        if [ "$CS_PM_ROOT" = - ]; then
            apk --repositories-file "$CS_REPOSITORIES" --keys-dir "$CS_TMP/keys" --no-network add "$@"
        else
            apk --root "$CS_PM_ROOT" --arch "$CS_ARCH" --repositories-file "$CS_REPOSITORIES" --keys-dir etc/apk/keys --no-network --no-scripts add "$@"
        fi
    fi
}
csqtt_validate_tuple() {
    [ "$(csqtt_j "$1" '@.schema')" = 2 ] && [ "$(csqtt_j "$1" '@.upstream')" = amurcanov/csqtt@v2.1.9 ] || csqtt_portable_die 'Unsupported portable manifest'
    for CS_KEY in family openwrt target architecture package_manager package_format; do
        [ "$(csqtt_j "$1" "@.platform.$CS_KEY")" = "$(csqtt_j "$CS_TMP/probe.json" "@.$CS_KEY")" ] || csqtt_portable_die 'Exact platform tuple mismatch'
    done
    if [ "$CS_FAMILY" = glinet ]; then
        for CS_KEY in firmware board; do
            [ "$(csqtt_j "$1" "@.platform.$CS_KEY")" = "$(csqtt_j "$CS_TMP/probe.json" "@.$CS_KEY")" ] || csqtt_portable_die 'Exact vendor firmware mismatch'
        done
    fi
    [ "$(csqtt_j "$1" '@.profile_id')" = "$CS_PROFILE" ] && [ "$(csqtt_j "$1" '@.backend')" = "$CS_BACKEND" ] || csqtt_portable_die 'Profile/backend mismatch'
    [ "$(csqtt_j "$1" '@.qualification.installation')" = true ] && [ "$(csqtt_j "$1" '@.qualification.activation')" = true ] && [ -n "$(csqtt_j "$1" '@.qualification.evidence[0]')" ] || csqtt_portable_die 'This exact profile has not passed installation and activation acceptance'
    [ -n "$(csqtt_j "$1" '@.requirements.kernel_package')" ] && [ "$(csqtt_j "$1" '@.requirements.kernel_package')" = "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" ] || csqtt_portable_die 'Running kernel package ABI mismatch'
    [ "$(csqtt_j "$1" '@.dns_binary')" = /usr/libexec/csqtt/dnsmasq ] || csqtt_portable_die 'Portable profiles require isolated CSQTT DNS'
    [ -z "$(csqtt_j "$1" '@.packages[3]')" ] || csqtt_portable_die 'Unexpected router package count'
    CS_ROLES=' '
    CS_N=0
    while [ "$CS_N" -lt 3 ]; do
        CS_ROLE=$(csqtt_j "$1" "@.packages[$CS_N].role")
        CS_FILE=$(csqtt_j "$1" "@.packages[$CS_N].name")
        CS_VERSION=$(csqtt_j "$1" "@.packages[$CS_N].version")
        case "$CS_ROLE" in csqtt|csqtt-captcha|luci-app-csqtt) ;; *) csqtt_portable_die 'Invalid package role' ;; esac
        case "$CS_ROLES" in *" $CS_ROLE "*) csqtt_portable_die 'Duplicate package role' ;; esac
        CS_ROLES="$CS_ROLES$CS_ROLE "
        csqtt_token "$CS_FILE" && csqtt_token "$CS_VERSION" || csqtt_portable_die 'Invalid package identity'
        case "$CS_FILE" in "$CS_PROFILE"--*."$CS_FORMAT") ;; *) csqtt_portable_die 'Package asset is not scoped to exact profile' ;; esac
        CS_N=$((CS_N + 1))
    done
}
csqtt_bundle_sources() {
    : > "$CS_TMP/repositories"
    CS_I=0
    while [ -n "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I]")" ]; do
        [ "$CS_I" -lt 16 ] || csqtt_portable_die 'Too many dependency indexes'
        CS_ID=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].id")
        csqtt_token "$CS_ID" && [ ! -e "$CS_TMP/repos/$CS_ID" ] || csqtt_portable_die 'Unsafe/duplicate dependency index'
        CS_SOURCE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].repository")
        case "$CS_FAMILY:$CS_SOURCE" in official:https://downloads.openwrt.org/*|glinet:https://fw.gl-inet.com/*|glinet:https://dl.gl-inet.com/*) ;; *) csqtt_portable_die 'Foreign distribution feed refused' ;; esac
        CS_KEY_HASH=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].key_sha256")
        csqtt_hash "$CS_KEY_HASH" || csqtt_portable_die 'Missing dependency source key pin'
        mkdir -p "$CS_TMP/repos/$CS_ID" "$CS_TMP/sourcekeys/$CS_ID"
        CS_SOURCE_KEY=
        if [ "$CS_PM" = apk ]; then CS_KEY_PATHS='/lib/apk/keys/* /etc/apk/keys/*'; else CS_KEY_PATHS='/etc/opkg/keys/*'; fi
        # Only local distro keys matching the signed exact fingerprint qualify.
        for CS_KEY_FILE in $CS_KEY_PATHS; do
            [ -f "$CS_KEY_FILE" ] || continue
            CS_ACTUAL_HASH=$(sha256sum "$CS_KEY_FILE" | awk '{ print $1 }')
            if [ "$CS_ACTUAL_HASH" = "$CS_KEY_HASH" ]; then CS_SOURCE_KEY=$CS_KEY_FILE; break; fi
        done
        [ -n "$CS_SOURCE_KEY" ] || csqtt_portable_die 'Authenticated distribution source key is unavailable'
        cp "$CS_SOURCE_KEY" "$CS_TMP/sourcekeys/$CS_ID/source.key"
        csqtt_asset "@.dependency_bundle.indexes[$CS_I]"
        CS_INDEX_NAME=$CS_ASSET_NAME
        if [ "$CS_PM" = apk ]; then
            [ "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].format")" = apk-adb ] || csqtt_portable_die 'Wrong dependency index format'
            apk --keys-dir "$CS_TMP/sourcekeys/$CS_ID" verify "$CS_TMP/assets/$CS_INDEX_NAME" >"$CS_TMP/index-$CS_I.log" 2>&1 || csqtt_portable_die 'Dependency index signature failed'
            cp "$CS_TMP/assets/$CS_INDEX_NAME" "$CS_TMP/repos/$CS_ID/packages.adb"
            printf 'file://%s/repos/%s/packages.adb\n' "$CS_TMP" "$CS_ID" >> "$CS_TMP/repositories"
        else
            [ "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].format")" = opkg ] || csqtt_portable_die 'Wrong dependency index format'
            command -v usign >/dev/null || csqtt_portable_die 'Native distribution index verifier is missing'
            csqtt_asset "@.dependency_bundle.indexes[$CS_I].signature"
            usign -V -p "$CS_SOURCE_KEY" -m "$CS_TMP/assets/$CS_INDEX_NAME" -x "$CS_TMP/assets/$CS_ASSET_NAME" >"$CS_TMP/index-$CS_I.log" 2>&1 || csqtt_portable_die 'Dependency index signature failed'
            cp "$CS_TMP/assets/$CS_INDEX_NAME" "$CS_TMP/repos/$CS_ID/Packages"
        fi
        CS_I=$((CS_I + 1))
    done
    CS_I=0; : > "$CS_TMP/new-dependencies"
    while [ -n "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I]")" ]; do
        [ "$CS_I" -lt 64 ] || csqtt_portable_die 'Too many dependency packages'
        CS_DEP=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].package")
        CS_VERSION=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].version")
        CS_ID=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].index")
        CS_FILE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].filename")
        csqtt_token "$CS_DEP" && csqtt_token "$CS_VERSION" && csqtt_token "$CS_ID" && csqtt_token "$CS_FILE" || csqtt_portable_die 'Unsafe dependency identity'
        case "$CS_DEP" in kernel|kmod-*|dnsmasq*|firewall*|procd|netifd|csqtt|csqtt-captcha|luci-app-csqtt) csqtt_portable_die 'System kernel/DNS/firewall/service replacement is forbidden' ;; esac
        [ -d "$CS_TMP/repos/$CS_ID" ] || csqtt_portable_die 'Dependency source index is missing'
        [ ! -e "$CS_TMP/repos/$CS_ID/$CS_FILE" ] || csqtt_portable_die 'Duplicate dependency package'
        CS_INSTALLED=$(csqtt_installed_version "$CS_DEP")
        [ -z "$CS_INSTALLED" ] || [ "$CS_INSTALLED" = "$CS_VERSION" ] || csqtt_portable_die 'Dependency bundle would upgrade an installed system package'
        [ -n "$CS_INSTALLED" ] || printf '%s\n' "$CS_DEP" >> "$CS_TMP/new-dependencies"
        csqtt_asset "@.dependency_bundle.packages[$CS_I]"
        if [ "$CS_PM" = opkg ]; then
            CS_DIGEST=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].sha256")
            CS_SIZE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].size")
            awk -v pkg="$CS_DEP" -v ver="$CS_VERSION" -v file="$CS_FILE" -v hash="$CS_DIGEST" -v bytes="$CS_SIZE" -v arch="$CS_ARCH" '
              BEGIN { RS=""; FS="\n" } { for(k in f) delete f[k]; for(i=1;i<=NF;i++){ p=index($i,": "); if(p) f[substr($i,1,p-1)]=substr($i,p+2) }
                if(f["Package"]==pkg && f["Version"]==ver && f["Filename"]==file && f["SHA256sum"]==hash && f["Size"]==bytes && (f["Architecture"]==arch || f["Architecture"]=="all")) matches++ }
              END { exit matches!=1 }' "$CS_TMP/repos/$CS_ID/Packages" || csqtt_portable_die 'Dependency bytes are not bound to the signed distribution index'
        fi
        cp "$CS_TMP/assets/$CS_ASSET_NAME" "$CS_TMP/repos/$CS_ID/$CS_FILE"
        CS_I=$((CS_I + 1))
    done
}
csqtt_portable_cleanup() {
    CS_EXIT=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$CS_CHANGED" = 1 ]; then
        printf 'CSQTT: restoring the authenticated previous package state offline\n' >&2
        if [ "$CS_UPGRADE" = 1 ]; then
            csqtt_pm_install - "$CS_TMP/previous" 1 >> "$CS_TMP/rollback.log" 2>&1
            CS_RESTORED=$?
        else
            if [ "$CS_PM" = apk ]; then apk --repositories-file "$CS_TMP/repositories" --keys-dir "$CS_TMP/keys" --no-network del luci-app-csqtt csqtt-captcha csqtt >> "$CS_TMP/rollback.log" 2>&1
            else csqtt_opkg remove luci-app-csqtt csqtt-captcha csqtt >> "$CS_TMP/rollback.log" 2>&1; fi
            CS_RESTORED=$?
        fi
        if [ "$CS_RESTORED" = 0 ]; then
            set --
            while IFS= read -r CS_DEP; do
                [ -n "$CS_DEP" ] || continue
                set -- "$@" "$CS_DEP"
            done < "$CS_TMP/new-dependencies"
            if [ "$#" -gt 0 ]; then
                if [ "$CS_PM" = apk ]; then apk --repositories-file "$CS_TMP/empty-repositories" --keys-dir "$CS_TMP/keys" --no-network del "$@" >> "$CS_TMP/rollback.log" 2>&1
                else csqtt_opkg remove "$@" >> "$CS_TMP/rollback.log" 2>&1; fi
                [ "$?" = 0 ] || CS_RESTORED=1
            fi
            csqtt_snapshot - > "$CS_TMP/packages-rolled-back"
            csqtt_exact_packages "$CS_TMP/packages-before" "$CS_TMP/packages-rolled-back" || CS_RESTORED=1
            for CS_CONFIG in csqtt dhcp firewall network; do
                [ ! -f "$CS_BACKUP/config/$CS_CONFIG" ] || cp -p "$CS_BACKUP/config/$CS_CONFIG" "/etc/config/$CS_CONFIG"
            done
            if [ "$CS_PM" = apk ]; then cp "$CS_BACKUP/world" /etc/apk/world; fi
            [ ! -f "$CS_BACKUP/platform.json" ] || cp "$CS_BACKUP/platform.json" /etc/csqtt/platform.json
            [ -f "$CS_BACKUP/platform.json" ] || rm -f /etc/csqtt/platform.json
            if [ "$CS_RESTORED" = 0 ]; then printf 'rollback_complete\n' > "$CS_BACKUP/phase"; printf 'CSQTT: package rollback completed; guarded service recovery needs inspection\n' >&2
            else printf 'rollback_incomplete\n' > "$CS_BACKUP/phase"; printf 'CSQTT: rollback package inventory differs; inspect the private backup\n' >&2; fi
        else printf 'CSQTT: rollback failed; keep guards and inspect the private backup\n' >&2; fi
    fi
    if [ "$CS_LOCKED" = 1 ]; then rm -f /var/lock/csqtt-maintenance/pid; rmdir /var/lock/csqtt-maintenance 2>/dev/null; fi
    if [ "$CS_EXIT" = 0 ]; then rm -rf "$CS_TMP"; else printf 'CSQTT: private diagnostics retained at %s\n' "$CS_TMP" >&2; fi
    exit "$CS_EXIT"
}
csqtt_portable_main() (
    set -eu; umask 077
    [ "$(id -u)" = 0 ] || csqtt_portable_die 'Run as root on the router'
    for CS_TOOL in openssl jsonfilter uclient-fetch sha256sum awk tar; do command -v "$CS_TOOL" >/dev/null || csqtt_portable_die "Required verifier/tool is missing: $CS_TOOL"; done
    unset OFFLINE_ROOT
    APK_CONFIG=/dev/null; export APK_CONFIG
    CS_RELEASE=${1:-latest}; csqtt_token "$CS_RELEASE" || csqtt_portable_die 'Invalid release version'
    CS_BASE="https://github.com/RATOR2000/csqtt-openwrt/releases/download/$CS_RELEASE"
    [ "$CS_RELEASE" != latest ] || CS_BASE=https://github.com/RATOR2000/csqtt-openwrt/releases/latest/download
    CS_TMP=$(mktemp -d /tmp/csqtt-portable.XXXXXX)
    CS_CHANGED=0 CS_LOCKED=0 CS_UPGRADE=0 CS_BACKUP=
    trap csqtt_portable_cleanup EXIT; trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM
    mkdir -p "$CS_TMP/assets" "$CS_TMP/keys" "$CS_TMP/projectkeys" "$CS_TMP/no-repositories" "$CS_TMP/repos" "$CS_TMP/sourcekeys"
    : > "$CS_TMP/empty-repositories"
    csqtt_probe_main > "$CS_TMP/probe.json"
    CS_PROFILE=$(csqtt_j "$CS_TMP/probe.json" '@.profile_id') CS_FAMILY=$(csqtt_j "$CS_TMP/probe.json" '@.family')
    CS_PM=$(csqtt_j "$CS_TMP/probe.json" '@.package_manager') CS_FORMAT=$(csqtt_j "$CS_TMP/probe.json" '@.package_format')
    CS_ARCH=$(csqtt_j "$CS_TMP/probe.json" '@.architecture') CS_BACKEND=$(csqtt_j "$CS_TMP/probe.json" '@.backend')
    csqtt_token "$CS_PROFILE" && csqtt_token "$CS_ARCH" || csqtt_portable_die 'Unknown or inconsistent package architecture'
    case "$CS_FAMILY:$CS_PM" in official:apk|official:opkg|glinet:opkg) ;; *) csqtt_portable_die 'Unknown distribution/package-manager profile' ;; esac
    cat > "$CS_TMP/project.pem" <<'CSQTT_PORTABLE_PUBLIC_KEY'
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETbV/mfygOtiJtOEqpvRlAazQEvb+
a2Y1lNcDNcPmDYDRB45yTNUvn6Ree4/eg+bWWf5kQeavIZvOLDB8iIcP4w==
-----END PUBLIC KEY-----
CSQTT_PORTABLE_PUBLIC_KEY
    cp "$CS_TMP/project.pem" "$CS_TMP/projectkeys/csqtt-public.pem"
    csqtt_fetch catalogue.json "$CS_TMP/catalogue.json"; csqtt_fetch catalogue.sig "$CS_TMP/catalogue.sig"
    [ "$(wc -c < "$CS_TMP/catalogue.json")" -le 262144 ] || csqtt_portable_die 'Catalogue is too large'
    csqtt_signature "$CS_TMP/catalogue.json" "$CS_TMP/catalogue.sig"
    [ "$(csqtt_j "$CS_TMP/catalogue.json" '@.schema')" = 2 ] && [ "$(csqtt_j "$CS_TMP/catalogue.json" '@.upstream')" = amurcanov/csqtt@v2.1.9 ] || csqtt_portable_die 'Unsupported release catalogue'
    CS_I=0 CS_MATCH=-1
    while [ -n "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_I]")" ]; do
        [ "$CS_I" -lt 128 ] || csqtt_portable_die 'Too many catalogue profiles'
        if [ "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_I].profile_id")" = "$CS_PROFILE" ]; then
            [ "$CS_MATCH" = -1 ] || csqtt_portable_die 'Ambiguous catalogue profile'; CS_MATCH=$CS_I
        fi
        CS_I=$((CS_I + 1))
    done
    [ "$CS_MATCH" != -1 ] || csqtt_portable_die 'No qualified release exists for this exact firmware/architecture'
    CS_MANIFEST_NAME=$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].name")
    CS_SIGNATURE_NAME=$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.name")
    [ "$CS_MANIFEST_NAME" = "$CS_PROFILE-manifest.json" ] && [ "$CS_SIGNATURE_NAME" = "$CS_PROFILE-manifest.sig" ] || csqtt_portable_die 'Unsafe tuple metadata names'
    CS_MANIFEST="$CS_TMP/manifest.json"
    csqtt_fetch "$CS_MANIFEST_NAME" "$CS_MANIFEST"; csqtt_fetch "$CS_SIGNATURE_NAME" "$CS_TMP/manifest.sig"
    [ "$(wc -c < "$CS_MANIFEST")" -le 262144 ] || csqtt_portable_die 'Tuple manifest is too large'
    csqtt_bytes "$CS_MANIFEST" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].sha256")" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].size")"
    csqtt_bytes "$CS_TMP/manifest.sig" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.sha256")" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.size")"
    csqtt_signature "$CS_MANIFEST" "$CS_TMP/manifest.sig"
    csqtt_validate_tuple "$CS_MANIFEST"
    for CS_RESOURCE in overlay_free_kib tmp_free_kib mem_available_kib; do
        CS_MIN=$(csqtt_j "$CS_MANIFEST" "@.requirements.$CS_RESOURCE") CS_NOW=$(csqtt_j "$CS_TMP/probe.json" "@.resource.$CS_RESOURCE")
        csqtt_uint "$CS_MIN" && csqtt_uint "$CS_NOW" && [ "$CS_MIN" -gt 0 ] && [ "$CS_NOW" -ge "$CS_MIN" ] || csqtt_portable_die 'Insufficient resources for the accepted profile'
    done
    printf 'dest root /\narch all 1\narch %s 10\noption check_signature 1\n' "$CS_ARCH" > "$CS_TMP/opkg.conf"
    if [ "$CS_PM" = apk ]; then
        for CS_KEY_FILE in /lib/apk/keys/* /etc/apk/keys/*; do [ ! -f "$CS_KEY_FILE" ] || cp "$CS_KEY_FILE" "$CS_TMP/keys/"; done
        cp "$CS_TMP/project.pem" "$CS_TMP/keys/csqtt-public.pem"
    fi
    CS_I=0
    while [ "$CS_I" -lt 3 ]; do csqtt_asset "@.packages[$CS_I]"; if [ "$CS_PM" = apk ]; then apk --keys-dir "$CS_TMP/projectkeys" verify "$CS_TMP/assets/$CS_ASSET_NAME" >"$CS_TMP/package-$CS_I.log" 2>&1 || csqtt_portable_die 'Native package signature failed'; fi; CS_I=$((CS_I + 1)); done
    csqtt_bundle_sources
    for CS_DEP in $(csqtt_j "$CS_MANIFEST" '@.requirements.packages[*]'); do
        csqtt_token "$CS_DEP" || csqtt_portable_die 'Invalid required package'
        if [ -z "$(csqtt_installed_version "$CS_DEP")" ]; then
            CS_FOUND=false
            for CS_BUNDLED in $(csqtt_j "$CS_MANIFEST" '@.dependency_bundle.packages[*].package'); do [ "$CS_DEP" != "$CS_BUNDLED" ] || CS_FOUND=true; done
            [ "$CS_FOUND" = true ] || csqtt_portable_die 'Required firmware dependency is missing; provide a verified dependency bundle'
        fi
    done
    CS_COUNT=0
    for CS_ROLE in csqtt csqtt-captcha luci-app-csqtt; do [ -z "$(csqtt_installed_version "$CS_ROLE")" ] || CS_COUNT=$((CS_COUNT + 1)); done
    [ "$CS_COUNT" = 0 ] || [ "$CS_COUNT" = 3 ] || csqtt_portable_die 'Existing router packages are incomplete'
    if [ "$CS_COUNT" = 3 ]; then
        CS_UPGRADE=1
        [ -f /etc/csqtt/releases/current/manifest.json ] && [ -f /etc/csqtt/releases/current/manifest.sig ] || csqtt_portable_die 'Upgrade requires the previous authenticated offline package bundle'
        mkdir -p "$CS_TMP/previous"; cp -a /etc/csqtt/releases/current/. "$CS_TMP/previous/"
        csqtt_signature "$CS_TMP/previous/manifest.json" "$CS_TMP/previous/manifest.sig"
        csqtt_validate_tuple "$CS_TMP/previous/manifest.json"
        CS_I=0
        while [ "$CS_I" -lt 3 ]; do
            CS_FILE=$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_I].name")
            CS_ROLE=$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_I].role")
            [ "$(csqtt_installed_version "$CS_ROLE")" = "$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_I].version")" ] || csqtt_portable_die 'Previous bundle does not match installed package versions'
            csqtt_bytes "$CS_TMP/previous/assets/$CS_FILE" "$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_I].sha256")" "$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_I].size")"
            CS_I=$((CS_I + 1))
        done
    fi
    csqtt_snapshot - > "$CS_TMP/packages-before"
    csqtt_clone "$CS_TMP/stage"
    csqtt_pm_install "$CS_TMP/stage" "$CS_TMP" 0 > "$CS_TMP/stage.log" 2>&1 || csqtt_portable_die 'Offline dependency/package transaction failed in the isolated root'
    csqtt_check_versions "$CS_TMP/stage" "$CS_TMP" || csqtt_portable_die 'Staged package identities or installed states are inconsistent'
    csqtt_snapshot "$CS_TMP/stage" > "$CS_TMP/packages-staged"
    csqtt_unchanged_packages "$CS_TMP/packages-before" "$CS_TMP/packages-staged" || csqtt_portable_die 'Transaction changes unrelated installed packages'
    if [ "$CS_UPGRADE" = 1 ]; then
        csqtt_pm_install "$CS_TMP/stage" "$CS_TMP/previous" 1 > "$CS_TMP/restore-proof.log" 2>&1 || csqtt_portable_die 'Previous packages cannot be restored offline'
        csqtt_check_versions "$CS_TMP/stage" "$CS_TMP/previous" || csqtt_portable_die 'Previous package state was not restored offline'
    fi
    mkdir -p /var/lock
    mkdir /var/lock/csqtt-maintenance 2>/dev/null || csqtt_portable_die 'CSQTT maintenance is already active'
    CS_LOCKED=1; printf '%s\n' "$$" > /var/lock/csqtt-maintenance/pid
    if [ -r /usr/libexec/csqtt/lifecycle.sh ]; then ( . /usr/libexec/csqtt/lifecycle.sh; csqtt_operation_enter ) || csqtt_portable_die 'Cannot wait for the current operation'; fi
    CS_BACKUP="/etc/csqtt/backups/portable-$(date +%Y%m%d-%H%M%S)-$$"
    mkdir -p "$CS_BACKUP/config"; chmod 0700 /etc/csqtt /etc/csqtt/backups "$CS_BACKUP"
    for CS_CONFIG in csqtt dhcp firewall network; do [ ! -f "/etc/config/$CS_CONFIG" ] || cp -p "/etc/config/$CS_CONFIG" "$CS_BACKUP/config/$CS_CONFIG"; done
    [ ! -f /etc/csqtt/platform.json ] || cp /etc/csqtt/platform.json "$CS_BACKUP/platform.json"
    [ "$CS_PM" != apk ] || cp /etc/apk/world "$CS_BACKUP/world"
    csqtt_copy_bundle "$CS_BACKUP/transaction"
    [ "$CS_UPGRADE" = 0 ] || cp -a "$CS_TMP/previous" "$CS_BACKUP/previous"
    cp "$CS_TMP/probe.json" "$CS_TMP/packages-before" "$CS_BACKUP/"
    printf 'prepared\n' > "$CS_BACKUP/phase"
    CS_CHANGED=1
    csqtt_pm_install - "$CS_TMP" 0 > "$CS_TMP/install.log" 2>&1 || csqtt_portable_die 'Offline package installation failed'
    csqtt_check_versions - "$CS_TMP" || csqtt_portable_die 'Installed package identities or states are inconsistent'
    csqtt_snapshot - > "$CS_TMP/packages-installed"
    csqtt_unchanged_packages "$CS_TMP/packages-before" "$CS_TMP/packages-installed" || csqtt_portable_die 'Installed transaction changed unrelated packages'
    printf 'packages_installed\n' > "$CS_BACKUP/phase"
    # Persist the exact signed capability grant before runtime activation.
    printf '{"schema":1,"profile_id":"%s","family":"%s","firmware":"%s","openwrt":"%s","board":"%s","target":"%s","architecture":"%s","package_manager":"%s","backend":"%s","kernel":"%s","kernel_package":"%s","qualification":{"activation":true},"dns_binary":"/usr/libexec/csqtt/dnsmasq"}\n' \
      "$CS_PROFILE" "$CS_FAMILY" "$(csqtt_j "$CS_TMP/probe.json" '@.firmware')" "$(csqtt_j "$CS_TMP/probe.json" '@.openwrt')" "$(csqtt_j "$CS_TMP/probe.json" '@.board')" "$(csqtt_j "$CS_TMP/probe.json" '@.target')" "$CS_ARCH" "$CS_PM" "$CS_BACKEND" "$(csqtt_j "$CS_TMP/probe.json" '@.kernel')" "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" > /etc/csqtt/platform.json.new
    chmod 0600 /etc/csqtt/platform.json.new; mv /etc/csqtt/platform.json.new /etc/csqtt/platform.json
    /etc/init.d/rpcd restart > "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'RPC service restart failed'
    if [ "$CS_UPGRADE" = 1 ]; then /etc/init.d/csqtt restart >> "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Transport restart failed'; fi
    for CS_SERVICE in csqtt-captcha csqtt-health; do "/etc/init.d/$CS_SERVICE" enable >> "$CS_TMP/service.log" 2>&1 && "/etc/init.d/$CS_SERVICE" restart >> "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Companion service restart failed'; done
    mkdir -p /etc/csqtt/releases
    CS_CURRENT="/etc/csqtt/releases/accepted-$(date +%Y%m%d-%H%M%S)-$$"
    csqtt_copy_bundle "$CS_CURRENT"
    [ ! -e /etc/csqtt/releases/current ] || mv /etc/csqtt/releases/current "$CS_BACKUP/previous-current"
    mv "$CS_CURRENT" /etc/csqtt/releases/current
    printf 'committed\n' > "$CS_BACKUP/phase"
    CS_CHANGED=0
    printf 'CSQTT installed for the accepted exact profile. Private backup: %s\n' "$CS_BACKUP"
)
case "${1:-}" in
    --check|--preflight) csqtt_probe_main; exit $? ;;
    --portable) shift; csqtt_portable_main "${1:-latest}"; exit $? ;;
esac
# Exact signed9 compatibility remains on its original transaction path.
CS_DISPATCH_RELEASE=$(csqtt_release_value /etc/openwrt_release DISTRIB_RELEASE)
CS_DISPATCH_TARGET=$(csqtt_release_value /etc/openwrt_release DISTRIB_TARGET)
CS_DISPATCH_ARCH=$(csqtt_release_value /etc/openwrt_release DISTRIB_ARCH)
CS_DISPATCH_VENDOR=$(csqtt_metadata_line /etc/glversion)
if [ "$CS_DISPATCH_RELEASE:$CS_DISPATCH_TARGET:$CS_DISPATCH_ARCH:$CS_DISPATCH_VENDOR" != '25.12.5:mediatek/filogic:aarch64_cortex-a53:' ]; then
    csqtt_portable_main "${1:-latest}"; exit $?
fi
# END PORTABLE INSTALLER
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
DISTRIB_RELEASE=$(csqtt_release_value /etc/openwrt_release DISTRIB_RELEASE)
DISTRIB_TARGET=$(csqtt_release_value /etc/openwrt_release DISTRIB_TARGET)
DISTRIB_ARCH=$(csqtt_release_value /etc/openwrt_release DISTRIB_ARCH)
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
MAINTENANCE_OWNED=0
cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$status" -ne 0 ] && [ "$DNS_REMOVED" = 1 ]; then
        echo 'Restoring the previous DNS package after failed installation.' >&2
        # Replacement is allowed only on a first install, so these roots did
        # not exist before the transaction. Keep configs and fail-closed guards.
        apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/cache" --no-network del csqtt-captcha luci-app-csqtt csqtt dnsmasq-full >> "$TMP/rollback.txt" 2>&1 || true
        # Official OpenWrt APKs are unsigned. Their identity is authenticated
        # by the signed index retained with the original hashed cache file.
        if apk --repositories-file "$TMP/repositories" --keys-dir "$TMP/keys" --cache-dir "$TMP/rollback-cache" --no-network add "dnsmasq=$DNS_VERSION" >> "$TMP/rollback.txt" 2>&1; then
            if [ -f "$BACKUP/dhcp" ]; then
                cp -p "$BACKUP/dhcp" /etc/config/dhcp || echo 'Cannot restore the DHCP configuration; inspect the private backup.' >&2
            fi
            cp -p "$BACKUP/world" /etc/apk/world || echo 'Cannot restore APK world; inspect the private backup.' >&2
            /etc/init.d/dnsmasq restart >> "$TMP/rollback.txt" 2>&1 || echo 'DNS service restart failed; inspect rollback.txt.' >&2
        else
            echo "Automatic DNS restore failed. Original DNS cache and signed indexes: $TMP/rollback-cache" >&2
        fi
    fi
    if [ "$MAINTENANCE_OWNED" = 1 ]; then
        rm -f /var/lock/csqtt-maintenance/pid
        rmdir /var/lock/csqtt-maintenance 2>/dev/null || true
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
mkdir -p "$TMP/packages" "$TMP/release-keys" "$TMP/keys" "$TMP/rollback-cache" "$TMP/cache"
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
stage_read() { apk --root "$STAGE" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk "$@"; }
stage_info() { stage_read --no-network info --from installed; }
stage_packages() {
    stage_read --no-network query --installed --all-matches --fields package --format json '*' > "$TMP/stage-packages.json"
    jsonfilter -i "$TMP/stage-packages.json" -e '@[*].package'
}
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
    [ "$DNS_PACKAGE" = "dnsmasq-$DNS_VERSION" ] || die 'Installed DNS package identity is inconsistent.'
    # OpenWrt signs repository indexes, not individual DNS APKs. Retain the
    # trusted index and its authenticated package under APK's hashed cache name.
    # A read-only fetch alone does not refresh a missing index cache.
    stage_read update > "$TMP/dns-cache.txt" 2>&1 || die 'Cannot cache signed OpenWrt repository indexes.'
    # Recursive selection uses the solver: APK 3.0.5's ordinary query path
    # compares the package name with the full name=version string and misses it.
    stage_read fetch --recursive --pkgname-spec '${name}-${version}.${hash:8}.apk' --output "$STAGE/var/cache/apk" "dnsmasq=$DNS_VERSION" >> "$TMP/dns-cache.txt" 2>&1 || die 'The exact original DNS package must be cached before replacement.'
    # APK fetch can exit zero after a solver failure without downloading a file.
    DNS_CACHE_FILE=
    for CACHED in "$STAGE/var/cache/apk/$DNS_PACKAGE."*.apk; do
        [ -f "$CACHED" ] || continue
        [ -z "$DNS_CACHE_FILE" ] || die 'Original DNS package cache is ambiguous.'
        DNS_CACHE_FILE=$CACHED
    done
    [ -n "$DNS_CACHE_FILE" ] || die 'Original DNS package cache is missing.'
    cp -a "$STAGE/var/cache/apk/." "$TMP/rollback-cache/"
    stage_packages > "$TMP/packages-before.txt"
    stage_info > "$TMP/installed-before.txt"
    stage_apk del --simulate dnsmasq > "$TMP/dns-remove.txt" 2>&1 || die 'Cannot safely replace the current DNS package.'
    stage_apk del dnsmasq >> "$TMP/dns-remove.txt" 2>&1 || die 'DNS replacement preflight failed.'
    stage_info > "$TMP/installed-after.txt"
    awk 'NR==FNR { kept[$0]=1; next } $0 != "dnsmasq" && !($0 in kept) { bad=1 } END { exit bad }' "$TMP/installed-after.txt" "$TMP/installed-before.txt" || die 'DNS replacement would remove other installed packages.'
    # Actually restore into another disposable root, with networking and
    # package scripts disabled. This checks signed-index identity and payload
    # hashes; standalone verify cannot authenticate an unsigned official APK.
    FORWARD_STAGE=$STAGE
    STAGE="$TMP/restore"
    mkdir -p "$STAGE"
    cp -aL "$FORWARD_STAGE/." "$STAGE/"
    cp -a "$TMP/rollback-cache/." "$STAGE/var/cache/apk/"
    stage_apk --no-network add "dnsmasq=$DNS_VERSION" > "$TMP/dns-restore-check.txt" 2>&1 || die 'Original DNS cannot be restored from its signed index and cache offline.'
    stage_packages > "$TMP/packages-restored.txt"
    awk 'NR==FNR { original[$0]=1; next } !($0 in original) { bad=1 } { delete original[$0] } END { for (package in original) bad=1; exit bad }' "$TMP/packages-before.txt" "$TMP/packages-restored.txt" || die 'Original DNS restore would change other installed package versions.'
    STAGE=$FORWARD_STAGE
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
# Exclude automatic recovery throughout live replacement and service restarts.
# Refuse an existing marker rather than deleting another installer's state.
mkdir -p /var/lock
mkdir /var/lock/csqtt-maintenance 2>/dev/null || die 'CSQTT maintenance is already active.'
MAINTENANCE_OWNED=1
printf '%s\n' "$$" > /var/lock/csqtt-maintenance/pid
# Wait for an already admitted operation; do not hold its lock across APK
# package scripts or init actions. The marker excludes new recovery admissions.
if [ -r /usr/libexec/csqtt/lifecycle.sh ]; then
    ( . /usr/libexec/csqtt/lifecycle.sh; csqtt_operation_enter ) || die 'Cannot wait for the current CSQTT operation.'
fi
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
/etc/init.d/csqtt-health enable || die 'Health monitor enable failed.'
/etc/init.d/csqtt-health restart || die 'Health monitor restart failed.'
# Persist the public key for future package operations only after success.
mkdir -p /etc/apk/keys
cp "$TMP/release-keys/csqtt-public.pem" /etc/apk/keys/csqtt-public.pem
DNS_REMOVED=0
echo "CSQTT installed. Open Services → CSQTT in LuCI. Configuration backup: $BACKUP"
