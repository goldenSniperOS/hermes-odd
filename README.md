# hermes-odd

Based on the ODD and RDD workflows of
[Gentle AI™](https://github.com/Gentleman-Programming/gentle-ai) and
[gentle-shell](https://github.com/Gentleman-Programming/gentle-shell)
(npm `gentle-pi`) by Alan Buscaglia / Gentleman Programming, running on
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
Independent community project; see [Not affiliated](#not-affiliated).

hermes-odd is an **Organic Driven Development (ODD)** and **receipt-driven
development (RDD)** workflow harness for Hermes Agent. It adapts the Gentle AI
workflows to Hermes-native surfaces: a compact system prompt section, lazy
plugin skills, and plain-text slash commands.

hermes-odd is **not** SDD. It ships no SDD agents, chains, skills,
preflight, or `gentle-sdd-*` commands.

## Status

Early (0.1.0). The plugin loads, injects a compact ODD prompt section,
ships lazy ODD skills, and registers `/odd_commands`, `/odd_agents` and
`/odd_tasks` (unreleased). The other viewers and RDD integration are planned (see
[Planned commands](#planned-commands)).

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

The canonical gentle-ai routing render for Hermes is vendored in
`upstream/odd-routing-hermes.canonical.md` for drift tracking.

## Upstream compatibility

hermes-odd supports **gentle-ai v3.7.0** (binary >= 3.7.0) and **gentle-shell
v3.7.0** (npm `gentle-pi` 3.7.0), pinned to exact upstream commits in
[`upstream/upstream.lock.json`](upstream/upstream.lock.json).
[`upstream/SUPPORTED.md`](upstream/SUPPORTED.md) has the support matrix per
component (ODD, RDD, review contract, viewers), the upstream sync procedure and
the triage log that records, for every upstream change, whether it was ported,
is not portable (and why) or is pending.

## Install

```bash
hermes plugins install goldenSniperOS/hermes-odd
```

Hermes installs user plugins **disabled**. Answer `y` to the
`Enable 'hermes-odd' now?` prompt, pass `--enable` to the install command,
or enable it later:

```bash
hermes plugins enable hermes-odd
```

Enabling adds `hermes-odd` to `plugins.enabled` in `~/.hermes/config.yaml`.
Restart the Hermes CLI or gateway so the plugin loads, then check it:

```bash
hermes plugins list
```

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

## gentle-ai requirement

> [!IMPORTANT]
> RDD uses the `gentle-ai review` CLI, so keep the **gentle-ai binary** current
> (>= 3.7.0):
>
> ```bash
> brew upgrade gentleman-programming/tap/gentle-ai
> gentle-ai version
> ```
>
> **Never** run `gentle-ai install` selecting Hermes, and **never** run
> `gentle-ai sync --agent hermes`. Both rewrite `~/.hermes/SOUL.md` with SDD
> content that hermes-odd replaces with a compact prompt section.
>
> If you sync gentle-ai for other agents, scope it and preview first:
>
> ```bash
> gentle-ai sync --agent opencode --dry-run
> gentle-ai sync --agent opencode
> ```

## Commands

Commands answer with plain text and never call the model, so the output is
the same in the CLI, the TUI, and every gateway.

In gateways (Telegram, Discord, Slack, ...) type the underscore form, for
example `/odd_commands`; the hyphen form works too. In the Hermes CLI type
the hyphen form, for example `/odd-commands`, because the CLI matches the
registered name exactly.

| Command | What it does |
|---|---|
| `/odd_commands` | Lists hermes-odd commands |
| `/odd_agents [id\|all]` | Shows your `delegate_task` subagents: running first, then the last 24 h (up to 10; `all` lists up to 50, one line each). An id prefix shows one run: goal, role, status, timings, parent session and platform, a tool timeline and the child's summary |
| `/odd_tasks [feature\|project]` | Shows your ODD feature documents (`odd/tasks/<feature>.md`): per project, each feature with a progress bar, done/total, the next open task and when it changed, newest first. A feature prefix (or `project/feature`) shows every task with ✓ / ○, the next step and the file; a project name lists only that project |

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

## Planned commands

| Pi (gentle-pi) | Hermes (hermes-odd) | Notes |
|---|---|---|
| `gentle:changes` | `/odd_changes` | `post_tool_call` on write/patch tools |
| `gentle:status` | `/odd_status` | plugin, binary, review mode, prompt budget |
| `gentle:doctor` | `/odd_doctor` | binary version pin, SOUL size/truncation, markers |
| `gentle:commands` | `/odd_commands` | lists hermes-odd commands |
| `gentle:review-mode` | `/odd_review_mode [status\|enable\|disable]` | wraps `gentle-ai review mode` |
| `gentle:persona` | `/odd_persona [gentleman\|neutral]` | swaps compact persona section |
| `gentle_review*` tools | review tool facade (+ RDD skill) | CLI facade over `gentle-ai review`, opaque bindings only |
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
