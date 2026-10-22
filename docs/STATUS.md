# Development status — resume here

Updated 2026-10-22. Read this first, then IMPLEMENTATION.md.
Files, Git and current router evidence are authoritative. Preserve owner settings.
Older detailed history is retained in Git at c509a1d1ad8d2126b86c2a1e502e46840b92cf86:
https://github.com/RATOR2000/csqtt-openwrt/blob/c509a1d1ad8d2126b86c2a1e502e46840b92cf86/docs/STATUS.md

## First unfinished action — official OpenWrt one-command preview

USER APPROVED replacement plan2026-10-22: official OpenWrt24.10/25.12 only,
no board lock; ARM64/x86_64 thenARMv7, MIPS remains a distinct feasibility gate.
ONE README command installs dependencies/client/LuCI; first setup in browser.
GLvendor firmware priority CANCELLED. Preserve its unfinished experiments in
checkpoint/history; exclude vendor private-runtime/legacy stack from new release.
Owner will personally install the published release: NO remote install/update,
reboot, activation, faults or service/config changes. New SSH alias is `router`;
only agreed readonly inspections allowed. NO Codex scheduled tasks.

Readonly inventory22Oct: GL-MT6000, official25.12.6, mediatek/filogic,
aarch64_cortex-a53, kernel6.12.112, APK; LuCI/firewall4/plain dnsmasq present,
CSQTT and kmod-tun absent, no /etc/glversion. Old72h collector directory absent
after owner's firmware reinstall. Old72h is INCOMPLETE/UNVERIFIED, neverPASS.
Do not run old reader through `openwrt-router` or silently start a new window.
GitHub default main README currently only2lines; user docs live on dev branch.

Baseline HEAD735b9cc(local ahead1), remote6276190. Preserve ALL unfinished
portable source as explicitly untested checkpoint before further changes.
Audit found actual blockers: preinstalled-only verifier/dependency bootstrap,
no dependency closure production, forbidden even exact-kernel TUN bundle,
no persisted interruption recovery/schema1r9 migration, all profiles unqualified,
unsigned candidate-only publication, missing portable tests/generated consistency,
workflow wrong catalogue path/missing nativelegacy script. No new CI run yet.
Next: finish official-only installer and signed dependency path, LuCI wizard,
native clean OpenWrt24/25 tests, signed preview publication and main README.
Never certify a profile just by changing qualification booleans.

Implementation milestone22Oct (NOT a release): unfinished baseline checkpoint
91285131ca77bdeee1813044b42ae7a24d4bf0c2 pushed through connector and localtree
equality verified; owner settings/router unchanged. Root updated official-only
AGENTS/contract/user docs and existing draftPR#1 title/body; PR attached to chat.
Default main README must be updated only after verified new preview assets.
Planned new tag v0.1.0-preview.10/r10; publiclateststill9, allolderassetsimmutable.

Active ownership (recheck liveness): installer_verify owns installer/bootstrap/
journal/r9migration/probe/tests; release_finish owns SDK/dependencyclosure/evidence/
VMdriver/signing/workflows; wizard_review owns runtime/pkgs/LuCI/guestsmoke/tests;
root owns docs/Git/CIintegration/publication. Prior agents ended; do not assume
their running test processes survived. ModernsourceNode127/127PASS reported,
shellsyntax and nativeUCgenerator/renderPASS; no nativeUC/SDK/VMproof yet.
LegacyGLproductionrenderer/backend/private-runtimebranches moved to experiments;
officialruntime uses nativeucode. Wizard uses existing scopedRPC/UCI, no new
arbitrary-command API, no configwrites until explicitfinish, bounded90s status
poll, preservesconfigured/stoppedr9+manualworkers and auto_recover0.

