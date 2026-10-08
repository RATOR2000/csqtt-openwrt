# Development status — resume here

Updated 2026-10-08. Read this first, then IMPLEMENTATION.md. Files, Git and CI
are the source of truth. Preserve current owner configuration. Historical
details are recoverable from Git; do not restart completed work.

## First unfinished action

Review the failed-first-activation guard persistence path and prepare a scoped
real boot proof that preserves current owner settings; fix any demonstrated gap.
Manual Android Helper/VK CAPTCHA still needs an actual challenge. Do not force
CAPTCHA or change owner devices for a green result. Other unresolved ACCEPTANCE
rows and outage observation remain stable-release gates. Auto VPN is cancelled.

Current router: signed preview6, all3 packages0.1.0-r6, connected72/no errors,
owner groups1/devices2/rules5. No synthetic state remains. Four current owner
config files unchanged by upgrade; never restore older owner backups. Recheck
SSH/Git/current state before mutations. Do not repeat completed crash/normal
boot/IPv6 proofs. Root owns integration/live/Git; preview6_stage and ipv6_checks
completed. Recheck agent liveness before delegating.

## Preview6 publication and signed upgrade (2026-10-08) — complete

- Public prerelease:
  https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.6
  Frozen source1d9c470dd89e7b820ff13c91fd3d7531181bfb9e;
  tag/build e274bedca1a72d0d8e03073abf1838f4a809fe8d;
  tree5f1455bebd8fc49828e64e89354c3d7a816661f9;
  branch codex/preview.6-build. Do not move frozen refs or dispatch duplicate CI.
- Single run37752081113 success: checks113227497194, native113227633654,
  core113227633836, SDK113228570283.75Node(73policy/LuCI+2release),4Python;
  Rust353passed/0failed/7existing ignored plus focusedTURN1. Native ucode/DNS/
  nftables, fresh SDK ARM64/LinuxTUN/offlineDNS tests passed.
- Authenticated logs and exact archives verified; .work/preview.6 retains
  release-config, provenance, assets, logs and helpers. OpenWrt artifact
  11539109569 SHA2567d8b01b544f4ee8aadd0841ec486829dd8215d436adfedb39de27eb8d5a37b17;
  Android11538572219 SHA256db0587b3a89fdfa1cdddd05c42f4b83d31c7d5f2791dd3ba1ba92afb49ee6d9b.
- verify-build-tree/fetch-artifacts/prepare-release PASS: pinned3APK+manifest
  signatures, exact frozen payloads/modes/licenses/dependencies,22packagedLuCI
  and6packagedinit tests, compiled ARM64 feature proof, originalAndroid reuse.
  Android/broker/installer/transport source unchanged. Initial prepare stopped
  on one optional overview.js newline after '+' removed by SDK C jsmin.
  Partial attempt retained; independent review approved exactly one separator
  normalization with all remaining bytes compared. Fresh prepare passed;
  no source/binary change or repeat CI. Provenance records the normalization.
- All8 assets uploaded; verify-public-release PASS: exact tag/title/body/flags,
  all8API sizes/digests and all8download hashes. provenance published=true and
  public_download_verified=true. Initial upload autosave failed; explicit Save
  draft allowed all8 to finish before Publish. No package bytes/ref changed.
  Agent tab3 is public release deliverable; published-release.png saved.
- SSH root/no pending edits, native helper sh-n PASS. Signed installer exit0,
  installer SHA2561bf8b9270a973283e51ce21e10364fc1d6a3d1236ce9d69b625fdaf6f9caa9ad
  matched published bytes; all3packages0.1.0-r6. All4files csqtt/dhcp/firewall/
  network byte-match preupgrade. Private backup:
  /etc/csqtt/backups/preview6-upgrade-20261008-092607-15078.
  Never export raw configs/installer logs/diagnostics. Safe local upgrade log
  .work/preview.6/router-upgrade.public.log and exit0 persist.
