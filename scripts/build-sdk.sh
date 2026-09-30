#!/usr/bin/env bash
set -euo pipefail
# Dependency builders do not need the release key in their environment.
RELEASE_SIGNING_KEY=${CSQTT_SIGNING_KEY:-}
unset CSQTT_SIGNING_KEY
export APK_CONFIG=/dev/null
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SDK_VERSION=25.12.5
SDK_NAME=openwrt-sdk-25.12.5-mediatek-filogic_gcc-14.3.0_musl.Linux-x86_64
SDK_SHA=ff4a38a397caa2cfe1c39e18f84ddede14878221b3593c3f2c4cfe24e3ec4c25
SDK_URL="https://downloads.openwrt.org/releases/$SDK_VERSION/targets/mediatek/filogic/$SDK_NAME.tar.zst"
WORK=${CSQTT_BUILD_DIR:-"$ROOT/.work/sdk"}
mkdir -p "$WORK" "$ROOT/dist"
# Keep verbose SDK output on disk; expose a useful failure tail in Actions.
run_logged() {
    local label=$1
    shift
    printf 'SDK phase: %s\n' "$label"
    if "$@" > "$WORK/$label.log" 2>&1; then
        tail -n 8 "$WORK/$label.log"
    else
        tail -n 100 "$WORK/$label.log" >&2
        return 1
    fi
}
# Remove only previous outputs of this build; a later failed build cannot leave
# an old manifest/signature looking like its new result.
rm -f "$ROOT"/dist/csqtt-*.apk "$ROOT"/dist/luci-app-csqtt-*.apk \
    "$ROOT/dist/manifest.json" "$ROOT/dist/manifest.sig" "$ROOT/dist/SHA256SUMS"
if [[ ! -d "$WORK/$SDK_NAME" ]]; then
    curl --fail --location --retry 3 "$SDK_URL" -o "$WORK/sdk.tar.zst"
    printf '%s  %s\n' "$SDK_SHA" "$WORK/sdk.tar.zst" | sha256sum -c -
    tar --zstd -xf "$WORK/sdk.tar.zst" -C "$WORK"
fi
SDK="$WORK/$SDK_NAME"
# Build with the release SDK's actual musl linker and headers.
TOOLCHAIN=$(find "$SDK/staging_dir" -maxdepth 1 -type d -name 'toolchain-aarch64*' -print -quit)
export STAGING_DIR="$TOOLCHAIN"
export PATH="$TOOLCHAIN/bin:$PATH"
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=aarch64-openwrt-linux-musl-gcc
export CC_aarch64_unknown_linux_musl=aarch64-openwrt-linux-musl-gcc
export CXX_aarch64_unknown_linux_musl=aarch64-openwrt-linux-musl-g++
export AR_aarch64_unknown_linux_musl=aarch64-openwrt-linux-musl-ar
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUSTFLAGS='-C target-feature=+crt-static'
rustup target add aarch64-unknown-linux-musl --toolchain 1.97.1
cargo +1.97.1 check --tests --manifest-path "$ROOT/vendor/csqtt/rust-client/Cargo.toml" --release --locked --target aarch64-unknown-linux-musl
cargo +1.97.1 build --manifest-path "$ROOT/vendor/csqtt/rust-client/Cargo.toml" --release --locked --target aarch64-unknown-linux-musl
(cd "$ROOT/captcha-broker" && CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags='-s -w' -o "$ROOT/dist/csqtt-captcha" .)
CORE="$ROOT/vendor/csqtt/rust-client/target/aarch64-unknown-linux-musl/release/client"
python3 "$ROOT/scripts/test-arm64.py" "$CORE" "$ROOT/dist/csqtt-captcha"
# SDK make derives its target/host staging paths itself. The compiler's staging
# directory must not override those make variables.
unset STAGING_DIR
cd "$SDK"
run_logged feeds-update ./scripts/feeds update -a
run_logged feeds-install ./scripts/feeds install -a
mkdir -p package/csqtt-local
rsync -a --delete "$ROOT/openwrt/" package/csqtt-local/
cat >> .config <<'EOF'
CONFIG_PACKAGE_csqtt=m
CONFIG_PACKAGE_csqtt-captcha=m
CONFIG_PACKAGE_luci-app-csqtt=m
CONFIG_PACKAGE_dnsmasq-full=m
# CONFIG_PACKAGE_dnsmasq is not set
CONFIG_ALL_NONSHARED=n
CONFIG_ALL_KMODS=n
CONFIG_ALL=n
EOF
run_logged defconfig make defconfig
# Cached dependencies may stay compiled; our three packages must always use
# this checkout's source and newly built binaries.
run_logged package-clean make package/csqtt-local/csqtt/clean package/csqtt-local/csqtt-captcha/clean package/csqtt-local/luci-app-csqtt/clean
run_logged packages make package/csqtt-local/csqtt/compile package/csqtt-local/csqtt-captcha/compile package/csqtt-local/luci-app-csqtt/compile -j2 V=s \
    CSQTT_BINARY="$CORE" CSQTT_CAPTCHA_BINARY="$ROOT/dist/csqtt-captcha"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then printf 'sdk_ready=true\n' >> "$GITHUB_OUTPUT"; fi
find bin -type f \( -name 'csqtt-*.apk' -o -name 'luci-app-csqtt-*.apk' \) -exec cp '{}' "$ROOT/dist/" ';'
sudo sh "$ROOT/scripts/test-native-apk.sh" "$SDK/staging_dir/host/bin/apk" "$ROOT/dist"
if [[ -n "$RELEASE_SIGNING_KEY" ]]; then
    umask 077
    KEYFILE=$(mktemp)
    SIGNATURE_ROOT=$(mktemp -d)
    trap 'rm -f "$KEYFILE"; rm -rf "$SIGNATURE_ROOT"' EXIT
    printf '%s\n' "$RELEASE_SIGNING_KEY" > "$KEYFILE"
    unset RELEASE_SIGNING_KEY
    openssl pkey -in "$KEYFILE" -pubout -out "$WORK/signing-public.pem"
    cmp "$WORK/signing-public.pem" "$ROOT/release/csqtt-public.pem"
    # adbsign parses its input's existing signatures before replacing them.
    # Only the generated build inputs may be unsigned; verify the new result
    # separately with the pinned project key and without allow-untrusted.
    "$SDK/staging_dir/host/bin/apk" --allow-untrusted --sign-key "$KEYFILE" adbsign --reset-signatures "$ROOT"/dist/*.apk > "$WORK/package-signing.log" 2>&1
    mkdir -p "$SIGNATURE_ROOT/etc/apk/keys"
    cp "$ROOT/release/csqtt-public.pem" "$SIGNATURE_ROOT/etc/apk/keys/release.pem"
    "$SDK/staging_dir/host/bin/apk" --root "$SIGNATURE_ROOT" --keys-dir etc/apk/keys verify "$ROOT"/dist/*.apk
fi
python3 "$ROOT/scripts/release-manifest.py" "$ROOT/dist"
if [[ -n "${KEYFILE:-}" ]]; then
    openssl dgst -sha256 -sign "$KEYFILE" -out "$ROOT/dist/manifest.sig" "$ROOT/dist/manifest.json"
    openssl dgst -sha256 -verify "$ROOT/release/csqtt-public.pem" -signature "$ROOT/dist/manifest.sig" "$ROOT/dist/manifest.json"
fi
