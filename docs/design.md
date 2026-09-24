# Design: hermes-odd

hermes-odd brings the Organic Driven Development (ODD) and receipt-driven
development (RDD) workflows of gentle-ai and gentle-shell (npm `gentle-pi`) to
Hermes Agent. This document records the architecture, the constraints that
shaped it, and the Hermes API facts it depends on. The live task plan is the
ODD feature document kept by the maintainer; this file only records decisions
that already hold.

## Problem

gentle-ai's own Hermes integration writes everything into `~/.hermes/SOUL.md`.
Measured on the maintainer's install: **88,483 characters (~22k tokens) sent
with every message, 56% of it SDD**, which hermes-odd does not use.

Hermes truncates context files instead of rejecting them
(`agent/prompt_builder.py`): the cap is
`max(20000, context_length * 4 * 0.06)` characters (unless
`context_file_max_chars` is pinned), and a truncated file keeps the first 70%
and the last 20% of the cap, dropping the middle.

| Model context | Cap (chars) | Kept (head + tail) | Dropped from SOUL.md |
|---|---|---|---|
| 128k | 30,720 | 21,504 + 6,144 = 27,648 | 60,835 (69%) |
| 200k | 48,000 | 33,600 + 9,600 = 43,200 | 45,283 (51%) |

The ODD routing block sits in the dropped middle, so on common 128k-200k models
the workflow is silently lost while most of the budget goes to SDD.

The Pi features of gentle-shell (agents view, changes, feature todo, review
mode, doctor, status) are Pi TUI features and do not exist in Hermes at all.

## Architecture: plugin plus lazy skills

hermes-odd is a standard Hermes plugin (`plugin.yaml` + `register(ctx)`) that
contributes three kinds of surface:

1. **One compact always-on prompt section**, `hermes-odd-workflow`, registered
   with `ctx.register_system_prompt_section`. It holds only what must be in
   every turn: the seven ODD steps, the mandatory `delegate_task` triggers,
   resume order, blocking-question and language rules, and pointers to the
   skills.
2. **Lazy plugin skills** (`skills/<name>/SKILL.md`), registered with
   `ctx.register_skill` and exposed as `hermes-odd:<name>`. They never enter
   the always-on skills index; the agent loads them with `skill_view` when the
   section tells it to. Detail lives here: `odd-workflow`, `odd-delegation`,
   `odd-feature-tracking` today; `rdd-review` with RDD.
3. **Plain-text slash commands** (`/odd_*`) whose handlers never call the
   model, so the CLI, the TUI and every gateway get identical output.

`register(ctx)` never raises: every step is guarded and a missing optional
`ctx` method is skipped with one warning, so an API change in Hermes degrades
hermes-odd instead of breaking Hermes startup.

### Prompt budget

| Limit | Value | Source |
|---|---|---|
| Hermes max per section | 4,000 chars | `MAX_SYSTEM_PROMPT_SECTION_CHARS`; longer sections are **skipped**, not truncated |
| Hermes max across all plugins | 8,000 chars | `MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS`, checked in `render_system_prompt_sections` |
| hermes-odd test budget | 3,800 chars | `SECTION_BUDGET_CHARS`, enforced by `tests/test_prompt_and_skills.py` |
| Current section | ~3.3k chars | measured by the smoke |

Because an oversized section disappears entirely, the test budget keeps 200
characters of headroom, and anything that does not have to be read every turn
moves into a skill. The section is rendered once per session (and on
invalidation), so it is effectively free after the first turn's cache.

## Hermes API facts relied on

Verified against the hermes-agent source; later tasks depend on them.

- **Commands** register under the key produced by `register_command`
  (lowercased, `/` stripped, spaces to `-`). The CLI and TUI look that key up
  verbatim; gateways look up `command.replace("_", "-")`.
- **Plugin skills**: `ctx.register_skill(name, path)` makes
  `hermes-odd:<name>`, found with `skills_list` and loaded with `skill_view`;
  not part of the always-on skills index.
- **Prompt sections**: `register_system_prompt_section(id, content |
  callable(session_info), max_chars <= 4000)`; rendered once per session;
  oversized sections are skipped; 8,000-char aggregate cap across plugins.
- **Delegation**: `delegate_task` has no toolsets argument; children inherit
  the parent's toolsets including MCP, and cannot call `clarify`, `memory`,
  `delegate_task`, `cronjob` or `send_message`.
- **Engram** tools are exposed as `mcp__engram__*`.
- **`clarify`** exists: at most 4 choices plus "Other"; rendered as buttons on
  Telegram.