- Read-only router-post-check exit0: all11signedr6 payload hashes, versions,
  running/enabled/policies active, connected72/noerrors, groups1/devices2/rules5,
  local/groupDNS example.com, WAN/VPN IPv4 HTTPS and different exits. Evidence
  .work/preview.6/router-post-check.public.log/.exit. Fresh LuCI relogin shows
  connected72, decimal units and policy protection; policies page has two enabled
  owner checkboxes checked, no pending edits. Owner rows were not toggled.
  Screenshot .work/preview.6/router-r6-overview.png saved. Actual Android
  launch/manualVK remains pending.
- README/BUILD/USAGE/PREVIEW_NOTES/ACCEPTANCE updated for verified preview6;
  git diff--check PASS. Checkpoint is development evidence, not a stable release.
- STATE=/etc/csqtt/backups/device-toggle-test-20261006-132153.OmHlBi retains
  private earlier acceptance/current owner baselines. All synthetic objects,
  temporary test packages and init hooks removed, as recorded below.

## Acceptance continuation (2026-10-08)

- User reported CAPTCHA opened blank browser page; Helper did not launch.
  Reconnect helped. Root delegated LuCI handoff fix/tests to captcha_fix;
  no real CAPTCHA success claimed. Recheck agent liveness on resume.
- SSH current connected72. Oct6 synthetic group/device/1.1.1.1 WAN rule and
  cq-toggle-test namespace still existed after interruption; owner active devices2
  plus synthetic1. Official test-only kmod-veth6.12.94-r1/coreutils-timeout9.9-r2
  remain installed; world.before under acceptance5-tools-20261006 private backup.
- Prior controlled stop packet evidence:4 ICMP/TCP attempts,0WAN passes;
  fresh DNS query1/guarded-source WAN0; direct1.1.1.1 HTTPS and LAN ping/HTTP
  succeeded. Service recovered72. Original command session lost at interruption;
  count evidence retained but do not invent its final exit code. Current config
  has newer owner edits; dhcp/firewall/network unchanged against stop backup.
- One real SIGKILL crash test PASS exit0 in16s on signed r5 binary. Strict
  PID/startticks/exe/argv/hash validation before signal, TUN disappeared;
  real ICMP1/TCP2 ingress attempts,0WAN egress, guards/unreachable retained,
  LAN available. procd new process recovered72 + VPN HTTPS. Four configs exact
  against current precrash copies, no pending edits, passive observer removed.
  Private evidence /etc/csqtt/backups/acceptance5-crash-EImneD;
  STATE/crash-run.public-result.log + crash-run.exit persist safe result.
- Test helper corrections only: asynchronous graceful stop needs TUN disappearance
  wait; BusyBox sleep has no fractions and nc has no -w; CGI cold load exceeded
  short probe, static LAN HTTP used. These were test assumptions, no source fix.
- Initial boot helper arm recorded before reboot. Root owns mutation/cleanup/docs;
  former native_device_checks/ui_finish/boot_checks sessions are gone.
- Real early boot proof PASS exit0 after actual reboot before START95, no core/TUN:
  TCP1/ICMP2 attempts, VPN-to-WAN0, direct WAN exception16 packets + HTTPS success,
  LAN ping available; unchanged4configs, normal connected72 afterward. First
  attempt stopped on policy.nft hash difference from legitimate netifd hotplug
  regeneration (benchmark alias disappears at boot); configs were exact. Private
  boot-attempt1 retains that failure. Corrected helper records generated policy
  hash but gates on unchanged4configs and actual live classifier/guard packets.
  Second actual boot proof files STATE/boot.* contain PASS/counts/exit0.
  Exact owned init service and startup links subsequently removed; all4 current
  owner configs still byte-match pretest baseline after both reboots.
- Before UI patch, all11 signed r5 payload hashes + versions and postboot WAN/VPN
  HTTPS/DNS PASS. LuCI CAPTCHA handoff source patch now installed OVER signed r5:
  Android direct-tap intent targets exact Helper package, secret-free same-origin
  Overview fallback; desktop manual-copy flow avoids unsupported scheme navigation.
  Pairing wipe/expiry remains. Source73 Node tests PASS including17 LuCI cases;
  independent review PASS. Actual browser blank cause not reproduced, no real
  Android/VK success claimed. Broker/Android/core unchanged. Private original
  overview.r5.js under /etc/csqtt/backups/captcha-handoff-20261008; source SHA cmp
  passed and client PID unchanged. Browser relogin confirms connected72.
