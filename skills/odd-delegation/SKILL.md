---
name: odd-delegation
description: "ODD delegation for Hermes: delegate_task mechanics, self-contained mission template, allowed edit surfaces, risk-proportionate verification."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, delegation, delegate_task, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow, odd-feature-tracking]
---
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator-delegation.md -->
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/assets/skills/_shared/odd-orchestrator-sections.md -->
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/assets/hermes/orchestrator.md -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/agents/gentle-ai-worker.md -->

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
- One launch per distinct task: before calling `delegate_task`, check that
  the same role and mission were not already launched this turn.
- The parent searches memory and passes what matters in `context`; children
  do not search it. When `mcp__engram__*` tools reach the child, ask it to
  save significant discoveries, decisions or fixes with
  `mcp__engram__mem_save` (project `<name>`) before returning.

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
Test-first: applies, runner <exact command> | exception: <which and why>

## Allowed edit surfaces        (writers only; see section 2)
path/to/file.py
src/module/**

## Verification                 (exact commands, run in the foreground)
<command>

## Known environmental failures (exact pre-existing failing tests/commands)

Rules: do not commit, push, stage or run destructive git; do not edit
outside the allowed surfaces; stop with status interaction_required when a
human decision is needed, including a derived candidate list.
Test-first: when it applies, observe RED before implementing, then GREEN,
then refactor with the focused tests green; for an exception, run the
proportionate checks. Report only observed RED/GREEN; never invent a runner.
Return: status completed|partial|blocked|interaction_required, summary,
files_changed, test-first (RED/GREEN observed, or the exception),
validation (<command>: <observed result>), risks.
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

## 3. Verifying a writer (risk-proportionate)

Judge the tier from what the change touches; an unclear tier is high.

| Tier | What it covers | Verification |
|---|---|---|
| Passive | documentation, images, comments with no executable effect | structural readback only |
| Medium | an ordinary behavior change covered by focused tests | the writer runs `## Verification` in the foreground and reports `<command>: <observed result>`; add a verifier child only when the writer ran on a small or low-effort model |
| High or unclear | security, credentials, data loss, concurrency, migrations, installers, public contracts, anything unclear | writer self-verification plus an independent read-only verifier child that re-runs the commands and reads the diff without the writer's context |

- A small or low-effort writer model raises the tier by one.
- The parent spot check (re-run one reported command before delivery) stays
  in every tier.
- Record per task the tier applied and the checks observed. Never assume low
  risk without evidence; a verifier that cannot run is reported as
  unavailable, never as a pass.
