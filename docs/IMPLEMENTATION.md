# CSQTT OpenWrt implementation contract

Current native reference: GL.iNet GL-MT6000, OpenWrt 25.12.5,
mediatek/filogic, aarch64_cortex-a53. Current delivery scope (user replacement
plan2026-10-22) is official24.10/25.12 ARM64/x86_64, later ARMv7. The GLvendor
firmware plan was cancelled; its experiments remain checkpointed. Qualification
is per verified ABI/firmware/capability profile, without a board allowlist or an
unconditional all-routers claim. Owner's current fresh reference is25.12.6.
One active tunnel. Upstream protocol is original
amurcanov/csqtt v2.1.9 at 446293aa2e873ac5323ef6fd2316d9b81d966c11.
Android deployment and upstream server stay compatible and unchanged.

## Components and shared interfaces

- `vendor/csqtt/rust-client`: upstream Rust transport with native Linux TUN,
  JSON configuration file input, graceful SIGTERM, JSON status, and a local
  control socket. Preserve upstream protocol and license notices.
- `openwrt/csqtt`: package, procd service, UCI config, netifd/firewall integration,
  per-device policy compiler and guarded DNS.
- `openwrt/luci-app-csqtt`: Russian LuCI JavaScript UI, scoped rpcd ACL and RPC
  methods. No arbitrary command execution API.
- `android-helper`: separate Android CAPTCHA companion. Native auto attempts
  remain available. A manual challenge is paired through a one-use LAN token;
  the helper never receives the router administrator or VPN password.
- `scripts` and `.github/workflows`: pinned-source build, tests, SDK packaging,
  signed release assets and a one-command installer.

UCI package name `csqtt`: named `main` section of type `client`, sections of
type `group`, `device`, and `rule`. A group has name and default_action (`vpn`
or `wan`). A device has name, mac and group (section ID). A rule has group,
enabled, destination (domain, IPv4 or CIDR) and action (`vpn` or `wan`);
UCI order is priority. A device belongs to one saved group. Its optional enabled
flag defaults to active when absent; enabled=0 retains the saved row/group/MAC
but removes the device from active policy membership, DNS redirects and IPv6
guards. It uses the ordinary unassigned WAN route. Devices RPC group and status
device counts describe active assignments. Disabling/re-enabling flushes affected
old/new client conntracks through the existing guarded apply transaction.
Unassigned devices use WAN. Auto VPN was explicitly cancelled and is out of scope.
LuCI Save & Apply applies policies without restarting a running transport when
the effective client.json is unchanged. The init reload compares a private
snapshot after a successful guarded apply; changed or absent transport restarts
from that prepared config. Failed apply preserves the process and its guards.
Domains match themselves and subdomains. LAN scope is explicit (default br-lan).

RPC object `csqtt`: status, start, stop, restart, diagnostics, devices,
captcha_begin, captcha_cancel. Status redacts secrets. Configuration uses UCI.
Interface/TUN name `csqtt0`. Credentials and runtime config are mode 0600.
Runtime files `/var/run/csqtt/`; persistent device identity `/etc/csqtt/`.
Transport receives `/var/run/csqtt/client.json` via `--config-file`.

Established TURN allocations alone do not prove that the CSQTT server responds.
Each allocation sends the existing authenticated READY request every 60 seconds.
Its existing reader accepts exact, authenticated and unreplayed READY_OK replies.
One five-second deadline covers sending and receiving; three consecutive misses
end that allocation through normal cleanup and worker reconnection. Idle traffic
does not disable these probes. This preserves the upstream wire protocol and
requires no public ICMP endpoint. Authentication and configuration errors retain
their existing handling. Internet access beyond the server is a separate check.

## Reliability recovery (implementation candidate)

Manual CAPTCHA availability and explicit human takeover are distinct. Waiting
for a human releases the shared authentication network permit; each credential
cohort remains single-flight. An unclaimed challenge can be revoked after60s
to retry normal VK Calls authorization; explicit takeover retains the original
deadline. CAPTCHA cooldown does not suppress the unrelated normal Calls path.
Recovery and human takeover use atomic private, bounded admission leases.

Private core status includes process startticks/boot ID/boot-clock freshness;
public RPC exposes only allowlisted state/ages/counters. A monitor samples WAN
and guarded VPN DNS/HTTPS every30s without reserving a VPN runtime identity.
Public `health` and `recovery` are additive. Router-origin probes do not prove
the classification of every LAN device. Missing/old observations are unknown.

Source correction after preview.9: `/proc/uptime` truncates to centiseconds,
while core status and recovery leases use millisecond `CLOCK_BOOTTIME`. Parse
the uptime into an integer interval `[L, L+10)` milliseconds. A timestamp inside
that interval can be current; reject the next tick and malformed timestamps.
Use the exclusive upper bound for the 15s status and <85s lease age limits,
allowing expiry up to10ms early without extending either deadline. All process,
boot and human-epoch ownership checks remain mandatory. This correction is not
installed on the signed r9 router during its72h observation.

