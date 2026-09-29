---
name: chained-pr
description: "PR slicing for Hermes under a 400-line review budget: the ODD delivery strategies (ask-on-risk, auto-chain, single-pr, exception-ok), stacked PRs vs a feature-branch chain with a tracker PR, and the gh commands to run through terminal."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, odd, git, github, pull-requests, review-workload, gentle-ai-compatible]
    category: workflow
    related_skills: [work-unit-commits, odd-feature-tracking, odd-workflow]
---
<!-- derived-from: gentle-ai@d96a5d4f021b09d048958b518f550e1d8d629700 internal/assets/skills/chained-pr/SKILL.md -->
<!-- derived-from: gentle-ai@d96a5d4f021b09d048958b518f550e1d8d629700 internal/assets/skills/chained-pr/references/chaining-details.md -->
<!-- derived-from: gentle-ai@d96a5d4f021b09d048958b518f550e1d8d629700 internal/components/agentguidance/routing.go -->

# Chained PRs (400-line review budget)

A reviewer can hold about 400 changed lines (additions plus deletions) and
about an hour of attention. This skill decides how a feature reaches review
in slices of that size. Commits themselves follow
`hermes-odd:work-unit-commits`.

## When to load it

- A planned PR may exceed 400 changed lines.
- An ODD feature's forecast, or its running authored count from work-unit
  commits, passes about 400 lines.
- The user asks for stacked or chained PRs, review slices or reviewer-load
  control.

The per-task ~400-line heuristic of `hermes-odd:work-unit-commits` never
forces a split by itself; this budget reads the accumulated branch.

## 1. Delivery strategy (one per feature)

Choose it when the feature document is created and record it in its
Delivery section, with the forecast (authored lines from the task list,
generated files excluded) and the running count.

| Strategy | Over the budget |
|---|---|
| `ask-on-risk` (default) | Ask once for a chain strategy before the next work-unit commit. |
| `auto-chain` | Slice automatically; ask only when no chain strategy is cached. |
| `single-pr` | Keep one PR and require a size exception; never ask for a chain. |
| `exception-ok` | Keep one PR and record the accepted size exception; never ask for a chain. |

Under the budget every strategy keeps one focused PR.

## 2. Chain strategy (asked once, then cached)

Ask with `clarify`, one question, recommended first:

1. **Stacked PRs to the default branch** (`stacked-to-main`): each slice can
   land on its own, in order.
2. **Feature-branch chain** (`feature-branch-chain`): nothing may land until
   the whole feature is integrated.

Without `clarify`, send the full question and both options as plain chat and
stop. Record the answer in the feature document and never mix strategies
within one feature.

| | Stacked to default branch | Feature-branch chain |
|---|---|---|
| Landing | each slice ships in order | the feature lands with the tracker |
| Rollback | revert one merged slice | hold or revert the feature branch |
| Risk | partial behavior reaches the default branch | nothing lands early |
| Effort | retarget or rebase after each merge | tracker PR, strict diff hygiene |

## 3. Rules

- The budget shapes the slicing, never the code: no deleting comments,
  blank lines, docs or tests, no compressing or restyling to fit.
- One honest slicing pass. If no cohesive split fits, keep the best one,
  report the real line count and why it cannot shrink, and recommend a size
  exception (the repository's `size:exception` label or its equivalent).
- One deliverable work unit per PR; its tests and docs travel with it. Each
  slice is a whole number of work-unit commits.
- Every PR states where it starts, what it delivers, what it depends on,
  what follows and what is out of scope, plus the chain diagram with the
  current PR marked `📍`.
- Verify the repository's default branch before creating branches or PRs:
  `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Use it
  as the base; `stacked-to-main` is only the strategy's name.
- A diff that shows another slice's changes is a base bug: retarget or
  rebase until only the current unit remains.
- Record slice boundaries (which commits each PR holds) in the feature
  document.
- Push and PR creation are the user's decisions. Plan slices and prepare
  local branches freely; run `git push` and `gh pr create` only when the user
  asked for them or recorded a policy that grants them.

## 4. Decision table

| Condition | Action |
|---|---|
| ≤400 changed lines and focused | one PR |
| >400, slices can land independently | stacked PRs to the default branch |
| >400, the feature must integrate first | feature-branch chain with a draft tracker PR |
| generated, vendored or migration diff that cannot split | ask for a size exception |
| no cohesive split fits after one pass | best split, report the overage, recommend a size exception |

## 5. Stacked PRs to the default branch

```text
<default> <- PR 1: foundation
               └── PR 2: slice built on PR 1
                     └── PR 3: slice built on PR 2
```

PR 1 targets the default branch; each later PR targets the previous PR's
branch. After a parent merges, retarget the next PR
(`gh pr edit <n> --base <default>`) and rebase it so only its own slice
shows.

## 6. Feature-branch chain

```text
<default>
 └── feat/<feature>                 tracker PR (draft, do not merge yet)
      └── feat/<feature>-01-<slice> PR 1, base feat/<feature>
           └── feat/<feature>-02-<slice> PR 2, base feat/<feature>-01-<slice>
```

1. Create `feat/<feature>` from the default branch and open the tracker PR to
   it as a draft (`gh pr create --draft`), stating it must not merge before
   the chain completes.
2. Slice 1 branches from the tracker and targets it; each later slice
   branches from the previous slice and targets it.
3. Integrate the slices in order; merge the tracker only when every slice is
   reviewed and integrated.

## 7. Chain context for the PR body

Append to the repository's PR template; never replace its required
sections.

```markdown
## Chain context

| Field | Value |
|---|---|
| Chain | <feature or stack name> |
| Tracker PR | <#N or "not needed"> |
| Position | <k of n> |
| Base | `<target branch>` |
| Depends on | <PR, issue or "none"> |
| Follow-up | <next PR or "none"> |
| Review budget | <additions + deletions> / 400 |
| Starts at | <branch or state this builds on> |
| Delivers | <the standalone result of this PR> |

<default>
 └── #N previous PR
      └── 📍 #N this PR
           └── #N next PR

Includes: <this unit>. Excludes: <deferred work>.
Checks: CI expected green; one deliverable scope; revertible alone; tests,
docs or manual verification cover it.
```

## 8. Commands (`terminal`)

```bash
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
git diff --shortstat <base>...HEAD          # size of the next slice
gh pr create --draft --base <default> --title "feat(<scope>): <feature> (tracker)" --body-file <file>
gh pr create --base <parent branch> --title "feat(<scope>): <slice>" --body-file <file>
gh pr view <n> --json additions,deletions,changedFiles,baseRefName,url
gh pr edit <n> --base <new base>             # retarget after a parent merges
```

Write PR bodies to a file outside the repository or pass `--body`; never
commit them.

## 9. Report

Return the delivery and chain strategy, the PR order, the current PR's
boundary (commits), the chain diagram, the budget (additions plus deletions
per PR), the verification plan per PR and any size-exception reason.
