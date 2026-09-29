---
name: work-unit-commits
description: "ODD commit closure for Hermes: every task closes with a work-unit commit (one deliverable behavior with its tests and docs, Conventional Commit message), recorded as evidence; the advisory ~400-line per-task heuristic; the running line count that feeds chained-pr."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, git, commits, review-workload, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow, odd-feature-tracking, chained-pr]
---
<!-- derived-from: gentle-ai@d96a5d4f021b09d048958b518f550e1d8d629700 internal/assets/skills/work-unit-commits/SKILL.md -->
<!-- derived-from: gentle-ai@d96a5d4f021b09d048958b518f550e1d8d629700 internal/components/agentguidance/routing.go -->

# Work-unit commits (ODD)

The single home of hermes-odd's commit rules. Load it before closing an ODD
task, before deciding what goes into a commit, and before splitting work into
commits. PR slicing and delivery strategies live in `hermes-odd:chained-pr`;
the feature document itself in `hermes-odd:odd-feature-tracking`.

## 1. What a work unit is

A commit is one deliverable unit: a behavior, a fix, a migration or a
documentation change that stands on its own.

| Rule | Meaning |
|---|---|
| One purpose | The diff and message explain why the commit exists. |
| Not by file type | Never "models", then "services", then "tests" when none works alone. |
| Tests travel with code | The tests that verify a behavior land in the same commit. |
| Docs travel with the change | README, docs and CHANGELOG lines ship with the behavior they describe. |
| Repository still works | Applying only this commit leaves the project building and its checks passing. |
| Clean rollback | Reverting it removes this unit and nothing unrelated. |
| PR-ready | Each commit could become its own PR slice if the change grows. |

| Weak | Better |
|---|---|
| `add models` | `feat(auth): add token validation model with tests` |
| `add services` | `feat(auth): validate tokens in the login flow` |
| `add tests` | tests inside each behavior commit |
| `update docs` | docs inside the commit whose behavior they explain |

## 2. ODD task closure

- Every substantial ODD task closes with at least one work-unit commit on the
  feature branch. When the current branch is the default branch, create the
  feature branch first, unless the user explicitly chose to commit to the
  default branch (record that choice in the feature document).
- The message is a Conventional Commit (`feat`, `fix`, `docs`, `refactor`,
  `test`, `chore`, optional scope, `!` for breaking) that states the
  outcome, not the file list. Follow the repository's own commit rules when
  it has them.
- Commit only after the task's outcome and checks were observed. Children
  never commit: the parent verifies a writer's report, then commits.
- Record the commit id (short sha is enough) and the observed check results
  under Evidence in `odd/tasks/<feature>.md`, then update the Engram mirror
  and the `todo` projection (`hermes-odd:odd-feature-tracking`).
- Push, pull request creation and merge are the user's decisions. A
  delegated or granted push policy is recorded in the feature document and
  followed exactly; nothing here grants it.
- The review candidate is that work-unit commit, or the PR slice it belongs
  to: never a TODO checkbox and never the accumulated feature branch.

## 3. The ~400-line heuristic (advisory)

- About 400 authored changed lines (additions plus deletions) per task is a
  planning heuristic only: not an acceptance criterion, cap, stop, split,
  counter or review trigger.
- Prefer the smallest coherent behavior with its tests and docs. If the clear
  solution is larger, say why in one line and continue; no size-only rework.
- Never shrink a diff cosmetically: no deleting comments, blank lines, docs
  or tests, no minifying or compressing code, no gratuitous abstractions and
  no artificial splits to meet the number.
- Forward this same advisory note in every implementation mission.

## 4. Before each commit

Run in `terminal` and check the story:

```bash
git status --short
git diff --stat            # unstaged
git diff --cached --stat   # staged
git log --oneline -5       # the repository's message style
```

Checklist:

- [ ] One clear purpose; the repository works with only this commit applied.
- [ ] Tests and docs for this unit are included where they apply.
- [ ] The focused check command and its observed result are recorded, with
      the observed RED then GREEN when test-first applied, or the exception
      and its reason (`hermes-odd:odd-workflow` section 6).
- [ ] A runtime check (command or scenario) and its result are recorded, or
      `N/A` with the reason when no runtime boundary exists.
- [ ] The rollback boundary names the files or behavior a revert removes.
- [ ] Nothing unrelated is staged (pre-existing changes stay unstaged).
- [ ] The message explains the outcome.

## 5. Running line count

After each commit add its authored size to the feature document's Delivery
section: `git show --shortstat --format= <sha>` (insertions plus deletions;
exclude generated files, lockfiles and vendored code from the authored
count, and say which were excluded). The branch total against its base is
`git diff --shortstat <base>...HEAD`.

When the forecast or the running count passes about 400 authored changed
lines for the branch, load `hermes-odd:chained-pr` before the next commit:
the feature's delivery strategy decides what happens next.
