# Feature: hermes-recall integration (hermes-odd v0.7.0)

## Objective

Make hermes-odd aware of the optional `recall` memory provider
(goldenSniperOS/hermes-recall, an Engram-compatible Hermes MemoryProvider), so the
health commands, the always-on prompt and the install docs reflect whether automatic
Engram recall/capture is active.

## Why

With hermes-recall, Engram recall and capture run on every turn without the model
deciding. hermes-odd must not keep telling the model to "load the protocol before
searching" when recall is automatic, must surface the last memory id, and must warn
when the Engram MCP server duplicates the provider's tools.

## Scope

- `/odd-doctor`: detect `memory.provider` == `recall`; probe Engram health
  (`http://127.0.0.1:7437/health`, short timeout, fail soft); warn about duplicate
  Engram MCP tools (`mcp_servers.engram`) while the provider is active.
- `/odd-status`: last memory id from `<hermes_home>/recall/state.json`, read directly as
  JSON (never import `hermes_recall`, an exclusive plugin). Keys: `last_memory_id`
  (int), `last_action` (str), `project` (str), `updated_at` (ISO 8601). Missing or
  malformed file -> fail soft.
- `MEMORY_POINTER` in `hermes_odd/prompt.py` adapts when recall is active (recall is
  automatic; keep the save protocol). The 4000-char budget test stays green.
- `docs/install-with-an-agent.md` and the README install section: hermes-recall as an
  optional, recommended step.

## Non-goals

- Editing hermes-recall (separate repo and session).
- Changing `memory.provider` on the user's live profile.
- Tagging/releasing v0.7.0 before goldenSniperOS/hermes-recall v0.1.0 is public.

## Constraints

- Python stdlib only; `unittest`; tests with python3.11 or the Hermes venv.
- Commands answer without the model and never raise.
- Credit Alan Buscaglia / Gentleman Programming; keep "Built with Gentle AI".
- No AI attribution in commits.

## Tasks

- [x] T1 Recall detection module: read `memory.provider`, `mcp_servers.engram`, the
      state file and Engram health; fail soft; unit tests.
- [x] T2 `/odd-doctor` recall check (provider, Engram health, duplicate MCP warning).
- [x] T3 `/odd-status` last memory id line.
- [x] T4 `MEMORY_POINTER` adapts to the recall provider (+ engram-protocol skill note);
      budget test green.
- [x] T5 Docs: install-with-an-agent.md + README install section + CHANGELOG
      (Unreleased) + docs/design.md.
- [x] T6 Gateway-safe replies: wrap displayed file paths in inline code so the gateway
      `extract_local_files` never auto-attaches them (Telegram received SOUL.md as a
      document from `/odd_doctor`); command references use the underscore form
      (`/odd_doctor`) so Telegram links the whole command. Tests.
- [x] T7 Docs: Telegram menu cap (`platforms.telegram.extra.command_menu.max_commands`
      and `priority`) in README; close stale T8 checkbox in hermes-odd-port.md.
- [ ] T8 Release v0.7.0 (blocked until hermes-recall v0.1.0 is public).

## Progress

- 2026-10-01: Branch `feat/hermes-recall-integration` created from `4d7b07b`. Pending
  checks of hermes-odd-port: CLI pty test of all 8 `/odd-*` commands passed on v0.6.0
  (real `hermes --cli` in a pty). Telegram check pending: gateway pid 66612 started
  2026-09-23, before v0.6.0 was installed (2026-09-29); needs `/restart`.

- 2026-10-01: Telegram check after `/restart`: `/odd_status` and `/odd_doctor` answer on
  v0.6.0; found the SOUL.md auto-attachment and hyphen-link issues (T6). Menu: 60-slot
  default cap hid all plugin commands; user approved `max_commands: 100` and an `odd_*`
  priority list on the live profile. Setup: rioplatense persona written, gentle-ai persona
  block removed (SOUL.md 9,862 -> 4,621 chars).
- 2026-10-01: OpenCode writer stopped mid-T1 (uncommitted `recall.py` + tests). Policy
  change from the user: no OpenCode; Pi subagents (or Hermes `delegate_task` when run
  from Hermes) write the code.

- 2026-10-01: Overlap check with hermes-recall (its session confirmed): it owns Engram
  health, URL resolution and `/recall`; hermes-odd only reads `state.json` and config,
  owns the duplicate-MCP warning, and treats `memory.recall.enabled: false` as not
  active. User decision: probe Engram only when recall is not active.
- 2026-10-01: goldenSniperOS/hermes-recall v0.1.0 is public (released 06:51 UTC).

## Evidence

Native review per work unit (committed-only, explicit base), all approved and
acknowledged; advisory findings handled in follow-up commits.

| Commit | Task | Review |
|---|---|---|
| `e9bd705` | feature doc | `review-009c52b6306ad5f7` low |
| `13a97a6` | T1 recall view | `review-dcb41d28479ca9a5` medium |
| `900035e` | T2, T3 doctor/status | `review-6eab9528519fd065` high |
| `36dfe5f` | T4 prompt pointer + skill | `review-0860f22bd6dbd010` medium |
| `0f60889` | defer Engram details to `/recall`, `memory.recall.enabled`, review fixes | `review-cca2bcd58fd0aaf6` high |
| `48fac91` + `b87fdd9` | T5, T7 docs; T6 gateway-safe replies | `review-f8fbb529aa31d43b` high |

Checks: real `hermes --cli` pty test of all 8 commands on v0.6.0; live Engram 2.0.0
probe through the Hermes venv; unittest suite green on python3.11; ruff clean.

## Next step

Hardening of the T6 reply wrapper (review advisories), then T8 release v0.7.0.
