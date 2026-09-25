# Feature: hermes-odd port (ODD + RDD for Hermes)

## Objective

Ship `hermes-odd`: a Hermes plugin plus a set of lazy-loaded skills that brings the
gentle-shell (npm `gentle-pi`) and gentle-ai ODD and RDD experience to Hermes, with the
same behavior and management model as Pi, adapted to Hermes-native surfaces.

## Problem

- gentle-ai's Hermes integration writes everything into `~/.hermes/SOUL.md` (measured
  88,483 chars / ~22k tokens per message; 56% is SDD). Hermes truncates context files to
  `max(20000, ctx_len*4*0.06)` chars keeping 70% head / 20% tail, so on 128k-200k models
  most of the ODD routing block is silently dropped.
- gentle-shell features (agents view, changes, todo/feature tracking, review mode, doctor,
  status) are Pi TUI features and do not exist in Hermes.

## Why

Hermes is the user's daily driver because of its gateways (Telegram first). The Gentle
workflow should run there with a lean prompt and viewer commands that work on every
gateway.

## Scope

- Hermes plugin (`plugin.yaml` + `register(ctx)`), installable with
  `hermes plugins install goldenSniperOS/hermes-odd`.
- Compact always-on ODD section via `ctx.register_system_prompt_section` (<= 4000 chars).
- Lazy skills: ODD detail (delegation, memory/feature continuity, skills protocol), RDD
  orchestration for Hermes, plus portable gentle-shell skills.
- Slash commands answered as plain messages (no LLM call), compatible with CLI/TUI and
  every gateway: `/odd_agents`, `/odd_changes`, `/odd_tasks` (feature tasks),
  `/odd_status`, `/odd_doctor`, `/odd_commands`, `/odd_review_mode`,
  `/odd_persona`.
- RDD driven through the `gentle-ai review` CLI (binary only).
- SOUL migration (strip gentle-ai managed blocks, with backup and dry-run).
- Upstream tracking: pinned lockfile of gentle-ai/gentle-shell commits + drift script.

## Non-goals

- SDD in any form (agents, chains, skills, preflight, `gentle-sdd-*` commands).
- Pi-only aesthetics: themes, banners, animations, TUI widgets, keyboard shortcuts,
  double-esc cancel.
- Pi-only runtime plumbing: dev-binary, telemetry, Pi model profiles, Pi package installs.
- Running `gentle-ai install` or `gentle-ai sync` for Hermes.

## Constraints

- Python stdlib only; tests with `unittest` (no pytest in the Hermes venv).
- Command names must be Telegram-safe (`[a-z0-9_]`); Hermes normalizes `-`/`_`.
- Always-on prompt budget: <= 4000 chars total from this plugin.
- Technical artifacts in English.
- gentle-ai must be current (binary only); never `install`/`sync` for Hermes.

## Pi -> Hermes command map

| Pi (gentle-pi) | Hermes (hermes-odd) | Notes |
|---|---|---|
| `gentle:agents` + agents card | `/odd_agents [id]` | hooks `subagent_start/stop` + `ctx.state` |
| `gentle:changes` | `/odd_changes` | `post_tool_call` on write/patch tools |
| `todo` card + ODD feature doc | `/odd_tasks [feature]` | reads `odd/tasks/*.md` |
| `gentle:status` | `/odd_status` | plugin, binary, review mode, prompt budget |
| `gentle:doctor` | `/odd_doctor` | binary version pin, SOUL size/truncation, markers |
| `gentle:commands` | `/odd_commands` | lists gentle commands |
| `gentle:review-mode` | `/odd_review_mode [status\|enable\|disable]` | wraps `gentle-ai review mode` |
| `gentle:persona` | `/odd_persona [gentleman\|neutral]` | swaps compact persona section |
| `gentle_review*` tools | `odd_review` tool (+ RDD skill) | CLI facade, opaque bindings only |
| `skill-registry:refresh` | Hermes native skill index | not needed |

## Tasks

- [x] T1 Plugin scaffold: `plugin.yaml`, `__init__.py` `register(ctx)`, package layout,
      unittest harness with a fake `ctx`, README (install, gentle-ai binary-only rule).
- [x] T1b Project packaging modeled on goldenSniperOS/hermes-telegram-voicenote:
      `pyproject.toml` (entry point `hermes_agent.plugins`, ruff config, dev extras),
      `CHANGELOG.md` (Keep a Changelog), CI (ruff + tests on 3.11/3.12 + build), release
      workflow (tag == pyproject == plugin.yaml == `__version__`, tag on main, CHANGELOG
      section, zip + SHA256SUMS), issue/PR templates, dependabot, CONTRIBUTING,
      SECURITY, CODE_OF_CONDUCT, `docs/design.md`, `scripts/smoke_e2e.py` (throwaway
      HERMES_HOME load).
- [x] T2 Compact ODD prompt section (<= 4000 chars, budget test) + `odd-workflow` skill
      (SDD-free delegation/memory/feature-continuity detail bound to `delegate_task`).
