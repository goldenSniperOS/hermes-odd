# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

**Breaking:** receipt-driven development (RDD) is removed. Since gentle-ai
`5ffb65fc` (`internal/model/rdd.go`) upstream limits RDD to runtimes with a
native review transport (claude-code, codex, opencode, pi) and excludes Hermes
by design. For a receipted review, commit the work and review it from a
supported runtime such as Pi.

### Removed

- `/odd-review-mode` and the `hermes-odd:rdd-review` skill.
- The RDD mode and native review checks in `/odd-doctor` and `/odd-status`,
  and the native review and review mode probes; the only gentle-ai probe left
  is `gentle-ai version`.
- The planned native review facade (T8), closed as won't-do.

### Changed

- `hermes-odd:rdd-review-lenses` is renamed to
  `hermes-odd:advisory-review-lenses` and is now self-contained: an optional
  4R advisory review that issues no receipt.
- The plugin and package descriptions no longer claim RDD support.
- Upstream re-pin (T14): gentle-ai `d96a5d4` and gentle-shell `4d2c3f5` (both
  still v3.7.0, pinned to later `main`); every commit is triaged in
  `upstream/SUPPORTED.md`. The Hermes routing render and the managed SOUL
  blocks are unchanged upstream.

### Fixed

- `/odd-changes` replies neutralize control characters in file and project
  names (tabs become two spaces, other control characters `?`), so a recorded
  name cannot carry terminal escapes into a CLI or gateway reply (concept of
  gentle-shell `69c9f665`).

## [0.5.1] - 2026-09-27

### Fixed

- Docs, skills and command output now name commands in the hyphen form
  (`/odd-status`). The Hermes CLI looks plugin commands up by exact name, so the
  underscore form (`/odd_status`) printed before failed there with "Unknown
  command"; gateways accept both. The smoke test checks it through the
  registered command table.

## [0.5.0] - 2026-09-27

### Changed

- ODD follows upstream's one default test-first policy (gentle-ai `55e3abf1`,
  gentle-shell `a76e6f2`): RED -> GREEN -> refactor when a relevant runnable
  deterministic test and a clear expected outcome exist; tests or a framework
  merely existing do not qualify; otherwise the agent states the exception and
  runs proportionate checks, and never invents RED/GREEN or a runner. Re-worded
  in the prompt section (step 6), `hermes-odd:odd-workflow`, the
  `hermes-odd:odd-delegation` mission template, `hermes-odd:odd-feature-tracking`,
  `hermes-odd:work-unit-commits` and `hermes-odd:judgment-day`.
- The prompt section says native RDD review is unavailable on Hermes and that
  verification covers one work-unit commit or PR slice, matching upstream's
  ODD-only Hermes routing (gentle-ai `5ffb65fc` gives receipt-driven
  development only to claude-code, codex, opencode and pi). Every combination
  still fits the 3,800-character budget (largest 3,791).
- `hermes-odd:odd-delegation` adds upstream's risk-proportionate verification
  of a writer's work (passive, medium, high or unclear), one launch per
  distinct task and parent-selected memory context; `hermes-odd:odd-workflow`
  adds the checking rules (normalize before checks, one quick check, at most
  one scoped correction).
- `/odd_soul` also removes the `gentle-ai:orchestrator` block, the ODD-only
  orchestrator that a current `gentle-ai install` writes for Hermes
  (gentle-ai `fb4b59a7`), and the `gentle-ai:strict-tdd-mode` block gentle-ai
  v3.7.0 wrote when strict TDD was on, which contradicts the test-first policy.
- Upstream pins moved to gentle-ai `a9e36e9` and gentle-shell `b756b4f`
  (`main`; no release after v3.7.0), with every indexed source re-hashed, the
  canonical Hermes routing re-rendered and all commits triaged in
  `upstream/SUPPORTED.md`.

### Removed

- The TDD choice of the first-run setup: the `/odd_setup tdd` subcommand, the
  setup question, the `tdd_mode` setting in `config_schema` and the
  `TDD mode:` prompt line. A `tdd_mode` value in an existing setup record or
  in `config.yaml` still loads and is ignored.

## [0.4.0] - 2026-09-26

### Fixed

- `plugin.yaml` declares `manifest_version: 1`. `hermes plugins install` (Hermes
  0.21) refused version 2, although the loader reads the same fields either way.
- Test fixtures no longer trip Hermes' install scanner (`tools/plugin_guard.py`),
  which blocked the install as "dangerous" because of fake secrets and injection
  phrases in tests. The smoke test now runs the installer's manifest and scan
  checks, so a blocked install fails CI-side checks first.

