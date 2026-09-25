# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `/odd_agents [id|all]` (`/odd-agents` in the CLI): plain-text view of `delegate_task`
  subagents, a concept port of gentle-shell's Gentle Agents. Observer hooks
  (`on_session_start`, `subagent_start`, `post_tool_call`, `subagent_stop`; never
  `pre_tool_call`) keep one record per child in `ctx.state` (schema
  `hermes-odd.agents/v1`, in-memory fallback): role, goal, status, timings, parent
  session and platform, tool count, last tool and a 15-entry tool timeline, and the
  child's own summary. Tool arguments and results are never stored. At most 50 records;
  finished runs are dropped after 24 h and runs with no stop event after 6 h are marked
  `stale`. Output stays under 3,500 characters for Telegram.
- `/odd_tasks [feature|project]` (`/odd-tasks` in the CLI): plain-text view of ODD
  feature documents (`odd/tasks/<feature>.md`), a concept port of gentle-shell's todo
  card. The overview lists each project's features, newest first, with a progress bar,
  done/total, the next open task and the last change; a feature prefix (or
  `project/feature`) shows every task, the next step and the file. A forgiving,
  read-only parser (`hermes_odd.feature_docs`) handles `## Tasks` checkboxes with task
  ids, nested items, continuation lines, fenced code, CRLF and documents without a
  Tasks heading, reading at most 256 KB per file and 50 files per project and never
  following symlinks. Projects come from the git roots of recent session working
  directories (recorded, at most 10, in `ctx.state` schema `hermes-odd.projects/v1`)
  plus the command process's own directory.

### Changed
- The `hermes-odd-workflow` prompt section is now registered as a callable so it can
  record the session's project root for `/odd_tasks`; the rendered text is unchanged
  byte for byte (tested, and checked through Hermes' render path in the smoke).

## [0.1.0] - 2026-09-24

First release: the ODD foundation. Viewer commands (`/odd_agents`, `/odd_tasks`,
`/odd_changes`, `/odd_status`, `/odd_doctor`) arrive in 0.2.0 and RDD in 0.3.0.

### Added
- Hermes plugin scaffold: `plugin.yaml` manifest, root `__init__.py` entry point for
  `hermes plugins install`, `hermes_odd` package with a guarded `register(ctx)` that
  never breaks Hermes startup, and a `unittest` suite with a fake plugin context.
- Declarative, Telegram-safe command registry and the first command, `/odd_commands`
  (`/odd-commands` in the CLI), which lists every hermes-odd command as plain text
  without calling the model.
- Compact always-on ODD system prompt section `hermes-odd-workflow` (about 3.3k
  characters; a test caps it at 3,800 of the 4,000 Hermes allows per section).
- Lazy plugin skills loaded on demand with `skill_view`: `hermes-odd:odd-workflow`,
  `hermes-odd:odd-delegation` and `hermes-odd:odd-feature-tracking`.
- Vendored canonical gentle-ai routing render for Hermes
  (`upstream/odd-routing-hermes.canonical.md`, from
  `RenderRouting(model.AgentHermes)`) with a SHA-256 provenance test, for drift
  tracking.
- Upstream support matrix: `upstream/upstream.lock.json` (schema
  `hermes-odd.upstream-lock/v1`) pins gentle-ai v3.7.0 (`f182ea2`, binary >= 3.7.0) and
  gentle-shell v3.7.0+16 (`4d702a4`, npm `gentle-pi` 3.7.0) and indexes every upstream
  source per component with its SHA-256; `upstream/SUPPORTED.md` holds the human matrix,
  the sync procedure and the triage log; `hermes_odd.upstream` reads the lock
  (`load_lock()`, `min_gentle_ai_version()`), and tests cross-check it against the
  `derived-from` markers, `THIRD_PARTY_NOTICES.md` and the canonical render.
- Credits, non-affiliation notice and `THIRD_PARTY_NOTICES.md` with the upstream MIT
  notices of gentle-ai and gentle-shell and the list of derived files.
- Project packaging: `pyproject.toml` (entry point `hermes_agent.plugins`, skills
  shipped in the wheel), ruff configuration, CI (ruff, tests on Python 3.11/3.12,
  build), tag-driven release workflow, issue and pull request templates, Dependabot,
  `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/design.md` and an
  isolated end-to-end smoke (`scripts/smoke_e2e.py`).

[Unreleased]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/goldenSniperOS/hermes-odd/releases/tag/v0.1.0