- **Hooks** (for the viewers) are called with keyword arguments
  (`invoke_hook(name, **kwargs)`, plus `telemetry_schema_version`):
  `subagent_start` (parent_session_id, parent_turn_id, parent_subagent_id,
  child_session_id, child_subagent_id `sa-<index>-<hex8>`, child_role,
  child_goal); `subagent_stop` (parent_session_id, parent_turn_id,
  child_session_id, child_role, child_summary, child_status `completed` |
  `failed` | `interrupted` | `timeout` | `error`, tool_call_history,
  duration_ms; no subagent id, always run on the parent thread);
  `post_tool_call` (tool_name, args, result, task_id, session_id,
  tool_call_id, turn_id, duration_ms, status `ok` | `error`, error_type,
  error_message) also fires for child tools, with
  `task_id == child_subagent_id`, on a timeout-bounded worker;
  `on_session_start` (session_id, model, platform) fires only for brand-new
  sessions. `pre_tool_call` fails closed on timeout, so hermes-odd never
  registers it.
- **State**: `ctx.state` is JSON under `<HERMES_HOME>/plugin-data/...`,
  cross-process locked, persistent across restarts, and shared by the CLI and
  the gateway of the same profile. Its API is `get(key, default)` and
  `set(key, value)`; each call re-reads the file under the lock and `set`
  enforces a 10 MB quota. There is no atomic update across a `get` and a
  `set`.
- **Subagent control**: `ctx.subagent_lifecycle` only cancels children it
  launched itself (its handles are HMAC-bound to its own `launch` and to the
  active parent in the calling context); `delegate_task` children are not in
  its registry. `delegate_task` `action=stop` is a model-facing tool scoped to
  the calling conversation's own spawn tree, and
  `tools.delegate_tool.interrupt_subagent` is an internal, unscoped,
  in-process function. Command handlers receive only `raw_args`, so a plugin
  command cannot stop a child safely; `/odd_agents` does not offer stop.
- **Gateway replies**: plugin command text is returned as the reply; the
  Telegram adapter splits messages over 4,096 characters, but hermes-odd keeps
  command output under 3,500 characters so it never needs splitting.

## Command naming

A command spec name is the Telegram-safe form users type in gateways
(`odd_commands`, `[a-z0-9_]`, at most 32 characters, no leading, trailing or
doubled `_`). hermes-odd registers the hyphenated key (`odd-commands`):

- gateways accept `/odd_commands` and `/odd-commands` (underscores are mapped
  to hyphens before lookup);
- the Telegram menu shows `/odd_commands` (Hermes shows `-` as `_`);
- the CLI needs the exact key, `/odd-commands`.

Optional arguments use `[...]` in `args_hint`; a hint starting with `<` marks
the command as requiring an argument and hides it from the Telegram menu.

## State model

Viewer state (subagent runs, changed files) is written by hooks into
`ctx.state` and read by the commands. Because `ctx.state` is per profile,
locked across processes and persistent, a subagent started from Telegram is
visible to `/odd-agents` in the CLI of the same profile, and survives a
gateway restart. Feature tasks are not duplicated in state: `/odd_tasks` reads
the project's `odd/tasks/*.md` feature documents directly.

### Subagent records (`/odd_agents`)

`hermes_odd/agents.py` keeps one JSON document, schema
`hermes-odd.agents/v1`, under the state key `agents.v1`: a list of records,
one per `delegate_task` child. It is a concept port of gentle-shell's Gentle
Agents `TaskRecord` (id, agent, label, status, timestamps, last step, last
activity, tool calls, result or error); no upstream code or text is copied.

| Field | Source |
|---|---|
| `subagent_id`, `child_session_id`, `parent_session_id`, `parent_subagent_id`, `role`, `goal` (200 chars) | `subagent_start` |
| `platform` | `on_session_start` of the parent session (kept in memory), or the parent child's record for nested children; empty for resumed sessions |
| `status` | `running` on start; `subagent_stop` `child_status` maps `completed`, `failed`/`error` -> `failed`, `interrupted`, `timeout` -> `timed_out`, anything else -> `failed`; `stale` from pruning |
| `started_at`, `ended_at`, `duration_ms`, `last_activity_at` | hook arrival times; `duration_ms` from `subagent_stop` |
| `tool_calls`, `last_tool` (name + ok/error), `timeline` (last 15: name, ok/error, duration, time) | `post_tool_call` whose `task_id` is a child this process started |
| `summary` (1,500 chars), `error` | `subagent_stop` (`error` is only `child status: <raw>`) |

- **Correlation.** `subagent_stop` has no subagent id, so it matches the
  record by `child_session_id`. A stop with no known start creates a record
  with a synthetic `sx-<hash>` id and backfills the tool count and timeline
  from the metadata-only `tool_call_history` (names and ok/error only).
