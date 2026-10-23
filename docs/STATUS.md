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

23Oct11:28UTC. Frozen dev/build candidate:
4f21dbf6f58b6c6fcac16eeb21c0be023b58f922,
tree daed5516a673f062a6524b562f9b071df158c8e1.
Connector push, credential-free fetch and exact tree equality PASS.
Fresh official39946222767 PENDING; regression39946224573 RUNNING.
Diagnostic6 run39946229202, source d4ab7c18cf1ccc067b6d0f020cabfc620346649d,
tree differs by diagnostic-only workflow. It uses old9358 SDK24 artifact,
NEVER release qualification. .work/preview.10/{candidate,probe}.json updated.
Preview10 NOT published; preview9 immutable; main README remains2lines,
existing attached draft PR#1 is the future main merge, no duplicate PR/schedule.

FIRST UNFINISHED ACTION: complete console provisioning fix owned by
qualification_review (vm_console.py + VMacceptance test), then push diagnostic7;
do NOT launch another6SDK cycle until actual diagnostic installation passes.
Compact current CI/probe snapshot; failed jobs only logs.
Official39946222767 waits for old39942392214 cancellation requested11:27UTC in
browser (UI confirms request, screenshot .work/preview.10/cancel-superseded-4dd.png).
Confirm old actually stops; do not mistake request for completed cancellation.
Old39942392214 now confirmed canceled, including2ARM/native-VM/release jobs.
Do not keep launching full SDK builds on diagnostic-only changes. If diagnostic6
reveals a real installer fault, fix guarded source + tests/checkpoint, then freeze
a new exact-source candidate. Successful diagnostic alone NEVER qualifies assets.
When final6SDK/3VM and5regression pass, continue signature/draft/public-download/
literal README-command gates below. Owner personally installs; no SSH mutation.

Failures resolved in current source, with honest remaining gates:
- Earlier9358 official build rejected legitimate unsigned official APK payloads.
  Producer now checks exact metadata + pinned official signed packages.adb and
  fresh empty offline native APK fetch through private file:// mirror; exact output
  filename/version/bytes mandatory, no --link/allow-untrusted. Installer already
  used correct native name=version signed-index path. 9e604 regression fixture
  falsely asserted raw info.hashes absent; removed only that assumption, retained
  all signed-index/payload/wrong-key/metadata/corruption checks. Supports either
  raw hash representation. Full corrected new candidate native SDK still pending.
- Official24.10.8 image has valid34byte FWx0 trailer after gzip. Shared bounded
  openwrt_image.py verifies whole compressed pin, gzip CRC/EOF/size and bounded
  fwtool framing/CRC. Arbitrary tail/extra gzip members refuse. Framing CRC is NOT
  cryptographic authentication; wholefile SHA is trust. Both actual24.10.8/25.12.6
  decode126353408bytes. Old artifact12454216980/.work/preview.10/sdk24-x86.zip
  ZIP SHA a08884e212db2b4f8871facef8f0bf89537423f34a98bada1623411b54ebc027.
- Both helpers prepare explicit1GiB disposable regular-file root, native offline
  e2fsck+resize2fs, preserve boot/partition1/root identity and atomic failure;
  no physical device/mount/root/symlink/junction/hardlink boundary bypass.
  image.test_disk discloses original/test bytes, expansion, physical_device=false.
  Stock104MiB capacity is NOT certified; installer resource guards unchanged.
  Native fixture initially omitted source.seek(0) after superblock read; fixed.
  Corrected Linux image/disk CI step PASS on4dd and diagnostic4/5. Actual pinned
  image expansion PASS in diagnostic4/5 before console. Native guest install not.
- Diagnostic4(39942434054) failed generic boot TIMEOUT; diagnostic5(39944323508)
  proved firmware actually boots: activation arrived19s, OpenWrt banner printed,
  hardcoded root@OpenWrt prompt was not matched. Shared vm_console.py now requires
  UID0 command response with split prefix/fresh128bit nonce, newline-anchored,
  accepts LF/CRLF/CRCRLF. Echo/stale/partial text cannot prove root or provisioning.
  set-eu prevents setup failure masked by ready echo. Distinct phases and bounded
  final64KiB fixed enum diagnostics only; no raw console/keys/URLs/commands.
  QEMU options/waits unchanged. This actual console fix awaits diagnostic6.
  Reference docs: https://openwrt.org/docs/guide-user/virtualization/qemu

Previous candidate4dd, official39942392214, is superseded, not accepted:
contracts120376734801/native-policy120378461887 SUCCESS;24.10.8 ARM/x86 and
25.12.5/25.12.6 x86 SDK SUCCESS; remaining2ARM were compiling at cancellation.
Regression39942395478 checks/core/Android/native-policy SUCCESS; SDK120379197506
was compiling, may be canceled by fresh regression concurrency. Never infer PASS.
Older39847161011/39941510870 failures and probes1-3 are historical, do not poll.

