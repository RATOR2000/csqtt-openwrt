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

23Oct16:54UTC. User resumed; rough release readiness estimate70% done/30% remains,
not a guaranteed percentage/date. Asked to conserve5h quota. Fresh app snapshot:
1% of5h used,32% weekly. Previous agents hit old quota; their edits were preserved
and completed, not assumed correct. diagnostics_finish completed/froze console helper/drivers/contracts. No active
subagent ownership; other old agents completed/errored. Recheck liveness.

Frozen source/dev+build06c2faf455a20f9ee6f2e85def176e0d8e6e165c,
treee5e2fd9578a8630a6bf79e52795a643dae706eac. Source checkpoint pushed through
connector, credential-free fetch and tree equality PASS. Previous4f21dbf candidate failed/superseded; fresh source qualifying. Preview10 NOT published; preview9/tag/assets
immutable. Main README remains2lines; existing attached draft PR#1 is future
delivery, no duplicate PR/schedule. Owner installs personally, no SSH mutation.

FIRST UNFINISHED ACTION: compact CI status for frozen candidate
06c2faf455a20f9ee6f2e85def176e0d8e6e165c, treee5e2fd9578a8630a6bf79e52795a643dae706eac.
Official6SDK/3VM/draft run39996605422; general5regression run39996612862. Both
started on the SAME exact source, dev/build refs updated through leased connector;
credential-free fetch and3tree equality PASS. Source is compiled/native/public
UNVERIFIED until these fresh gates actually pass. Do not restart or repoll old CI.
This final STATUS checkpoint is docs-only ahead of candidate: do NOT re-freeze or
rebuild merely because HEAD contains newer status text. Exact metadata is in
.work/preview.10/candidate.json. Read failed logs only, bounded/redacted. No source
changes expected during CI; fix concrete failures with a new checkpoint if needed.

Focused module transaction test PASS12subcases across both PMs,342.992s:
new/existing, wrong/missing ABI, service-failure rollback, SIGKILL/resume. Log
.work/preview.10/modules-focused.log. No test process remains. Independent final
integration review: no blocker found. Fresh module cache needed; old diagnostics
cannot pass full install or qualify release. No GITHUB_SHA override. When fresh
6SDK/3VM+5regression and migration pass, review signed draft, verify publicassets,
literal README command2VM, and existing main PR#1 below. No duplicate PR/schedule.
User5h quota83% at last snapshot; finish coherent checkpoint before exhaustion,
continue only on user request if this turn has ended. Owner installs personally.

Diagnostic13 run39993383309/sourcea92a3f429016e1ed4cd7b521407824327abdfa1e:
-25.12.6 job120550565871: bootstrap + exact wrong-project-signature rejection
 PASS; firstinstall stopped at portable673 missing required dependency. Old
 verified artifact12499657002 manifest lacks kmod-nf-conntrack-netlink in cache.
 Producer closure skipped all kmods exceptTUN even when their signed-index rows
 existed; reproduced directly. No project installation occurred.
-24.10.8 job120550566248: signed feed/native staged solver nowPASS after listpath
 fix; stopped at portable132 bootstrap removal proof. Native opkg source processes
 operands in order; alphabetic libopenssl3 before openssl-util blocks removal.
 Full source references: official opkg_conf.c541-545, opkg_cmd.c862+, pkg.c
 pkg_run_script noaction/offlineroot guards at https://git.openwrt.org/project/opkg-lede/.
 Existing signed9 migration diagnostic9 PASS; don't repeat for these edits.

Implemented source, native results still pending:
- Producer traverses ALL required modules/transitive deps. EACH selected module
 proves its own exactly one positive kernel=ABI dependency in signed metadata;
 reject missing/nonexact/duplicate/conflicting declarations and duplicate-feed
 ambiguity. Record kernel_package on each module; selectedTUN still mandatory.
 Firmware/kernel/DNS/firewall/procd/netifd exclusions unchanged. Schema/installer
 require every module ABI equal manifest AND current probe kernel. All signatures,
 native package checks and unchanged-inventory proofs remain mandatory.