### Added

- README install guide in three steps: the Gentle AI binaries and
  `hermes mcp add` commands for Engram and Context7 (never gentle-ai's
  Hermes install), then the plugin, then the first-run setup.
- First-run setup over chat, the Hermes version of the gentle-ai installer's persona
  step. While it is pending, the prompt section carries one line asking the agent to
  offer it once, never mid-task. Skill `hermes-odd:setup` asks five questions in one
  `clarify` call (persona with no default and no recommended option, answer style, TDD
  mode, Engram protocol, SOUL cleanup), shows one summary and asks for explicit
  confirmation before writing anything to `SOUL.md`.
- Tool `odd_setup_apply` (toolset `hermes_odd`, strict schema): validates the answers,
  mirrors them to `plugins.entries.hermes-odd.settings` with `ctx.set_config` (managed
  installs and older Hermes are reported, answers stay in plugin state), records the
  setup (`hermes-odd.setup/v1`) and writes the persona only when
  `apply_persona_to_soul` is true. It never raises; errors are `{"error": ...}` JSON.
- `/odd_setup [status|skip|reset|persona ID [confirm]|tdd MODE|engram on|off|verbosity
  short|detailed]` (group Setup): deterministic status with where each answer is
  applied, skip, reset (keeps the SOUL.md block), and direct setters. Persona changes
  are a dry-run preview until the `confirm` form.
- Persona block: exactly one `<!-- hermes-odd:persona -->` block at the top of
  `SOUL.md` (after a leading H1 or comment header), replaced in place, removed with
  persona `none`. Every write backs up to `SOUL.md.hermes-odd-bak-<UTC timestamp>`
  (last 5 kept) and replaces the file atomically with its permissions; user text and
  `gentle-ai:` blocks stay byte-identical, and a coexisting gentle-ai persona is
  reported. Own text is sanitized (no comments or markers, at most 1,500 characters)
  and checked against Hermes' own SOUL.md threat scan when available. The built-in
  personas (`hermes_odd/personas.py`) are hermes-odd's own wording of the upstream
  behavior rules, without product identity or branding.
- `/odd_soul [status|plan [persona]|apply [persona] confirm|restore [N|backup]]` (group
  Setup): cleans gentle-ai's managed blocks out of `SOUL.md`. `sdd-orchestrator` (with its
  nested `sdd-session-preflight`) and `agent-routing` are removed, keeping the nested
  `remote-authorization` block byte-identical in agent-routing's place (with its
  `gentle-ai:` markers); `engram-protocol` and `codegraph-guidance` move to lazy skills;
  the gentle-ai `persona` is kept unless explicitly requested while a hermes-odd persona
  exists; user text and unknown blocks stay byte-identical. `plan` is a dry run with the
  characters saved and Hermes truncation before -> after (128k, 200k, 1M and the
  configured model); `apply confirm` reuses the persona machinery (backup
  `SOUL.md.hermes-odd-bak-<UTC>`, last 5 kept, atomic write with the file's
  permissions) and verifies the written file; `restore` lists and restores backups
  (backing up the current file first). Unclosed, stray or crossed markers refuse with
  the line number and change nothing. Plan and apply warn that `gentle-ai install` for
  Hermes or `gentle-ai sync --agent hermes` re-adds the blocks.
- Tool `odd_soul_apply` (`confirm` required): `confirm=false` returns the dry-run plan and
  a `plan_id`; `confirm=true` applies only with the `plan_id` of the current file. The
  setup skill uses it when the `soul_cleanup` answer is the new `yes`.
- Lazy skills `hermes-odd:engram-protocol` (Engram protocol bound to `mcp__engram__*`,
  derived from gentle-ai `internal/assets/engram/protocol.md`) and `hermes-odd:codegraph`
  (CodeGraph guidance with the upstream `codegraph init` CLI, derived from
  `codegraph_guidance.go`). The prompt section adds one pointer line to each: Engram while
  `engram_protocol` is `auto` (default), CodeGraph while the new `codegraph_guidance`
  preference is `auto` and a `codegraph` binary is on `PATH` or `mcp_servers.codegraph` is
  configured. The largest combination stays under the 3,800-character cap (tested).