Focused local current checks: dependency8, image6, release9, public-command7,
VMcontract10 PASS. Disk17:15PASS/2explicit Windows skips (real Linux e2fsprogs,
symlink privilege); Linux CI and actual pinned image expansion separately above.
VMcontract includes actual POSIX shell UID0/nonroot, setup failure, fresh nonce,
echo/stale/partial/CR line ending and bounded privacy checks. Python compile,
assemble-installer.py --check, native APK shell syntax, diff-check PASS.
No local Rust/WSL/Docker. Agent disk_finish completed image disk module/tests;
qualification_review completed shared console/drivers/tests, no active ownership
assumed on resume. Root owns Git/release/integration. All source checkpointed.

Native installer/storage/runtime of portable release remain UNVERIFIED.
Diagnostic6 FAILED39946229202/job120389455717 at boot_console_ready_wait:
UID0 fresh response PASS, then set-e provisioning exited to askfirst console.
Agent confirmed both actual pinned images lack stty in all binary directories;
network config is generated on first boot. Remove unjustified stty dependency,
wait boundedly for EXISTING UCI network.lan interface before mutation, then
fixed phase + fresh nonce proof for each key/network/service preparation step.
Never weaken fail-on-error or fabricate guest readiness. Current full4f21 cycle
may fail old provisioning; do not misclassify as an application failure/pass.
Provisioning fix source complete, diagnostic-only push next: no stty; bounded
existing network.lan interface wait, key/DHCP/dropbear/network as separate fixed
phases, each UID0 + fresh nonce OK/FAIL. Explicit && chains/checked exits prevent
POSIX if/errexit masking. Actual shell tests cover first mkdir/UCI-set failure
without later writes. VMcontract13/13 + public-command7/7 + pycompile PASS.
Agent qualification_review finished those2files; root owns subsequent Git.
Diagnostic7 RUNNING39948133378 on6386f8ce7664beae699f8de7a35fac186e838c96.
Dev41db96d1a2419d18185c2ee6887ea036b9a909d8 is the skipci provisioning checkpoint;
connector/fetch/tree equality PASS. Build stays4f21; no new6SDK cycle launched.
Current metadata .work/preview.10/probe.json saved; .work/preview.10/candidate.json
still describes4f21/full runs, not this diagnostic-only source. Keep them separate.
Probe7 FAILED job120395721748: boot/UID0/all5SSHprovision steps PASS; actual
installer first_offline_install returned1 in0.2s. Prior bad-signature nonzero
also instant and could be generic preflight refusal, so NOT signature evidence.
Root delegated ONLY test-openwrt-vm.py + VMacceptance test to qualification_review:
safe static installer error-callsite/missing-known-tool enums and strengthen
rejection to require actual expected signature error in bounded private log.
No production-installer fix without concrete evidence; diagnostic8 next.
Safe VM diagnostics complete: current fixed phase log only,8KiB bound; exact
static installer failure literals map to integer source callsites, fixed known
missing-tool/POSIX-shell enums, source-allowlisted guest stages. No raw logs.
Wrong signature now requires nonzero AND exact signature error line; other early
refusals cannot count. VMcontract17/17/public-command7/7/compile PASS. Owner
qualification_review complete. Root pushing diagnostic8; production parser work
by disk_finish remains separate/uncommitted until its own tests/freeze.
Root added generated-install.sh numeric error line locations only (bounded to
actual source lines, never raw variable/path); VMcontract now18/18 PASS.
Diagnostic8 RUNNING39949386881 on1c8964733e477868afde00c5790a1beb7b0bc904.
Dev88ae789145ec5f88193693c35975481b6e729610 checkpoint pushed/fetched with tree
equality; build stays4f21. No new full cycle for diagnostic-only code.
11:54UTC regression39946224573 ALL5 SUCCESS, including native reference APK
job120391910853: corrected producer/native signed-index fixtures now truly pass.
Official39946222767 contracts/policy +3SDK PASS;3SDK still compiling. Remaining
portable install/VM/final-source qualification/public command gates still open.
Independent concrete image finding:24.10.8 stock status has171 install-ok and4
install-hold installed packages. Three production opkg parsers only accepted
install-ok, so held package preservation proof was incomplete (not yet shown as
the early failure cause). disk_finish now owns ONLY portable-install.sh,
focused installer tests and generated install.sh: include supported held/user
installed records, reject partial and unknown-installed ambiguity, preserve
all trust/rollback/lock guards. qualification_review owns VM driver/VMtest only.
Held-package source now frozen: shared opkg parser includes ok/hold/user installed
records in inventory/snapshot/live+staged version checks; excludes partial states,
rejects unknown installed flags/duplicates atomically. All snapshot/inventory
failures checked explicitly, including rollback invoked with errexit disabled.
Focused OpkgInventoryTest6/6 PASS (real POSIX shell), final-source both-backend
install PASS (51.425s), generated installer check/compile/shell/diff PASS.
Signed bootstrap+SIGKILL-resume session60312 and independent opkg_state_review
still PENDING; no full CI/public release acceptance implied. Checkpoint now;
disk_finish retains ownership only for concrete follow-up findings/results.
At11:36UTC fresh official contracts/native-policy and4regression nonSDK jobs
SUCCESS;6SDK + reference SDK compiling. All new source/Git IDs above preserved.
No owner router changes, scheduled tasks, reboot or WAN guard relaxation.

