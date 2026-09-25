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
`max(20000, min(context_length * 4 * 0.06, 500000))` characters (unless
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
the project's `odd/tasks/*.md` feature documents directly; state only holds
the list of known project roots.

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

### Feature documents (`/odd_tasks`)

`/odd_tasks` is a concept port of gentle-shell's todo card
(`extensions/gentle-todo.ts`, `lib/shell-todo.ts`) and the ODD feature
document view. The interactive todo tool is not ported: Hermes' native
`todo` is the session projection (see `skills/odd-feature-tracking`).

#### Project resolution

Command handlers receive only `raw_args` (verified: gateway
`gateway/run.py` calls `plugin_handler(user_args)`; the TUI
`tui_gateway/methods_tools.py` calls `handler(arg)`; the CLI calls the
handler the same way). There is no session, chat or cwd. In the gateway the
handler even runs after `reset_session_vars()` cleared the session cwd
contextvar and before `_set_session_env` binds the new session, so
`agent.runtime_cwd.resolve_agent_cwd()` would only return `TERMINAL_CWD` or
the gateway's launch directory. What Hermes does expose:

| Source | What it gives | Evidence |
|---|---|---|
| Prompt-section callable | `session_info["cwd"]` per new session: the session cwd override (TUI/ACP project switch), else `TERMINAL_CWD`, else `""` | `agent/system_prompt.py` `_plugin_session_info` -> `agent/runtime_cwd.py` `resolve_context_cwd` |
| `TERMINAL_CWD` in the command process | CLI (local backend): its launch directory, always exported (`cli.py` load config: `terminal_config["cwd"] = os.getcwd()`); gateway: `terminal.cwd`, or `MESSAGING_CWD`, or the home directory for placeholders (`gateway/run.py` + `gateway/cwd_placeholder.py`); non-local backends: a sandbox path or unset | `cli.py`, `gateway/run.py`, `gateway/cwd_placeholder.py` |
| `os.getcwd()` | the process launch directory | |

hermes-odd therefore combines:

1. **Known projects.** The `hermes-odd-workflow` section is registered as a
   callable. On each render (once per new session) it passes `session_info`
   to `ProjectStore.on_section_render`, which records the git top-level of
   `cwd` (nearest ancestor with `.git`, no subprocess; the directory itself
   when there is none; an empty `cwd` falls back to `os.getcwd()` of the
   rendering process, the directory Hermes then uses for context files). The
   state key `projects.v1` (schema `hermes-odd.projects/v1`) holds at most 10
   entries `{root, platform, last_seen}`, most recent first, deduplicated by
   root. The callable returns exactly `ODD_SECTION.strip()`; the recorder is
   wrapped so a failure is logged at debug level and never makes Hermes skip
   the section (Hermes skips a section whose callable raises). Tests and the
   smoke assert the rendered text is byte-identical.
2. **The command process's own directories**: `TERMINAL_CWD` and
   `os.getcwd()`, each mapped to its git top-level.

Candidates are deduplicated by resolved path and only directories holding
`odd/tasks/` are shown. This makes `/odd_tasks` in Telegram show the
projects the agent actually worked in (any platform of the same profile),
and the CLI show the current project even before a session was rendered.
Limits: a project is only known after a session rendered its prompt there;
for non-local terminal backends the path is often a sandbox path that does
not exist on the host and is filtered out.

#### Engram mirror: not read

The Engram mirror (topic `odd/<feature>/tasks`) is deliberately not used by
`/odd_tasks`. `PluginContext.call_mcp(server, tool, arguments, timeout)`
(`hermes_cli/plugins.py`) exists and is synchronous, but:

- it is **default-off**: each server must be listed by the operator under
  `plugins.entries.hermes-odd.mcp_allowlist` in `config.yaml`, otherwise it
  raises `PermissionError`; hermes-odd never edits user config;
- it **blocks the caller** up to the timeout (clamped to 1-600 s) through
  `tools.mcp_tool._make_tool_handler`, and gateway plugin commands run inline
  on the gateway's asyncio event loop, so a slow or reconnecting Engram
  server would stall every chat of the gateway (a lazy server may even be
  spawned on first use);
- the command does not know the Engram project name for a chat, and search
  results are free text that would have to be parsed back into a document;
- the mirror is a recovery copy, not the authority; the file is.

Revisit if Hermes adds an async, non-blocking MCP path for commands. Until
then the agent itself reads the mirror during the resume protocol.

#### Parsing and output

`hermes_odd/feature_docs.py` only matches lines; it never executes or
evaluates content. Title: the first `# ` heading (`Feature:` stripped), else
the file stem. Tasks: top-level checkboxes (`- [ ]`, `- [x]`, `[X]`, `*`/`+`
bullets) under `## Tasks` until the next level-1/2 heading; without that
heading, every top-level checkbox. Deeper-indented items are nested and
ignored, indented non-checkbox lines are continuations (the title is the
first line), fenced code is skipped, CRLF and a BOM are accepted. The id is
the first token when it looks like one (`T1`, `T2b`, `10`, `**T3**`). Next
step: the first paragraph under `## Next step(s)`. Limits: 256 KB per file
(the rest ignored, marked truncated), 50 newest `*.md` files per project,
symlinks never followed; an unreadable file shows as `⚠ <feature>:
unreadable (<error type>)`.

Output is plain text under 3,500 characters (`… N more` when cut), without
full home paths (only the last two path components):

- no arguments: per project (`name (…/parent/name)`), each feature as
  `▰▰▰▰▰▱▱▱▱▱ 6/13 <feature> · <age>` plus the next open task, newest
  first;
- `<feature prefix>` or `project/feature`: title, progress, every task with
  `✓` / `○` (the next one marked `← next`), the next step and the file; an
  exact name wins over a prefix, then a project name (or prefix) lists that
  project; ambiguous and not-found answers name the candidates.

### Changed files (`/odd_changes`)

`/odd_changes` is a concept port of gentle-shell's Gentle Changes
(`lib/session-changes.ts`, `lib/shell-changes-view.ts`, the Gentle Changes
sections of `README.md` and `docs/gentle-shell.md`): what the agent changed,
attributed and counted, without repository scans or background polling. No
upstream code or text is copied. Upstream keeps bounded before/after
snapshots and shows a two-pane diff viewer; hermes-odd keeps no content and
answers in plain text.

#### Capture model

Capture comes only from `post_tool_call` for the Hermes file-mutating tools
(verified in `tools/file_tools.py`; there is no notebook or multi-edit
tool):

| Tool | Arguments | Success result (JSON) |
|---|---|---|
| `write_file` | `path`, `content` (full new content) | `bytes_written`, `verified`, `resolved_path`, `files_modified: [resolved_path]` |
| `patch` (replace, default) | `path`, `old_string`, `new_string`, `replace_all` | `success`, `diff` (`difflib` unified diff, `a/<abs>` / `b/<abs>` headers), `files_modified`, `resolved_path`; `no_change` when already applied |
| `patch` (`mode: "patch"`, V4A) | `patch` (`*** Update/Add/Delete/Move File:` sections) | as above, one diff section per file, `files_modified` with every resolved path, `files_created`, `files_deleted` |

`execute_code`'s `hermes_tools.write_file` / `patch` go through
`handle_function_call`, so they arrive under the same tool names. Terminal
and shell commands, and scripts that write files directly, are not captured
(same coverage as upstream); every output says so.

- **Success.** Only `status == "ok"` (Hermes sets `error` when the result
  JSON has an `error` key) and a result that is not `success: false` or
  `no_change`.
- **Paths.** The absolute paths come from the result's `files_modified` /
  `resolved_path`: Hermes resolved them with the task's live terminal cwd,
  the registered session cwd, or `TERMINAL_CWD`, which a plugin cannot see
  (`post_tool_call` has no cwd). Only when the result is unparsable is
  `args["path"]` used: `~` expanded, relative paths joined to an absolute
  `TERMINAL_CWD`, else `os.getcwd()` of the hook process. That fallback
  ignores a terminal `cd` and container backends' paths; it is rare because
  every successful Hermes write reports its resolved path.
- **Project.** The git top-level of the file's own directory (nearest
  ancestor with `.git`, `projects.git_root`, no subprocess), so a nested
  repository is attributed to itself. Outside git the project is the file's
  directory.
