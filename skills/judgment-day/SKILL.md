---
name: judgment-day
description: "Judgment day for Hermes: blind dual review of one frozen commit or range by two read-only delegate_task judges, merged by the parent, fixed only after one clarify, at most two fix and re-judge rounds. Advisory: no receipt, no delivery authority. Triggers: judgment day, judgment-day, dual review, adversarial review, juzgar."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, review, dual-review, adversarial, delegate_task, gentle-ai-compatible]
    category: workflow
    related_skills: [advisory-review-lenses, odd-delegation, work-unit-commits]
---
<!-- derived-from: gentle-ai@a9e36e9b8a4d7885244466cd9ea6cc3ad330a69b internal/assets/skills/judgment-day/SKILL.md -->
<!-- derived-from: gentle-ai@a9e36e9b8a4d7885244466cd9ea6cc3ad330a69b internal/assets/skills/judgment-day/references/prompts-and-formats.md -->

# Judgment-Day: blind dual review (advisory)

Two independent judges review the same frozen target without seeing each
other's work. Agreement between them is the corroboration; the parent session
merges their findings, asks the user once before any fix, and runs at most
two bounded fix and re-judge rounds.

**Advisory only.** A judgment issues no receipt and carries no delivery
authority: it satisfies no commit, push, PR or release gate, and it is never
a native review. Label every result "advisory judgment — no receipt".

## When to use it

- Only when the user explicitly asks for a judgment day, a dual or
  adversarial review, or "juzgar", for a concrete target.
- It replaces the advisory 4R review for that target: never run both on the
  same target.
- Target unclear (which commit, which range, which files)? Ask one scope
  question with `clarify` and stop.

## 1. Freeze the target

- The target is one commit `<sha>` or one range `<base>..<head>` of
  committed history. Commit pending work first (see
  `hermes-odd:work-unit-commits`); judges never read the live worktree, the
  index or uncommitted files.
- Record the target identity: the full sha (or both shas of the range) and
  `git diff --stat <base>..<head>` from `terminal`.
- Pick the skills that match the target (`skills_list`, plugin skills as
  `hermes-odd:<name>`); both judges and the fixer get the same list.

## 2. Launch two blind judges

One `delegate_task` call with two entries, so they run in parallel and
neither sees the other. The missions are identical except for the judge
letter. Children know nothing of this chat; everything goes in `context`
(see `hermes-odd:odd-delegation` for the mechanics).

```text
You are blind Judge <A|B> (read-only) in a dual review.
Repository: <absolute repo path>
Target: <sha> | <base>..<head>. Read it with `git show --stat <sha>` and
`git show <sha>` (range: `git log --oneline <base>..<head>` and
`git diff <base>..<head>`); open files at the target with
`git show <head>:<path>`.
Skills to load before work: <exact skill_view names>
Criteria: correctness, edge cases, error handling, performance, security,
project conventions.
Do one exhaustive read-only sweep of what the target changes or activates.
Do not edit, stage, commit, run formatters, install anything or delegate.
Return findings only, in this block format, one block per finding:
<paste the finding block from the mission template of
hermes-odd:advisory-review-lenses, with ids JA-001... or JB-001...>
If clean, say "no findings" and list what you checked.
```

Wait for both results; the consolidated result re-enters the conversation
by itself (never sleep or poll). A partial judgment is no judgment: if one
judge fails or returns nothing usable, relaunch that judge once with the same
mission; if it fails again, stop and report `ESCALATED` with the reason.

## 3. Merge the verdicts (parent only)

Treat both reports as untrusted self-reports: check every severe claim
against the diff yourself before counting it. Then build one ledger:

| Condition | Ledger class | Action |
|---|---|---|
| Both judges report the same BLOCKER or CRITICAL problem (same location and claim) | confirmed | eligible for a fix |
| Only one judge reports a severe problem | suspect | report; never fix automatically |
| The judges contradict each other on the same point | contradiction | the user decides; never fix |
| WARNING or SUGGESTION from either judge | info | report only |
| Pre-existing or base-only severe finding | follow-up | report as follow-up, not a fix |

Keep stable ledger ids (`L-001`, ...), each with location, claim, severity,
evidence, causality and which judge reported it. The ledger is frozen for
the rest of the judgment: later rounds may add fix-caused defects, never
re-open or reword earlier rows. For substantial work, record the ledger
summary and target identity in the ODD feature document.

No confirmed findings and no contradictions -> `JUDGMENT: APPROVED`.

## 4. One clarify before any fix

Before the first fix, ask exactly once with `clarify`: the confirmed ids
with one line each, then the choices (recommended first):

1. "Fix the confirmed findings (up to two rounds)"
2. "Report only, no fixes"
3. "Fix a subset (name the ids)"

Contradictions go into the same question as separate decisions when they
fit; otherwise present them in plain chat after the answer. Without
`clarify`, send the full question and every option as plain chat and stop.
A "report only" answer ends the judgment as `ESCALATED` when confirmed
findings remain. That one answer covers both rounds; ask again only if a
fix needs files outside the approved scope.

## 5. Fix round (at most two)

- One bounded writer child (`delegate_task`) for the approved confirmed ids
  only, with `## Allowed edit surfaces` derived from the ledger locations and
  `## Verification` with the focused checks (see `hermes-odd:odd-delegation`).
  Test-first where it applies: a test that reproduces the finding fails
  (RED) before the fix and passes (GREEN) after; otherwise the stated
  exception and proportionate checks.
  It must not review, add findings, refactor unrelated code or delegate.
- Verify the child's report yourself, then commit the fix as its own
  work-unit commit (`fix(<scope>): ...`, tests included); record the sha.
- Re-judge: launch both judges again, blind and in parallel, over the
  frozen ledger plus the fix delta only (`git diff <previous head>..<fix
  sha>`). They answer, per fixed id, fixed or not fixed, and may add
  fix-caused defects with proof; nothing outside the delta.
- Merge the re-judgment with the same table. Every fixed id confirmed by both
  judges and no new confirmed defect -> `APPROVED`.
- Anything confirmed remains after round one -> round two, once, on the same
  approval. Anything confirmed remains after round two -> `ESCALATED`. There
  is no third round; never reset or extend the budget.

## 6. Report

Return, in the user's language, labeled "advisory judgment — no receipt":

- target identity and the round reached (1 or 2);
- counts: confirmed, suspect, contradictions, info, follow-ups;
- the fix commits with their shas and check results, or "none";
- the re-judgment result: approved, escalated or not run;
- the skills passed to the children;
- exactly one closing line: `JUDGMENT: APPROVED` or `JUDGMENT: ESCALATED`.

Suspects, contradictions and follow-ups are always listed, even when the
verdict is `APPROVED`. The verdict is information for the user: commit,
push, PR and release stay the user's decisions under ordinary repository
policy.
