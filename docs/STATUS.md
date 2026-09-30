# Development status — resume here

Updated 2026-09-30. Signed experimental **v0.1.0-preview.1 published**:
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.1
All five CI jobs passed; release bytes/signatures verified. First real router
attempt stopped at architecture preflight; second stopped at DNS backup fetch.
Corrected installer succeeded; runtime/UI fixes are deployed and real VK connects.
Signed preview2 rebuild and real LAN policy acceptance are pending.
Read this, then IMPLEMENTATION.md. Files/Git/CI are
authority; historical component notes do not override this checkpoint.

## First unfinished action

Owner authorized direct SSH on2026-09-30: **ssh openwrt-router**. BatchMode
with StrictHostKeyChecking succeeded; uid0, GL-MT6000, OpenWrt25.12.5 revision
r33051-f5dae5ece4, tunedarch confirmed. User requires telling them what is done
on the router before each change. Task scope: current CSQTT install/debug and
acceptance; preserve management, never print secrets/credentials/VK links.
Read-only package/space preflight: only dnsmasq2.93-r1, no CSQTT packages/config;
overlay6574032KiB free, TMP495552KiB free. R2 download SHA verified, installer completed **exit0** on real router.
Three projectpackages0.1.0-r1 and dnsmasq-full2.93-r1 installed; kmodtun and
required deps present. Original DNS removed only after real isolated restore proof.
Private backup /etc/csqtt/backups/20260930-175413-32114. DNS/rpcd/CAPTCHA running;
WAN up, local127.0.0.1 DNS resolves example.com, DHCP config compared with backup.
csqtt status stopped/enabledfalse/groups0/devices0/policiesinactive.

**First unfinished action: real LAN policy traffic acceptance and signed preview2
rebuild.** Root has authorized LuCI browser2/tab2 at http://192.168.1.1; user
explicitly authorized provided private server/VK parameters for tests. Those
values were entered directly in LuCI and remain only on the router/chat; never
copy them into source, fixtures, STATUS or logs. Reuse router saved settings.
Actual browser reproduced empty group option: native select contained a nested
span. Plain string label fixed it; browser now shows main and saves a temporary
device successfully. Group table now uses an escaped DOM label for displayname;
latest source deployed, browser table shows main after reload. VK domain was vk.ru, absent
from allowlist; model now accepts vk.com/m.vk.com/vk.ru/m.vk.ru, keeps rawhash
protocol and canonical full-link display. Actual save exposed another blocker:
LAN DynamicList's empty add-item input was incorrectly rejected although br-lan
already existed. Empty add-input now valid; final saved list must be nonempty
and valid. Model/settings/policies live patches saved with private backups.
Real LuCI Android import + fullVKlink Save/Apply succeeded, no invalid fields;
SSH checked only peer/password booleans and hashcount1. **Real VK connected**:
csqtt0 tunnel, 9workers; ping-Icsqtt0 3/3, curl HTTPS boundcsqtt0 succeeds and
exitIP differs from WAN-bound curl. No raw logs/secrets printed.
Temporary testdevice name Проверка формы, unused MAC02:12:34:56:78:9A, assigned
to existing groupdisplayname main / IDcfg0246f2; UI Save/Apply succeeded. Status
groups1/devices1/policiesactive true, policy_error empty, groupDNSrunning and
localDNShealthy. Owner then added two real entries: devices3; SSH source MAC
known and management_assigned=false verified without printing MAC/IP. This
temporary entry must be removed after acceptance. preview_review owns read-only investigation
of ephemeral virtual LAN test capability; root owns browser/router mutations.
runtime_release_plan completed focused preview-build workflow reusing proven
Android artifact and cargo cache; scripts/build-sdk.sh guard fix done. Recheck agents.
`node --test tests/policy/*.test.mjs tests/luci/*.test.cjs`: **44/44 PASS**;
git diff--check PASS. Native select proof and real saves supersede earlier
Node-only UI confidence. Router remains installedr1 with test patches, no new
signed package yet. Preserve management and announce mutations before action.

Real runtime blocker FIXED: actual ucode85922056-r2 rejected escaped-NUL regex
and POSIX hash quantifier1024. Explicit ASCII scan and separate length checks
preserve validation. Root backed up original runtime.uc as runtime.uc.preview1
under the private install backup, uploaded reviewed source, compiled -c -o/dev/null
successfully, and ran manageprepare exit0. status policy_error empty/groups1/
devices0/stopped/enabledfalse/policiesinactive. RPCdevices returns12 entries
(countonly logged), services and DNS healthy, DHCP_UNCHANGED.
Native runtime driver now executes the full source with isolated fs/UCI/ubus
adapters; actual router ucode stdin execution passed all validation/redaction and
ARP/lease cases without reading private config. NativeCI previously tested only
policy.uc; Node parsed runtime asJS and missed the two POSIX failures.

