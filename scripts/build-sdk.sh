#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SDK_VERSION=25.12.5
SDK_NAME=openwrt-sdk-25.12.5-mediatek-filogic_gcc-14.3.0_musl.Linux-x86_64
SDK_SHA=ff4a38a397caa2cfe1c39e18f84ddede14878221b3593c3f2c4cfe24e3ec4c25
SDK_URL="https://downloads.openwrt.org/releases/$SDK_VERSION/targets/mediatek/filogic/$SDK_NAME.tar.zst"
WORK=${CSQTT_BUILD_DIR:-"$ROOT/.work/sdk"}
mkdir -p "$WORK" "$ROOT/dist"
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
# SDK make derives its target/host staging paths itself. The compiler's staging
# directory must not override those make variables.
unset STAGING_DIR
cd "$SDK"
./scripts/feeds update -a
./scripts/feeds install -a
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
make defconfig
make package/csqtt-local/csqtt/compile package/csqtt-local/csqtt-captcha/compile package/csqtt-local/luci-app-csqtt/compile -j2 V=s \
    CSQTT_BINARY="$CORE" CSQTT_CAPTCHA_BINARY="$ROOT/dist/csqtt-captcha"
find bin -type f \( -name 'csqtt-*.apk' -o -name 'luci-app-csqtt-*.apk' \) -exec cp '{}' "$ROOT/dist/" ';'
sudo sh "$ROOT/scripts/test-native-apk.sh" "$SDK/staging_dir/host/bin/apk" "$ROOT/dist"
if [[ -n "${CSQTT_SIGNING_KEY:-}" ]]; then
    umask 077
    KEYFILE=$(mktemp)
    trap 'rm -f "$KEYFILE"' EXIT
    printf '%s\n' "$CSQTT_SIGNING_KEY" > "$KEYFILE"
    openssl pkey -in "$KEYFILE" -pubout -out "$WORK/signing-public.pem"
    cmp "$WORK/signing-public.pem" "$ROOT/release/csqtt-public.pem"
    "$SDK/staging_dir/host/bin/apk" adbsign --sign-key "$KEYFILE" "$ROOT"/dist/*.apk
fi
python3 "$ROOT/scripts/release-manifest.py" "$ROOT/dist"
if [[ -n "${CSQTT_SIGNING_KEY:-}" ]]; then
    openssl dgst -sha256 -sign "$KEYFILE" -out "$ROOT/dist/manifest.sig" "$ROOT/dist/manifest.json"
    openssl dgst -sha256 -verify "$ROOT/release/csqtt-public.pem" -signature "$ROOT/dist/manifest.sig" "$ROOT/dist/manifest.json"
fi
