---
name: odd-workflow
description: "Organic Driven Development (ODD) for Hermes: routing, delegate_task missions, blocking prompts, checks, delivery."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, delegation, orchestration, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-feature-tracking]
---
<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/orchestrator-delegation.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/orchestrator-skills.md -->

# ODD workflow for Hermes

Reference detail for the always-on "ODD workflow (hermes-odd)" section. The parent
session orchestrates; `delegate_task` children execute bounded units.
Formal SDD is not provided by this plugin.

## 1. Protocol (every request, in order)

1. **Authorize.** Investigation, explanation, review, audit, comparison and
   proposal or planning-only requests are read-only: inspect, explain,
   compare and recommend, but never write files, delegate a writer or create
   implementation artifacts. Ambiguous or conditional change intent gets one
   clarification; stay read-only until it is answered.
2. **Explore** existing code and requirements first, proportionately.
3. **Resolve uncertainty** (section 4).
4. **Classify.** Substantial = two or more meaningful implementation steps,
   or progress worth recovering after an interruption. Not a line count.
5. **Track before the first write** — load `hermes-odd:odd-feature-tracking`.
6. **Implement task by task** through the routing ladder (section 2).
7. **Close** with the verified outcome, every failed, skipped or pending
   check, and the next step.

Research findings and automatic pace never authorize a mutation.

## 2. Routing ladder

Every authorized change takes exactly one route:

- **Direct inline:** decide or verify from 1–3 files; one mechanical,
  already-understood file change with no research and no open design
  decision; `git`/`gh` state commands.
- **Delegated direct:** one narrow mapping child when understanding needs 4+
  files; one writer child for 2+ non-trivial files. Reading that prepares a
  write and broad research also delegate.

File count, size or perceived risk never force a heavier route. Tests,
builds and installs may still use a fresh per-action child without changing
the route.

### Mandatory delegation triggers

Mandatory, not advisory. When one fires, stop and call `delegate_task`
before continuing; executing past it inline is a routing defect even if the
work succeeds. These are parent rules: never pass them to a child as
permission to orchestrate.

1. **Mapping (4-file rule):** understanding needs 4 or more files -> one
   read-only mapping child before deciding or writing.
2. **Writer (multi-file write rule):** 2 or more non-trivial files -> one
   bounded writer child. A mechanical second-file edit does not fire it.
3. **Preparation:** reading that prepares a write, broad research, or
   context compression goes with or ahead of the writer.
4. **Incident:** wrong `cwd`, accidental repository or worktree mutation,
   failed merge recovery, confusing test command or environment workaround ->
   stop writes, capture `git status`, diagnose separately, then apply only
   confirmed recovery steps.
5. **Long session:** about 20 tool calls, 5 exploratory reads or 2
   non-mechanical edits without delegation -> delegate the next unit.
6. **Verification:** executing check commands beyond a 1–3 file read-only
   check goes to a verifier child, unless the writer already ran them under
   `## Verification`; the parent still re-runs one reported command as a spot
   check before claiming done.
7. **Route declaration:** for substantial work record the route per task
   (inline or delegated) and the trigger evidence in the feature document.

If `delegate_task` is unavailable, stop the complex work and say so; never
silently continue inline.

## 3. Delegation mechanics

Load `hermes-odd:odd-delegation` before the first `delegate_task` call:
verified `delegate_task` behavior, the mission template, and the allowed
edit surface rules for writers.

## 4. Research depth and assumption challenge

- Recommend research only for a named uncertainty. Adapt depth to
  uncertainty and consequence; no fixed questionnaire.
- The parent owns product decisions: one focused question, then stop.
- For external evidence use available authorized web/documentation tools,
  prefer primary sources, attribute claims to URLs or code locations, and
  separate verified facts, assumptions, contradictions and gaps. If tools are
  missing, say so; never invent access.
- Delegate research to a fresh read-only child through `delegate_task`;
  return findings, recommendation, tradeoffs, open questions and
  implementation implications.
- At most one scoped read-only assumption challenge for a high-consequence
  unproven premise: name premise, evidence and consequence; no debate loop.
  Deterministic failures need fixes, not debate.
