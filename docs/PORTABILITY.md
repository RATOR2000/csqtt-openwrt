# Portable CSQTT delivery

Approved2026-10-20. Work is source development until the gates below pass.
The user's current OpenWrt25 router and preview9 observation remain untouched.
No Codex automation, firmware flashing or automatic firmware upgrades.

## Priority and compatibility

1. Global/US Stable GL.iNet Flint2, starting with4.11.0 and later explicitly
   qualified updates. This includes the vendor MTK firmware, not just op24/op25.
2. Official OpenWrt24.10/25.12: ARM64 and x86_64, then ARMv7 ABI variants.
3. MIPS LE/BE: separate port requiring32-bit atomic adaptation and a pinned
   Tier3 Rust/std toolchain. Do not advertise it as supported by a matrix label.

SDK compilation, user-mode emulation, native package-manager tests and actual
router acceptance are distinct evidence. A profile needs authenticated package,
dependency, rollback and packet-path proofs before installation/activation.
Unqualified or unknown firmware receives a reasoned refusal before mutation.

## Exact vendor factory evidence

Official download centre: https://dl.gl-inet.com/router/mt6000/stable

Image read via HTTPS, never executed or flashed:
https://fw.gl-inet.com/firmware/mt6000/release/mt6000-4.11.0_release3-1147-0924-1790238424.bin

SHA256 `4004632eaf516fd2844be0e5595b6e4171d243181ff49b81569b986c79007dae`,
83,146,618bytes. This is a recorded content digest, not a claim of a separate
vendor cryptographic signature. SquashFS starts at offset3,806,720.
Reproduce with `scripts/inspect-glinet-firmware.py IMAGE --sha256 DIGEST`;
optional Python dependency `dissect.squashfs==1.0` remains a developer tool.
The checked-in public result is `docs/evidence/glinet-flint2-4.11.0.json`.

The actual image reports OpenWrt21.02-SNAPSHOT r15812+1095-46b6ee7ffc,
mediatek/mt7986/aarch64_cortex-a53 and kernel
5.4.238-1-d4a7d36962bb6218ebd94bf040ac560e. It ships fw3, iptables1.8.7,
ipset7.6, dnsmasq-full2.92-7, kmod-tun, OpenSSL1.1.1t and signed-index opkg
configuration. No installed ucode, firewall4, nftables or LuCIbase;27 LuCI IPKs
are bundled separately. Exact matching SDK/private runtime remains a build gate.

Vendor DNS and firewall are integrated with the GL panel. Hardware acceleration
uses mtkhnat with `/sys/kernel/debug/hnat/hook_toggle` and interface hooks;
ordinary fw4 flow-offload settings alone cannot establish fail-closed routing.
Installing official OpenWrt25 firewall/modules/libraries on this image is forbidden.

## Required acceptance

- Authenticate exact platform bundles and dependencies; prove offline rollback
  before system changes. Preserve explicit settings, identity and recovery budget.
- Run existing Rust/Go/LuCI/policy tests, each target's ABI/TLS/TUN tests, native
  opkg/APK install/upgrade/interruption/rollback and invalid signature tests.
- Test local management, default/domain/IP rules, guarded DNS/local names, IPv6,
  interface naming, acceleration and vendor firewall reload/hotplug.
- Exercise Stop/Reload/Helper/recovery concurrency and boot protection. Neither
  a missing process nor a legacy platform may bypass guards or enable WAN fallback.
- Measure idle/auth/traffic/recovery peak RAM, CPU and throughput before qualifying
  automatic resource profiles. Preserve explicit workers; minimum9/cohort limits.
- After the owner independently migrates to GL firmware, qualify the exact installed
  version, Russian LuCI, real VPN/VK behavior and sustained stability. Until then
  GL build results are experimental; immutable preview9 assets remain unchanged.

The existing72h observation, failed-first-activation boot test and Android/VK
acceptance remain separate release gates. Do not claim stable acceptance from
an offline factory inspection or simulated tests.