Installer in progress: native-signed bootstrap and prefetch, exact-kernel TUN,
durablejournal/offlinerollback/schema1migration. Both package-manager mock success
paths pass; bootstrap interruption/badsignature inventory rollback being tightened.
Readonly owner'sAPK3.0.5 --formatdefault query confirmed Name/Version output used
before jsonfilter exists. No install/service/network mutation performed.
Newcandidate workflow has4officialSDKtargets; official-preview pipeline then
2cleanstockx86VMs, exactsource/packageproofs andP256signeddraft. Preview acceptance
scope is ABI+cleanOpenWrtVM, neverphysical-device/VKcertification. Allprofileflags
remainheld until realrunnerproof. NextsourceCIpushwaits installer generatedcheck/
tests and finaldependency/licensehelpers; no newCIrun yet.

Continuation audit22Oct: source/doc checkpoint e16c108 is local, not pushed yet.
All implementation files below it remain uncommitted pending coherent freeze.
The first4 catalogue omitted25.12.5, making advertised r9 migration unreachable.
Release owner is adding exact25.12.5 filogic+x86 SDK/dependency/VM evidence rather
than substituting25.12.6 proof. Real-board migration remains distinct from native
isolated package transactions. Root added missing luci-theme-bootstrap dependency
for truly LuCI-absent firmware. Nonstandard fresh LAN discovery is being audited
in installer/wizard; preserve existing explicit interface choices.
Root ran sh -n on portable-install.sh, platform-probe.sh, test-openwrt-guest.sh
and git diff --check successfully; Git sh runtime discovery differed between
agent sessions, so any fresh test SKIP must be reported, never counted as PASS.

Source freeze22Oct for first full CI (NOT installation-ready): all owners frozen.
129/129 Node policy+LuCI PASS; native-runtime fixture generation PASS (execution
requires CI), platform9/release8/dependency4 PASS; legacy installer7/7 PASS.
New focused installer lifecycle/LAN2/2 PASS: owner/ticks exported, competing Stop
admitted only after cleanup; current lifecycle embedded in generated installer
and held for the full transaction, including first install. Generated --check,
POSIX syntax and diff-check PASS. Fresh full portable13-method suite and focused
bootstrap/powerloss tests still running; old run invalidated by concurrent source
and test-wrapper change is DISCARDED, not counted as passing or a product failure.
Sources now cover6 exact SDK tuples (24.10.8/25.12.5/25.12.6 x filogic ARM64/x86),
3 clean x86 VM checks and signed original ARM r9 native APK upgrade/rollback
in an isolated root with package scripts disabled. All native results PENDING.
Fresh LAN auto uses trusted static firewall/netifd scope, refuses unknown LAN;
existing explicit lists unchanged. New guest fixture has separate static LAN.
Next: connector push this checkpoint, inspect current CI, then run dedicated
codex/portable-preview.10-build workflow for native VM/signing/draft publication.
Never publish or update main README as ready until signed public assets and all
required checks pass. Owner router untouched; no scheduled tasks.

Pre-push guard fix: bootstrap now proves removal of new verifier packages in
the cloned native database restores the exact pre-bootstrap inventory before any
live addition. Both PM orphan-pruning refusals covered;8 fresh negative scenarios
PASS. Focused lifecycle/LAN2tests PASS. Full portable/resume checks continue.
SDK matrix runs once via official-preview workflow (or manual portability run),
not twice for identical dev/build branch pushes; existing PR CI remains intact.
Fresh8 bootstrap/SIGKILL resume scenarios PASS for both PMs (288.3s), including
interruption during bootstrap, completed bootstrap plus main install, and main
transaction. Root caught connector exporter missing renamed-file deletions before
ref update; --no-renames fixes export, tree equality remains a mandatory gate.

CI started22Oct: source checkpoint6d21a10773946d899ee268266ee926c88db9dc6e
pushed via connector; credential-free fetch and exact tree equality confirmed
(aebae0209c29968db4d13dfd13071ba3b70ac408). Local HEAD aligned, no owner changes.
Dedicated branch codex/portable-preview.10-build at the SAME source SHA.
Current runs: official preview39806158401; existing regression39806085162.
Initial Rust core job SUCCESS; contract checks/native-policy/Android still running.
Next first unfinished action: inspect these CURRENT run jobs compactly, read only
failed job logs as needed, fix source with checkpoints, and move BOTH dev/build
refs to the exact corrected source when required. Never inspect old CI as current.
No new release yet. Keep README preparation warning and main unchanged until all
release gates and public assets pass. Old9/tag/assets remain immutable.
Public signed ARM9 native APK migration intentionally disables scripts; physical
r9 service/VK/long-duration proof is not inferred from it or from x86 VM scripts.

