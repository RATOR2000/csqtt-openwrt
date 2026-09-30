# Development status — resume here

Updated 2026-09-30. Signed experimental **v0.1.0-preview.1 published**:
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.1
All five CI jobs passed; release bytes/signatures verified. First real router
attempt stopped at architecture preflight; second stopped at DNS backup fetch.
VPN acceptance is pending.
Read this, then IMPLEMENTATION.md. Files/Git/CI are
authority; historical component notes do not override this checkpoint.

## First unfinished action

Run focused native APK regression, publish additional corrected preview.1 asset
`install-openwrt25-r2.sh` and update release command, then owner retries manually.
Second router attempt used install-openwrt25.sh and passed architecture, all three
stock APK signature checks, manifest signature and package checksums. It stopped
before live DNS/config changes: `dnsmasq: unable to select package (or its dependencies)`;
`The exact original DNS package must be cached before replacement.` Temporary
diagnostics at /tmp/csqtt-install.gpCMMm. Owner read-only query confirms installed
dnsmasq-2.93-r1; no matching file under /var/cache/apk. Same2.93-r1 is in official
25.12.5 base feed. APK3.0.5 fetch opens READ|NO_STATE; missing cached index is not
downloaded automatically. -U alone does not fix that read-only path. Installer
uses explicit --no-cache for exact rollback fetch; signed remote indexes and
strict original APK verify still required. Missing exact version still aborts.
Realistic command double reproduced identical first-install failure beforefix;
afterfix `python tests/installer/installer_test.py` all6 methods/30scenarios passed
in117.224s. Both install.sh/test-native-apk.sh sh -n, Node --check, diff check pass.
Native suite adds isolated empty-index failure/direct-fetch success, signature/
byte equality and unchanged state. Linux execution of this new check is pending.
preview_review owns ONLY .github/workflows/installer-smoke.yml creation: pinned
native APK build plus existing published binaries/native tests, no SDK/Rust/Android
rebuild or release private key. Root owns installer/tests/docs/publish. Recheck agents.
Dedicated codex/installer-smoke branch will trigger this single job; source/tag/
three signed APK/manifest remain unchanged. No direct router control/SSH details.

Previous architecture fix (published, now superseded for next retry):
Architecture fix **bb2df3a00096238338560ebe4a9014270a979029**, tree
3e9006ff67cf65230ebda5b29088c8f517d293ba, committed/pushed on development branch.
Additional asset and updated release notes are public and verified:
13963bytes, SHA256 d59b2f6fa4df904ec3fe116f0aa0ac3370ea58991bfb889eff713ec1e1af856a.
Release API confirms nine assets, all sizes/digests match local bytes, eight
original assets unchanged, new public download matches tested source exactly.
Release description matches prepared text (ignoring surrounding whitespace).
Tag still eb461d9. .work/preview.1/provenance.json records fix separately with
published/public_download_verified true. Browser shows fix heading/Assets11
(two source archives); release tab left open. Original install.sh asset retains
the old guard; use the additional asset. No deletion, tag move or package rebuild.
Owner manually ran original release installer: `Unsupported package architecture`
before temporary files/package/config changes. Read-only owner output confirms:
`apk --print-arch` = aarch64; `/etc/apk/arch` and DISTRIB_ARCH = aarch64_cortex-a53.
APK3.0.5 prints its compiled CPU architecture; package DB reads the arch file.
Installer now checks both firmware DISTRIB_ARCH and exact APK arch file, retaining
board/version/target guards. The double now reproduces APK's generic print output:
before fix first/repeat cases failed identically; after fix all6 methods/30scenarios
passed in119.069s (`python tests/installer/installer_test.py`). Portable sh -n,
Node --check and git diff --check passed. Missing/wrong firmware/DB architectures
stop without mutation. Only installer/tests/docs changed; signed APK/manifest/tag
remain at eb461d9; no SDK/Rust/Android rebuild required. No new all-jobs CI claim.
Preview_review agent checked official APK/OpenWrt source read-only and completed;
root owns fix/tests/publication. Recheck live agents before assigning future work.
No direct router connection details/scope; owner performs manual commands.
Credentials/server/VK values stay private in LuCI.
Start with wired management outside groups; install preview with exact tag,
connect without groups, then one test device and WAN exception. See ACCEPTANCE.

Verified **CI36719698753**, source/tag
**eb461d9c6a57fb5594880348e771b27e19e11251**, SDK **109901822944**:
all five jobs SUCCESS. Per-file project signing verified all three APKs, then
manifest signature Verified OK. Native payload/license/modes/dependencies,
ARM64 Cortex-A53 execution, actual Linux TUN lifecycle, DNS/cache/offline and
exact rollback all passed. No duplicate rebuild or owner key setup needed.
Node37, release Node2/Python4, Rust341(+focused TURN), Android13, Go race/vet
and installer27 scenarios passed. OpenWrt/mbedTLS/package scripts and VK/phone
remain real-test obligations; do not describe this preview as stable or live-tested.

