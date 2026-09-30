# Development status — resume here

Updated2026-09-30. **Source/build validation in progress; no verified installable
release and no real router/VK acceptance.** Read this, then IMPLEMENTATION.md.
Actual files/Git/CI are authority.

## First unfinished action

Publish/re-run the native APK query correction after CI36683192758 ataa5b35f,
SDK job109783468912. Checks/core/Android/native-policy passed. SDK compiled
all three packages; required payloads/modes/dependencies/license, strict
signatures/wrong-key, stripped ARM64 smoke and real Linux TUN lifecycle passed.
Transactions reached successful offline add, then the test query returned[]
because APK query requires a selection term. Source now supplies --all-matches
and quoted '*', plus exact baseline/status assertions. No installer change:
its named queries and info --from installed were already correct.
Superseded SDK jobs109773381996 (defa7f0c, cancelled by root) and109779735578
(587e1d7, automatically replaced in queue) did not finish native APK tests.
Native DNS/policy (including IPv6 DNS transport), checks, Rust and Android
passed there. CI36677864570 at d7627c3d compiled all three packages and passed
raw ARM64 QEMU plus strict SDK signatures/wrong-key rejection, then failed on
the already corrected query --no-scripts flag. SDK dependencies cache saved.
The latest checkpoint includes that correction and extracted-payload audit.
Do not repeat passed Rust/Android work or completed installer doubles.

## Saved repository/tooling

- Public https://github.com/RATOR2000/csqtt-openwrt
- Attached draft PR https://github.com/RATOR2000/csqtt-openwrt/pull/1
- Development branch codex/csqtt-openwrt. Last confirmed remoteaa5b35f77303b9f0bdf79948f3147f8d81bbfb56; inspect HEAD for later commits.
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
  User confirmed2026-09-30 that original server/client and active VK call are
  ready. Values remain private for LuCI; do not ask that readiness question
  again. No router connection details/task scope supplied.

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
  suite ran at b30a0b76 but stopped because a documentation-range fixture reply
  was rejected by DNS rebind protection. Fixture now returns public addresses
  inside isolated namespaces; protection retained. Wire roundtrips and Python
  syntax passed locally; rerun native CI. Latest first-apply correction commits
  the saved maintenance hold to fw4 before live nft validation, so a failed
  first activation remains guarded across reboot. Policy26passed locally,
  including failed-apply shell scenario. Real reboot remains unverified.
  Latest complete Node policy/LuCI run:35passed. Shell syntax for manage,
  build-sdk and native APK runner, Python syntax for DNS/QEMU and diff checks
  passed. CI36677864570 at d7627c3d: native DNS and complete native policy traffic
  passed (exact WAN/VPN resolver path, local names, nftset population, tunnel
  up/down). CI36679945450 also passed the new IPv6 DNS transport cases.
  d7627c3d passed raw ARM64 Cortex-A53 QEMU config/broker execution; the latest
  extracted-payload audit and complete native APK transaction suite await SDK.
- Android13 JVM tests, Kotlin/lintDebug/assembleDebug passed in CI; see
  ANDROID_STATUS. No actual phone/WebView/VK acceptance.
- Broker latest local go test/go vet passed: pairing/result/cancel serialized;
  stale results/cancels cannot affect replacement, quoted16KiB token fits64KiB
  JSON bound, control tokens and trailing JSON rejected. CI race check and vet
  passed at b30a0b76. Private grants/pin/URLs excluded from public status.
- Installer27 isolated command-double scenarios passed locally; Linux CI
  installer suite passed. Upgrade/core/CAPTCHA restart and exact original DNS
  rollback covered. Native APK3 signature/cache/no-scripts/offline/rollback
  runner executed at b30a0b76 but failed before its first strict verify because
  adbsign rejects the unsigned input and returns zero despite the error. Fixed:
  signing-only local transformation accepts unsigned build input; every verify
  and install stays strict. Corrected runner awaits CI. See INSTALLER_STATUS.