CURRENT BLOCKER from first CI: official39806158401 contracts FAILED; SDK/VM/release
skipped, nothing published. Both PM bootstrap_powerloss second-run scenarios
returned127; other portable groups passed. Likely POSIX dash/ash stale command
hash after rollback removes verifier executables: clear hash before recomputing
bootstrap needs, verify on CI. Local Bash resume PASS alone is insufficient.
Installer owner also found APK3.0.5 deliberately strips script environment unless
--preserve-env; live add/del must carry lifecycle owner/ticks to avoid upgrade
prerm deadlock. Minimal fix+mock/environment checks in progress, no guard bypass.
Existing regression core/native-policy SUCCESS; current checks failed same cases.
On exact corrected source checkpoint, push dev and update build ref using leases;
rerun full current CI, do not retry the known-bad source. Full local portablev2
run still readonly but cannot supersede the native Linux CI failure.
Disposable VM resource audit: pinned25.12.6 image root104MiB/free75.629MiB before
bootstrap. If actual installer resource guard refuses, expand ONLY disposable VM
disk, preserve firmware files, and explicitly bind resize metadata in evidence;
do not lower installation space requirements or claim stock storage qualified.

Corrective source freeze22Oct: hash -r after verifier rollback fixes stale command
cache before needs recomputation. Harness now executes selected SH for BOTH
initial/retry, not hardcoded inner sh. Both PM powerloss resumes PASS using actual
bundled usr/bin/dash.exe on Windows/MSYS; Linux CI remains authoritative.
All4 live APK mutations use --preserve-env so maintainer scripts inherit the
exact lifecycle owner/ticks; mocked native environment behavior now requires it.
Fresh targeted3 methods (APK environment/lock, both PM install, bootstrap refusal)
PASS93.8s; generated/syntax/diff-check PASS. No guard or signature checks weakened.
Next: push this corrective checkpoint to dev AND build refs, inspect NEW CI only.

Corrective checkpoint pushed+fetched with exact tree equality: source
6d83ac2237e3280a977fe0667b378972a273d5f3, tree8c1786c83af7670753c503158a9daac3f18fa547.
Both dev/build refs now at this SHA; OLD39806158401/39806085162 are superseded.
CURRENT official39807723601 and regression39807727948 IN PROGRESS.
First unfinished action is compact inspection of THESE runs, failed logs only.
Local portable13/13 PASS1074.4s reported, but source evolved during that Windows
run; final targeted tests and actual selected dash augment it, frozen Linux CI
remains mandatory. No active installer test processes or remaining source edits.

CURRENT milestone: official39807723601 candidate/contracts SUCCESS on exact
6d83ac2; native Linux installer/powerloss regressions now PASS.6 SDK jobs and
native-policy launched/queued. Regression39807727948 core/native-policy/Android
SUCCESS; checks finishing. Native SDK/VM/signing/publication still PENDING.
Independent tests-only follow-up owned release_finish: public-command helper+
workflow after publication, leaving candidate6d83 product immutable. Current VM
uses private authenticated HTTP fixture seam; it must NOT be counted as actual
public README HTTPS command acceptance. New disposable VMs will verify exact
published signatures/installer/tag, remove preinstalled LuCI/OpenSSL tool/TUN
normally if needed, run literal README command, native guest smoke, repeat+remove.
Root must run public-command acceptance before advertising readiness/merging main.

