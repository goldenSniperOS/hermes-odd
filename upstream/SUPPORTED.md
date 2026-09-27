# Upstream support matrix

hermes-odd adapts the ODD and RDD workflows of
[gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) and
[gentle-shell](https://github.com/Gentleman-Programming/gentle-shell) (npm
`gentle-pi`). This file is the human view of
[`upstream.lock.json`](upstream.lock.json), which is authoritative and checked
by `tests/test_upstream_lock.py`. It records which upstream versions are
supported, which upstream files each hermes-odd component derives from, and a
triage decision for every upstream change.

## Supported versions

| Upstream | Supported release | Pinned commit | gentle-ai binary min |
|---|---|---|---|
| gentle-ai | v3.7.0 (pinned to later `main`) | `a9e36e9b8a4d7885244466cd9ea6cc3ad330a69b` (2026-09-27) | 3.7.0 (tested 3.7.0) |
| gentle-shell (npm `gentle-pi` 3.7.0) | v3.7.0 (pinned to later `main`) | `b756b4f34193eeb566d670f90ffc1c85e4fda601` (2026-09-26, `v3.7.0-208-gb756b4f`) | 3.7.0 (pinned by gentle-pi 3.7.0) |

Notes:

- **No release after v3.7.0.** Neither upstream has tagged a release since
  v3.7.0 (gentle-shell `package.json` and its bundled gentle-ai installer
  still say 3.7.0), so both pins follow `main` (T11, 2026-09-27): gentle-ai
  `a9e36e9`, 134 commits after the previous pin `f182ea2`; gentle-shell
  `b756b4f`, 208 commits after the tag. Every commit is triaged below. The
  binary minimum stays 3.7.0, the latest release.
- **gentle-ai tag vs history.** The `v3.7.0` tag points at `6dee8f8`, which is
  not on gentle-ai's current `main` (its history was rewritten to drop the
  `.engram/` directory); `f182ea2` (the pin until T11) is its main-history
  equivalent.
- **RDD on Hermes, officially.** Since gentle-ai `5ffb65fc` upstream gives
  receipt-driven development only to runtimes with a native review
  transport (`internal/model/rdd.go`: claude-code, codex, opencode, pi);
  Hermes, like every other runtime, receives ODD only. hermes-odd's stance
  matches: native review is unavailable on Hermes, and its advisory reviews
  (4R, judgment-day) say "no receipt".
- The gentle-ai binary is used only through `gentle-ai review` (RDD). Never
  run `gentle-ai install` for Hermes or `gentle-ai sync --agent hermes`.

## Component matrix

| Component | Status | hermes-odd surface | Upstream sources (pinned) |
|---|---|---|---|
| `odd` | ported (T11: default test-first policy, ODD-only orchestrator behavior) | `hermes_odd/prompt.py` (section `hermes-odd-workflow`), `skills/odd-workflow`, `skills/odd-delegation`, `skills/odd-feature-tracking`, `upstream/odd-routing-hermes.canonical.md` | gentle-ai `internal/components/agentguidance/routing.go`, `internal/agents/capabilitymanifest/manifest.go`, `internal/assets/skills/_shared/odd-orchestrator-sections.md`, `internal/assets/hermes/orchestrator.md`, `internal/model/rdd.go`; gentle-shell `extensions/gentle-ai.ts`, `assets/orchestrator.md`, `assets/orchestrator-delegation.md`, `assets/orchestrator-skills.md`, `assets/orchestrator-memory.md`, `assets/agents/gentle-ai-worker.md` |
| `rdd` | partial (T7 ported, T8 blocked upstream; Hermes officially ODD-only upstream since `5ffb65fc`) | `/odd_review_mode` (`hermes_odd/commands/review_mode.py`, `hermes_odd/rdd.py`, probes in `hermes_odd/probes.py`), `skills/rdd-review`, `skills/rdd-review-lenses`; planned `odd_review` facade | gentle-ai `internal/assets/skills/rdd-defect-workflow/SKILL.md`, `internal/agents/capabilitymanifest/manifest.go`, `internal/cli/review_transport_capability.go`, `internal/model/rdd.go`; gentle-shell `skills/rdd-defect-workflow/SKILL.md`, `docs/review-integration.md`, `extensions/gentle-ai.ts`, `lib/review-integration-v2.ts`, `lib/native-review-cli.ts`, `assets/agents/review-{risk,resilience,readability,reliability}.md`, `assets/chains/4r-review.chain.md` |
| `review-contract` | pending (T8, blocked upstream) | CLI contract `gentle-ai.review-integration/v2` (capabilities v2.6); provider contract mirror 1.2.0; verified: `--agent hermes` fails with `gentle-ai.review-integration.failure/v2` `immutable_review_transport_unsupported` | gentle-ai `contracts/review-provider-contract/CONTRACT_SEMVER`, `contracts/review-integration/v2/schemas/{capabilities-v2.6,start-v4,status-v9,consent-v3,transition-binding}.schema.json`; gentle-shell `contracts/review-provider-contract-mirror/provider-contract.lock.json`, `.../v1.2.0/bundle/orchestration/pi.md`, `scripts/gentle-ai-installer.mjs` |
| `viewers` | ported | Viewers `/odd_agents`, `/odd_tasks`, `/odd_changes`; Health `/odd_status`, `/odd_doctor`, `/odd_commands` (all concept ports, no copied text) | gentle-shell `extensions/gentle-ai.ts`, `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts`, `docs/gentle-agents-activity.md`, `extensions/gentle-shell.ts`, `extensions/gentle-todo.ts`, `docs/gentle-shell.md`, `lib/shell-changes.ts`, `lib/shell-todo.ts`, `lib/review-sidebar-state.ts`, `lib/session-changes.ts`, `lib/shell-changes-view.ts`, `README.md` |
| `persona` | ported (T9a) | First-run setup: skill `skills/setup` (one `clarify` call), `/odd_setup` (`hermes_odd/commands/setup.py`), tool `odd_setup_apply` (`hermes_odd/setup_tool.py`), preferences and setup record (`hermes_odd/setup.py`), plugin `config_schema`, and one `<!-- hermes-odd:persona -->` block at the top of `SOUL.md` (`hermes_odd/soul_persona.py`, texts in `hermes_odd/personas.py`, own wording) | gentle-ai `internal/assets/hermes/persona-gentleman.md`, `internal/assets/hermes/persona-neutral.md`; gentle-shell `extensions/gentle-ai.ts` (`GENTLEMAN_PERSONA_PROMPT`, `NEUTRAL_PERSONA_PROMPT`) |
| `soul-cleanup` | ported (T9b) | `/odd_soul` (`hermes_odd/commands/soul.py`), tool `odd_soul_apply` (`hermes_odd/soul_tool.py`), cleanup rules and verification (`hermes_odd/soul_cleanup.py`, concept port), lazy skills `skills/engram-protocol` and `skills/codegraph` (own wording), one pointer line each in the prompt section | gentle-ai `internal/assets/engram/protocol.md`, `internal/components/communitytool/codegraph_guidance.go`, `internal/components/agentguidance/inject.go`, `internal/components/agentguidance/remote_authorization.go`, `internal/assets/generic/remote-authorization-contract.md`, `internal/components/agentguidance/orchestrator.go` |

| `portable-skills` | ported (T10) | Skills `skills/judgment-day` (blind dual review, advisory), `skills/work-unit-commits` (ODD commit closure) and `skills/chained-pr` (400-line review budget, delivery and chain strategies); behavior only, in hermes-odd's own words; the prompt section and `hermes-odd:odd-workflow` point to them by qualified name | gentle-ai `internal/assets/skills/judgment-day/SKILL.md` (+ `references/prompts-and-formats.md`), `internal/assets/skills/work-unit-commits/SKILL.md`, `internal/assets/skills/chained-pr/SKILL.md` (+ `references/chaining-details.md`), `internal/components/agentguidance/routing.go` |