- captcha_fix completed; ipv6_checks owns only ignored IPv6 helper preparation.
  Root owns integration/live testing/cleanup/docs/Git; recheck liveness on resume.
- First routed IPv6 attempt stopped at positive HTTP403 from isolated uhttpd
  without default index config (8 controlTCP packets passed fw4). No protection
  PASS claimed. All4config bytes/policy hash unchanged. All temporary IPv6
  routes/addresses/veth/ns/fw4 rules/observer removed and synthetic MAC restored;
  helper cleanup reported0, likely its own child process reaping check. Agent
  fixes explicit index.html URL and cleanup diagnostics before retry. Private
  evidence acceptance5-ipv6-lAejlL; root prepared reviewed final-cleanup.sh.
- Second actual routed IPv6 packet proof PASS before/after real fw4 reload:
  unassigned TCP HTTP + UDP AAAA positive controls passed both phases; protected
  TCP2/UDP1 ingress attempts each phase,0 packets past product guard, localIPv6
  ping passed. Isolated documentation endpoint, no ISPIPv6 claim. All4configs
  exact and policy hash unchanged. Helper exit1 only on cleanup checks for
  missing client-neighbor/endpoint-alias identity; no product packet failure.
  Independent root inspection confirmed all IPv6 aliases/routes/neighbors,
  endpoint namespace/veth, scoped fw4 rules and observer gone, MAC restored.
  Keep distinction between packet proof and helper exit. Private evidence
  acceptance5-ipv6-fmChDp; STATE/ipv6-run.public-result.log/exit retained.
- Reviewed final-cleanup.sh native sh-n PASS; actual cleanup exit0. Removed
  exact cq_accept_wan then original owned toggle sections/ns/veth/198.19 alias/
  resolver/pointer and exact synthetic ARP. Original helper exit1 was expected
  newer-owner vs Oct6 export comparison; cleanup-complete existed. Final all4
  config files byte-match Oct8 owner-expected copy, pending edits empty. Owner
  rules5 preserved. Removed only test-added coreutils-timeout9.9-r2/kmod-veth
  6.12.94-r1 after simulation proved exactly2 removals; unloaded veth, APK world
  byte-match pretest. No temporary init/observer/accept/address/route/ns/link.
  STATE/final-cleanup.public.log/exit0 retains proof; private logs stay private.
- Final read-only final-health.sh native sh-n + real run exit0:10 signed r5
  payload hashes, original signed overview backup hash and1source patch hash,
  r5 package versions; connected72/no errors, owner groups1/devices2/rules5,
  local+group DNS, WAN+VPN HTTPS and different exits all PASS. Served HTTP JS
  hash also matches source. Source73 Node tests/17 LuCI passed before install;
  no source changed afterward. No new compilation or public binary release.
  captcha_fix/ipv6_checks completed; root owns next preview and real acceptance.

## Preview5 publication and signed upgrade (2026-10-06) — complete

- Release https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.5
  is public prerelease, not stable. Exact tag/build
  38e0283f724aa3110cfc75ad22f9bf57801e4b80, frozen source
  295fa037a007d77e40899109cd70e8df53ad1c5a,
  tree adb5492d7177a7a508cf182d8997a8b532ea56de. Build branch
  codex/preview.5-build; one run37464598550, no duplicate dispatch.
- All four fresh jobs success: checks112272354749, native112272425249,
  core112272425384, SDK112273279793.71 source tests,20 packaged LuCI,
  6 packaged init;353 Rust /0 failed /7 ignored plus focused TURN;
  native policy flags/DNS/nftables, ARM64 ELF/TUN, offline DNS restoration.
- verify-build-tree.py, fetch-artifacts.py, prepare-release.py PASS: exact
  authenticated logs/artifacts, frozen payload/source/modes/dependencies/license,
  pinned manifest and3APK signatures, Android whole APK/signature reuse proof.
  SDK artifact11415902761 ZIP SHA256
  401f404152f76d83f449c6653f9e00b06437b255bc0d9e8e2684a964070e9f9e;
  Android11414083202 ZIP SHA256
  5bad74c69bfe1520046f7f01a91420d643893ed59d85c0e4d398b7b42597b8ff.