- **Hot path.** `post_tool_call` fires for every tool call. The store keeps
  the ids of the children it saw start in memory (a child always runs in its
  parent's process), so a parent or unrelated tool call returns without
  touching state.
- **Retention.** At most 50 records (oldest finished dropped first). Records
  not `running` are dropped 24 h after they ended (or their last activity).
  A record still `running` 6 h after it started is marked `stale` (kept, then
  dropped by the 24 h rule).
- **Failure.** Hook handlers never raise and log at debug level. When
  `ctx.state` is missing or a `get`/`set` fails (corrupt file, quota), the
  store switches to an in-memory backend for the rest of the process with one
  warning.
- **Concurrency.** A read-modify-write is a `get` plus a `set`, serialized by
  a process-local lock. Two processes of one profile writing at the same
  moment can drop one update; this is rare because the hooks for a child all
  fire in its parent's process.

### Privacy

Records never contain tool arguments, tool results, tool error messages or
anything derived from them: per tool call only the name, ok/error, duration
and time. `tool_call_history`'s `tool_input` summary is ignored. The goal is
the parent's own delegation text, truncated to 200 characters; the summary is
the child's own final summary, truncated to 1,500. Tests feed a fake secret
through `args`, `result`, `error_message` and `tool_input` and assert it is
absent from the stored state and from every `/odd_agents` output.

### Output

`/odd_agents` answers in plain text (no Markdown tables) under 3,500
characters: a count line, then up to 10 blocks (running first, newest
first) of `<glyph> <short id> <role> · <elapsed>`, the goal on one line, and
`last: <tool> <ok|error> · <n> tools`. Glyphs: `●` running, `✓` completed,
`✗` failed, `⊘` interrupted, `⏱` timed out, `○` stale. `/odd_agents <id
prefix>` matches the full id or its 8-hex tail; `all` lists up to 50 one-line
entries. Anything cut ends with `… N more`.

## Install layouts and skill discovery

hermes-odd supports two install layouts:

| Layout | How | Where skills live |
|---|---|---|
| git clone | `hermes plugins install goldenSniperOS/hermes-odd` | `<plugin dir>/skills/` (repository root) |
| wheel | `pip install` of the built wheel; Hermes finds it through the `hermes_agent.plugins` entry point | `hermes_odd/_skills/` inside the package |

`skills/` and `upstream/` stay at the repository root, where the git-clone
install (the primary one) expects them next to `plugin.yaml`. `pyproject.toml`
maps them into data-only subpackages (`hermes_odd._skills`,
`hermes_odd._upstream`) with `package-dir`, so the wheel carries them without
moving any file. `hermes_odd.skills.resolve_skills_dir` checks
`hermes_odd/_skills` first and the repository-root `skills/` second, and uses
the first one that contains a `SKILL.md`. If neither exists (a broken or
partial install), registration logs one warning and registers no skills; it
never raises.

## Upstream sync model

hermes-odd tracks upstream by pinned commits, not by following branches:

- every derived file carries `derived-from` markers (upstream repository,
  40-character commit, source path), and `THIRD_PARTY_NOTICES.md` lists it;
  tests enforce both;
- `upstream/odd-routing-hermes.canonical.md` is a verbatim render of gentle-ai's
  `RenderRouting(model.AgentHermes)` with its SHA-256, for drift comparison;
- `upstream/upstream.lock.json` (schema `hermes-odd.upstream-lock/v1`) pins
  the supported gentle-ai release, commit and minimum binary version and the
  gentle-shell release, commit and `gentle-pi` version, and indexes every
  upstream source per component (`odd`, `rdd`, `review-contract`, `viewers`)
  with its SHA-256 at the pin; `hermes_odd.upstream.load_lock()` reads it from
  `hermes_odd/_upstream` (wheel) or `upstream/` (git clone), the same order as
  the skills. `upstream/SUPPORTED.md` keeps the human support matrix, the sync
  procedure and a triage log per upstream release (ported / not portable and
  why / pending); tests cross-check lock, markers, notices and canonical
  render;
- **pending (T10):** a drift script over the lockfile reports changed upstream
  sources and new upstream commands or skills to triage, run by scheduled CI.

Port requests use the **Upstream port request** issue template. SDD, Pi-only
aesthetics and Pi runtime plumbing are recorded as not portable.

## Non-goals

- SDD in any form.
- Pi-only aesthetics (themes, banners, animations, TUI widgets, shortcuts).
- Pi-only runtime plumbing (dev binary, telemetry, Pi model profiles).
- Running `gentle-ai install` or `gentle-ai sync` for Hermes; RDD uses only the
  `gentle-ai` binary's `review` CLI.