- Rollback allows modules only if present exactlyonce in the verified transaction
 bundle with matching ABI AND absent from original package snapshot. Both staged
 and journal-resume paths pass this context. Bootstrap still forbids all modules.
- opkg removals use native --noaction per exact target, then checked actual remove.
 Retry only blocked readonly plans after another selected removal succeeded;
 zero progress fails, actual write error aborts. No autoremove/force/nodeps.
 This handles dependency order without removing baseline packages. APK unchanged.
 Mock now models dependent libopenssl3/openssl-util and nonmutating --noaction.
 Focused opkg bootstrap_success + bad-project-signature full inventory restore PASS;
 earlier old offline listpath correctly fails before live writes. Native pending.
- Private VM also now requires no pending bootstrap/project journal and preserved
 system config after invalid-project-signature rollback, before valid installation.

Checks: dependency12/12, release10/10, VM34=32PASS/2explicitWindowsnative skips,
public7/7, platform16=15PASS/1WindowsBBskip (actual Linux BB PASS12/13), generated
installer/shell syntax/nodecheck/diffPASS. New module transaction test12subcases PASS342.992s: both PMs new/existing,
wrong/missing ABI, failed-service rollback and SIGKILL/resume. Private nested diagnostics remain bounded/redacted.
Readonly actual router awk16feedcases PASS earlier; NO owner installation, reboot,
service/config/network changes. Router is personal-install-only. No schedules.
User requested quota economy: snapshot17:00UTC48%5h used; later83%5h/45%weekly,
reset21:20UTC. Save coherent checkpoint before quota exhaustion, no new agents.
All agent edits frozen; architecture/module producer agent completed focused
checks, root owns installer integration/test/final Git. Recheck agents on resume.
Preview10 NOT published/ready; rough estimate70%done/30%remaining, not guarantee.

Diagnostic9 native migration already PASS; do not repeat for console-only edits.
Both are diagnostic ONLY, old binaries differ from current source: NEVER release
qualification; no GITHUB_SHA override. After actual clean-install/native guest/
repeat proof, freeze new exact-source candidate and run final6SDK/3VM +5regression.
Then signatures/draft/public downloads/literal README checks and main PR below.
Do not launch full6SDK on each diagnostic-only edit. No owner router/network
changes. No scheduled follow-ups.

Diagnostic9 native migration job120530522032 SUCCESS: pinned SDK hostAPK present,
actual signed r9->candidate->r9/offline-index transactions, complete inventory,
full DNS provider,6synthetic owner files and originalworld preservation PASS.
No Rust/project rebuild used. Still diagnostic-only source/package mismatch,
so final exact-source ARM migration must rerun in final full candidate.
VM job120530522383 FAILED at boot_root_check_wait after180s; banner reached
after22s, installer never ran. Same handshake passed probes7/8; exact cause not
proven. Current console fix retries only readonly UID0 nonce probes under180s/
90attempt bounds and prints leading LF before every result marker, so output
cannot join a prompt without a newline. Provisioning stays checked/one-shot.
Diagnostic10 passed console/bounded read; proceed with strict BusyBox fix12;
do not rerun already-passed migration simply for this console-only edit.

Exact local metadata .work/preview.10/{candidate,probe}.json; probe-workflow-v9.yml
has both diagnostic jobs. Failed original ARM artifact12499474417 is complete,
14,428,822bytes, ZIP SHAa14b6359eec963d7066b9700431144afa10a82ead3405ad03049da5ede085545.
SDK tools require Linux; Windows has no Rust/Docker/WSL.

Current implemented fixes, remaining native gates:
- Producer accepts legitimate unsigned official APK payloads only via exact
  metadata + pinned official signed index + fresh offline native file:// fetch,
  complete payload verification and exact output bytes; no --link/untrusted.
  Native signed-index/wrong-key/metadata/payload fixtures really passed in full
  regression39946224573 on4f21 ALL5 SUCCESS, SDK120391910853.
