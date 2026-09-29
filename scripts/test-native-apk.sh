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
for TOOL in openssl python3 sha256sum cp find grep cmp; do command -v "$TOOL" >/dev/null || die "Missing host tool: $TOOL"; done
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
        csqtt-captcha-[0-9]*.apk) [ -z "$CAPTCHA" ] || die 'Duplicate CAPTCHA APK.'; CAPTCHA=$NAME ;;
        luci-app-csqtt-[0-9]*.apk) [ -z "$LUCI" ] || die 'Duplicate LuCI APK.'; LUCI=$NAME ;;
        csqtt-[0-9]*.apk) [ -z "$CORE" ] || die 'Duplicate core APK.'; CORE=$NAME ;;
        *) die 'Unexpected SDK APK filename.' ;;
    esac
    cp "$PACKAGE" "$TMP/signed-sdk/$NAME"
    tools_apk --sign-key "$TMP/signing.pem" adbsign --reset-signatures "$TMP/signed-sdk/$NAME"
    tools_apk verify "$TMP/signed-sdk/$NAME" >/dev/null
    if "$APK" --root "$TOOLS" --keys-dir etc/apk/wrong-keys verify "$TMP/signed-sdk/$NAME" > "$TMP/wrong-key.txt" 2>&1; then die 'An SDK APK was accepted with the wrong key.'; fi
done
[ -n "$CORE" ] && [ -n "$CAPTCHA" ] && [ -n "$LUCI" ] || die 'Missing SDK package kind.'
sha256sum "$PACKAGE_DIR"/*.apk > "$TMP/sdk-after.sha256"
cmp "$TMP/sdk-before.sha256" "$TMP/sdk-after.sha256"
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
    tools_apk --sign-key "$TMP/signing.pem" mkpkg --output "$TMP/repo/$name-1.0-r1.apk" --files "$TMP/payloads/$payload" --info "name:$name" --info version:1.0-r1 --info arch:aarch64_cortex-a53 --info license:MIT --info 'description:isolated native APK fixture' --script "post-install:$TMP/post-install" "$@"
}
make_fixture csqtt-native-old old --info provides:csqtt-native-dns=1.0-r1
make_fixture csqtt-native-dependency dependency
make_fixture csqtt-native-full full --info provides:csqtt-native-dns=1.0-r1 --info 'depends:csqtt-native-dependency=1.0-r1 !csqtt-native-old'
make_fixture csqtt-native-app app --info depends:csqtt-native-full=1.0-r1
make_fixture csqtt-native-broken app --info depends:csqtt-native-missing=1.0-r1
tools_apk --sign-key "$TMP/signing.pem" mkndx --output "$TMP/repo/packages.adb" --pkgname-spec '${name}-${version}.apk' "$TMP/repo/"*.apk
cp "$TMP/repo/csqtt-native-app-1.0-r1.apk" "$TMP/app.apk"
cp "$TMP/repo/csqtt-native-old-1.0-r1.apk" "$TMP/original-dns.apk"
cp "$TMP/app.apk" "$TMP/unsigned.apk"
tools_apk adbsign --reset-signatures "$TMP/unsigned.apk"
if tools_apk verify "$TMP/unsigned.apk" > "$TMP/unsigned.txt" 2>&1; then die 'Unsigned APK accepted.'; fi
cp "$TMP/app.apk" "$TMP/tampered.apk"
python3 - "$TMP/tampered.apk" <<'NATIVE_APK_TAMPER'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
data = bytearray(path.read_bytes())
data[-1] ^= 1
path.write_bytes(data)
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
BASE="$TMP/base"
prepare_root "$BASE"
root_apk "$BASE" add --initdb "$TMP/original-dns.apk" > "$TMP/base-install.txt" 2>&1
cp "$BASE/etc/apk/world" "$TMP/original-world"
root_apk "$BASE" query --installed --fields name,version,status --format json > "$TMP/baseline.json"
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
root_apk "$BASE" query --installed --fields name,version,status --format json > "$TMP/baseline-after-stage.json"
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
root_apk "$OFFLINE" query --installed --fields name,version,status --format json > "$TMP/offline-installed.json"
python3 - "$TMP/offline-installed.json" <<'NATIVE_APK_ASSERT'
import json, pathlib, sys
packages = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert {item['name'] for item in packages} == {'csqtt-native-app', 'csqtt-native-full', 'csqtt-native-dependency'}, packages
assert all(item['version'] == '1.0-r1' for item in packages), packages
assert all('broken-scripts' not in str(item.get('status', '')) for item in packages), packages
NATIVE_APK_ASSERT
root_apk "$OFFLINE" --no-network del csqtt-native-app csqtt-native-full >> "$TMP/offline.txt" 2>&1
root_apk "$OFFLINE" --no-network add "$TMP/original-dns.apk" >> "$TMP/offline.txt" 2>&1
root_apk "$OFFLINE" query --installed --fields name,version,status --format json > "$TMP/rollback-installed.json"
cmp "$TMP/baseline.json" "$TMP/rollback-installed.json"
cmp "$TMP/original-world" "$OFFLINE/etc/apk/world"
[ -z "$(find "$TMP" -name native-script-ran -print)" ] || die 'A package script executed despite no-scripts.'
rm -f "$TMP/signing.pem" "$TMP/wrong-signing.pem"
echo 'native APK: three SDK package signatures verified; wrong-key, unsigned and tampered APKs rejected; isolated DNS conflict/replacement, staged dependency cache, offline install and exact rollback passed.'
