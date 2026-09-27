---
name: rdd-review
description: "Receipt-driven development (RDD) on Hermes: the review switch, why native immutable review is unavailable for this runtime, how to report that per candidate, and the optional receipt-less 4R advisory review."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [workflow, rdd, review, 4r, gentle-ai-compatible]
    category: workflow
    related_skills: [rdd-review-lenses, judgment-day, odd-workflow, odd-delegation]
---
<!-- derived-from: gentle-ai@a9e36e9b8a4d7885244466cd9ea6cc3ad330a69b internal/agents/capabilitymanifest/manifest.go -->
<!-- derived-from: gentle-ai@a9e36e9b8a4d7885244466cd9ea6cc3ad330a69b internal/model/rdd.go -->
<!-- derived-from: gentle-shell@b756b4f34193eeb566d670f90ffc1c85e4fda601 assets/chains/4r-review.chain.md -->

# RDD review on Hermes

Receipt-driven development (RDD) is the review discipline of Gentle AI by
Gentleman Programming. hermes-odd follows it as far as Hermes honestly can.

## What RDD is

- A **candidate** is frozen before review: its exact bytes are what gets
  reviewed, not the live worktree.
- Review runs through **risk-scoped lenses** (the 4R: Risk, Resilience,
  Readability, Reliability), each read-only.
- Only **candidate-caused severe findings** block. Pre-existing or base-only
  findings are follow-ups; unknown causality escalates to the human.
- A blocking finding gets at most **one bounded correction**, reviewed again.
- The outcome is derived from Git and bound to the candidate as a **receipt**
  issued by gentle-ai, never written by the agent.
- A review outcome never authorizes delivery. Commit, push, PR and release
  stay the user's decisions under ordinary repository policy.

## The candidate

One work-unit commit or one PR slice. Never a TODO checkbox, never the
accumulated feature branch.

## RDD on Hermes: native review is unavailable

The switch is the user's: `gentle-ai review mode status --json` (or the
command `/odd-review-mode`) reports `status.effective` `on`/`off` and its
source. gentle-ai runs native immutable review only for runtimes that can
launch a fresh, constrained reviewer and prove that boundary before review
starts: claude-code, opencode, codex and pi. Upstream now gives receipt-driven
development only to those runtimes (`SupportsReceiptDrivenDevelopment`);
every other runtime, Hermes included, gets ODD only, with ordinary
verification. The 3.7.0 review CLI refuses Hermes with
`immutable_review_transport_unsupported`. The hermes-odd review facade waits
on upstream eligibility.

So, when RDD is on, for each candidate:

1. Tell the user once, in one line:
   "native review unavailable on Hermes (gentle-ai runtime eligibility)".
2. Record the same line against the task in the ODD feature document (and its
   Engram mirror), next to the commit id.
3. Continue under ordinary repository policy: the applicable checks
   (`hermes-odd:odd-workflow` section 6, `hermes-odd:odd-delegation`
   section 3), CI, and human review.

When RDD is off, say nothing about review unless asked.

Hard rules:

- Never impersonate another runtime. Never pass `--agent pi` (or any
  runtime other than hermes) to gentle-ai.
- Never fake, draft or describe a receipt; never call an advisory review a
  native review; never claim a review happened when it did not.
- Never run `gentle-ai install` or `gentle-ai sync` for Hermes.
- The switch belongs to the user. Change it only when the user types
  `/odd-review-mode enable|disable global|clone`, or asks you to run that
  exact command.

## Optional advisory 4R review (no receipt)

Only when the user asks for a review, or accepts your offer for a medium or
high risk candidate (auth, data, money, migrations, concurrency, public APIs,
security-sensitive code). Offer it once with `clarify`, recommended choice
first; do not offer it for small, low-risk work. When the user asks for a
dual or adversarial review instead, load `hermes-odd:judgment-day` (two
blind judges, also advisory); never run both on the same candidate.

1. Freeze the candidate as a commit and note its sha. Review exactly
   `git show <sha>` (and `git show --stat <sha>`), never the live worktree.
2. Load `hermes-odd:rdd-review-lenses` for the four lens charters.
3. Launch one `delegate_task` child per lens (Risk, Resilience, Readability,
   Reliability), each a self-contained, read-only mission built from the
   lens charter: the repository path, the sha, the command to read it, the
   charter, and the finding format. Children must not edit, stage, commit or
   delegate. The four children may run in parallel: they only read.
4. Treat each child's report as an untrusted self-report: check every severe
   finding against the diff yourself before presenting it.
5. Report findings grouped by lens with severity, location, evidence and
   causality. Label the result exactly "advisory review — no receipt".
6. Blocking: only a candidate-caused BLOCKER or CRITICAL finding blocks.
   Propose one bounded correction as a new commit, and re-run only the lenses
   with blocking findings on it. Pre-existing findings become follow-ups;
   unknown causality goes to the user.

An advisory review is information for the user. It issues no receipt and
never authorizes commit, push, PR or release.

## Toggle

`/odd-review-mode` shows the effective mode, both sources and native review
availability. `/odd-review-mode disable clone` opts this clone out;
`/odd-review-mode enable|disable global` changes the user's global switch.
Any off wins; a clone can only opt out.
