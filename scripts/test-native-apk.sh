#!/bin/sh
# Native APK 3.0.5 checks. Every APK operation is scoped to a disposable root.
# Usage: sudo sh scripts/test-native-apk.sh /absolute/sdk/staging_dir/host/bin/apk /absolute/dist
set -eu
umask 077
APK_CONFIG=/dev/null
export APK_CONFIG
die() { echo "native APK: $*" >&2; exit 1; }
[ "$#" -eq 2 ] || die 'Expected the SDK apk executable and compiled package directory.'
APK=$1
case "$APK" in /*) ;; *) die 'Pass an absolute SDK apk path.' ;; esac
[ -x "$APK" ] || die 'SDK apk is not executable.'
[ "$(id -u)" = 0 ] || die 'Run this isolated native check as root in the Linux CI job.'
PACKAGE_DIR=$(cd "$2" && pwd -P)
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
for TOOL in openssl python3 sha256sum cp find grep cmp qemu-aarch64; do command -v "$TOOL" >/dev/null || die "Missing host tool: $TOOL"; done
set -- "$PACKAGE_DIR"/*.apk
[ "$#" -eq 3 ] || die 'Expected exactly three compiled SDK APKs.'
TMP=$(mktemp -d /tmp/csqtt-native-apk.XXXXXX)
SERVER_PID=
cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    set +e
    [ -z "$SERVER_PID" ] || kill "$SERVER_PID" 2>/dev/null
    rm -f "$TMP/signing.pem" "$TMP/wrong-signing.pem"
    if [ "$status" -eq 0 ]; then rm -rf "$TMP"; else echo "Native APK diagnostics retained in $TMP (ephemeral private keys removed)." >&2; fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
TOOLS="$TMP/tools-root"
mkdir -p "$TOOLS/etc/apk/keys" "$TOOLS/etc/apk/wrong-keys" "$TMP/signed-sdk" "$TMP/repo" "$TMP/payloads"
tools_apk() { "$APK" --root "$TOOLS" --keys-dir etc/apk/keys "$@"; }
# APK 3.0.5 adbsign parses the old signature before loading trusted keys and
# reports per-file failures without a failing exit status. Accept input only
# for this local artifact transformation; every verification stays strict.
fixture_adbsign() {
    tools_apk --allow-untrusted adbsign "$@" > "$TMP/adbsign.txt" 2>&1
    [ ! -s "$TMP/adbsign.txt" ] || die 'adbsign emitted diagnostics; inspect adbsign.txt.'
}
case "$(tools_apk --version)" in *'apk-tools 3.0.5'*) ;; *) die 'The pinned SDK APK 3.0.5 is required.' ;; esac
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP/signing.pem"
openssl pkey -in "$TMP/signing.pem" -pubout -out "$TOOLS/etc/apk/keys/fixture.pem" >/dev/null
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP/wrong-signing.pem"
openssl pkey -in "$TMP/wrong-signing.pem" -pubout -out "$TOOLS/etc/apk/wrong-keys/fixture.pem" >/dev/null
sha256sum "$PACKAGE_DIR"/*.apk > "$TMP/sdk-before.sha256"
CORE= CAPTCHA= LUCI=
for PACKAGE in "$PACKAGE_DIR"/*.apk; do
    NAME=${PACKAGE##*/}
    case "$NAME" in
        csqtt-captcha-[0-9]*.apk) [ -z "$CAPTCHA" ] || die 'Duplicate CAPTCHA APK.'; CAPTCHA=$NAME; KIND=captcha ;;
        luci-app-csqtt-[0-9]*.apk) [ -z "$LUCI" ] || die 'Duplicate LuCI APK.'; LUCI=$NAME; KIND=luci ;;
        csqtt-[0-9]*.apk) [ -z "$CORE" ] || die 'Duplicate core APK.'; CORE=$NAME; KIND=core ;;
        *) die 'Unexpected SDK APK filename.' ;;
    esac
    cp "$PACKAGE" "$TMP/signed-sdk/$NAME"
    fixture_adbsign --sign-key "$TMP/signing.pem" --reset-signatures "$TMP/signed-sdk/$NAME"
    tools_apk verify "$TMP/signed-sdk/$NAME" >/dev/null
    if "$APK" --root "$TOOLS" --keys-dir etc/apk/wrong-keys verify "$TMP/signed-sdk/$NAME" > "$TMP/wrong-key.txt" 2>&1; then die 'An SDK APK was accepted with the wrong key.'; fi
    mkdir -p "$TMP/extracted/$KIND"
    # extract never executes package scripts; APK 3.0.5 accepts --no-scripts
    # only for the add/del applets.
    tools_apk extract --destination "$TMP/extracted/$KIND" "$TMP/signed-sdk/$NAME" > "$TMP/extract-$KIND.txt" 2>&1 || die "SDK payload extraction failed; inspect extract-$KIND.txt."
    tools_apk adbdump --format json "$TMP/signed-sdk/$NAME" > "$TMP/extracted/$KIND.json"