Deliberately not ported (see `excluded` in the lock): SDD in every form; Pi
themes, banners, animations, TUI widgets and shortcuts; Pi runtime plumbing
(dev binary, bundled gentle-ai download, telemetry, Pi model profiles and
routing, Pi package installers, the in-process reviewer host); gentle-ai's
Hermes agent writers (`install`/`sync` into `SOUL.md`); upstream development
tooling.

## How to sync with upstream

1. **Fetch** both upstreams read-only (`git fetch --tags origin main`) into a
   local checkout outside this repository.
2. **Compare against the lock.** List the changes since each `pinned_commit`
   (`git log --oneline <pinned>..origin/main`, and new tags), and recompute the
   sha256 of every `sources` entry at the candidate commit
   (`git show <commit>:<path> | shasum -a 256`). A changed hash marks the
   component for review. `scripts/check_upstream_drift.py` automates this
   step (clone or fetch into `HERMES_ODD_UPSTREAM_CACHE`, verify each pin is
   an ancestor of the default branch, re-hash every source at the pin and at
   the head, list the commits per changed source and new upstream files to
   triage); the scheduled workflow `.github/workflows/upstream-drift.yml`
   runs it weekly and keeps one open `[upstream-drift]` issue.
3. **Triage every change** into a new entry of the triage log below, one line
   per commit: short sha, subject, decision (`ported`, `not portable: reason`,
   `pending: task`, or `not applicable`).
4. **Port or reject.** Port only what fits hermes-odd's scope; record every
   rejection with its reason.
5. **Update derived files** and their `derived-from` markers (new 40-character
   commit), and `THIRD_PARTY_NOTICES.md` (pinned commit and the list of
   derived files).
6. **Re-render the canonical ODD routing** for Hermes from gentle-ai
   (`RenderRouting(model.AgentHermes)`) into
   `upstream/odd-routing-hermes.canonical.md` with its new `source_commit` and
   `block_sha256`, and diff it against the previous render. The render is a
   throwaway program in a temporary directory outside both repositories:
   extract the pinned tree (`git archive <commit> | tar -x -C <tmp>`), add
   `<tmp>/cmd/render/main.go` that prints
   `agentguidance.RenderRouting(model.AgentHermes)` (Go only allows the
   `internal/` import from inside the module), run `go run ./cmd/render` in
   `<tmp>`, and use its exact stdout as the body after the header. Check the
   method by rendering the previous pin too: it must equal the vendored body.
7. **Bump the lock**: `supported_release`, `pinned_commit`, `commit_date`,
   binary `min_version`/`tested_version`, and every `sources` sha256.
8. **CHANGELOG**: add a line under `## [Unreleased]` naming the new upstream
   versions and what was ported.
9. Run the tests; `tests/test_upstream_lock.py` cross-checks the lock, the
   markers, `THIRD_PARTY_NOTICES.md`, the canonical render and this file.

## Triage log

### 2026-09-27: T11 re-pin (gentle-ai `a9e36e9`, gentle-shell `b756b4f`)

Both pins move to `main`: gentle-ai `f182ea2..a9e36e9` (134 commits: the 36
of the 2026-09-25 entry, whose `needs-port` items are ported below, plus the
98 listed at the end) and gentle-shell `4d702a4..b756b4f` (192 commits: the
81 of the 2026-09-25 entry plus the 111 listed at the end). No new release
tag on either side. After the bump `scripts/check_upstream_drift.py` reports
clean.

**Test-first policy (user decision: follow upstream exactly).**

| Upstream | Decision |
|---|---|
| gentle-ai `55e3abf1`/`f2cecbae`, gentle-shell `a76e6f2`/`80375c6`: one default applicable test-first policy | ported in own words: RED -> GREEN -> refactor when a relevant runnable deterministic test and a clear expected outcome exist; test or framework presence alone is not applicability; otherwise state the exception and run proportionate checks; forward the runner and the evidence or exception to workers; never invent RED/GREEN or a runner. Prompt section step 6, `hermes-odd:odd-workflow` section 6, the `hermes-odd:odd-delegation` mission template (`Test-first:` line, rules, return field), `hermes-odd:odd-feature-tracking` Checks, `hermes-odd:work-unit-commits` checklist, `hermes-odd:judgment-day` fix round |
| Installer strict TDD picker removed (`internal/tui/screens/strict_tdd.go`) | the hermes-odd setup TDD choice is retired: no `/odd_setup tdd`, no clarify question, no `tdd_mode` setting in `config_schema`, no `TDD mode:` prompt line. A `tdd_mode` value in an older setup record or in `config.yaml` still loads and is ignored (tested) |