SDK BLOCKER after Linux contracts PASS: official39807723601 job119929294664
(25.12.5 x86) FAILED: no make target package/network/services/dnsmasq/compile in
SDK. SDK source recipes are feed-installed; compile target and corresponding-
source recipe path must be discovered/validated, not assume full buildroot layout.
release_finish owns targeted fix plus restore/always-save Cargo cache so later
packaging failures do not discard expensive compiled dependencies. Other current
SDKs may reveal additional failures; read failed logs only. No draft/tag created.
Public acceptance tests-only source now ready/uncommitted: test-public-command.py,
public-command-check.yml, public_command_test.py (6host boundary PASS). Root added
verify-published-release.py +published_test.py (3PASS): bounded TLS downloads,
pinned P256, signed hashes, exact actual tag/source/installer; no router access.
These complement frozen product checks; run the public workflow only AFTER actual
publication. Public check fixture removes LuCI/OpenSSL-tool/TUN normally, then
literal HTTPS command, repeat/manual18, native uninstall and management/DNS checks.

SDK fix source checkpoint (native result PENDING): sdk_recipe.py selects the exact
dnsmasq-full Source-Makefile from SDK metadata (feed/classic); build and GPL source
packager share it, require SDK-contained source/license/version/upstream hash.
sdk_recipe5 tests PASS; public_command6 and published3 PASS; py_compile/diff PASS.
Cargo restore/always-save retains compile cache even if later packaging fails.
Unused private dnsmasq conntrack feature disabled after official recipe inspection;
external conntrack utility/flush logic preserved. README warning is now conditional
on actual publication (so immutable tag will not forever say 'still preparing');
exact versions/targets listed, no unverified broad support claim. Main unchanged.
Active read-only owner dns_abi_audit examines missing selected-CPU startup coverage
for the separate dynamic DNS payload; core/Go tests alone must not be called proof
that ARM private DNS executed. Recheck liveness before delegation; other owners
frozen. Next product-source push waits that focused audit and any minimal check.

## Historical2026-10-20 vendor work — superseded, retained as checkpoint

USER APPROVED portability plan 2026-10-20: first latest global/US Stable Flint2
and subsequent qualified firmware updates, then official OpenWrt24.10/25.12 on
ARM64/x86_64, later ARMv7; MIPS is a distinct source/toolchain feasibility gate.
New installs may adapt resource use; preserve existing explicit settings.
USER OVERRIDE: leave main router alone now (including SSH/installation/restart).
Owner will flash official GL firmware and add Russian later. Do not interrupt
signed9 collector or replace frozen9 assets. No Codex scheduled tasks.

Baseline clean1add9ff. Offline official4.11.0 image inspected without execution:
83,146,618bytes, SHA2564004632eaf516fd2844be0e5595b6e4171d243181ff49b81569b986c79007dae.
OpenWrt21.02-SNAPSHOT r15812+1095-46b6ee7ffc; mediatek/mt7986;
aarch64_cortex-a53; kernel5.4.238-1-d4a7d36962bb6218ebd94bf040ac560e.
fw3/iptables1.8.7/ipset7.6, dnsmasq-full2.92-7 and kmod-tun installed;
ucode/fw4/LuCIbase NOT installed.27 LuCIipks bundled in factory image.
CORRECTION after variant enumeration: nftables-nojson0.9.6-3 and nft binary plus
kmod-nft-core ARE installed. Initial exact-name lookup missed the nojson variant.
Legacy firewall remains fw3. Investigate an independent nft safetytable because
fw3flush may remove xtables-only guards. Source/native qualification still held.
mtkhnat acceleration enabled; vendor hooks can change packet path.
This is image evidence, NOT native compatibility/installation/traffic proof.
Reproducible audit: scripts/inspect-glinet-firmware.py and
docs/evidence/glinet-flint2-4.11.0.json. Source image/extracted public files remain
ignored under .work/portability/glinet-4.11.0; optional dissect.squashfs1.0 tooling
under .work/tools/firmware-python. Exact source URL is in PORTABILITY.md.

