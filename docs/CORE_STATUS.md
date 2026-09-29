# Rust core checkpoint

Updated: 2026-09-30. Owner: `core_ci_fix` (check live agents before delegation).
Source integration is complete. Linux Rust CI passed at commit
`450df529d1435f2be6e63f51d335f70fa97075d4`: **337 tests passed, 7 ignored**
(result reported by the root agent). Subsequent changes listed below still
need CI. Live TUN/VK operation has not been verified. Root owns CI,
checkpoints and publication.

Latest CI at `18baa7d` compiled the core but reported **339 passed, 1 failed,
7 ignored**. The failure is
`turn::integration_tests::authenticated_flow_survives_pool_deficit_and_keeps_channel_data_zero_copy`:
the fixture server's UDP receive timed out after 3 seconds, then the client's
ChannelBind preparation timed out after 5 seconds. The prior helper omitted
the handshake stage. This is unresolved; a subsequent successful retry alone
does not demonstrate that the cause was fixed.

## Implemented

- `--config-file` reads private JSON; validates unknown fields, credentials,
  worker/hash capacity, paths and interface names. Defaults: 9 workers,
  video obfuscation, UDP TURN, `csqtt0`, MTU 1300.
- Linux opens an exclusive, nonpersistent TUN descriptor, uses the existing
  dispatcher/packet framing and preserves upstream native-TUN GETCONF port 0.
  Descriptor loss cancels the client. Wire, auth, TURN and shared protocol files
  remain upstream compatible.
- SIGTERM/SIGINT and private `stop` command cancel the client. Daemon startup
  can be cancelled during peer DNS resolution. Daemon mode does not consume
  stdin or exit when its parent PID changes.
- Validated TUNCONF applies /32 address and MTU/link state, then runs hook `up`.
  Hook takes one action argument (`up` or `down`) and environment variables
  `CSQTT_TUN_DEVICE`, `CSQTT_TUN_IP` (bare IPv4), `CSQTT_TUN_DNS` (comma list).
  Hook processes have bounded deadlines and are killed on cancellation.
  Shutdown cleans only the socket/TUN integration owned by this process.
- Persistent private identity has an exclusive advisory lock. Generation is
  incremented and atomically saved before transport starts; corrupt identity
  and conflicting device IDs are rejected instead of silently replaced.
- Atomic private JSON status exposes state/pid/tun_device/tunnel_ip/dns,
  active_workers/bytes_up/bytes_down, redacted CAPTCHA and error_code. Events
  update status without printing upstream machine messages in daemon mode.
  Sensitive/oversized upstream diagnostics are suppressed.
- Private Unix socket authenticates peer UID, bounds requests/concurrency/time,
  and accepts one newline JSON request per connection: status, captcha_get,
  captcha_manual, captcha_result, captcha_cancel, stop. Responses use `ok`.
  CAPTCHA mutations require `id`; result additionally requires `token`.
- Native CAPTCHA automatic attempts remain active. Manual takeover cancels
  their future and proof-of-work token, then waits for the companion result.
  Challenge UUIDs, monotonic deadlines, epoch-second expiry, one-use answers
  and drop cleanup reject stale, expired, canceled or duplicate responses.
  Only `captcha_get`/private control responses expose challenge credentials;
  public status contains only id/state/expires_at.
- Original Android stdin/WebView behavior remains selected outside daemon mode.

## Cross-component contract

`client_ids` is a comma-separated string. `vk_auth_mode` accepts `vkcalls` or
`legacy`; fingerprint accepts firefox/chrome/edge/safari/opera. Optional
`turn_host` and numeric `turn_port` are supported. `captcha_timeout_secs` is
30..600. Runtime JSON must omit `captcha_mode` and `mtu`: automatic/manual
companion behavior and MTU 1300 are fixed; unknown JSON fields are rejected.
The policy and LuCI agents were notified of this contract.

Scoped review confirmed hook action/environment names match the actual
OpenWrt hook, private socket paths and JSON command/id/token names match the
Go broker, and expiry is an integer number of Unix seconds. The broker and
core now both allow CAPTCHA result tokens up to 16,384 bytes. Core request
frames allow 65,536 bytes including JSON escaping. Both the published epoch
deadline and a monotonic deadline are enforced; process cancellation revokes
answers immediately. These last changes have not yet run in CI.

## Added tests

- Configuration typos/delimiters/hash capacity, IPv6 peer and TUN name safety.
- TUNCONF address/DNS validation and redacted status transitions.
- Identity persistence/generation/parallel lock; private-file permissions and
  symlink rejection.
- Unix malformed/missing/stale/unknown commands and successful stop reply flush.
- Manual takeover wins automatic completion; one-use answer; expiry/cancel;
  old cleanup cannot erase a new challenge.
- The preceding tests were present in the successful CI snapshot above.
  Later tests below still need CI:
- Native dispatcher forwards an IPv4 packet and stops when the owned
  descriptor disappears (Unix stream fixture, no CAP_NET_ADMIN required).
- Broker-compatible token/frame bounds, published epoch expiry, and immediate
  answer revocation on process cancellation.

## Checks actually run and remaining work

- Read and reviewed source contracts and edited files. Inspected Git state.
- `Get-Command cargo,rustc,rustup` found no Rust toolchain.
- `wsl --list --quiet` failed because WSL is not installed. No local Rust test
  ran; the verified result above comes from Linux GitHub Actions.
- Changes after the verified SHA: `dispatcher.rs` native descriptor test,
  `main.rs` runtime-creation failure status, and `captcha.rs`/`daemon.rs`
  broker-limit, epoch/cancellation fixes and regression tests.
- CI failure review: confirmed `turn.rs`, `turn_core.rs`, `udp_batch.rs` and
  `turn_integration_tests.rs` were unchanged between `450df5` and `18baa7d`.
  Static review did not establish a production defect. Under the sole pool
  lease deficit, the UDP driver handles STUN through its stack buffer and
  schedules a native control pump; wake notifications retain a permit.
- Added receive stage diagnostics (initial/authenticated Allocate,
  CreatePermission, ChannelBind, outbound ChannelData and deallocation
  Refresh). The failing fixture now observes its server task alongside the
  client during allocation, preparation and inbound receive, so server
  failures surface immediately. Timeouts, protocol assertions and zero-copy
  checks are unchanged. This diagnostic change has not been compiled/tested.
- Separately fixed a confirmed data-phase fixture race: the server could
  receive outbound data on another worker and send inbound data before
  `send_with_duplicate` dropped the sole packet lease. A one-shot gate now
  permits inbound sends only after the client send completes. The Allocate
  and ChannelBind handshake still runs with zero available pool buffers;
  malformed/wrong-channel rejection and storage-pointer reuse assertions
  remain. This does not explain or resolve the observed preparation timeout.
- Rechecked `Get-Command cargo,rustc,rustup -ErrorAction SilentlyContinue`:
  none is installed. `git diff --check` passed for the diagnostic/status edit.
- Next: run the named test with `RUST_BACKTRACE=1`, then the complete CI core
  job. If the timeout recurs, use its stage/backtrace to fix the confirmed
  cause. On Linux with Rust 1.97.1, run:

  ```sh
  cargo +1.97.1 test --locked --manifest-path vendor/csqtt/rust-client/Cargo.toml
  cargo +1.97.1 build --locked --release --manifest-path vendor/csqtt/rust-client/Cargo.toml
  ```

- The tested Linux snapshot compiled successfully, including libc TUN ioctl
  and async ownership code. Re-run CI on the latest source before packaging.
- Remaining real acceptance: SIGTERM/boot/crash on OpenWrt, actual /dev/net/tun,
  original server handshake/data transfer, and live VK auto/manual CAPTCHA.
  No live router changes or credentials were used.

## Follow-up CI at d10c559

Run36638062416 compiled the updated source. The focused TURN fixture passed,
and it also passed in the full suite. Full result:340 passed/1failed/7ignored.
The sole failure was a new redaction test expectation: its dummy password
contained the word `password`, so the existing sensitive-field filter omitted
the whole line before literal replacement. Changed the dummy value to exercise
replacement independently; production suppression was already correct.
Native Device ID/device_id log fields are now suppressed in daemon mode.
Latest full green Rust result still requires another CI run.

## OpenWrt musl ABI compilation fix

SDK job `109643864295` at `d10c559` reached the Rust cross-build and failed
on four target-libc differences: `linux_tun.rs` passed a `c_ulong` ioctl
request where musl requires `c_int`; `udp_batch.rs` passed signed flags where
musl's `recvmmsg` and `sendmmsg` require unsigned flags; its `msghdr` struct
literal could not name musl's private `__pad1`/`__pad2` fields.

The ioctl request and Linux mmsg flags now cast to the type inferred from
the target libc signature, preserving their bit patterns. The shared mmsg
header starts zeroed, including private padding, then sets its public iovec
pointer and count. This keeps the previous null/zero fields and batch behavior.
Android syscall branches are unchanged. Reviewed the Linux/Android/test cfg
paths in both files and searched the Rust tree for additional ioctl/mmsg
calls and msghdr literals; no additional occurrences need the same repair.
Existing UDP tests cover connected/unconnected batches and source addresses.

`git diff --check` passed for these source/status edits. No local Rust compiler
or SDK was used. Next: rerun the OpenWrt SDK release build and host core tests;
also cross-check test compilation with
`cargo +1.97.1 check --locked --tests --target aarch64-unknown-linux-musl
--manifest-path vendor/csqtt/rust-client/Cargo.toml` using the SDK compiler
environment. Successful host glibc tests alone do not verify musl compilation.