- **Line counts**, computed at capture time, only numbers kept. `patch`: from
  the result diff, consumed by hunk lengths (added = new length minus
  context, removed = old length minus context), so content that looks like
  a header and `difflib`'s missing-final-newline joins are counted right;
  without a usable diff, from `old_string`/`new_string` (line diff; CRLF and
  a trailing newline are normalized) or the V4A `+`/`-` lines. `write_file`:
  the written lines as added and removed **unknown** (`−?`), because an
  overwrite's old content is never in the call.
- **Attribution.** `task_id` is the subagent id (`sa-*`) for
  `delegate_task` children and a per-run UUID for the main agent, so
  `sa-*`/`sx-*` or an id the agent store saw start is a subagent, anything
  else is `main`. The subagent's role comes from the `/odd_agents` record at
  capture time; its goal is looked up when the detail is rendered. The
  platform is the parent session's (`on_session_start`) or the child record's.

#### Hook registration

Hermes' `register_hook` appends to a per-hook callback list, and
`invoke_hook` bounds each callback with `plugins.hook_callback_timeout`, skips
a callback that is still running from a previous call, and suppresses it for a
while after a timeout, **per callback**. Change capture is therefore its own
`post_tool_call` callback, next to the subagent tracker, so one never delays
or suppresses the other. Its fast path returns before any I/O for tools other
than `write_file`/`patch` and for non-`ok` calls. Limit: when the agent runs
file tools concurrently, a call whose post hook arrives while the previous
one is still being recorded is skipped by Hermes (no row).

