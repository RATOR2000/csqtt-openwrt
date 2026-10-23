#!/bin/sh
# Public, read-only platform facts. Never evaluate firmware-owned release files.
# Regex strings avoid BusyBox/GNU differences parsing slash in literal classes.
csqtt_release_value() {
    [ -r "$1" ] || return 0
    awk -v wanted="$2" '
      { line=$0; sub(/\r$/, "", line); p=index(line,"="); if (!p) next;
        key=substr(line,1,p-1); gsub(/^[ \t]+|[ \t]+$/, "", key);
        if (key != wanted) next;
        value=substr(line,p+1); gsub(/^[ \t]+|[ \t]+$/, "", value);
        if (value ~ /^\047.*\047$/ || value ~ /^".*"$/) value=substr(value,2,length(value)-2);
        if (value ~ "^[A-Za-z0-9_.+:/,@-]+$" && length(value)<=160) print value;
        exit;
      }' "$1"
}
csqtt_metadata_line() {
    [ -r "$1" ] || return 0
    awk 'NR==1 { sub(/\r$/, ""); if ($0 ~ "^[A-Za-z0-9_.+:/,@-]+$" && length($0)<=160) print; exit }' "$1"
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
        else
            CS_KERNEL_PACKAGE=$(apk query --installed --match name --fields version --format default kernel 2>/dev/null | awk '/^Version: [A-Za-z0-9_.+~-]+$/ {print $2;exit}' || true)
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
    CS_PRIVATE_NFTSET=false
    if [ -x /usr/libexec/csqtt/dnsmasq ]; then
        if /usr/libexec/csqtt/dnsmasq --version 2>/dev/null | awk '/(^|[[:space:]])nftset([[:space:]]|$)/ { found=1 } END { exit !found }'; then CS_PRIVATE_NFTSET=true; fi
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
    printf '{"schema":1,"profile_id":"%s","family":"%s","firmware":"%s","openwrt":"%s","board":"%s","target":"%s","architecture":"%s","package_manager":"%s","package_format":"%s","kernel":"%s","kernel_package":"%s","backend":"%s","readiness":"unqualified","resource":{"mem_total_kib":%s,"mem_available_kib":%s,"overlay_free_kib":%s,"tmp_free_kib":%s,"cpu_count":%s},"capabilities":{"ucode":%s,"nft":%s,"fw4":%s,"fw3":%s,"procd":%s,"netifd":%s,"dnsmasq_nftset":%s,"dnsmasq_ipset":%s,"private_dnsmasq_nftset":%s},"reasons":["signed_profile_and_acceptance_required"]}\n' \
      "$CS_PROFILE" "$CS_FAMILY" "$CS_FIRMWARE" "$CS_OPENWRT" "$CS_BOARD" "$CS_TARGET" "$CS_ARCH" "$CS_PM" "$CS_FORMAT" "$CS_KERNEL" "$CS_KERNEL_PACKAGE" "$CS_BACKEND" \
      "${CS_MEM_TOTAL:-0}" "${CS_MEM_AVAILABLE:-0}" "$CS_OVERLAY" "$CS_TMP" "${CS_CPUS:-1}" \
      "$CS_UCODE" "$CS_NFT" "$CS_FW4" "$CS_FW3" "$CS_PROCD" "$CS_NETIFD" "$CS_NFTSET" "$CS_IPSET" "$CS_PRIVATE_NFTSET"
)
case "${0##*/}" in platform-probe|platform-probe.sh) csqtt_probe_main "$@" ;; esac