- All8 assets fully uploaded. verify-public-release.py PASS: exact tag/title/body,
  API uploaded states/sizes/digests and all8 public downloads/hash matches.
  Ignored .work/preview.5 retains complete frozen release-config, signed assets,
  authenticated logs, provenance and reviewed upgrade/postcheck helpers.
- Reviewed upgrade-router.sh executed through SSH: installer hash
  1bf8b9270a973283e51ce21e10364fc1d6a3d1236ce9d69b625fdaf6f9caa9ad
  matched published bytes; signed installer exit0, all3 packages0.1.0-r5.
  /etc/config/csqtt,dhcp,firewall,network byte-match private preupgrade backups.
  Backup /etc/csqtt/backups/preview5-upgrade-20261006-131154-7089 contains private
  configuration, installer/diagnostics/logs; never publish raw contents.
- Read-only router-post-check.sh PASS: all11 installed payload hashes match
  exact signed r5 packages, versions r5, running/enabled/policies active,
  connected72, groups1/devices2/rules4/no errors, LAN/group DNS example.com,
  WAN/VPN IPv4 HTTPS and differing exits. Local management available.
- Real LuCI after rpcd restart/relogin: two owner checkbox rows checked; Overview
  connected72 and decimal Кб values, no old binary units/Auto VPN. Owner rows
  were not toggled. Earlier synthetic VPN→WAN→VPN test remains separate below.
- Verification helper first stopped after successful11 hashes on missing status
  rules field. Corrected to count UCI rule sections privately; complete rerun
  PASS. No router/product fault or source change. Cold SDK compilation warning
  did not prevent its success. Initial artifact download needed User-Agent;
  exact digest/size gates then passed. No downloaded old SDK/core reused.
- Agent ui_finish updated README/USAGE/BUILD/PREVIEW_NOTES only; native_device_checks
  fixed ignored helper only. Both completed, no ongoing ownership. Root owns
  publication/live upgrade/checkpoint. Recheck agents on resume.

## Device source fixes (2026-10-06) — before signed r5 upgrade

Owner cancelled Auto VPN; original WAN/VPN only. Overview formats decimal byte
counts as Б/Кб/Мб/Гб (1000), finite/negative guards retained. Saved device rows
have an inline enabled checkbox; missing/1 remains active,0 removes routing,
DNS redirect and IPv6 guard membership while retaining row/name/MAC/group.
Validation still covers inactive IDs/MACs/groups/duplicates/flags. RPC group and
status count reflect active assignments. Explanation moved above the table so
checkbox column stays compact. Fresh LuCI confirms two owner rows checked.

Actual LuCI Save & Apply revealed old init reload always restarted transport.
Fixed csqtt.init to snapshot client.json privately, apply guarded policies once,
keep the same running process when transport config is unchanged, and restart
only when changed/missing/stopped. Disabled main stops transport after apply;
failed apply leaves original process/guards, cleans snapshot and returns error.
Existing procd file-watch scope retained; no protocol/core changes.

Checks:
- All71 Node policy/runtime/DNS/LuCI/service-reload tests PASS, final full command:
  `node --test --test-reporter=dot tests/policy/*.test.mjs tests/luci/*.test.cjs`.
  Six service tests use a real disposable process: same PID, config change,
  failed apply, main disabled, absent/stopped process, stop failure.
- Real router ucode native policy + generated runtime adapter assertions PASS:
  flag types, full inactive validation, active-only model/RPC/status, DNS/IPv6
  removal, reenable equality, existing control/redaction/DNS lifecycle.
  Runtime compile and init/helper `sh -n` PASS; git diff --check PASS.
- Real synthetic bridged namespace VPN → browser-uncheck/SaveApply → WAN →
  browser-check/SaveApply → VPN PASS. Actual HTTPS exits distinguished WAN/VPN,
  DNS and LAN management worked both modes; previous conntracks absent before
  fresh traffic. Disabled row persisted after browser reload, runtime/live nft
  excluded its MAC/group, reenable restored it. Original PID/startticks survived
  both successful browser toggles (only original failed test restarted it).
