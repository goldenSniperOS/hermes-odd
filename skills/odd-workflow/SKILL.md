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
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator.md -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator-delegation.md -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator-skills.md -->
<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/assets/skills/_shared/odd-orchestrator-sections.md -->

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
6. **Implement task by task** through the routing ladder (section 2), with
   the default test-first policy and proportionate checks (section 6).
7. **Close** with the verified outcome, every failed, skipped or pending
   check, and the next step. Verification covers one work-unit commit or PR
   slice, never a TODO checkbox and never the accumulated feature branch.

Research findings and automatic pace never authorize a mutation.

**Project boundary.** Keep session work inside the project root and its
registered worktrees of the same clone. Before any read or write
outside the project root, ask once, naming the absolute path. Consent is
per target and per session: a script in the project that names an outside
path is not standing consent. Hermes has no guard that enforces this; it is the
parent's rule, and missions to children stay inside the same boundary.

## 2. Routing ladder

Every authorized change takes one route. **Direct inline** is the default,
for small work and for tracked work with no writer reason: decide or verify
within the evidence budget (one parallel batch of at most 3 calls and ~10k
tokens, bounded searches and line ranges); one understood change stays
inline even across files, and its focused test and suite run inline once
each. **Delegated direct** applies only when a trigger below truly holds.
File count, task size or perceived risk alone never force it; tests,
builds and installs may still use a per-action child.

### Delegation triggers

Parent rules, never passed to a child. Each holds only when its condition
truly holds; no trigger holds by default, and when in doubt work inline.
Once one holds, call `delegate_task` before continuing, then re-evaluate
the task size.

1. **Mapping:** beyond the evidence budget (at most 3 calls, ~10k tokens),
   ~5+ sequential lookups or long-session mapping -> one read-only explorer
   child returning at most ~2k tokens with `path:line` evidence; spot-check
   once. Never explore files you will read anyway before writing inline.
2. **Writer (named reason only):** one bounded writer per unit for (a) two
   or more independent units of behavior (code, tests and docs together)
   with disjoint edit surfaces, each several files or
   roughly 100+ changed lines (a child spends minutes reading first), launched
   together; or (b) the long-session backstop. Dependent or smaller units
   run inline, one after another. Never for task size or file count.
3. **Preparation:** reading that prepares a delegated write, and broad
   research, go with that writer; an inline write reads inline.
4. **Incident:** wrong `cwd`, accidental repository or worktree mutation,
   failed merge recovery or a confusing environment -> stop writes, capture
   `git status`, diagnose separately, apply only confirmed recovery steps.
5. **Long session:** at ~150k parent-context tokens (advisory; Hermes does
   not measure it), delegate the next bounded unit. Bound shell output to
   counts, `--stat`, `tail` or summaries.
6. **Verification:** only a change whose Risk line names a high-risk item
   gets an independent verifier child, after its own checks; size, an
   unclear change or the writer's model never add one. Otherwise its
   focused test and suite run inline (tiers: `hermes-odd:odd-delegation`
   section 3). The parent re-runs one reported command before claiming done.
7. **Route declaration:** for substantial work record the route per task
   and the trigger evidence in the feature document.

**Risk line.** Close every code change with `Risk: item N (reason)` or
`Risk: none`, per the high-risk list in `hermes-odd:odd-delegation`
section 3 (item 1: only data or effects that cannot be rebuilt). A diff
that changes shared code (options, parsers, helpers) other behavior uses
is item 3.

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

## 6. Checks and test-first

One default policy for every ODD behavior change; there is no TDD setting to
choose or configure.

- **Test-first when it applies:** a relevant test can run deterministically
  and the expected outcome is clear. Then observe RED (the new or changed
  test fails for the intended reason) before implementing, make it GREEN
  with the smallest change, cover the relevant alternate cases, and refactor
  while the focused tests stay green.
- **Presence is not applicability.** A test suite or framework existing in
  the repository does not by itself make the policy apply.
- **Otherwise, an exception:** passive documentation, a change with no
  meaningful runnable RED, or no available runner. Say which exception and
  why in one line, then run proportionate functional or structural checks
  (a readback for passive text). An exception never means no checks.
- **Never invent evidence:** no RED or GREEN that was not observed, and no
  guessed test command. A missing command is a reported limitation.
- Record the runner and the observed RED/GREEN, or the exception and its
  reason, in the feature document; forward the same in every implementation
  mission (`hermes-odd:odd-delegation`) and refresh it on resume.
- Source-changing normalizers (formatters, generators, fixers) run before
  the final checks; if bytes change after the checks, re-run the affected
  checks. A quick check runs once; proof that stays unavailable, partial or
  declined becomes one "needs your decision" line, never a retry loop. One
  verified change gets at most one scoped correction.
- Focused checks while iterating, applicable full checks at task close.

## 7. Commits, delivery and review workload

Each rule lives in one skill; load it by its qualified name, never a
same-named bare skill (those may carry workflows this plugin does not ship):

- `hermes-odd:work-unit-commits`: closing every task with a work-unit
  commit, Conventional Commit messages, the commit id as evidence, the
  advisory ~400-line per-task heuristic and the running line count.
- `hermes-odd:chained-pr`: the per-feature delivery strategy (`ask-on-risk`,
  `auto-chain`, `single-pr`, `exception-ok`), the oversized delivery menu
  (`feature-branch-chain`, `stacked-to-main`, or one `single-pr`, least
  recommended), slice boundaries and the `gh` commands.
- `hermes-odd:advisory-review-lenses`: the optional 4R advisory review of
  one work-unit commit or PR slice, only on request; it carries no receipt.
  A code review never replaces applicable tests, builds or functional checks.
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
