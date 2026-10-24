#!/usr/bin/env bash
set -euo pipefail
# Dependency builders do not need the release key in their environment.
RELEASE_SIGNING_KEY=${CSQTT_SIGNING_KEY:-}
unset CSQTT_SIGNING_KEY
export APK_CONFIG=/dev/null
PACKAGE_RELEASE=${CSQTT_PACKAGE_RELEASE:-1}
[[ "$PACKAGE_RELEASE" =~ ^[1-9][0-9]{0,6}$ ]] || { echo 'Invalid package release number' >&2; exit 1; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
# Select an exact checked-in tuple before downloading or creating outputs. An
# omitted profile preserves the existing preview SDK, layout and manifest.
PROFILE_ARGS=()
if [[ -n "${CSQTT_PROFILE:-}" ]]; then PROFILE_ARGS=(--profile "$CSQTT_PROFILE"); fi
PROFILE_ENV=$(python3 "$ROOT/scripts/platforms.py" "${PROFILE_ARGS[@]}" --format shell)
eval "$PROFILE_ENV"
WORK=${CSQTT_BUILD_DIR:-"$ROOT/.work/sdk"}
OUT="$ROOT/dist"
if [[ -n "${CSQTT_PROFILE:-}" ]]; then OUT="$OUT/$PROFILE_ID"; fi
mkdir -p "$WORK" "$OUT"
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
rm -f "$OUT"/csqtt-*.apk "$OUT"/luci-app-csqtt-*.apk "$OUT"/csqtt_*.ipk \
    "$OUT"/csqtt-captcha_*.ipk "$OUT"/luci-app-csqtt_*.ipk \
    "$OUT"/"$PROFILE_ID"--*.apk "$OUT"/"$PROFILE_ID"--*.ipk \
    "$OUT/manifest.json" "$OUT/manifest.sig" "$OUT/SHA256SUMS" \
    "$OUT/$PROFILE_ID-manifest.json" "$OUT/$PROFILE_ID-manifest.sig" \
    "$OUT/$PROFILE_ID-abi-evidence.json" "$OUT/$PROFILE_ID-vm-evidence.json" "$OUT/dependencies.json"
if [[ ! -d "$WORK/$SDK_NAME" ]]; then
    curl --fail --location --retry 3 "$SDK_URL" -o "$WORK/sdk.tar.zst"
    printf '%s  %s\n' "$SDK_SHA" "$WORK/sdk.tar.zst" | sha256sum -c -
    tar --zstd -xf "$WORK/sdk.tar.zst" -C "$WORK"
fi
SDK="$WORK/$SDK_NAME"
# Expand SDK target defaults before comparing the architecture fields. SDK
# config.buildinfo is only a diff and can omit these derived string values.
run_logged sdk-default-config make -C "$SDK" defconfig
# Build with the release SDK's actual musl linker and headers.
TOOLCHAIN=$(python3 "$ROOT/scripts/platforms.py" --profile "$PROFILE_ID" --verify-sdk "$SDK")
export STAGING_DIR="$TOOLCHAIN"
export PATH="$TOOLCHAIN/bin:$PATH"
RUST_ENV=${RUST_TARGET//-/_}
export "CARGO_TARGET_${RUST_ENV^^}_LINKER=$SDK_TOOLCHAIN_PREFIX-gcc"
export "CC_$RUST_ENV=$SDK_TOOLCHAIN_PREFIX-gcc" "CXX_$RUST_ENV=$SDK_TOOLCHAIN_PREFIX-g++" "AR_$RUST_ENV=$SDK_TOOLCHAIN_PREFIX-ar"
export "CARGO_TARGET_${RUST_ENV^^}_RUSTFLAGS=-C target-feature=+crt-static"
if [[ "$GOARCH" = arm ]]; then
    export "CARGO_TARGET_${RUST_ENV^^}_RUSTFLAGS=-C target-feature=+crt-static -C target-cpu=cortex-a15"
    export "CFLAGS_$RUST_ENV=-mcpu=cortex-a15 -mfpu=neon-vfpv4 -mfloat-abi=softfp"
fi
# Separate native objects by SDK tuple, including the two ARM64 musl versions.
# Reusing Cargo outputs across different C linkers/headers can silently mix ABIs.
if [[ -n "${CSQTT_PROFILE:-}" ]]; then export CARGO_TARGET_DIR="$ROOT/.work/cargo/$PROFILE_ID"; fi
rustup target add "$RUST_TARGET" --toolchain "$RUST_VERSION"
cargo +"$RUST_VERSION" check --tests --manifest-path "$ROOT/vendor/csqtt/rust-client/Cargo.toml" --release --locked --target "$RUST_TARGET"
cargo +"$RUST_VERSION" build --manifest-path "$ROOT/vendor/csqtt/rust-client/Cargo.toml" --release --locked --target "$RUST_TARGET"
(cd "$ROOT/captcha-broker" && CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH" GOAMD64=v1 GOARM="$GOARM" go build -trimpath -ldflags='-s -w' -o "$OUT/csqtt-captcha" .)
CORE="${CARGO_TARGET_DIR:-$ROOT/vendor/csqtt/rust-client/target}/$RUST_TARGET/release/client"
python3 "$ROOT/scripts/test-platform.py" --profile "$PROFILE_ID" --require-tls "$CORE" "$OUT/csqtt-captcha"
# SDK make derives its target/host staging paths itself. The compiler's staging
# directory must not override those make variables.
unset STAGING_DIR
cd "$SDK"
run_logged feeds-update ./scripts/feeds update -a
run_logged feeds-install ./scripts/feeds install -a
mkdir -p package/csqtt-local
rsync -a --delete "$ROOT/openwrt/" package/csqtt-local/
# The SDK defaults to deleting build trees after compile. Retain the actual
# patched GPL source and DNS binary; a literal "n" is truthy to package.mk.
sed -i '/^CONFIG_AUTOREMOVE=/d; /^# CONFIG_AUTOREMOVE is not set$/d' .config
cat >> .config <<'EOF'
# CONFIG_AUTOREMOVE is not set
CONFIG_PACKAGE_csqtt=m
CONFIG_PACKAGE_csqtt-captcha=m
CONFIG_PACKAGE_luci-app-csqtt=m
CONFIG_PACKAGE_dnsmasq-full=m
CONFIG_PACKAGE_dnsmasq_full_nftset=y
# CONFIG_PACKAGE_dnsmasq_full_conntrack is not set
# CONFIG_PACKAGE_dnsmasq_full_dnssec is not set
# CONFIG_PACKAGE_dnsmasq_full_idn is not set
# CONFIG_PACKAGE_dnsmasq_full_idn2 is not set
# CONFIG_PACKAGE_dnsmasq_full_ipset is not set
# CONFIG_PACKAGE_dnsmasq is not set
CONFIG_ALL_NONSHARED=n
CONFIG_ALL_KMODS=n
CONFIG_ALL=n
EOF
run_logged defconfig make defconfig
PRIVATE_DNS_ARGS=()
if [[ -n "${CSQTT_PROFILE:-}" ]]; then
    # A separate resolver binary avoids replacing the owner's dnsmasq package.
    # Dependencies stay ordinary matching-firmware packages; the binary itself
    # lives only below /usr/libexec/csqtt.
    DNS_COMPILE_TARGET=$(python3 "$ROOT/scripts/sdk_recipe.py" --sdk "$SDK" --field target)
    run_logged private-dns make "$DNS_COMPILE_TARGET" -j2 V=s CONFIG_AUTOREMOVE=
    mapfile -t DNS_BINARIES < <(find build_dir -type f -path '*/dnsmasq-full/dnsmasq-*/src/dnsmasq')
    [[ "${#DNS_BINARIES[@]}" = 1 ]] || { echo 'Expected exactly one SDK full dnsmasq binary' >&2; exit 1; }
    DNS_SOURCE=$(dirname "$(dirname "$SDK/${DNS_BINARIES[0]}")")
    python3 "$ROOT/scripts/package-dnsmasq-source.py" --profile "$PROFILE_ID" --source "$DNS_SOURCE" --sdk "$SDK" --output "$OUT"
    PRIVATE_DNS_ARGS=("CSQTT_DNSMASQ_BINARY=$SDK/${DNS_BINARIES[0]}" "CSQTT_DNSMASQ_LICENSE=$DNS_SOURCE/COPYING" "CSQTT_DNSMASQ_NOTICE=$OUT/dnsmasq-NOTICE")
fi
# Cached dependencies may stay compiled; our three packages must always use
# this checkout's source and newly built binaries.
run_logged package-clean make package/csqtt-local/csqtt/clean package/csqtt-local/csqtt-captcha/clean package/csqtt-local/luci-app-csqtt/clean CSQTT_PACKAGE_RELEASE="$PACKAGE_RELEASE"
# A fresh SDK has no package output directory until its first compile.
if [[ -d bin ]]; then
    find bin -type f \( -name 'csqtt-[0-9]*.apk' -o -name 'csqtt-captcha-[0-9]*.apk' -o -name 'luci-app-csqtt-[0-9]*.apk' -o -name 'csqtt_*.ipk' -o -name 'csqtt-captcha_*.ipk' -o -name 'luci-app-csqtt_*.ipk' \) -delete
fi
# LuCI depends on both other local packages. One leaf target compiles all three
# once; separate top-level targets repeat SDK dependency/kernel compilation.
run_logged packages make package/csqtt-local/luci-app-csqtt/compile -j2 V=s \
    CONFIG_AUTOREMOVE= \
    CSQTT_BINARY="$CORE" CSQTT_CAPTCHA_BINARY="$OUT/csqtt-captcha" CSQTT_PACKAGE_RELEASE="$PACKAGE_RELEASE" \
    CSQTT_FIREWALL_BACKEND="$FIREWALL_BACKEND" CSQTT_PLATFORM_PROBE="$ROOT/scripts/platform-probe.sh" "${PRIVATE_DNS_ARGS[@]}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then printf 'sdk_ready=true\n' >> "$GITHUB_OUTPUT"; fi
find bin -type f \( -name 'csqtt-[0-9]*.apk' -o -name 'csqtt-captcha-[0-9]*.apk' -o -name 'luci-app-csqtt-[0-9]*.apk' -o -name 'csqtt_*.ipk' -o -name 'csqtt-captcha_*.ipk' -o -name 'luci-app-csqtt_*.ipk' \) -exec cp '{}' "$OUT/" ';'
if [[ "$PACKAGE_FORMAT" = apk ]]; then
    sudo env CSQTT_PLATFORM_PROFILE="$PROFILE_ID" CSQTT_PACKAGE_ARCH="$PACKAGE_ARCH" CSQTT_EMULATOR="$EMULATOR" CSQTT_PRIVATE_DNS="${CSQTT_PROFILE:+1}" CSQTT_SDK="$SDK" \
        sh "$ROOT/scripts/test-native-apk.sh" "$SDK/staging_dir/host/bin/apk" "$OUT"
else
    sudo python3 "$ROOT/scripts/test-native-ipk.py" --profile "$PROFILE_ID" --sdk "$SDK" "$OUT"
fi
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
    mkdir -p "$SIGNATURE_ROOT/etc/apk/keys"
    cp "$ROOT/release/csqtt-public.pem" "$SIGNATURE_ROOT/etc/apk/keys/release.pem"
    # APK 3.0.5 retains signatures_written across adbsign file arguments and
    # returns success despite per-file errors. Use a fresh process for each.
    for PACKAGE in "$OUT"/*.apk; do
        [[ -f "$PACKAGE" ]] || continue
        "$SDK/staging_dir/host/bin/apk" --allow-untrusted --sign-key "$KEYFILE" adbsign --reset-signatures "$PACKAGE" > "$WORK/package-signing.log" 2>&1
        [[ ! -s "$WORK/package-signing.log" ]] || { echo 'APK signing emitted diagnostics; inspect package-signing.log' >&2; exit 1; }
        "$SDK/staging_dir/host/bin/apk" --root "$SIGNATURE_ROOT" --keys-dir etc/apk/keys verify "$PACKAGE"
    done
fi
if [[ -n "${CSQTT_PROFILE:-}" ]]; then
    USIGN="$SDK/staging_dir/host/bin/usign"
    if [[ ! -x "$USIGN" && "$PACKAGE_FORMAT" = ipk ]]; then
        run_logged host-usign make tools/usign/compile -j2 V=s
    fi
    python3 "$ROOT/scripts/bundle-dependencies.py" --profile "$PROFILE_ID" --directory "$OUT" \
        --apk "$SDK/staging_dir/host/bin/apk" --usign "$USIGN"
    python3 "$ROOT/scripts/release-manifest.py" "$OUT" --profile "$PROFILE_ID" --registry "$ROOT/platforms/registry.json" --dependencies "$OUT/dependencies.json" --third-party "$OUT/dnsmasq-source.json"
else
    python3 "$ROOT/scripts/release-manifest.py" "$OUT"
fi
if [[ -n "${CSQTT_PROFILE:-}" ]]; then
    python3 "$ROOT/scripts/release-evidence.py" abi --directory "$OUT" --profile "$PROFILE_ID"
fi
if [[ -n "${KEYFILE:-}" ]]; then
    openssl dgst -sha256 -sign "$KEYFILE" -out "$OUT/manifest.sig" "$OUT/manifest.json"
    openssl dgst -sha256 -verify "$ROOT/release/csqtt-public.pem" -signature "$OUT/manifest.sig" "$OUT/manifest.json"
    if [[ -n "${CSQTT_PROFILE:-}" ]]; then cp "$OUT/manifest.sig" "$OUT/$PROFILE_ID-manifest.sig"; fi
fi
if [[ "$PROFILE_ID" = official-25.12.5-mediatek-filogic-aarch64_cortex-a53 && -n "${CSQTT_PROFILE:-}" ]]; then
    sudo python3 "$ROOT/scripts/test-r9-migration.py" --apk "$SDK/staging_dir/host/bin/apk" --directory "$OUT" \
        --source-commit "$(git -C "$ROOT" rev-parse HEAD)"
fi