- Cleanup PASS: synthetic rows/group/namespace/veth/address/resolver/ARP removed;
  all four owner UCI exports match retest baseline exactly, no pending edits.
  Temporary exact official kmod-veth/coreutils-timeout removed, veth unloaded.
  Final installed five files cmp match source, DNS ready, connected72/devices2,
  no remaining private reload snapshot. Management remains unassigned.

Before the signed r5 upgrade, five source files were patched over signed r4:
policy.uc/runtime.uc/csqtt.init/model.js/policies.js. Persistent rollback copies
and all four original configs remain private under
/etc/csqtt/backups/device-enabled-fix-20261006-121314-31188.
Ignored .work/device-toggle has reviewed deployment/helper scripts and UI proofs;
private packet-test evidence remains under device-toggle-test backups on router.
No test-state pointer/process/namespace is left. Agent-created browser test tab4
retained for final LuCI verification; user-owned tabs1/2 preserved. Long-open tab1 retained
old HTTP scripts; fresh tabs load updated UI. Screenshots remain ignored.

Failures/corrections retained:
- Original init restart caught by strict PID assertion before WAN probe; fixed
  and complete fresh retest passed. First browser save materialized enabled1 on
  two legacy rows only (same behavior); private memory comparison confirmed
  dhcp/firewall/network unchanged, no owner route/credentials changed.
- Router timeout was a BusyBox symlink to a missing applet; temporary official
  coreutils-timeout fixed helper. Stale owned ARP after first cleanup was checked
  by MAC/IP/interface and removed before retest; final ARP cleanup done.
- Standalone policy `ucode -c` is invalid for module exports; native import worked.
  Generated runtime wrapper needs command dns-ready. Portable Git lacked sleep/
  stat; shell process test corrected to available tail, mode600 asserted on Linux.

Root integrated/published; ui_finish/native_device_checks completed. Recheck
agent liveness on resume. Cancelled Auto archive stays local and never installed.

## Current requested changes (2026-10-04)

Owner explicitly cancelled Auto VPN. All three Auto agents stopped. Active
development restored to bca8f60; cancelled unfinished source saved only locally
at codex/auto-vpn-cancelled-20261004 /05e14d5 for recovery, never published or
installed. Do not resume that branch or add Auto to runtime/UI/packages.
No Auto changes ever reached the router. New task owns only existing WAN/VPN
release fixes. Root owns integration, docs, Git/publication and live testing;
recheck agent ownership before assigning UI/backend work.

**v0.1.0-preview.4 is published, verified and installed.**
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.4
Exact tag/build SHA **3e493716b564266c48af28b4310d2abc2783df7f**,
tree f899ad98288661cc6aafa2d59d92cc502da4431b, branch codex/preview.4-build.
Do not move frozen refs or trigger duplicate builds.

All eight public files verified by API sizes/digests and full downloads:
python .work/preview.4/verify-public-release.py PASS.
Ignored provenance records verified/published/public_download_verified=true.
GitHub Assets10 means eight files plus two source archives. First publication
lacked Android because reload interrupted upload. Failed placeholder removed,
same verified APK reuploaded and saved. Require data-state=uploaded, not just
filename rows. No package bytes or frozen tag changed.

Signed upgrade completed exit0; csqtt/csqtt-captcha/luci-app-csqtt all0.1.0-r4.
All four configs (csqtt/dhcp/firewall/network) compared unchanged.
Private backup /etc/csqtt/backups/preview4-upgrade-20261004-092016-21289.
At upgrade groups1/devices3/rules4, connected72 and all diagnostics green.
Owner has since removed one device: current groups1/devices2/rules4,
six links/72workers, management known and unassigned. Preserve current values.
Latest owner report: no Internet outages yet; daily cure still needs observation.

