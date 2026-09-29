# Development status — resume here

Updated: 2026-09-30. State: **implementation in progress; no installable release
has been verified**. Do not confuse source files with completed integration.

## User decisions (settled)

- Original amurcanov/csqtt Android app deploys the original server; retain that
  protocol and web administration. Server will be deployed later.
- Router: GL.iNet GL-MT6000, official OpenWrt 25.12.5
  r33051-f5dae5ece4, kernel 6.12.94, mediatek/filogic,
  aarch64_cortex-a53, about 1 GiB RAM and 6.3 GiB free overlay.
- Russian LuCI CSQTT tab; manual call hashes/links and necessary settings.
- One active VPN, named device groups; ordered domain/IP/CIDR exceptions in
  both directions. Unassigned devices use ordinary WAN.
- VPN-classified traffic is blocked on failure. Explicit direct exceptions
  remain direct. User accepts DNS-based domain classification limitations.
- Automatic CAPTCHA plus manual solution using a separate Android helper.
- Public repo and eventual one-command install. User wants concise updates,
  most effort spent on code, and durable resumption after usage-limit breaks.

## Repository and source

- GitHub: https://github.com/RATOR2000/csqtt-openwrt (created; connector has push).
- Local branch: `codex/csqtt-openwrt`; origin already configured/fetched.
- Remote initial main: `04ff32842b2ab26ea779ca10cd3caf44664d17bf`.
- At this checkpoint, initial implementation files were still untracked;
  root is about to adopt origin/main as parent and create/push a WIP checkpoint.
  Always inspect actual Git state instead of relying on this sentence.
- Vendored upstream tag v2.1.9, commit
  `446293aa2e873ac5323ef6fd2316d9b81d966c11`; pristine clone `.work/upstream`.
- SDK URL and SHA are pinned in `scripts/build-sdk.sh` and verified against the
  official 25.12.5 mediatek/filogic download listing.

## Implemented source so far

- Original Rust client/shared source with work on Linux TUN, JSON daemon
  config, private control socket/status, identity lifecycle, SIGTERM, native
  CAPTCHA and manual takeover. Core agent is finishing integration/tests.
- OpenWrt package/backend: ucode policy compiler, persistent fw4/nft guard,
  per-group dnsmasq configuration; shell/procd integration still being finished.
- LuCI Russian settings/status/groups/devices/rules/diagnostics and private
  CAPTCHA link dialog; UI tests/integration still being finished.
- `captcha-broker/`: Go TLS bridge, one-use pairing grants, current-challenge
  validation, private Unix control, restricted VK CONNECT relay, persistent
  certificate identity. Public HTTP status never contains credentials.
- `android-helper/`: separate Kotlin APK source, pairing validation and pinned
  TLS, WebView result interception, authenticated relay via loopback to router.
- GitHub CI for Go/Node/Rust/Android/SDK and SDK packaging scripts exist.
- Three packages planned: csqtt, luci-app-csqtt, csqtt-captcha.

## Verified, not assumed

- Go 1.26.8 portable archive SHA256 checked before extraction.
- `go test ./...` in captcha-broker passed (destination allowlist/SSRF,
  one-use grant, stale/expired session, result replay, TLS identity persistence).
- `go vet ./...` emitted no issues in the completed command sequence.
- ARM64 Linux broker binary exists in ignored `dist/csqtt-captcha` (~6.2 MB);
  verify ELF header/build command status before considering it release material.
- Rust compilation/tests, Android build, actual ucode/nft semantics and SDK
  packages have NOT yet been confirmed. Node policy/LuCI test results pending.
- No live router changes, no actual VPN connection, no live manual CAPTCHA test.

## Next actions (in order)

1. Finish durable Git checkpoint and push the development branch. Use connector
   Git tree/blob APIs if local Git credentials cannot push; do not expose tokens.
2. Check active agents before spawning replacements. Latest ownership:
   core_finish → vendor/csqtt; policy_finish → openwrt/csqtt + tests/policy;
   luci_finish → openwrt/luci-app-csqtt + tests/luci. Root owns broker, Android,
   build/release/installer and integration. Preserve their existing files.
3. Complete installer (install.sh absent at this checkpoint), release signing,
   README and build/release documentation. No stable release before CI checks.
4. Fix/check Android: replace InputStream.readNBytes with an API-28-compatible
   bounded read; review nullable relay sockets/lifecycle/manual retry, certificate
   failure handling and WebView lint. Build and test on GitHub Actions.
5. Run Node tests; run Go checks again only after relevant edits. Validate native
   ucode and nftables in Linux, not only the JavaScript compatibility harness.
6. Publish source to development branch, create/attach draft PR, read CI results,
   fix failures until Rust/Android/OpenWrt package builds pass.
7. Review cross-component config paths, status/error shapes, hook invocation,
   timestamps, DNS/routing behavior on crash/reload and installer failure handling.
8. Real acceptance requires a server deployed by the user and valid VK call
   hashes. Never publish those to Git. Verify mixed WAN/VPN devices, kill switch,
   DNS/IPv6 and manual CAPTCHA on GL-MT6000 before calling the release stable.

## Integration contracts

- See `docs/IMPLEMENTATION.md` for UCI and policy behavior.
- Core: --config-file /var/run/csqtt/client.json; control socket
  /var/run/csqtt/control.sock; Unix newline JSON command status, captcha_get,
  captcha_manual, captcha_result, captcha_cancel, stop. Mutation includes id;
  result includes token. Responses contain ok boolean. captcha_get exposes the
  private challenge id/state/redirect_uri/session_token/expires_at (epoch secs).
- TUN hook: /usr/libexec/csqtt/tun-hook with action argument and
  CSQTT_TUN_DEVICE, CSQTT_TUN_IP, CSQTT_TUN_DNS environment (confirm actual code).
- Broker: /usr/bin/csqtt-captcha serve --listen LAN_IP:9443; Unix socket
  /var/run/csqtt/captcha.sock. Fixed CLI `pair`, `cancel`, `status`.
- pair returns ok, uri/helper_uri, expires_at. URI scheme csqtt-helper://pair
  contains host, port, grant, pin and id; disclose only in authenticated action.
- Helper GET /v1/challenge consumes grant, returns session + VK URL. Results
  POST /v1/result; cancel POST /v1/cancel; authenticated CONNECT only VK-domain
  HTTPS/public IPv4 during the challenge. Leaf certificate is pinned from URI.

## Do not repeat

No need to rediscover hardware, select fork, ask policy/failure/CAPTCHA questions,
reinstall Go, re-read large upstream files or browse GitHub creation again. The
user authenticated and the public repo now exists. Browser/runtime handles and
subagents may disappear across turns; persistent files and Git survive.
