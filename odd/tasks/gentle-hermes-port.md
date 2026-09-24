# Feature: gentle-hermes port (ODD + RDD for Hermes)

## Objective

Ship `gentle-hermes`: a Hermes plugin plus a set of lazy-loaded skills that brings the
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
  `hermes plugins install goldenSniperOS/gentle-hermes`.
- Compact always-on ODD section via `ctx.register_system_prompt_section` (<= 4000 chars).
- Lazy skills: ODD detail (delegation, memory/feature continuity, skills protocol), RDD
  orchestration for Hermes, plus portable gentle-shell skills.
- Slash commands answered as plain messages (no LLM call), compatible with CLI/TUI and
  every gateway: `/gentle_agents`, `/gentle_changes`, `/gentle_odd` (feature tasks),
  `/gentle_status`, `/gentle_doctor`, `/gentle_commands`, `/gentle_review_mode`,
  `/gentle_persona`.
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

| Pi (gentle-pi) | Hermes (gentle-hermes) | Notes |
|---|---|---|
| `gentle:agents` + agents card | `/gentle_agents [id]` | hooks `subagent_start/stop` + `ctx.state` |
| `gentle:changes` | `/gentle_changes` | `post_tool_call` on write/patch tools |
| `todo` card + ODD feature doc | `/gentle_odd [feature]` | reads `odd/tasks/*.md` |
| `gentle:status` | `/gentle_status` | plugin, binary, review mode, prompt budget |
| `gentle:doctor` | `/gentle_doctor` | binary version pin, SOUL size/truncation, markers |
| `gentle:commands` | `/gentle_commands` | lists gentle commands |
| `gentle:review-mode` | `/gentle_review_mode [status\|enable\|disable]` | wraps `gentle-ai review mode` |
| `gentle:persona` | `/gentle_persona [gentleman\|neutral]` | swaps compact persona section |
| `gentle_review*` tools | `gentle_review` tool (+ RDD skill) | CLI facade, opaque bindings only |
| `skill-registry:refresh` | Hermes native skill index | not needed |

## Tasks

- [x] T1 Plugin scaffold: `plugin.yaml`, `__init__.py` `register(ctx)`, package layout,
      unittest harness with a fake `ctx`, README (install, gentle-ai binary-only rule).
- [ ] T2 Compact ODD prompt section (<= 4000 chars, budget test) + `odd-workflow` skill
      (SDD-free delegation/memory/feature-continuity detail bound to `delegate_task`).
- [ ] T3 Subagent tracking + `/gentle_agents` viewer.
- [ ] T4 `/gentle_odd` feature-task viewer.
- [ ] T5 `/gentle_changes` viewer.
- [ ] T6 `/gentle_status`, `/gentle_doctor`, `/gentle_commands`.
- [ ] T7 `/gentle_review_mode` + `rdd-review` skill (Hermes orchestration contract).
- [ ] T8 `gentle_review` tool facade over `gentle-ai review` (lifecycle, consent relay).
- [ ] T9 `/gentle_persona` + SOUL migration command (backup, dry-run).
- [ ] T10 Port portable skills + `upstream.lock.json` + drift script.

## Acceptance criteria

- Plugin loads in Hermes and every command answers without invoking the model.
- Always-on prompt contribution <= 4000 chars, enforced by a test.
- Commands produce identical plain-text output in CLI and gateway contexts.
- No SDD content anywhere in the package.

## Checks

- `python3 -m unittest discover -s tests` (Hermes venv python).
- Live smoke: `hermes plugins list` shows the plugin enabled; commands reply in CLI.

## Progress

- 2026-09-24: Feasibility investigated (Engram `gentle-hermes/feasibility`). Branch
  `feat/hermes-port` created.
- 2026-09-24: T1 done. 13 unittest tests green. Hermes API findings for later tasks:
  - Commands register hyphenated (`gentle-commands`); gateways map `_`->`-`
    (gateway/run.py:19433), Telegram menu shows `/gentle_commands`, CLI needs the hyphen
    form. Optional args hints must use `[...]` (`<...>` hides the command in Telegram).
  - Plugin skills: `ctx.register_skill(name, path)` -> namespaced `gentle-hermes:<name>`,
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

T2 compact ODD prompt section + odd-workflow skill.
