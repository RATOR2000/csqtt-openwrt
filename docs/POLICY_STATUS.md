# OpenWrt policy/backend checkpoint

Updated: 2026-09-30. Owner for this session: `backend_validate`.
Source implementation and host checks passed. Pinned native ucode, generated
nft/DNS/model comparisons, dnsmasq syntax and initial namespace traffic passed
in Linux CI at `d10c559`; complete traffic, OpenWrt integration and real router
behavior remain unverified. Root owns commits, CI and SDK packaging.

## Completed source and review

- Ucode validates ordered group/domain/IPv4 rules, unicast membership and
  resource limits; normalizes CIDR host bits before nft emission.
- Separate per-group dnsmasq contexts use nftsets, preserve domain sets across
  policy reload, populate matching ancestor sets, and respect the first matching
  domain rule for resolver selection. VPN DNS has a dedicated source address,
  policy route and output guard; no resolver WAN fallback is configured.
- Persistent nft forward guards plus unreachable IPv4 policy routes retain the
  block through transport stop/crash. Group IPv6 can leave through configured LAN
  devices only; broad ULA/multicast exemptions were removed. Router input and LAN
  egress remain available.
- `manage` compiles private staging files, installs a persistent maintenance
  guard for old/proposed clients, validates DNS/nft, updates fw4 includes,
  waits for procd DNS instances and flushes known client conntrack flows before
  releasing the maintenance guard. It detects reserved routing-rule/table and
  firewall-section collisions and active pbr/mwan services.
- Bounded final review found no additional forwarding escape: independent
  forward/output guards cover route loss; stop/crash keeps unreachable routes;
  MAC/port checks block obsolete DNS DNAT after group assignments change.
  Flow offloading is disabled while policies are active and previous options
  are restored on deactivation unless an administrator changed them later.
- Runtime client JSON now matches the original core's fields and worker
  capacity: 9..126 in multiples of nine, at most 27 per hash and six distinct
  hashes. `captcha_mode`/`mtu` are omitted because core rejects unknown fields.
- Missing/null status JSON now uses safe defaults; status exposes an explicit
  allowlist and excludes passwords, hashes, private CAPTCHA fields and device
  identity. Hook action is argv (`up`/`down`) with `CSQTT_TUN_DEVICE`.
- `tests/policy/native.uc` runs production compiler assertions on native ucode
  and writes native nft/DNS/model outputs. `render.mjs OUTPUT_DIRECTORY` writes
  production compiler output through the Node compatibility harness.
- Native traffic smoke source now distinguishes WAN, simulated csqtt0 and local
  replies, exercises tunnel route up/down and complete policy-rule loss, checks
  guarded router source routing, local IPv4/IPv6 access, routed ULA blocking,
  learned domain-set persistence and unassigned clients. Server startup is
  synchronized and ARP/NDP state is flushed after a fixture MAC changes.
  Namespaces have per-process names and all links are created inside them.

## Exact host checks

- Initial `node --test tests/policy/*.test.mjs`: 16/17 passed; status failed on
  `JSON.parse(null)` bypassing the fallback. Fixed in `runtime.uc`.
- Latest `node --test tests/policy/*.test.mjs`: **22/22 passed**.
- `node tests/policy/render.mjs .work/policy-render`: passed; generated ignored
  nft, DNS and model files, with no credentials in the fixture.
- Bundled Git `sh.exe -n` on `manage`, `tun-hook`, `csqtt.init`,
  `csqtt-dns.init`, `90-csqtt`: all passed.
- `git diff --check -- openwrt/csqtt tests/policy`: passed.
- First Linux CI native run reported ucode syntax errors at exported function
  boundaries (`Expecting ';'`). All three exports in `policy.uc` now end in `};`.
  After the fix, Node tests passed **22/22**, render CLI and scoped whitespace
  checks passed. The Linux run at `d10c559` subsequently passed native ucode
  assertions, nft/DNS/model comparisons and dnsmasq syntax validation.
- `python -m py_compile tests/policy/network-smoke.py`: passed. Actual smoke
  traffic uses a veth simulation, without CSQTT transport or VK connectivity.
- At `d10c559`, nft installed and initial WAN, blocked and local traffic checks
  passed. Healthy csqtt0 failed because the wildcard echo socket replied from
  its interface address, breaking the expected reverse NAT tuple. The fixture
  now binds every destination address and uses connected UDP clients to require
  exact reply sources. A host UDP probe confirmed wildcard/exact-bind source
  behavior; latest Python syntax and scoped whitespace checks passed. Complete
  Linux traffic rerun is pending. Failure-only namespace diagnostics were added.

## Next concrete checks

1. Root reruns the corrected native namespace smoke in Linux CI. Complete the
   healthy csqtt0, down/routing-loss, reload and IPv6 traffic checks before
   claiming the full native suite passed.
2. Build packages through the pinned 25.12.5 SDK and confirm installed fw4,
   procd, UCI and dnsmasq integration on the exact target.
3. Real GL-MT6000 acceptance still needs server/VK details from the user: mixed
   clients, DNS/IPv6, crash/boot/reload, existing flows and explicit WAN exceptions.
   No live router or VK tests were run in this session.

Known limits: DNS caches/shared IPs/DoH affect hostname classification. Domain
sets intentionally survive reload; obsolete unreferenced sets/chains are not
garbage-collected yet, so long-running frequent rule edits can accumulate them.