12:03UTC diagnostic8 FAILED39949386881/job120399845109 at strict signature
rejection; boot and SSH preparation PASS. No static/missing-tool/shell diagnostics
were emitted. Do NOT assume implicit shell failure yet: diagnostic reader ignored
its own return/stderr and tail-c support may be absent. qualification_review now
owns VMdriver+VMtest: prove bounded log-read success (fixed unavailable enum on
failure; dd+wc bounded alternative if needed), then private sh-x with only fixed
function names/line IDs emitted if still needed. Exact signature cause mandatory.
Probe9 next; no new full SDK until diagnostic actual install succeeds.

Held-package checkpoint d7286a4346159497a8fa1095dc33f0eeab69de06 pushed/fetched,
exact tree equality PASS. Source/generated installer synced. All pending held
checks finished: both-backend install and signed bootstrap/SIGKILL-resume selected
2tests PASS/352.210s; final-source both-backend standalone PASS/51.425s;6new parser
tests PASS. Independent opkg_state_review NO BLOCKER. disk_finish complete.
No actual native held-parser/installer acceptance yet. Root owns further Git.

12:07UTC full39946222767 completed FAILED:5SDK +contracts+native-policy SUCCESS,
original25.12.5ARM job120392335507 failed ONLY native r9 migration after successful
compile/privateDNS/ISA/TUN/nativeAPK/signed-index corruption fixtures/signatures
and6signedindexes/50cacheddeps. No3VM/final release gates ran. Not accepted.
disk_finish now owns ONLY test-r9-migration.py + focused migration tests: it adds
unsigned official dependency APKs as explicitfiles, likely incompatible with
signed-index-only trust model; use native authenticated offline index/exact names,
preserve original r9 DNS provider/settings/identity/budget and source proof. Add
fixed stage/error enums, no raw native logs. No production installer mutation
unless separate concrete issue reported. Actual native migration rerun mandatory.

User resumed and asked progress/5h economy: rough readiness70% done/30% remains,
explicitly estimated by gates, not a guarantee/date. App usage snapshot newturn:
5h1% used (weekly32%); previous agents errored quota mid-edit. Their source was
preserved; root now owns migration, fresh diagnostics_finish owns VMdriver/test.
No full SDK cycle until diagnostic native installation/migration pass.

Migration harness fix completed by root from interrupted source: signed-index
file:// repositories and exact missing dependency names, reused fresh native APK
authentication, no unsigned explicit official payload operands. Rooted historical
dnsmasq-full, preserve every nonproject baseline package, six synthetic owner
files, remove only introduced dependencies on rollback and require full inventory
and original world equality. Added safe fixed stages/errors, no raw native logs,
scripts still disabled. Fixed official key filenames to exact SHA required by
shared verifier; stale migration proof removed before each attempt. Host
migration_test7/7 PASS, compile/installer-sync/diff PASS; actual native pending.
Both general/portable contracts include migration_test.py.

Artifact API confirms failed ARM build DID upload complete unqualified candidate
12499474417 (14,428,822bytes, ZIPsha a14b6359eec963d7066b9700431144afa10a82ead3405ad03049da5ede085545)
under run39946222767/name candidate-official-25.12.5-mediatek-filogic-aarch64_cortex-a53.
Can download through Actions and use pinned25.12.5 SDK host APK (no Rust rebuild)
for a standalone diagnostic migration job. Source differs, NEVER release proof.
Diagnostic9 will run VM and that migration in parallel; no GITHUB_SHA override.

Fresh diagnostics_finish completed and froze VMdriver/test: phase-only wc/dd
reader checks success sentinel/status/exact8192-byte bound before UTF8 decoding;
fixed unavailable on any readfailure. Private sh-x emits only source-allowlisted
functionnames/line numbers before cleanup, never raw trace/arguments. Exact
signatureerror still mandatory, public-command driver unchanged. VM25tests:
24PASS/1Windows-skip(native dd), public-command7/7, compile/diff PASS. Root owns all.
Next push diagnostic9 with these fixes and parallel migration on uploaded ARM
candidate + pinned SDK host APK. No project rebuild/secret in migration job.

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