#### Store, privacy, limits

`hermes_odd/changes.py` keeps schema `hermes-odd.changes/v1` under the
state key `changes.v1`, with the same fallback and concurrency model as the
agent store. One entry per file: absolute path, project root, relative path,
whether it is in git, operation count, lines added and removed (plus a
"removed unknown" flag), first/last time, last tool, attribution (at most 5:
id, role, count, last time), last session id and platform, and a 12-entry
timeline (time, tool, +/−, attribution). At most 200 files (least recently
changed dropped first); entries not changed for 7 days are dropped.

File content, diffs, `old_string`/`new_string`/`patch` text and tool results
are never stored or shown; tests push a fake secret through every one of
them. Output never prints full home paths (a project is shown by name and
its last two path components).

#### Output

Plain text under 3,500 characters (`… N more` when cut):

- no arguments: the last 24 h grouped by project, newest first, with
  per-project totals and one line per file,
  `+A −R  path  (n edits · by main, sa-xxxxxxxx · 3m ago)`, and a footer on
  the capture scope; `all` covers the 7 days kept;
- a file (exact path, name, `project/path`, then a path prefix or
  substring): the detail with attribution, subagent goals, platform and
  session, the timeline, and, only inside a git repository with `git`
  available, the file's current uncommitted count from
  `git -c core.fsmonitor=false -C <root> diff --no-ext-diff --no-textconv
  --numstat -- <rel>` (no shell, minimal environment `PATH`/`HOME`/`LC_ALL`
  and non-interactive git variables, 2 s timeout; only the two numbers are
  read). Ambiguous and not-found answers name the candidates;
- a project name (or prefix): that project's files over 7 days;
- `clear`: forget every recorded change and say how many.

## Health commands (`/odd_status`, `/odd_doctor`)

Concept ports of gentle-pi's `gentle:status` and `gentle:doctor`
(`extensions/gentle-ai.ts`): the Pi versions report Pi package assets,
OpenSpec, model routing and the dev binary; the Hermes versions report what
matters here. No upstream code or text is copied. The RDD wording follows
gentle-ai's own `receipt-driven development: <mode> (decided by <source>)`.
The gentle-shell RDD sidebar labels (`lib/review-sidebar-state.ts`, commits
`2ac9c68` and `8becfd8`) describe a review lineage (`Reviewing`, `Awaiting
consent`, `Approved · awaiting acknowledgement`, ...) and are not applicable
until native review exists on Hermes (T8, blocked upstream); the status
reports the review *mode* and the native review availability only.

