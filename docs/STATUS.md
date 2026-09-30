# Development status — resume here

Updated 2026-09-30. SDK/native validation passed; corrected secret1 is verified
against the pinned project key. Per-package signing fix awaits CI. No preview or real
router/VK acceptance. Read this, then IMPLEMENTATION.md. Files/Git/CI are
authority; historical component notes do not override this checkpoint.

## First unfinished action

Inspect **CI36719698753**, source
**eb461d9c6a57fb5594880348e771b27e19e11251**, SDK **109901822944**.
Checks/core/native-policy/Android passed; SDK compiling. This is the per-file
project-signing correction. Do not start a duplicate run.
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

Prepared ignored files in .work/preview.1: install.sh copied byte-for-byte from
b21f3dd, draft release-notes.md, provenance.json and android/app-debug.apk.
Android artifact11096628199 from run36717531786 downloaded; ZIP digest
50b4b571a58df9cf7711b856b8dadbba02a0023e27258e921163cf8a899d30cb verified.
Replace staged assets/provenance with final successful run before publication.
No router APK or signed manifest is staged; provenance verified=false.
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

1. Inspect CI36719698753/SDK109901822944 with per-file signing. Key is verified; no owner
   action is needed. Complete all three strict project signatures and manifest.
   No agent reads/transmits the key. Signing and installable artifacts pending.
2. Local checks after corrections passed: Node policy/LuCI37/37; portable
   sh -n scripts/test-native-apk.sh; all five embedded Python blocks compiled;
   same-length metadata mutation assertion; git diff --check. Final preview
   must include both corrections and verified project signatures.
3. Prepare experimental preview from exact verified source; update PR/docs.
   Save small checkpoints. Do not call preview stable.
4. Obtain minimum router connection details/scope after concrete preview is
   reviewable, then test installation/server, mixed WAN/VPN, crash/stop,
   DNS/IPv6, firewall/boot, existing flows and helper CAPTCHA.
   Keep private data out of chat/logs; record results before stable release.
