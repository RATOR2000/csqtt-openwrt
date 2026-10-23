# Development status — resume here

Updated 2026-10-23. Read this first, then IMPLEMENTATION.md.
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

## Current checkpoint and first unfinished action

Resumed2026-10-23. Frozen candidate dev/build4dd255ed392a3149cd3f185e9088d29e313ffd1f
(tree86c3af427f7e8e803f3c4e738c49e7d48a2eb77e). Checkpoint pushed through connector;
credential-free fetch and exact tree equality PASS. Official39941507237 and
regression39941510870 are superseded/failed; fresh official39942392214 and
regression39942395478 RUNNING. Native Linux image/disk preparation step PASS in
both fresh official contracts and diagnostic4. No guest acceptance inferred.
Preview10 NOT published; preview9
immutable; main README remains2lines, attached existing draft PR#1.

Current regression39847161011 on9e604 completed: checks/core/Android/native-policy
SUCCESS; reference SDK job120066943263 FAILED. All build/TUN/earlier native APK
fixtures passed, then the NEW fixture wrongly asserted raw APK info.hashes was
absent. Actual producer exposes it. Root removed only that unverified absence
assertion; signed-index digest, exact metadata, fresh native offline fetch and
wrong-key/metadata/payload corruption checks remain mandatory. Producer supports
both raw hash representations. Local dependency8/8 PASS; actual native rerun
still required. Do not call this failed regression accepted.

Prior9358 regression39839535419 ALL5 SUCCESS. Official39839530729: both24.10.8
SDKs SUCCESS;25.x builds/CPU/privateDNS/TUN/project signatures passed then bundle
producer rejected legitimate unsigned official dependency APKs. The9e604 fix
uses exact signed file:// index + pinned official signer + fresh native APK fetch
and exact resulting bytes. No --link/allow-untrusted. Installer already used the
correct dependency name=version/index path and was unchanged. Independent review
PASS; complete corrected native producer contract still pending rerun.

Diagnostic39845922812/c6db8b1 failed opaque host_preflight. Diagnostic2
39849782402/25d42ee20b2df1c1e11e53fe43638b2b38f7ca39,job120072536918 failed
image_extract/BadGzipFile after successful validation, fixture signing/server and
whole pinned image SHA. Actual official24.10.8 has valid34byte FWx0 trailer after
gzip. Shared openwrt_image.py now checks full compressed pin, gzip CRC/EOF/size
and bounded fwtool framing/CRC, rejecting arbitrary trailing bytes. Actual pinned
24.10.8 and25.12.6 decode126353408bytes; framing CRC is not claimed as signature
authentication. Local image6/6 PASS; VMcontract2/2/public-command7/7 PASS.
Diagnostic proofs are NEVER release qualification: their source differs from
the9358 binary artifacts. Artifact12454216980 remains .work/preview.10/sdk24-x86.zip
with verified ZIP digest a08884e212db2b4f8871facef8f0bf89537423f34a98bada1623411b54ebc027.

Both VM helpers now prepare explicit1GiB disposable root filesystems and record
image.test_disk (original/test bytes, expansion, physical_device=false). Stock
root104MiB/free75.629MiB is NOT certified by this expanded test environment.
All installer resource/rollback guards retained; no system files/package data
changed by offline disk expansion. disk_finish completed module/tests; root owns
integration/Git/docs. Readonly qualification_review found no CI-launch blockers;
recheck agent liveness on resume. Linux real e2fsprogs and actual guest execution
remain mandatory, mocks are not acceptance.
Headless VM host dependencies use --no-install-recommends +e2fsprogs; observed
apt preparation improved20min to9min. Only one bounded live host-apt UI read was
used for the earlier stall; no private guest logs/secrets were read.

Focused final Windows checks23Oct: dependency8, image6, release9, VMcontract2,
public-command7 all PASS. Disk17 tests:15 PASS,2 explicit Windows skips (actual
Linux e2fsprogs expansion/data readback and symlink creation). Python compilation,
actual assemble-installer.py --check, native APK shell syntax and diff-check PASS.
One attempted build-installer.py check used a nonexistent filename; corrected to
assemble-installer.py and passed. No native Linux/guest pass inferred from these.

Diagnostic3 pushed d78ace7064753001c2ddfd63fa2d31241ac37637,
tree469dba48b7f5e7d763dd8af5e1b26236edaac4b9, run39941575430 RUNNING.
It contains current helpers plus diagnostic-only workflow, Linux image/disk tests
and headless e2fsprogs. It uses older9358 SDK24 artifact, NEVER release evidence.
Both candidate.json/probe.json saved locally; diagnostic2 is failed/superseded.

