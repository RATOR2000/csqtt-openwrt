# LuCI implementation checkpoint

Updated: 2026-09-30. Source implementation and simulated Node checks are complete.
The interface has not been exercised on OpenWrt or built as an SDK package here.

## Ownership and files

- Agent `luci_finish` owns `openwrt/luci-app-csqtt/` and `tests/luci/` in this
  development turn. Root handles commits, pushes and integration. Recheck agent
  liveness before delegating future changes.
- Four Russian views: overview, connection settings, device/group policies and
  diagnostics. Menu paths resolve to existing views.
- Scoped rpcd object: status, start, stop, restart, apply, diagnostics, devices,
  captcha_begin, captcha_cancel. Commands are fixed; no shell arguments or
  command execution endpoint can be supplied by the caller.
- ACL reads/writes only UCI package `csqtt`; read methods cannot create CAPTCHA
  pairing grants. No file or generic execution permissions are requested.

## Implemented behavior

- Settings support CSQTT v2 link import, explicit port normalization, 1–6 unique
  VK hashes/full links, worker capacity validation, video/UDP defaults and
  supported advanced transport/auth/DNS/LAN/CAPTCHA fields.
- Password validation follows core limits: 4–128 UTF-8 bytes, no control
  characters or `|`; spaces are allowed. Hashes are 16–1024 ASCII letters,
  digits, underscore or hyphen. Import failures never echo the source URL.
- Named groups, MAC assignment with discovered-device suggestions, duplicate
  device rejection, guarded group removal and sortable domain/IPv4/CIDR rules.
- Standard LuCI Save & Apply uses UCI and the backend procd reload trigger.
  Diagnostics offers explicit reapplication of already saved policies.
- CAPTCHA pair/cancel use fixed broker CLI operations. The helper URI appears
  only after the user's pairing action in a private modal. Its scheme, fields,
  challenge ID and expiry are checked. Hide, expiry, challenge change, service
  actions and status failure wipe the visible value and link target.
- Diagnostics exports only allowlisted component facts with local static
  explanations, never backend raw logs, arbitrary details or configuration.
- All untrusted device/group/status text uses LuCI text-array children or DOM
  nodes. This matters because LuCI treats scalar string children as HTML.

## Checks actually run

`node --test tests/luci/luci.test.cjs` — 9 tests passed, 0 failed after final
edits. Tests cover import compatibility/error redaction; core settings limits;
deep-link validation; user-action-only CAPTCHA disclosure and stale challenge
wiping; diagnostics redaction; settings save rejection; device membership,
rule sorting and group deletion; menu resolution, JS parsing and narrow RPC
dispatch/ACL. The DOM stub detects untrusted scalar HTML children.

`git diff --check` — exit 0. An unrelated Rust file had a CRLF normalization
warning, with no whitespace errors reported.

## Remaining integration and next steps

1. Build the LuCI/OpenWrt package in CI using the pinned SDK.
2. In an actual LuCI browser session, verify GridSection add/edit/remove,
   updated group choices, drag/arrow rule order, Save & Apply and default theme
   layout on desktop/mobile. Node stubs do not prove real LuCI widget behavior.
3. Verify rpcd ACL behavior with read-only and write-capable sessions; check
   backend service controls and diagnostic statuses on the target router.
4. Test manual CAPTCHA on a real Android helper and VK challenge, including
   clipboard fallback, cancellation, expiry, stale answer and route changes.
5. Run the broader DNS, IPv6, policy failure and mixed-client acceptance tests
   recorded in `IMPLEMENTATION.md`. UI assertions are not dataplane proof.

No live router was contacted, no real VK credentials were used, and no stable
or installable release is claimed by this checkpoint.
