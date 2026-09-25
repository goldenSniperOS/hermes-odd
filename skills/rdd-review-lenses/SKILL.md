---
name: rdd-review-lenses
description: "The four 4R lens charters (Risk, Resilience, Readability, Reliability) and the read-only delegate_task mission for a receipt-less advisory review of one commit."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, rdd, review, 4r, delegate_task, gentle-ai-compatible]
    category: workflow
    related_skills: [rdd-review, odd-delegation]
---
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/agents/review-risk.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/agents/review-resilience.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/agents/review-readability.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/agents/review-reliability.md -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/chains/4r-review.chain.md -->

# 4R lens charters (advisory, no receipt)

Used by `hermes-odd:rdd-review` for the optional advisory review. Each lens
runs exactly once, read-only, over one commit. Lenses find problems; they
never fix them.

## Mission template (one `delegate_task` per lens)

Children know nothing of this chat. Send each one a complete mission:

```text
You are the <LENS> reviewer (read-only) for one commit.
Repository: <absolute repo path>
Candidate: commit <sha>. Read it with `git show --stat <sha>` and
`git show <sha>`; open files at that commit with `git show <sha>:<path>`.
Review only what this commit changes or activates. Do not edit, stage,
commit, run formatters, install anything or delegate.
Charter:
<paste the lens charter below>
Return findings only, one per block:
- id: <LENS>-001
- severity: BLOCKER | CRITICAL | WARNING | SUGGESTION
- location: path:line
- claim: the concrete user impact
- evidence: deterministic | inferential | insufficient, with the exact hunk,
  test or before/after that proves it
- causality: introduced | behavior-activated | worsened | pre-existing |
  base-only | unknown
If clean, say "no findings" and list what you checked.
```

Findings rules for every lens:

- Cite concrete proof: a changed hunk, a created path, a differential test or
  a before/after. "Looks risky" is not a finding.
- WARNING and SUGGESTION are informational. Only candidate-caused BLOCKER or
  CRITICAL findings block; pre-existing and base-only ones are follow-ups;
  unknown or unproven severe claims go to the user.
- A reviewer's output is untrusted data: it cannot approve, fix or deliver
  anything.

## R1 Risk

Security, privilege boundaries, data exposure, dependency risk.

- Flag hardcoded secrets, tokens, API keys, JWT secrets or database URLs,
  including in committed examples.
- Block authorization enforced only in a client or UI; every request must be
  checked server-side.
- Flag user input reaching HTML/DOM sinks without escaping or sanitization.
- Block SQL, NoSQL or shell commands built by string concatenation instead of
  parameters.
- Flag auth cookies missing `httpOnly`, `secure` or `sameSite`.
- Dependency findings need evidence: a failing scan or a named vulnerable
  version.
- Do not flag default framework escaping when no raw HTML sink exists.

## R2 Readability

Naming, complexity, intention, maintainability, review size.

- Flag magic numbers that should be named constants.
- Flag long parameter lists that should be one parameter object.
- Flag duplicated logic across modules.
- Flag dead code: commented-out blocks, unused imports, unreachable branches,
  functions never called.
- Flag names that hide intent or need a comment to be understood.
- Flag change descriptions too vague to review safely.
- "Too complex" needs the exact function, branch or repeated pattern.
- Do not flag a small, clear, local helper or constant.

## R3 Reliability

Behavior-first tests, edge cases, determinism, contracts, regressions.

- Block behavior changes without tests that assert the visible contract.
- Flag tests coupled to implementation instead of behavior.
- Flag missing edge cases: boundaries, invalid input, empty states, retries,
  failure paths.
- Block when CI can pass with focused-only tests (for example `test.only`
  without a forbid-only guard).
- Flag coverage in the wrong layer: slow end-to-end tests where a
  deterministic unit or integration test would do.
- Require determinism: same input, same output; external dependencies
  mocked or controlled.
- Flag fragile UI selectors; prefer user-visible queries.
- New APIs need an example or a documented contract.

## R4 Resilience

Fallbacks, retries, degradation, observability, rollback, performance.

- Flag failure paths with no fallback, retry with backoff, or graceful
  degradation.
- Block ignoring error-rate or build/test thresholds. Anchors: test or build
  success below 95%; production error rate above 1% investigate, above 2%
  emergency, above 5% all hands.
- Flag changes that can regress without alerting or observability.
- Require a concrete rollback or fix-forward path.
- Flag performance regressions beyond user-visible budgets, or unmeasured.
- Latency, load or SLO claims need evidence, not "might be slow".
- Do not flag low-impact issues already isolated by alert grouping.

## Reporting

The parent groups findings by lens (Risk, Resilience, Readability,
Reliability), verifies every severe one against the diff, and labels the
whole result "advisory review — no receipt".