- Plugin `config_schema` for `persona` (default `unset`), `verbosity`, `tdd_mode`,
  `engram_protocol`, `soul_cleanup` (`unset`, `yes`, `later`, `no`) and
  `codegraph_guidance` (`auto`, `off`); `/odd_setup codegraph <auto|off>`. A chosen TDD mode adds one `TDD mode:` line
  to the prompt section, which `hermes-odd:odd-workflow` reads.
- Portable skills, rebuilt for Hermes in hermes-odd's own words (behavior only; the
  upstream skill files declare Apache-2.0 in their frontmatter while the upstream
  repositories are MIT): `hermes-odd:judgment-day` (blind dual review by two read-only
  `delegate_task` judges, the parent merges one frozen ledger, one `clarify` before any
  fix, at most two fix and re-judge rounds; advisory, no receipt, no delivery
  authority), `hermes-odd:work-unit-commits` (the ODD commit closure rules) and
  `hermes-odd:chained-pr` (400-line review budget, delivery and chain strategies, `gh`
  through `terminal`).
- `scripts/check_upstream_drift.py` (standard library only): clones or fetches both
  upstreams into `--cache` / `HERMES_ODD_UPSTREAM_CACHE`, checks that each pin exists and
  is an ancestor of the default branch, re-hashes every indexed source at the pin
  against the lock and at the head (changed, deleted, unchanged, with the commits per
  source), lists new upstream skills and guidance files to triage (SDD excluded) and
  flags a Go re-render when `routing.go` or `manifest.go` change. `--format json`
  (schema `hermes-odd.upstream-drift/v1`) or `markdown`, `--output`, `--offline`,
  `--exit-zero`; exit 0 clean, 1 drift, 2 error.
- Scheduled workflow **Upstream drift** (weekly and on demand, `contents: read`,
  `issues: write`): an error fails the job; drift opens or updates one
  `[upstream-drift] Upstream changes to triage` issue with the port request template
  headings, creating the `upstream-port` and `needs-triage` labels idempotently.

### Changed
- The prompt section names the portable skills by qualified name only
  (`hermes-odd:work-unit-commits`, `hermes-odd:chained-pr`, `hermes-odd:judgment-day`),
  never a same-named bare skill; the largest combination is 3,789 characters (cap 3,800).
- `hermes-odd:odd-workflow` section 7 now points to the commit, delivery and review
  skills instead of repeating their rules, so each rule lives in one skill;
  `hermes-odd:rdd-review` points to `hermes-odd:judgment-day` for dual reviews.
- Upstream lock: new component `portable-skills`; `upstream/SUPPORTED.md` records the
  skill decisions (ported, and not ported with reasons) and the first drift triage of
  every commit past the pins (gentle-ai up to `6c7f162f`, gentle-shell up to `5456811`).
  Pins unchanged: the default applicable test-first policy (gentle-ai `55e3abf1`,
  gentle-shell `a76e6f2`) needs a port and the canonical routing a re-render first.
  The capability manifest is unchanged, so native review (T8) stays blocked.
- `/odd_doctor`'s SOUL.md check recommends `/odd_soul plan` (with the blocks to remove
  and the characters saved) when the cleanup would help.
- With the default preferences the prompt section now ends with the Engram skill pointer
  line; `build_odd_section()` without inputs is still exactly `ODD_SECTION`.
- `/odd_doctor` also reports the hermes-odd persona block (size, whether it is at the
  top), and SOUL.md truncation math covers `hermes-odd:` blocks too; only gentle-ai
  blocks trigger the "sent with every message" warning.
- Upstream lock: new component `persona` indexing the gentle-ai Hermes persona assets
  and gentle-shell `extensions/gentle-ai.ts`; `upstream/SUPPORTED.md` triages the
  installer steps (persona and strict TDD ported as setup; presets, component
  selection and model pickers not portable or not applicable).
- Upstream lock: new component `soul-cleanup` indexing gentle-ai
  `internal/assets/engram/protocol.md`, `codegraph_guidance.go`, `inject.go`,
  `remote_authorization.go` and the remote-authorization contract; `SUPPORTED.md`
  triages the SOUL blocks (engram protocol and codegraph guidance ported as lazy skills;
  remote-authorization kept in SOUL).

## [0.3.0] - 2026-09-25

Honest RDD on Hermes: toggle and inspect gentle-ai's receipt-driven development switch,
see live whether native review is available for Hermes (gentle-ai 3.7.0 does not yet
advertise it), and run an optional, clearly labeled receipt-less 4R advisory review.

