---
name: odd-feature-tracking
description: "ODD feature document, Engram mirror (mcp__engram__*), resume protocol and todo projection for Hermes."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, engram, memory, todo, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow]
---
<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/orchestrator-memory.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 extensions/gentle-ai.ts -->

# ODD feature tracking for Hermes

Substantial authorized implementation keeps three views of one plan:

| View | Where | Role |
|---|---|---|
| Feature document | `odd/tasks/<feature>.md` in the repository | durable authority |
| Engram mirror | topic `odd/<feature>/tasks`, current project | recovery copy |
| `todo` list | Hermes session | visible projection only |

Small or read-only work gets none of them.

## Tool names (Hermes)

Hermes exposes MCP tools as `mcp__<server>__<tool>`. With the Engram MCP
server configured as `engram`:

- `mcp__engram__mem_save` — `title`, `content`, `type`, `topic_key`,
  `project`, `scope`; a repeated `topic_key` upserts.
- `mcp__engram__mem_search` — `query`, `project`, `type`, `match_mode`,
  `all_projects`, `limit`.
- `mcp__engram__mem_get_observation` — `id`; returns the full content.
- `mcp__engram__mem_context` — recent project context.
- `mcp__engram__mem_update` — `id` plus changed fields.
- `mcp__engram__mem_review` — lifecycle review, when present.

If the server has another name, substitute it. If no Engram tool is callable,
say so and mark the mirror pending; never claim persistence. Hermes' built-in
`memory` tool (MEMORY.md) is not the feature mirror.

## When to create it

After exploration, when the work is substantial and implementation is
authorized, create the document before the first source write. No
permission prompt for tasks or storage. Tell the user in one line which
document was created and how many tasks it holds.

Use a descriptive, filename-safe feature name. Reuse the same identity for
the whole feature; never overwrite another feature's document.

## Feature document template

One document per feature; no separate plan file or topic.

```markdown
# Feature: <feature name>

## Objective
## Problem
## Why
## Scope
## Non-goals
## Constraints
## Tasks
- [ ] T1 <behavior-level task> (route: inline|delegated; trigger: <evidence>)
- [ ] T2 ...
## Acceptance criteria
## Checks
<TDD mode, source, runner; applicable check commands>
## Delivery
<strategy, forecast of authored changed lines, running count, slice boundaries>
## Progress
<dated entries; concise rationale for meaningful accepted changes>
## Evidence
<commit ids and observed check results per task>
## Next step
```

Rules:

- Stable task IDs (`T1`, `T2`, ...). Never renumber completed tasks.
- Check a box only after its outcome and checks were observed. Record
  failed, skipped, unavailable or pending checks honestly. A checkbox grants
  no approval or review receipt.
- Accepted user, review or verification changes update intent and tasks:
  keep valid completed and unrelated work, add genuinely new tasks, reopen
  invalidated ones with a reason, revise their checks. Findings alone never
  expand scope; new business scope needs user authorization.
- Routine corrections stay with their task; no exhaustive decision journal.
- The parent merges bounded child results; a child's partial view never
  replaces the whole document.

## Mirror protocol

1. Write the file first.
2. Mirror the **full current document** plus its repository-relative
   locator, not a summary:
   `mcp__engram__mem_save(title="ODD tasks: <feature>", type="architecture",
   topic_key="odd/<feature>/tasks", project="<project>",
   content="Locator: odd/tasks/<feature>.md\n\n<full document>")`.
3. Read both back (the file, and `mem_search` + `mem_get_observation`); the
   two writes are not atomic.
4. If Engram is unavailable, keep the local progress, note "mirror pending"
   in Progress, continue safe work, and resync when it returns.
5. If a file write is unsafe or unavailable, keep existing state and report.
6. On irreconcilable edits keep both versions and ask only about the real
   conflict; never silently prefer the newer timestamp.

Update file and mirror after every task transition and material plan
change, in the same turn.

## Resume protocol

1. `mcp__engram__mem_context` for the current project.
2. `mcp__engram__mem_search` scoped to the project and feature
   (`query="odd/<feature>/tasks"`, `project=...`).
3. `mcp__engram__mem_get_observation(id)` for the full saved document.
4. Read the actual `odd/tasks/<feature>.md`.
5. Reconcile requirements, code, git log and evidence; then continue the
   next unfinished task.

Never infer active work from the newest global memory. A missing copy is
not permission to overwrite surviving progress. Memories flagged
`needs_review` are stale context: surface them and verify before relying on
them; never mark them reviewed without explicit user confirmation.

Before implementation or resume the parent reads both the file and the full
observation, reconciles them, and passes the locator, task IDs, intent,
allowed scope and checks to children, who read the document before edits.

## `todo` projection

Hermes `todo(todos=[{id, content, status, parent?}], merge=false|true)`:

- After the durable file and mirror are written, and before the first
  source write, rebuild the list with `merge=false` from the feature tasks:
  `id` = task ID, `content` = `"T1 <title>"`.
- Status map: `[x]` -> `completed`; the task being worked -> `in_progress`
  (only one at a time); open -> `pending`; dropped or superseded ->
  `cancelled`.
- On each transition update the file, the mirror and the list together;
  use `merge=true` for single-item changes.
- The list is session state. A cleared or replayed list never deletes or
  replaces the durable document or mirror; rebuild it from the file on
  resume.
- If `todo` is unavailable, record that limitation instead of claiming the
  projection is in sync.