- [x] T2c Rename to `hermes-odd` (plugin, package `hermes_odd`, skills namespace
      `hermes-odd:*`, command prefix `/odd_*`, GitHub repo) and full attribution:
      README credits + non-affiliation notice (Gentle AI™ / gentle-shell / gentle-pi by
      Alan Buscaglia / Gentleman Programming; Hermes Agent by Nous Research),
      `THIRD_PARTY_NOTICES.md` with both upstream MIT notices (Gentleman Programming;
      Mario Zechner) and which files derive from each. No upstream marks as product name.
- [x] T2b Upstream support matrix: `upstream/upstream.lock.json` (last supported
      gentle-ai binary version/commit, gentle-shell/gentle-pi version/commit, and per
      component ODD/RDD/gentle-review: upstream source paths + sha256) and
      `upstream/SUPPORTED.md` (human matrix + porting triage log per upstream release:
      ported / not portable + reason / pending). Tests that every `derived-from` marker
      is indexed in the lock.
- [x] T3 Subagent tracking + `/odd_agents` viewer.
- [x] T4 `/odd_tasks` feature-task viewer.
- [x] T5 `/odd_changes` viewer.
- [x] T6 `/odd_status`, `/odd_doctor`, `/odd_commands`.
- [x] T7 `/odd_review_mode [status|enable|disable]` over the real `gentle-ai review mode`
      CLI + `rdd-review` skill: honest RDD on Hermes (native immutable review unavailable
      for this runtime -> report per candidate, continue under ordinary policy) + optional
      4R advisory review via `delegate_task`, clearly labeled as receipt-less.
- [ ] T8 BLOCKED ON UPSTREAM: native `odd_review` facade. gentle-ai 3.7.0 rejects
      `--agent hermes` (`immutable_review_transport_unsupported`; capability manifest
      advertises review transport only for claude-code, opencode, codex, pi). Never
      impersonate `--agent pi`. Ask upstream via the gentle-ai Discussion.
- [x] T9a First-run setup: `/odd_setup`, tool `odd_setup_apply`, skill `setup` (one
      `clarify`, <=5 questions), plugin `config_schema`, pending-setup hint in the section.
      Persona (no default; mentor rioplatense / mentor neutral / own text / none) is
      written ONLY as one `<!-- hermes-odd:persona -->` block at the top of SOUL.md, with
      backup and explicit confirmation; own wording, no Gentle AI identity or branding.
- [x] T9b SOUL cleanup (explicit consent, dry-run + backup): remove gentle-ai SDD blocks
      (sdd-orchestrator, sdd-session-preflight) and agent-routing; move engram-protocol and
      codegraph-guidance to lazy skills; keep remote-authorization.
- [ ] T10 Port portable skills + drift script over `upstream.lock.json` (reports changed
      upstream sources per component and new upstream commands/skills to triage) +
      scheduled CI.

## Acceptance criteria

- Plugin loads in Hermes and every command answers without invoking the model.
- Always-on prompt contribution <= 4000 chars, enforced by a test.
- Commands answer with the same plain text in the CLI and in gateways.
- No SDD content anywhere in the package.

## Checks

- `python3 -m unittest discover -s tests` (Hermes venv python).
- Live smoke: `hermes plugins list` shows the plugin enabled; commands reply in CLI.

## Delivery decision

- 2026-09-24: user asked to commit work-unit by work-unit directly to `main` (no
  feature branch).
- 2026-09-24: user delegated push, tags and GitHub releases to the agent (gh is
  authenticated as goldenSniperOS). Policy: push `main` after each verified work-unit
  commit; tag `vX.Y.Z` + release only at milestones, after version surfaces and
  CHANGELOG match and CI is green. Remote switched to HTTPS with a repo-local gh
  credential helper (SSH key unavailable).
- Release milestones: v0.1.0 = T1..T2b (plugin, ODD section, skills, packaging, support
  matrix); v0.2.0 = viewers T3..T6; v0.3.0 = RDD T7..T8; v0.4.0 = T9..T10.

## Progress

- 2026-09-25: Real SOUL cleanup applied with user consent (88,482 -> 9,862 chars; backup
  SOUL.md.hermes-odd-bak-20260925T210233Z). Repo made public; real `hermes plugins install
  goldenSniperOS/hermes-odd --enable` works after two fixes: manifest_version 1 (installer
  caps at 1) and test fixtures that tripped plugin_guard critical patterns. Smoke now runs
  the installer gates.
- 2026-09-25: T9b /odd_soul + odd_soul_apply (plan_id guard); remote-authorization lifted
  with upstream markers. Real SOUL dry run: 88,482 -> 9,862 chars (not applied, awaiting
  user). README install guide: gentle-ai binaries + `hermes mcp add` (verified in a temp
  HERMES_HOME), never gentle-ai's Hermes install.
- 2026-09-25: T9a setup: clarify always marks choices[0] "(Recommended)" (no opt-out),
  so the persona question is asked with no choices (options in the question text).
  Persona block written only at top of SOUL.md, backup + atomic write + confirmation.