**Real INPUT-only allocation recovery PASS exit0 in143s.**
Private persistent result /etc/csqtt/backups/preview4-proof-cNDeLF/result.log;
safe local copy .work/preview.4/fault-result-input.txt.
Selected old UDP socket closed after133s with exactly one new typed
PEER_LIVENESS_TIMEOUT; all71other baseline socket inodes survived every poll.
421 inbound ChannelData packets dropped; STUN sent5/received5.
No new local send error or TURN control timeout; all72workers restored at the
first recovery sample (5s polling). Client PID/startticks unchanged.
VPN-bound ping passed, all four configs/UCI unchanged, temporary nft table gone.
Private config backup /etc/csqtt/backups/liveness-fault-IAMjHf stays on router.
This proves single-allocation recovery, not absence of every later outage.

Readonly post-check repeated after fault cleanup PASS:
ten installed core/broker/runtime/manage/policy/fiveUI hashes match signed r4;
connected72/noerror; local and group DNS example.com; WAN/VPN HTTPS IPv4,
VPN exit differs from WAN. Safe result .work/preview.4/post-check-result.txt.
Actual LuCI overview confirms connected72 and policy protection active.
README/USAGE/BUILD now use preview4 and describe the real recovery proof.

Ignored helpers in .work/preview.4:
upgrade-router.sh, router-liveness-fault.sh, run-router-fault.sh,
router-post-check.sh. Native router sh-n/nft-c and independent review passed.
Fault helper targets only INPUT ChannelData on one unique owned UDP port,
preserves STUN/output, checks71other sockets, exactly one timeout, no new send
error, duration>=120s, recovery<=30s, overall<=285s and trap cleanup.
Result wrapper creates a private persistent log across tool interruptions.
No fault process/table is left. Never export private configuration/raw logs.

Test failures preserved for continuation:
- Earlier foreground result lost across interruption; /tmp helpers disappeared.
  No complete proof from that attempt, and no process/table remained.
- Outbound DROP test closed socket in5s without peer timeout: existing TURN UDP
  send failure/retry. Exit1/elapsed45s, all config/process/cleanup checks passed.
  Result /etc/csqtt/backups/preview4-proof-igCeDM/result.log. INPUT-only test above
  corrects the fault method; no production bug inferred from outbound DROP.
- Initial ignored post-check falsely reported zero matching hashes because its
  async watchdog lost pipeline stdin. Explicit savedFD3 fixed that helper.
  Installed files were unchanged; actual ten hashes and connectivity then pass.

The documentation checkpoint covers publication, signed upgrade and real
recovery proof. Verify local/remote alignment after push; use Git log for its
exact SHA. The continuation point is the first unfinished action above.

## Owner report and live state before r4

Oct4: VPN clients still lose Internet about twice/day. Router reboot does not
help; LuCI Reconnect helps. Owner answered: currently working, failure later.
SSH openwrt-router BatchMode+StrictHostKeyChecking succeeded, uid0.
GL-MT6000/OpenWrt25.12.5/mediatek-filogic/aarch64_cortex-a53/kernel6.12.94.
Explicit authorized scope: CSQTT install, debug and router/browser acceptance.
Tell owner before changes; preserve LAN management. Never print private values.

Before upgrade packages were r2 with tested local DNS/UI patches; now all3r4.
At upgrade sixVKlinks/72workers/groups1/devices3/rules4 were unchanged. Owner
has since changed devices to2; current management known+unassigned. Enabledtrue.
Do not restore earlier values.
Latest readonly samples: connected72, statusPID matches procd, age1–3s,
traffic grows, RSS13920KiB, DNS/policy/tunnel checks green, unreplied0,
TUNerrors/drops0 and no TURN/session fatal counters. Managementknowntrue,
management_unassigned=false. WANIPv6default absent. No outage captured today.
Helper .work/preview.2/router-triage-readonly.sh, deployed
/tmp/csqtt-triage-readonly.sh; values are fixed counts/booleans/enums.
Captures .work/preview.3/router-triage-20261004.txt and
.work/preview.4/before-upgrade-triage.txt. No broad live transport fault/reboot.