### What `register` records

`register(ctx)` fills a `RuntimeInfo` (`hermes_odd/runtime.py`) as each step
succeeds: section registered and its length, the skills directory (`wheel`
= `hermes_odd/_skills`, `clone` = `<plugin>/skills`) and registered skill
names, hooks registered out of expected (4 agent hooks + 1 change hook),
commands registered, and the stores (whose memory-fallback flag the doctor
reports). The commands read this record instead of guessing.

### Probes (`hermes_odd/probes.py`)

Only three subcommands of the user's `gentle-ai` binary are run by the
read-only commands: `gentle-ai version` (output `gentle-ai X.Y.Z`),
`gentle-ai review mode status [--cwd <repo>] --json` (verified with
`gentle-ai review mode --help`: `status` is read-only; the JSON is schema
`gentle-ai.review-mode/v1` with `status.effective` `on`/`off`,
`status.source`, `status.global` and `status.clone_local`), and the native
review availability probe (see [RDD on Hermes](#rdd-on-hermes-odd_review_mode)).
Every run has no shell, stdin closed, a 3 s timeout and a minimal environment
(`PATH`, `HOME` for gentle-ai's own config, `LC_ALL=C`, `NO_COLOR=1`).
Binaries are found with `shutil.which` plus a scan of every `PATH` entry,
deduplicated by real path (a Homebrew symlink and its Cellar target count
once); version probes run in parallel, and the doctor runs the RDD mode and
the native review probe in parallel, so it stays within about 6 s in total. A
shared `Prober` caches results for 60 s: `/odd_status` runs the cached
version and native review probes and shows the RDD mode only if
`/odd_doctor` or `/odd_review_mode` cached it for the same repository. The
repository is the git root (nearest `.git`, no subprocess) of `TERMINAL_CWD`,
then `os.getcwd()`; gateways run from their launch directory, so the RDD mode
of a project is usually known only from the CLI (or from `/odd_review_mode
<project>`).

### SOUL.md check (`hermes_odd/soul.py`)

The home is `hermes_constants.get_hermes_home()` when Hermes already imported
it (profile-aware), else `HERMES_HOME`, else `~/.hermes`. The size is measured
as Hermes does (`load_soul_md`: `strip()`, then a leading BOM is dropped).
Managed blocks are `<!-- gentle-ai:<name> -->` … `<!-- /gentle-ai:<name> -->`
(nesting-aware; an unclosed block runs to the end). The cap mirrors
`agent/prompt_builder.py` (`CONTEXT_FILE_MAX_CHARS = 20_000`,
`_CONTEXT_FILE_CHARS_PER_TOKEN = 4`, `_CONTEXT_FILE_WINDOW_FRACTION = 0.06`,
`_CONTEXT_FILE_DYNAMIC_CEILING = 500_000`, head 0.7 / tail 0.2, an explicit
`context_file_max_chars` wins). The context length is `model.context_length`,
else the `context_length_cache.yaml` entry `<model.default>@<base_url>` (or
the single value of that model); both files are read by a line matcher for
exactly those keys, no YAML and nothing else kept. When unknown the doctor
shows the cap for 128k / 200k / 1M. A top-level block is `dropped` when it
lies entirely in the lost middle and `partly` when it overlaps it. SOUL
content is never returned. The migration that strips the blocks is T9.

### Privacy and limits

Never read: `.env`, `auth.json`, credentials. Paths under the home show as
`~/…`, others as their last three components. The `ctx.state` probe writes
the key `doctor.probe`, reads it back and restores the previous value.
`/odd_status` stays under 1,500 characters and `/odd_doctor` under 3,500.
Each status line and each doctor check is guarded: a failure becomes a line,
never an exception.

## RDD on Hermes (`/odd_review_mode`)

### Upstream limitation (verified)

gentle-ai compiles the runtimes eligible for native immutable review into its
capability manifest (`internal/agents/capabilitymanifest/manifest.go`,
`ContractReviewTransportV1` / `ContractImmutableReviewExecutorV1`): they are
advertised only when a provider can launch a fresh, constrained reviewer and
prove that boundary before review START. gentle-ai 3.7.0 advertises them for
claude-code, opencode, codex and pi; the hermes adapter's exposures are
dormant. `internal/cli/review_transport_capability.go` narrows that set per
environment (pi only with its host relay handshake, opencode only on a V1
runtime), and a refusal lists the runtimes eligible in the probing
environment. Verified against the 3.7.0 binary:

```text
$ gentle-ai review status --cwd . --contract gentle-ai.review-integration/v2 --agent hermes --next-transition
schema gentle-ai.review-integration.failure/v2, phase preflight,
code immutable_review_transport_unsupported, mutation_outcome not_started,
next_action stop, cause "... supported immutable review runtimes: ..."
```

hermes-odd never passes another runtime's identity to gentle-ai: posing as
`pi` (or any runtime) would break the review contract and make receipts
meaningless. The native review facade (T8) waits on upstream eligibility.

### Availability probe

`Prober.native_review` runs exactly that command, always with `--agent
hermes` (`probes.AGENT_ID`; a test scans the package for any other
`--agent` value). It runs only when `--cwd` is inside an existing git
repository, because `review status` may initialize Git in a genuinely
unversioned directory once a runtime is accepted: the command's own
repository, else the most recent known project with `.git`. The result is
cached 60 s per binary (eligibility does not depend on the repository) and
classified as `unavailable` (failure schema + `immutable_review_transport_unsupported`),
`available` (exit 0 with a non-failure JSON object: a future gentle-ai that
accepts Hermes; hermes-odd then says "available (detected)", points out that
the facade is pending and starts nothing), or `unknown` (another code,
garbage, timeout). The wording names the compiled set from the lock
(`review-contract.immutable_review_runtimes`) unless gentle-ai reports a
runtime outside it; `/odd_review_mode` also shows the runtimes eligible in
the probing environment.

### The command

`/odd_review_mode [status|enable|disable] [global|clone] [project]`:

- the target is a known project (exact name, then prefix; ambiguous and
  not-found answers name the candidates) among the recorded `/odd_tasks`
  projects and the process directories that are git repositories, else the
  process repository;
- `status` (default) runs `review mode status --cwd <root> --json` (without
  `--cwd` when the process is in no git repository: gentle-ai then reports
  the global source only) plus the availability probe;
- `enable`/`disable` run `gentle-ai review mode <action> --scope
  <global|clone> [--cwd <root>] --json` once (5 s timeout, never cached,
  cached modes dropped). The scope must be typed explicitly; `clone` without
  a resolvable git repository is refused before anything runs. These are the
  only writes hermes-odd makes to gentle-ai state, and only for the user's
  own typed command. Errors show gentle-ai's message on one line with the
  home as `~` and other absolute paths shortened.

Output is plain text under 3,500 characters.

### Skills

`hermes-odd:rdd-review` is the protocol: RDD concepts (frozen candidate,
risk-scoped lenses, bounded correction, outcome derived from Git; a review
outcome never authorizes delivery), the candidate (one work-unit commit or PR
slice), and on Hermes: when RDD is on, report "native review unavailable on
Hermes (gentle-ai runtime eligibility)" once per candidate, record it in the
feature document, and continue under ordinary repository policy. The
optional advisory 4R review (on request, or an accepted offer for a medium or
high risk candidate) runs one read-only `delegate_task` child per lens over
`git show <sha>`, with the charters of `hermes-odd:rdd-review-lenses`
(condensed from gentle-shell `assets/agents/review-*.md` and
`assets/chains/4r-review.chain.md`, without the Pi ledger envelope,
`gentle_review_scope` tool or controller authority). Only candidate-caused
BLOCKER/CRITICAL findings block, and the result is labeled "advisory review —
no receipt". The skills are split so the charters load only when a review
actually runs.

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
- Impersonating another review runtime or producing receipts outside
  gentle-ai.