- Release-manifest producer/verifier CLI tests4passed locally. Shell syntax and
  git diff --check passed for latest root scripts. Public key is the only PEM
  tracked. Signed draft workflow exists; signing secret/release still pending.
- SDK runs36638972094 and36639256975 passed ARM64 client compilation but failed
  SDK host prerequisite path. Staging fix succeeded at b30a0b76: all three APKs
  compiled. Native APK tests then failed as above; no uploaded installer-ready
  artifacts yet. SDK dependency cache/forced clean of own packages, compressed
  failure diagnostics and ARM64 QEMU binary smoke implemented for next run.
  Release signing now strictly verifies project signatures and removes the
  private key from dependency builders' environment; signing secret absent.
- Package LICENSE/required original attribution added to core and Android APK
  sources, matching root LICENSE byte-for-byte. USAGE.md and ACCEPTANCE.md
  describe setup and outstanding real tests. APK extracted-payload audit now
  checks architecture, dependencies, modes, license and stripped QEMU binaries;
  passed CI36683192758. APK read commands no longer receive the
  add/del-only no-scripts flag; tightened installer doubles27scenarios passed
  again. Added native info preflight command check. New IPv6 DNS transport
  cases through LAN/public redirect passed CI36679945450.
  Preview.N now produces all three package revisions0.1.0-rN, allowing upgrades;
  revision wiring awaits workflow/SDK verification. See INSTALLER_STATUS.
- Added isolated real Linux TUN lifecycle for the extracted ARM64 client:
  private control/status, graceful stop/SIGTERM, SIGKILL TUN removal and stale
  socket restart. Python syntax and native runner shell syntax passed locally;
  actual QEMU/kernel execution passed CI36683192758. CI installs iproute2/
  kmod and checks /dev/net/tun. No server/VK or OpenWrt boot success is claimed.
- Preview preflight now requires an existing tag matching GITHUB_SHA before
  building; release uses --verify-tag and includes install.sh. BUILD documents
  tag-specific preview install and workflow_dispatch's default-branch condition.
  Four shell blocks/Python AST/diff checks passed; actual signed draft awaits
  signing secret and a verified tagged source on main. No new access token.
- SDK compilation now requests only the LuCI leaf; all three own packages are
  still cleaned and both binaries/revision supplied. Official v25.12.5 source
  (package-metadata.pl, package/Makefile, subdir.mk and toplevel.mk) confirms
  runtime DEPENDS generate compile prerequisites and each explicit SDK goal
  invokes a separate submake. Historical b30 log showed three kernel builds
  of429/417/413seconds and repeated core/CAPTCHA compilation. Local portable
  sh syntax/diff checks passed; the attempted bundled bash path was absent.
  CI36683192758 proved all three APKs and the one-leaf SDK build: packages
  phase8m19s, whole SDK job about14minutes versus38minutes with three goals.
  Native transaction rollback proof awaits the corrected query rerun.

## Ownership and next sequence

Check collaboration.list_agents before reuse; previous sessions may end.
apk_signature_fix finished preview tag preflight/verified existing tag
and install.sh release asset in draft-release.yml/BUILD.md. runtime_acceptance
completed a focused first-start service/RPC/package contract audit, found no
new definite blocker and stopped edits. tun_lifecycle finished the new
scripts/test-arm64-tun.py for isolated real Linux TUN lifecycle under QEMU;
root integrated it into SDK/CI. All three stopped edits. Root owns broker,
SDK/CI/release, top-level docs and Git. No previous process may be assumed alive.

1. Publish the native query correction and inspect its next SDK job. Signing
   secret requested from user; GitHub form shown and local private-file tab
   queued for them. No key value read or sent by agent. Await explicit user
   'готово' before treating Actions secret as configured. Native rollback
   proof still pending. Do not redo corrected d762 query failure.
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
