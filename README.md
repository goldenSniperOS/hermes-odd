# gentle-hermes

Gentle workflow for [Hermes](https://github.com/NousResearch/hermes-agent):
a port of the **Organic Driven Development (ODD)** and **receipt-driven
review (RDD)** experience from
[gentle-shell](https://www.npmjs.com/package/gentle-pi) and
[gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) to Hermes.

gentle-hermes is **not** SDD. It ships no SDD agents, chains, skills,
preflight, or `gentle-sdd-*` commands.

## Status

Early (0.1.0). The plugin scaffold loads and registers one command,
`/gentle_commands`. The ODD prompt section, viewers, and RDD integration are
planned (see [Planned commands](#planned-commands)).

## Install

```bash
hermes plugins install goldenSniperOS/gentle-hermes
```

Hermes installs user plugins **disabled**. Answer `y` to the
`Enable 'gentle-hermes' now?` prompt, pass `--enable` to the install command,
or enable it later:

```bash
hermes plugins enable gentle-hermes
```

Enabling adds `gentle-hermes` to `plugins.enabled` in `~/.hermes/config.yaml`.
Restart the Hermes CLI or gateway so the plugin loads, then check it:

```bash
hermes plugins list
```

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
> content that gentle-hermes replaces with a compact prompt section.
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
example `/gentle_commands`; the hyphen form works too. In the Hermes CLI type
the hyphen form, for example `/gentle-commands`, because the CLI matches the
registered name exactly.

| Command | What it does |
|---|---|
| `/gentle_commands` | Lists gentle-hermes commands |

## Planned commands

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

## Development

The plugin uses the Python standard library only. Tests use `unittest` and do
not import Hermes. Run them from the repository root with the Hermes venv:

```bash
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests -v
```

Layout:

- `plugin.yaml` — Hermes manifest.
- `__init__.py` — entry point Hermes imports; delegates to `gentle_hermes`.
- `gentle_hermes/plugin.py` — `register(ctx)` wiring.
- `gentle_hermes/commands/` — declarative command registry and commands.
- `tests/` — `unittest` suite with a fake plugin context.

## License

MIT