Private backups stay on router, never export:
- /etc/csqtt/backups/20260930-175413-32114 (original installation)
- /etc/csqtt/backups/preview2-upgrade-20260930-195841-17634
- /etc/csqtt/backups/dns-ready-fix-20261001-121411-11049
R4 wrapper will print its new private backup directory.

## New native liveness implementation and verification

Established TURN allocations previously counted as connected even if CSQTT
server replies stopped indefinitely. Existing reader could wait forever.
Pinned upstream expires authenticated sessions after10h idle; bare TURN0xff
keepalive bypasses CSQTT activity. Existing authenticated READY updates activity
and returns READY_OK without epoch/config changes. This is a plausible outage
path, not proof of the owner's exact failure or explanation of reboot behavior.

Source: vendor/csqtt/rust-client/liveness.rs, session.rs, main.rs.
Per-allocation pending ACK state; existing sole reader accepts exact authenticated
and replay-filtered READY_OK. Single-flight60s probes,5s send+reply deadline,
3consecutive misses -> typed PeerLivenessTimeout and normal allocation cleanup/
worker reconnect. Idle traffic still probed. Immediate reply/lost wake/cancellation
handled; child tasks aborted and awaited. No new wire message/crate/credentials,
external ICMP dependency or upstream server modification. Worker.rs unchanged.
READY has no per-probe nonce; do not claim stronger wire correlation.
Internet beyond the server remains separate.

Source checkpoint2cc5596b666d359568467f19ae97ae0f57566307 pushed.
Current development HEAD before publication checkpoint:
fee8079855189c989f51e3ba7d1cf1b592805699 (docs/native-success evidence).
Frozen focused run **37189418467 SUCCESS**, all4jobs:
checks111398302622, native-policy111398350556, core111398350565,
SDK111398669183. https://github.com/RATOR2000/csqtt-openwrt/actions/runs/37189418467
Fresh Rust focusedTURN1/1 and full353passed/0failed/7ignored.
All11paused-clock liveness and9session tests confirmed in authenticated logs:
silence, idle, successfulreset, immediate/late/unsolicited ACK, incarnation,
malformed/unrelated replies, stalledwriter deadline, cancellation, authenticated
Audio/Video ACK/replay/corruption/wrongkey and childtaskcleanup.
Independent read-only source/fault review and git diff--check PASS.
Local Cargo unavailable; native compilation/tests occurred in GitHub Actions.

Verified SDKartifact11298099574, ZIPSHA256
a6eaa11451916ca2b65a657114672aa51e1d83f8c12eb941417975347e13c0e4.
ReusedAndroid11297874928 ZIPSHA256
1a5d5bc761bfa57924b64ebfc9784ff0650e44afd04a9286818cb89d2485c968.
OriginalAndroid11117296798/run36757684228 byte equality, signing retained.
AndroidAPK SHA256c3cda9bbd2d7f614c7afa9225fdf72bcbad0055fa2d9b9cf9c2adcd23923babe.
Installer unchanged SHA256
1bf8b9270a973283e51ce21e10364fc1d6a3d1236ce9d69b625fdaf6f9caa9ad.
Actual signed ARM64core SHA256
6d7e18539226c175b91a4da0ff7beea2f081e16fcd0e111888ce9aeb2299ed28,
ELF64/AArch64/0755 and exact PEER_LIVENESS_TIMEOUT marker verified.
This proves compiled feature inclusion, not real router behavior alone.

.work/preview.4/provenance.json verified=true; publication flag set only after
python .work/preview.4/verify-public-release.py passes. All3APK+manifest pinned
signatures, exactr4metadata/checksums/frozenruntime/manage/policy/5minifiedJS/menu,
modes/license/defaultconfig/dependencies,16packagedLuCItests passed.
SDK ARM64startup/TUN, native ucode/DNS/nftables and isolated offline DNS rollback
passed. Workflow fresh core/native precede SDK; unchanged-source guards cover
broker/Android/installer; no stale r3 binary relabelled as4.
Preview3 tagcb6357832b079e3d159a1a7187d783be958b5c90/run36861604341 and all8
publicbytes verified; no r3 upgrade run. R4 directly replaces patchedr2.

## Earlier real acceptance and fixed failures

