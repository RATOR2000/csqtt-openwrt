# Development status — resume here

Updated 2026-10-25. Read this first, then IMPLEMENTATION.md.
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

PREVIEW10 PUBLISHED 2026-10-24T23:43:21Z (25Oct Moscow), prerelease,418assets.
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.10
Frozen tag/application/installer source6c70e490585651b9a65d7d128ecc551415c32f4e.
General40139752629 ALL5 PASS; official40139753900 ALL6SDK +3nativeVM PASS,
including25.12.6 ARM owner tuple and signed native ARM9->10->9 package migration.
No physical owner install, actual VK/Android, boot7 or72h pass claimed.

FIRST UNFINISHED: repair public-command host harness, then both literal HTTPS
command VMs, then PR#1/main README. Initial run40143890684:24.10.8 failed at
missing_dependencies_fixture exit255 BEFORE installer;25.12.6 still active.
Do not assume255isSSH: opkg native dependency-order removal mayreturn255 too.
signing_fix owns ONLYtest-public-command.py/public_command_test.py: consecutive
readonly readiness + bounded native fixture removal passes requiring inventory
progress, noforce/dependencybypass; add failure classes. Root owns orchestration.
These are host-test fixes; release/tag/assets immutable. Do not rebuild SDK.
Docs final text in README/PREVIEW_NOTES/BUILD is local and HELD until both PASS.

Independent public verification COMPLETE PASS: fresh public-6c70e49 output,
all6profiles/396referencedassets + manifests/catalogue/installer/tag/source pinned
P256 checks PASS. Additional7 public assets downloaded from public HTTPS and
compared byte-exact: Helper3, signed publication provenance, SHA256SUMS, key,
notes. Cross-directory comparison covers ALL415base files +3Helper =418; no
missing/different bytes. Evidence public-6c70e49/.verification.json/public-extra.
Owner installs personally; no SSH changes. No schedules.

Raw signed artifact12579223101 from40139753900 independently PASS:414files,
ZIP72635488bytes SHA25624d2d80ae6ee2bf72f1522e174dd01b5d5d2f2b9103f06713616cbb82aaf1aa0;
pinned P256 catalogue/all6manifests, every artifact/proof/source and installer
binding PASS. Original ECDSA double-sign bug fixed before full requalification;
ALL6 real OpenSSL signing regressions PASS in generalchecks121008796653.

GitHub normalizes asset-name '~' to '.', found while draft-only. Pure host
publication normalizer validates original signed raw bundle, changes ONLY
transport names/descriptor name fields, preserves package/version/native
filename/proof/installer/source bytes, re-signs metadata and binds separate
publication provenance to catalogue. No GITHUB_SHA override or recompilation.
Four real Node P256 normalization regression tests PASS. Flat multi-profile
public verifier fixed with5real P256 tests; publicationguards5PASS.
Publication-only run40143742489 on671de8b324e2d888d58466cfe9e2fcb1646c902a PASS.
Canonical artifact12579437941 github-signed-preview10:415files, ZIP72643796bytes,
SHA256f7bfad787abc997aa7429b8778c59c1d370436d81d148388a722af454e045faa.
Independent local inspection .work/preview.10/github-6c70e49 PASS all signatures,
hashes/source+provenance. Local .work/preview.10/draft-verification-6c70e49.json.
Helper from exact6c source/general40139752629 artifact12578351034 appended:
APK3613575bytes SHA25601d837fef92239db28951f7ce60f5a26eb77c1c33236e8bb188d4a84e7c4d8d4,
plus .sha256 and android-helper-provenance.json. Debug APK, physical VK pending.
Published metadata read back: draft=false/prerelease=true/source6c; ALL418
GitHub asset digest+size comparisons PASS, no extras/missing. Preview9 untouched.
Browser publication screenshot .work/preview.10/published.jpg; ghTab marked output.

Root owns Git/CI/release/STATUS. signing_fix completed/frozen. release_docs_audit
is editing README/PREVIEW_NOTES/BUILD final text; root holds commit until both
public-command jobs pass. Recheck liveness before delegation. Do not rebuild SDK
for these host-only publication or documentation changes. No schedules.
Push dev through connector, credential-free fetch, align same-tree local ref.
Keep continuation and CI polling compact; no scheduled tasks.
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
Frozen Linux contracts subsequently PASS. Exact-source SDK/QEMU private DNS,3nativeVM and signature publication now PASS;
public HTTPS command acceptance is the remaining delivery gate.
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

## Historical reliability acceptance — incomplete after reference reflash

The old preview9 long-run observation was interrupted by a firmware reinstall.
Elapsed wall time is not72h evidence. Do not claim a pass, resume the old collector,
silently reset its window, or enable source-default automatic recovery on that basis.
Published preview9 and its source/assets remain immutable. Old native connection
and source-fault/Stop/observer-restart/Start/Reload checks passed on the previous
reference installation; they do not establish the current preview10 fault gates.

Detailed live measurements, private collection paths and observation clocks are
not needed in public resume documentation. Private local acceptance metadata
remains ignored. The source contract and existing tests preserve the important
process-ownership/freshness/coverage rules. The millisecond-vs-centisecond boot
clock interval correction is documented in IMPLEMENTATION and covered by tests.

No Codex scheduled tasks: previous automation was removed at the user's request.
Do not recreate an automation or token-consuming monitor. Manual continuation
only when requested. Recovery inside the router's own procd service is separate.
Current automatic-recovery default remains observe-only pending its stated gates.

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
