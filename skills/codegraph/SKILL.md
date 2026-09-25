---
name: codegraph
description: "CodeGraph guidance for Hermes: use the CodeGraph index before broad searches for structural questions, worktree placement, lazy `codegraph init` and the read-only CLI or MCP surface."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [codegraph, code-intelligence, exploration, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow, odd-delegation]
---
<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/components/communitytool/codegraph_guidance.go -->

# CodeGraph (Hermes)

For structural or codebase questions (repository maps, architecture, call
flow, dependencies, symbol references, impact analysis, "how does X work"),
use CodeGraph before broad file searches. This is a hard ordering rule, not
a preference. This skill is the lazy version of the CodeGraph block
gentle-ai wrote into `SOUL.md`; `/odd_soul` moves it here.

## Worktree placement

- Create Git worktrees that may need CodeGraph under the user's home
  directory, preferably as a sibling:
  `<repo-parent>/<repo-name>-worktrees/<worktree-name>`. Never put a
  CodeGraph-dependent worktree under `/tmp` or `/var/tmp`; generic
  temporary-work guidance does not override this.
- Every worktree needs its own `.codegraph/` index. Never copy, symlink or
  reuse another checkout's index: its root and checked-out bytes may differ.

## Surface

- Prefer the CodeGraph MCP tools when Hermes has them. With the server
  configured as `codegraph` in `mcp_servers` they are
  `mcp__codegraph__codegraph_explore` (relevant source, call paths and
  blast radius in one call) and `mcp__codegraph__codegraph_node` (one
  symbol or file with its callers and dependents).
- Without MCP tools, run the upstream `codegraph` CLI with the `terminal`
  tool. Read-only intelligence commands: `codegraph status`,
  `codegraph query`, `codegraph explore`, `codegraph node`, `codegraph files`,
  `codegraph callers`, `codegraph callees`, `codegraph impact` and
  `codegraph affected`.
- Never run or recommend the destructive or administrative commands
  `codegraph uninit`, `codegraph install`, `codegraph uninstall` or
  `codegraph upgrade`. Keep `codegraph index` (a full rebuild) for explicit
  index-corruption recovery, never routine use.

## Required order for structural questions

1. Resolve the project root: `git rev-parse --show-toplevel || pwd`.
2. Confirm it is a real project or workspace. Do not ask before
   initializing CodeGraph in a real project. Never initialize it in `$HOME`,
   temporary directories or non-project folders (`codegraph init` refuses a
   home directory or filesystem root unless forced; never force it).
3. Check for `<project-root>/.codegraph/` before any broad read, glob or
   grep exploration.
4. If `.codegraph/` is missing and CodeGraph is available, run
   `codegraph init <project-root>` once (it builds the initial index).
5. A missing `.codegraph/` is the trigger to initialize, not a reason to
   skip CodeGraph.
6. After initialization use the MCP tools, or the read-only CLI commands
   when the MCP tools are absent.
7. After edits rely on the watcher's auto-sync. Run `codegraph sync` only
   when the watcher is disabled or CodeGraph reports stale files that do not
   refresh on their own.
8. Fall back to ordinary file tools only after initialization or use
   fails, and say briefly why.

Broad read, glob or grep exploration before this check is discouraged for
structural questions.

## With delegation

A `delegate_task` child inherits the parent's tools, MCP included. Tell a
mapping child in its mission to follow this order (or to load
`hermes-odd:codegraph`), and name the project root so it does not
initialize the wrong directory.
