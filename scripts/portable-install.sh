#!/bin/sh
# Embedded into install.sh by assemble-installer.py. No downloaded code is run.
csqtt_portable_die() { printf 'CSQTT: %s\n' "$*" >&2; exit 1; }
csqtt_j() { jsonfilter -i "$1" -e "$2" 2>/dev/null; }
csqtt_token() { case "$1" in ''|*[!A-Za-z0-9_.+~-]*|.*|-*) return 1 ;; esac; [ "${#1}" -le 200 ]; }
csqtt_hash() { case "$1" in *[!a-f0-9]*) return 1 ;; esac; [ "${#1}" -eq 64 ]; }
csqtt_uint() { case "$1" in ''|*[!0-9]*) return 1 ;; esac; [ "${#1}" -le 9 ]; }
csqtt_stage() { printf 'CSQTT: %s\n' "$*"; }
# opkg's middle Status token is a flag, not the package installation state.
# Stock firmware includes held packages; manually selected packages may use user.
# Buffer records so malformed/unknown installed states never yield a partial
# inventory that could be mistaken for a complete preservation/rollback proof.
csqtt_opkg_records() {
    awk -v mode="$2" -v wanted="${3:-}" '
      BEGIN { RS=""; FS="\n" }
      {
        name=""; version=""; state=""; names=0; versions=0; states=0
        for(i=1;i<=NF;i++) {
          if($i ~ /^Package: /) { name=substr($i,10); names++ }
          if($i ~ /^Version: /) { version=substr($i,10); versions++ }
          if($i ~ /^Status: /) { state=substr($i,9); states++ }
        }
        if(names>1 || versions>1 || states>1 || (name!="" && seen[name]++)) bad=1
        if(state !~ /(^|[ \t])installed([ \t]|$)/) next
        if(state !~ /^install (ok|hold|user) installed$/ || names!=1 || versions!=1 || states!=1 ||
           name !~ /^[A-Za-z0-9_.+~-]+$/ || version !~ /^[A-Za-z0-9_.+~-]+$/) { bad=1; next }
        package[++count]=name; release[count]=version
      }
      END {
        if(bad) exit 1
        for(i=1;i<=count;i++) {
          if(mode=="json") printf "{\"name\":\"%s\",\"version\":\"%s\"}\n",package[i],release[i]
          else if(mode=="version") { if(package[i]==wanted) print release[i] }
          else print package[i] " " release[i]
        }
      }' "$1"
}
# The native package manager and the firmware's local distribution keys are the
# bootstrap trust anchor. Project metadata is never parsed before this succeeds.
csqtt_inventory() {
    if [ "$CS_PM" = apk ]; then
        if [ "$1" = - ]; then apk --no-network query --installed --all-matches --fields name,version --format default '*'
        else apk --root "$1" --arch "$CS_ARCH" --no-network query --installed --all-matches --fields name,version --format default '*'; fi |
          awk '/^Name: / { n=$2 } /^Version: / { if(n ~ /^[A-Za-z0-9_.+~-]+$/ && $2 ~ /^[A-Za-z0-9_.+~-]+$/) print n " " $2; else exit 1; n="" }'
    else
        CS_INV=/usr/lib/opkg/status; [ "$1" = - ] || CS_INV="$1/usr/lib/opkg/status"
        csqtt_opkg_records "$CS_INV" inventory
    fi
}
csqtt_preserve_inventory() {
    awk 'NR==FNR{old[$1]=$2;next} {if($1 in old){if(old[$1]!=$2)bad=1;delete old[$1]}} END{for(n in old)bad=1;exit bad}' "$1" "$2"
}
csqtt_opkg_remove_ordered() (
    CS_RM_ROOT=$1 CS_RM_CONF=$2; shift 2
    CS_RM_STATUS=/usr/lib/opkg/status
    [ "$CS_RM_ROOT" = - ] || CS_RM_STATUS="$CS_RM_ROOT/usr/lib/opkg/status"
    csqtt_removal_command() {
        if [ "$CS_RM_ROOT" = - ]; then OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_RM_CONF" --lists-dir "$CS_TMP/no-repositories" "$@"
        else OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_RM_CONF" --lists-dir "$CS_TMP/no-repositories" --offline-root "$CS_RM_ROOT" "$@"; fi
    }
    # opkg processes operands in order. Prove each removal first, then retry
    # blocked dependencies only after another selected package was removed.
    while [ "$#" -gt 0 ]; do
        CS_RM_PENDING= CS_RM_PROGRESS=0
        for CS_RM_PACKAGE do
            csqtt_token "$CS_RM_PACKAGE" || exit 1
            CS_RM_VERSION=$(csqtt_opkg_records "$CS_RM_STATUS" version "$CS_RM_PACKAGE") || exit 1
            [ -n "$CS_RM_VERSION" ] || continue
            if csqtt_removal_command --noaction remove "$CS_RM_PACKAGE" >> "$CS_TMP/removal-plan.log" 2>&1; then
                csqtt_removal_command remove "$CS_RM_PACKAGE" || exit 1
                CS_RM_VERSION=$(csqtt_opkg_records "$CS_RM_STATUS" version "$CS_RM_PACKAGE") || exit 1
                [ -z "$CS_RM_VERSION" ] || exit 1
                CS_RM_PROGRESS=1
            else CS_RM_PENDING="$CS_RM_PENDING $CS_RM_PACKAGE"; fi
        done
        [ -n "$CS_RM_PENDING" ] || exit 0
        [ "$CS_RM_PROGRESS" = 1 ] || exit 1
        set -- $CS_RM_PENDING
    done
)
csqtt_bootstrap_rollback() {
    CS_BOOT=/etc/csqtt/installer-bootstrap
    [ -d "$CS_BOOT" ] || return 0
    ( cd "$CS_BOOT" && sha256sum -c integrity.sha256 ) > "$CS_TMP/bootstrap-integrity.log" 2>&1 || return 1
    csqtt_inventory - > "$CS_BOOT/current" || return 1
    awk 'NR==FNR{planned[$1]=$2;next} $1 in planned{if(planned[$1]!=$2)bad=1;else print $1} END{exit bad}' "$CS_BOOT/new" "$CS_BOOT/current" > "$CS_BOOT/remove" || return 1
    set --
    while read -r CS_BNAME; do
        csqtt_token "$CS_BNAME" || return 1
        case "$CS_BNAME" in kernel|kmod-*|dnsmasq*|firewall*|procd|netifd|csqtt|csqtt-captcha|luci-app-csqtt) return 1 ;; esac
        set -- "$@" "$CS_BNAME"
    done < "$CS_BOOT/remove"
    if [ "$#" -gt 0 ]; then
        if [ "$CS_PM" = apk ]; then apk --preserve-env --repositories-file /dev/null --no-network del "$@" > "$CS_BOOT/recover.log" 2>&1
        else csqtt_opkg_remove_ordered - "$CS_BOOT/offline.conf" "$@" > "$CS_BOOT/recover.log" 2>&1; fi || return 1
    fi
    csqtt_inventory - > "$CS_BOOT/recovered" || return 1
    csqtt_exact_packages "$CS_BOOT/before" "$CS_BOOT/recovered" || return 1
    [ "$CS_PM" != apk ] || cp "$CS_BOOT/world" /etc/apk/world || return 1
    rm -rf "$CS_BOOT"
    # ash/dash may retain command-v hits for executables just removed by the
    # rollback. Recompute bootstrap needs from the actual filesystem.
    hash -r
}
csqtt_bootstrap() {
    CS_NEED=
    command -v openssl >/dev/null || CS_NEED=openssl-util
    command -v jsonfilter >/dev/null || CS_NEED="$CS_NEED jsonfilter"
    CS_BOOT=/etc/csqtt/installer-bootstrap
    # A prepared bootstrap contains only new packages; existing versions must
    # remain byte-for-byte identical in the isolated solver proof.
    if [ -d "$CS_BOOT" ]; then
        CS_BOOT_PHASE=$(csqtt_metadata_line "$CS_BOOT/phase")
        case "$CS_BOOT_PHASE" in
          complete) command -v openssl >/dev/null && command -v jsonfilter >/dev/null || csqtt_portable_die 'Не найдены средства проверки завершённой подготовительной транзакции'; return 0 ;;
          prepared|installing) csqtt_bootstrap_rollback || csqtt_portable_die 'Не удалось восстановить прерванную установку средств проверки' ;;
          *) csqtt_portable_die 'Неполный журнал установки средств проверки; требуется проверка /etc/csqtt/installer-bootstrap' ;;
        esac
    fi
    CS_NEED=
    command -v openssl >/dev/null || CS_NEED=openssl-util
    command -v jsonfilter >/dev/null || CS_NEED="$CS_NEED jsonfilter"
    [ -n "$CS_NEED" ] || return 0
    csqtt_stage 'Проверка и установка средств проверки из подписанных репозиториев OpenWrt'
    mkdir -p "$CS_TMP/bootstrap/cache" "$CS_TMP/bootstrap/keys" "$CS_TMP/bootstrap/lists"
    csqtt_inventory - > "$CS_TMP/bootstrap/before" || csqtt_portable_die 'Не удалось прочитать исходный состав пакетов'
    [ -s "$CS_TMP/bootstrap/before" ] || csqtt_portable_die 'Не удалось прочитать исходный состав пакетов'
    csqtt_clone "$CS_TMP/bootstrap/root"
    : > "$CS_TMP/bootstrap/repositories"
    if [ "$CS_PM" = apk ]; then
        for CS_BCONFIG in /etc/apk/repositories /etc/apk/repositories.d/*.list; do
            [ -f "$CS_BCONFIG" ] || continue
            awk -v prefix="https://downloads.openwrt.org/releases/$CS_OPENWRT/" '/^[ \t]*($|#)/{next} {if(index($0,prefix)!=1 || $0 ~ "[^A-Za-z0-9_./:+~-]")exit 1;print}' "$CS_BCONFIG" >> "$CS_TMP/bootstrap/repositories" || csqtt_portable_die 'Средства проверки разрешены только из точных официальных репозиториев этой прошивки'
        done
        [ -s "$CS_TMP/bootstrap/repositories" ] || csqtt_portable_die 'Официальные репозитории OpenWrt не настроены'
        for CS_KEY_FILE in /lib/apk/keys/* /etc/apk/keys/*; do [ ! -f "$CS_KEY_FILE" ] || cp "$CS_KEY_FILE" "$CS_TMP/bootstrap/keys/"; done
        apk --root "$CS_TMP/bootstrap/root" --arch "$CS_ARCH" --repositories-file "$CS_TMP/bootstrap/repositories" --keys-dir "$CS_TMP/bootstrap/keys" --cache-dir "$CS_TMP/bootstrap/cache" --cache-predownload --no-scripts add $CS_NEED > "$CS_TMP/bootstrap/solver.log" 2>&1 || csqtt_portable_die 'Подписанная установка средств проверки не прошла в изолированной базе'
    else
        printf 'dest root /\narch all 1\narch %s 10\noption check_signature 1\n' "$CS_ARCH" > "$CS_TMP/bootstrap/opkg.conf"
        for CS_BCONFIG in /etc/opkg/distfeeds.conf; do
            [ -f "$CS_BCONFIG" ] || continue
            awk -v prefix="https://downloads.openwrt.org/releases/$CS_OPENWRT/" '/^[ \t]*($|#)/{next} {raw=$0;gsub(/[ \t]/,"",raw);if(raw ~ "[^A-Za-z0-9_./:+~-]" || NF!=3 || $1!="src/gz" || $2!~/^[A-Za-z0-9_-]+$/ || index($3,prefix)!=1 || $3 ~ "[^A-Za-z0-9_./:+~-]")exit 1;print}' "$CS_BCONFIG" >> "$CS_TMP/bootstrap/opkg.conf" || csqtt_portable_die 'Неофициальные источники средств проверки запрещены'
        done
        command -v usign >/dev/null || csqtt_portable_die 'В прошивке отсутствует usign для проверки официальных репозиториев'
        OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_TMP/bootstrap/opkg.conf" --lists-dir "$CS_TMP/bootstrap/lists" update > "$CS_TMP/bootstrap/update.log" 2>&1 || csqtt_portable_die 'Не прошла проверка подписанных репозиториев OpenWrt'
        # Native opkg prefixes lists_dir with offline_root, even for an absolute
        # argument. Copy the already authenticated lists into that private root.
        mkdir -p "$CS_TMP/bootstrap/root/tmp/csqtt-bootstrap-lists"
        cp -a "$CS_TMP/bootstrap/lists/." "$CS_TMP/bootstrap/root/tmp/csqtt-bootstrap-lists/"
        OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_TMP/bootstrap/opkg.conf" --lists-dir tmp/csqtt-bootstrap-lists --cache "$CS_TMP/bootstrap/cache" --offline-root "$CS_TMP/bootstrap/root" install $CS_NEED > "$CS_TMP/bootstrap/solver.log" 2>&1 || csqtt_portable_die 'Средства проверки недоступны без изменения системных пакетов'
    fi
    csqtt_inventory "$CS_TMP/bootstrap/root" > "$CS_TMP/bootstrap/after" || csqtt_portable_die 'Не удалось проверить состав средств проверки в изолированной базе'
    csqtt_preserve_inventory "$CS_TMP/bootstrap/before" "$CS_TMP/bootstrap/after" || csqtt_portable_die 'Установка средств проверки потребовала бы обновления системных пакетов'
    awk 'NR==FNR{old[$1]=1;next}!($1 in old){print}' "$CS_TMP/bootstrap/before" "$CS_TMP/bootstrap/after" > "$CS_TMP/bootstrap/new"
    while read -r CS_BNAME CS_BVER; do case "$CS_BNAME" in kernel|kmod-*|dnsmasq*|firewall*|procd|netifd) csqtt_portable_die 'Запрещённая системная зависимость средств проверки' ;; esac; done < "$CS_TMP/bootstrap/new"
    # Prove removal as well as addition. In particular APK may garbage-collect
    # existing non-world packages while deleting new roots; a rollback must not
    # discover that loss only after it has already changed the live system.
    awk '{print $1}' "$CS_TMP/bootstrap/new" > "$CS_TMP/bootstrap/remove"
    csqtt_remove_new "$CS_TMP/bootstrap/root" "$CS_TMP/bootstrap/remove" > "$CS_TMP/bootstrap/rollback-proof.log" 2>&1 || csqtt_portable_die 'Не удалось проверить автономное удаление средств проверки'
    csqtt_inventory "$CS_TMP/bootstrap/root" > "$CS_TMP/bootstrap/rolled-back" || csqtt_portable_die 'Не удалось проверить состав пакетов после изолированного отката средств проверки'
    csqtt_exact_packages "$CS_TMP/bootstrap/before" "$CS_TMP/bootstrap/rolled-back" || csqtt_portable_die 'Откат средств проверки изменил бы исходный состав пакетов'
    CS_BOOT_KIB=$(du -sk "$CS_TMP/bootstrap" | awk '{print $1}')
    csqtt_uint "$CS_BOOT_KIB" && [ "$(csqtt_free_kib /overlay)" -ge "$((CS_BOOT_KIB * 2 + 1024))" ] || csqtt_portable_die 'Недостаточно места для автономного кэша и установки средств проверки'
    mkdir -p /etc/csqtt
    [ ! -d "$CS_BOOT.new" ] || rm -rf "$CS_BOOT.new"
    cp -a "$CS_TMP/bootstrap" "$CS_BOOT.new"
    printf 'dest root /\narch all 1\narch %s 10\n' "$CS_ARCH" > "$CS_BOOT.new/offline.conf"
    [ "$CS_PM" != apk ] || cp /etc/apk/world "$CS_BOOT.new/world"
    ( cd "$CS_BOOT.new"; set -- before after new; [ ! -f world ] || set -- "$@" world; sha256sum "$@" > integrity.sha256 )
    printf 'prepared\n' > "$CS_BOOT.new/phase"
    sync
    mv "$CS_BOOT.new" "$CS_BOOT"
    sync
    printf 'installing\n' > "$CS_BOOT/phase.new"; mv "$CS_BOOT/phase.new" "$CS_BOOT/phase"; sync
    if [ "$CS_PM" = apk ]; then
        set --; while read -r CS_BNAME CS_BVER; do set -- "$@" "$CS_BNAME=$CS_BVER"; done < "$CS_BOOT/new"
        apk --preserve-env --repositories-file "$CS_BOOT/repositories" --keys-dir "$CS_BOOT/keys" --cache-dir "$CS_BOOT/cache" --no-network add "$@" > "$CS_BOOT/install.log" 2>&1 || csqtt_portable_die 'Установка средств проверки прервана; повторите ту же команду для восстановления'
    else
        set --; for CS_BFILE in "$CS_BOOT/cache/"*.ipk; do [ ! -f "$CS_BFILE" ] || set -- "$@" "$CS_BFILE"; done
        [ "$#" -gt 0 ] || csqtt_portable_die 'Отсутствует автономный кэш средств проверки'
        OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_BOOT/offline.conf" install "$@" > "$CS_BOOT/install.log" 2>&1 || csqtt_portable_die 'Установка средств проверки прервана; повторите ту же команду для восстановления'
    fi
    command -v openssl >/dev/null && command -v jsonfilter >/dev/null || csqtt_portable_die 'Установленные средства проверки недоступны'
    csqtt_inventory - > "$CS_BOOT/installed" || csqtt_portable_die 'Не удалось проверить состав установленных средств проверки'
    csqtt_exact_packages "$CS_BOOT/after" "$CS_BOOT/installed" || csqtt_portable_die 'Состав установленных средств проверки отличается от проверенного'
    printf 'complete\n' > "$CS_BOOT/phase.new"; mv "$CS_BOOT/phase.new" "$CS_BOOT/phase"; sync
}
csqtt_fetch() { uclient-fetch -q -O "$2" "$CS_BASE/$1" || csqtt_portable_die 'Не удалось загрузить файл выпуска'; }
csqtt_bytes() {
    csqtt_hash "$2" && csqtt_uint "$3" && [ "$3" -gt 0 ] && [ "$3" -le 67108864 ] || csqtt_portable_die 'Недопустимые размер или контрольная сумма файла'
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(wc -c < "$1")" -eq "$3" ] || csqtt_portable_die 'Размер файла не совпадает'
    printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null || csqtt_portable_die 'Контрольная сумма файла не совпадает'
}
csqtt_asset() {
    CS_ASSET_NAME=$(csqtt_j "$CS_MANIFEST" "$1.name")
    csqtt_token "$CS_ASSET_NAME" || csqtt_portable_die 'Неверное имя или повтор файла выпуска'
    [ ! -e "$CS_TMP/assets/$CS_ASSET_NAME" ] || csqtt_portable_die 'Неверное имя или повтор файла выпуска'
    csqtt_fetch "$CS_ASSET_NAME" "$CS_TMP/assets/$CS_ASSET_NAME"
    csqtt_bytes "$CS_TMP/assets/$CS_ASSET_NAME" "$(csqtt_j "$CS_MANIFEST" "$1.sha256")" "$(csqtt_j "$CS_MANIFEST" "$1.size")"
}
csqtt_signature() {
    [ "$(wc -c < "$2")" -le 1024 ] || csqtt_portable_die 'Подпись слишком велика'
    openssl dgst -sha256 -verify "$CS_TMP/project.pem" -signature "$2" "$1" >/dev/null 2>&1 || csqtt_portable_die 'Подпись выпуска недействительна'
}
csqtt_installed_version() {
    if [ "$CS_PM" = apk ]; then
        apk query --installed --match name --fields version --format json "$1" 2>/dev/null | jsonfilter -e '@[0].version' 2>/dev/null || true
    else
        OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg -f "$CS_TMP/opkg.conf" status "$1" 2>/dev/null | csqtt_opkg_records - version "$1"
    fi
}
csqtt_opkg() { OPKG_CONF_DIR="$CS_TMP/no-repositories" opkg --conf "$CS_TMP/opkg.conf" --lists-dir "$CS_TMP/no-repositories" "$@"; }
csqtt_clone() {
    mkdir -p "$1/var/lock" "$1/tmp"
    if [ "$CS_PM" = apk ]; then
        mkdir -p "$1/lib/apk/db" "$1/etc/apk/keys"
        cp -aL /lib/apk/db/. "$1/lib/apk/db/"
        cp /etc/apk/world "$1/etc/apk/world"
        for CS_CLONE_KEY in "$CS_TMP/keys/"*; do [ ! -f "$CS_CLONE_KEY" ] || cp "$CS_CLONE_KEY" "$1/etc/apk/keys/"; done
    else
        mkdir -p "$1/usr/lib/opkg/info" "$1/etc/opkg"
        cp /usr/lib/opkg/status "$1/usr/lib/opkg/status"
        cp -a /usr/lib/opkg/info/. "$1/usr/lib/opkg/info/"
    fi
}
csqtt_check_versions() {
    CS_CHECK_ROOT=$1; CS_CHECK_BUNDLE=$2; CS_CHECK_N=0
    while [ "$CS_CHECK_N" -lt 3 ]; do
        CS_CHECK_ROLE=$(csqtt_package_field "$CS_CHECK_BUNDLE/manifest.json" "$CS_CHECK_N" role)
        CS_CHECK_VERSION=$(csqtt_package_field "$CS_CHECK_BUNDLE/manifest.json" "$CS_CHECK_N" version)
        if [ "$CS_CHECK_ROOT" = - ]; then CS_CHECK_ACTUAL=$(csqtt_installed_version "$CS_CHECK_ROLE") || return 1
        elif [ "$CS_PM" = apk ]; then CS_CHECK_ACTUAL=$(apk --root "$CS_CHECK_ROOT" --arch "$CS_ARCH" --keys-dir etc/apk/keys --no-network query --installed --match name --fields version --format json "$CS_CHECK_ROLE" | jsonfilter -e '@[0].version')
        else CS_CHECK_ACTUAL=$(csqtt_opkg_records "$CS_CHECK_ROOT/usr/lib/opkg/status" version "$CS_CHECK_ROLE") || return 1; fi
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
        csqtt_opkg_records "$CS_STATUS" json
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
csqtt_package_field() {
    if [ "$(csqtt_j "$1" '@.schema')" = 1 ]; then
        CS_OLD_FILE=$(csqtt_j "$1" "@.packages[$2].name")
        case "$CS_OLD_FILE" in csqtt-0.1.0-r9.apk) CS_OLD_ROLE=csqtt ;; csqtt-captcha-0.1.0-r9.apk) CS_OLD_ROLE=csqtt-captcha ;; luci-app-csqtt-0.1.0-r9.apk) CS_OLD_ROLE=luci-app-csqtt ;; *) return 1 ;; esac
        if [ "$3" = role ]; then printf '%s\n' "$CS_OLD_ROLE"; elif [ "$3" = version ]; then printf '0.1.0-r9\n'; else return 1; fi
    else csqtt_j "$1" "@.packages[$2].$3"; fi
}
csqtt_previous() {
    if [ -f /etc/csqtt/releases/current/manifest.json ] && [ -f /etc/csqtt/releases/current/manifest.sig ]; then
        mkdir -p "$CS_TMP/previous"; cp -a /etc/csqtt/releases/current/. "$CS_TMP/previous/"
    else
        # Immutable signed r9 did not retain a release bundle. Fetch only that
        # exact historical release, then authenticate before using any bytes.
        [ "$CS_PM:$CS_OPENWRT:$CS_ARCH:$(csqtt_j "$CS_TMP/probe.json" '@.target')" = apk:25.12.5:aarch64_cortex-a53:mediatek/filogic ] || csqtt_portable_die 'Для обновления требуется предыдущий подписанный автономный комплект'
        for CS_ROLE in csqtt csqtt-captcha luci-app-csqtt; do [ "$(csqtt_installed_version "$CS_ROLE")" = 0.1.0-r9 ] || csqtt_portable_die 'Автоматический перенос поддерживает только неизменённый подписанный preview.9'; done
        csqtt_stage 'Подготовка проверенного отката с подписанного preview.9'
        mkdir -p "$CS_TMP/previous/assets" "$CS_TMP/previous/repos"
        CS_PREVIOUS_BASE=$CS_BASE; CS_BASE=https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.9
        csqtt_fetch manifest.json "$CS_TMP/previous/manifest.json"; csqtt_fetch manifest.sig "$CS_TMP/previous/manifest.sig"
        csqtt_signature "$CS_TMP/previous/manifest.json" "$CS_TMP/previous/manifest.sig"
        csqtt_validate_previous "$CS_TMP/previous/manifest.json"
        CS_PREV_I=0
        while [ "$CS_PREV_I" -lt 3 ]; do
            CS_PREV_FILE=$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_PREV_I].name")
            csqtt_fetch "$CS_PREV_FILE" "$CS_TMP/previous/assets/$CS_PREV_FILE"
            CS_PREV_I=$((CS_PREV_I + 1))
        done
        CS_BASE=$CS_PREVIOUS_BASE
    fi
    csqtt_signature "$CS_TMP/previous/manifest.json" "$CS_TMP/previous/manifest.sig"
    csqtt_validate_previous "$CS_TMP/previous/manifest.json"
    CS_PREV_I=0
    while [ "$CS_PREV_I" -lt 3 ]; do
        CS_PREV_FILE=$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_PREV_I].name")
        CS_PREV_ROLE=$(csqtt_package_field "$CS_TMP/previous/manifest.json" "$CS_PREV_I" role)
        [ "$(csqtt_installed_version "$CS_PREV_ROLE")" = "$(csqtt_package_field "$CS_TMP/previous/manifest.json" "$CS_PREV_I" version)" ] || csqtt_portable_die 'Предыдущий комплект не соответствует установленным версиям'
        csqtt_bytes "$CS_TMP/previous/assets/$CS_PREV_FILE" "$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_PREV_I].sha256")" "$(csqtt_j "$CS_TMP/previous/manifest.json" "@.packages[$CS_PREV_I].size")"
        [ "$CS_PM" != apk ] || apk --keys-dir "$CS_TMP/projectkeys" verify "$CS_TMP/previous/assets/$CS_PREV_FILE" > "$CS_TMP/previous/verify-$CS_PREV_I.log" 2>&1 || csqtt_portable_die 'Подпись пакета предыдущего выпуска недействительна'
        CS_PREV_I=$((CS_PREV_I + 1))
    done
}
csqtt_validate_previous() {
    if [ "$(csqtt_j "$1" '@.schema')" = 1 ]; then
        [ "$CS_PM:$CS_OPENWRT:$CS_ARCH:$(csqtt_j "$CS_TMP/probe.json" '@.target')" = apk:25.12.5:aarch64_cortex-a53:mediatek/filogic ] || csqtt_portable_die 'Старый выпуск не соответствует текущей прошивке'
        for CS_OLD_KEY in openwrt target architecture; do [ "$(csqtt_j "$1" "@.$CS_OLD_KEY")" = "$(csqtt_j "$CS_TMP/probe.json" "@.$CS_OLD_KEY")" ] || csqtt_portable_die 'Несовместимый старый комплект'; done
        [ "$(csqtt_j "$1" '@.upstream')" = amurcanov/csqtt@v2.1.9 ] && [ -z "$(csqtt_j "$1" '@.packages[3]')" ] || csqtt_portable_die 'Неверный старый манифест'
        CS_OLD_ROLES=' '; CS_OLD_I=0
        while [ "$CS_OLD_I" -lt 3 ]; do
            CS_OLD_ROLE=$(csqtt_package_field "$1" "$CS_OLD_I" role) || csqtt_portable_die 'Разрешён только подписанный preview.9'
            case "$CS_OLD_ROLES" in *" $CS_OLD_ROLE "*) csqtt_portable_die 'Повтор пакета предыдущего выпуска' ;; esac
            CS_OLD_ROLES="$CS_OLD_ROLES$CS_OLD_ROLE "; CS_OLD_I=$((CS_OLD_I + 1))
        done
    else csqtt_validate_tuple "$1"; fi
}
csqtt_repositories() {
    : > "$1/repositories"
    for CS_REPO_INDEX in "$1"/repos/*/packages.adb; do [ ! -f "$CS_REPO_INDEX" ] || printf 'file://%s\n' "$CS_REPO_INDEX" >> "$1/repositories"; done
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
            CS_DEP=$(csqtt_j "$CS_PM_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_N].package")
            # Preserve any installed version that satisfies native constraints.
            # An implicit solver upgrade is rejected by the inventory proof.
            [ -n "$(csqtt_installed_version "$CS_DEP")" ] || set -- "$@" "$CS_PM_BUNDLE/assets/$CS_FILE"
            CS_N=$((CS_N + 1))
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
            [ -n "$(csqtt_installed_version "$CS_DEP")" ] || set -- "$@" "$CS_DEP=$CS_VERSION"
            CS_N=$((CS_N + 1))
        done
        csqtt_repositories "$CS_PM_BUNDLE"
        CS_REPOSITORIES="$CS_PM_BUNDLE/repositories"
        [ "$CS_PM_DOWNGRADE" = 0 ] || CS_REPOSITORIES="$CS_TMP/empty-repositories"
        if [ "$CS_PM_ROOT" = - ]; then
            # APK otherwise strips the lifecycle owner/ticks from maintainer
            # scripts, whose direct init calls would wait on their own parent.
            apk --preserve-env --repositories-file "$CS_REPOSITORIES" --keys-dir "$CS_TMP/keys" --no-network add "$@"
        else
            apk --root "$CS_PM_ROOT" --arch "$CS_ARCH" --repositories-file "$CS_REPOSITORIES" --keys-dir etc/apk/keys --no-network --no-scripts add "$@"
        fi
    fi
}
csqtt_validate_tuple() {
    [ "$(csqtt_j "$1" '@.schema')" = 2 ] && [ "$(csqtt_j "$1" '@.upstream')" = amurcanov/csqtt@v2.1.9 ] || csqtt_portable_die 'Неподдерживаемая схема манифеста или каталога'
    for CS_KEY in family openwrt target architecture package_manager package_format; do
        [ "$(csqtt_j "$1" "@.platform.$CS_KEY")" = "$(csqtt_j "$CS_TMP/probe.json" "@.$CS_KEY")" ] || csqtt_portable_die 'Выпуск не соответствует версии, целевой платформе или архитектуре прошивки'
    done
    [ "$CS_FAMILY" = official ] || csqtt_portable_die 'Поддерживается только официальная OpenWrt 24.10/25.12'
    [ "$(csqtt_j "$1" '@.profile_id')" = "$CS_PROFILE" ] && [ "$(csqtt_j "$1" '@.backend')" = "$CS_BACKEND" ] || csqtt_portable_die 'Выпуск не соответствует версии, целевой платформе или архитектуре прошивки'
    [ "$(csqtt_j "$1" '@.qualification.installation')" = true ] && [ "$(csqtt_j "$1" '@.qualification.activation')" = true ] && [ -n "$(csqtt_j "$1" '@.qualification.evidence[0]')" ] || csqtt_portable_die 'Этот профиль ещё не прошёл проверку установки и активации'
    [ -n "$(csqtt_j "$1" '@.requirements.kernel_package')" ] && [ "$(csqtt_j "$1" '@.requirements.kernel_package')" = "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" ] || csqtt_portable_die 'Версия установленного ядра не совпадает с подписанным комплектом'
    [ "$(csqtt_j "$1" '@.dns_binary')" = /usr/libexec/csqtt/dnsmasq ] || csqtt_portable_die 'Для безопасной работы требуется отдельный DNS CSQTT'
    [ -z "$(csqtt_j "$1" '@.packages[3]')" ] || csqtt_portable_die 'Неверный состав трёх пакетов CSQTT'
    CS_ROLES=' '
    CS_N=0
    while [ "$CS_N" -lt 3 ]; do
        CS_ROLE=$(csqtt_j "$1" "@.packages[$CS_N].role")
        CS_FILE=$(csqtt_j "$1" "@.packages[$CS_N].name")
        CS_VERSION=$(csqtt_j "$1" "@.packages[$CS_N].version")
        case "$CS_ROLE" in csqtt|csqtt-captcha|luci-app-csqtt) ;; *) csqtt_portable_die 'Неверный состав трёх пакетов CSQTT' ;; esac
        case "$CS_ROLES" in *" $CS_ROLE "*) csqtt_portable_die 'Неверный состав трёх пакетов CSQTT' ;; esac
        CS_ROLES="$CS_ROLES$CS_ROLE "
        csqtt_token "$CS_FILE" && csqtt_token "$CS_VERSION" || csqtt_portable_die 'Неверный состав трёх пакетов CSQTT'
        case "$CS_FILE" in "$CS_PROFILE"--*."$CS_FORMAT") ;; *) csqtt_portable_die 'Неверное имя или повтор файла выпуска' ;; esac
        CS_N=$((CS_N + 1))
    done
}
csqtt_bundle_sources() {
    : > "$CS_TMP/repositories"
    CS_I=0
    while [ -n "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I]")" ]; do
        [ "$CS_I" -lt 16 ] || csqtt_portable_die 'Неверный состав подписанных индексов зависимостей'
        CS_ID=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].id")
        csqtt_token "$CS_ID" && [ ! -e "$CS_TMP/repos/$CS_ID" ] || csqtt_portable_die 'Неверный состав подписанных индексов зависимостей'
        CS_SOURCE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].repository")
        case "$CS_FAMILY:$CS_SOURCE" in "official:https://downloads.openwrt.org/releases/$CS_OPENWRT/"*) ;; *) csqtt_portable_die 'Недопустимый источник зависимостей или другая версия OpenWrt' ;; esac
        CS_KEY_HASH=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].key_sha256")
        csqtt_hash "$CS_KEY_HASH" || csqtt_portable_die 'В подписанном манифесте отсутствует отпечаток ключа OpenWrt'
        mkdir -p "$CS_TMP/repos/$CS_ID" "$CS_TMP/sourcekeys/$CS_ID"
        CS_SOURCE_KEY=
        if [ "$CS_PM" = apk ]; then CS_KEY_PATHS='/lib/apk/keys/* /etc/apk/keys/*'; else CS_KEY_PATHS='/etc/opkg/keys/*'; fi
        # Only local distro keys matching the signed exact fingerprint qualify.
        for CS_KEY_FILE in $CS_KEY_PATHS; do
            [ -f "$CS_KEY_FILE" ] || continue
            CS_ACTUAL_HASH=$(sha256sum "$CS_KEY_FILE" | awk '{ print $1 }')
            if [ "$CS_ACTUAL_HASH" = "$CS_KEY_HASH" ]; then CS_SOURCE_KEY=$CS_KEY_FILE; break; fi
        done
        [ -n "$CS_SOURCE_KEY" ] || csqtt_portable_die 'Ключ официального репозитория не найден в установленной прошивке'
        cp "$CS_SOURCE_KEY" "$CS_TMP/sourcekeys/$CS_ID/source.key"
        csqtt_asset "@.dependency_bundle.indexes[$CS_I]"
        CS_INDEX_NAME=$CS_ASSET_NAME
        if [ "$CS_PM" = apk ]; then
            [ "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].format")" = apk-adb ] || csqtt_portable_die 'Неверный состав подписанных индексов зависимостей'
            apk --keys-dir "$CS_TMP/sourcekeys/$CS_ID" verify "$CS_TMP/assets/$CS_INDEX_NAME" >"$CS_TMP/index-$CS_I.log" 2>&1 || csqtt_portable_die 'Подпись индекса зависимостей OpenWrt недействительна'
            cp "$CS_TMP/assets/$CS_INDEX_NAME" "$CS_TMP/repos/$CS_ID/packages.adb"
            printf 'file://%s/repos/%s/packages.adb\n' "$CS_TMP" "$CS_ID" >> "$CS_TMP/repositories"
        else
            [ "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.indexes[$CS_I].format")" = opkg ] || csqtt_portable_die 'Неверный состав подписанных индексов зависимостей'
            command -v usign >/dev/null || csqtt_portable_die 'В прошивке отсутствует средство проверки подписи индекса OpenWrt'
            csqtt_asset "@.dependency_bundle.indexes[$CS_I].signature"
            usign -V -p "$CS_SOURCE_KEY" -m "$CS_TMP/assets/$CS_INDEX_NAME" -x "$CS_TMP/assets/$CS_ASSET_NAME" >"$CS_TMP/index-$CS_I.log" 2>&1 || csqtt_portable_die 'Подпись индекса зависимостей OpenWrt недействительна'
            cp "$CS_TMP/assets/$CS_INDEX_NAME" "$CS_TMP/repos/$CS_ID/Packages"
        fi
        CS_I=$((CS_I + 1))
    done
    CS_I=0; : > "$CS_TMP/new-dependencies"
    while [ -n "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I]")" ]; do
        [ "$CS_I" -lt 64 ] || csqtt_portable_die 'Неверный состав подписанных зависимостей'
        CS_DEP=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].package")
        CS_VERSION=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].version")
        CS_ID=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].index")
        CS_FILE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].filename")
        csqtt_token "$CS_DEP" && csqtt_token "$CS_VERSION" && csqtt_token "$CS_ID" && csqtt_token "$CS_FILE" || csqtt_portable_die 'Неверный состав подписанных зависимостей'
        case "$CS_DEP" in
          kmod-*) [ "$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].kernel_package")" = "$(csqtt_j "$CS_MANIFEST" '@.requirements.kernel_package')" ] && [ "$(csqtt_j "$CS_MANIFEST" '@.requirements.kernel_package')" = "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" ] || csqtt_portable_die 'Модуль предназначен для другого ядра' ;;
          kernel|dnsmasq*|firewall*|procd|netifd|csqtt|csqtt-captcha|luci-app-csqtt) csqtt_portable_die 'Замена ядра, DNS, межсетевого экрана или системных служб запрещена' ;;
        esac
        [ -d "$CS_TMP/repos/$CS_ID" ] || csqtt_portable_die 'Неверный состав подписанных индексов зависимостей'
        [ ! -e "$CS_TMP/repos/$CS_ID/$CS_FILE" ] || csqtt_portable_die 'Неверный состав подписанных зависимостей'
        CS_INSTALLED=$(csqtt_installed_version "$CS_DEP")
        [ -n "$CS_INSTALLED" ] || printf '%s\n' "$CS_DEP" >> "$CS_TMP/new-dependencies"
        csqtt_asset "@.dependency_bundle.packages[$CS_I]"
        if [ "$CS_PM" = opkg ]; then
            CS_DIGEST=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].sha256")
            CS_SIZE=$(csqtt_j "$CS_MANIFEST" "@.dependency_bundle.packages[$CS_I].size")
            awk -v pkg="$CS_DEP" -v ver="$CS_VERSION" -v file="$CS_FILE" -v hash="$CS_DIGEST" -v bytes="$CS_SIZE" -v arch="$CS_ARCH" '
              BEGIN { RS=""; FS="\n" } { for(k in f) delete f[k]; for(i=1;i<=NF;i++){ p=index($i,": "); if(p) f[substr($i,1,p-1)]=substr($i,p+2) }
                if(f["Package"]==pkg && f["Version"]==ver && f["Filename"]==file && f["SHA256sum"]==hash && f["Size"]==bytes && (f["Architecture"]==arch || f["Architecture"]=="all")) matches++ }
              END { exit matches!=1 }' "$CS_TMP/repos/$CS_ID/Packages" || csqtt_portable_die 'Файл зависимости не соответствует подписанному индексу OpenWrt'
        fi
        cp "$CS_TMP/assets/$CS_ASSET_NAME" "$CS_TMP/repos/$CS_ID/$CS_FILE"
        CS_I=$((CS_I + 1))
    done
}
csqtt_remove() {
    CS_DEL_ROOT=$1; shift
    [ "$#" -gt 0 ] || return 0
    if [ "$CS_PM" = apk ]; then
        if [ "$CS_DEL_ROOT" = - ]; then apk --preserve-env --repositories-file "$CS_TMP/empty-repositories" --keys-dir "$CS_TMP/keys" --no-network del "$@"
        else apk --root "$CS_DEL_ROOT" --arch "$CS_ARCH" --repositories-file "$CS_TMP/empty-repositories" --keys-dir etc/apk/keys --no-network --no-scripts del "$@"; fi
    else csqtt_opkg_remove_ordered "$CS_DEL_ROOT" "$CS_TMP/opkg.conf" "$@"; fi
}
csqtt_new_module_allowed() (
    CS_MOD_BUNDLE=$1 CS_MOD_BASELINE=$2 CS_MOD_PACKAGE=$3
    [ -s "$CS_MOD_BASELINE" ] && [ -f "$CS_MOD_BUNDLE/manifest.json" ] || exit 1
    # A recorded baseline module can never become a removal target.
    awk -v wanted="$CS_MOD_PACKAGE" '{name=$0;sub(/^.*"name"[ ]*:[ ]*"/,"",name);sub(/".*$/,"",name);if(name==wanted)found=1} END{exit found}' "$CS_MOD_BASELINE" || exit 1
    CS_MOD_ABI=$(csqtt_j "$CS_MOD_BUNDLE/manifest.json" '@.requirements.kernel_package')
    [ -n "$CS_MOD_ABI" ] && [ "$CS_MOD_ABI" = "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" ] || exit 1
    CS_MOD_I=0 CS_MOD_MATCHES=0
    while [ -n "$(csqtt_j "$CS_MOD_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_MOD_I]")" ]; do
        [ "$CS_MOD_I" -lt 64 ] || exit 1
        if [ "$(csqtt_j "$CS_MOD_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_MOD_I].package")" = "$CS_MOD_PACKAGE" ]; then
            [ "$(csqtt_j "$CS_MOD_BUNDLE/manifest.json" "@.dependency_bundle.packages[$CS_MOD_I].kernel_package")" = "$CS_MOD_ABI" ] || exit 1
            CS_MOD_MATCHES=$((CS_MOD_MATCHES+1))
        fi
        CS_MOD_I=$((CS_MOD_I+1))
    done
    [ "$CS_MOD_MATCHES" = 1 ]
)
csqtt_remove_new() {
    CS_REMOVE_ROOT=$1 CS_REMOVE_LIST=$2 CS_REMOVE_BUNDLE=${3:-} CS_REMOVE_BASELINE=${4:-}; set --
    while IFS= read -r CS_DEP; do
        [ -n "$CS_DEP" ] || continue
        csqtt_token "$CS_DEP" || return 1
        case "$CS_DEP" in kernel|dnsmasq*|firewall*|procd|netifd|csqtt|csqtt-captcha|luci-app-csqtt) return 1 ;; kmod-*) [ -n "$CS_REMOVE_BUNDLE" ] && csqtt_new_module_allowed "$CS_REMOVE_BUNDLE" "$CS_REMOVE_BASELINE" "$CS_DEP" || return 1 ;; esac
        set -- "$@" "$CS_DEP"
    done < "$CS_REMOVE_LIST"
    csqtt_remove "$CS_REMOVE_ROOT" "$@"
}
csqtt_phase() { printf '%s\n' "$1" > "$CS_BACKUP/phase.new"; mv "$CS_BACKUP/phase.new" "$CS_BACKUP/phase"; sync; }
csqtt_journal_hashes() (
    cd "$CS_BACKUP"
    set -- packages-before new-dependencies upgrade probe.json
    for CS_SAVED in config/csqtt config/dhcp config/firewall config/network platform.json world; do [ ! -f "$CS_SAVED" ] || set -- "$@" "$CS_SAVED"; done
    sha256sum "$@" > integrity.sha256
)
csqtt_archive_journal() {
    mkdir -p /etc/csqtt/backups
    CS_ARCHIVED="/etc/csqtt/backups/portable-$(date +%Y%m%d-%H%M%S)-$$"
    mv "$CS_BACKUP" "$CS_ARCHIVED" || return 1
    CS_BACKUP=$CS_ARCHIVED
    sync
}
csqtt_rollback() {
    csqtt_stage 'Восстановление предыдущих пакетов и настроек без сети'
    CS_RESTORED=0
    if [ "$CS_UPGRADE" = 1 ]; then csqtt_pm_install - "$CS_BACKUP/previous" 1 >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1
    else csqtt_remove - luci-app-csqtt csqtt-captcha csqtt >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1; fi
    if [ "$CS_RESTORED" = 0 ]; then
        csqtt_remove_new - "$CS_BACKUP/new-dependencies" "$CS_BACKUP/transaction" "$CS_BACKUP/packages-before" >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1
        csqtt_snapshot - > "$CS_BACKUP/packages-rolled-back" || CS_RESTORED=1
        csqtt_exact_packages "$CS_BACKUP/packages-before" "$CS_BACKUP/packages-rolled-back" || CS_RESTORED=1
        for CS_CONFIG in csqtt dhcp firewall network; do
            if [ -f "$CS_BACKUP/config/$CS_CONFIG" ]; then cp -p "$CS_BACKUP/config/$CS_CONFIG" "/etc/config/$CS_CONFIG" || CS_RESTORED=1
            else rm -f "/etc/config/$CS_CONFIG" || CS_RESTORED=1; fi
        done
        if [ "$CS_PM" = apk ]; then cp "$CS_BACKUP/world" /etc/apk/world || CS_RESTORED=1; fi
        if [ -f "$CS_BACKUP/platform.json" ]; then cp "$CS_BACKUP/platform.json" /etc/csqtt/platform.json || CS_RESTORED=1
        else rm -f /etc/csqtt/platform.json || CS_RESTORED=1; fi
        if [ -d "$CS_BACKUP/previous-current" ]; then
            [ ! -e /etc/csqtt/releases/current ] || rm -rf /etc/csqtt/releases/current
            mv "$CS_BACKUP/previous-current" /etc/csqtt/releases/current || CS_RESTORED=1
        fi
        if [ "$CS_UPGRADE" = 1 ] && [ "$CS_RESTORED" = 0 ]; then
            if [ "$(uci -q get csqtt.main.enabled 2>/dev/null || true)" = 1 ]; then /etc/init.d/csqtt restart >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1; fi
            for CS_OLD_SERVICE in csqtt-captcha csqtt-health; do "/etc/init.d/$CS_OLD_SERVICE" restart >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1; done
        fi
        if [ -n "$(csqtt_installed_version rpcd)" ] && [ -x /etc/init.d/rpcd ]; then /etc/init.d/rpcd restart >> "$CS_BACKUP/rollback.log" 2>&1 || CS_RESTORED=1; fi
    fi
    if [ "$CS_RESTORED" = 0 ]; then
        csqtt_phase rollback_complete
        csqtt_archive_journal || return 1
        CS_CHANGED=0
        csqtt_stage "Откат завершён. Закрытая резервная копия: $CS_BACKUP"
    else csqtt_phase rollback_incomplete; printf 'CSQTT: Откат не завершён; журнал сохранён, повторите установку для восстановления.\n' >&2; return 1; fi
}
csqtt_recover() {
    [ -d /etc/csqtt/installer-transaction ] || return 0
    CS_BACKUP=/etc/csqtt/installer-transaction
    CS_RECOVERY_PHASE=$(csqtt_metadata_line "$CS_BACKUP/phase")
    case "$CS_RECOVERY_PHASE" in committed|rollback_complete) csqtt_archive_journal; return ;; prepared|installing|packages_installed|rollback_incomplete) ;; *) csqtt_portable_die 'Неполный журнал транзакции; требуется проверка /etc/csqtt/installer-transaction' ;; esac
    csqtt_stage 'Обнаружена прерванная установка. Проверка автономного восстановления'
    ( cd "$CS_BACKUP" && sha256sum -c integrity.sha256 ) > "$CS_TMP/journal-integrity.log" 2>&1 || csqtt_portable_die 'Резервная копия прерванной транзакции повреждена; автоматический откат остановлен'
    CS_UPGRADE=$(csqtt_metadata_line "$CS_BACKUP/upgrade")
    case "$CS_UPGRADE" in 0|1) ;; *) csqtt_portable_die 'Повреждён журнал транзакции' ;; esac
    csqtt_signature "$CS_BACKUP/transaction/manifest.json" "$CS_BACKUP/transaction/manifest.sig"
    csqtt_validate_tuple "$CS_BACKUP/transaction/manifest.json"
    if [ "$CS_UPGRADE" = 1 ]; then
        csqtt_signature "$CS_BACKUP/previous/manifest.json" "$CS_BACKUP/previous/manifest.sig"
        csqtt_validate_previous "$CS_BACKUP/previous/manifest.json"
        CS_REC_I=0
        while [ "$CS_REC_I" -lt 3 ]; do
            CS_REC_FILE=$(csqtt_j "$CS_BACKUP/previous/manifest.json" "@.packages[$CS_REC_I].name")
            csqtt_bytes "$CS_BACKUP/previous/assets/$CS_REC_FILE" "$(csqtt_j "$CS_BACKUP/previous/manifest.json" "@.packages[$CS_REC_I].sha256")" "$(csqtt_j "$CS_BACKUP/previous/manifest.json" "@.packages[$CS_REC_I].size")"
            CS_REC_I=$((CS_REC_I + 1))
        done
    fi
    CS_CHANGED=1
    csqtt_rollback || csqtt_portable_die 'Автономное восстановление не завершено'
    CS_UPGRADE=0
}
csqtt_lock() {
    mkdir -p /var/lock
    if [ -d /var/lock/csqtt-maintenance ] && [ -d /etc/csqtt/installer-transaction -o -d /etc/csqtt/installer-bootstrap ]; then
        CS_OLD_PID=$(csqtt_metadata_line /var/lock/csqtt-maintenance/pid)
        if csqtt_uint "$CS_OLD_PID" && ! kill -0 "$CS_OLD_PID" 2>/dev/null; then rm -f /var/lock/csqtt-maintenance/pid; rmdir /var/lock/csqtt-maintenance 2>/dev/null || true; fi
    fi
    mkdir /var/lock/csqtt-maintenance 2>/dev/null || csqtt_portable_die 'Установка или другая операция CSQTT уже выполняется'
    CS_LOCKED=1; printf '%s\n' "$$" > /var/lock/csqtt-maintenance/pid
    # Embedded from the same source as the runtime. Hold the lifecycle lease in
    # this installer process, including a first install without runtime files.
    # Package scripts and direct init children inherit the exact owner/ticks,
    # while unrelated Stop/Reload/Helper operations must wait for completion.
    csqtt_operation_enter || csqtt_portable_die 'Не удалось дождаться текущей операции'
    trap csqtt_portable_cleanup EXIT; trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM
}
csqtt_finish_url() {
    # Prefer the saved CSQTT scope, then the actual OpenWrt LAN configuration.
    # Do not assume that a fresh installation has a bridge named br-lan.
    CS_LAN_DEVICES=$(uci -q get csqtt.main.lan_device 2>/dev/null || true)
    CS_LAN_NETWORKS=lan
    for CS_ZONE in $(uci -q show firewall 2>/dev/null | awk -F= '$2=="zone" {sub(/^firewall\./,"",$1);if($1~/^(@zone\[[0-9]+\]|[A-Za-z0-9_]+)$/)print $1}' || true); do
        if [ "$(uci -q get "firewall.$CS_ZONE.name" 2>/dev/null || true)" = lan ]; then
            CS_LAN_NETWORKS="$CS_LAN_NETWORKS $(uci -q get "firewall.$CS_ZONE.network" 2>/dev/null || true)"
        fi
    done
    for CS_NETWORK in $CS_LAN_NETWORKS; do
        case "$CS_NETWORK" in ''|*[!A-Za-z0-9_-]*) continue ;; esac
        CS_LAN_DEVICES="$CS_LAN_DEVICES $(uci -q get "network.$CS_NETWORK.device" 2>/dev/null || true) $(uci -q get "network.$CS_NETWORK.ifname" 2>/dev/null || true)"
        if command -v ubus >/dev/null 2>&1; then
            CS_LAN_DEVICES="$CS_LAN_DEVICES $(ubus call "network.interface.$CS_NETWORK" status 2>/dev/null | jsonfilter -e '@.l3_device' 2>/dev/null || true)"
        fi
    done
    CS_LAN_IP=
    for CS_LAN_DEVICE in $CS_LAN_DEVICES; do
        case "$CS_LAN_DEVICE" in ''|*[!A-Za-z0-9_.:-]*) continue ;; esac
        CS_LAN_IP=$(ip -4 -o addr show dev "$CS_LAN_DEVICE" scope global 2>/dev/null | awk '$3=="inet" {sub(/\/.*/,"",$4);n=split($4,a,".");ok=n==4;for(i=1;i<=n;i++)if(a[i]!~/^[0-9]+$/ || a[i]>255)ok=0;if(ok && a[1]!=0 && a[1]!=127)print $4;exit}' || true)
        [ -z "$CS_LAN_IP" ] || break
    done
    CS_WEB_SCHEME=http
    CS_WEB_LISTEN=$(uci -q get uhttpd.main.listen_http 2>/dev/null || true)
    if [ -z "$CS_WEB_LISTEN" ]; then CS_WEB_LISTEN=$(uci -q get uhttpd.main.listen_https 2>/dev/null || true); [ -z "$CS_WEB_LISTEN" ] || CS_WEB_SCHEME=https; fi
    CS_WEB_LISTEN=${CS_WEB_LISTEN%% *}; CS_WEB_PORT=${CS_WEB_LISTEN##*:}
    if ! csqtt_uint "$CS_WEB_PORT" || [ "$CS_WEB_PORT" -lt 1 ] || [ "$CS_WEB_PORT" -gt 65535 ]; then CS_WEB_PORT=80; [ "$CS_WEB_SCHEME" != https ] || CS_WEB_PORT=443; fi
    CS_WEB_SUFFIX=:$CS_WEB_PORT
    case "$CS_WEB_SCHEME:$CS_WEB_PORT" in http:80|https:443) CS_WEB_SUFFIX= ;; esac
    if [ -n "$CS_LAN_IP" ]; then printf 'CSQTT установлен. Откройте %s://%s%s/cgi-bin/luci/admin/services/csqtt\n' "$CS_WEB_SCHEME" "$CS_LAN_IP" "$CS_WEB_SUFFIX"
    else printf 'CSQTT установлен. Откройте LuCI этого роутера: Службы → CSQTT (адрес LAN не удалось определить).\n'; fi
    printf 'Первую настройку выполните в браузере. Резервная копия: %s\n' "$CS_BACKUP"
}
csqtt_portable_cleanup() {
    CS_EXIT=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$CS_CHANGED" = 1 ]; then csqtt_rollback || CS_EXIT=1; fi
    if [ "$CS_EXIT" != 0 ] && [ "$CS_CHANGED" = 0 ]; then
        csqtt_bootstrap_rollback || { printf 'CSQTT: Не удалось восстановить средства проверки; сохранён /etc/csqtt/installer-bootstrap.\n' >&2; CS_EXIT=1; }
    elif [ "$CS_EXIT" = 0 ]; then rm -rf /etc/csqtt/installer-bootstrap; fi
    csqtt_operation_release
    if [ "$CS_LOCKED" = 1 ] && [ "$CS_CHANGED" = 0 ]; then rm -f /var/lock/csqtt-maintenance/pid; rmdir /var/lock/csqtt-maintenance 2>/dev/null; fi
    if [ "$CS_EXIT" = 0 ]; then rm -rf "$CS_TMP"; else printf 'CSQTT: Закрытая диагностика сохранена: %s\n' "$CS_TMP" >&2; fi
    exit "$CS_EXIT"
}
csqtt_portable_main() (
    set -eu; umask 077
    [ "$(id -u)" = 0 ] || csqtt_portable_die 'Запустите установщик от root на роутере'
    for CS_TOOL in uclient-fetch sha256sum awk tar sync du; do command -v "$CS_TOOL" >/dev/null || csqtt_portable_die "В прошивке отсутствует необходимая команда: $CS_TOOL"; done
    unset OFFLINE_ROOT
    APK_CONFIG=/dev/null; export APK_CONFIG
    CS_RELEASE=${1:-latest}; csqtt_token "$CS_RELEASE" || csqtt_portable_die 'Недопустимая версия выпуска'
    CS_BASE="https://github.com/RATOR2000/csqtt-openwrt/releases/download/$CS_RELEASE"
    [ "$CS_RELEASE" != latest ] || CS_BASE=https://github.com/RATOR2000/csqtt-openwrt/releases/latest/download
    CS_TMP=$(mktemp -d /tmp/csqtt-portable.XXXXXX)
    CS_CHANGED=0 CS_LOCKED=0 CS_UPGRADE=0 CS_BACKUP=
    trap csqtt_portable_cleanup EXIT; trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM
    mkdir -p "$CS_TMP/assets" "$CS_TMP/keys" "$CS_TMP/projectkeys" "$CS_TMP/no-repositories" "$CS_TMP/repos" "$CS_TMP/sourcekeys"
    : > "$CS_TMP/empty-repositories"
    CS_OPENWRT=$(csqtt_release_value /etc/openwrt_release DISTRIB_RELEASE)
    CS_ARCH=$(csqtt_release_value /etc/openwrt_release DISTRIB_ARCH)
    [ "$(csqtt_release_value /etc/openwrt_release DISTRIB_ID):$(csqtt_release_value /etc/os-release ID)" = OpenWrt:openwrt ] && [ ! -e /etc/glversion ] || csqtt_portable_die 'Поддерживается только официальная OpenWrt 24.10/25.12'
    csqtt_token "$CS_ARCH" || csqtt_portable_die 'Неизвестная архитектура прошивки'
    case "$CS_OPENWRT:$(csqtt_has apk):$(csqtt_has opkg)" in
      24.10.[0-9]*:false:true) CS_PM=opkg ;;
      25.12.[0-9]*:true:false) CS_PM=apk ;;
      *) csqtt_portable_die 'Неподдерживаемая версия OpenWrt или менеджер пакетов' ;;
    esac
    printf 'dest root /\narch all 1\narch %s 10\noption check_signature 1\n' "$CS_ARCH" > "$CS_TMP/opkg.conf"
    csqtt_lock
    csqtt_bootstrap
    csqtt_stage 'Проверка платформы, подписи выпуска и доступного места'
    csqtt_probe_main > "$CS_TMP/probe.json"
    CS_PROFILE=$(csqtt_j "$CS_TMP/probe.json" '@.profile_id') CS_FAMILY=$(csqtt_j "$CS_TMP/probe.json" '@.family')
    CS_PM=$(csqtt_j "$CS_TMP/probe.json" '@.package_manager') CS_FORMAT=$(csqtt_j "$CS_TMP/probe.json" '@.package_format')
    CS_ARCH=$(csqtt_j "$CS_TMP/probe.json" '@.architecture') CS_BACKEND=$(csqtt_j "$CS_TMP/probe.json" '@.backend')
    csqtt_token "$CS_PROFILE" && csqtt_token "$CS_ARCH" || csqtt_portable_die 'Выпуск не соответствует версии, целевой платформе или архитектуре прошивки'
    case "$CS_FAMILY:$CS_PM" in official:apk|official:opkg) ;; *) csqtt_portable_die 'Выпуск не соответствует версии, целевой платформе или архитектуре прошивки' ;; esac
    cat > "$CS_TMP/project.pem" <<'CSQTT_PORTABLE_PUBLIC_KEY'
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETbV/mfygOtiJtOEqpvRlAazQEvb+
a2Y1lNcDNcPmDYDRB45yTNUvn6Ree4/eg+bWWf5kQeavIZvOLDB8iIcP4w==
-----END PUBLIC KEY-----
CSQTT_PORTABLE_PUBLIC_KEY
    cp "$CS_TMP/project.pem" "$CS_TMP/projectkeys/csqtt-public.pem"
    if [ "$CS_PM" = apk ]; then
        for CS_KEY_FILE in /lib/apk/keys/* /etc/apk/keys/*; do [ ! -f "$CS_KEY_FILE" ] || cp "$CS_KEY_FILE" "$CS_TMP/keys/"; done
        cp "$CS_TMP/project.pem" "$CS_TMP/keys/csqtt-public.pem"
    fi
    csqtt_recover
    csqtt_fetch catalogue.json "$CS_TMP/catalogue.json"; csqtt_fetch catalogue.sig "$CS_TMP/catalogue.sig"
    [ "$(wc -c < "$CS_TMP/catalogue.json")" -le 262144 ] || csqtt_portable_die 'Неверный или неоднозначный каталог выпуска'
    csqtt_signature "$CS_TMP/catalogue.json" "$CS_TMP/catalogue.sig"
    [ "$(csqtt_j "$CS_TMP/catalogue.json" '@.schema')" = 2 ] && [ "$(csqtt_j "$CS_TMP/catalogue.json" '@.upstream')" = amurcanov/csqtt@v2.1.9 ] || csqtt_portable_die 'Неподдерживаемая схема манифеста или каталога'
    CS_I=0 CS_MATCH=-1
    while [ -n "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_I]")" ]; do
        [ "$CS_I" -lt 128 ] || csqtt_portable_die 'Неверный или неоднозначный каталог выпуска'
        if [ "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_I].profile_id")" = "$CS_PROFILE" ]; then
            [ "$CS_MATCH" = -1 ] || csqtt_portable_die 'Неверный или неоднозначный каталог выпуска'; CS_MATCH=$CS_I
        fi
        CS_I=$((CS_I + 1))
    done
    [ "$CS_MATCH" != -1 ] || csqtt_portable_die 'Для этой версии, целевой платформы и архитектуры пока нет проверенного выпуска'
    CS_MANIFEST_NAME=$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].name")
    CS_SIGNATURE_NAME=$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.name")
    [ "$CS_MANIFEST_NAME" = "$CS_PROFILE-manifest.json" ] && [ "$CS_SIGNATURE_NAME" = "$CS_PROFILE-manifest.sig" ] || csqtt_portable_die 'Неверное имя или повтор файла выпуска'
    CS_MANIFEST="$CS_TMP/manifest.json"
    csqtt_fetch "$CS_MANIFEST_NAME" "$CS_MANIFEST"; csqtt_fetch "$CS_SIGNATURE_NAME" "$CS_TMP/manifest.sig"
    [ "$(wc -c < "$CS_MANIFEST")" -le 262144 ] || csqtt_portable_die 'Неверный или неоднозначный каталог выпуска'
    csqtt_bytes "$CS_MANIFEST" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].sha256")" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].size")"
    csqtt_bytes "$CS_TMP/manifest.sig" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.sha256")" "$(csqtt_j "$CS_TMP/catalogue.json" "@.profiles[$CS_MATCH].signature.size")"
    csqtt_signature "$CS_MANIFEST" "$CS_TMP/manifest.sig"
    csqtt_validate_tuple "$CS_MANIFEST"
    for CS_RESOURCE in overlay_free_kib tmp_free_kib mem_available_kib; do
        CS_MIN=$(csqtt_j "$CS_MANIFEST" "@.requirements.$CS_RESOURCE") CS_NOW=$(csqtt_j "$CS_TMP/probe.json" "@.resource.$CS_RESOURCE")
        csqtt_uint "$CS_MIN" && csqtt_uint "$CS_NOW" && [ "$CS_MIN" -gt 0 ] && [ "$CS_NOW" -ge "$CS_MIN" ] || csqtt_portable_die 'Недостаточно памяти или места для проверенного профиля'
    done
    printf 'dest root /\narch all 1\narch %s 10\noption check_signature 1\n' "$CS_ARCH" > "$CS_TMP/opkg.conf"
    if [ "$CS_PM" = apk ]; then
        for CS_KEY_FILE in /lib/apk/keys/* /etc/apk/keys/*; do [ ! -f "$CS_KEY_FILE" ] || cp "$CS_KEY_FILE" "$CS_TMP/keys/"; done
        cp "$CS_TMP/project.pem" "$CS_TMP/keys/csqtt-public.pem"
    fi
    CS_I=0
    while [ "$CS_I" -lt 3 ]; do csqtt_asset "@.packages[$CS_I]"; if [ "$CS_PM" = apk ]; then apk --keys-dir "$CS_TMP/projectkeys" verify "$CS_TMP/assets/$CS_ASSET_NAME" >"$CS_TMP/package-$CS_I.log" 2>&1 || csqtt_portable_die 'Подпись пакета CSQTT недействительна'; fi; CS_I=$((CS_I + 1)); done
    csqtt_bundle_sources
    for CS_DEP in $(csqtt_j "$CS_MANIFEST" '@.requirements.packages[*]'); do
        csqtt_token "$CS_DEP" || csqtt_portable_die 'Неверный состав подписанных зависимостей'
        if [ -z "$(csqtt_installed_version "$CS_DEP")" ]; then
            CS_FOUND=false
            for CS_BUNDLED in $(csqtt_j "$CS_MANIFEST" '@.dependency_bundle.packages[*].package'); do [ "$CS_DEP" != "$CS_BUNDLED" ] || CS_FOUND=true; done
            [ "$CS_FOUND" = true ] || csqtt_portable_die 'Отсутствует необходимая зависимость в подписанном автономном комплекте'
        fi
    done
    CS_COUNT=0
    for CS_ROLE in csqtt csqtt-captcha luci-app-csqtt; do [ -z "$(csqtt_installed_version "$CS_ROLE")" ] || CS_COUNT=$((CS_COUNT + 1)); done
    [ "$CS_COUNT" = 0 ] || [ "$CS_COUNT" = 3 ] || csqtt_portable_die 'Ранее установленные пакеты CSQTT неполны'
    if [ "$CS_COUNT" = 3 ]; then
        CS_UPGRADE=1
        csqtt_previous
    fi
    csqtt_stage 'Загрузка зависимостей завершена. Проверка установки и полного отката без сети'
    csqtt_snapshot - > "$CS_TMP/packages-before" || csqtt_portable_die 'Не удалось проверить исходный состав установленных пакетов'
    csqtt_clone "$CS_TMP/stage"
    csqtt_pm_install "$CS_TMP/stage" "$CS_TMP" 0 > "$CS_TMP/stage.log" 2>&1 || csqtt_portable_die 'Проверка автономной установки в изолированной базе завершилась ошибкой'
    csqtt_check_versions "$CS_TMP/stage" "$CS_TMP" || csqtt_portable_die 'Версии или состояние пакетов в изолированной базе не соответствуют манифесту'
    csqtt_snapshot "$CS_TMP/stage" > "$CS_TMP/packages-staged" || csqtt_portable_die 'Не удалось проверить состав пакетов после изолированной установки'
    csqtt_unchanged_packages "$CS_TMP/packages-before" "$CS_TMP/packages-staged" || csqtt_portable_die 'Проверенная транзакция изменила бы посторонние установленные пакеты'
    CS_STAGE_KIB=$(du -sk "$CS_TMP/stage" | awk '{print $1}')
    csqtt_uint "$CS_STAGE_KIB" || csqtt_portable_die 'Не удалось измерить распакованный размер пакетов'
    if [ "$CS_UPGRADE" = 1 ]; then
        csqtt_pm_install "$CS_TMP/stage" "$CS_TMP/previous" 1 > "$CS_TMP/restore-proof.log" 2>&1 || csqtt_portable_die 'Предыдущие пакеты нельзя восстановить без сети'
        csqtt_check_versions "$CS_TMP/stage" "$CS_TMP/previous" || csqtt_portable_die 'Предыдущие пакеты нельзя восстановить без сети'
    else csqtt_remove "$CS_TMP/stage" luci-app-csqtt csqtt-captcha csqtt > "$CS_TMP/restore-proof.log" 2>&1 || csqtt_portable_die 'Не удалось проверить удаление новых пакетов'; fi
    csqtt_remove_new "$CS_TMP/stage" "$CS_TMP/new-dependencies" "$CS_TMP" "$CS_TMP/packages-before" >> "$CS_TMP/restore-proof.log" 2>&1 || csqtt_portable_die 'Не удалось проверить автономный откат зависимостей'
    csqtt_snapshot "$CS_TMP/stage" > "$CS_TMP/packages-restored" || csqtt_portable_die 'Не удалось проверить состав пакетов после изолированного отката'
    csqtt_exact_packages "$CS_TMP/packages-before" "$CS_TMP/packages-restored" || csqtt_portable_die 'Проверенный откат не восстановил исходный состав пакетов'
    CS_BUNDLE_KIB=$(du -sk "$CS_TMP" | awk '{print $1}')
    csqtt_uint "$CS_BUNDLE_KIB" && [ "$(csqtt_free_kib /overlay)" -ge "$((CS_BUNDLE_KIB * 2 + CS_STAGE_KIB + 2048))" ] || csqtt_portable_die 'Недостаточно места для пакетов, полного журнала отката и сохранённого выпуска'
    csqtt_snapshot - > "$CS_TMP/packages-precommit" || csqtt_portable_die 'Не удалось повторно проверить исходный состав установленных пакетов'
    csqtt_exact_packages "$CS_TMP/packages-before" "$CS_TMP/packages-precommit" || csqtt_portable_die 'Состав системных пакетов изменился во время проверки; повторите установку'
    CS_BACKUP=/etc/csqtt/installer-transaction.new
    [ ! -d "$CS_BACKUP" ] || rm -rf "$CS_BACKUP"
    mkdir -p "$CS_BACKUP/config" /etc/csqtt/backups; chmod 0700 /etc/csqtt /etc/csqtt/backups "$CS_BACKUP"
    for CS_CONFIG in csqtt dhcp firewall network; do [ ! -f "/etc/config/$CS_CONFIG" ] || cp -p "/etc/config/$CS_CONFIG" "$CS_BACKUP/config/$CS_CONFIG"; done
    [ ! -f /etc/csqtt/platform.json ] || cp /etc/csqtt/platform.json "$CS_BACKUP/platform.json"
    [ "$CS_PM" != apk ] || cp /etc/apk/world "$CS_BACKUP/world"
    csqtt_copy_bundle "$CS_BACKUP/transaction"
    [ "$CS_UPGRADE" = 0 ] || cp -a "$CS_TMP/previous" "$CS_BACKUP/previous"
    cp "$CS_TMP/probe.json" "$CS_TMP/packages-before" "$CS_TMP/new-dependencies" "$CS_BACKUP/"
    printf '%s\n' "$CS_UPGRADE" > "$CS_BACKUP/upgrade"
    printf 'prepared\n' > "$CS_BACKUP/phase"
    cp -a "$CS_TMP/keys" "$CS_BACKUP/keys"
    csqtt_journal_hashes
    sync
    mv "$CS_BACKUP" /etc/csqtt/installer-transaction
    CS_BACKUP=/etc/csqtt/installer-transaction
    sync
    CS_CHANGED=1
    csqtt_phase installing
    csqtt_stage 'Установка проверенных пакетов и сохранение настроек'
    csqtt_pm_install - "$CS_BACKUP/transaction" 0 > "$CS_BACKUP/install.log" 2>&1 || csqtt_portable_die 'Автономная установка пакетов завершилась ошибкой'
    csqtt_check_versions - "$CS_TMP" || csqtt_portable_die 'Версии установленных пакетов не соответствуют подписанному манифесту'
    csqtt_snapshot - > "$CS_TMP/packages-installed" || csqtt_portable_die 'Не удалось проверить полный состав установленных пакетов'
    csqtt_unchanged_packages "$CS_TMP/packages-before" "$CS_TMP/packages-installed" || csqtt_portable_die 'Установленная транзакция изменила посторонние пакеты'
    csqtt_phase packages_installed
    # Persist the exact signed capability grant before runtime activation.
    printf '{"schema":1,"profile_id":"%s","family":"%s","firmware":"%s","openwrt":"%s","board":"%s","target":"%s","architecture":"%s","package_manager":"%s","backend":"%s","kernel":"%s","kernel_package":"%s","qualification":{"activation":true},"dns_binary":"/usr/libexec/csqtt/dnsmasq"}\n' \
      "$CS_PROFILE" "$CS_FAMILY" "$(csqtt_j "$CS_TMP/probe.json" '@.firmware')" "$(csqtt_j "$CS_TMP/probe.json" '@.openwrt')" "$(csqtt_j "$CS_TMP/probe.json" '@.board')" "$(csqtt_j "$CS_TMP/probe.json" '@.target')" "$CS_ARCH" "$CS_PM" "$CS_BACKEND" "$(csqtt_j "$CS_TMP/probe.json" '@.kernel')" "$(csqtt_j "$CS_TMP/probe.json" '@.kernel_package')" > /etc/csqtt/platform.json.new
    chmod 0600 /etc/csqtt/platform.json.new; mv /etc/csqtt/platform.json.new /etc/csqtt/platform.json
    /etc/init.d/rpcd restart > "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Не удалось перезапустить rpcd'
    if awk '$0=="uhttpd" {found=1} END {exit !found}' "$CS_TMP/new-dependencies"; then
        /etc/init.d/uhttpd enable >> "$CS_TMP/service.log" 2>&1 && /etc/init.d/uhttpd restart >> "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Не удалось запустить веб-интерфейс LuCI'
    fi
    if [ "$CS_UPGRADE" = 1 ] && [ "$(uci -q get csqtt.main.enabled 2>/dev/null || true)" = 1 ]; then /etc/init.d/csqtt restart >> "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Не удалось восстановить прежнее состояние клиента'; fi
    for CS_SERVICE in csqtt-captcha csqtt-health; do "/etc/init.d/$CS_SERVICE" enable >> "$CS_TMP/service.log" 2>&1 && "/etc/init.d/$CS_SERVICE" restart >> "$CS_TMP/service.log" 2>&1 || csqtt_portable_die 'Не удалось включить или перезапустить вспомогательную службу'; done
    mkdir -p /etc/csqtt/releases
    CS_CURRENT="/etc/csqtt/releases/accepted-$(date +%Y%m%d-%H%M%S)-$$"
    csqtt_copy_bundle "$CS_CURRENT"
    [ ! -e /etc/csqtt/releases/current ] || mv /etc/csqtt/releases/current "$CS_BACKUP/previous-current"
    mv "$CS_CURRENT" /etc/csqtt/releases/current
    csqtt_phase committed
    CS_CHANGED=0
    csqtt_archive_journal
    csqtt_finish_url
)
