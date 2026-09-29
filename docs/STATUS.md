# Development status — resume here

Updated2026-09-30. **Source/build validation in progress; no verified installable
release and no real router/VK acceptance.** Read this, then IMPLEMENTATION.md.
Actual files/Git/CI are authority.

## First unfinished action

Publish this checkpoint (SDK staging fix, real group DNS checks, CAPTCHA
serialization), inspect its new PR CI run and fix SDK/native DNS/APK failures.
The previous SDK runs failed after successful ARM64 client compilation because
STAGING_DIR leaked into SDK make; source now scopes it to the compiler.
Do not repeat passed Rust/Android work or completed installer doubles.

## Saved repository/tooling

- Public https://github.com/RATOR2000/csqtt-openwrt
- Attached draft PR https://github.com/RATOR2000/csqtt-openwrt/pull/1
- Development branch codex/csqtt-openwrt. Last confirmed remote54141e46bf48de563220cbda3977678c06b24a39; inspect HEAD for later commits.
- Local push lacks auth; GitHub connector tree/commit/ref APIs work.
  scripts/export-github-tree.py exports committed delta to .work/publish-delta.
  Publish with manifest base_tree/parent, fetch, compare tree hashes and align.
- Go1.26.8 already in .work/tools/go/bin; Node/Python available. No local Rust,
  WSL or Docker. Pristine .work/upstream exists. Do not reinstall/reclone.
- Private signing key .work/signing/release.pem is ignored; never print/commit.
  Public release/csqtt-public.pem is embedded in installer. Actions secret
  CSQTT_SIGNING_KEY not configured. See BUILD.md.

## Settled scope

- Original amurcanov/csqtt v2.1.9 at446293aa2e873ac5323ef6fd2316d9b81d966c11;
  retain Android-deployed server/web administration. No incompatible fork.
- GL-MT6000, official OpenWrt25.12.5 r33051-f5dae5ece4, kernel6.12.94,
  mediatek/filogic/aarch64_cortex-a53, about1GiB RAM/6.3GiB overlay free.
- Russian LuCI, one active tunnel, named groups, one group per MAC, ordered
  domain/IP/CIDR rules. Unassigned devices use WAN.
- VPN-classified traffic stays blocked on tunnel failure; explicit WAN rules
  continue; router/LAN access stays. DNS limitations accepted. Internet IPv6
  blocked for groups that can select VPN; local IPv6 stays.
- Native automatic CAPTCHA plus separate Android helper via pinned TLS,
  one-use pairing and authenticated VK-only relay for blocked VPN phones.
- Eventual one-command signed install. No stable release before real acceptance.
  No router connection scope or deployed server/VK hashes supplied.

## Current source and verification

- Rust daemon/TUN/private JSON control/config/status/identity and CAPTCHA
  integrated. Linux CI36638972094 at88d8189:341passed/0failed/7ignored plus
  focused TURN fixture. Core job at54141e4 also passed. Musl ABI fixes passed
  ARM64 test compilation and release binary build in SDK; no ARM64 execution.
  See CORE_STATUS. Initial TURN preparation timeout remains historical; later
  fixture race fixed and stage diagnostics retained.
- Real ucode, exact nft/DNS/model comparisons, dnsmasq syntax and namespace
  traffic passed at88d8189 and54141e4: simulated VPN up/down, WAN exceptions,
  routing loss, reserved-source guard, learned sets/reload, local access,
  IPv6/ULA and unassigned clients. See POLICY_STATUS.
- Latest DNS changes add real group resolver queries/set insertion and fix local
  names (domain-needed/rebind/delegation). Latest LuCI shows local domain via
  scoped status RPC and rejects internet rules for local names. New native DNS
  suite is not executed yet. Node policy/LuCI33passed locally.
- Android13 JVM tests, Kotlin/lintDebug/assembleDebug passed in CI; see
  ANDROID_STATUS. No actual phone/WebView/VK acceptance.
- Broker latest local go test/go vet passed: pairing/result/cancel serialized;
  stale results/cancels cannot affect replacement, quoted16KiB token fits64KiB
  JSON bound, control tokens and trailing JSON rejected. CI race check pending
  for these latest edits. Private grants/pin/URLs excluded from public status.
- Installer27 isolated command-double scenarios passed locally; Linux CI
  installer suite passed. Upgrade/core/CAPTCHA restart and exact original DNS
  rollback covered. Native APK3 signature/cache/no-scripts/offline/rollback
  script implemented and hooked after SDK build; not executed yet. See
  INSTALLER_STATUS.
- Release-manifest producer/verifier CLI tests4passed locally. Shell syntax and
  git diff --check passed for latest root scripts. Public key is the only PEM
  tracked. Signed draft workflow exists; signing secret/release still pending.
- SDK runs36638972094 and36639256975 passed ARM64 client compilation but failed
  SDK host prerequisite path. Fixed by unsetting compiler STAGING_DIR before
  feeds/make and setting compiler staging to toolchain. Cargo cache populated;
  latest package compilation/native APK test awaits new CI.

## Ownership and next sequence

Check collaboration.list_agents before reuse; previous sessions may end.
backend_validate owns backend/policy/native DNS tests, milestone completed.
android_validate completed Android. core_ci_fix completed musl/fixture fixes.
installer_validate completed installer/native APK source. Root owns broker,
SDK/CI/release, top-level docs and Git. No previous process may be assumed alive.

1. Publish latest checkpoint and resolve fresh native DNS/SDK/APK failures.
2. Confirm three APK packages and helper artifact; inspect package contents,
   executable permissions, dependencies, UCI/procd/fw4/control contracts.
3. Configure signing secret and validate signed preview only after builds pass.
   Android debug signature is not a permanent update/release identity.
4. Authorized real GL-MT6000/server tests: mixed WAN/VPN clients, crash/stop,
   DNS/IPv6, firewall/boot, existing flows, manual CAPTCHA from blocked phone.
   Record results before stable release. No live tests run yet.

Known limit: DNS caches/shared IPs/DoH affect classification. Unused nft
chains/sets can accumulate after frequent edits; not garbage-collected yet.
Do not repeat settled questions, GitHub login/create, cloning or tooling setup.