done
[ -n "$CORE" ] && [ -n "$CAPTCHA" ] && [ -n "$LUCI" ] || die 'Missing SDK package kind.'
sha256sum "$PACKAGE_DIR"/*.apk > "$TMP/sdk-after.sha256"
cmp "$TMP/sdk-before.sha256" "$TMP/sdk-after.sha256"
python3 - "$TMP/extracted" "$ROOT" <<'NATIVE_APK_PAYLOAD'
import json, pathlib, re, stat, sys
extracted, source = map(pathlib.Path, sys.argv[1:])
packages = {
    'core': ('csqtt', 'aarch64_cortex-a53', {
        'kmod-tun', 'ip-full', 'firewall4', 'nftables-json', 'dnsmasq-full',
        'ucode', 'ucode-mod-fs', 'ucode-mod-uci', 'ucode-mod-ubus', 'jsonfilter', 'conntrack',
    }, {
        'usr/bin/csqtt-client': 0o755,
        'usr/libexec/csqtt/manage': 0o755, 'usr/libexec/csqtt/tun-hook': 0o755,
        'etc/init.d/csqtt': 0o755, 'etc/init.d/csqtt-dns': 0o755,
        'etc/hotplug.d/iface/90-csqtt': 0o755,
        'etc/config/csqtt': 0o600, 'etc/csqtt/policy.nft': 0o600,
        'usr/share/csqtt/policy.uc': 0o644, 'usr/share/csqtt/runtime.uc': 0o644,
        'usr/share/licenses/csqtt/LICENSE': 0o644,
    }),
    'captcha': ('csqtt-captcha', 'aarch64_cortex-a53', {'csqtt', 'ca-bundle'}, {
        'usr/bin/csqtt-captcha': 0o755, 'etc/init.d/csqtt-captcha': 0o755,
        'etc/hotplug.d/iface/91-csqtt-captcha': 0o755,
    }),
    'luci': ('luci-app-csqtt', 'noarch', {'csqtt', 'csqtt-captcha', 'luci-base', 'rpcd'}, {
        'usr/libexec/rpcd/csqtt': 0o755, 'etc/uci-defaults/90-luci-csqtt': 0o644,
        'usr/share/rpcd/acl.d/luci-app-csqtt.json': 0o644,
        'usr/share/luci/menu.d/luci-app-csqtt.json': 0o644,
        **{'www/luci-static/resources/view/csqtt/' + page + '.js': 0o644
           for page in ('overview', 'settings', 'policies', 'diagnostics')},
        **{'www/luci-static/resources/csqtt/' + asset: 0o644
           for asset in ('api.js', 'model.js', 'style.css')},
    }),
}
for kind, (name, architecture, dependencies, files) in packages.items():
    info = json.loads((extracted / (kind + '.json')).read_text())['info']
    assert info['name'] == name and info['arch'] == architecture, name + ': metadata mismatch'
    declared = {re.split(r'[<>=~]', dependency, maxsplit=1)[0]
                for dependency in info.get('depends', []) if not dependency.startswith('!')}
    assert dependencies <= declared, name + ': missing required dependencies'
    for relative, mode in files.items():
        path = extracted / kind / relative
        metadata = path.lstat()
        assert stat.S_ISREG(metadata.st_mode) and metadata.st_size > 0, name + ': invalid payload ' + relative
        assert stat.S_IMODE(metadata.st_mode) == mode, name + ': wrong mode ' + relative
        if relative.endswith('.json'):
            json.loads(path.read_text())
assert (extracted / 'core/usr/share/licenses/csqtt/LICENSE').read_bytes() == (source / 'vendor/csqtt/LICENSE').read_bytes(), 'Upstream license payload mismatch'
assert (extracted / 'core/etc/config/csqtt').read_bytes() == (source / 'openwrt/csqtt/files/csqtt.config').read_bytes(), 'Default private UCI configuration mismatch'
print('native APK: required payloads, permissions, architecture, dependencies and upstream license passed.')
NATIVE_APK_PAYLOAD
python3 "$ROOT/scripts/test-arm64.py" "$TMP/extracted/core/usr/bin/csqtt-client" "$TMP/extracted/captcha/usr/bin/csqtt-captcha"
python3 "$ROOT/scripts/test-arm64-tun.py" "$TMP/extracted/core/usr/bin/csqtt-client"
# These synthetic packages exercise the same conflict, dependency and cache
# mechanics as the installer. No architecture-specific payload is executed.
mkdir -p "$TMP/payloads/old/usr/share/csqtt-native-test" "$TMP/payloads/full/usr/share/csqtt-native-test" "$TMP/payloads/dependency/usr/share/csqtt-native-test" "$TMP/payloads/app/usr/share/csqtt-native-test"
printf 'original DNS fixture\n' > "$TMP/payloads/old/usr/share/csqtt-native-test/dns.txt"
printf 'full DNS fixture\n' > "$TMP/payloads/full/usr/share/csqtt-native-test/dns.txt"
printf 'dependency fixture\n' > "$TMP/payloads/dependency/usr/share/csqtt-native-test/dependency.txt"
printf 'application fixture\n' > "$TMP/payloads/app/usr/share/csqtt-native-test/app.txt"
cat > "$TMP/post-install" <<'NATIVE_APK_SCRIPT'
#!/bin/sh
printf 'package script unexpectedly ran\n' > native-script-ran
exit 99
NATIVE_APK_SCRIPT
make_fixture() {
    name=$1
    payload=$2
    shift 2
    tools_apk --compression none --sign-key "$TMP/signing.pem" mkpkg --output "$TMP/repo/$name-1.0-r1.apk" --files "$TMP/payloads/$payload" --info "name:$name" --info version:1.0-r1 --info arch:aarch64_cortex-a53 --info license:MIT --info 'description:isolated native APK fixture' --script "post-install:$TMP/post-install" "$@"
    tools_apk verify "$TMP/repo/$name-1.0-r1.apk" >/dev/null
}
make_fixture csqtt-native-old old --info provides:csqtt-native-dns=1.0-r1
make_fixture csqtt-native-dependency dependency
make_fixture csqtt-native-full full --info provides:csqtt-native-dns=1.0-r1 --info 'depends:csqtt-native-dependency=1.0-r1 !csqtt-native-old'
make_fixture csqtt-native-app app --info depends:csqtt-native-full=1.0-r1
make_fixture csqtt-native-broken app --info depends:csqtt-native-missing=1.0-r1
tools_apk --sign-key "$TMP/signing.pem" mkndx --output "$TMP/repo/packages.adb" --pkgname-spec '${name}-${version}.apk' "$TMP/repo/"*.apk
tools_apk verify "$TMP/repo/packages.adb" >/dev/null
cp "$TMP/repo/csqtt-native-app-1.0-r1.apk" "$TMP/app.apk"
cp "$TMP/repo/csqtt-native-old-1.0-r1.apk" "$TMP/original-dns.apk"
cp "$TMP/app.apk" "$TMP/unsigned.apk"
fixture_adbsign --reset-signatures "$TMP/unsigned.apk"
if tools_apk verify "$TMP/unsigned.apk" > "$TMP/unsigned.txt" 2>&1; then die 'Unsigned APK accepted.'; fi
cp "$TMP/app.apk" "$TMP/tampered.apk"
python3 - "$TMP/tampered.apk" <<'NATIVE_APK_TAMPER'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
# Flipping the last compressed byte can change only unused padding, leaving
# authenticated contents intact. Alter a known signed metadata value instead.
# Fixture packages are uncompressed so no compressor details are assumed.
data = path.read_bytes()
original = b'isolated native APK fixture'
changed = b'Isolated native APK fixture'
assert data.startswith(b'ADB.') and data.count(original) == 1, 'Unexpected native APK fixture format'
path.write_bytes(data.replace(original, changed, 1))
NATIVE_APK_TAMPER
if tools_apk verify "$TMP/tampered.apk" > "$TMP/tampered.txt" 2>&1; then die 'Tampered APK accepted.'; fi
# The repository is served only on loopback. Stop it before the offline proof
# so an accidentally omitted no-network flag cannot hide missing cache files.
python3 - "$TMP/repo" "$TMP/port" <<'NATIVE_APK_SERVER' > "$TMP/repository-server.txt" 2>&1 &
import functools, http.server, pathlib, sys
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
handler = functools.partial(QuietHandler, directory=sys.argv[1])
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
pathlib.Path(sys.argv[2]).write_text(str(server.server_port))
server.serve_forever()
NATIVE_APK_SERVER
SERVER_PID=$!
TRIES=0
while [ ! -s "$TMP/port" ]; do
    TRIES=$((TRIES + 1))
    [ "$TRIES" -lt 50 ] || die 'Local fixture repository did not start.'
    kill -0 "$SERVER_PID" 2>/dev/null || die 'Local fixture repository exited.'
    sleep 0.1
done
PORT=$(cat "$TMP/port")
prepare_root() {
    root=$1
    case "$root" in "$TMP/"*) ;; *) die 'Root escaped the disposable directory.' ;; esac
    mkdir -p "$root/etc/apk/keys" "$root/var/cache/apk"
    cp "$TOOLS/etc/apk/keys/fixture.pem" "$root/etc/apk/keys/"
    printf 'http://127.0.0.1:%s/packages.adb\n' "$PORT" > "$root/etc/apk/repositories"
}
root_apk() {
    root=$1
    shift
    case "$root" in "$TMP/"*) ;; *) die 'APK root escaped the disposable directory.' ;; esac
    "$APK" --root "$root" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-scripts "$@"
}
root_query() {
    root=$1
    case "$root" in "$TMP/"*) ;; *) die 'Query root escaped the disposable directory.' ;; esac
    # Unlike info, query requires a selection term; no arguments return [].
    "$APK" --root "$root" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-network query --installed --all-matches --fields name,version,status --format json '*'
}
# A fresh router can have no cached index. Unlike add, fetch does not refresh
# it automatically; exercise the installer's explicit direct-index read.
FETCH_ROOT="$TMP/fetch-root"
prepare_root "$FETCH_ROOT"
mkdir -p "$TMP/fetched"
fetch_original() {
    fetch_version=$1
    shift
    "$APK" --root "$FETCH_ROOT" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --repositories-file "$FETCH_ROOT/etc/apk/repositories" fetch "$@" --output "$TMP/fetched" "csqtt-native-old=$fetch_version"
}
if fetch_original 1.0-r1 > "$TMP/fresh-fetch.txt" 2>&1; then die 'An empty index cache unexpectedly satisfied a read-only fetch.'; fi
# APK 3.0.5's ordinary query compares name with the entire name=version term.
if fetch_original 1.0-r1 --no-cache >> "$TMP/fresh-fetch.txt" 2>&1; then die 'The pinned ordinary name=version query unexpectedly matched.'; fi
if ! fetch_original 1.0-r1 --no-cache --recursive >> "$TMP/fresh-fetch.txt" 2>&1; then
    cat "$TMP/fresh-fetch.txt" >&2
    die 'Direct signed-index fetch failed.'
fi
tools_apk verify "$TMP/fetched/csqtt-native-old-1.0-r1.apk" >/dev/null
cmp "$TMP/fetched/csqtt-native-old-1.0-r1.apk" "$TMP/original-dns.apk"
if fetch_original 9.0-r1 --no-cache --recursive >> "$TMP/fresh-fetch.txt" 2>&1; then die 'An unavailable exact version was replaced by a different version.'; fi
[ ! -e "$FETCH_ROOT/etc/apk/world" ] && [ ! -e "$FETCH_ROOT/lib/apk/db/installed" ] || die 'Read-only fetch changed package state.'
echo 'native APK: fresh signed-index exact-version fetch passed; ordinary selection and unavailable version rejected; package/state verified.'
BASE="$TMP/base"
prepare_root "$BASE"
root_apk "$BASE" add --initdb "$TMP/original-dns.apk" > "$TMP/base-install.txt" 2>&1
cp "$BASE/etc/apk/world" "$TMP/original-world"
root_query "$BASE" > "$TMP/baseline.json"
python3 - "$TMP/baseline.json" <<'NATIVE_APK_BASELINE'
import json, pathlib, sys
packages = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert packages == [{'name': 'csqtt-native-old', 'version': '1.0-r1', 'status': ['installed']}], packages
NATIVE_APK_BASELINE
# Exercise the installer's read-only preflight command against the real CLI.
"$APK" --root "$BASE" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-network info --from installed > "$TMP/installed-names.txt"
[ "$(cat "$TMP/installed-names.txt")" = csqtt-native-old ] || die 'Installed-package name query differs from installer assumptions.'
if root_apk "$BASE" add --simulate "$TMP/repo/csqtt-native-broken-1.0-r1.apk" > "$TMP/missing-dependency.txt" 2>&1; then die 'An unsatisfied dependency was accepted.'; fi
if root_apk "$BASE" add --simulate "$TMP/app.apk" csqtt-native-full > "$TMP/conflict.txt" 2>&1; then die 'DNS provider conflict was not detected.'; fi
cmp "$BASE/etc/apk/world" "$TMP/original-world"
STAGE="$TMP/stage"
mkdir -p "$STAGE"
cp -aL "$BASE/." "$STAGE/"
root_apk "$STAGE" del csqtt-native-old > "$TMP/stage.txt" 2>&1
root_apk "$STAGE" add --simulate "$TMP/app.apk" csqtt-native-full >> "$TMP/stage.txt" 2>&1
root_apk "$STAGE" --cache-predownload add "$TMP/app.apk" csqtt-native-full >> "$TMP/stage.txt" 2>&1
[ -s "$STAGE/usr/share/csqtt-native-test/dependency.txt" ] || die 'The dependency was not installed in the stage.'
[ -s "$STAGE/usr/share/csqtt-native-test/app.txt" ] || die 'The application payload is missing.'
if grep -q '^csqtt-native-dependency' "$STAGE/etc/apk/world"; then die 'A transitive dependency became a world root.'; fi
[ -n "$(find "$STAGE/var/cache/apk" -type f -name 'csqtt-native-dependency-*.apk' -print)" ] || die 'Dependency was not cached under the relative cache path.'
cmp "$BASE/etc/apk/world" "$TMP/original-world"
root_query "$BASE" > "$TMP/baseline-after-stage.json"
cmp "$TMP/baseline.json" "$TMP/baseline-after-stage.json"
kill "$SERVER_PID"
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=
MISSING_CACHE="$TMP/missing-cache"
mkdir -p "$MISSING_CACHE"
cp -aL "$BASE/." "$MISSING_CACHE/"
root_apk "$MISSING_CACHE" --no-network del csqtt-native-old > "$TMP/missing-cache.txt" 2>&1
if root_apk "$MISSING_CACHE" --no-network add --simulate "$TMP/app.apk" csqtt-native-full >> "$TMP/missing-cache.txt" 2>&1; then die 'An incomplete dependency cache was accepted offline.'; fi
OFFLINE="$TMP/offline"
mkdir -p "$OFFLINE"
cp -aL "$BASE/." "$OFFLINE/"
cp -aL "$STAGE/var/cache/apk/." "$OFFLINE/var/cache/apk/"
root_apk "$OFFLINE" --no-network del csqtt-native-old > "$TMP/offline.txt" 2>&1
root_apk "$OFFLINE" --no-network add --simulate "$TMP/app.apk" csqtt-native-full >> "$TMP/offline.txt" 2>&1
root_apk "$OFFLINE" --no-network add "$TMP/app.apk" csqtt-native-full >> "$TMP/offline.txt" 2>&1
root_query "$OFFLINE" > "$TMP/offline-installed.json"
python3 - "$TMP/offline-installed.json" <<'NATIVE_APK_ASSERT'
import json, pathlib, sys
packages = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert {item['name'] for item in packages} == {'csqtt-native-app', 'csqtt-native-full', 'csqtt-native-dependency'}, packages
assert all(item['version'] == '1.0-r1' for item in packages), packages
assert all(item.get('status') == ['installed'] for item in packages), packages
NATIVE_APK_ASSERT
root_apk "$OFFLINE" --no-network del csqtt-native-app csqtt-native-full >> "$TMP/offline.txt" 2>&1
root_apk "$OFFLINE" --no-network add "$TMP/original-dns.apk" >> "$TMP/offline.txt" 2>&1
root_query "$OFFLINE" > "$TMP/rollback-installed.json"
cmp "$TMP/baseline.json" "$TMP/rollback-installed.json"
cmp "$TMP/original-world" "$OFFLINE/etc/apk/world"
[ -z "$(find "$TMP" -name native-script-ran -print)" ] || die 'A package script executed despite no-scripts.'
rm -f "$TMP/signing.pem" "$TMP/wrong-signing.pem"
echo 'native APK: three SDK package signatures verified; wrong-key, unsigned and tampered APKs rejected; isolated DNS conflict/replacement, staged dependency cache, offline install and exact rollback passed.'
