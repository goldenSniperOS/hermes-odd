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
<!-- derived-from: gentle-ai@1ab243ca426d55dee64cf0ba693d0745cb1146c2 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@a1c4463f31eef337bffcbb057e2638a1947c5a72 assets/orchestrator.md -->
<!-- derived-from: gentle-shell@a1c4463f31eef337bffcbb057e2638a1947c5a72 assets/orchestrator-delegation.md -->
<!-- derived-from: gentle-shell@a1c4463f31eef337bffcbb057e2638a1947c5a72 assets/orchestrator-skills.md -->
<!-- derived-from: gentle-ai@1ab243ca426d55dee64cf0ba693d0745cb1146c2 internal/assets/skills/_shared/odd-orchestrator-sections.md -->

# ODD workflow for Hermes

Reference detail for the always-on "ODD workflow (hermes-odd)" section. The parent
session orchestrates; `delegate_task` children execute bounded units.
Formal SDD is not provided by this plugin.

## 1. Protocol (every request, in order)

1. **Authorize.** Investigation, review, audit, comparison and proposal or
   planning-only requests are read-only: no file writes, writers or
   implementation artifacts. Ambiguous or conditional change intent gets one
   clarification; stay read-only until it is answered.
2. **Explore** existing code and requirements first, proportionately.
3. **Resolve uncertainty** (section 4).
4. **Classify** by task size (section 3).
5. **Track before the first write** (large only) — load
   `hermes-odd:odd-feature-tracking`.
6. **Implement task by task** through the routing ladder (section 2), with
   the default test-first policy and proportionate checks (section 6).
7. **Close** with the verified outcome, every failed, skipped or pending
   check, and the next step. Verification covers one work-unit commit or PR
   slice, never a TODO checkbox and never the accumulated feature branch.

**Informed short approval.** Clarify only what the human needs to understand
to decide the action. A short "yes" or "go ahead" accepts the immediately
preceding concrete proposal: act on it and never re-ask. A preference alone
is not authorization, and approval never covers publish or destructive
steps the proposal did not name. Research findings and automatic pace
never authorize a mutation.

**Continuity.** Authorized in-scope steps continue without per-step
approval. A pending child is a wait, not a stop; its completion resumes the
work. Only a real human decision, an explicit stop, a denial or an
exhausted limit stops the work it covers, never independent authorized
work. Hedged wording is not a stop: "I may stop you later" asks for notes
and separate commits. Missing or declined proof blocks the completion claim
for that work only. Resolving an incident never cancels the objective.

**Project boundary.** Keep session work inside the project root and its
registered worktrees of the same clone. Before any read or write
outside the project root, ask once, naming the absolute path. Consent is
per target and per session: a script in the project that names an outside
path is not standing consent. No Hermes guard enforces this; missions to
children stay inside the same boundary.

## 2. Routing ladder

**Direct inline** is the default for small work and tracked work with no
writer reason: decide or verify within the evidence budget (one parallel
batch, bounded searches and line ranges). **Delegated direct** applies only
when a trigger below truly holds; file count, size or perceived risk never
force it. Load `hermes-odd:odd-delegation` before the first `delegate_task`
call.

### Delegation triggers

Parent rules, never passed to a child; no trigger holds by default, and
when in doubt work inline. Once one holds, call `delegate_task` before
continuing, then re-evaluate the task size.

1. **Mapping:** beyond the evidence budget (at most 3 calls, ~10k tokens),
   ~5+ sequential lookups or long-session mapping -> one read-only explorer
   child returning at most ~2k tokens with `path:line` evidence; spot-check
   once. Never explore files you will read anyway before writing inline.
2. **Writer (named reason only):** one bounded writer per unit for (a) two
   or more independent units of behavior (code, tests and docs together)
   with disjoint edit surfaces, each several files or
   roughly 100+ changed lines (a child spends minutes reading first),
   launched together in one turn; or (b) the long-session backstop.
   Dependent or smaller units run inline, one after another. Never for
   task size or file count.
3. **Preparation:** reading for a delegated write goes with that writer;
   an inline write reads inline.
4. **Incident:** wrong `cwd`, accidental repository or worktree mutation or
   a confusing environment -> stop writes, capture `git status`, diagnose
   apart, apply only confirmed recovery, then resume the objective.
5. **Long session:** at ~150k parent-context tokens (advisory; Hermes does
   not measure it), delegate the next bounded unit. Bound shell output to
   counts, `--stat`, `tail` or summaries.
6. **Verification:** only a change whose Risk line names a high-risk item
   gets an independent verifier child, after its own checks; size, an
   unclear change or the writer's model never add one. Otherwise its
   focused test and suite run inline (tiers: `hermes-odd:odd-delegation`
   section 3). The parent re-runs one reported command before claiming done.
7. **Route declaration:** for large work record the route per task and the
   trigger evidence in the feature document.

**Risk line.** Close every code change with `Risk: item N (reason)` or
`Risk: none`, per the high-risk list in `hermes-odd:odd-delegation`
section 3 (item 1: only data or effects that cannot be rebuilt). A diff
that changes shared code (options, parsers, helpers) other behavior uses
is item 3.

