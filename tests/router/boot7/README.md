# Remaining failed-first-activation boot proof

These are acceptance helpers for the authorized GL-MT6000 test router. They
are not installed package files. Do not run a fault or reboot until the
controller, persistent recovery and client observation have been reviewed and
rehearsed. A private mount/network check does not prove actual host boot.

Completed prerequisites are recorded in `docs/STATUS.md`; generated binaries,
private contexts and results belong in ignored `.work/boot7`.

## Readonly and context preparation

- `preflight.py` supplies active physical Windows NIC facts to `preflight.uc`
  in memory. Native checks corroborate the SSH socket, LAN route, ARP/neighbor
  MAC and absence of an active policy assignment. Output contains fixed labels
  and counts. A successful preflight is one prerequisite, not the full gate.
- `stage.py` creates a private current-config snapshot and native closed-hold
  artifact. `prepare.uc` derives a protected group/domain set and verifies two
  synthetic locally administered MACs against owner assignments and leases.
  It stores dynamic facts only in the private router context. No arm marker,
  policy/config change, service operation or boot hook is performed.
- `recovery.sh check STATE` validates that context and runs native `nft -c`.
  `validate-native.py` compiles its embedded ucode without executing it.
- `fw4-missing/main.go` binds a private readonly view over `/etc/csqtt` in its
  own mount namespace. Native `fw4 print` plus `nft -c` checks missing full
  includes and retained hold. It never loads rules. Its fixed fixture path must
  be absent before use; inspect retained evidence before preparing another run.

## Bounded client probe

Build from the repository root using the existing portable Go toolchain:

```powershell
.work/tools/go/bin/go.exe test tests/router/boot7/probe.go tests/router/boot7/probe_test.go
$env:GOOS='linux'; $env:GOARCH='arm64'; $env:CGO_ENABLED='0'
.work/tools/go/bin/go.exe build -trimpath -ldflags='-s -w' -o .work/boot7/probe-linux-arm64 tests/router/boot7/probe.go
Remove-Item Env:GOOS,Env:GOARCH,Env:CGO_ENABLED
python tests/router/boot7/preflight.py
python tests/router/boot7/validate-native.py
python tests/router/boot7/stage.py
```

The probe uses one 1500ms deadline and validates DNS response identity,
questions, compression, lengths and an A answer. It prints no endpoint, query
or transaction ID. `blocked_candidate` requires external passive ingress and
zero post-guard counters; no answer alone is insufficient.

## Still unfinished

The full real-host fault/boot controller has not been implemented or executed.
Do not infer that recovery has been executed from successful `check` mode.
Before arming, record exact current/staged config hashes, verify test-client
positive controls, install independently recoverable hooks, then cause the
specific compiled nft set-type rejection. Keep saved and live guards closed
until native policy/DNS readiness releases them. Restore current owner bytes,
startup links and only explicitly owned test objects, then repeat signed-r7
health checks. Record source, native checks, rehearsal and actual boot separately.