Automatic recovery is initially observe-only (`auto_recover=0`). Both fixed
VPN HTTPS targets must fail after successful bound DNS, with both matching WAN
controls reachable, continuously for180s. HTTP errors with verified TLS prove
reachability and do not cause a restart. Unknown, WAN failure, VPN success,
configuration/intent changes or active human takeover cancel the window.
One cycle first reapplies guarded routes/DNS without restarting transport,
then requires a new failed sample at least30s later before one transport restart.
Reserve a cycle before mutation, including failed attempts: at most3/rollinghour
and at least300s between starts, retained across monitor/client respawn this boot.
An internal recover never enables a manually stopped service. Serialize lifecycle
changes and exclude installation; prepared restarts must not recursively prepare
under the policy lock. Every failed operation retains fail-closed guards.
Take the lifecycle lock before rc.common's procd lock, including direct init
commands. Recheck intent/configuration/pending edits after asynchronous stop.
Each fixed recovery step runs in its own process group for at most70s, capped
by the remaining admission deadline; stop its descendants before ending the
lease. Process exits remain procd's responsibility; never fabricate a lease
from a missing or stale core. VPN probe sockets also bind explicitly to csqtt0.

Candidate code, CI, signed package, live controlled checks and72h observation
are separate gates. These paragraphs describe intended candidate behavior,
not completed live acceptance. No router reboot or automatic WAN fallback.

## Routing invariants

Preserve router/LAN access. For managed internet traffic, ordered group rules
precede group default. VPN-classified traffic may only leave csqtt0; an
unreachable route remains when the tunnel is down. Explicit WAN exceptions
continue to work. Guards survive transport stop, crash, boot and fw4 reload.
Do not use a global VPN default route. Router-origin VK/TURN traffic uses WAN.
Masquerade forwarded LAN traffic to the assigned tunnel IPv4.

Use fw4/nftables plus policy routing. Own all CSQTT rules under a dedicated
prefix; do not overwrite unrelated configuration. Reject incompatible active
pbr/mwan configurations before activation. Disable flow offloading while
managed policies are active and restore the prior setting when deactivated.
IPv6 internet is blocked for groups that can select VPN; LAN IPv6 remains.
Domain classification uses router DNS and is subject to caches, shared IPs and
independent DoH. Do not claim arbitrary hostname-level fail-closed guarantees.
Use dnsmasq-full nftsets and separate managed DNS contexts; no public DNS WAN
fallback for VPN-default queries. Keep local names available. Preserve/reseed
domain sets across firewall reload; hold affected groups closed on failure.
During a policy transaction, the persistent maintenance guard also closes held
devices' TCP/UDP DNS input on port 53 and group ports 5400–5415. This prevents
first-activation or old-resolver WAN recursion before replacement DNS is ready.
DNS, including local names, pauses until the atomic release after readiness;
LAN management by IP and unassigned/router-origin DNS remain available. Normal
active-policy local DNS remains available when the VPN transport is stopped.

## Delivery and acceptance

### Portable platform contract (replaced2026-10-22)

Provide one installer with a read-only compatibility mode. Select signed exact
platform manifests through an authenticated catalogue; retain schema1 verification
for immutable prior releases. Separate opkg/IPK and APK transaction backends and
SDK profiles. Before mutation, prove compatible kernel dependencies, authenticated
complete downloads, adequate storage/staging RAM and offline package/config
rollback. Never force dependency/architecture/kernel mismatch or unsigned trust.
Unknown versions preserve settings and refuse unsafe activation. A compiled or
emulated target is not native device qualification. Public diagnostic additions
must preserve existing RPC fields and secret redaction.

Official OpenWrt retains fw4/nft semantics below. Private DNS must retain stock
DHCP/DNS, local names and equivalent guarded routing; offloading must be disabled
while active and restored after safe deactivation. Preserve LAN, explicit WAN
exceptions, IPv6 restrictions, boot and reload guards. The Helper follows
configured LAN scope, not logical-name 'lan'. GLlegacy/private-runtime experiments
are excluded from current release/build qualification, preserved in history.

New-install resource profiles require measured RAM/load evidence, valid worker
cohorts (minimum9, multiples9, credential-dependent limits) and manual override.
Existing explicit parameters survive upgrade/reinstall unchanged. Do not invent
hardware minimums or reduce security to fit a device. A Russian LuCI first-run
wizard collects existing connection fields, selects devices and checks public
VPN health only after explicit activation. New installs remain disabled until
completion; configured upgrades bypass the wizard, even when manually stopped.
No scheduled Codex jobs. Owner installs the published preview personally; no
remote mutation is authorized. Current SSH alias `router` permits agreed reads.
See PORTABILITY.md and docs/evidence for source/build/native gate distinctions.

One README command must work on a clean supported image: authenticated bootstrap
of verifier/tools, full signed dependency resolution (including exact-kernel TUN),
staged downloads and solver proof, persistent transaction journal/offline rollback,
and schema1r9 upgrade migration. Never require the user to preinstall tools or
replace DNS manually. Package install success means software installed; actual
VPN success is reported separately by the wizard. Publish only after native
clean-OpenWrt installation and guarded-routing proofs are bound to the release.
VM/ABI preview qualification is distinct from physical-device/VK acceptance.

### Existing reference release

New public repository `csqtt-openwrt`. Do not publish untested binaries as a
stable release. Support the exact router target first. Build through the
25.12.5 SDK; dependencies and kmod-tun come from compatible official feeds.
Installer checks target, release, signatures and space before changing state,
backs up settings, preserves secrets, and supports repeat install/upgrade.

Test mixed WAN/VPN clients; rule ordering; DNS and IPv6; boot/crash/reload;
existing flows during policy changes; malformed config; secret redaction;
CAPTCHA expiry/cancel/stale answers; installer mismatch and interrupted install.
End-to-end TURN and cross-device CAPTCHA require an actual server and live VK
challenge. Report these as unverified until tested, never simulate success.
