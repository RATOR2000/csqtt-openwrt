# Development status — resume here

Updated: 2026-09-30. **Implementation/build validation in progress; no verified
installable release and no real router/VK acceptance.**

## First unfinished action

Publish the current checkpoint on codex/csqtt-openwrt, read its fresh PR CI
results, and fix native policy, Android or SDK failures. Inspect actual Git
first: this file is included in the checkpoint being published. Finish installer
tests and save later corrections in another small checkpoint.

## Repository and continuity

- Public: https://github.com/RATOR2000/csqtt-openwrt
- Attached draft PR: https://github.com/RATOR2000/csqtt-openwrt/pull/1
- Last confirmed remote: 88d8189304b328ba92f888331806eb1a4320ad57.
  Actual Git HEAD/status are authority for subsequent changes.
- Local push lacks authentication; GitHub connector tree/commit/ref APIs work.
  scripts/export-github-tree.py exports committed delta to .work/publish-delta.
  Use manifest base_tree/parent, update dev ref, fetch, compare trees and align.
- Go1.26.8 in .work/tools/go/bin already verified; Node/Python available.
  Windows has no Rust, WSL or Docker. Pristine .work/upstream already exists.
- Private signing key: .work/signing/release.pem, ignored. Never print/commit it.
  Public release/csqtt-public.pem is embedded in installer. Actions signing
  secret CSQTT_SIGNING_KEY is not configured. See docs/BUILD.md.

## Settled requirements

- Original amurcanov/csqtt v2.1.9 at 446293aa2e873ac5323ef6fd2316d9b81d966c11.
  No incompatible fork. Original Android deploys server/web administration.
- GL-MT6000, OpenWrt25.12.5 r33051-f5dae5ece4, kernel6.12.94,
  mediatek/filogic, aarch64_cortex-a53, about1GiB RAM/6.3GiB free overlay.
- Russian LuCI, one tunnel, named groups, one group per MAC, ordered
  domain/IP/CIDR rules. Unassigned devices use WAN.
- VPN-classified traffic remains blocked on failure; explicit WAN exceptions
  continue; LAN/router access stays. DNS classification limitations accepted.
  IPv6 internet blocked for groups that can select VPN; local IPv6 stays.
- Automatic CAPTCHA and separate Android helper with authenticated VK-only
  relay for phones in blocked VPN groups.
- Eventual one-command signed installer. No stable release before real tests.
  No live router access details or deployed server/VK hashes yet.

## Saved source milestones

- Linux Rust daemon/TUN, private JSON control/config/status/identity, SIGTERM,
  automatic/manual CAPTCHA. Latest edits add token/frame bounds, epoch expiry
  and descriptor tests. CORE_STATUS has details.
- OpenWrt ucode/procd, per-group DNS, persistent nft/routing guards, maintenance
  protection and offload restore. Review fixed null status, capacity/CIDR and
  routed IPv6 bypass. POLICY_STATUS has details; obsolete unused sets/chains
  can accumulate across repeated configuration edits.
- Russian LuCI/scoped RPC/ACL, safe text rendering, expiring private pairing
  dialog. LUCI_STATUS has details.
- Go broker: one-use pairing, TLS pin, private Unix control, replay/expiry,
  restricted public IPv4 VK CONNECT relay.
- Android lifecycle/transport fixes plus13 added JVM tests: reservation,
  stale callbacks, expiry, proxy cleanup, tracked sockets, API28 reads,
  redirects, token/URI validation. ANDROID_STATUS has details.
- Installer: pinned APK/manifest verification, exact target check, staged APK
  database/cache, original dnsmasq rollback. Fake-router tests being added;
  actual OpenWrt APK runtime still unverified.
- New native ucode/dnsmasq/nft namespace tests and SDK build in CI. Signed
  draft preview workflow and BUILD/PREVIEW_NOTES added; workflows unverified.

## Checks actually completed

- PR run36634479898 at450df5: Rust337 passed/7ignored. Go/Node passed.
  Shell job failed on absent install.sh, now present. Android compiled/tested,
  lint failed on API33 readNBytes, now replaced. SDK skipped. Latest source
  changes still need a new Rust/Android run.
