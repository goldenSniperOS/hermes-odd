---
name: odd-delegation
description: "ODD delegation for Hermes: delegate_task mechanics, self-contained mission template, allowed edit surfaces."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, delegation, delegate_task, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow, odd-feature-tracking]
---
<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/orchestrator-delegation.md -->

# ODD delegation for Hermes

How the parent turns a fired delegation trigger (see `hermes-odd:odd-workflow`)
into a `delegate_task` call. The parent orchestrates; children execute one
bounded unit and never orchestrate.

## 1. `delegate_task` mechanics (verified against hermes-agent)

- Call shape: `delegate_task(tasks=[{goal, context, output_schema?}])`. One
  entry spawns one child; several independent entries run in parallel.
- Children get a fresh conversation, their own terminal, and the parent's
  toolsets (MCP included unless `delegation.inherit_mcp_toolsets` is false).
  There is no toolsets argument: name the tools the child should use or
  avoid in `context` instead.
- Children cannot call `clarify`, `memory`, `delegate_task`, `cronjob` or
  `send_message`. They return decision gaps to the parent.
- Top-level delegations run in the background. The consolidated result
  re-enters the conversation on its own: end the turn or do non-overlapping
  work; never sleep or poll. Use `action="list"` to inspect, `"steer"` with
  `subagent_id` + `message` to correct drift, `"stop"` to end a child.
- `/stop`, `/new` or process exit discard running children: record in-flight
  work in the feature document and relaunch rather than claim recovery.
- Child summaries are self-reports. Verify files, commits and command
  results yourself before telling the user.
- Never run two writers in the same worktree. Parallel read-only mappers on
  non-overlapping topics are fine.

### Mission template

Write missions in English (translate the user's request; keep exact quotes,
errors, filenames and commands verbatim). `goal` is one sentence; `context`
carries everything else, because the child knows nothing of this chat:

```text
Role: read-only mapper | bounded writer | verifier
Repository: <absolute repo root>, branch <branch>
Feature document: odd/tasks/<feature>.md, task <ID> (read it before edits)
Intent and acceptance criteria: <from the feature document>
Relevant context: <paths, findings, errors>
Skills to load before work: <exact skill_view names>
TDD: mode <on|off>, source <config|user>, runner <exact command>

## Allowed edit surfaces        (writers only; see section 2)
path/to/file.py
src/module/**

## Verification                 (exact commands, run in the foreground)
<command>

## Known environmental failures (exact pre-existing failing tests/commands)

Rules: do not commit, push, stage or run destructive git; do not edit
outside the allowed surfaces; stop with status interaction_required when a
human decision is needed, including a derived candidate list.
Return: status completed|partial|blocked|interaction_required, summary,
files_changed, validation (<command>: <observed result>), risks.
Close with a "## Key Learnings" block of 1-5 numbered standalone facts,
or omit it when there is nothing reusable.
```

Use `output_schema` only for fields you will read, e.g. `status` and
`files_changed`. Omit the Key Learnings instruction when the child must return
strict JSON. A failing command not named under Known environmental failures
means `partial`, never `completed`.

## 2. Allowed edit surfaces (mandatory for writers)

The parent derives the surface before launching a writer: the files the
change must touch plus directories where new files are authorized.

- Exact repository-relative paths or narrow globs, one per line; never `.`,
  a bare repository root or an absolute path. Wrap paths containing spaces in
  backticks.
- List pre-existing untracked targets explicitly.
- Nothing beyond the delegated task: a surface wider than the task is the
  same defect as no surface.
- If the surface cannot be derived, do not launch the writer and never ask
  the human to author paths. Present the derived candidate list as an
  approve/decline choice using the lossless blocking prompt rules in
  `hermes-odd:odd-workflow`. Relay a writer's `interaction_required`
  about surfaces the same way.
