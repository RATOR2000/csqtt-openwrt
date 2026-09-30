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
    unsigned=0
    if [ "${1:-}" = --unsigned ]; then
        [ "$name" = csqtt-native-old ] || die 'Only the original DNS fixture may be unsigned.'
        unsigned=1
        shift
        set -- mkpkg "$@"
    else
        set -- --sign-key "$TMP/signing.pem" mkpkg "$@"
    fi
    tools_apk --compression none "$@" --output "$TMP/repo/$name-1.0-r1.apk" --files "$TMP/payloads/$payload" --info "name:$name" --info version:1.0-r1 --info arch:aarch64_cortex-a53 --info license:MIT --info 'description:isolated native APK fixture' --script "post-install:$TMP/post-install"
    if [ "$unsigned" = 1 ]; then
        if tools_apk verify "$TMP/repo/$name-1.0-r1.apk" > "$TMP/original-unsigned.txt" 2>&1; then die 'The original DNS fixture unexpectedly has a trusted standalone signature.'; fi
    else
        tools_apk verify "$TMP/repo/$name-1.0-r1.apk" >/dev/null
    fi
}
make_fixture csqtt-native-old old --unsigned --info provides:csqtt-native-dns=1.0-r1
make_fixture csqtt-native-dependency dependency
make_fixture csqtt-native-full full --info provides:csqtt-native-dns=1.0-r1 --info 'depends:csqtt-native-dependency=1.0-r1 !csqtt-native-old'
make_fixture csqtt-native-app app --info depends:csqtt-native-full=1.0-r1
make_fixture csqtt-native-broken app --info depends:csqtt-native-missing=1.0-r1
# Index creation accepts only these locally generated inputs. Verification and
# every installation below require trust, including the unsigned DNS package.
tools_apk --allow-untrusted --sign-key "$TMP/signing.pem" mkndx --output "$TMP/repo/packages.adb" --pkgname-spec '${name}-${version}.apk' "$TMP/repo/"*.apk
tools_apk verify "$TMP/repo/packages.adb" >/dev/null
if "$APK" --root "$TOOLS" --keys-dir etc/apk/wrong-keys verify "$TMP/repo/packages.adb" > "$TMP/wrong-index.txt" 2>&1; then die 'The repository index was accepted with the wrong key.'; fi
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
root_read_apk() {
    root=$1
    shift
    case "$root" in "$TMP/"*) ;; *) die 'Read-only APK root escaped the disposable directory.' ;; esac
    "$APK" --root "$root" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk "$@"
}
root_query() {
    root=$1
    case "$root" in "$TMP/"*) ;; *) die 'Query root escaped the disposable directory.' ;; esac
    # Unlike info, query requires a selection term; no arguments return [].
    "$APK" --root "$root" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --no-network query --installed --all-matches --fields name,version,status --format json '*'
}
# OpenWrt signs its index rather than individual DNS APKs. Cache the signed
# index and its authenticated package identity before any DNS replacement.
FETCH_ROOT="$TMP/fetch-root"
prepare_root "$FETCH_ROOT"
mkdir -p "$TMP/fetched"
fetch_original() {
    fetch_version=$1
    fetch_output=$2
    shift 2
    "$APK" --root "$FETCH_ROOT" --arch aarch64_cortex-a53 --keys-dir etc/apk/keys --cache-dir var/cache/apk --repositories-file "$FETCH_ROOT/etc/apk/repositories" fetch "$@" --output "$fetch_output" "csqtt-native-old=$fetch_version"
}
# An unconstrained name distinguishes a missing index from the separate
# name=version matching bug in the ordinary APK 3.0.5 query.
if root_read_apk "$FETCH_ROOT" fetch --output "$TMP/fetched" csqtt-native-old > "$TMP/fresh-fetch.txt" 2>&1; then die 'An empty index cache unexpectedly satisfied a read-only fetch.'; fi
# APK 3.0.5's ordinary query compares name with the entire name=version term.
if fetch_original 1.0-r1 "$TMP/fetched" --no-cache >> "$TMP/fresh-fetch.txt" 2>&1; then die 'The pinned ordinary name=version query unexpectedly matched.'; fi
if ! root_read_apk "$FETCH_ROOT" update >> "$TMP/fresh-fetch.txt" 2>&1; then
    cat "$TMP/fresh-fetch.txt" >&2
    die 'Signed-index cache update failed.'
