# CSQTT OpenWrt implementation contract

Target: GL.iNet GL-MT6000, OpenWrt 25.12.5, mediatek/filogic,
aarch64_cortex-a53. One active tunnel. Upstream protocol is original
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