Published eight assets (three0.1.0-r1APK, manifest.json/.sig, SHA256SUMS,
install.sh and app-debug.apk). Release API confirmed public prerelease/draftfalse,
all eight sizes/digests match verified local bytes; public installer/manifest/
signature downloads match byte-for-byte. Fetched tag points exactly to eb461d9.
Final ignored files/provenance are in .work/preview.1, verified=true/published=true.
SDK artifact11100510550, ZIP SHA256
757f5a04beb24e587e835401bc7b8f385102c48a2c59704dd25fb578b765ea13;
Android artifact11097333273, ZIP SHA256
09d27a0e77398f46bed6b935c3c2c9c9126f424ee9861cb03b1a86b02b62cf4e.
Local Node verified pinned manifest signature; verify-release.py verified exact
roles/target/sizes/hashes; SHA256SUMS checked. Frozen codex/preview.1 branch is
at tested source, avoiding a duplicate release workflow build or main merge.
Source record below describes historical failures; do not repeat those repairs.
CI36717531786 atb21f3dd, SDK109894580250, passed all native/runtime/transaction
checks and actual project-key preflight: readable PEM, pinned match and probe
signature. Actual strict project verification passed core APK, but CAPTCHA/
LuCI were UNTRUSTED because APK3.0.5 adbsign signs only the first file in a
multi-file invocation. Pinned app_adbsign.c retains signatures_written across
arguments and returns0 despite per-file errors. The fix uses a new process per
APK, rejects signing diagnostics, and strictly verifies each immediately.
The native runner already proved this per-file pattern with three packages.
Owner secret correction is complete; do not ask again or read private values.

Previous CI **36714458987**, commit
`e430c0b29fca41f74412a6128d1c394f75e34934`, SDK job **109884388142**.
Checks, core, native-policy and Android passed. SDK compiled all three packages;
payload/signature negatives, ARM64/TUN, offline/cache and exact rollback all
passed. It then failed at openssl pkey: "Could not read key". No project-key
signature/manifest acceptance and no installable OpenWrt artifact was uploaded.
This includes tested deterministic tamper fixture and runtime diagnostics.
Previous signed attempt36686878030 at8cf1ae4 failed before signing because
its tamper fixture sometimes changed only compression padding. The corrected
fixture uses uncompressed APK and changes a known signed metadata value.
User added the private release key as Actions secret `secret1`. Both workflows
accept `CSQTT_SIGNING_KEY || secret1`; no key value was read by the agent.
New scripts/check-signing-key.cjs validates PEM, pinned public DER and an actual
SHA256 signature in memory before expensive SDK work; constant errors only.
Both CI and draft workflow call it. Two local ephemeral-key/redaction tests,
four release CLI tests, Node syntax and diff checks passed. The current CI
includes preflight. Do not rerun old36714458987, which lacks it.

Previous CI **36685991129**, commit `19b1e7c`, completed **all five jobs
successfully**, including SDK job **109792330330**. It used the old secret
name and produced unsigned output; do not publish/install those artifacts.
No cancellation was needed. Its native APK suite proved:

- All three SDK packages compile with one LuCI leaf build goal.
- Strict temporary-key signatures pass; wrong-key, unsigned and tampered
  packages are rejected.
- Extracted payloads, modes, architecture, dependencies and license pass.
- Packaged ARM64 Cortex-A53 QEMU smoke and real Linux TUN lifecycle pass.
- Isolated DNS replacement/conflict, staged dependency cache, network-free
  install and exact original installed-state/world rollback pass.

The APK query fix supplies `--all-matches '*'` and asserts an exact baseline;
the complete suite passed after this correction. No installer change needed.
Earlier failed/superseded SDK jobs are historical, not work to repeat.

## Repository and tools

- Public https://github.com/RATOR2000/csqtt-openwrt
- Attached draft PR https://github.com/RATOR2000/csqtt-openwrt/pull/1
- Branch `codex/csqtt-openwrt`; latest source under CI `eb461d9`, tree
  `44ea4ee9f6383e2b403ab7851a7631f6030686e8`. Local/remote aligned. Inspect
  HEAD for later documentation checkpoints; they do not replace tested SHA.
- Local push lacks auth. GitHub connector tree/commit/ref APIs work.
  `scripts/export-github-tree.py` exports committed delta to `.work/publish-delta`.
  Publish using manifest base_tree/parent, fetch, compare tree hashes and align.
  Documentation checkpoints use `[skip ci]`; record tested source SHA.
- Go 1.26.8 exists in `.work/tools/go/bin`; Node/Python and portable Git sh
  available. No local Rust, WSL or Docker. Do not reinstall/reclone.
- Private `.work/signing/release.pem` ignored; never print or commit it.
  Public `release/csqtt-public.pem` embedded in installer.