New actual Linux failure23Oct: regression39941510870 checks120373804280 FAILED
in native disk fixture before expansion: _superblock moved the source cursor to
2048, then fixture copied from that position. Fixed missing source.seek(0) in
the test only; helper guards unchanged. Native tests moved to first CI step so
future fixture failures precede expensive contracts. Local disk15PASS/2Windows
SKIP retained; native result must be rerun. Probe39941575430 canceled in browser
as superseded during apt (confirmed cancellation request; screenshot in .work).
Owner disk_finish independently confirmed the cursor error, no other native
sequence flaw found. No native pass/release claimed.

Diagnostic4 source18f8c25b076e343952d439cca292575ba232213f,
run39942434054, job120376874228 RUNNING (apt). It uses corrected test first, old
9358 binary artifact; never release eligible. Candidate/probe metadata updated.
At11:02UTC: official contracts120376734801 and native-policy120378461887 SUCCESS;
all6SDK jobs running. Regression checks120376744675/core120376744762/Android
120376744350/native-policy120376744743 SUCCESS; SDK120379197506 running.
Probe4 FAILED at clean_firmware_boot/TIMEOUT (11:05UTC), before any installation.
Actual pinned24.10.8 image download, full SHA, trailer extraction, native offline
disk expansion and SSH-key generation passed;180s wait for console did not.
Readonly review agent now owns ONLY both VM helpers, VMacceptance test and optional
vm_console.py: add fixed allowlisted boot signals/distinct console phases, never
raw guest log/URLs/keys. No speculative hardware change/timeout increase yet.
Official docs confirm combined-image VirtIO BIOS method (q35 example):
https://openwrt.org/docs/guide-user/virtualization/qemu
Need diagnostic5 before deciding actual boot fix. Current6SDK/regression SDK still
running; retain exact-source qualification requirement, no diagnostic proof reuse.
Boot diagnostic source now complete: shared vm_console.py used by both drivers,
distinct activation/root/provision/ready phases and final64KiB fixed signal scan.
No raw console, matched substrings, commands, keys or URLs emitted. QEMU options,
timeouts and acceptance unchanged. VMcontract7/7, public-command7/7, pycompile
PASS. qualification_review complete; root owns integration/Git. Push diagnostic5
with new shared module; do not rebuild all6SDK until actual boot fix is known.
Diagnostic5 is now running39944323508, source9c0847c135bc397629b0f100394987f289e93e54.
Dev checkpoint52e7bdd2fe7e24b3fc1d97a6321c71927c408d31 (skipci) pushed/fetched,
exact tree190bd6810aea7243a576fb5b62e7bde7448e2f1a matched. Build remains4dd255e;
do not infer final-source qualification from this diagnostic change. At11:12UTC
all6SDK compiling, reference regression SDK starting compilation; no new failure.
Diagnostic5 FAILED boot_root_prompt_wait/TIMEOUT (11:21UTC). Crucial finding:
activation prompt arrived after19s and shell printed OpenWrt banner, so pinned
image/expanded root/kernel actually boot. Hardcoded root@OpenWrt prompt was not
observed. Root cause is console synchronization, not evidence of a firmware or
installer fault. qualification_review owns vm_console.py + VMacceptance test:
replace hostname prompt with UID0-checked command-response marker, split printf
arguments so echoed input cannot satisfy readiness; same for provision marker.
Do not provision before successful root proof. Retain strict waits/cleanup.
At11:22UTC SDK24.10.8 ARM/x86 and25.12.6 x86 SUCCESS; other3SDK compiling.
UID0 handshake fix complete: activation followed by UID==0 test and newline-
anchored split prefix/fresh128bit nonce response; no dependence on hostname or
ANSI prompt. Provisioning set-eu and fresh split ready marker prevent masked
errors/echo false positives. VMcontract10/10 PASS including actual POSIX-shell
UID0/nonroot and earlier-command-failure cases; public-command7/7/pycompile PASS.
Owner qualification_review complete. Freeze new candidate; supersede stale full
CI before updating build ref, then diagnostic6 can exercise the fix earlier.

FIRST UNFINISHED ACTION: inspect compact current CI/probe jobs; read only failed
job diagnostics. Fix actual failures and checkpoint; when successful continue
signature/draft/public download/literal README-command gates below. Keep final exact-source6SDK/3VM/signature/
public-command gates; no reused diagnostic qualification or GITHUB_SHA override.
New root release9/9 tests require explicit1GiB test-disk disclosure. Workflow
checks include image/disk tests. SDK recipe7PASS/1localGNUmakeSKIP from prior
checkpoint; earlier general Node129/platform13 remain separate evidence.

Native boot/installation/storage/runtime of the new portable installer are NOT
yet proved. No owner router changes or Codex scheduled tasks. Owner installs
personally only after published signed preview and actual README command tests.

