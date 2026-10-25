# Resume instructions

Read `docs/STATUS.md` first, then `docs/IMPLEMENTATION.md`. Treat a user message
such as "Продолжай" as continuing the first unfinished action in STATUS.
For a fresh chat/account, also read `docs/AI_HANDOFF.md` and the current README.
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
  the protocol-incompatible danusha2345 fork or upstream2.5.0 without a new,
  explicit protocol migration decision. The retained Windows compatibility is intentional.
- Current delivery scope: official OpenWrt24.10/25.12, selected by verified ABI
  and capabilities without a board lock. Historical native reference is
  GL-MT6000/25.12.5; current native reference is25.12.6. GLvendor firmware
  work was cancelled2026-10-22 and retained in checkpoints. One active tunnel,
  named groups, domain/IP rules.
- VPN-classified traffic must not fall back to WAN. Preserve local management.
  Explicit WAN exceptions are allowed. See the full contract for DNS/IPv6.
- Keep passwords, VK links, pairing grants, private signing keys and runtime
  identities out of Git, logs, status RPC responses and test fixtures.
- Keep personal filesystem paths, network identifiers, raw router output and
  detailed live usage measurements out of public handoff/status documentation.
- Preserve upstream license/attribution. Keep `.work/`, `dist/`, generated
  build files and private credentials ignored.
- Separate source implementation, compilation, simulated tests and real
  router/VK tests in reports. Do not call the project ready for installation
  until the stated release checks have actually passed.
- User installs published releases personally. Router access must be supplied
  privately and is for agreed read-only checks only; no installation, reboot or
  network/service changes without separate authorization. Never assume old SSH
  aliases, browser sessions, signing access or agents exist in a fresh chat.
- No Codex scheduled tasks. Old72h acceptance is incomplete after owner reflash;
  elapsed wall time is not evidence of a pass.

## Local tooling

Detect the current OS and available tools before running commands. The original
workspace used Windows/PowerShell, Node/Python and optional portable Go under
ignored `.work/tools/go/bin/`; reuse tools if present. Fresh checkouts do not
contain private `.work/` files or runtimes. Linux/Rust, Android and OpenWrt SDK
builds are defined in GitHub Actions. Missing access/tools are not evidence of
a successful check. Do not publish local paths or replace signing trust to
work around missing repository secrets.

`AGENTS.md` is the project instruction mechanism described in the
[official guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