Real r1 install and signedr2 upgrade completed exit0 with config unchanged.
Real LuCI import/fullVKlinks SaveApply and actual VK connection passed.
Empty group select fixed: use modal option clone and plain string label.
vk.ru/m.vk.ru accepted; six separate full-link inputs preserve rawhash protocol.
Empty DynamicList add-input valid while final LAN scope must be nonempty.
Native runtime POSIX regex blockers fixed with explicit ASCII/length validation.
TCP/TLS UI now stores canonical tcp (native also understands tcp_tls).

Oct1 real DNS endurance reproduced Connectionrefused immediately afterapply,
despite directIP/VPNHTTPS/APKdownload passing and old dns-ready reportingtrue.
Fix waits for oldDNSPIDs to exit and requires currentPID-owned UDP+TCP listeners
for all exact active groupIDs on every LANIPv4 address. Missing/wrong/duplicateID,
wrongPID/UDPonly/loopbackonly staysguarded. No new runtime dependency.
Native router ucode/parser/fixture, manage sh-n and4POSIXrestart regressions PASS;
final Node policy/LuCI51/51 PASS. First native fixture adapter had forwardreference,
corrected before live deploy. Same real LAN endurance with no addedwarmup:
DNS12/12, directIPping12/12, VPNHTTPSexit differsWAN12/12, SHAverifiedHTTPS
APKdownload12/12 PASS in168s. Config unchanged and all ephemeral cleanup passed.
Temporary kmod-veth/coreutils-timeout removed exit0, no namespaces/addresses left.

Real IPv4 LAN acceptance onr2 passed VPNexit!=WAN, managed/localDNS, WANdomain
exception, failclosed fulltransportstop, localmanagement, recovery, fw4check/reload.
First stop assertion raced asynchronous procd termination; boundedstoppedwait
fixed test timing, secondfullrun PASS. No boot/crash/routedIPv6/manualCAPTCHA proof.
Owner's uncontrolled reboot+initialworkingVPN does not prove early-boot guards.

Installer architecture uses firmware+APKDB tunedarch, not generic print-arch.
OpenWrt signs repositoryindex, individualDNSAPK is unsigned. Installer trusts
signedindex, caches exactoriginalDNSversion, proves offline restore beforechange,
compares complete installedstate/world and preserves guard/config on rollback.
36local scenarios and nativeAPK3.0.5 signature/tamper/offline/exactrollback PASS
run36739033136. secret1 now valid; per-file APK signing uses freshprocess.
Do not repeat key setup or ask owner to expose key. Private credentials never
belong in source, fixtures, statusRPC, logs or public release.

## Repository, ownership and continuation

Repository https://github.com/RATOR2000/csqtt-openwrt; dev codex/csqtt-openwrt.
DraftPR1 attached, PR3 used CI; no merge into main merely to save progress.
Root owns live router, browser/publication, STATUS and checkpoints.
Agent preview3_verify completed r4artifact verification and ignoredpostchecker.
Agent transport_outage and childreview completed. Fresh preview4_docs completed
README/USAGE/BUILD updates; fault_review approved corrected INPUT/71inode proof.
Recheck collaboration.list_agents; do not assume past sessions remain alive.
All .work/ evidence/helpers are ignored; generated dist/build/private keys ignored.
Windows/PowerShell, Node/Python/portableGo present. No localRust/WSL/Docker.
Native Git sh available under cached runtime usr/bin/sh.exe; derive from git path.
Local git push lacks auth. Connector github_create_tree/create_commit/update_ref
works. scripts/export-github-tree.py exports committed delta to .work/publish-delta.
Compare remote/local tree before fetch+softalign. Use labelled [skip ci] checkpoint
commits and push dev, never move frozen release refs or claim checkpoints tested.

Stable release remains gated by outage observation, failed first activation boot,
manualAndroidCAPTCHA and remaining ACCEPTANCE scenarios. Real crash, normal early
boot and synthetic routedIPv6 TCP/UDP packet proof are now recorded above.
One active originalv2.1.9 tunnel; VPN traffic cannot fall back to WAN; explicitWAN
exceptions and LANmanagement retained. No project-wide stable readiness claim.