Current subagent ownership (recheck liveness on resume): installer_portability
owns install/probe/catalog/manifest/transaction tests; architecture_portability
owns platforms registry, SDK/build/portableCI; runtime_portability owns openwrt
runtime/LuCI/legacy renderer/policy tests. Root owns image audit/docs/Git/review.
Next: integrate their source, run focused regression checks, checkpoint and push
through GitHub connector; execute native build checks before claiming support.
Unknown/unqualified tuples must refuse activation without altering vendor stack.
Retain current25.12.5 schema1 installation path; no wholesale vendor firewall or
DHCP/DNS replacement, no unrelated official libraries/kernel modules on GL.
Image audit milestone: exact digest re-read through the inspector;5/5 offline
evidence/security tests PASS (tests/firmware/firmware_test.py): metadata ambiguity,
shell-as-data rejection, oversized input before read, wrong digest before parse,
and no native qualification inferred from the reference image. No router access.
Audit/contract checkpoint pushed62761908840f4e425f33c198ec2bbace6767a3a8
through GitHub connector; credential-free fetch/local tree equality verified.
Manual resource collector/report source added;4/4 resource evidence tests PASS
(PIDreuse/gaps/counterreset/impossiblemetrics/noautomaticqualification), shell
syntax PASS. No actual measurements: owner forbids touching the main router.

## Historical72h observation — interrupted/unverified after owner reflash

The paragraphs below describe Oct18–20 evidence, NOT current live state.
On22Oct the router has a fresh25.12.6 image, noCSQTT and no oldcollector directory.
Deadline passing does not prove acceptance. Preserve source/evidence without
declaring72PASS, enabling defaultauto1 or restarting the old observation.

Signed preview.9 is published, installed and passed native smoke acceptance.
72H IS RUNNING, NOT COMPLETE. Do not reinstall or repeat completed fault/Stop tests.
Start: 2026-10-18T20:28:48Z (18Oct23:28:48MSK).
Deadline: 2026-10-21T20:28:48Z (21Oct23:28:48MSK).
Private router directory: /etc/csqtt/backups/preview9-acceptance-20261018-202846.
.work/preview.9/acceptance.json pins the directory, build, hashes and exact clocks.
Latest native read: sameboot, live exactPID/startticks/argv, fresh sample,72workers,
WAN/VPN/groupDNS healthy, one configured client/observer, no process change.
Baseline1attempt/1soft/1transport incident came from the planned test BEFORE this
window; do not count it as a new ordinary-use outage. Rolling attempts age out.

Use the existing readonly command, no new source/CI audit for unchanged state:
& 'C:/Users/Alexander/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' .work/preview.9/check-acceptance.py
It saves bounded public evidence/summary locally and validates sample freshness,
sameboot, exact process ownership and coverage. A finished72h marker means
finished_review_required, never automatic overall acceptance. Inspect detected
outages and recovery results; do not declare72h before actual complete coverage.
Process exit, boot change, sample gaps or invalid evidence mean incomplete; never
silently reset the window. User ordinary settings/usage must be preserved.

USER OVERRIDE 2026-10-19: NO CODEX SCHEDULED TASKS. User cited token availability
and explicitly requested removal. Heartbeat csqtt-preview9-72 DELETED through app
tool, deleteStatus=deleted; its automation.toml is absent. Do not recreate it or
any substitute schedule without a new explicit user request. Continue manually
when the user asks. Router-local procd recovery and passive72h evidence collection
remain running without Codex tokens; cancellation did not change router services.
After successful72h, implement the remaining defaultauto1 source/release step
with appropriate checks/checkpoint; never replace published9 tag/assets.
Source defaultauto remains0 pending acceptance; live owner auto_recover=1.

