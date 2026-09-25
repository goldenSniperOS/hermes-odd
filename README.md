# hermes-odd

Based on the ODD and RDD workflows of
[Gentle AI™](https://github.com/Gentleman-Programming/gentle-ai) and
[gentle-shell](https://github.com/Gentleman-Programming/gentle-shell)
(npm `gentle-pi`) by Alan Buscaglia / Gentleman Programming, running on
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
Independent community project; see [Not affiliated](#not-affiliated).

<div align="center">

<a href="https://github.com/Gentleman-Programming/gentle-ai">
  <img width="220" src="https://raw.githubusercontent.com/Gentleman-Programming/gentle-ai/main/docs/assets/brand/built-with-gentle-ai.png" alt="Built with Gentle-AI" />
</a>

</div>

hermes-odd is an **Organic Driven Development (ODD)** and **receipt-driven
development (RDD)** workflow harness for Hermes Agent. It adapts the Gentle AI
workflows to Hermes-native surfaces: a compact system prompt section, lazy
plugin skills, and plain-text slash commands.

hermes-odd is **not** SDD. It ships no SDD agents, chains, skills,
preflight, or `gentle-sdd-*` commands.

## Status

Early (0.1.0). The plugin loads, injects a compact ODD prompt section,
ships lazy ODD skills, and registers the viewers `/odd_agents`,
`/odd_tasks`, `/odd_changes`, the RDD switch `/odd_review_mode` and the
health commands `/odd_status`, `/odd_doctor`, `/odd_commands`, plus a
[first-run setup](#first-run-setup) (`/odd_setup`, persona and preferences)
and the [SOUL.md cleanup](#soulmd-cleanup-of-gentle-ai-blocks) of gentle-ai
blocks (`/odd_soul`).
Native RDD review is blocked upstream for Hermes (see
[RDD on Hermes](#rdd-on-hermes)).

## What gets injected

- **Always on:** one system prompt section, `hermes-odd-workflow` (about
  3.3k characters; a test caps it at 3,800 of the 4,000 Hermes allows per
  section and 8,000 across all plugins). It carries the ODD protocol, the
  mandatory `delegate_task` triggers, the feature-tracking and resume
  rules, blocking-question and language rules, and pointers to the skills
  below.
- **Lazy skills** (loaded only on demand with `skill_view`; plugin skills
  never enter the always-on skills index):
  - `hermes-odd:odd-workflow` — full ODD protocol, routing ladder and
    triggers, research depth, lossless blocking prompts over chat, checks
    and TDD, commits and delivery strategy.
  - `hermes-odd:odd-delegation` — `delegate_task` mechanics, mission
    template, allowed edit surfaces for writers.
  - `hermes-odd:odd-feature-tracking` — feature document template,
    Engram™ mirror (`mcp__engram__*` tools), resume protocol, `todo`
    projection.
  - `hermes-odd:setup` — the first-run setup conversation (see
    [First-run setup](#first-run-setup)).
  - `hermes-odd:engram-protocol` — the Engram™ memory protocol bound to
    `mcp__engram__*`: when and what to save, topic keys, search before
    asking, session summaries (moved here from `SOUL.md` by `/odd_soul`).
  - `hermes-odd:codegraph` — CodeGraph before broad searches for structural
    questions, worktree placement, lazy `codegraph init` (moved here from
    `SOUL.md` by `/odd_soul`).
- **Skill pointers:** one line pointing to `hermes-odd:engram-protocol`
  while the `engram_protocol` preference is `auto` (the default), and one
  pointing to `hermes-odd:codegraph` while `codegraph_guidance` is `auto` and
  CodeGraph is present (a `codegraph` binary on `PATH` or an
  `mcp_servers.codegraph` entry in Hermes' `config.yaml`).
- **Only while setup is pending:** one extra line in the section asking the
  agent to offer the setup once, never mid-task. After setup, one
  `TDD mode: <mode>` line when you chose a TDD mode. Every combination stays
  under the 3,800-character cap (tested).
- **Only if you choose a persona:** one `<!-- hermes-odd:persona -->` block at
  the top of `SOUL.md` (see below). Nothing else in `SOUL.md` changes unless
  you run the [cleanup](#soulmd-cleanup-of-gentle-ai-blocks) and confirm it.

The canonical gentle-ai routing render for Hermes is vendored in
`upstream/odd-routing-hermes.canonical.md` for drift tracking.

## Upstream compatibility

hermes-odd supports **gentle-ai v3.7.0** (binary >= 3.7.0) and **gentle-shell
v3.7.0** (npm `gentle-pi` 3.7.0), pinned to exact upstream commits in
[`upstream/upstream.lock.json`](upstream/upstream.lock.json).
[`upstream/SUPPORTED.md`](upstream/SUPPORTED.md) has the support matrix per
component (ODD, RDD, review contract, viewers, persona), the upstream sync procedure and
the triage log that records, for every upstream change, whether it was ported,
is not portable (and why) or is pending.

## Install

Setup has three steps: install a few binaries from the Gentle AI™
ecosystem, install the plugin, then answer the first-run setup in chat.

### 1. What to install from Gentle AI (binaries only)

hermes-odd needs only the **binaries** from the Gentle AI ecosystem, not the
gentle-ai installer's Hermes integration.

> [!IMPORTANT]
> **Never** run `gentle-ai install` selecting Hermes, and **never** run
> `gentle-ai sync --agent hermes`. Even a selection with only Engram writes
> managed blocks into `~/.hermes/SOUL.md`: the always-installed routing,
> plus SDD, persona and protocol blocks. hermes-odd replaces them with a
> compact prompt section and lazy skills. If you already ran one of those
> commands, see [SOUL.md cleanup](#soulmd-cleanup-of-gentle-ai-blocks).

| What | Needed for | Install |
|---|---|---|
| `gentle-ai` binary >= 3.7.0 | RDD: `/odd_review_mode` and the review status probe | `brew install gentleman-programming/tap/gentle-ai` |
| Engram™ binary | Persistent memory (the `hermes-odd:engram-protocol` skill and feature-doc mirrors) | `brew install gentleman-programming/tap/engram` |
| Context7 MCP (optional) | Up-to-date library docs | Needs `npx` (Node.js) |
| CodeGraph (optional) | Code navigation (the `hermes-odd:codegraph` skill) | See the upstream CodeGraph project |

Register the MCP servers with Hermes itself instead of gentle-ai. These
commands write the same `mcp_servers` entries that the gentle-ai installer
writes for Hermes, and nothing else:

```bash
hermes mcp add engram --command engram --args mcp --tools=agent
# optional
hermes mcp add context7 --command npx --args -y --package=@upstash/context7-mcp@2.2.5 context7-mcp
```

Each command asks `Enable all N tools? [Y/n/select]`; answer `Y`. Keep
`--args` as the last option, and do not add a literal `--` inside it (Hermes
rejects it). Check the result with `hermes mcp list` and `hermes mcp test
engram`.

Keep the binaries current. `gentle-ai sync` is fine for your *other*
agents; scope it and preview it first:

```bash
brew upgrade gentleman-programming/tap/gentle-ai gentleman-programming/tap/engram
gentle-ai version
gentle-ai sync --agent opencode --dry-run   # other agents only, never hermes
```

### 2. Install the plugin

```bash
hermes plugins install goldenSniperOS/hermes-odd --enable
```

Hermes installs user plugins **disabled** unless you pass `--enable` or
answer `y` to the `Enable 'hermes-odd' now?` prompt. You can also enable it
later with `hermes plugins enable hermes-odd`, which adds `hermes-odd` to
`plugins.enabled` in `~/.hermes/config.yaml`. Restart the Hermes CLI or
gateway so the plugin loads, then check it:

```bash
hermes plugins list
```

### 3. First-run setup

Start a new session. While setup is pending, hermes-odd asks the model to
offer it once, when you are not in the middle of a task. You can also start
it yourself with `/odd_setup`. It asks about:

- persona;
- answer style;
- TDD mode;
- the Engram protocol;
- the SOUL.md cleanup.

The persona is written into `SOUL.md` only after you confirm it, with a
backup. Details are in [First-run setup](#first-run-setup). Finish with:

```text
/odd_doctor
```

It reports the health of the plugin, `SOUL.md` and the gentle-ai binary.

## Updating

A plugin installed with `hermes plugins install` is a git checkout in
`~/.hermes/plugins/hermes-odd`. Update it with:

```bash
hermes plugins update hermes-odd
```

This runs `git pull --ff-only` in the plugin directory (local edits are
autostashed and re-applied). If you installed a pinned commit with `--ref`,
reinstall instead:

```bash
hermes plugins install goldenSniperOS/hermes-odd --ref <40-char-commit-sha> --force --enable
```

Restart the Hermes CLI or gateway afterwards. Release notes on GitHub list
the exact commit of each release.

## Commands

Commands answer with plain text and never call the model, so the output is
the same in the CLI, the TUI, and every gateway.

In gateways (Telegram, Discord, Slack, ...) type the underscore form, for
example `/odd_commands`; the hyphen form works too. In the Hermes CLI type
the hyphen form, for example `/odd-commands`, because the CLI matches the
registered name exactly.

**Viewers**

| Command | What it does |
|---|---|
| `/odd_agents [id\|all]` | Shows your `delegate_task` subagents: running first, then the last 24 h (up to 10; `all` lists up to 50, one line each). An id prefix shows one run: goal, role, status, timings, parent session and platform, a tool timeline and the child's summary |
| `/odd_tasks [feature\|project]` | Shows your ODD feature documents (`odd/tasks/<feature>.md`): per project, each feature with a progress bar, done/total, the next open task and when it changed, newest first. A feature prefix (or `project/feature`) shows every task with ✓ / ○, the next step and the file; a project name lists only that project |
| `/odd_changes [file\|project\|all\|clear]` | Shows which files the agent and its subagents changed in the last 24 h (`all`: 7 days), grouped by project: `+added −removed  path  (n edits · by main/sa-xxxx · age)`, newest first, with per-project totals. A file (path, name or prefix) shows its edit timeline and, inside a git repository, its current uncommitted `git diff --numstat`; a project name lists that project; `clear` forgets every recorded change |

**Review**

| Command | What it does |
|---|---|
| `/odd_review_mode [status\|enable\|disable] [global\|clone] [project]` | `status` (default, read-only): the effective RDD mode and its source for the repository (a known project by name or prefix, else the directory Hermes runs from), both sources (global, clone), and whether native review is available on Hermes. `enable`/`disable` run the real `gentle-ai review mode <enable\|disable> --scope <global\|clone> --json`; the scope is required, and `clone` needs a git repository |

**Setup**

| Command | What it does |
|---|---|
| `/odd_setup [status\|skip\|reset\|persona ID [confirm]\|tdd MODE\|engram on\|off\|codegraph auto\|off\|verbosity short\|detailed]` | `status` (default): pending / complete / skipped, every answer with its value, where it came from (config, setup, default) and where it is applied, and the SOUL.md block. `skip` stops the agent from offering setup; `reset` clears the answers and makes setup pending again (it does not remove the SOUL.md block: use `persona none`). `persona <rioplatense\|neutral\|custom\|none>` shows a dry-run preview of the SOUL.md change; only `persona <id> confirm` writes it (backup first). `tdd <off\|strict\|project>`, `engram <on\|off>`, `codegraph <auto\|off>`, `verbosity <short\|detailed>` store one answer |
| `/odd_soul [status\|plan [persona]\|apply [persona] confirm\|restore [N]]` | Cleans the gentle-ai blocks out of `SOUL.md` (see [SOUL.md cleanup](#soulmd-cleanup-of-gentle-ai-blocks)). `status` (default): each block, its size and what the cleanup would do, and the current truncation. `plan`: dry run with the action per block, characters saved, the new size and the truncation before → after. `apply confirm`: backup, atomic write, verification. `restore`: lists the backups; `restore N` restores one (backing up the current file first) |

**Health**

| Command | What it does |
|---|---|
| `/odd_status` | One compact message: hermes-odd version, prompt section size, skills, subagents (running / finished in 24 h), changes in 24 h, ODD features and open tasks, the gentle-ai binary version against the supported minimum (✓ / ✗), the RDD mode when `/odd_doctor` or `/odd_review_mode` checked it in the last minute, native review availability on Hermes, and the supported upstream versions |
| `/odd_doctor` | Read-only health report, one `✓ / ⚠ / ✗  check: finding` line per check with a fix hint: every `gentle-ai` on `PATH` and its version (flags a binary below the minimum or shadowing another), the RDD mode of the current git repository (`gentle-ai review mode status`), native review availability on Hermes, `SOUL.md` size, gentle-ai managed blocks and whether Hermes truncates it (and which blocks it drops), the plugin's section, skills, hooks and state, the upstream lock, and Hermes itself |
| `/odd_commands` | Lists hermes-odd commands, grouped |

`/odd_agents` records only metadata, from Hermes' `subagent_start`,
`post_tool_call` and `subagent_stop` hooks: per tool call the name,
ok/error and duration. Tool arguments and results are never stored. Records
live in the profile's plugin state, so a run started from Telegram is visible
in the CLI of the same profile. Stopping a subagent from the command is not
supported (Hermes has no safe plugin API for it); ask the agent to stop it.

`/odd_tasks` reads the feature documents straight from disk; nothing is
copied into state. Because a command does not know which chat or directory
it was typed in, it looks in the projects where a Hermes session of this
profile recently ran (the last 10 git roots of the session working
directory, recorded when the ODD prompt section is rendered) and in the
directory Hermes itself runs from (`terminal.cwd` / the CLI launch
directory). Only directories with an `odd/tasks/` folder are shown. The
Engram mirror of each feature is not read (see `docs/design.md`).

`/odd_changes` captures only successful `write_file` and `patch` calls
(including the ones `execute_code` makes through `hermes_tools`), from the
main agent and its subagents, through Hermes' `post_tool_call` hook: no
repository scans and no background polling. Edits made with terminal/shell
commands or other tools are **not** tracked, so a missing file does not mean
a clean tree. Only the path, line counts, tool name, time, attribution,
session id and platform are kept; file content and diffs are never stored or
shown. `write_file` replaces a whole file, so its removed lines are unknown
and show as `−?`. Entries are kept for 7 days, at most 200 files.

`/odd_status` runs no subprocess except a `gentle-ai version` probe and the
native review probe, both cached for 60 s. `/odd_doctor` runs only `gentle-ai
version`, `gentle-ai review mode status --json` and the native review probe
(no shell, minimal environment, 3 s timeout each, about 6 s in total, cached
for 60 s); it never runs `gentle-ai install` or `sync`.
It measures `SOUL.md` and reads only the model name, base URL and context
length keys of `config.yaml` and `context_length_cache.yaml` to compute
Hermes' truncation cap; `.env`, `auth.json` and other secrets are never
read, SOUL content is never printed, and paths under your home show as `~/…`.
In a gateway the command runs from the gateway's directory, so the RDD mode
of a repository is usually only known from the CLI.

## First-run setup

Like the gentle-ai installer's persona step, but over chat (CLI, TUI and
Telegram). Until you run or skip it, the prompt section carries one line
asking the agent to offer it once when you are not in the middle of a task.
The agent loads `hermes-odd:setup` and asks everything in **one** `clarify`
form (buttons on Telegram):

1. **Persona** — Mentor rioplatense (voseo), Mentor neutral, your own text,
   or None (Hermes default). There is no default and no recommended option:
   Hermes' `clarify` marks the first choice as "(Recommended)", so this
   question is asked as free text with the four options listed.
2. **Answer style** — short first, or detailed.
3. **TDD mode** — per project (detect the runner), strict (RED → GREEN →
   REFACTOR) or off.
4. **Engram memory protocol** — auto (a prompt line points to
   `hermes-odd:engram-protocol` when `mcp__engram__*` tools exist) or off.
5. **SOUL cleanup of gentle-ai blocks** — yes (the agent shows the dry-run
   plan through the `odd_soul_apply` tool and applies it only after your
   explicit yes), later (`/odd_soul` whenever you want), or no.

The agent then sends one summary and asks you to confirm before it calls the
`odd_setup_apply` tool. If you decline the persona, the other answers are
kept and `SOUL.md` is not touched. You can do everything without the model
too: `/odd_setup persona neutral` (preview), then
`/odd_setup persona neutral confirm`.

Where each answer goes:

- **Persona and answer style**: one managed block, `<!-- hermes-odd:persona -->`
  … `<!-- /hermes-odd:persona -->`, at the top of `SOUL.md` (after a leading
  `# title` or comment header). Hermes cuts the middle of a long `SOUL.md`,
  so the top is the safe place. Before every write the file is copied to
  `SOUL.md.hermes-odd-bak-<UTC timestamp>` (the last 5 are kept) and the new
  file is written atomically with the same permissions. Your own text and any
  `<!-- gentle-ai:... -->` blocks stay byte-identical; if a gentle-ai persona
  block exists, both personas coexist and the summary says so. `/odd_setup
  persona none` (then `confirm`) removes the block again.
- **TDD mode**: one `TDD mode: <mode>` line in the prompt section.
- **Engram protocol / CodeGraph guidance**: one pointer line each in the
  prompt section (`codegraph_guidance` is not asked; it defaults to `auto`,
  `/odd_setup codegraph off` removes the line).
- **All answers**: `plugins.entries.hermes-odd.settings` in `config.yaml`
  (the plugin's `config_schema`), and the setup record in the plugin state.
  A valid value you edit in `config.yaml` wins. Managed installs refuse the
  config write; the answers then stay in the plugin state.

Everything takes effect in the **next new session** (`/new` or a new chat).
The built-in personas are hermes-odd's own wording of the upstream behavior
rules (short answers, one question at a time, verify before agreeing,
artifacts in English, ...); they carry no product identity.

## SOUL.md cleanup of gentle-ai blocks

If you ever ran `gentle-ai install` for Hermes or `gentle-ai sync --agent
hermes`, your `~/.hermes/SOUL.md` holds gentle-ai's managed blocks. Hermes
sends `SOUL.md` with every message and cuts the middle of a long one, and
hermes-odd already supplies ODD through its prompt section, so most of them
are dead weight. `/odd_soul` removes them, only with your confirmation:

| Block | What `/odd_soul` does |
|---|---|
| `sdd-orchestrator` (with its nested `sdd-session-preflight`) | removed |
| `agent-routing` | removed; its nested `remote-authorization` block is kept in its place |
| `engram-protocol` | removed; now the lazy skill `hermes-odd:engram-protocol` |
| `codegraph-guidance` | removed; now the lazy skill `hermes-odd:codegraph` |
| `persona` | kept; `plan persona` / `apply persona confirm` also removes it, only while a hermes-odd persona block exists |
| your own text, unknown blocks, `hermes-odd:` blocks | kept, byte-identical |

The kept `remote-authorization` block is a general safety rule; it keeps
gentle-ai's own markers and bytes (hermes-odd does not claim text it does not
maintain, and gentle-ai's tooling still recognizes it).

1. `/odd_soul plan` — dry run: every block with its action and size, the
   characters saved, the new size and whether Hermes truncates it at 128k,
   200k and 1M context and for your configured model. Nothing is written.
2. `/odd_soul apply confirm` — copies `SOUL.md` to
   `SOUL.md.hermes-odd-bak-<UTC timestamp>` (the last 5 are kept), writes the
   new file atomically with the same permissions, then re-reads it and checks
   that kept blocks are byte-identical and in order, removed blocks are gone,
   the lifted block is there and your text outside blocks is unchanged (only
   the blank lines around removed blocks change). A second apply finds
   nothing to do.
3. `/odd_soul restore` lists the backups; `/odd_soul restore 1` puts the
   newest back (the current file is backed up first, so a restore can be
   undone the same way).

Unclosed, stray or crossed markers make it refuse, with the line number, and
change nothing. Over chat, the setup's "yes" answer makes the agent show the
same plan through the `odd_soul_apply` tool and apply it only after your
explicit yes (the tool also refuses a plan that no longer matches the file).

> [!WARNING]
> gentle-ai writes these blocks again if you later run `gentle-ai install`
> selecting Hermes or `gentle-ai sync --agent hermes`. hermes-odd needs only
> the gentle-ai **binary**; keep Hermes out of gentle-ai's install and sync.

## RDD on Hermes

Receipt-driven development (RDD) is Gentle AI's review discipline: a frozen
candidate (one work-unit commit or PR slice), risk-scoped review lenses, at
most one bounded correction, and an outcome derived from Git and bound to the
candidate as a receipt. A review outcome never authorizes delivery.

**Native RDD review does not run on Hermes today, and hermes-odd says so.**
gentle-ai runs native immutable review only for runtimes that can launch a
fresh, constrained reviewer and prove that boundary before the review starts.
gentle-ai 3.7.0 advertises that for claude-code, opencode, codex and pi, not
for hermes. Asked as Hermes, the review CLI refuses in preflight:

```text
gentle-ai review status --cwd . --contract gentle-ai.review-integration/v2 --agent hermes --next-transition
schema: gentle-ai.review-integration.failure/v2
code:   immutable_review_transport_unsupported
next_action: stop
```

What hermes-odd does instead:

- `/odd_review_mode` shows your RDD switch and the availability line
  (`Native review on Hermes: unavailable — gentle-ai 3.7.0 advertises
  immutable review only for claude-code, opencode, codex, pi`), detected live;
  `/odd_status` and `/odd_doctor` show the same line.
- The `hermes-odd:rdd-review` skill tells the agent, when RDD is on, to report
  "native review unavailable on Hermes (gentle-ai runtime eligibility)" once
  per candidate, record it in the ODD feature document, and continue under
  your ordinary repository policy (tests, CI, human review).
- On request, an **advisory 4R review** (Risk, Resilience, Readability,
  Reliability; `hermes-odd:rdd-review-lenses`) runs as read-only
  `delegate_task` children over the exact commit (`git show <sha>`), labeled
  "advisory review — no receipt".

hermes-odd never impersonates another runtime (it never passes `--agent pi`
or any other identity to gentle-ai) and never fakes a receipt. The native
review facade waits on upstream runtime eligibility for Hermes.

## Planned commands

| Pi (gentle-pi) | Hermes (hermes-odd) | Notes |
|---|---|---|
| `gentle:persona` | `/odd_setup persona ID` | shipped as the [first-run setup](#first-run-setup) |
| SOUL.md cleanup of gentle-ai blocks | `/odd_soul` | shipped: dry run, explicit confirmation, backup and restore |
| `gentle_review*` tools | native review facade | blocked upstream: gentle-ai does not accept Hermes as an immutable review runtime yet |
| `skill-registry:refresh` | Hermes native skill index | not needed |

## Development

The plugin uses the Python standard library only. Tests use `unittest`, do
not import Hermes, and also run under pytest. From the repository root:

```bash
# tests (Hermes venv python; no extra packages needed)
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests -v

# lint and format (any ruff >= 0.6: ruff, uvx ruff or pipx run ruff)
ruff check . && ruff format --check .

# end-to-end smoke: loads the plugin through Hermes' PluginManager in a
# throwaway HERMES_HOME; never touches ~/.hermes, no network, no model calls
~/.hermes/hermes-agent/venv/bin/python scripts/smoke_e2e.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and release process
and [docs/design.md](docs/design.md) for the architecture.

Layout:

- `plugin.yaml` — Hermes manifest.
- `__init__.py` — entry point Hermes imports; delegates to `hermes_odd`.
- `hermes_odd/plugin.py` — `register(ctx)` wiring.
- `hermes_odd/prompt.py` — compact always-on ODD section.
- `hermes_odd/skills.py` — discovery and registration of `skills/*/SKILL.md`.
- `hermes_odd/upstream.py` — reads the upstream support lock.
- `hermes_odd/commands/` — declarative command registry and commands.
- `skills/` — lazy plugin skills.
- `upstream/` — upstream support lock and matrix (`upstream.lock.json`,
  `SUPPORTED.md`) and vendored canonical sources for drift tracking.
- `tests/` — `unittest` suite with a fake plugin context.
- `scripts/smoke_e2e.py` — isolated load through Hermes' own plugin manager.
- `docs/design.md` — architecture, prompt budget and Hermes API facts.

## Credits and acknowledgements

This project exists because of the work of Alan Buscaglia and the
Gentleman Programming community. The ideas that make it useful come from
them: Organic Driven Development (ODD), receipt-driven development (RDD), the
mandatory delegation triggers, feature documents and their resume protocol,
the Engram memory protocol, and native review. hermes-odd only adapts those
workflows to Hermes surfaces (prompt sections, plugin skills,
`delegate_task`, gateway-safe commands). Thank you for building them in the
open and under the MIT license.

hermes-odd itself is being built with Gentle AI: planned and implemented with the ODD workflow through gentle-pi.

Thanks as well to Nous Research for Hermes Agent, the daily driver this
plugin runs on. The author is a Hermes user and admirer; hermes-odd uses its
public plugin API and copies none of its code.

Derived files, pinned upstream commits and the full upstream license texts
are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Not affiliated

hermes-odd is an independent community project. It is **not** an official
Gentle AI, gentle-shell, gentle-pi, or Hermes Agent project, and it is not
sponsored, endorsed, certified, or partnered with Gentleman Programming,
Alan Buscaglia, or Nous Research. Their names are used nominatively, only to
describe what this project is based on and compatible with.

Gentle AI, Gentle-AI, gentle-ai, and Engram are trademarks of Alan
Buscaglia; gentle-shell and gentle-pi are trademarks of Alan Buscaglia.
Hermes Agent is a project of Nous Research. All other names and trademarks
belong to their respective owners.

## License

MIT for this project's own code; see [LICENSE](LICENSE). Portions derived
from gentle-ai and gentle-shell keep their MIT notices in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
