# Install hermes-odd with an agent

You can install hermes-odd by hand by following the [Install](../README.md#install)
section of the README. You can also hand the job to the Hermes agent itself:
copy the prompt below and paste it into a chat with that agent (CLI, TUI or
any gateway such as Telegram).

The same prompt covers three starting points. The agent detects which one
applies to it:

| Starting point | What changes for you |
|---|---|
| **A. Nothing installed** (no gentle-ai, no Engram) | The agent installs the gentle-ai and Engram binaries, registers Engram as an MCP server, and installs the plugin. |
| **B. gentle-ai already installed for other agents** (Claude Code, OpenCode, Pi...) but never for Hermes | Only the plugin is new. The agent upgrades the binaries, registers Engram for Hermes if it is missing, and installs the plugin. Your other agents are not touched. |
| **C. gentle-ai already installed for Hermes** (`gentle-ai install` or `gentle-ai sync` selected Hermes) | Same as B, plus the first-run setup cleans the gentle-ai blocks out of `~/.hermes/SOUL.md` (with a backup and a dry-run first). Do not run `gentle-ai install` or `gentle-ai sync` for Hermes again. |

You can tell C apart from B with:

```bash
grep -c "<!-- gentle-ai:" ~/.hermes/SOUL.md
```

Any number above 0 means starting point C.

## The prompt

````text
Install and configure the Hermes plugin "hermes-odd"
(https://github.com/goldenSniperOS/hermes-odd) on this machine.
Run each step, and report the real output of each one. Never invent results.

HARD RULES
- NEVER run `gentle-ai install` selecting Hermes, and NEVER run
  `gentle-ai sync --agent hermes`. They write large managed blocks into
  ~/.hermes/SOUL.md, and hermes-odd replaces those blocks.
- Do not run `gentle-ai sync` for any other agent either, unless I ask.
- Do not edit ~/.hermes/config.yaml by hand; use `hermes` CLI commands.
- Only touch the active Hermes profile.
- If a command needs a password, sudo, or a credential, stop and ask me.

STEP 0 - Detect the starting point and tell me which one applies:
  - `gentle-ai version` and `engram --version` (missing = not installed)
  - `grep -c "<!-- gentle-ai:" ~/.hermes/SOUL.md` (above 0 = gentle-ai was
    installed for Hermes before)
  - `hermes plugins list` (is hermes-odd already there?)
  - `hermes mcp list` (is engram already registered?)
  A = nothing installed. B = gentle-ai installed for other agents only.
  C = gentle-ai blocks found in SOUL.md.

STEP 1 - Binaries (all starting points; Homebrew):
  If missing: brew install gentleman-programming/tap/gentle-ai gentleman-programming/tap/engram
  If present: brew upgrade gentleman-programming/tap/gentle-ai gentleman-programming/tap/engram
  Check: `gentle-ai version` >= 3.7.0 and `engram --version` works.
  If Homebrew is missing, stop and tell me.

STEP 2 - MCP servers (skip any that `hermes mcp list` already shows enabled):
  hermes mcp add engram --command engram --args mcp --tools=agent
  Optional, needs Node.js/npx:
  hermes mcp add context7 --command npx --args -y --package=@upstash/context7-mcp@2.2.5 context7-mcp
  Answer "Y" to "Enable all N tools?". Keep --args as the last option and do
  not add a literal "--" inside it. Check with `hermes mcp test engram`.

STEP 3 - Plugin:
  New install:      hermes plugins install goldenSniperOS/hermes-odd --enable
  Already installed: hermes plugins update hermes-odd
                     hermes plugins enable hermes-odd
  Check: `hermes plugins list` shows hermes-odd enabled, and
  `hermes plugins doctor ~/.hermes/plugins/hermes-odd` reports OK.

STEP 4 - Restart so the plugin loads.
  If you run inside the gateway, you cannot restart yourself: tell me to send
  /restart in the chat, or to run `hermes gateway restart` in a terminal.
  If you run in the CLI, tell me to start a new session. Then stop and wait.

STEP 5 - After the restart (I will message you again):
  Run /odd_doctor (in the CLI: /odd-doctor) and show me the full result.
  "Native review unavailable" is expected: upstream gentle-ai excludes Hermes
  from receipt-driven development. It is not a failure.

STEP 6 - First-run setup: run /odd_setup (CLI: /odd-setup).
  It asks about persona, answer style, the Engram protocol and the SOUL.md
  cleanup. In starting point C, choose the cleanup. Wait for my answers.
  Never change SOUL.md without my explicit confirmation; show the dry-run first.

Finish with a short summary: starting point, installed versions, doctor
result (ok / warn / fail counts), and anything still pending.
````

## After the install

- Update later with `hermes plugins update hermes-odd`, then restart.
- Run `/odd_doctor` at any time to check the plugin, `SOUL.md` and the
  gentle-ai binary.