**RDD gating (`5ffb65fc`).** `internal/model/rdd.go` (lines 12–27) makes
claude-code, codex, opencode and pi the only receipt-driven development
runtimes (`SupportsReceiptDrivenDevelopment`), tied by
`internal/components/agentguidance/rdd_gating_test.go` (line 81) to the
runtimes whose capability manifest advertises the review transport.
`RenderRouting` (`routing.go`) and `RenderOrchestratorWithSource`
(`orchestrator.go` line 162) give every other runtime, Hermes included, ODD
only: step 7 says verification covers a work-unit commit or PR slice, the
verification bullet is risk-proportionate, and the review-mode section, the
Provider Defect Handoff and every review wording are removed (a leak check
fails the render otherwise). The assumption challenge stays. Upstream now
officially excludes Hermes from RDD. hermes-odd's honest stance matches:
native review unavailable on Hermes, reported once per candidate with RDD on;
the 4R advisory ("advisory review — no receipt") and judgment-day ("advisory
judgment — no receipt") issue no receipt. Aligned: the prompt Review line and
step 7, `hermes-odd:odd-workflow` sections 1, 6 and 7, `hermes-odd:rdd-review`.
T8 stays blocked: `manifest.go` and `review_transport_capability.go` are
byte-identical to v3.7.0 (`reviewTransportExposureByAgent` and
`immutableReviewExecutorExposureByAgent`, lines 149–187, advertise only the
four runtimes; the Hermes feature claims, line 307, are skills, system prompt
and MCP).

**ODD-only Hermes orchestrator (`fb4b59a7`, `1ba7d888`).** gentle-ai now
renders `internal/assets/hermes/orchestrator.md` with the `(ODD only)` shared
sections of `internal/assets/skills/_shared/odd-orchestrator-sections.md`
and writes it into `SOUL.md`.

| Orchestrator behavior | Decision |
|---|---|
| Delegated Verification Gate (ODD only): passive readback, medium writer self-verification, high or unclear adds an independent verifier, small-model bias, parent spot check | ported: `hermes-odd:odd-delegation` section 3 (referenced by the verification trigger in `hermes-odd:odd-workflow`) |
| Native Checking Contract (ODD only): normalize before checks, one quick check, one scoped correction, "needs your decision" | ported: `hermes-odd:odd-workflow` section 6 |
| Sub-agent launch deduplication | ported: one launch per distinct task (`hermes-odd:odd-delegation`) |
| Sub-agent context protocol (parent passes memory, children save with `mem_save`) | ported: `hermes-odd:odd-delegation` section 1 |
| Coordinator role, work routing ladder, mandatory triggers, allowed edit surfaces, Key Learnings, language contract, safety | already ported (prompt section, `odd-*` skills) |
| "ODD Implementation Context" still says "configured TDD mode" | not ported: stale upstream wording; the test-first policy above wins |
| Lossless prompts "always use the plain chat fallback" on Hermes | not ported: hermes-odd uses `clarify` (verified), with the plain-chat fallback |
| "Toolsets, MCP servers, and skills are NOT automatically inherited" | not ported: verified wrong for current Hermes (see the T10 entry) |
| Skill paths from a `~/.hermes/skills/` scan, `hermes-ephemeral-delegation` pointer | not ported: hermes-odd passes qualified `skill_view` names; see the T10 skill decisions |
| Provider Defect Handoff | not applicable: removed from non-RDD renders; hermes-odd's gentle-ai calls are the read-only review probes and the mode switch |

**SOUL cleanup.** A current `gentle-ai install` selecting Hermes writes one
new top-level block: `<!-- gentle-ai:orchestrator -->`
(`OrchestratorSectionID`, `orchestrator.go` line 23), placed right before
`agent-routing` by `injectOrchestratorSection` (lines 371–385) and converted
from a v3.7.0 `sdd-orchestrator` block by
`migrateLegacyOrchestratorSection` (lines 390–407); `InjectRoutingWithOptions`
(`inject.go` lines 89–136) renders it for every runtime except Pi (line 115)
and still nests `remote-authorization` in `agent-routing` (line 109). `/odd_soul`
now removes `orchestrator` (hermes-odd supplies ODD); persona and
remote-authorization keep their handling. `strict-tdd-mode`: written by v3.7.0
(`internal/components/sdd/inject.go` line 538) when strict TDD was on, never
by a current install (`internal/cli/run.go` line 1105 calls
`InjectStrictTDDWithOptions` with `enabled=false`, which removes it); kept as
an unknown block.

**Every other changed indexed source.**

| Source | Class | Reason |
|---|---|---|
| gentle-ai `internal/components/agentguidance/routing.go` | ported | test-first policy and RDD gating above; canonical re-render |
| gentle-ai `internal/components/agentguidance/inject.go` | ported | orchestrator block (SOUL cleanup above); Codex worker assignments are not applicable |
| gentle-ai `internal/assets/skills/work-unit-commits/SKILL.md` | informational | only its SDD section was removed (`e219644b`); the T10 port never had it |
| gentle-shell `assets/orchestrator.md`, `assets/orchestrator-delegation.md` | ported | test-first policy (`a76e6f2`); SDD removal (`cc5fbd94`) needs nothing; the ODD phase signal (`50960b9`) is not applicable (Pi prompt widget) |
| gentle-shell `assets/orchestrator-memory.md`, `assets/orchestrator-skills.md` | informational | SDD sections removed (`cc5fbd94`); the ODD parts are unchanged |
| gentle-shell `extensions/gentle-ai.ts` | ported | the harness test-first bullet and step 6 (`a76e6f2`); the rest is Pi TUI (profiles, models panel, ODD phase, cards) and native review selectors (T8 reference) |
| gentle-shell `extensions/gentle-agents.ts`, `lib/agents-view.ts` | informational | Pi agents RPC, polling and cost formatting; `/odd_agents` is a concept port with no shared code |
| gentle-shell `extensions/gentle-shell.ts`, `README.md`, `docs/gentle-shell.md` | not-applicable | Pi TUI: visual customization, Vim mode, status bar, profiles, prompt history |
| gentle-shell `lib/native-review-cli.ts` | informational | committed-range selector fixes of the Pi native review CLI; a T8 reference |

New sources indexed: gentle-ai `internal/assets/skills/_shared/odd-orchestrator-sections.md`,
`internal/assets/hermes/orchestrator.md`, `internal/model/rdd.go` (`odd`, `rdd`),
`internal/components/agentguidance/orchestrator.go` (`soul-cleanup`);
gentle-shell `assets/agents/gentle-ai-worker.md` (`odd`). The 2026-09-25
candidates `strict_tdd.go`, `opencode_background.go`, `pi_cleanup.go`,
`reviewassets/*.go`, `lib/odd-phase.ts` and
`skills/issue-creation/references/delegated-workflow-actions.md` keep their
classes; the Hermes orchestrator asset moves from informational to ported.
New since then: gentle-shell `docs/prompt-history.md` (not-applicable: Pi
prompt history) and `lib/agents-message-delivery.ts` (not-applicable: Pi
cross-orchestrator messaging).

### 2026-09-25: T10 portable skills

Upstream skill files declare `license: Apache-2.0` in their frontmatter,
while both upstream repositories are MIT-licensed (their `LICENSE` files).
hermes-odd therefore copies no upstream skill text: every port below carries
over behavior only, in hermes-odd's own words, with `derived-from` markers,
lock `sources` entries and `THIRD_PARTY_NOTICES.md` lines under the MIT
notices. The gentle-shell copies of the same skills are not indexed.

| Upstream skill | Decision |
|---|---|
| `judgment-day` (gentle-ai `internal/assets/skills/judgment-day/`, gentle-shell `skills/judgment-day/`) | ported as `hermes-odd:judgment-day`: two blind read-only `delegate_task` judges in one call, the parent merges a frozen ledger (confirmed, suspect, contradiction, info, follow-up), one `clarify` before any fix, at most two fix and re-judge rounds, terminal `APPROVED` or `ESCALATED`; labeled "advisory judgment — no receipt"; finding format shared with `hermes-odd:rdd-review-lenses`; replaces the advisory 4R of `hermes-odd:rdd-review` for its target. Not ported: the native judge JSON result shape, the `review-refuter` rule and the artifact-store persistence (they belong to the native review) |
| `work-unit-commits` (gentle-ai `internal/assets/skills/work-unit-commits/`) | ported as `hermes-odd:work-unit-commits`: the single home of the ODD commit rules (work units, Conventional Commits, evidence, the advisory ~400-line per-task heuristic, the running line count), moved out of `hermes-odd:odd-workflow` section 7. Not ported: its SDD section |
| `chained-pr` (gentle-ai `internal/assets/skills/chained-pr/`) | ported as `hermes-odd:chained-pr`: 400-line review budget, the ODD delivery strategies (`ask-on-risk`, `auto-chain`, `single-pr`, `exception-ok`), `stacked-to-main` vs `feature-branch-chain` asked once over `clarify`, chain context for PR bodies, `gh` through `terminal`, push and PR creation left to the user. Not ported: the SDD gate |
| `hermes-ephemeral-delegation` (gentle-ai) | not ported: its tuning facts are outdated for current Hermes (it says children do not inherit toolsets, MCP servers or skills; hermes-odd verified that they inherit the parent's toolsets, MCP included unless `delegation.inherit_mcp_toolsets` is false), it forbids running tests inline where `hermes-odd:odd-delegation` allows a 1–3 file check, and it points to the SDD orchestrator; `hermes-odd:odd-delegation` covers the same ground |
| `branch-pr` | not ported: gentle-ai's own issue-first PR policy (issue links, labels, maintainer approval) for its repositories, not a Hermes workflow; `hermes-odd:chained-pr` covers PR slicing |
| `issue-creation` | not ported: gentle-ai's own issue triage and authority rules for its repositories |
| `comment-writer` | not ported: a tone guide for GitHub and chat comments, not an ODD or RDD behavior; the language boundary of `hermes-odd:odd-workflow` covers the language rule |
| `cognitive-doc-design` | not ported: documentation style guidance, outside the ODD/RDD scope |
| `skill-creator`, `skill-improver`, `skill-registry` | not ported: Hermes has its own skill tooling and index (`skills_list`, `skill_view`, `hermes skills`); there is no registry to refresh |
| `go-testing` | not ported: Go and Bubbletea testing patterns for gentle-ai's own code base |
| `rdd-defect-workflow` (gentle-ai and gentle-shell) | not ported: upstream issue and PR discipline for gentle-ai's RDD development; the RDD concepts hermes-odd needs are restated in `hermes-odd:rdd-review` (see the T7 entry) |
| `systemic-issue-triage` | not ported: gentle-ai maintainers' cross-issue triage process |
| `gentle-ai-bench` | not ported: gentle-ai's benchmark harness |
| gentle-shell `skills/gentle-ai` | not ported: the Pi harness skill (Pi subagents, OpenSpec artifacts, Pi TDD wiring); hermes-odd's prompt section and `odd-*` skills are its Hermes counterpart |
| gentle-ai repository-development skills (`skills/gentle-ai-collab-perfect`, `skills/issue-root-resolution`, `skills/rdd-advisory-transport`, top-level copies of `branch-pr`, `chained-pr`, `work-unit-commits`, ...) | not ported: development tooling of the gentle-ai repository itself, not installed for users |

### 2026-09-25: seen beyond the pins (T10 drift triage; supported since the T11 re-pin)

Produced with `scripts/check_upstream_drift.py` against gentle-ai `main` at
`6c7f162f` and gentle-shell `main` at `5456811`. Neither upstream has a new
release tag (latest `v3.7.0` for both; gentle-shell `package.json` still
3.7.0). Classes: `needs-port` (behavior hermes-odd should adopt before
re-pinning), `informational` (read, nothing to port beyond re-hashing),
`not-applicable` (outside hermes-odd's scope).

Indexed sources that changed: gentle-ai `routing.go` (`55e3abf1`,
`e219644b`; the canonical render needs a Go re-render), `inject.go`
(`e219644b`: Codex worker assignments and doc comments), `work-unit-commits`
(`e219644b`: SDD section removed); gentle-shell `assets/orchestrator.md`,
`orchestrator-delegation.md`, `orchestrator-memory.md`,
`orchestrator-skills.md`, `extensions/gentle-ai.ts`,
`extensions/gentle-agents.ts`, `extensions/gentle-shell.ts`,
`lib/native-review-cli.ts`, `README.md`, `docs/gentle-shell.md`. Unchanged:
the capability manifest (`manifest.go`), `review_transport_capability.go`,
the Hermes adapter (`internal/agents/hermes/`), the persona assets
(`internal/assets/hermes/persona-*.md`), the Engram `protocol.md` and
`codegraph_guidance.go`.

**T8 stays blocked.** `internal/agents/capabilitymanifest/manifest.go` is
byte-identical to the pin: `reviewTransportExposureByAgent` (lines 149–159)
and `immutableReviewExecutorExposureByAgent` (lines 177–187) start every
agent dormant and advertise only claude-code, opencode, codex and pi; the
Hermes entry (line 307) claims only skills, system prompt and MCP.

**Pins not bumped.** A bump requires, first: re-porting the default
applicable test-first policy (gentle-ai `55e3abf1`, gentle-shell `a76e6f2`)
into the prompt section step 6, `hermes-odd:odd-workflow` section 6 and the
setup TDD question (upstream removed its installer's strict TDD picker; the
setup question needs a product decision), and re-rendering
`RenderRouting(model.AgentHermes)` into
`upstream/odd-routing-hermes.canonical.md`. Every other changed source is
`informational` or `not-applicable`: re-hash it and move its markers.

New upstream files reported by the drift script (candidates):

| Upstream | File | Class | Reason |
|---|---|---|---|
| gentle-ai | `internal/assets/hermes/orchestrator.md`, `internal/assets/generic/orchestrator.md` | informational | the former `sdd-orchestrator.md` assets without SDD (`e219644b`); no Go code injects the Hermes one at the new head, and hermes-odd's own section replaces it |
| gentle-ai | `internal/assets/skills/_shared/odd-orchestrator-sections.md` | informational | renamed shared orchestrator sections (`e219644b`); covered by the `odd-*` skills |
| gentle-ai | `internal/components/agentguidance/strict_tdd.go` | informational | manages the legacy `strict-tdd-mode` section of system-prompt files (`SOUL.md` for Hermes, markdown-sections strategy); `internal/cli/run.go` calls it with `enabled=false`, so a newer gentle-ai run retires that section. hermes-odd writes no such block (its TDD line lives in its own prompt section) and `/odd_soul` keeps unknown blocks |
| gentle-ai | `internal/components/agentguidance/opencode_background.go`, `pi_cleanup.go` | not-applicable | OpenCode background agents; Pi prompt cleanup |
| gentle-ai | `internal/components/reviewassets/*.go` (`codegraph`, `contract`, `install`, `judgment`, `lens`, `ownership`, `render`) | informational | native review asset installer (judge contract and JSON result shape for runtimes with native review); a T8 reference, not needed by the advisory `hermes-odd:judgment-day` |
| gentle-shell | `lib/odd-phase.ts` | not-applicable | Pi prompt phase label |
| gentle-shell | `skills/issue-creation/references/delegated-workflow-actions.md` | not-applicable | `issue-creation` is not ported |

gentle-ai `f182ea2..6c7f162f` (36 commits):

| Commit | Date | Subject | Class | Reason |
|---|---|---|---|---|
| `6c7f162f` | 2026-09-25 | fix(pi): isolate CodeGraph manifest for custom agent directories (#4985) | not-applicable | Pi adapter and `sync`: CodeGraph manifest for custom Pi agent directories |
| `8b52c465` | 2026-09-25 | Merge pull request #4983 from Gentleman-Programming/feat/skill-friction-current | informational | merge of `8f3f6de3`, `07a3de03`, `7d27f219` |
| `7d27f219` | 2026-09-25 | style(skills): format contract assertions | not-applicable | upstream skill contract tests |
| `07a3de03` | 2026-09-25 | fix(skills): align PR policy with verified evidence | informational | `branch-pr` and repository-development skills; `branch-pr` is not ported (see the T10 skill decisions) |
| `8f3f6de3` | 2026-09-25 | fix(skills): clarify issue authority and attestations | informational | `issue-creation`; not ported (see the T10 skill decisions) |
| `eb79777b` | 2026-09-25 | fix(update): pin cross-major beta upgrade to checked revision (#4979) | not-applicable | gentle-ai self-update |
| `f2cecbae` | 2026-09-25 | Merge pull request #4978 from Gentleman-Programming/feat/default-applicable-tdd | needs-port | merge of `55e3abf1` |
| `bb578636` | 2026-09-25 | test(bench): follow installer without strict TDD picker | not-applicable | upstream benchmark |
| `84b9286a` | 2026-09-25 | test(odd): align runtime guidance assertions | not-applicable | upstream tests |
| `55e3abf1` | 2026-09-25 | feat(odd): default to applicable test-first development | needs-port | `routing.go`: ODD TDD becomes one default applicable test-first policy (RED/GREEN/REFACTOR when a runnable deterministic test and a clear expected outcome exist, else a stated exception) instead of a configured on/off mode; the installer's strict TDD picker (`internal/tui/screens/strict_tdd.go`) is removed. Affects the prompt section step 6, `hermes-odd:odd-workflow` section 6, the setup TDD question and the canonical render |
| `8d6f4560` | 2026-09-25 | fix(update): derive go-install module major from the target version (#4687, slice 2/2) (#4926) | not-applicable | gentle-ai self-update |
| `16e11590` | 2026-09-25 | fix(update): add version-aware Go module path helper (#4687, slice 1/2) (#4925) | not-applicable | gentle-ai self-update |
| `ece42b1e` | 2026-09-25 | Merge pull request #4971 from Gentleman-Programming/feat/review-assess-changed-line-signals | informational | merge of the review risk-signal commits (`0b459051`, `5825ea83`, `88871c1a`) |
| `728b7016` | 2026-09-25 | chore: integrate current main for risk signals PR | informational | merge of `main` into the risk-signal branch |
| `520ed86e` | 2026-09-25 | Merge pull request #4967 from Gentleman-Programming/feat/remove-sdd-odd-only-main | informational | merge of `e219644b` |
| `15a02e94` | 2026-09-25 | docs(odd): record fourth CI failure and XDG fix | not-applicable | upstream feature document |
| `3021ad4b` | 2026-09-25 | test(sync): honor XDG settings path in CI | not-applicable | upstream tests |
| `72ce8aa0` | 2026-09-25 | docs(odd): record OpenCode sync regression evidence | not-applicable | upstream feature document |
| `a92d4f9c` | 2026-09-25 | fix(sync): persist OpenCode model picker assignments safely | not-applicable | OpenCode model picker sync |
| `60d2d151` | 2026-09-25 | test(review): canonicalize macOS temp lock fixtures | not-applicable | upstream tests |
| `96ab7468` | 2026-09-25 | test(workflow): align CI fixtures with ODD install outputs | not-applicable | upstream tests |
| `86cfae1d` | 2026-09-25 | test(pi): isolate filesystem fixtures from inherited agent directory | not-applicable | upstream tests |
| `15025cf8` | 2026-09-25 | test(workflow): align driven and E2E coverage with ODD-only install | not-applicable | upstream tests |
| `0b459051` | 2026-09-25 | feat(review): classify dangerous sinks on added lines | informational | review risk classifier inside the binary (`gentle-ai review assess`); no hermes-odd surface while native review is unavailable (T8) |
| `1ad219bd` | 2026-09-25 | docs(odd): record retired workflow verification and commit | not-applicable | upstream feature document |
| `e219644b` | 2026-09-25 | feat(workflow)!: retire SDD and OpenSpec in favor of ODD | informational | retires SDD and OpenSpec upstream: `routing.go`, `inject.go` and the Hermes orchestrator asset lose their SDD text (`internal/assets/hermes/sdd-orchestrator.md` becomes `orchestrator.md`, and no Go code injects it at the new head); hermes-odd already ships no SDD, so nothing to port beyond re-hashing and the canonical re-render; `/odd_soul` keeps removing the old `sdd-orchestrator` block of existing `SOUL.md` files. `work-unit-commits` loses its SDD section, matching the T10 port |
| `a412f30c` | 2026-09-25 | docs(odd): track clean SDD retirement reapplication | not-applicable | upstream feature document |
| `88871c1a` | 2026-09-25 | fix(review): keep process scan on binary-attributed files | informational | review process-boundary scan inside the binary; no hermes-odd surface (T8) |
| `5825ea83` | 2026-09-25 | fix(review): scan process boundaries on added lines only | informational | review process-boundary scan inside the binary; no hermes-odd surface (T8) |
| `40b35ee2` | 2026-09-24 | fix(telemetry): render expired runtime series before evicting them | not-applicable | telemetry |
| `c7651af5` | 2026-09-24 | docs(telemetry): record the cardinality fix delivery and deploy | not-applicable | upstream feature document |
| `480f2e3b` | 2026-09-24 | fix(telemetry): evict idle runtime metric series after a TTL | not-applicable | telemetry |
| `0281553d` | 2026-09-24 | fix(telemetry): skip zero-delta series in runtime metrics | not-applicable | telemetry |
| `465452eb` | 2026-09-24 | Merge pull request #4963 from Gentleman-Programming/fix/4433-terminal-start-conflict-current | informational | merge of `c2ed12a5` |
| `8edb9d98` | 2026-09-24 | docs(odd): record issue 4433 verification evidence | not-applicable | upstream feature document |
| `c2ed12a5` | 2026-09-24 | fix(review): stop restarting escalated original targets | informational | review CLI restart behavior inside the binary; relevant only once the facade exists (T8) |

gentle-shell `4d702a4..5456811` (81 commits):

| Commit | Date | Subject | Class | Reason |
|---|---|---|---|---|
| `5456811` | 2026-09-25 | Merge pull request #1451 from Gentleman-Programming/docs/odd-phase-task-close | not-applicable | merge of an upstream feature document |
| `553cd77` | 2026-09-25 | docs(odd): close phase prompt work record | not-applicable | upstream feature document |
| `6338115` | 2026-09-25 | Merge pull request #1450 from Gentleman-Programming/fix/odd-phase-loader-registry | not-applicable | merge of `87993a9`, `58b5371` |
| `cd3f22c` | 2026-09-25 | docs(odd): record phase prompt work units | not-applicable | upstream feature document |
| `58b5371` | 2026-09-25 | fix(shell): hide routine ODD phase tool output | not-applicable | Pi prompt phase label (`gentle_odd_phase` tool output) |
| `87993a9` | 2026-09-25 | fix(shell): share ODD phases across extension loaders | not-applicable | Pi prompt phase label shared across extension loaders |
| `3cebcf2` | 2026-09-25 | fix(review): bound windows owner probes with a configurable timeout (#1449) | not-applicable | Pi review candidate view, Windows owner probes |
| `8423017` | 2026-09-25 | Merge pull request #1448 from Gentleman-Programming/fix/models-panel-fullscreen | not-applicable | merge of the `/gentle:models` panel fixes (Pi TUI) |
| `681c78f` | 2026-09-25 | fix(models): size /gentle:models lists to the terminal height | not-applicable | `/gentle:models` panel (Pi TUI) |
| `c79f65d` | 2026-09-25 | fix(overlay): repaint every cell after closing a gentle overlay (#1404) | not-applicable | overlay repaint (Pi TUI) |
| `a25633d` | 2026-09-25 | fix(models): open /gentle:models fullscreen like /gentle:profiles | not-applicable | `/gentle:models` panel (Pi TUI) |
| `a283cbe` | 2026-09-25 | fix(startup): show banner when launched through gentle-shell (#1445) | not-applicable | startup banner (Pi TUI) |
| `89b8de3` | 2026-09-25 | Merge pull request #1440 from Gentleman-Programming/feat/odd-input-phase-labels | not-applicable | merge of `50960b9` |
| `0dc3a81` | 2026-09-25 | chore(merge): integrate latest main for ODD phase labels | informational | merge of `main` into the phase-label branch |
| `e876cd1` | 2026-09-25 | docs(odd): record phase-label work-unit review evidence | not-applicable | upstream feature document |
| `50960b9` | 2026-09-25 | feat(shell): show explicit ODD phase in working prompt | not-applicable | ODD phase shown in the Pi working prompt (`gentle_odd_phase`, `lib/odd-phase.ts`, `assets/orchestrator-delegation.md` signaling rules); Hermes has no prompt phase widget |
| `42d9676` | 2026-09-25 | Merge pull request #1317 from carolitascl/feat/gentle-ai-card-elapsed | not-applicable | merge of the gentle-ai card duration commits (Pi renderer) |
| `b50b417` | 2026-09-25 | Merge pull request #1433 from Gentleman-Programming/feat/skill-friction-current | informational | merge of `555c12a`, `dd064b3`, `4014403` |
| `555c12a` | 2026-09-25 | fix(skills): align PR evidence and authorization | informational | `branch-pr`; not ported (see the T10 skill decisions) |
| `dd064b3` | 2026-09-25 | fix(skills): bind issue actions to explicit authority | informational | `issue-creation`; not ported (see the T10 skill decisions) |
| `4014403` | 2026-09-25 | fix(skills): clarify chained PR delivery boundaries | informational | `chained-pr`: verify the default branch before creating branches or PRs, and one gate per delivery strategy; restated in hermes-odd's own words in `hermes-odd:chained-pr` (T10). The gentle-shell copy is not indexed |
| `80375c6` | 2026-09-25 | Merge pull request #1428 from Gentleman-Programming/feat/default-applicable-tdd | needs-port | merge of `a76e6f2` |
| `a76e6f2` | 2026-09-25 | feat(odd): default to applicable test-first development | needs-port | default applicable test-first policy (same change as gentle-ai `55e3abf1`) in `assets/orchestrator.md`, `assets/orchestrator-delegation.md` and the Pi worker/verify agents |
| `5422444` | 2026-09-25 | Merge pull request #1426 from Gentleman-Programming/feat/fullscreen-scroll-tui-0871 | not-applicable | merge of the Pi 0.87.1 fullscreen scroll work |
| `54ab4fe` | 2026-09-25 | chore(merge): integrate main into fullscreen scroll candidate | informational | merge of `main` into the fullscreen scroll branch |
| `8c367be` | 2026-09-25 | docs(odd): record packed import work unit | not-applicable | upstream feature document |
| `42e36ad` | 2026-09-25 | fix(deps): verify packed Pi 0.87.1 imports | not-applicable | Pi package dependencies |
| `8035114` | 2026-09-25 | Merge pull request #1420: keep committed base selector through intended-untracked selection | informational | merge of the #1192 native review selector fixes |
| `2f12f0a` | 2026-09-25 | fix(review): append only the missing committed-range selector on submission | informational | Pi native review CLI selector (`lib/native-review-cli.ts`); a T8 reference only while the facade is blocked |
| `6a4dae2` | 2026-09-25 | Merge pull request #1421 from Gentleman-Programming/feat/customize-vim-mode | not-applicable | merge of the Vim mode settings (Pi TUI) |
| `fea663f` | 2026-09-25 | build(runtime): regenerate native review CLI module for #1192 | not-applicable | Pi runtime bundle |
| `36f3a8c` | 2026-09-25 | docs(odd): record #1192 select-intended-untracked end-to-end proof | not-applicable | upstream feature document |
| `7fa3fee` | 2026-09-25 | fix(review): keep committed selector on select-intended-untracked and harden provider tokens | informational | Pi native review CLI selector and provider tokens; a T8 reference only |
| `5bb6a90` | 2026-09-25 | docs(odd): record #1192 end-to-end RDD proof and verifier follow-ups | not-applicable | upstream feature document |
| `2af13fb` | 2026-09-25 | fix(review): carry committed selector and lineage through untracked selection | informational | Pi native review CLI selector and lineage; a T8 reference only |
| `4b46884` | 2026-09-25 | fix(review): keep committed base selector on intended-untracked submission | informational | Pi native review CLI selector; a T8 reference only |
| `9b55fd2` | 2026-09-25 | docs(visual-customization): record Vim modal proof | not-applicable | upstream feature document |
| `c7d9a70` | 2026-09-25 | feat(visual-customization): expose Vim mode in settings | not-applicable | visual customization (Pi TUI) |
| `fb7afbf` | 2026-09-25 | Merge pull request #1411 from Gentleman-Programming/feat/visual-customization-integration | not-applicable | merge of the visual customization chain (Pi TUI) |
| `d5cf0c0` | 2026-09-25 | docs(visual-customization): record Vim integration proof | not-applicable | upstream feature document |
| `0ea1a8e` | 2026-09-25 | chore(visual-customization): integrate current main | not-applicable | visual customization merge (Pi TUI) |
| `cf3a585` | 2026-09-25 | docs(visual-customization): record live TUI acceptance | not-applicable | upstream feature document |
| `b6936f7` | 2026-09-25 | fix(visual-customization): retain top header without rail | not-applicable | visual customization (Pi TUI) |
| `27b5827` | 2026-09-25 | docs(visual-customization): record Commands panel checks | not-applicable | upstream feature document |
| `e63af07` | 2026-09-25 | feat(visual-customization): present Commands-style panels | not-applicable | visual customization (Pi TUI) |
| `4b2d21d` | 2026-09-25 | Merge pull request #1415 from Gentleman-Programming/feat/vim-prompt-mode | not-applicable | merge of the Vim prompt mode (Pi TUI) |
| `985fcb9` | 2026-09-25 | fix(deps): correct Pi 0.87.1 upgrade test/doc evidence | not-applicable | Pi dependency upgrade evidence |
| `cc7e7d1` | 2026-09-25 | test(vim): keep CI fixtures portable across Pi versions | not-applicable | upstream tests |
| `af7cf7f` | 2026-09-25 | docs(visual-customization): keep mirror lag explicit | not-applicable | upstream feature document |
| `366f8f1` | 2026-09-24 | docs(visual-customization): record profile validation | not-applicable | upstream feature document |
| `9bfc4ec` | 2026-09-24 | feat(visual-customization): add validated named profiles | not-applicable | visual profiles (Pi TUI) |
| `a5cc9b9` | 2026-09-24 | build(deps): align Pi TUI and coding-agent to 0.87.1 | not-applicable | Pi package dependencies |
| `7d07404` | 2026-09-24 | docs(odd): record verified Vim work units and delivery scope | not-applicable | upstream feature document |
| `8e0e859` | 2026-09-24 | feat(shell): wire opt-in Vim prompt mode with docs and tests | not-applicable | Vim prompt mode (Pi TUI) |
| `442e7db` | 2026-09-24 | feat(vim): add gated modal editing engines and tests | not-applicable | Vim editing engines (Pi TUI) |
| `3e296af` | 2026-09-24 | docs(visual-customization): flag pending task mirror | not-applicable | upstream feature document |
| `08d8e8b` | 2026-09-24 | docs(visual-customization): record responsive layout proof | not-applicable | upstream feature document |
| `5d8dc39` | 2026-09-24 | feat(visual-customization): apply responsive layout controls | not-applicable | responsive layout (Pi TUI) |
| `f045787` | 2026-09-24 | docs(visual-customization): record integrated review | not-applicable | upstream feature document |
| `81a0e19` | 2026-09-24 | docs(odd): consolidate visual customization into one PR | not-applicable | upstream feature document |
| `5e6df95` | 2026-09-24 | feat(shell): integrate visual panel foundation and themes | not-applicable | visual panel and themes (Pi TUI) |
| `041beff` | 2026-09-24 | feat(shell): preview installed theme palettes without applying | not-applicable | theme previews (Pi TUI) |
| `dd27e35` | 2026-09-24 | fix(shell): satisfy visual panel type contracts | not-applicable | visual panel types (Pi TUI) |
| `af052f1` | 2026-09-24 | docs(odd): record reviewed visual child PRs | not-applicable | upstream feature document |
| `d7d4159` | 2026-09-24 | chore: align panel slice with foundation PR | not-applicable | visual customization chain upkeep (Pi TUI) |
| `6a6d136` | 2026-09-24 | feat(shell): add visual customization panel controls | not-applicable | visual panel controls (Pi TUI) |
| `76e5274` | 2026-09-24 | chore: align policy slice with visual tracker | not-applicable | visual customization chain upkeep (Pi TUI) |
| `a3ebe46` | 2026-09-24 | docs(odd): omit local worktree path from tracker | not-applicable | upstream feature document |
| `ff9f8be` | 2026-09-24 | docs(odd): track visual customization integration chain | not-applicable | upstream feature document |
| `6bf3a4a` | 2026-09-24 | feat(shell): persist visual customization preferences | not-applicable | visual customization preferences (Pi TUI) |
| `a923264` | 2026-09-24 | Merge pull request #1408 from Gentleman-Programming/feat/remove-sdd-odd-only | informational | merge of `cc5fbd9` |
| `2201956` | 2026-09-24 | chore: integrate Shell main into ODD retirement | informational | merge of `main` into `cc5fbd9` |
| `ac09a7f` | 2026-09-24 | test(shell): verify raw scroll frame parity | not-applicable | upstream tests |
| `8efb840` | 2026-09-24 | test(shell): characterize fullscreen sidebar scroll costs | not-applicable | upstream tests |
| `0822e74` | 2026-09-24 | test(shell): record isolated packed installer proof | not-applicable | upstream feature document |
| `7c95eb4` | 2026-09-24 | docs(odd): record Shell verification and review blocker | not-applicable | upstream feature document |
| `cc5fbd9` | 2026-09-24 | refactor(shell): remove SDD surfaces and retain user safety | informational | removes SDD from Pi (`assets/orchestrator*.md`, `extensions/gentle-ai.ts`, `extensions/gentle-agents.ts`, docs); hermes-odd already ships no SDD, and the retained ODD rules (English artifacts, the parent passes skill paths, memory on demand) are already in the `odd-*` skills: re-hash only |
| `8faeb54` | 2026-09-23 | fix: guard replayed RUNNING start stamping in gentle-ai call cards | not-applicable | gentle-ai call cards (Pi renderer) |
| `878212c` | 2026-09-22 | fix(renderer): persist card durations in session entries for honest replays | not-applicable | gentle-ai call card durations (Pi renderer) |
| `969a870` | 2026-09-22 | fix(renderer): keep replayed card durations honest and one timer per row | not-applicable | gentle-ai call card durations (Pi renderer) |
| `b93864d` | 2026-09-22 | feat(renderer): show live call duration on gentle-ai cards | not-applicable | gentle-ai call card durations (Pi renderer) |

### 2026-09-25: T9b SOUL cleanup and lazy guidance skills

gentle-ai's Hermes writer puts these top-level blocks into `SOUL.md` (verified
on a real install: 88,482 chars, cut by Hermes at 128k and 200k context):
`codegraph-guidance`, `persona`, `engram-protocol`, `sdd-orchestrator` (with
a nested `sdd-session-preflight`) and `agent-routing` (with a nested
`remote-authorization`, injected by `InjectRoutingWithOptions` in
`internal/components/agentguidance/inject.go`).

| Area | Decision |
|---|---|
| Engram protocol block (`internal/assets/engram/protocol.md`, full variant) | ported as a lazy skill: `hermes-odd:engram-protocol`, own condensed wording bound to `mcp__engram__*` (when and what to save, topic keys, search before asking, session summary, after compaction); removed from `SOUL.md` by `/odd_soul`; a prompt-section line points to it while `engram_protocol` is `auto`. The slim, passive-capture and compact variants are not ported (they target runtimes with their own hooks) |
| CodeGraph guidance block (`CodeGraphGuidanceMarkdown` in `internal/components/communitytool/codegraph_guidance.go`) | ported as a lazy skill: `hermes-odd:codegraph` (worktree placement, required order, read-only surface); `gentle-ai codegraph init --cwd <root>` becomes the upstream CLI `codegraph init <root>` (codegraph 1.2.0); a prompt-section line points to it while `codegraph_guidance` is `auto` and CodeGraph is on `PATH` or configured as an MCP server |
| `remote-authorization` block (`remote_authorization.go`, `internal/assets/generic/remote-authorization-contract.md`) | kept in SOUL: lifted byte-identical, with its `gentle-ai:` markers, out of `agent-routing` into its place (a general safety rule the user keeps) |
| `sdd-orchestrator`, `sdd-session-preflight`, `agent-routing` blocks | removed by `/odd_soul apply confirm` (backup, atomic write, verification); hermes-odd ships no SDD and supplies ODD routing through its own section |
| gentle-ai `persona` block | kept; `/odd_soul plan persona` removes it only on request and only while a hermes-odd persona block exists |
| Re-adding by gentle-ai | not portable: `gentle-ai install` selecting Hermes or `gentle-ai sync --agent hermes` writes the blocks again; `/odd_soul` warns about it (binary-only rule) |

### 2026-09-25: T9a first-run setup (gentle-ai installer persona step)

The gentle-ai installer (`internal/tui/screens/*.go`) is a terminal wizard that
selects what gentle-ai writes into each agent's configuration. hermes-odd is
one Hermes plugin with a fixed surface, so only the steps that record a user
preference Hermes can apply are ported, over chat (CLI/TUI and Telegram).

| Area | Decision |
|---|---|
| Installer persona step (`internal/tui/screens/persona.go`: gentleman / neutral / custom) and the gentle-pi persona view (`GENTLEMAN_PERSONA_PROMPT`, `NEUTRAL_PERSONA_PROMPT` in `extensions/gentle-ai.ts`) | ported as the first-run setup: `hermes-odd:setup` asks once over `clarify` (Mentor rioplatense (voseo), Mentor neutral, My own text, None; no default and no recommended option), `/odd_setup persona <id>` previews and `confirm` writes; the persona is one `hermes-odd:persona` block at the top of `SOUL.md`, with a backup |
| Persona texts (`internal/assets/hermes/persona-gentleman.md`, `persona-neutral.md`) | ported in hermes-odd's own words (`hermes_odd/personas.py`): the behavior rules only. Not ported: the `## Identity` product identity, branding, author biography, tool preferences, and the Hermes skill-loading and Engram memory sections (Hermes loads plugin skills itself; the Engram protocol became the lazy skill `hermes-odd:engram-protocol` in T9b) |
| Installer strict TDD step (`internal/tui/screens/strict_tdd.go`) | ported as the setup's TDD question (off / strict / per project); it reached ODD as one `TDD mode:` line in the prompt section. Retired in T11 with the upstream picker (see the 2026-09-27 entry) |
| Engram setup and SOUL cleanup of gentle-ai blocks | preferences stored in T9a (`engram_protocol`, `soul_cleanup`); behavior shipped in T9b (see the T9b entry) |
| Installer presets (`internal/tui/screens/preset.go`: Memory Only, Dev Stack, Dev Stack + Polish, Custom) | not portable: they choose which gentle-ai components (SDD, skills, themes, logo, GGA) get installed into agent configurations; hermes-odd installs as one plugin and ships no SDD, themes or logo |
| Component selection and dependency tree (`skill_picker.go`, `community_tools.go`, `dependency_tree.go`, `opencode_plugins.go`) | not applicable: the plugin surface is fixed; Engram and CodeGraph are separate MCP servers the user installs in Hermes |
| Model pickers and model configuration (`model_picker.go`, `claude_model_picker.go`, `codex_model_picker.go`, `kiro_model_picker.go`, `model_config.go`, `profiles.go`) | not applicable: Hermes owns model selection (`hermes model`, `config.yaml`); hermes-odd never routes models |
| Review mode step (`review_mode.go`, `install_review_mode.go`) | already ported: `/odd_review_mode` (T7) |
| Backups screen (`backups.go`) | partly: every `SOUL.md` write keeps a `SOUL.md.hermes-odd-bak-<UTC timestamp>` copy (last 5); `/odd_soul restore` lists and restores them (T9b) |
| SDD mode, agent builder, upgrade/sync/uninstall screens | not portable: SDD, or gentle-ai's own lifecycle for agent writers hermes-odd replaces |

### 2026-09-25: T7 RDD on Hermes (gentle-ai 3.7.0 binary verified)

Verified against the installed gentle-ai 3.7.0 binary. `gentle-ai review
status --cwd <repo> --contract gentle-ai.review-integration/v2 --agent hermes
--next-transition` fails in preflight (nothing started) with schema
`gentle-ai.review-integration.failure/v2`, code
`immutable_review_transport_unsupported`, `next_action: stop`. The eligible
set is compiled into gentle-ai (`internal/agents/capabilitymanifest/manifest.go`,
`ContractReviewTransportV1` / `ContractImmutableReviewExecutorV1`: claude-code,
opencode, codex, pi) and narrowed per environment by
`internal/cli/review_transport_capability.go` (pi only with its host relay
handshake, opencode only on a V1 runtime); the refusal lists the runtimes
eligible in the probing environment. `gentle-ai review mode
status|enable|disable [--cwd] [--scope global|clone] [--json]` works for any
caller.

| Area | Decision |
|---|---|
| Review mode switch (gentle-pi review-mode view over `gentle-ai review mode`) | ported: `/odd_review_mode [status\|enable\|disable] [global\|clone] [project]`, concept port; `status` read-only, `enable`/`disable` need an explicit scope and are user-typed writes of gentle-ai's own switch |
| Native review facade (`gentle_review*` over `gentle-ai review start/status/...`) | blocked upstream: runtime eligibility; Hermes is refused with `immutable_review_transport_unsupported`. hermes-odd never passes another runtime's identity (`--agent pi` or any other). Availability is probed read-only and shown by `/odd_review_mode`, `/odd_status` and `/odd_doctor`; T8 waits on upstream |
| RDD protocol for a runtime without native review | ported as `skills/rdd-review`: candidate = one work-unit commit or PR slice; with RDD on, report "native review unavailable on Hermes" once per candidate, record it in the feature document and continue under ordinary repository policy; no fake receipts |
| 4R lenses (gentle-shell `assets/agents/review-{risk,resilience,readability,reliability}.md`, `assets/chains/4r-review.chain.md`) | ported as a receipt-less skill: `skills/rdd-review-lenses`, condensed charters run as read-only `delegate_task` children over `git show <sha>`, labeled "advisory review — no receipt"; the Pi ledger/JSON envelope, `gentle_review_scope` tool and controller authority are not portable (they need the native facade) |
| `rdd-defect-workflow` skill (gentle-ai and gentle-shell) | not derived: its frontmatter declares Apache-2.0 and it governs upstream issue/PR discipline; the RDD concepts are restated in hermes-odd's own words |
| RDD sidebar lifecycle labels (`2ac9c68`, `8becfd8`) | not applicable until native review exists on Hermes |

### 2026-09-24: baseline gentle-ai v3.7.0 and gentle-shell v3.7.0

Initial port at gentle-ai `f182ea2` (v3.7.0) and gentle-shell `4d702a4`
(v3.7.0+16, npm `gentle-pi` 3.7.0).

| Area | Decision |
|---|---|
| ODD protocol, delegation triggers, resume order, feature tracking (gentle-ai `routing.go`; gentle-shell `assets/orchestrator*.md`, `extensions/gentle-ai.ts`) | ported: compact section + `odd-*` skills, bound to `delegate_task`, `clarify`, `mcp__engram__*` |
| Canonical `RenderRouting(model.AgentHermes)` | ported: vendored verbatim in `upstream/odd-routing-hermes.canonical.md` for drift comparison |
| RDD review lifecycle (`gentle_review*` facade, `rdd-defect-workflow`, review CLI contract v2, provider contract mirror 1.2.0) | T7 ported (review mode, honest protocol, advisory 4R); facade blocked upstream (T8), see the 2026-09-25 entry |
| Pi agents view (gentle-shell `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts` `TaskRecord` model) | ported: `/odd_agents` (T3), concept port with no copied text, fed by Hermes `subagent_start`/`post_tool_call`/`subagent_stop` hooks |
| Pi agents view: stopping a running subagent | not portable: Hermes offers no safe plugin path from a command (`ctx.subagent_lifecycle.cancel` only accepts handles minted by its own `launch`; `tools.delegate_tool.interrupt_subagent` is internal, unscoped and in-process); users ask the agent to run `delegate_task` `action=stop` |
| Pi todo card + ODD feature document view (gentle-shell `extensions/gentle-todo.ts`, `lib/shell-todo.ts`) | ported: `/odd_tasks` (T4) as a plain-text viewer, concept port with no copied text; it reads `odd/tasks/*.md` of known projects (roots recorded from the prompt section's session `cwd`) and of the command process's own directory |
| Pi interactive `todo` tool | not portable: Hermes' native `todo` tool is used instead (the `odd-feature-tracking` skill maps feature tasks onto it) |
| Pi Gentle Changes capture and list (gentle-shell `lib/session-changes.ts`, `lib/shell-changes.ts`, `lib/shell-changes-view.ts`, Gentle Changes in `README.md` / `docs/gentle-shell.md`) | ported as text: `/odd_changes` (T5), concept port with no copied text; successful `write_file`/`patch` calls from Hermes' `post_tool_call` (main agent and subagents), per-file line counts computed at capture time, attribution, 24 h / 7 day windows, per-file timeline and `git diff --numstat`; like upstream, shell edits are not captured. No file content or diff is stored, so `write_file` removed lines are unknown |
| Pi Gentle Changes two-pane diff viewer (`lib/shell-changes-view.ts`: accordion, captured diff pane, `alt+g`, `o` to open in the editor) and before/after snapshots | not portable: Pi TUI overlay; hermes-odd commands answer plain text on every gateway and never store file content |
| Pi `gentle:status` (`extensions/gentle-ai.ts`) | ported: `/odd_status` (T6), concept port with no copied text: version, prompt section size, skills, subagents, changes, ODD features, gentle-ai binary against the lock minimum, cached RDD mode, supported upstreams |
| Pi `gentle:doctor` (`extensions/gentle-ai.ts`) | ported: `/odd_doctor` (T6), concept port with no copied text: pass/warn/fail checks with remedies for the gentle-ai binaries on `PATH`, RDD mode (`gentle-ai review mode status --json`), `SOUL.md` size, managed blocks and Hermes truncation, the plugin surface and `ctx.state`, the upstream lock and Hermes |
| Pi doctor/status checks for package assets, OpenSpec config, skill registry, model routing and the dev binary | not portable: Pi package and runtime plumbing (OpenSpec is SDD) |
| Pi views: review mode, persona | review mode ported: `/odd_review_mode` (T7); persona ported as the first-run setup (T9a, see the 2026-09-25 T9a entry; `/odd_commands` ported) |
| gentle-ai `internal/assets/skills/hermes-ephemeral-delegation` | not ported (T10): see the T10 skill decisions |
| gentle-ai `internal/assets/hermes/persona-*.md` | ported in own words as the setup personas (T9a, see the 2026-09-25 T9a entry) |
| SDD assets, agents, chains, skills, commands, preflight | not portable: hermes-odd ships no SDD |
| Themes, banners, animations, TUI widgets, shortcuts, double-esc cancel | not portable: Pi terminal UI |
| Dev binary, bundled gentle-ai download, telemetry, Pi model profiles/routing, Pi package installers | not portable: Pi runtime plumbing |
| gentle-ai `install`/`sync` agent writers for Hermes | not portable: they write SDD-heavy `SOUL.md` that Hermes truncates |

### 2026-09-24: gentle-shell v3.7.0..4d702a4 (unreleased, 16 commits)

Included in the pin; decisions below record what hermes-odd takes from each.

| Commit | Subject | Decision |
|---|---|---|
| `2ac9c68` | feat(sidebar): add RDD status contract and renderer | partly ported (T6): `/odd_status` and `/odd_doctor` show the RDD mode in gentle-ai's own wording; the lineage labels (`Reviewing`, `Awaiting consent`, ...) are not applicable until native review exists on Hermes (T8, blocked upstream); the sidebar widget is not portable (Pi TUI) |
| `8becfd8` | fix(sidebar): distinguish pending reviews and accept replayed starts | not applicable until native review exists on Hermes (T8, blocked upstream): pending vs replayed START semantics belong to the review facade; nothing to port for the review mode shown in T6 |
| `b019517` | feat(agents): require user consent before cross-orchestrator communication (#1364) | not portable: gates Pi `orchestrator_send_message` between Pi sessions; hermes-odd adds no inter-session messaging tool |
| `4210e56` | fix(agents): sanitize consent prompt, derive concrete reason, and handle prompt session change (#1364) | not portable: same Pi messaging consent as `b019517` |
| `46abadb` | docs(odd): record Gentle Shell v3.7.0 publication | not applicable: upstream feature document |
| `be2d7b1` | Merge pull request #1319 (feat/rdd-status-sidebar-01-contract-renderer) | as `2ac9c68`/`8becfd8`: mode wording ported in T6, lineage labels pending: T8 |
| `fdc46b4` | fix(tests): run all pnpm test stages independently of stage-1 failures (#1285) | not applicable: upstream test runner |
| `e12ecb9` | test(tests): cover the run-test-suite CLI branch exit contract (#1285) | not applicable: upstream test runner |
| `1a33f21` | test(tests): use double quotes in CLI stage fixtures for cmd.exe compatibility (#1285) | not applicable: upstream test runner |
| `7faf0d2` | fix(tests): harden run-test-suite CLI guard, error surfacing, and exit contract (#1285) | not applicable: upstream test runner |
| `0031c09` | fix(launcher): avoid duplicate package asset registration | not portable: Pi launcher package registration |
| `be00412` | docs(odd): record launcher deduplication evidence | not applicable: upstream feature document |
| `41508d1` | Merge pull request #1381 (fix/deduplicate-shell-assets) | not portable: merge of `0031c09` |
| `7f78c36` | Merge pull request #1380 (fix/test-suite-stages-v2) | not applicable: merge of the #1285 test-runner commits |
| `5e49b35` | fix(agents): harden cross-orchestrator consent boundary | not portable: same Pi messaging consent as `b019517` |
| `4d702a4` | Merge pull request #1372 (feat/1364-cross-orchestrator-consent) | not portable: merge of the #1364 consent commits |