fi
if ! fetch_original 1.0-r1 "$FETCH_ROOT/var/cache/apk" --recursive --pkgname-spec '${name}-${version}.${hash:8}.apk' >> "$TMP/fresh-fetch.txt" 2>&1; then
    cat "$TMP/fresh-fetch.txt" >&2
    die 'Unsigned DNS fetch through the signed index failed.'
fi
set -- "$FETCH_ROOT/var/cache/apk"/csqtt-native-old-1.0-r1.*.apk
[ "$#" -eq 1 ] && [ -f "$1" ] || die 'The exact original DNS package is missing from the fresh cache.'
ORIGINAL_CACHE_NAME=${1##*/}
cmp "$1" "$TMP/original-dns.apk"
if tools_apk verify "$1" > "$TMP/fetched-unsigned.txt" 2>&1; then die 'Standalone verification unexpectedly authenticated the unsigned DNS cache.'; fi
# fetch ignores solver failure in its exit status. The installer also requires
# an exact file in its fresh rollback directory; no download means rejection.
mkdir -p "$TMP/missing-version"
fetch_original 9.0-r1 "$TMP/missing-version" --recursive >> "$TMP/fresh-fetch.txt" 2>&1 || true
[ -z "$(find "$TMP/missing-version" -type f -name '*.apk' -print)" ] || die 'An unavailable exact version was replaced by a different version.'
[ ! -e "$FETCH_ROOT/etc/apk/world" ] && [ ! -e "$FETCH_ROOT/lib/apk/db/installed" ] || die 'Read-only fetch changed package state.'
WRONG_INDEX="$TMP/wrong-index-root"
prepare_root "$WRONG_INDEX"
cp "$TOOLS/etc/apk/wrong-keys/fixture.pem" "$WRONG_INDEX/etc/apk/keys/fixture.pem"
root_read_apk "$WRONG_INDEX" update > "$TMP/wrong-index-update.txt" 2>&1 || true
if root_apk "$WRONG_INDEX" --no-network add --initdb csqtt-native-old=1.0-r1 >> "$TMP/wrong-index-update.txt" 2>&1; then die 'An unsigned DNS package was installed through an untrusted index.'; fi

echo 'native APK: unsigned original DNS fetched through a signed index; wrong index key, ordinary selection and unavailable version rejected.'
BASE="$TMP/base"
prepare_root "$BASE"
cp -a "$FETCH_ROOT/var/cache/apk/." "$BASE/var/cache/apk/"
root_apk "$BASE" --no-network --cache-predownload add --initdb csqtt-native-old > "$TMP/base-install.txt" 2>&1
cp "$BASE/etc/apk/world" "$TMP/original-world"
root_query "$BASE" > "$TMP/baseline.json"
python3 - "$TMP/baseline.json" <<'NATIVE_APK_BASELINE'
import json, pathlib, sys
packages = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert packages == [{'name': 'csqtt-native-old', 'version': '1.0-r1', 'status': ['installed']}], packages
NATIVE_APK_BASELINE
ROLLBACK_CACHE="$TMP/rollback-cache"
mkdir -p "$ROLLBACK_CACHE"
cp -aL "$BASE/var/cache/apk/." "$ROLLBACK_CACHE/"
RESTORE_PROOF="$TMP/restore-proof"
mkdir -p "$RESTORE_PROOF"
cp -aL "$BASE/." "$RESTORE_PROOF/"
root_apk "$RESTORE_PROOF" --no-network del csqtt-native-old > "$TMP/restore-proof.txt" 2>&1
cp -aL "$ROLLBACK_CACHE/." "$RESTORE_PROOF/var/cache/apk/"
if ! root_apk "$RESTORE_PROOF" --no-network add csqtt-native-old=1.0-r1 >> "$TMP/restore-proof.txt" 2>&1; then
    cat "$TMP/restore-proof.txt" >&2
    die 'The unsigned original DNS package could not be restored offline before replacement.'
fi
root_query "$RESTORE_PROOF" > "$TMP/restore-proof-installed.json"
cmp "$TMP/baseline.json" "$TMP/restore-proof-installed.json"
# Restore the original unpinned world only after the exact-version add succeeds.
cp "$TMP/original-world" "$RESTORE_PROOF/etc/apk/world"
cmp "$TMP/original-world" "$RESTORE_PROOF/etc/apk/world"
cmp "$TMP/payloads/old/usr/share/csqtt-native-test/dns.txt" "$RESTORE_PROOF/usr/share/csqtt-native-test/dns.txt"
echo 'native APK: unsigned original DNS restored offline by exact version before replacement; installed state, payload and original world verified.'
# Verify both the unsigned package metadata identity and its payload hashes.
# Only disposable guard roots change; the installed BASE state stays intact.
for KIND in metadata payload; do
    GUARDED="$TMP/guard-$KIND"
    mkdir -p "$GUARDED"
    cp -aL "$BASE/." "$GUARDED/"
    root_apk "$GUARDED" --no-network del csqtt-native-old > "$TMP/guard-$KIND.txt" 2>&1
    cp -aL "$ROLLBACK_CACHE/." "$GUARDED/var/cache/apk/"
    python3 - "$GUARDED/var/cache/apk/$ORIGINAL_CACHE_NAME" "$KIND" <<'NATIVE_APK_UNSIGNED_TAMPER'
import pathlib, sys
path, kind = pathlib.Path(sys.argv[1]), sys.argv[2]
data = path.read_bytes()
original = b'isolated native APK fixture' if kind == 'metadata' else b'original DNS fixture\n'
changed = b'Isolated native APK fixture' if kind == 'metadata' else b'Original DNS fixture\n'
assert data.startswith(b'ADB.') and data.count(original) == 1, 'Unexpected unsigned DNS fixture format'
path.write_bytes(data.replace(original, changed, 1))
NATIVE_APK_UNSIGNED_TAMPER
    if root_apk "$GUARDED" --no-network add csqtt-native-old=1.0-r1 >> "$TMP/guard-$KIND.txt" 2>&1; then
        cat "$TMP/guard-$KIND.txt" >&2
        die 'A changed unsigned DNS package was accepted against the signed index.'
    fi
done
root_query "$BASE" > "$TMP/baseline-after-guards.json"
cmp "$TMP/baseline.json" "$TMP/baseline-after-guards.json"
cmp "$TMP/original-world" "$BASE/etc/apk/world"
echo 'native APK: unsigned DNS metadata and payload corruption rejected before replacement; original installed state and world preserved.'
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
root_apk "$OFFLINE" --cache-dir "$ROLLBACK_CACHE" --no-network add csqtt-native-old=1.0-r1 >> "$TMP/offline.txt" 2>&1
root_query "$OFFLINE" > "$TMP/rollback-installed.json"
cmp "$TMP/baseline.json" "$TMP/rollback-installed.json"
cp "$TMP/original-world" "$OFFLINE/etc/apk/world"
cmp "$TMP/original-world" "$OFFLINE/etc/apk/world"
cmp "$TMP/payloads/old/usr/share/csqtt-native-test/dns.txt" "$OFFLINE/usr/share/csqtt-native-test/dns.txt"
[ -z "$(find "$TMP" -name native-script-ran -print)" ] || die 'A package script executed despite no-scripts.'
rm -f "$TMP/signing.pem" "$TMP/wrong-signing.pem"
echo 'native APK: three SDK package signatures verified; unsigned DNS authenticated through a signed index; isolated DNS conflict/replacement, staged dependency cache, offline install and exact original DNS/world rollback passed.'