- Latest local Node policy/LuCI:31 passed/0failed.
- POSIX sh syntax passed: install.sh, build-sdk.sh, test-native-policy.sh.
- Python py_compile passed: export-github-tree.py, release-manifest.py,
  verify-release.py, network-smoke.py. git diff --check passed.
- Broker go test/go vet passed earlier; ARM64 Linux cross-build exists ignored.
- CI36637150431 at18baa7d: checks passed; Android Kotlin,13 JVM tests,
  lintDebug and assembleDebug passed. Native ucode failed on missing semicolons
  after exported functions; fixed for rerun. Rust compiled with339passed,
  1failed/7ignored: TURN prepare_channel timed out. Added receive-stage
  diagnostics and immediate server failure reporting; separately gated a
  confirmed data-phase single-buffer fixture race. No production TURN fix.
  SDK skipped; now scheduled after checks concurrently with native/Rust jobs.
- Broker latest go test/go vet passed after65536-byte escaped-token body fix
  and stale HTTP cancel/replacement race regression. Native identity log leak
  (upstream Device ID/device_id fields) suppressed with a new Rust regression.
- Installer isolated tests passed24 scenarios, then10 hardened/rollback cases;
  final portable full suite/upgrade service lifecycle adjustments in progress.
- CI36638062416 atd10c559: checks including installer scenarios passed;
  Android passed again. Native ucode assertions, all model/nft/DNS comparisons,
  dnsmasq syntax and initial WAN/blocked/local traffic passed. Healthy simulated
  VPN failed because wildcard echo sent replies from a different source IP;
  exact-source sockets and connected UDP fixtures fix it, pending rerun.
- Rust focused TURN fixture and full-suite TURN passed;340passed/1failed/7ignored
  overall. Remaining failure was the new redaction test's dummy password value
  triggering the existing keyword filter; fixture corrected, pending rerun.
- SDK reached ARM64 musl Rust compilation and failed4libc ABI errors (ioctl,
  sendmmsg/recvmmsg flags, private msghdr padding). Portable ABI fixes saved;
  SDK now also checks musl test compilation before release build. Target CXX
  compiler set explicitly. Cargo caches/per-job CI scheduling added.
- Installer final local checks cover27 isolated scenarios across6 test methods;
  upgrade restarts installed core/CAPTCHA versions. Real native APK signature,
  staging/cache checks are implemented in scripts/test-native-apk.sh and now
  hooked after SDK compilation, before project signing. Native execution pending.
- CI36638972094 at88d8189 is the current run for musl and network fixture fixes.
  Inspect its current jobs before claiming success. Later SDK script edits add
  native APK checks and remove stale manifests/packages from repeated builds.
- Native complete traffic suite, latest Rust/musl source, SDK packages, signed installation,
  real router/VK/CAPTCHA have not passed yet.

## Agent ownership

Check collaboration.list_agents; sessions may disappear.
backend_validate: backend milestone complete; reviewing network-smoke healthy
tunnel/transitions, owns backend/tests/policy/POLICY_STATUS.
android_validate: milestone complete; Android source/status saved.
installer_validate: install.sh/tests/installer/INSTALLER_STATUS, tests pending.
Root: broker, CI/SDK/release, native shell runner, top-level docs/Git/integration.

## Remaining sequence

1. Publish checkpoint; inspect new CI concise errors and resolve failures.
2. Finish installer rollback tests and verify native APK semantics.
3. Check compiled component paths, permissions, service/control contracts and
   DNS/routing transitions; save and push meaningful checkpoints.
4. Configure signing secret for signed preview after SDK succeeds. Android
   debug APK does not have a permanent release/update signing identity.
5. Real authorized GL-MT6000/server tests: mixed clients, tunnel crash/stop,
   DNS/IPv6, firewall/boot, existing flows, manual phone CAPTCHA.
   Record results before stable release.

See IMPLEMENTATION for contracts. Do not repeat settled questions, GitHub
login/repo creation, upstream clone, tooling installation or finished work.