## Settled scope

- Original amurcanov/csqtt v2.1.9 at
  `446293aa2e873ac5323ef6fd2316d9b81d966c11`; Android-deployed server/web
  administration retained. No incompatible fork.
- GL-MT6000, official OpenWrt 25.12.5 r33051-f5dae5ece4, kernel 6.12.94,
  mediatek/filogic/aarch64_cortex-a53, about 1 GiB RAM/6.3 GiB overlay free.
- Russian LuCI, one active tunnel, named groups, one group per MAC, ordered
  domain/IP/CIDR rules. Unassigned devices use WAN.
- VPN traffic blocked on failure; explicit WAN exceptions and local management
  retained. Internet IPv6 blocked for VPN-capable groups; local IPv6 retained.
  DNS cache/shared IP/DoH classification limits accepted.
- Native auto CAPTCHA plus Android helper with pinned TLS, one-use pairing
  and authenticated VK-only WAN relay for a phone in blocked VPN group.
- One-command signed installation; stable release requires real acceptance.
  User confirmed original server/client and active VK call ready.
  Private values go into LuCI. Do not ask that readiness question again.
- No router connection details or live-task scope supplied. Do not access it.

## Verification and remaining limits

CI at `19b1e7c` and four completed jobs at `8cf1ae4` cover:

- Node policy/LuCI: 35 tests; Go race tests/vet; release CLI: 4 tests.
- Installer command doubles: 6 tests/27 isolated scenarios, including repeat,
  upgrade/restarts, signature rejection and DNS/settings rollback.
- Rust: focused TURN fixture plus full suite, 341 passed/0 failed/7 ignored.
- Native ucode/nft/dnsmasq namespaces: WAN/VPN rules, tunnel/route failure,
  local DNS, domain sets/reload, IPv4/IPv6 DNS, local IPv6 and unassigned WAN.
- Android: 13 JVM tests, lint and debug APK build.
- SDK at `19b1e7c`: compiled packages, native transactions and extracted ARM64
  runtime checks above. SDK APK uses OpenSSL; stock router mbedTLS APK,
  BusyBox ash and actual package scripts remain unverified. TUN namespace
  tests make no server/VK connection.

Source includes private config/status/control/identity, procd/TUN hooks,
fail-closed fw4/policy routing, guarded per-group DNS, LuCI, CAPTCHA broker/
helper and signed installer. First activation saves maintenance hold before
nft validation so failed activation remains guarded across reboot.
Actual OpenWrt boot/reload, mixed clients, server/VK and phone WebView CAPTCHA
have not run. No stable readiness claim.

Preview workflow requires an existing `v0.1.0-preview.N` tag at `GITHUB_SHA`,
builds revision `0.1.0-rN`, verifies signatures and creates a draft prerelease
with `--verify-tag`, including `install.sh`. Main still has initial source and
no workflows; workflow_dispatch needs workflow on main. First preview can use
verified CI artifacts if provenance/revision/all assets are checked.
See BUILD.md. Android debug signing is not permanent update identity.
Unused nft objects can accumulate after repeated edits; no garbage collection.

Final files in .work/preview.1 belong to successful run36719698753/sourceeb461d9;
all signed router assets, installer and helper staged; provenance verified=true.
For lean preview1, use successful final run's artifacts, verify manifest with
Node crypto and verify-release.py, then create a frozen codex/preview.1 branch
at that exact source SHA and use authenticated GitHub UI to create tag/release.
Connector lacks release/tag/upload APIs. No main merge/full duplicate build
needed. Current browser form is unsaved/unpublished; do not assume session live.
Use first tag v0.1.0-preview.1 only with package revision0.1.0-r1; next preview
requires increased revision through the draft build workflow.

## Ownership and next sequence

Check collaboration.list_agents before reuse. Root owns SDK/signing/release,
status and checkpoints. Prior runtime diagnostic edits were integrated and
passed Node37 plus CI. preview_review confirmed deterministic signed metadata
mutation and early key validator semantics; no edits/secrets/remote changes.
All agents finished. No router actions. Never assume sessions/processes alive.

1. Real router test choice/details pending; signed preview and all artifact
   checks complete. No further signing/build setup is needed.
   No agent reads/transmits the key. Signing and installable artifacts pending.
2. Local checks after corrections passed: Node policy/LuCI37/37; portable
   sh -n scripts/test-native-apk.sh; all five embedded Python blocks compiled;
   same-length metadata mutation assertion; git diff --check. Final preview
   must include both corrections and verified project signatures.
3. Preview published, PR/docs updated; preserve small checkpoints. Keep stable
   release gated on actual acceptance.
4. Obtain test choice/details/scope, then test installation/server, mixed WAN/VPN, crash/stop,
   DNS/IPv6, firewall/boot, existing flows and helper CAPTCHA.
   Keep private data out of chat/logs; record results before stable release.
