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

- [ ] T1 Recall detection module: read `memory.provider`, `mcp_servers.engram`, the
      state file and Engram health; fail soft; unit tests.
- [ ] T2 `/odd-doctor` recall check (provider, Engram health, duplicate MCP warning).
- [ ] T3 `/odd-status` last memory id line.
- [ ] T4 `MEMORY_POINTER` adapts to the recall provider (+ engram-protocol skill note);
      budget test green.
- [ ] T5 Docs: install-with-an-agent.md + README install section + CHANGELOG
      (Unreleased) + docs/design.md.
- [ ] T6 Release v0.7.0 (blocked until hermes-recall v0.1.0 is public).

## Progress

- 2026-10-01: Branch `feat/hermes-recall-integration` created from `4d7b07b`. Pending
  checks of hermes-odd-port: CLI pty test of all 8 `/odd-*` commands passed on v0.6.0
  (real `hermes --cli` in a pty). Telegram check pending: gateway pid 66612 started
  2026-09-23, before v0.6.0 was installed (2026-09-29); needs `/restart`.

## Evidence

(commit ids recorded per task)

## Next step

T1-T5 delegated to one OpenCode writer.