Manual read Oct19 15:50UTC: elapsed69686s (19h21m), sameboot/coverage valid,
collector fresh/alive,72workers and WAN/VPN/DNS healthy.385 recordedchanges/
heartbeats,0observed client process changes, no new soft/transport cycle. Brief
groupDNS failures returned to vpn_reachable after84/24/25s; two preceding
probe_uncertain samples also cleared. Counts are recorded transitions, not a
claim of confirmed LAN outages.100 status_stale transitions require diagnosis.
Readonly low-priority native clock proof .work/preview.9/clock-freshness.public.json:
status5ms ahead of truncated /proc/uptime, SAME PID/startticks/boot,72workers,
clock catches up at next10ms tick. Thus strict future-time comparison can reject
a current status; it does not establish the cause of every historical warning.
SOURCE correction completed in runtime.uc and recovery.test/native-runtime:
integer uptime interval[L,L+10), current-tick timestamp accepted, next tick and
malformed data rejected. Expiry uses conservative upperbound: status<=15s,
lease<85s; may expire<=10ms early, never later. PID/startticks/boot/human ownership
checks preserved. Node runtime/recovery40/40 PASS, native generator syntax and
generation PASS, actual router ucode in-memory fixture PASS (production services
untouched). Centiseconds .01/.08/.09/.12, +0/+1/+9/+10ms, expired/malformed times,
ownership mismatches and lease guards covered. Original native success marker
preserved; extra freshness marker added. Evidence: .work/preview.9/freshness-
{node,native}.public.log; generator node tests/policy/native-runtime.mjs followed
by root run-freshness-native.py. No new SDK/Rust/CI build or signed release.
Source-only checkpoint; no live installation/restart/window reset, signed9 continues.

## Exact signed release and live state

Release: https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.9
Frozen source20d405f272ec24fdd4cb02780e6a9068e3274351,
build926a44f31caeb760df70d808eee53d6f715d0d8b,
treef7ee0b0931e151f4c732bfe7e3949577d74ee893.
Run39161176161 all5 PASS: checks117774641657, core117774641601,
native117774641441, Android117774641697, SDK117774930559.
OpenWrt artifact12148789642, Android12149236103; exact digests/head/log bindings
in .work/preview.9/{release-config,artifact-metadata,job-log-metadata,provenance}.json.
All8 public downloads, API sizes/digests, tag/commit/title/body verified. All3APK
and manifest signatures match pinned project P256 public key. Public PEM SHA256:
39259baf94d83602c784b103506445cd7e26ec9c3635cc277b90ff31fe4d4bac.

Signed installer exit0; csqtt/csqtt-captcha/luci-app-csqtt are all0.1.0-r9.
Four files csqtt/dhcp/firewall/network byte-preserved; enabled1/auto_recover1 and
rolling budget/last_action retained. Native all15 installed payload hashes match
signed9; temporary production health.uc hotfix fully replaced. Normal group DNS,
local DNS, policies,72workers, separate WAN/VPN HTTPS exits and released maintenance
guards PASS. Router GL-MT6000/OpenWrt25.12.5, no reboot and no WAN fallback.
Proof .work/preview.9/router-{upgrade,post-check}.public.log, both exits0.
Private current backup: /etc/csqtt/backups/preview9-upgrade-20261018-202542-1058.
It includes four configs, signed7 rollback APK/manifest/installer/publickeys and
signature/hash proofs; native offline solver simulated all3 r9-to-r7 downgrades
successfully WITHOUT actually downgrading. Do not use withdrawn8 for rollback.

## Completed reliability checks — do not restart them

CI:104policy/LuCI+2release Node,7installer+4release Python,376Rust passed/0failed/
7existing ignored, focusedTURN1. Exact packaged LuCI25 and reload6 PASS.
Native real health.uc filesystem import/all6exports, ucode/DNS TCP/UDP/IPv4/IPv6,
traffic guards, ARM64 startup and real isolated LinuxTUN lifecycle PASS.
New signed ELF early --health-probe/--control-request/--recovery-step native PASS
before installation; device-id/livePID unchanged. Package/source/mode/license/
dependency/minification verification complete in provenance. No localRust build.

