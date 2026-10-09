# Resume instructions

Read `docs/STATUS.md` first, then `docs/IMPLEMENTATION.md`. Treat a user message
such as "Продолжай" as continuing the first unfinished action in STATUS.
Confirm the current files and Git state; the chat history and previous agent
sessions are not the source of truth. Do not repeat settled product questions,
reclone the upstream source, or restart already completed work.

## Preserve progress

- Update STATUS after each meaningful milestone and before ending a turn.
  Record completed work, exact checks run, failures, and the next concrete step.
- Save unfinished source in small, explicitly labelled checkpoint commits.
  Push the development branch when GitHub access is available. Do not treat a
  checkpoint as a tested release or merge it just to save work.
- Before a likely interruption, save source and STATUS immediately. A future
  session must be able to continue using files alone.
- Record subagent ownership, but recheck whether those agents are still alive
  before delegating. Never assume a previous tool session/process still exists.
- Keep logs short and spend effort on implementation and meaningful checks.

## Project constraints

- Preserve compatibility with original amurcanov/csqtt v2.1.9; do not switch to
  the protocol-incompatible danusha2345 fork.
- First supported target: GL-MT6000, OpenWrt 25.12.5, mediatek/filogic,
  aarch64_cortex-a53. One active tunnel, named groups, domain/IP rules.
- VPN-classified traffic must not fall back to WAN. Preserve local management.
  Explicit WAN exceptions are allowed. See the full contract for DNS/IPv6.
- Keep passwords, VK links, pairing grants, private signing keys and runtime
  identities out of Git, logs, status RPC responses and test fixtures.
- Preserve upstream license/attribution. Keep `.work/`, `dist/`, generated
  build files and private credentials ignored.
- Separate source implementation, compilation, simulated tests and real
  router/VK tests in reports. Do not call the project ready for installation
  until the stated release checks have actually passed.
- Do not touch the live router without connection details and task scope.

## Local tooling

Workspace is Windows/PowerShell. Node and Python are available. Portable Go is
in `.work/tools/go/bin/`; it does not need reinstalling if present. No WSL,
Docker or Rust toolchain was available at the last checkpoint. Linux/Rust,
Android and OpenWrt SDK builds are defined in GitHub Actions.

`AGENTS.md` is the project instruction mechanism described in the
[official guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