- 2026-09-25: v0.3.0 released. Setup design approved with changes: persona goes to
  SOUL.md as a single hermes-odd managed block (user: personality belongs in SOUL);
  no recommended persona (user choice among equals).
- 2026-09-25: T7 honest RDD: gentle-ai 3.7.0 refuses `--agent hermes`
  (`immutable_review_transport_unsupported`; manifest advertises review transport and
  immutable executor only for claude-code, opencode, codex, pi). /odd_review_mode wraps
  the real mode switch and probes availability live (git repo only, always
  `--agent hermes`); skills rdd-review + rdd-review-lenses (4R advisory, receipt-less).
  T8 blocked on upstream; candidate fix to propose: host relay over Hermes `ctx.llm`
  (tool-less completion) as the constrained reviewer (to verify).
- 2026-09-25: **v0.2.0 released** (tag on c1e16c8): T6 5159ae1 (/odd_status, /odd_doctor,
  Built with Gentle-AI badge). CI caught a Linux-only path leak in /odd_doctor (fixed
  with regression test before tagging).
- 2026-09-25: T3 01ac068 (/odd_agents), T4 277b771 (/odd_tasks; projects learned from
  the section callable cwd; Engram mirror not queried: call_mcp opt-in + blocks the
  gateway loop), T5 (/odd_changes; captures write_file/patch via a second post_tool_call
  callback; abs path from result files_modified/resolved_path; shell edits not tracked).
- 2026-09-25: RDD relay failure root cause: Pi auth.json applies AWS_PROFILE/AWS_REGION
  (encora-continue) only to the main session; the in-process reviewer falls back to the
  [default] profile, which has no credentials. Lineages review-509c2e2a804627f6 (T1) and
  review-794c6354241a4f12 (T3) left open pending the user's choice.
- 2026-09-24: **v0.1.0 released** (tag on 8f67746 `chore(release): 0.1.0`, CI + Release
  workflows green; assets zip, wheel, sdist, SHA256SUMS; wheel verified to ship skills,
  upstream lock and notices). Commits: T1 ce942ab, T2 333cd5e, T2c 8bc4966,
  T1b 54591ff, T2b e6f8211. Upstream moved past pins (gentle-shell a923264 removes SDD
  surfaces and touches indexed odd/viewers sources) -> triage pending next sync.
- 2026-09-24: official channel to present the project upstream: gentle-ai GitHub
  Discussions (CONTRIBUTING: ideas/general conversation), then community Discord and
  Twitch stream chat with the Discussion link; post only after the repo is public.
- 2026-09-24: T2 done: section `hermes-odd-odd` 3354 chars; skills odd-workflow,
  odd-delegation (split for size), odd-feature-tracking; canonical
  `RenderRouting(model.AgentHermes)` vendored from gentle-ai f182ea2. Hermes facts:
  `delegate_task` has no toolsets arg (children inherit parent toolsets incl. MCP; cannot
  call clarify/memory/delegate_task/cronjob/send_message); Engram tools are
  `mcp__engram__*`; `clarify` exists (max 4 choices + Other; Telegram buttons).
- 2026-09-24: naming decision: upstream TRADEMARKS.md forbid confusingly similar names;
  user chose `hermes-odd` (commands `/odd_*`). Credit Gentleman Programming prominently.
- 2026-09-24: RDD review of T1 (lineage review-509c2e2a804627f6) blocked by Pi host
  relay environment: first no model routing for review lenses (fixed in
  ~/.pi/gentle-ai/models.json), then "Could not load credentials from any providers"
  for amazon-bedrock in the in-process reviewer. Tooling incident, not a code finding;
  lineage left open.
- 2026-09-24: Feasibility investigated (Engram `gentle-hermes/feasibility`). Branch
  `feat/hermes-port` created.
- 2026-09-24: T1 done. 13 unittest tests green. Hermes API findings for later tasks:
  - Commands register hyphenated (`gentle-commands`); gateways map `_`->`-`
    (gateway/run.py:19433), Telegram menu shows `/odd_commands`, CLI needs the hyphen
    form. Optional args hints must use `[...]` (`<...>` hides the command in Telegram).
  - Plugin skills: `ctx.register_skill(name, path)` -> namespaced `hermes-odd:<name>`,
    not in the always-on skills index; found via `skills_list`, loaded via `skill_view`.
  - Hooks: `subagent_start` (child_session_id, child_subagent_id `sa-*`, child_goal,
    child_role), `subagent_stop` (child_session_id, child_status, child_summary,
    tool_call_history, duration_ms; no subagent id), `post_tool_call` fires for child
    tools with `task_id == child_subagent_id`.
  - `register_system_prompt_section(id, content|callable(ctx_map), max_chars<=4000)`:
    rendered once per session (and on invalidation), skipped (not truncated) if too long;
    global cap 8000 chars across plugins.
  - `ctx.state`: JSON under `<HERMES_HOME>/plugin-data/...`, cross-process locked,
    persists across restarts, shared by CLI and gateway in the same profile.

## Evidence

(commit ids recorded per task)

## Next step

T10 portable skills + drift script + scheduled CI; then v0.4.0.