- Full official39946222767 on4f21 FAILED:5SDK+contracts+native-policy SUCCESS;
  original25.12.5ARM job120392335507 passed compile/privateDNS/ISA/TUN/signatures/
  nativeAPK/index fixtures/50dependencycache, then failed r9 migration. No3VM/
  publication gates ran. Other old runs/probes1-8 superseded; do not poll.
- Shared image extraction checks whole compressed SHA, gzip CRC/EOF/size and
  recognized bounded fwtool trailers (actual24.10.8 valid34byte trailer).
  Framing CRC is not crypto authentication. Both pinned24.10.8/25.12.6 decode
  126353408bytes. Actual Linux disk expansion passed in probes4-8: native offline
  fsck/resize2fs, explicit1GiB disposable root, boot/partition1/UUID preserved,
  no block devices/mount/root or symlink/junction/hardlink boundary escape.
  image.test_disk disclosure required; stock104MiB capacity NOT qualified.
- vm_console.py proves executing UID0 with fresh split128bit nonce markers,
  hostname/ANSI/echo/stale/partial safe. Stock image has no stty, so none required.
  Wait for existing generated network.lan; separate checked key/UCI/dropbear/
  network steps. Boot and all SSH preparation really PASS in probes7/8.
- Probe7 first installer exited1 in0.2s. Its earlier arbitrarynonzero signature
  rejection was NOT evidence; now exact fixed signature-error line required.
  Probe8 failed there with no reason. Old reader ignored tail/read return, so
  no implicit-shell-failure cause established. Current driver checks only current
  fixed phase log via wc/dd, <=8192rawbytes + checked sentinel/status BEFORE UTF8
  decode; read failure emits unavailable. Private sh-x returns only known source
  functionnames and numeric lines beforecleanup, never rawcommands/logs/keys/URLs.
  Public-command workflow unchanged. Actual corrected transport/trace awaits
  diagnostic12;10/11 isolated actual BusyBox parser differences.
- Real stock24.10.8 DB has171 install-ok +4 install-hold records. Shared production
  opkg parser now includes supported ok/hold/user installed records, rejects
  duplicates/unknown installed flags atomically, excludes partial states. Every
  inventory/snapshot failure checked explicitly, including rollback with errexit
  disabled; generated install.sh synced. Focused6/6, final bothPM install PASS/
  51.425s, signed bootstrap/SIGKILL selected2tests PASS/352.210s, independent review
  NO BLOCKER. Native production installer/held parser still pending.
- Migration harness incorrectly passed unsigned official dependencies as files
  and did not root historical dnsmasq-full or prove complete cleanup. Fixed with
  signed local indexes + pinned key lookup + native fresh verification + exact
  missing dependency names. Seed real r9 full-DNS root, preserve all existing
  nonproject packages and6synthetic owner files, remove introduced deps only,
  require complete inventory + originalworld restoration. Scripts remain off.
  Stale proof removed before attempt, fixed phase/error enums, no raw diagnostics.
  Corrected exact hashed official-key filenames. Actual native diagnostic9 PASS;
  final exact-source migration remains required.

Focused final host checks: migration7/7 PASS, VM34tests32PASS/2explicit Windows
native-dd/symlink SKIPs, public-command7/7, dependency8/image6/release9 PASS.
Disk17:15PASS/2Windows SKIP; actual Linux image/disk success separately above.
Python compile, assemble-installer.py --check, shell and diff checks PASS.
General/portable CI now include migration host contracts. Current source has NOT
had final full CI/native/public command acceptance. Native installer readiness
and release remain UNVERIFIED. Router25.12.6 untouched; old72h incomplete.
Detailed preceding diagnostic history retained in8ae767e docs/STATUS.md.

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
