# Development status — resume here

Updated 2026-10-04. Signed experimental **v0.1.0-preview.2 published**:
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.2
Tag is exact tested SHA9e95e812a05480ab458bad49a106cc3866eb2ebf. All eight
public asset downloads match verified local bytes; APK/manifest signatures and
packaged LuCI tests passed. Real VK/IPv4 LAN policy acceptance passed. Signed
upgrade to r2 succeeded with private configuration unchanged. Owner reports an
intermittent loss of VPN Internet on the phone. A real DNS restart readiness
race is fixed and passed live endurance; a signed preview3 build is next.
Read this, then IMPLEMENTATION.md. Files/Git/CI are
authority; historical component notes do not override this checkpoint.

## First unfinished action

**Current action: complete protocol-compatible READY/READY_OK liveness recovery,
run fresh native core tests and signed preview4 build, then verify/publish/upgrade
and test automatic recovery on the real router.**
Owner's Oct4 report: improvement, but VPN-classified devices still lose Internet
about twice/day; reboot does not help, LuCI Reconnect helps. Currently working.
SSH BatchMode/StrictHostKeyChecking succeeded, uid0, router uptime1h. Redacted
diagnostics connected72workers, DNS/policy/tunnel checks green. Current owner
config groups1/devices3/rules4 (not Oct1 values); management MAC is now assigned
to a VPN policy. Preserve LAN management and these settings, no blind restoration
or broad live transport fault. Readonly snapshot Oct4: process/status PID agree,
classification agrees with UCI, RSS13884KiB, traffic rose1267506988->1267928272,
unanswered2->0. Evidence ignored .work/preview.3/router-triage-20261004.txt.
Confirmed source gap: established TURN allocations count as connected while
CSQTT server replies can stop indefinitely. Upstream authenticated sessions have
10h idle expiry; existing TURN keepalive bypasses CSQTT obfuscation/activity.
READY is already authenticated/encrypted, updates upstream activity and returns
READY_OK without epoch/config mutation. This is a plausible delayed-outage path,
not proof of the owner's exact failure or explanation of the reboot observation.
Agent transport_outage owns session.rs/new liveness.rs/main.rs and async tests:
single reader, per-incarnation ACK state, single-flight probes every60s,5s bounded
send+reply deadline,3misses -> existing session cleanup and worker reconnect.
No new wire message, external ICMP service or credentials. Source DONE in3files;
11paused-clock asynchronous fake-peer tests, authenticated Audio/Video ACK/replay/
malformed-response regression and strengthened child-task drop/await test added.
Independent source review and diff--check PASS. Cargo unavailable locally;
compilation/tests/nativeCI remain pending. Source checkpoint
2cc5596b666d359568467f19ae97ae0f57566307 pushed. Frozen preview4 build
3e493716b564266c48af28b4310d2abc2783df7f, treef899ad98288661cc6aafa2d59d92cc502da4431b,
branchcodex/preview.4-build, focusedpush run37189418467 inprogress.
https://github.com/RATOR2000/csqtt-openwrt/actions/runs/37189418467
Do not trigger a duplicate or move frozen/published refs. Root owns docs/workflow/router/browser.
Preview4 workflow rootprepared: fresh checks/core/native-policy precede SDKr4;
unchanged broker/Android/installer source and originalAndroid artifact guarded.
Agent preview3_verify owns ignored preview4 verifiers, authenticated artifacts/logs
and readonlyworkflow review. Agent transport_outage completed source and now
prepares ignored one-allocation ChannelData fault script; no live writes. Root
must review before running on verified r4, preserve LAN and remove own temporary
table on every exit. Require same process PID, oldsocket gone, typedtimeout,
STUNcontrol stillpassed, restored workers and VPN ping, configUNCHANGED.
Recheck liveness before delegation; prior agents ended at quota or are gone.
Preview3 focused run36861604341 finished SUCCESS(all3jobs) at exact frozenSHA
cb6357832b079e3d159a1a7187d783be958b5c90. A newer fullCI36864359516 is also
successful at that SHA(PR3 trigger), but select the focused artifact identity.
SDKartifact11163088247 ZIPsha256c19313bfdf3554c0cdabf96d624cdd1da2135b8b90645f0caf82b4d74e4eeeec;
reusedAndroid11161509092 ZIPsha2568cd6a00bc593356852881cfad45f4f7ff42dda86201e9eb050a4078f072164f6.
Ignored .work/preview.3/provenance.json verified=true/published=false and8assets
staged: exacttree/source/runtime/manage/policy/all5minifiedJS/modes/license/deps,
pinned3APK+manifest signatures/checksums, originalAndroid byte equality,
unchangedinstaller1bf8...,16/16packagedLuCI PASS. Initial verifier reporter
mismatch fixed with explicit TAP/UTF8; final check used fresh staging. Root is
published exact frozenSHA/8assets as experimental preview3 at
https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.3.
Public verifier first stopped only because GitHub body uses CRLF; normalized
newline text matches exactly. Public verifier PASS: exact tag/flags/description,
all8API sizes/digests and all8public downloads; provenance published=true and
public_download_verified=true. No signedr3 upgrade was performed.
Signedr3 upgrade not run; prioritize the forthcoming r4 recovery upgrade.
Continue investigating the later outage; do not claim it cured.
Owner rebooted router before today's work, then created VPN group, assigned
phone and two WAN site exceptions. Internet/VPN worked initially then failed;
WAN exceptions seemed to keep working. Do not restart before capturing evidence.
Owner answered: phone currently works, outage recurs later. Preserve
current owner configuration (six VK links,72workers,one device,two rules);
do not restore yesterday's values. SSH management known and unassigned.

