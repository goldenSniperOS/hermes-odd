# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Changed
- Renamed the project to hermes-odd: plugin `hermes-odd`, package `hermes_odd`, skill
  namespace `hermes-odd:*`, command prefix `/odd_*`, repository
  `goldenSniperOS/hermes-odd`.