If `delegate_task` is unavailable, stop the complex work and say so; never
silently continue inline.

## 3. Task size

A task is **small** when all three hold: (1) understood: outcome and where
to change are known, no product decision is open, proven within one read
batch (at most 3 calls, ~10k tokens); (2) contained risk: no high-risk item;
(3) resumable: someone could finish from the original request and
`git diff` alone (the resume test). Files, commands, tests, fixes or a
requested todo list never decide size. **Large** only when the resume test
fails: several sessions, an external wait, deliverables the user wants
apart, or requirements too long to survive compaction.

Small path: inline across files, RED before the fix, focused test and suite
once each; no explorer, writer, verifier, feature document, mirror or
commits unless asked. Large work gets tracking; a writer only by the Writer
trigger.

## 4. Research depth and assumption challenge

- Recommend research only for a named uncertainty; depth follows
  consequence. The parent owns product decisions: one question, then stop.
- External evidence: prefer primary sources, attribute claims to URLs or
  code locations, separate facts, assumptions and gaps; never invent access.
  Delegated research goes to a fresh read-only child.
- At most one scoped read-only assumption challenge for a high-consequence
  unproven premise: name premise, evidence and consequence; no debate loop.
  Deterministic failures need fixes, not debate. Reuse sibling findings.

## 5. Lossless blocking prompts over chat

When you or a tool must block on the human (including a child's
`interaction_required` payload):

- Preserve the full envelope: why input is needed, every question and group
  in order, every option label and description, the selection mode and the
  allowed answers. Never summarize, reorder, relabel, merge or omit choices;
  never split one atomic decision across interactions.
- **Native route:** `clarify(questions=[...])` — up to 5 questions and 4
  choices each, recommended first. Its "Other" free-text row is rejected
  for closed decisions; ask again.
- **Fallback:** when `clarify` is unavailable, too small or non-interactive,
  send the complete envelope as one chat message with the answer syntax
  ("Reply 1, 2 or 3"), then **stop**; never choose, default or infer.
- **Answer validation:** accept only an answer in the allowed domain. For a
  closed single choice, trim and compare labels case-insensitively; accept
  exactly one match. Ordinal aliases for option N: `N`, `la N`, `opción N`,
  and `first` for option 1. A question about the block is answered from the
  envelope, then the envelope is re-presented. Invalid or ambiguous input
  -> re-present the full envelope and stop again. Hand a valid answer back
  to the blocked actor exactly once.

## 6. Checks and test-first

One default policy for every ODD behavior change; there is no TDD setting.

- **Test-first when it applies:** a relevant test can run deterministically
  and the expected outcome is clear. Observe RED (the new test fails for
  the intended reason) before implementing, make it GREEN with the smallest
  change, then refactor while the focused tests stay green.
- **What to test:** one RED test per requested rule, asserting every
  observable effect (output, exit code, stored data) through the public
  interface. For each existing command or option the change touches
  (shared options, parsers, helpers), one test proving its previous
  behavior still holds; no other cases. Only when shared code changed, run
  a differential check: the same commands against a `mktemp -d` copy of the
  base commit and against the change; an unrequested difference is a
  regression. When a command, option or message changes, update its help
  text and docs.
- **Presence is not applicability.** A test suite or framework existing in
  the repository does not by itself make the policy apply.
- **Otherwise, an exception:** passive documentation, no meaningful
  runnable RED, or no available runner. Say which and why in one line, then
  run proportionate checks (a readback for passive text).
- **Never invent evidence:** no RED or GREEN that was not observed, and no
  guessed test command. A missing command is a reported limitation.
- Record the runner and the observed RED/GREEN, or the exception, in the
  feature document and forward it in every implementation mission.
- Formatters and generators run before the final checks. Unavailable or
  declined proof is reported once, never retried in a loop. One verified
  change gets at most one scoped correction.
- Focused checks while iterating, applicable full checks at task close.

## 7. Commits, delivery and review workload

Each rule lives in one skill; load it by its qualified name, never a
same-named bare skill (those may carry workflows this plugin does not ship):

- `hermes-odd:work-unit-commits`: work-unit commits, Conventional Commit
  messages, the commit id as evidence, slice size and the running count.
- `hermes-odd:chained-pr`: the per-feature delivery strategy, the
  oversized delivery menu, slice boundaries and the `gh` commands.
- `hermes-odd:advisory-review-lenses`: the optional 4R advisory review of
  one commit or PR slice; no receipt. A review never replaces checks.
- `hermes-odd:judgment-day`: only when the user asks for a dual or
  adversarial review; advisory, no receipt.

Push, pull request creation and merge are the user's decisions.

## 8. Skills for children

Pass only the skills that match the unit (`skills_list`, plugin skills as
`hermes-odd:<name>`) as exact `skill_view` names under `Skills to load
before work`; children never rediscover skills. A missing skill is named,
then the smallest safe fallback continues.

## 9. Language boundary

Replies and blocking prompts use the user's language. Code, comments,
tests, commits, PR text, feature documents and missions are in English
unless the user or project convention says otherwise. Public comments
follow the target thread's language.
