# OpenWrt policy/backend checkpoint

Updated: 2026-09-30. Owner for this session: `runtime_acceptance` (completed;
root owns publish/CI and the current DNS fixture).
Source implementation and host checks passed. The full native policy traffic
suite passed in Linux CI run `36677864570` at `d7627c3`, including pinned ucode,
generated nft/DNS/model comparisons, actual IPv4 group DNS resolution/set
insertion, dnsmasq syntax and routing checks. New IPv6 DNS transport cases,
OpenWrt integration and real router behavior remain unverified.
Root owns commits, CI and SDK packaging.

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
- First activation now commits the saved maintenance guard's fw4 include
  before nft validation. Previously a failed first transaction could leave a
  live hold with no persistent include, so reboot reopened proposed clients
  before the client service prepared policy. The new hold-only runtime mode
  requires no complete policy files and keeps local-access exemptions. The
  focused shell command-double test fails nft validation and confirms that
  both the saved hold and its firewall include survive the failure. Actual
  OpenWrt reboot/reload behavior remains unverified.
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
- New `dns-smoke.py` runs actual generated group dnsmasq configs inside the
  existing test namespaces. Synthetic exact-source upstreams exist on WAN and
  VPN paths, so unavailable endpoints cannot hide unintended WAN fallback.
  Unique real port-53 queries check defaults/exceptions, local names, parent/
  child nftset insertion and resolver behavior through tunnel route up/down.
  Test PID/config files stay in the runner's temporary output directory.
- IPv6 DNS transport follow-up queries both `[fd00:1::1]:53` (LAN router) and
  `[2001:db8:2::2]:53` (redirected isolated external DNS fixture) from managed
  clients a/b. A-record answers still use the configured guarded IPv4
  upstreams. Cases cover default/exception routing, local names and simulated
  tunnel up/down; unique names prevent cached successes. Native CI is pending
  for these new queries; no AAAA-answer behavior is claimed.
- Pinned dnsmasq 2.93 source review confirmed that `domain-needed` rejects plain
  local names and rebind checks strip private local answers from 127.0.0.1.
  Compiler removes that option and adds rebind exceptions only for plain/local
  names; internet rules under the configured local suffix are rejected so they
  cannot replace local delegation. Native DNS rerun must verify this behavior.
  Review used the [official source archive](https://thekelleys.org.uk/dnsmasq/dnsmasq-2.93.tar.xz)
  with the same SHA256 pinned by CI.

## Exact host checks

- Runtime acceptance follow-up: `node --test tests/policy/runtime.test.mjs`
  passed **14/14**; `node --test tests/policy/*.test.mjs` passed **26/26**.
  The two new regressions cover the hold-only include, ownership collision,
  offload/deactivation behavior and failed first-apply persistence. Bundled
  Git `usr/bin/sh.exe -n openwrt/csqtt/files/manage` and scoped
  `git diff --check` passed. Initial harness runs failed because the bundled
  shell has a portable path and no chmod executable; shell discovery and the
  command doubles were corrected. These are host simulations, not native
  fw4/procd/router tests.
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
  Linux traffic rerun subsequently passed at `88d8189`. Failure-only namespace
  diagnostics were added.
- CI `36638972094` at `88d8189`: **native policy job passed**, including healthy
  simulated csqtt0, down/routing-loss, guarded-source, learned-set reload,
  maintenance/local access, IPv6/ULA and unassigned-client traffic.
- After new DNS source/config changes: `node --test tests/policy/*.test.mjs`
  passed **24/24** (includes root's safe local-domain status test);
  `node tests/policy/render.mjs .work/policy-render` and scoped
  `git diff --check` passed. Python syntax passed for `dns-smoke.py` and
  `network-smoke.py`; an in-memory synthetic DNS A-response roundtrip and
  truncated-reply checks passed. Actual new resolver/set-insertion traffic
  remains pending the next Linux CI run.
- Root confirmed CI `36677864570` at `d7627c3` passed the native policy/DNS job,
  including actual group resolver selection, local private answers and nftset
  insertion. New IPv6 transport source passed
  `python -m py_compile tests/policy/dns-smoke.py`, scoped `git diff --check`
  and an in-memory DNS wire roundtrip for IPv4/IPv6 socket selection,
  connected port-53 destination and A-answer decoding. The new namespace
  IPv6 DNS cases require the next Linux CI run.

## Next concrete checks

1. Root reruns the native DNS job with the new IPv6 transport cases. Confirm
   LAN listeners, external-DNS redirection and local names through route loss;
   correct failures before claiming IPv6 DNS behavior is verified.
2. Build packages through the pinned 25.12.5 SDK and confirm installed fw4,
   procd, UCI and dnsmasq integration on the exact target.
3. Real GL-MT6000 acceptance still needs server/VK details from the user: mixed
   clients, DNS/IPv6, crash/boot/reload, existing flows and explicit WAN exceptions.
   No live router or VK tests were run in this session.

Known limits: DNS caches/shared IPs/DoH affect hostname classification. Domain
sets intentionally survive reload; obsolete unreferenced sets/chains are not
garbage-collected yet, so long-running frequent rule edits can accumulate them.
