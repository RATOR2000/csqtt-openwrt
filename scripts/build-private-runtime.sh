#!/usr/bin/env bash
# Experimental private userspace bundle. Never installs or replaces system libs.
set -euo pipefail
unset CSQTT_SIGNING_KEY
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK="$ROOT/.work/private-runtime"
OUT="$ROOT/dist/glinet-4.11-arm64-private-runtime-experiment"
mkdir -p "$WORK" "$OUT"
eval "$(python3 - "$ROOT/platforms/private-runtime-experiment.json" <<'PY'
import json, shlex, sys
data = json.load(open(sys.argv[1]))
for kind in ('sdk', 'ucode', 'musl_license'):
    for key in ('name', 'url', 'sha256', 'revision'):
        if key in data[kind]:
            print(f'{kind.upper()}_{key.upper()}={shlex.quote(data[kind][key])}')
PY
)"
fetch() {
    local url=$1 hash=$2 archive=$3
    if [[ ! -f "$archive" ]]; then curl --fail --location --retry 3 "$url" -o "$archive"; fi
    printf '%s  %s\n' "$hash" "$archive" | sha256sum -c -
}
fetch "$SDK_URL" "$SDK_SHA256" "$WORK/sdk.tar.xz"
fetch "$UCODE_URL" "$UCODE_SHA256" "$WORK/ucode.tar.gz"
fetch "$MUSL_LICENSE_URL" "$MUSL_LICENSE_SHA256" "$WORK/musl-COPYRIGHT"
if [[ ! -d "$WORK/$SDK_NAME" ]]; then tar -xJf "$WORK/sdk.tar.xz" -C "$WORK"; fi
if [[ ! -d "$WORK/ucode-$UCODE_REVISION" ]]; then tar -xzf "$WORK/ucode.tar.gz" -C "$WORK"; fi
SDK="$WORK/$SDK_NAME"
SOURCE="$WORK/ucode-$UCODE_REVISION"
python3 - "$ROOT/platforms/private-runtime-experiment.json" "$SDK" <<'PY'
import json, pathlib, re, sys
config, sdk = json.load(open(sys.argv[1])), pathlib.Path(sys.argv[2])
for name, expected in config['sdk_sources'].items():
    text = (sdk / name).read_text()
    for key, value in expected.items():
        assert re.search(r'^' + re.escape(key) + r':=' + re.escape(value) + r'$', text, re.M), 'SDK source pin differs: ' + name
PY
# No moving package feeds are used. These four base package sources and hashes
# are bound by the checked SDK archive and the explicit source-pin check above.
cat >> "$SDK/.config" <<'EOF'
CONFIG_PACKAGE_libjson-c=y
CONFIG_PACKAGE_libubox=y
CONFIG_PACKAGE_libubus=y
CONFIG_PACKAGE_libuci=y
CONFIG_PACKAGE_lua=n
EOF
make -C "$SDK" defconfig > "$WORK/sdk-config.log" 2>&1
make -C "$SDK" package/libs/libjson-c/compile package/libs/libubox/compile package/system/ubus/compile package/system/uci/compile -j2 V=s > "$WORK/sdk-libraries.log" 2>&1 || { tail -n 80 "$WORK/sdk-libraries.log" >&2; exit 1; }
mapfile -t TARGETS < <(find "$SDK/staging_dir" -maxdepth 1 -type d -name 'target-aarch64_cortex-a53_musl*')
mapfile -t TOOLCHAINS < <(find "$SDK/staging_dir" -maxdepth 1 -type d -name 'toolchain-aarch64_cortex-a53_gcc-8.4.0_musl*')
[[ "${#TARGETS[@]}" = 1 && "${#TOOLCHAINS[@]}" = 1 ]] || { echo 'Unexpected experimental SDK ABI directories' >&2; exit 1; }
TARGET=${TARGETS[0]}
TOOLCHAIN=${TOOLCHAINS[0]}
export STAGING_DIR="$TOOLCHAIN"
export PATH="$TOOLCHAIN/bin:$PATH"
export PKG_CONFIG_LIBDIR="$TARGET/usr/lib/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$TARGET"
cmake -S "$SOURCE" -B "$WORK/ucode-build" \
    -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
    -DCMAKE_C_COMPILER="$TOOLCHAIN/bin/aarch64-openwrt-linux-musl-gcc" \
    -DCMAKE_FIND_ROOT_PATH="$TARGET;$TOOLCHAIN" \
    -DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY \
    -DCMAKE_C_FLAGS="-Os -I$TARGET/usr/include" \
    -DCMAKE_EXE_LINKER_FLAGS="-L$TARGET/usr/lib" -DCMAKE_SHARED_LINKER_FLAGS="-L$TARGET/usr/lib" \
    -DCMAKE_BUILD_TYPE=MinSizeRel -DCMAKE_SKIP_RPATH=TRUE \
    -DLIB_SEARCH_PATH='/usr/libexec/csqtt/ucode-runtime/modules/*.so' \
    -DFS_SUPPORT=ON -DUCI_SUPPORT=ON -DUBUS_SUPPORT=ON \
    -DULOOP_SUPPORT=OFF -DNL80211_SUPPORT=OFF -DRTNL_SUPPORT=OFF -DRESOLV_SUPPORT=OFF \
    -DZLIB_SUPPORT=OFF -DDIGEST_SUPPORT=OFF -DLOG_SUPPORT=OFF > "$WORK/ucode-config.log" 2>&1 || { tail -n 80 "$WORK/ucode-config.log" >&2; exit 1; }
cmake --build "$WORK/ucode-build" -j2 > "$WORK/ucode-build.log" 2>&1 || { tail -n 80 "$WORK/ucode-build.log" >&2; exit 1; }
python3 "$ROOT/scripts/private-runtime.py" assemble "$WORK/ucode-build" "$TARGET" "$TOOLCHAIN" "$OUT" --musl-license "$WORK/musl-COPYRIGHT"
mapfile -t UBUS_DAEMONS < <(find "$SDK/build_dir" -type f -path '*/ubus-*/ubusd')
[[ "${#UBUS_DAEMONS[@]}" = 1 ]] || { echo 'Expected exactly one isolated legacy ubusd fixture' >&2; exit 1; }
python3 "$ROOT/scripts/private-runtime.py" smoke "$OUT" --ubusd "${UBUS_DAEMONS[0]}"