Signed upgrade `sh /tmp/csqtt-preview2-upgrade.sh` finished exit0 yesterday.
Installed csqtt/csqtt-captcha/luci-app-csqtt all0.1.0-r2. Private backup
/etc/csqtt/backups/preview2-upgrade-20260930-195841-17634. Wrapper compared csqtt,
DHCP and firewall config with before copies: allUNCHANGED. Installed runtime
and three minified JS SHA256 match provenance payloads. Verified installer
SHA2561bf8b9270a973283e51ce21e10364fc1d6a3d1236ce9d69b625fdaf6f9caa9ad.
Wrapper is ignored .work/preview.2/upgrade-router.sh; config copies stay in
/etc/csqtt/backups/preview2-upgrade-*/ (mode0700), never export them. No pending
UCI changes before start. Prior state connected9workers/groups1/devices3.
Public verification by runtime_release_plan passed: exact tag, prerelease,
eight asset names/sizes/API digests/download hashes. Provenance in ignored
.work/preview.2/provenance.json has verified/published/public_download_verified
true. Today browser confirmed six separate full-link inputs, all valid and
filled; Add Device modal shows groupdisplayname main_vpn. Reload discarded our
empty test row, no saved device/rule changes. Today routerboundping3/3,
VPNHTTPSexit differsWAN, localDNS and groupDNS5400 example.com/www.iana.org pass.
Table202defaultcsqtt0metric10+unreachable, mark/source routes-to-TUN intact.
TUNerrors/drops0, RSS12MiB, memoryavailable824MiB, conntrack232/limitchecked.
Readonly three samples4s apart: updated_atage1-2s, connected72, no sessionends,
TURNtransactiontimeout/fulloutage/TUNreadwriteerrors; no phone traffic during
8s observed idle. These probes do not establish the phone is healthy.
Ignored .work/preview.2/router-triage-readonly.sh uploaded to
/tmp/csqtt-triage-readonly.sh; captures safe fixedlabels/counts only, no
credentials/rawlogs/MACs/IPs. Captured .work/preview.2/triage-20261001.txt.
Extended readonly helper ran on actualrouter: phoneMAC/currentARP/DHCP and
installedpolicy/nftclassification allagree; oneVPNdevice,twoWANrules, IPv4
conntrack32-45, unanswered0, TCPestablished12. Phonetraffic nowpassedseveralMiB.
No source of the later intermittent outage confirmed. Root installed matching
official kmod-veth6.12.94-r1 and coreutils-timeout temporarily for current-group
ephemeralLAN endurance. Both test packages and their markers are now removed;
`sh /tmp/csqtt-veth-test-package.sh remove` finished exit0. Scripts do not
restart transport. Owner groups1/devices1/rules2 and configuration preserved.
First actual endurance sample after apply failedDNS: nslookup returned
Connectionrefused/timedout, while directIPping/VPNHTTPS/verifiedAPKdownload
allpassed. Readonlycapture kept group_dns_ready=true. Cleanup removed temporary
device/netns/address, ownerclientsettingsUNCHANGED, groups1/devices1 restored.
Evidence private /tmp/csqtt-lan-endurance.hIHNLm; only synthetic public probe
destinations in dns-1.log. This proves DNS restart readiness gap; link to owner's
later outage not yet established. Agent dns_recovery completed manage/runtime.uc
and readiness tests: snapshot old DNS PIDs and wait for full stop before replacing
configuration; require exact active group IDs and UDP plus TCP listening sockets
owned by the current process on every LAN IPv4 address before releasing guard.
Missing processes/sockets/IDs keep clients guarded. No added runtime dependency.
Four POSIX shell restart regressions and final Node policy/LuCI51/51 PASS.
Native ucode fixture/parser and manage shell parser passed on the actual router.
The initial native test adapter failed at a forward reference; adapter corrected,
full native fixture then passed before applying production changes.
Root atomically deployed reviewed runtime/manage/settings after private backup
/etc/csqtt/backups/dns-ready-fix-20261001-121411-11049. Config compared UNCHANGED.
Installed packages are still r2 WITH TEST PATCHES; proper signed r3 is pending.
Same ephemeralLAN endurance, with no warmup added: DNS12/12, directIPping12/12,
VPNHTTPS exit different from WAN12/12, SHA-verified HTTPS APKdownload12/12 PASS,
elapsed168s. First post-apply DNS refusal did not recur. Trap cleanup confirmed
test device/namespace/address removed and owner clientsettings UNCHANGED.
Actual diagnostics now checks owned DNS listeners; connected72workers,
policiesactive true/noerror, DNS/tunnel/policy checks green after cleanup.
Two earlier endurancepreflightfailures (missingtimeout, thenod) changed no
policies. Root installed officialcoreutils-timeout temporarily; marker
/tmp/csqtt-endurance-added-timeout. MACgeneration corrected usingPID+collision
checks. Testpackages and ephemeral state have been removed as recorded above.
Agent r2_acceptance completed settings.js/TCP regressiontest: confirmed UIemits
tcp_tls but runtimeallowsudp/tcp; nativeclient accepts both aliases asTCP/TLS.
Fix canonicalUIvalue tcp DONE in source, regressionfailedbefore with InvalidTURN
transport, afterfix Nodepolicy/LuCI45/45passed, final51/51 PASS. CurrentUDP setting
unchanged. TCP source/evidence checkpoint8cb0accd3b4b3d193e6c888672556f3424f4fb6b
pushed. Reviewed preview-build.yml now targets only codex/preview.3-build, package
revision3, with checks -> fresh native-policy -> SDK. It authenticates prior
successful core/Android checks and artifact11117296798; unchanged-source guards
avoid rebuilding those components while allowing new DNS/native tests.
Local YAML, nine embedded shell blocks and embedded JS/Python syntax PASS;
native dependency/build steps match the proven pinned reusable CI workflow.
DNS source/live-proof checkpoint3e81099f240f0f1a747d849fb2c3cdc57b319304 pushed.
Frozen non-skip build cb6357832b079e3d159a1a7187d783be958b5c90, common tree
95f53ddd991355e75ee831c5b1e3a99784e4f253, branch codex/preview.3-build.
Run36861604341: checks110366899078 SUCCESS; native-policy110366961970 SUCCESS;
SDK110367350959 in progress at Native OpenWrt packages. Do not duplicate builds
or move preview2 refs. https://github.com/RATOR2000/csqtt-openwrt/actions/runs/36861604341
Agent preview3_build prepared ignored .work/preview.3 verifiers/config and owns
artifact verification once metadata is available. Root owns publication/live.
Agent outage_audit performs narrow read-only delayed-outage source review;
no source/router writes. Recheck liveness before delegation.
Crash/boot planning stopped in favour of reported outage; controlled reboot,
crash and real routedIPv6/manualCAPTCHA acceptance remain unverified. Owner's
reboot+initialworkingVPN is an observation, not controlled early-boot leak proof.
Historical notes below are superseded here.

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