## Implemented source and verification scope

- Official-only native signed verifier bootstrap; complete authenticated native
  feed dependency cache, exact-kernel TUN, offline staged install AND rollback,
  persistent journal/SIGKILL resume, immutable signed9 schema1 migration.
- Installer holds shared lifecycle lease through package/script/service work;
  APK --preserve-env carries owner/ticks. Bootstrap rollback hash-r prevents
  POSIX shell stale command lookup. New verifier removal must reproduce exact
  prior package inventory in staging before live changes.
- Browser first-run wizard: no writes until explicit finish; nine connections,
  disabled VPN/auto recovery until configured. Existing configuration, stopped
  state/manual72/identity/budget retained. Helper/CAPTCHA action explicit.
- New LAN auto resolves trusted static firewall/netifd scope, excludes WAN;
  manual interfaces unchanged. No board allowlist. Private DNS keeps stock DHCP/
  DNS and management. Complete LuCI+Russian locale+bootstrap theme dependencies.
- Six exact SDK tuples: 24.10.8/25.12.5/25.12.6 x filogic aarch64_cortex-a53 and
  x86/64 x86_64. ARMv7 registry candidates remain held; MIPS separate adaptation.
- SDK recipe now selected from real Source-Makefile metadata (feed/classic),
  shared by compilation and GPL corresponding source packager. Private DNS uses
  nftset; unused DNS conntrack disabled, external conntrack/guards preserved.
- Each extracted APK/IPK private DNS must execute with selected QEMU CPU and
  matching SDK musl/libraries, exact nftset token and managed config --test.
  Two mandatory ABI evidence checks added; no daemon/network mutation by smoke.
- Pipeline:6SDK/3clean x86 VMs then exact-source/package evidence and pinned P256
  signed draft10. Actual public signed ARM9→10→9 native APK transaction required
  for original tuple; scripts disabled, not proof of physical ARM services/VK.
  GL vendor experiments preserved in experiments/glinet and older checkpoints.

Local source checks: Node129/129 PASS; platform13/13 PASS (4 new private-DNS
boundary/extraction cases); release8/dependency4/SDKrecipe5/public-command6/
published-verifier3 PASS. Native-runtime fixture generation, Python compilation,
generated installer --check, shell syntax and diff-check PASS. Portable13/13
Windows full run PASS but source evolved during that run; final focused native-
environment/lock/bootstrap tests plus actual Windows/MSYS dash resumes passed.
Frozen Linux contracts subsequently PASS. Actual new SDK/QEMU private DNS, VM,
signature publication/public command remain PENDING; never infer them from mocks.
Logs .work/portable-final-v2.log, portable-apk-env.log, portable-dash-resume.log.

## Publication and final delivery gates

Keep published preview9/tag/assets immutable. New tag10/package revision10 only.
README dev uses exact-tag HTTPS tempfile command, conditional availability notice
and exact target/version table; no unconditional all-routers claim. Main README
currently only2lines; update through existing PR#1 only when verified release ready.

After private VM/signing gates, inspect signed draft, publish, then independently
verify public assets with scripts/verify-published-release.py --tag
v0.1.0-preview.10 --source-commit <exact candidate SHA> --output
.work/preview.10/public. Host verifier uses Node crypto (Windows OpenSSL absent),
bounded TLS, pinned P256, signed sizes/hashes, actual tag commit and installer
equality with tagged/qualified source. Candidate metadata .work/preview.10/candidate.json.

Then push tests-only branch codex/portable-preview.10-public-check to run
public-command-check.yml (24.10.8 and25.12.6). This checks literal tagged README
HTTPS command on disposable VMs with LuCI/OpenSSL-tool/TUN removed normally,
tagged native guest smoke, repeat/manual18 preservation and actual removal of
three application packages with four configs/LAN/LuCI/system DNS preserved.
Private HTTP CI fixture checks do NOT count as literal public command acceptance.
No secrets/signing key in public-check jobs; never overwrite failed public assets.

VM specification:768MiB RAM,2CPU, explicit1GiB disposable root filesystem.
Pinned firmware bytes and installer resource checks remain mandatory. Expansion
is recorded in image.test_disk; stock104MiB capacity is not certified. Physical device/VK/Android/live r9 services/long duration and
boot7 remain separate gates. Owner installs personally; never SSH-install.

Git pushes MUST use GitHub connector (normal git push opens GCM OAuth).
scripts/export-github-tree.py exports committed delta with --no-renames. Reassemble
UTF8 parts, create_tree on origin tree, verify exact HEAD tree, create_commit and
leased update_ref; fetch credential-free and align local branch without reset.
Deletion tree entries need mode100644,type blob,sha null. Preserve checkpoints.


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