User requested full VK links in separate input fields. Implemented six Value
fields, canonicalfull-links display after reload, required first/optional others;
Androidimport fills fields; validation/dedup/capacity retain rawhash protocol
compatibility internally. Original model/settings/policies files backed up as
*.preview1 in private install backup, then all3 reviewedJS files deployed over
SSH. Remote/local SHA256 match all4 patchedfiles. Router remains packageversion
0.1.0-r1 WITH LOCAL TEST PATCHES, not a newly signed release. These must be included
in proper signed preview2 packages. Live UI confirmation FAILED after Ctrl+F5; see first unfinished action.

User couldn't add devices to main: actual GridSection clones formoptions, closure
filled parent instead of modalclone. policies.js now fills this(optionclone);
new tests fail beforefix and pass after. Displayname main is valid (anonymousUCI
ID differs from clientmain). Root runtimefix restored deviceRPC; both code fixeslive but actual UI remains failing.
`node --test tests/policy/*.test.mjs tests/luci/*.test.cjs`: **41/41 PASS**.
Agent reports native-runtime stdinrealucode pass + shell/Python syntax; no agent
routerwrites. preview_review/runtime_release_plan work complete; recheck liveness.

Corrected source/dev checkpoint **6ee2bad410a0d02293ef09e71e0cf8be884ef738**,
tree **56a82c4c423b1c7a9cb80eb4484bd125411675e4**, local/remote aligned before
this docs checkpoint. **Preview2 run36757684228 dispatched**, exact buildSHA
**ed15182e51f45b9335ccea96b049496002ae97ce** (same tree), branch
codex/preview.2-build. First jobs success: native-policy110031973942 and
checks110031974856. Android110031974509 and core110031974649 SUCCESS; SDK110032580125
FAILED before package compilation: clean SDK lacked bin, unconditional find
exited1. Guard -d bin fixed; original failure reproduced and empty/cached cleanup
tested. Native APK/signing did NOT run in this failed run. Log .work/preview.2/sdk.log.
Focused preview-build wrapper now runs updated Node/release checks + SDK only;
guards unchanged core/broker/Android/native/installer source against ed15182,
authenticates prior four successjobs and Android artifact11117296798/digest,
reuses artifact and Cargo/SDK caches, requires signingsecret1 fallback, verifies
three exact r2 filenames/manifest/signatures/hashes. Prior ARM64 binary was not
uploaded; SDK builds it incrementally from Cargo cache. Agent workflow syntax,
SDK step equivalence, source guard, Node46/46 including release2, Pythonrelease4/4
passed. New focused build must be triggered after source checkpoint; freeze exact
new testedSHA for preview2. Ignored .work/preview.2/ci-status.py BUILD_SHA writesci.json and
prints compact statuses. Fetch completed logs for failures, don't repeat unchanged
polls or rebuild. Artifact/signature/revision checks remain before publication.
Build: .github/workflows/preview-build.yml thin push wrapper on
codex/preview.2-build calls existing reusableCI once with package_release2,
secretsinherit. Source/dev checkpoints skipCI; triggerwrapper commit without
skipmarker. After all5 jobs pass, tag EXACT testedSHA v0.1.0-preview.2 and publish
verified artifacts manually; don'tdispatchdraftworkflow (duplicatebuild/main
workflow unavailable). Assert exact three r2 names and extractedfixedruntime/UI.
No stable/VK/devicepolicy acceptance claim until actual tests finish.
Do not request owner to
repeat manual install now; agent has access. Values stay private in LuCI.
Command (root, exact preview tag):
```
uclient-fetch -O /tmp/csqtt-install.sh https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.1/install-openwrt25-r2.sh && sh /tmp/csqtt-install.sh v0.1.0-preview.1
```
**R2 published and public bytes verified**: 16247bytes, SHA256
1bf8b9270a973283e51ce21e10364fc1d6a3d1236ce9d69b625fdaf6f9caa9ad.
Release API confirms all10 asset sizes/digests match local verified bytes, all9
prior assets unchanged, new public download byte-identical, body matches prepared
notes. Tag remains eb461d9c6a57fb5594880348e771b27e19e11251. Browser shows DNS fix
heading/Assets12 including two auto-source archives. No package rebuild/main merge.
Ignored .work/preview.1/provenance.json records installer_dns_fetch_fix with
published/public_download_verified true, tested source6fab62b, native36739033136;
router_retry_verified false. Credentials/server/liveVK already ready; do not ask
again. Values stay private in LuCI. Wired management device remains outsidegroups.

