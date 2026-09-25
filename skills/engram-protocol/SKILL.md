---
name: engram-protocol
description: "Engram persistent memory protocol for Hermes (mcp__engram__* tools): when and what to save, topic keys, searching before asking, session summaries and recovery after compaction."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [memory, engram, protocol, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-feature-tracking]
---
<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/assets/engram/protocol.md -->

# Engram memory protocol (Hermes)

Engram™ is a persistent memory that survives sessions and context
compaction. This skill is the lazy, Hermes-bound version of the memory
protocol gentle-ai wrote into `SOUL.md`; `/odd_soul` moves it here so it no
longer costs tokens on every message. Load it when Engram tools exist and
you are about to decide, fix, learn or recall something worth keeping.

## Tool names

Hermes exposes MCP tools as `mcp__<server>__<tool>`. With the Engram MCP
server configured as `engram` in `mcp_servers` (if it has another name,
substitute it):

| Tool | Use |
|---|---|
| `mcp__engram__mem_current_project` | resolve the project name from the workspace path |
| `mcp__engram__mem_context` | recent project context (fast, cheap) |
| `mcp__engram__mem_search` | keyword search (`query`, `project`, `type`, `match_mode`, `all_projects`, `limit`) |
| `mcp__engram__mem_get_observation` | full, untruncated content of one result (`id`) |
| `mcp__engram__mem_save` | save one observation (see the format below) |
| `mcp__engram__mem_update` | fix a known observation by `id` |
| `mcp__engram__mem_suggest_topic_key` | ask for a stable key when unsure |
| `mcp__engram__mem_review` | lifecycle review, when the server has it |
| `mcp__engram__mem_session_summary` | end-of-session summary |

If no Engram tool is callable, say so once and continue; never claim
something was saved. Hermes' built-in `memory` tool (MEMORY.md) is a
different store.

## Session start

1. When the runtime gives a workspace directory, call
   `mcp__engram__mem_current_project` with it and keep the project name for
   every read and search.
2. Use only a session id the runtime already registered. Never invent,
   derive or register one; when none is available, leave `session_id` out
   of the calls instead of guessing.
3. Before architecture-sensitive work, when `mem_review` exists, list the
   project's memories with it; if it does not exist, continue with
   `mem_context` and `mem_search`.

## When to save (proactively, without being asked)

Call `mcp__engram__mem_save` right after any of these:

- an architecture or design decision;
- a team convention, workflow change or naming/structure pattern;
- a tool or library choice with its tradeoffs;
- a completed bug fix (with the root cause);
- a feature built with a non-obvious approach;
- a configuration or environment change;
- a non-obvious discovery, gotcha or edge case in the codebase;
- a user preference or constraint;
- a significant issue, PR or tracker artifact created or updated.

After every task ask yourself: did I decide, fix, learn or establish
something? If yes, save it now.

## What to save (structure)

- `title`: verb + what, short and searchable ("Fixed N+1 query in UserList").
- `type`: `bugfix`, `decision`, `architecture`, `discovery`, `pattern`,
  `config` or `preference`.
- `scope`: `project` (default) or `personal`.
- `topic_key`: a stable key for a topic that evolves, such as
  `architecture/auth-model`.
- `session_id`: only the registered one (see Session start).
- `content`, four short parts:
  - **What**: one sentence, what was done;
  - **Why**: what motivated it (request, bug, performance);
  - **Where**: files or paths affected;
  - **Learned**: gotchas and surprises (omit when none).

Prompt capture: leave `capture_prompt` unset for normal saves. Set it to
`false` only for automated artifacts (generated reports, caches, registry
output). If the server's schema has no `capture_prompt`, omit it.

Never save secrets, credentials, tokens, private keys or personal data.

## Topic keys

- Different topics never overwrite each other: give each its own key.
- The same topic evolving reuses its `topic_key` (the save upserts).
- Unsure about the key: call `mcp__engram__mem_suggest_topic_key` first.
- Correcting one known observation: `mcp__engram__mem_update` with its `id`.

## Search before asking

On "remember", "recall", "what did we do", "how did we solve" or any
reference to past work, in any language:

1. `mcp__engram__mem_context` (recent history);
2. if not found, `mcp__engram__mem_search` with distinctive keywords;
3. on a hit, `mcp__engram__mem_get_observation` for the full content.

Also search on your own when starting work that may have been done before,
when the user names a topic you have no context on, and on the user's first
message about a project, feature or problem.

Memories marked `needs_review` are stale context, not facts: tell the user
and verify them against current evidence before relying on them. Mark a
memory reviewed only after the user explicitly confirms it.

## Ambiguous project

When a write (`mem_save`, `mem_save_prompt`, `mem_session_summary`) fails
with `ambiguous_project`, never guess: ask the user to choose exactly one of
`available_projects`, then retry the same write with `project`,
`project_choice_reason=user_selected_after_ambiguous_project` and the
returned `recovery_token`. When `mem_session_start` fails that way, retry it
with the intended repository root as `directory` (it takes no `project` or
`recovery_token`), and attach that session id to no write until it is
registered.

## Saving is not replying

Memory is bookkeeping for your future self; the user never sees it.

- Save before you compose the final answer, then end the turn with the
  complete answer and no tool call after it.
- Never let a save stand in for the answer, and never shrink the answer to
  "saved" or "done".
- If a memory call fails or times out, deliver the full answer anyway and
  mention the failure briefly.

## Session close

Before ending a session or saying "done", call
`mcp__engram__mem_session_summary` with:

```markdown
## Goal
What this session worked on.

## Instructions
User preferences or constraints discovered (skip if none).

## Discoveries
- Technical findings, gotchas, non-obvious learnings.

## Accomplished
- Completed items with key details.

## Next Steps
- What remains for the next session.

## Relevant Files
- path/to/file — what it does or what changed.
```

Skipping it means the next session starts blind.

## After compaction

When a compaction summary or "FIRST ACTION REQUIRED" appears:

1. call `mcp__engram__mem_session_summary` with the compacted summary
   first, so the work before compaction is kept;
2. call `mcp__engram__mem_context` for more context;
3. only then continue.

ODD feature documents keep their own Engram mirror
(`odd/<feature>/tasks`); `hermes-odd:odd-feature-tracking` covers it.