Source fault acceptance: router-origin198.18.0.1TCP443 only, no LAN forward match;
soft repair at215s then one transport restart at276s, one cycle charged, guards
checked every5s/no duplicate; cleanup/table removal exit0, restored72healthy.
Native Stop/observerrestart/Start/unchangedReload PASS: Stop disabled/0clients,
observer respected it, guards/budget preserved, Start1client, Reload samePID and
effective config; four configs restored byte-identical. Source-test evidence in
.work/preview.9/source-{controlled-acceptance,management}.public.log. One initial
preflight refused transientstatus_stale BEFORE mutation; fresh baseline retry PASS.
These source proofs are separate from signed9 smoke and real LAN/VK acceptance.

Collector reads bounded8sucode/5subus, logs safe enums/counts/state changes and
10min heartbeats, samples10s,2MiBcap. Rejects >60s sampling gaps/window reset.
Reader checks fresh sample, initial/log coverage, exactPID/startticks/NULargv,
sameboot,259200s duration and terminal/finishclock proof; SSHoverall timeout45s.
Shell/Python syntax and isolated valid/invalid/identity/timeout cases PASS.
Native collector readiness/fresh advancing sample PASS; native forced2stimeout
reaped its own process group and preserved an unrelated child (public proof
.work/preview.9/collector-timeout.public.log). All private raw stderr stays private.

## Withdrawn8, implementation and deferred gates

Preview.8 was published then WITHDRAWN after real ucode export grammar failure;
all8 assets renamed withdrawn-, release warns against installation, old tag kept.
Source9 adds six }; export terminators + real filesystem import regression.
First9 candidate39159616158 failed only the strict QEMUownership fixture: QEMU8.2.2
synthesizes /proc/self/stat and /proc/<pid>/stat startup clocks. Current code reads
kernel TGID leader /proc/<pid>/task/<pid>/stat; exact ownership checks retained,
native Rust main/thread regression and actual ARM64 fixture now pass. Old failed
candidate/evidence isolated in .work/preview.9/failed-candidate1, never reused.

Implemented auth queue release during human CAPTCHA wait, per-cohort singleflight,
unclaimed60s retries, protected activeHelper/stale-answer rejection, atomic90s
admission, private fresh owned status, early identity-free bounded TLS/DNS probes,
30sprocd observer, confirmed180s/softthenfresh30s/one transport restart,300sbetween/
3rollinghour including failures, serialized lifecycle/installer/recovery and
failclosed policies. Original amurcanov/csqttv2.1.9 protocol/server unchanged.
Real VK CAPTCHA may still require a person. Auto VPN group switching CANCELLED.
Full contract and public status semantics: docs/IMPLEMENTATION.md.

Stable release still requires actual failed-first-activation BOOT and full real
Android/VK Helper/manualCAPTCHA acceptance, plus remaining ACCEPTANCE gates.
Boot7 materials saved in ee557fd5dbf66c20466916ca76c9f30402aa7a90; do not reboot
or run new boot faults under that deferred plan. Do not repeat passed normal
boot/crash/synthetic routedIPv6 proof. Never call the project stable/fullyaccepted.

## Tooling and ownership

Root owns live/router/Git/publication. Freshness review agent finished; check liveness
before delegation. Keep future outputs/checks focused: owner requests lowtokens.
Repo RATOR2000/csqtt-openwrt; dev codex/csqtt-openwrt, no merge just to save work.
Windows/PowerShell, portableGo .work/tools/go/bin; no localRust/WSL/Docker.
SSH openwrt-router with BatchMode/StrictHostKeyChecking/ConnectTimeout8.
Send LF scripts as Python subprocess bytes; PowerShell pipeline appendsCR.
Router has setsid, NO nohup. Never expose passwords/VKlinks/grants/identity/keys.
.work/dist/build/private credentials remain ignored. GitHub publication tab2 is9;
user tab1preview1 must remain. No OAuth/key setup needed.
Push through GitHub connector create_tree/create_commit/update_ref using
scripts/export-github-tree.py committed bytes; normalgitpush opens GCM OAuth.
Credential-free fetch, require tree equality, update localref; dev checkpoints
skipci. Frozen tags/assets immutable. Detailed old history linked at top.
