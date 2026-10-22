#!/bin/sh
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