**First unfinished action: verify/publish signed preview2 assets, then upgrade the
router through its installer and confirm saved settings and traffic.** SDK build
36763376001 SUCCESS at exactSHA9e95e812a05480ab458bad49a106cc3866eb2ebf;
checks110051305537 and SDK110051407012 success. runtime_release_plan owns ignored
artifact download/verification and preparation; root owns publication/router/docs.
Recheck liveness. Real IPv4 LAN acceptance completed below. Root has authorized
LuCI browser2/tab2 at http://192.168.1.1; user
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
to existing groupdisplayname main / IDcfg0246f2; UI Save/Apply succeeded. Root
then tested that same MAC as an ephemeral veth LAN client, benchmark198.19.0.2/30,
secondarybridge198.19.0.1/30, isolated temporary VPN group and domainWANrule.
**Real packet checks PASS**: managedDNS+router access; namespace HTTPS VPN exit
differsWAN; domainapi.ipify.org exception usesWAN; after transport fully stops,
previously successful directIPping1.1.1.1 blocked, while WANexception and router
remain available; afterrestart directIPping and VPNHTTPS recover. Scriptexit0,
trap cleanup PASS. First run failed at an overly immediate stopped-state assertion
because procd termination is asynchronous; cleanup restored connection. Added
wait for runningfalse+TUNremoved within20s, second run all checks PASS. This was
a test timing error, not evidence of a transport stop failure. Script ignored at
.work/preview.2/router-policy-test.sh; first failure private logs retained at
/tmp/csqtt-router-probe.NlppNf, do not print rawlogs. `fw4 check`+`fw4 reload` also
passed with VPNHTTPS/groupDNS/localDNS intact. No real boot/crash/manualCAPTCHA
or routedIPv6 acceptance: WANIPv6default absent; prior native tests remain separate.
All temporary namespaces/veth/subnet/group/rule/resolver removed; dummyUCIdevice
cfg030f15 removed and manageapply passed; added kmod-veth purged. Owner added three
real devices to main during tests, final groups1/devices3/policiesactive true,
connected9workers/noerror, groupDNS/localDNShealthy. SSH management MAC checked
known+unassigned before tests; do not assign it blindly. preview_review completed
test script/review; root executed and fixed procd timing. No live agent writes.
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
passed. Updated source checkpoint **f8bc6c865efdcbd96c99e1742f4bbc2fa65a19a4**,
tree **33e0fe6c32541f2f0a9a7f6a00dfc74839e3dbe0**, pushed/local aligned.
Focused buildSHA **9e95e812a05480ab458bad49a106cc3866eb2ebf**, same tree;
run **36763376001 SUCCESS**, checks110051305537 and SDK110051407012 SUCCESS.
Freeze exact testedSHA for preview2; no extra
workflow dispatch. Root installed official **kmod-veth6.12.94-r1** on matching
kernel6.12.94 for ephemeral virtualLAN test; package subsequently purged and all
test interfaces/subnet/group/device removed after passing acceptance.
Ignored .work/preview.2/ci-status.py BUILD_SHA writesci.json and
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
