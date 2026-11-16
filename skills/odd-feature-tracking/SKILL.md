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
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator-memory.md -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 extensions/gentle-ai.ts -->

# ODD feature tracking for Hermes

Large authorized implementation (task size in `hermes-odd:odd-workflow`
section 3: the resume test fails) keeps three views of one plan. The file
is the source; the other two are projections of it:

| View | Where | Role |
|---|---|---|
| Feature document | `odd/tasks/<feature>.md` in the repository | the source and the spec children read |
| Engram mirror | topic `odd/<feature>/tasks`, current project | recovery copy |
| `todo` list | Hermes session | visible projection only |

Small or read-only work gets none of them unless the user asks.

## Tool names (Hermes)

Hermes exposes MCP tools as `mcp__<server>__<tool>`. With the Engram MCP
server configured as `engram`:

- `mcp__engram__mem_save` — `title`, `content`, `type`, `topic_key`,
  `project`, `scope`; a repeated `topic_key` upserts.
- `mcp__engram__mem_search` — `query`, `project`, `type`, `match_mode`,
  `all_projects`, `limit`.
- `mcp__engram__mem_get_observation` — `id`; returns the full content.
- `mcp__engram__mem_context` — recent project context.
- `mcp__engram__mem_update` — `id`, `expected_project` (the project that
  owns the observation) plus changed fields.
- `mcp__engram__mem_review` — lifecycle review, when present.

If the server has another name, substitute it. Hermes' built-in `memory`
tool (MEMORY.md) is not the feature mirror.

## With the recall provider

When Hermes' memory provider is `recall` (the hermes-recall plugin), the
Engram tools are the provider's plain `mem_*` names, without the
`mcp__engram__` prefix. The mirror and resume steps below use `mem_save`,
`mem_search`, `mem_get_observation`, `mem_context`, `mem_update` (with
`expected_project`; read it with `mem_get_observation` first) and
`mem_review`. Recall injects the session and project; never pass a session
id. Recall refuses writes from children, so the parent writes the mirror.

Only when neither `mcp__engram__*` nor recall's `mem_*` tools are callable,
say so and mark the mirror pending; never claim persistence.

## When to create it

After exploration, when the task is large and implementation is
authorized, create the document before the first source write. No
permission prompt for tasks or storage. Tell the user in one line which
document was created and how many tasks it holds.

Use a descriptive, filename-safe feature name. Reuse the same identity for
the whole feature; never overwrite another feature's document.

## Feature document template

One document per feature; no separate plan file or topic. Fixed order,
stable content first and the growing log last:

```markdown
# Feature: <feature name>

<2-3 lines: objective, branch, delivery strategy, test runner>

## Specs
- S1 "<the user's exact words, errors and examples, verbatim>" — scope,
  acceptance criteria, checks
- S2 ...

## Tasks
- [ ] T1 [S1] <behavior-level task> — route: inline|delegated (trigger:
  <evidence>) — commit: <sha> or RED/GREEN evidence
- [ ] T2 [S2] ...

## Delivery
<forecast of authored changed lines, running count, slice boundaries;
see hermes-odd:chained-pr and hermes-odd:work-unit-commits>

## Next step
<one short paragraph>

## Log
- L1 <the user's original request, verbatim>
- L2 <date> <a user correction verbatim, evidence, decision or progress>
```

Rules:

- `## Specs` numbers the user's requirements as `S#` and quotes their
  strings, error messages, commands and examples verbatim in the user's
  language; never summarize them and never add requirements nobody asked
  for (mark assumptions as assumptions).
- A requirement change appends its verbatim `## Log` entry, rewrites only
  the affected `S#` and reopens only its linked task. Keep valid completed
  and unrelated work; findings alone never expand scope.
- Stable task IDs (`T1`, `T2`, ...). Never renumber completed tasks. An
  obsolete task is marked `dropped`; one waiting on something external is
  `blocked` with its unblock condition.
- Check a box only after its outcome and checks were observed. Record
  failed, skipped, unavailable or pending checks honestly. A checkbox grants
  no approval or review receipt.
- Routine corrections stay brief; no exhaustive decision journal.
- Edit the file with targeted edits, never a whole-file rewrite. The parent
  merges bounded child results; a child's partial view never replaces the
  whole document.
- Hand off by reference: `Spec: odd/tasks/<feature>.md, T2, S3-S4`; the
  child must read until `## Log` before edits and report which `S#` it
  covered.

## Mirror protocol

1. Write the file first; the file is the source.
2. Mirror the **full current document** plus its repository-relative
   locator, not a summary:
   `mcp__engram__mem_save(title="ODD tasks: <feature>", type="architecture",
   topic_key="odd/<feature>/tasks", project="<project>",
   content="Locator: odd/tasks/<feature>.md\n\n<full document>")`.
3. Read both back with the normal read tool (the file, and `mem_search` +
   `mem_get_observation`); the two writes are not atomic, but never author
   reconciliation scripts or gates for them.
4. After a failed or partial sync, check which writes already applied and
   continue from there; never replay an applied write. A mirror that differs
   from the file is refreshed from the file, never a blocker.
5. If Engram is unavailable, keep the local progress, log "mirror pending",
   continue safe work, and resync when it returns.
6. If a file write is unsafe or unavailable, keep existing state and report.
7. On irreconcilable edits keep both versions and ask only about the real
   conflict; never silently prefer the newer timestamp.

Refresh the mirror once per task transition (a task starts, finishes, is
blocked, reopened or dropped), on a material plan change, and at close.
`## Log` entries between those points go to the file only and reach the
mirror at the next one.

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
observation, reconciles them, and passes the locator, task IDs and linked
`S#` to children, who read the document until `## Log` before edits.

## `todo` projection

Hermes `todo(todos=[{id, content, status, parent?}], merge=false|true)`:

- After the durable file and mirror are written, and before the first
  source write, rebuild the list with `merge=false` from the feature tasks:
  `id` = task ID, `content` = `"T1 <title>"`.
- Status map: `[x]` -> `completed`; the task being worked -> `in_progress`
  (only one at a time); open or `blocked` -> `pending`; `dropped` or
  superseded -> `cancelled`.
- On each task transition update the list from the file, with `merge=true`
  for single-item changes.
- The list is session state. A cleared or replayed list never deletes or
  replaces the durable document or mirror; rebuild it from the file on
  resume.
- If `todo` is unavailable, record that limitation instead of claiming the
  projection is in sync.
