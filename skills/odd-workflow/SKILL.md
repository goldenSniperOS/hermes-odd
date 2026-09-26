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
    related_skills: [odd-feature-tracking, odd-delegation, work-unit-commits, chained-pr]
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
- A `TDD mode: <mode>` line in the always-on section is the user's explicit
  choice from the hermes-odd setup (`hermes-odd:setup`, `/odd_setup tdd`);
  record its source as "hermes-odd setup". `strict`: TDD on everywhere;
  `off`: ordinary functional checks; `per project`: resolve from the
  project's own configuration and detect its runner, asking once if unclear.
  Without the line, resolve as above.
- Forward mode, source and runner in every implementation mission. When on:
  observed RED before implementation, then GREEN, then REFACTOR; never invent
  evidence. When off: ordinary functional checks, not no checks.
- Unknown or conflicting mode, or a missing runner: disclose and resolve only
  what affects the next action; never invent a command.
- Focused checks while iterating, applicable full checks at task close.

## 7. Commits, delivery and review workload

Each rule lives in one skill; load it by its qualified name, never a
same-named bare skill (those may carry workflows this plugin does not ship):

- `hermes-odd:work-unit-commits`: closing every task with a work-unit
  commit, Conventional Commit messages, the commit id as evidence, the
  advisory ~400-line per-task heuristic and the running line count.
- `hermes-odd:chained-pr`: the per-feature delivery strategy (`ask-on-risk`,
  `auto-chain`, `single-pr`, `exception-ok`), the chain strategy
  (`stacked-to-main`, `feature-branch-chain`), slice boundaries and the `gh`
  commands.
- `hermes-odd:rdd-review`: the review candidate (a work-unit commit or a PR
  slice) and native review under the user-owned RDD switch.
- `hermes-odd:judgment-day`: only when the user asks for a dual or
  adversarial review; advisory, no receipt.

Push, pull request creation and merge are the user's decisions.

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