Owner's router: exact recursive fetch with --no-cache downloaded dnsmasq-2.93-r1
and four dependencies; standalone verify reports UNTRUSTED. /lib/apk/keys is
absent; /etc/apk/keys/openwrt-25.12.pem exists (178 bytes). Verify using copied
TMP keys also reports UNTRUSTED. This is expected: official OpenWrt25.12.5
package-pack.mk creates unsigned APKs; package/Makefile signs packages.adb.
Pinned APK3.0.5 authenticates fetched package metadata identity against the
trusted index and verifies payload hashes. Do not use allow-untrusted, repeat
key questions, or install/verify the original unsigned APK as a local filename.

Implemented and tested: isolated stage update retains signed indexes;
recursive exact-version fetch uses APK's name-version.hash8.apk cache format;
independent rollback cache preserves indexes/package; actual isolated offline
restore by name=exactversion with no scripts proves both index/payload trust and
unchanged original package versions before any live DNS mutation. Live rollback
uses exact name/version plus preserved cache/index. Root owns install.sh,
tests/installer, docs/publish. Completed preview_review work: scripts/test-native-apk.sh
(unsigned original DNS fixture, signed index, corruption/wrong-key guards,
offline exact restore) and .github/workflows/installer-smoke.yml (APT timeouts).
Recheck agent liveness before delegating in a future session.

Historical fixes: read-only fetch does not populate missing indexes (-U alone
is insufficient); nonrecursive name=version selection is broken in query.c;
--recursive honors exact constraints but may exit0 after solver failure with
no download. Production requires the exact file and proves offline restoration.
Earlier harness passed all6 methods/30 scenarios in201.904s atffbd97a before the
unsigned-original correction; latest36-scenario pass is below. Native runs36729783098/
36730351333 confirmed the first two fetch failures. Run36731100060 fetched the
exact signed fixture but its missing-version assertion was wrong and was fixed
inf03d5d7. Final rerun36732102710/job109944165886 atsmoke682759f was CANCELLED
in APT dependencies; no native pass, no cause inferred, all later steps skipped.
These failures are superseded by the passing unsigned-original test below.

The focused native workflow builds only pinned APK3.0.5 and consumes verified preview
binaries; no SDK/Rust/Android rebuild or private signing key. Source checkpoints
use [skip ci]. No rerun is needed now. If a future installer/native change needs
CI, create a commit with current smokehead parent, newdev additional parent and
newdevtree, then update smoke ref. Frozen tag and project APK/manifest are unchanged.
Implementation complete and pushed: **077a39263ec2188eaaf3f8f53ed9f5dd4af82552**,
tree **4ec2cec94fef16661a88ad13ec316a26c3aec7c9**. Later source6fab62b below
only corrected the native empty-DB fixture; inspect HEAD for docs checkpoints.
Full harness: `python tests/installer/installer_test.py`, **6 methods/36 scenarios
passed in255.489s**. Node syntax, installer/native shell -n, Python AST and diff
check passed. Native embedded Python/workflow shell syntax passed by agent.
Read-only review found no blocker: full installed version set comparison,
actual extraction through signed index, independent cache snapshot and absolute
cache-dir all match pinned APK semantics. No real router mutation performed.

Latest native regression **SUCCESS**: run **36739033136**, job **109968191447**,
smoke **475ccf8b6e20d95d821e5845a209463311f40ffb**, source checkpoint
**6fab62bd6f6d186feedd46d036091579b4a64a3a**, tree
**d3d6e7f35a1d5ada83988b904d771a985f574118**. Installer bytes unchanged since
077a392; no production edit after36-scenario pass. Completed logs confirm:
pinned APK3.0.5 build, published manifest/hashes and three project signatures;
required payload/license/modes/dependencies; ARM64 smoke + Linux TUN lifecycle;
unsigned original DNS by trusted signed index; wrong key/missing version rejected;
actual offline exact restore before replacement; unsigned metadata and payload
corruption rejected; independent rollbackcache + forwarddeps + exact original
installed state/world/payload restore after loopback server stopped. No package
scripts ran in isolated roots; no untrusted bypass for verification/installation.
These are native/simulated Linux tests, not real router/VK acceptance.

Run36737840894 failed only because new empty fetch root lacked a DB for update.
6fab62b initialized that disposable DB offline with scripts disabled; before/after
empty installed/world snapshots and explicit UNTRUSTED wrong-key diagnostic now
passed. Active agent work complete; recheck liveness before future delegation.
Root owns direct router installation and acceptance as authorized above.

Ignored prepare-dns-fix.py was executed with tested source6fab62b/smoke475ccf8b;
verify-dns-fix.py passed all10 asset checks after browser upload/body update.
Native agent work completed; root now handles real router installation/acceptance.

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