- Reuse sibling findings; re-verify only what is stale.

## 5. Lossless blocking prompts over chat

When you or a tool must block on the human (including a child's
`interaction_required` payload):

- Preserve the full envelope: why input is needed, every question and group
  in order, every option label and description, the selection mode and the
  allowed answers. Never summarize, reorder, relabel, merge or omit choices;
  never split one atomic decision across interactions.
- **Native route:** `clarify(questions=[...])` — up to 5 questions and 4
  choices each, recommended choice first, options only in `choices`. Hermes
  renders it as buttons on Telegram and as a numbered list on text gateways.
  `clarify` always adds an "Other" free-text row: for closed decisions,
  reject free text that is not one of the choices and ask again.
- **Fallback:** when `clarify` is unavailable, the envelope does not fit its
  limits, or the session is non-interactive, send the complete envelope as
  one plain chat message with the answer syntax (for example "Reply 1, 2 or
  3"), then **stop**. Do not choose, default, infer or launch dependent work.
- **Answer validation:** accept only an answer in the allowed domain. For a
  closed single choice, trim and compare labels case-insensitively; accept
  exactly one match. Ordinal aliases for option N: `N`, `la N`, `opción N`,
  and `first` for option 1. A question about the block (why, what a choice
  does) is answered from the envelope, then the envelope is re-presented.
  Invalid or ambiguous input -> re-present the full envelope and stop again.
  Hand a valid answer back to the blocked actor exactly once.

## 6. Checks and TDD

- Resolve TDD on/off from project or session configuration or an explicit
  user choice; keep its source and exact runner and record them in the
  feature document. Tests existing does not enable TDD.
- Forward mode, source and runner in every implementation mission. When on:
  observed RED before implementation, then GREEN, then REFACTOR; never invent
  evidence. When off: ordinary functional checks, not no checks.
- Unknown or conflicting mode, or a missing runner: disclose and resolve only
  what affects the next action; never invent a command.
- Focused checks while iterating, applicable full checks at task close.

## 7. Commits, delivery and review workload

- Every task closes with at least one work-unit commit on the feature branch
  (branch first when on the default branch), Conventional Commit message,
  tests and docs with the behavior; record the commit id as evidence.
- Push, pull request creation and merge are the user's decisions.
- About 400 authored changed lines (additions plus deletions) per task is a
  planning heuristic only — not a cap, stop, split or review trigger. If the
  clear solution exceeds it, say why and continue. Never strip whitespace or
  comments, omit tests or split artificially to fit. Forward this same
  advisory note to children.
- At feature-document creation forecast authored changed lines and keep a
  running count from commits. Pick one delivery strategy per feature:
  `ask-on-risk` (default), `auto-chain`, `single-pr` or `exception-ok`. When
  the forecast or count exceeds about 400 lines, apply it before the next
  commit: `ask-on-risk` asks once for `stacked-to-main` or
  `feature-branch-chain`; `auto-chain` asks only for a missing chain
  strategy. Cache the choices and record slice boundaries (which commits each
  PR holds) in the feature document. Resolve the `work-unit-commits` and
  `chained-pr` skills by name with `skills_list`; report if missing.
- The review candidate is a work-unit commit or a PR slice, never a TODO
  checkbox or the accumulated branch. Native review runs only under the
  user-owned RDD switch; load `hermes-odd:rdd-review` for it.

## 8. Skills for children

Hermes keeps its own skill index; there is no registry to refresh. Before
the first delegation, pick the skills that match the task (`skills_list`,
plugin skills as `hermes-odd:<name>`) and pass their exact `skill_view`
names under `Skills to load before work`. Children must load them before
working and must not rediscover skills on their own. Prefer the most specific
project skill; if an expected skill is missing, continue with the smallest
safe fallback and say which one was unavailable.

## 9. Language boundary

- Replies and blocking prompts: the user's language.
- Technical artifacts — code, comments, identifiers, tests, commits, PR
  text, feature documents, missions — in English unless the user asks
  otherwise or the project convention is non-English.
- Public comments (GitHub, Slack) follow the target thread's language.