### Added
- `/odd_review_mode [status|enable|disable] [global|clone] [project]` (`/odd-review-mode`
  in the CLI, group Review): the RDD switch over the real `gentle-ai review mode` CLI.
  `status` (default, read-only) shows the effective mode and its source for a known
  project (name or prefix) or the directory Hermes runs from, both sources, and native
  review availability on Hermes; `enable`/`disable` require an explicit scope
  (`clone` needs a git repository) and report gentle-ai's resulting JSON status.
- Native review availability probe: read-only `gentle-ai review status --cwd <git repo>
  --contract gentle-ai.review-integration/v2 --agent hermes --next-transition` (no
  shell, minimal environment, 3 s timeout, cached 60 s, only inside a git repository).
  gentle-ai 3.7.0 refuses Hermes with `immutable_review_transport_unsupported`;
  `/odd_review_mode`, `/odd_status` and `/odd_doctor` report "Native review on Hermes:
  unavailable" honestly. hermes-odd never passes another runtime's identity.
- Skills `hermes-odd:rdd-review` (honest RDD protocol on Hermes: report "native review
  unavailable on Hermes" once per candidate, record it, continue under ordinary
  repository policy; never impersonate a runtime or fake a receipt) and
  `hermes-odd:rdd-review-lenses` (4R lens charters condensed from gentle-shell for an
  optional advisory review via `delegate_task`, labeled "advisory review — no receipt").

### Changed
- Upstream lock: component `rdd` is `partial` (T7 ported; native facade T8 blocked on
  upstream runtime eligibility) and indexes the gentle-shell 4R sources;
  `review-contract` records the verified failure schema and code.

## [0.2.0] - 2026-09-25

Viewers and health: see what your Hermes subagents are doing, your ODD feature
progress, the files the agent changed, and a read-only doctor, from the CLI or any
gateway (Telegram first), without calling the model.

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
- `/odd_changes [file|project|all|clear]` (`/odd-changes` in the CLI): plain-text view of
  the files the agent and its subagents changed, a concept port of gentle-shell's Gentle
  Changes. A second `post_tool_call` callback captures successful `write_file` and
  `patch` calls only (replace and V4A modes; terminal/shell edits are not tracked), with
  the absolute path Hermes reports in the result, line counts computed at capture time
  (from the patch result's unified diff, else the arguments; `write_file` removed lines
  are unknown), attribution (`main` or the subagent id, enriched with its role and goal)
  and the session and platform. Content and diffs are never stored (schema
  `hermes-odd.changes/v1`, in-memory fallback; 200 files, 7 days). The list covers the
  last 24 h (`all`: 7 days) grouped by project; a file shows its edit timeline and, in a
  git repository, `git diff --numstat` for that file (no shell, minimal environment,
  2 s timeout); `clear` forgets everything.
- `/odd_status` (`/odd-status` in the CLI): one compact status message, a concept port
  of gentle-pi's `gentle:status`: hermes-odd version, prompt section size, registered
  skills, subagents running / finished (24 h), changes in 24 h, ODD features and open
  tasks, the first-on-PATH gentle-ai version against the lock minimum, the RDD mode
  when `/odd_doctor` cached it, and the supported upstream versions. It runs no
  subprocess except a `gentle-ai version` probe cached for 60 s.
- `/odd_doctor` (`/odd-doctor` in the CLI): read-only health report, a concept port of
  gentle-pi's `gentle:doctor`, one `✓ / ⚠ / ✗` line per check with a fix hint: every
  `gentle-ai` on `PATH` with its version (below the minimum, or a stale binary
  shadowing another; hints repeat the binary-only rule), the RDD mode of the current
  git repository (`gentle-ai review mode status --json`), `SOUL.md` size, gentle-ai
  managed blocks and Hermes' truncation cap (`max(20000, min(ctx*4*0.06, 500000))`,
  70/20 head/tail, naming the managed blocks in the dropped middle), the plugin's
  section, skills, hooks and a `ctx.state` write/read probe, the upstream lock, and
  Hermes' version and enabled state. Subprocesses run without a shell, with a minimal
  environment and a 3 s timeout (about 6 s in total), cached for 60 s; `.env`,
  `auth.json` and SOUL content are never read or printed beyond sizes.
- README: the official "Built with Gentle-AI" badge under the credits, and a note that
  hermes-odd is being built with Gentle AI's ODD workflow through gentle-pi.

### Changed
- `/odd_commands` groups the commands under Viewers and Health.
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

[Unreleased]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/goldenSniperOS/hermes-odd/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/goldenSniperOS/hermes-odd/releases/tag/v0.1.0
