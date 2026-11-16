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
- Parallel read-only mappers on non-overlapping topics are fine.
- One launch per distinct task: before calling `delegate_task`, check that
  the same role and mission were not already launched this turn.
- The parent searches memory and passes what matters in `context`; children
  do not search it. When `mcp__engram__*` tools reach the child, ask it to
  save significant discoveries, decisions or fixes with
  `mcp__engram__mem_save` (project `<name>`) before returning.
- With the recall provider (Hermes memory provider `recall`), children can
  only read memory: recall refuses writes outside the primary agent. Ask the
  child to return significant discoveries, decisions and fixes in its final
  summary (the Key Learnings block); the parent saves them with `mem_save`
  after verifying them.

### Parallel writers

Independent units are launched together in one turn, as entries of one
`delegate_task` call. Work in another repository goes in a fresh worktree
from its main, never a checkout someone else may use. Units in the same
local repository share the tree with disjoint edit surfaces:

- the parent owns git; writers never stage, commit or run repository-wide
  formatters, generators or installs;
- a shared file has one owner, or the parent edits it at the end; units
  that need the same file use separate worktrees;
- the parent checks each writer's diff against its surface before
  accepting it, then runs one seam check at the end (the full suite, once);
- each mission names the existing helpers its unit must reuse for shared
  state and the invariants they keep (ordering, uniqueness, validation,
  normalization): parallel units cannot see each other.

### Mission template

Write missions in English, but hand requirements off by reference to the
feature document's `## Specs`, never paraphrased; without a document,
include the user's request verbatim. `goal` is one sentence; `context`
carries everything else, because the child knows nothing of this chat:

```text
Role: read-only mapper | bounded writer | verifier
Repository: <absolute repo root>, branch <branch>
Spec: odd/tasks/<feature>.md, T<n>, S<a>-S<b> (read until `## Log`;
  report which `S#` you covered) | no document: <request verbatim>
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
human decision is needed, including a derived candidate list. When resumed
or steered, do not re-read skills or specs already read unless they
changed. Keep test scratch outside the worktree (`mktemp -d`); before
returning, check `git status --short` for caches or scratch you created and
name leftovers instead of deleting them.
Test-first: when it applies, observe RED before implementing, then GREEN,
then refactor with the focused tests green; for an exception, run the
proportionate checks. Report only observed RED/GREEN; never invent a runner.
Return at most ~2k tokens, never restating the task, spec or unchanged
files: status completed|partial|blocked|interaction_required, summary,
files_changed, test-first (RED/GREEN observed, or the exception),
validation (<command>: <observed result>), risks, leftovers.
Close with a "## Key Learnings" block of 1-5 numbered standalone facts,
or omit it when there is nothing reusable.
```

Pass only skills that match the unit: no commit skill to a child that will
not commit. A resumed or steered child does not re-read what it already
read. Use `output_schema` only for fields you will read, e.g. `status` and
`files_changed`. Omit the Key Learnings instruction when the child must return
strict JSON. A failing command not named under Known environmental failures
means `partial`, never `completed`.

## 2. Allowed edit surfaces (mandatory for writers)

The parent derives the surface before launching a writer: the files the
change must touch plus directories where new files are authorized. Every
new writer launch carries `## Allowed edit surfaces`; a steer or
continuation that changes it passes the full list again (a replacement,
not a union).

- Exact repository-relative paths or narrow globs, one per line; never `.`,
  a bare repository root or an absolute path. Wrap paths containing spaces in
  backticks.
- List pre-existing untracked targets explicitly.
- Nothing beyond the delegated task: a surface wider than the task is the
  same defect as no surface.
- If the surface cannot be derived, do not launch the writer and never ask
  the human to author paths. Present the derived candidate list as an
  approve/decline choice using the lossless blocking prompt rules in
  `hermes-odd:odd-workflow`.
- A writer asking for another path: when it serves the authorized objective
  and no other unit owns it, the parent adds the path itself and relaunches.
  Ask the human only for new scope, another repository, a destructive step
  or after a denial.
- A rejected launch is repaired once for what the rejection names and is
  never resent unchanged.

## 3. Verifying a change (risk-proportionate)

Judge the tier from what the change touches. A change is **high risk**
when a mistake would be hard to detect, hard to undo, or reaches beyond the
change; it touches:

1. data or irreversible effects that cannot be rebuilt: migrations,
   changing or deleting existing stored data, persisted format changes (not
   saving new records, nor a dev or test database a seed or backup
   rebuilds);
2. security: auth, permissions, credentials, secrets, guards, sandbox;
3. contracts others consume: changing or removing a public API, CLI flags,
   config formats, published exports, or mirrored prompts others already
   consume (not adding a flag, command or optional field; requested changes
   are not high risk by themselves, unrequested breaks in shared code are);
4. concurrency: locks, races, async ordering;
5. delivery or environment: installers, release, CI, deploy, dependencies;
6. no test would catch a regression in what changes.

Count "unclear" as high only when a bounded look cannot tell whether items
1-5 apply.

| Tier | What it covers | Verification |
|---|---|---|
| Passive | documentation, images, comments with no executable effect | structural readback only |
| Medium | an ordinary behavior change covered by focused tests | whoever made the change runs its focused test and suite (a writer runs `## Verification` in the foreground and reports `<command>: <observed result>`); no separate verifier, whatever model wrote it |
| High | only when the parent names the high-risk item the change touches | that self-verification plus an independent read-only verifier child that re-runs the commands and reads the diff without the writer's context |

- The verifier runs only for a named item: never for task size, an unclear
  change, or the model or effort that wrote it. An unclear change keeps
  self-verification until the parent names the item that applies.
- When several deliveries of one feature were written inline, run one
  verifier at the feature's end; verify per unit only when that unit names
  a high-risk item.
- Verifier blockers get one correction batch and one recheck limited to
  them; with a blocker still open the unit stays `partial`, naming the
  decision it needs, while independent authorized work continues.
- The parent spot check (re-run one reported command before delivery) stays
  in every tier.
- Record per task the tier applied and the checks observed. A verifier that
  cannot run is reported as unavailable, never as a pass.

### Verifier mission by change kind

The mission names the change kind and the baseline commit. The verifier
does not re-run the writer's suite (the parent spot check covers it); it
runs the spec's examples and the commands the parent authorized, plus its
own probes from the request: boundaries, malformed input, exact errors and
exit codes. Mutating probes run only against isolated state (a `mktemp -d`
copy); stored data stays byte-identical after every rejected command.

- External tool or environment: reproduce the real case with the real tool
  and configuration; a mismatched fixture is not proof.
- Prompt or contract text: compare each removed or rewritten sentence with
  the baseline and report every lost qualifier or rule turned absolute.
- A failure the user reported: run the user's exact command at the baseline
  first; it counts as reproduced only when it fails there with the user's
  error, and the fix is verified only when it then passes.

It returns a verdict per `S#`, and its probes as ready-to-add regression
tests; they become tests through the writer, never written by the verifier.
