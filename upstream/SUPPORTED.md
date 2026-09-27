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
| `rdd` | partial (T7 ported, T8 blocked upstream; Hermes officially ODD-only upstream since `5ffb65fc`) | `/odd-review-mode` (`hermes_odd/commands/review_mode.py`, `hermes_odd/rdd.py`, probes in `hermes_odd/probes.py`), `skills/rdd-review`, `skills/rdd-review-lenses`; planned `odd_review` facade | gentle-ai `internal/assets/skills/rdd-defect-workflow/SKILL.md`, `internal/agents/capabilitymanifest/manifest.go`, `internal/cli/review_transport_capability.go`, `internal/model/rdd.go`; gentle-shell `skills/rdd-defect-workflow/SKILL.md`, `docs/review-integration.md`, `extensions/gentle-ai.ts`, `lib/review-integration-v2.ts`, `lib/native-review-cli.ts`, `assets/agents/review-{risk,resilience,readability,reliability}.md`, `assets/chains/4r-review.chain.md` |
| `review-contract` | pending (T8, blocked upstream) | CLI contract `gentle-ai.review-integration/v2` (capabilities v2.6); provider contract mirror 1.2.0; verified: `--agent hermes` fails with `gentle-ai.review-integration.failure/v2` `immutable_review_transport_unsupported` | gentle-ai `contracts/review-provider-contract/CONTRACT_SEMVER`, `contracts/review-integration/v2/schemas/{capabilities-v2.6,start-v4,status-v9,consent-v3,transition-binding}.schema.json`; gentle-shell `contracts/review-provider-contract-mirror/provider-contract.lock.json`, `.../v1.2.0/bundle/orchestration/pi.md`, `scripts/gentle-ai-installer.mjs` |
| `viewers` | ported | Viewers `/odd-agents`, `/odd-tasks`, `/odd-changes`; Health `/odd-status`, `/odd-doctor`, `/odd-commands` (all concept ports, no copied text) | gentle-shell `extensions/gentle-ai.ts`, `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts`, `docs/gentle-agents-activity.md`, `extensions/gentle-shell.ts`, `extensions/gentle-todo.ts`, `docs/gentle-shell.md`, `lib/shell-changes.ts`, `lib/shell-todo.ts`, `lib/review-sidebar-state.ts`, `lib/session-changes.ts`, `lib/shell-changes-view.ts`, `README.md` |
| `persona` | ported (T9a) | First-run setup: skill `skills/setup` (one `clarify` call), `/odd-setup` (`hermes_odd/commands/setup.py`), tool `odd_setup_apply` (`hermes_odd/setup_tool.py`), preferences and setup record (`hermes_odd/setup.py`), plugin `config_schema`, and one `<!-- hermes-odd:persona -->` block at the top of `SOUL.md` (`hermes_odd/soul_persona.py`, texts in `hermes_odd/personas.py`, own wording) | gentle-ai `internal/assets/hermes/persona-gentleman.md`, `internal/assets/hermes/persona-neutral.md`; gentle-shell `extensions/gentle-ai.ts` (`GENTLEMAN_PERSONA_PROMPT`, `NEUTRAL_PERSONA_PROMPT`) |
| `soul-cleanup` | ported (T9b) | `/odd-soul` (`hermes_odd/commands/soul.py`), tool `odd_soul_apply` (`hermes_odd/soul_tool.py`), cleanup rules and verification (`hermes_odd/soul_cleanup.py`, concept port), lazy skills `skills/engram-protocol` and `skills/codegraph` (own wording), one pointer line each in the prompt section | gentle-ai `internal/assets/engram/protocol.md`, `internal/components/communitytool/codegraph_guidance.go`, `internal/components/agentguidance/inject.go`, `internal/components/agentguidance/remote_authorization.go`, `internal/assets/generic/remote-authorization-contract.md`, `internal/components/agentguidance/orchestrator.go` |

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
| Installer strict TDD picker removed (`internal/tui/screens/strict_tdd.go`) | the hermes-odd setup TDD choice is retired: no `/odd-setup tdd`, no clarify question, no `tdd_mode` setting in `config_schema`, no `TDD mode:` prompt line. A `tdd_mode` value in an older setup record or in `config.yaml` still loads and is ignored (tested) |

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
and still nests `remote-authorization` in `agent-routing` (line 109). `/odd-soul`
now removes `orchestrator` (hermes-odd supplies ODD); persona and
remote-authorization keep their handling. `strict-tdd-mode`: written by v3.7.0
(`internal/components/sdd/inject.go` line 538) when strict TDD was on, never
by a current install (`internal/cli/run.go` line 1105 calls
`InjectStrictTDDWithOptions` with `enabled=false`, which removes it);
`/odd-soul` removes it too, since it contradicts the test-first policy
(follow-up to the T11 review).

**Every other changed indexed source.**

| Source | Class | Reason |
|---|---|---|
| gentle-ai `internal/components/agentguidance/routing.go` | ported | test-first policy and RDD gating above; canonical re-render |
| gentle-ai `internal/components/agentguidance/inject.go` | ported | orchestrator block (SOUL cleanup above); Codex worker assignments are not applicable |
| gentle-ai `internal/assets/skills/work-unit-commits/SKILL.md` | informational | only its SDD section was removed (`e219644b`); the T10 port never had it |
| gentle-shell `assets/orchestrator.md`, `assets/orchestrator-delegation.md` | ported | test-first policy (`a76e6f2`); SDD removal (`cc5fbd94`) needs nothing; the ODD phase signal (`50960b9`) is not applicable (Pi prompt widget) |
| gentle-shell `assets/orchestrator-memory.md`, `assets/orchestrator-skills.md` | informational | SDD sections removed (`cc5fbd94`); the ODD parts are unchanged |
| gentle-shell `extensions/gentle-ai.ts` | ported | the harness test-first bullet and step 6 (`a76e6f2`); the rest is Pi TUI (profiles, models panel, ODD phase, cards) and native review selectors (T8 reference) |
| gentle-shell `extensions/gentle-agents.ts`, `lib/agents-view.ts` | informational | Pi agents RPC, polling and cost formatting; `/odd-agents` is a concept port with no shared code |
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

gentle-ai `6c7f162f..a9e36e9b` (98 commits):

| Commit | Date | Subject | Class | Reason |
|---|---|---|---|---|
| `a9e36e9b` | 2026-09-27 | Merge pull request #5027 from Gentleman-Programming/fix/5026-codex-mcp-multiline | not-applicable | Codex MCP TOML handling |
| `def54b8d` | 2026-09-27 | fix(filemerge): ignore Codex MCP headers inside TOML multiline strings | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `eb462d2a` | 2026-09-27 | Merge pull request #5024 from Gentleman-Programming/fix/5022-filemerge-edge-cases | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `109351c0` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/5022-filemerge-edge-cases | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `a23ee94e` | 2026-09-26 | fix(filemerge): skip chmod when the forced mode already matches | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `e0744c8c` | 2026-09-26 | Merge pull request #5016 from Gentleman-Programming/fix/opencode-settings-writer-consistency | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `bb6df49e` | 2026-09-26 | fix(filemerge): ignore TOML headers in multiline strings and report mode-only changes | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `b79dca8c` | 2026-09-26 | docs(odd): record bot review fixes | not-applicable | upstream feature document |
| `e9926159` | 2026-09-26 | fix(opencode): keep new settings refusals off other agents | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `464fba4d` | 2026-09-26 | Merge pull request #5019 from Gentleman-Programming/fix/codex-toml-multiline | not-applicable | Codex MCP TOML handling |
| `21116ab5` | 2026-09-26 | fix(engram): reuse the TOML scanner for multiline string detection | not-applicable | Codex MCP TOML handling |
| `da3bcc8a` | 2026-09-26 | fix(engram): ignore MCP headers inside TOML multiline strings | not-applicable | Codex MCP TOML handling |
| `a596d7b3` | 2026-09-26 | Merge pull request #4914 from danielgap/fix/4882-telemetry-increment-syncs | not-applicable | telemetry |
| `091c25ad` | 2026-09-26 | docs(odd): record workspace settings regression fix | not-applicable | upstream feature document |
| `52863e0c` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/opencode-settings-writer-consistency | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `3268e4ad` | 2026-09-26 | fix(opencode): keep workspace installs on the loaded settings file | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `533c3872` | 2026-09-26 | Merge pull request #5014 from Gentleman-Programming/fix/preserve-file-mode | not-applicable | merge of the file-mode fixes (`6c729f36`, `a3c139a6`) |
| `44be4761` | 2026-09-26 | Merge pull request #5017 from Gentleman-Programming/fix/install-sync-convergence | not-applicable | merge of `ea0b6986` |
| `64173bb2` | 2026-09-26 | Merge pull request #4760 from ardelperal/feat/1884-doctor-state-manifest | not-applicable | merge of the managed-assets manifest (`0da1ab73`) |
| `ed90f1e2` | 2026-09-26 | Merge pull request #5012 from Gentleman-Programming/fix/hermetic-pi-tests-brew | not-applicable | Pi adapter and install tests, Homebrew |
| `a3c139a6` | 2026-09-26 | fix(filemerge): never widen forced zero modes and repair launcher exec bits | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `ea0b6986` | 2026-09-26 | fix(sync): make install and sync converge on the same files | not-applicable | install/sync convergence (Codex TOML ordering, OpenCode) |
| `4e66ab0a` | 2026-09-26 | test(opencode): isolate config tests from OPENCODE_CONFIG_DIR | not-applicable | upstream tests |
| `bd196fde` | 2026-09-26 | docs(odd): record settings writer review corrections | not-applicable | upstream feature document |
| `e03e405d` | 2026-09-26 | fix(opencode): scope settings refusals to OpenCode and port new tests | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `2564eaab` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/preserve-file-mode | not-applicable | merge of `main` into the file-mode branch |
| `6c729f36` | 2026-09-26 | fix(filemerge): stop rewrites from widening existing file permissions | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `7585680f` | 2026-09-26 | fix(opencode): keep settings comments and refuse theme symlinks | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `90bbcd36` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/hermetic-e-ff | not-applicable | Pi adapter and install tests, Homebrew |
| `f0b4215d` | 2026-09-26 | test(pi): isolate the Pi adapter tests from PI_CODING_AGENT_DIR | not-applicable | upstream tests |
| `fc546c30` | 2026-09-26 | test(cli): isolate brew env assertion and copy the command environment | not-applicable | upstream tests |
| `a67fd182` | 2026-09-26 | fix(install): keep Pi tests hermetic and brew free of auto-update | not-applicable | Pi adapter and install tests, Homebrew |
| `dee8edd2` | 2026-09-26 | Merge pull request #4899 from danielgap/fix/2995-review-store-exit | informational | merge of the #2995 review store commits (T8 reference) |
| `3603d96c` | 2026-09-26 | fix(opencode): route component settings through selected config | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `c9d6b0f7` | 2026-09-26 | Merge pull request #4965 from ardelperal/fix/4689-unix-installer-module-major | not-applicable | merge of the installer module-path fixes (`c2dc7129`) |
| `171b36f2` | 2026-09-26 | Merge pull request #3731 from ardelperal/fix/3049-reviewer-plugin-path-skew | not-applicable | merge of the OpenCode reviewer plugin path fixes (#3049) |
| `6ee5df7e` | 2026-09-26 | Merge pull request #5008 from Gentleman-Programming/fix/uninstall-opencode-agents | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `5dc4fffb` | 2026-09-26 | fix(opencode): route theme writes to selected settings | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `87826c1a` | 2026-09-26 | fix(uninstall): scope OpenCode-family cleanup by runtime and legacy ownership | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `f00df6a1` | 2026-09-26 | test(uninstall): pin XDG_CONFIG_HOME in OpenCode uninstall integration tests | not-applicable | upstream tests |
| `f5b236e7` | 2026-09-26 | fix(uninstall): remove gentle-ai-managed OpenCode and Kilo agents | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `3a19dbf8` | 2026-09-26 | Merge pull request #5004 from pablon/pr-slice-1 | not-applicable | merge of the JSONC legacy marker cleanup (OpenCode settings) |
| `da00e9b3` | 2026-09-26 | fix(opencode): explain non-regular settings resolution | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `fe4390b8` | 2026-09-26 | docs(odd): record OpenCode marker migration evidence | not-applicable | upstream feature document |
| `0dc8cc60` | 2026-09-26 | fix(opencode): migrate legacy agent markers during sync | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `263a8f63` | 2026-09-26 | Merge pull request #5006 from Gentleman-Programming/fix/review-guidance-ownership | informational | merge of `535fd70e`, `b8f5d7b1` |
| `befd337e` | 2026-09-26 | fix(opencode): record legacy migration writes even when publishing errors | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `b8f5d7b1` | 2026-09-26 | refactor(agentguidance): keep review-contract fallback helpers test-only | informational | `orchestrator.go`: review-contract fallback helpers made test-only; no Hermes behavior |
| `d652462a` | 2026-09-26 | fix(filemerge): accept empty OpenCode settings during marker cleanup | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `535fd70e` | 2026-09-26 | fix(opencode): scope review cleanup and review-contract wiring | informational | `inject.go`/`orchestrator.go`: OpenCode review cleanup and review-contract wiring; the Hermes injection path is unchanged |
| `6471b688` | 2026-09-26 | Merge pull request #5005 from Gentleman-Programming/fix/orchestrator-prompt-install | informational | merge of `fb4b59a7`, `1ba7d888`, `5ffb65fc` and their tests |
| `3d5c5a4e` | 2026-09-26 | docs(odd): align orchestrator feature objective with RDD scoping | not-applicable | upstream feature document |
| `81a4711a` | 2026-09-26 | test(e2e): expect the orchestrator section in theme-only installs | not-applicable | upstream tests |
| `4d95d115` | 2026-09-26 | test(e2e): expect RDD routing guidance only on RDD runtimes | not-applicable | upstream tests (RDD routing only on RDD runtimes) |
| `5ffb65fc` | 2026-09-26 | feat(rdd): limit receipt-driven development to Claude Code, Codex and OpenCode | ported | RDD only for runtimes with a native review transport (`model.SupportsReceiptDrivenDevelopment`: claude-code, codex, opencode, pi); Hermes gets ODD-only routing and orchestrator prompts. hermes-odd keeps its honest stance (native review unavailable on Hermes; the 4R advisory and judgment-day say "no receipt"), aligns the prompt Review line and step 7, `hermes-odd:rdd-review` and the canonical re-render |
| `2372afd1` | 2026-09-26 | fix(filemerge): require json.Valid before MarshalJSONPreservingPermissions | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `96bed1cb` | 2026-09-26 | feat(filemerge): add JSONC-aware legacy marker cleanup with comment preservation | not-applicable | gentle-ai config file writer (TOML/JSON merge, file modes) |
| `1ba7d888` | 2026-09-26 | feat(prompts): port Gentle Shell orchestration sections to every runtime | ported | shared orchestrator sections (`_shared/odd-orchestrator-sections.md`): the risk-proportionate Delegated Verification Gate and checking rules ported into `hermes-odd:odd-delegation` section 3 and `hermes-odd:odd-workflow` section 6 |
| `fb4b59a7` | 2026-09-26 | fix(install): install the ODD and RDD orchestrator prompt for every runtime | ported | installs the ODD-only Hermes orchestrator (`internal/assets/hermes/orchestrator.md`) as a top-level `gentle-ai:orchestrator` block ahead of agent-routing in `SOUL.md`, renaming a v3.7.0 `sdd-orchestrator` block; `/odd-soul` now removes `orchestrator` too. Its ODD behavior is ported in own words (see the T11 table above) |
| `c014fbe3` | 2026-09-26 | Merge pull request #4998 from Gentleman-Programming/fix/4471-opencode-agent-parity | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `45523842` | 2026-09-26 | fix(upgrade): back up OpenCode default-agent ownership at the effective path | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `209d8867` | 2026-09-26 | fix(opencode): preserve settings file mode on managed rewrites | not-applicable | OpenCode settings file mode (touches `inject.go` for OpenCode delivery only) |
| `a0509694` | 2026-09-26 | docs(odd): record PR review fixes for opencode agent parity | not-applicable | upstream feature document |
| `3f8df517` | 2026-09-26 | fix(skills): remove the legacy shared marker on Windows and uninstall | not-applicable | gentle-ai uninstall for OpenCode/Kilo |
| `b51df813` | 2026-09-26 | docs(odd): record opencode agent parity verification evidence | not-applicable | upstream feature document |
| `57871ec7` | 2026-09-26 | fix(kilo): restore managed agents and migrate v3.7.0 __managed_by | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `3d01b376` | 2026-09-26 | fix(install): restore non-SDD assets dropped by the SDD retirement | not-applicable | gentle-ai skill and OpenCode asset installer after the SDD retirement; hermes-odd ships its own skills |
| `b674adf5` | 2026-09-25 | fix(opencode): migrate v3.7.0 managed agents off __managed_by | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `72519aca` | 2026-09-25 | fix(opencode): restore agent parity with Gentle Shell without __managed_by | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `84062a2e` | 2026-09-25 | fix(assets): probe the PATH binary on every relay and drop the mtime cache | not-applicable | OpenCode review transport plugin |
| `9fdf84d7` | 2026-09-25 | test(state): merge the bundle-digest sensitivity tests into one | not-applicable | upstream tests |
| `be20c940` | 2026-09-21 | chore(deadcode): baseline updated for #4760 manifest data model | not-applicable | upstream dead-code baseline |
| `0da1ab73` | 2026-09-18 | feat(state): introduce managed-assets manifest model | not-applicable | gentle-ai managed-assets state manifest |
| `bff0ddac` | 2026-09-25 | Merge remote-tracking branch 'upstream/main' into fix/2995-rebased | informational | merge of `main` into the #2995 review store branch |
| `7ac249a4` | 2026-09-23 | docs(odd): reconcile ga-2995 edge-detachment checklist with completed evidence (#4899) | not-applicable | upstream feature document |
| `ce97fa40` | 2026-09-23 | docs(odd): record re-confirmed size decision for #4899 | not-applicable | upstream feature document |
| `cb6383f9` | 2026-09-23 | docs(odd): record increment review evidence for the edge-detachment follow-up (#2995) | not-applicable | upstream feature document |
| `f4dea1e3` | 2026-09-23 | fix(review): hold edge-detachment across all historical disposition surfaces (#2995) | informational | review store and disposition logic inside the binary; no hermes-odd surface while native review is unavailable (T8) |
| `26b363ba` | 2026-09-23 | fix(review): fail-closed edge-detachment guard and decoupled disposition derivation (#2995) | informational | review store and disposition logic inside the binary; no hermes-odd surface while native review is unavailable (T8) |
| `bf41c6fb` | 2026-09-22 | style(bench): apply gofmt to the journey review-mode registration (#2995) | not-applicable | upstream tests |
| `70dcf4e6` | 2026-09-22 | feat(review): selector-scoped historical disposition exit for multi-record stores (#2995) | informational | review store and disposition logic inside the binary; no hermes-odd surface while native review is unavailable (T8) |
| `a8fc566f` | 2026-09-22 | fix(review): keep retired-seam refusals analyzable for the refusal ratchet (#2995) | informational | review store and disposition logic inside the binary; no hermes-odd surface while native review is unavailable (T8) |
| `ca229e94` | 2026-09-22 | fix(review): classify released v2.2.x completed records as historical, not malformed (#2995) | informational | review store and disposition logic inside the binary; no hermes-odd surface while native review is unavailable (T8) |
| `a14592cb` | 2026-09-23 | docs(odd): scope ga-4882 Windows-suite status to the PR lane, keep main pending | not-applicable | upstream feature document |
| `b8fca0cf` | 2026-09-23 | docs(odd): mark ga-4882 task-3 checks done and record green Windows lane (#4914) | not-applicable | upstream feature document |
| `ead893ec` | 2026-09-23 | docs(odd): record CI flake triage for the ga-4882 unit job | not-applicable | upstream feature document |
| `2fa7fe15` | 2026-09-23 | docs(odd): record ga-4882 review evidence and PR linkage | not-applicable | upstream feature document |
| `d66e7214` | 2026-09-23 | fix(telemetry): carry same-process exclusion with a path mutex, not byte-range semantics (#4882) | not-applicable | telemetry |
| `2d320b83` | 2026-09-24 | test(install): tighten the module-path suite to fit the 400-line budget | not-applicable | upstream tests |
| `fb1786ef` | 2026-09-24 | test(update): guard the derived installer module path instead of the hard-coded /v3 | not-applicable | upstream tests |
| `c2dc7129` | 2026-09-24 | fix(install): derive unix installer module path from the resolved source revision | not-applicable | gentle-ai self-install and update |
| `047c81f5` | 2026-09-21 | fix(test): match runOpenCodeTransportPluginHarness 3-value return at assets_test.go:90 | not-applicable | upstream tests |
| `5fe328ca` | 2026-09-18 | chore(opencode): tighten comments around the #3049 binary-handshake module | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `7ad964a5` | 2026-09-18 | chore(opencode): tighten comments around the #3049 binary-handshake module | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `e273773c` | 2026-09-09 | fix(opencode): lower MIN_GENTLE_AI_VERSION to 2.0.0 for E2E binary compatibility | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `72c492e8` | 2026-09-03 | fix(opencode): resolve gentle-ai.exe on Windows in resolveGentleAiPath | not-applicable | OpenCode/Kilo adapter, settings and agents |
| `8559320f` | 2026-09-03 | fix(test): pin TestOpenCodeReviewTransportPluginBinaryHandshakeRefusesUnavailable to a controlled PATH | not-applicable | upstream tests |
| `5e9498b0` | 2026-08-25 | fix(opencode): probe PATH gentle-ai before relay, refuse on binary skew or absent binary | not-applicable | OpenCode/Kilo adapter, settings and agents |

gentle-shell `5456811..b756b4f` (111 commits):

| Commit | Date | Subject | Class | Reason |
|---|---|---|---|---|
| `b756b4f` | 2026-09-26 | Merge pull request #1482 from Gentleman-Programming/fix/history-review-advisories | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `13e1407` | 2026-09-26 | fix(history): resolve review advisories on carry, notices and layout | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `50b2af7` | 2026-09-26 | Merge pull request #1480 from Gentleman-Programming/feat/history-responsive-header | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `4c89734` | 2026-09-26 | feat(history): restore responsive selector header and sidebar-aware margin | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `5167c5c` | 2026-09-26 | Merge pull request #1477 from Gentleman-Programming/fix/history-reliability-followups | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `7f2d968` | 2026-09-26 | fix(history): harden GC and delete follow-ups, query-aware Home/End | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `d615b2e` | 2026-09-26 | Merge pull request #1475 from Gentleman-Programming/feat/history-customize-toggle | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `9eaa2ea` | 2026-09-26 | feat(history): add persisted capture toggle to Customize | not-applicable | prompt-history capture toggle in the Pi Customize panel (`extensions/gentle-shell.ts`, `README.md`) |
| `45240bc` | 2026-09-26 | Merge pull request #1472 from Gentleman-Programming/fix/test-isolation-local-state | not-applicable | merge of Pi TUI work listed in this table |
| `002ac99` | 2026-09-26 | test: isolate presence and vim tests from local machine state | not-applicable | upstream tests |
| `b322392` | 2026-09-26 | Merge pull request #1394 from carolitascl/feat/history-slice-06-gc | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `d50e80e` | 2026-09-26 | Merge pull request #1470 from Gentleman-Programming/fix/profiles-name-input | not-applicable | Pi model profiles |
| `8b341d1` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/history-pr1394-adaptation | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `117398e` | 2026-09-26 | fix(profiles): make create, duplicate, and rename name input visible | not-applicable | `/gentle:profiles` name input (Pi TUI); touches `extensions/gentle-ai.ts` only for that panel |
| `a3d063f` | 2026-09-26 | Merge pull request #1441 from rjoleinik/fix/subagent-empty-root-selector | not-applicable | Pi agents widget and RPC |
| `d71eec3` | 2026-09-26 | Merge pull request #1393 from carolitascl/feat/history-slice-05-delete | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `779bdb7` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/history-pr1393-adaptation | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `3561ee3` | 2026-09-26 | Merge pull request #1468 from Gentleman-Programming/fix/hide-running-agent-polls | not-applicable | merge of Pi TUI work listed in this table |
| `1d128c9` | 2026-09-26 | Merge pull request #1391 from carolitascl/feat/history-slice-04-seed | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `f0ac446` | 2026-09-26 | feat(agents): hide running result polls from the transcript | not-applicable | hides running subagent result polls from the Pi transcript (`extensions/gentle-agents.ts`); Hermes renders its own transcript |
| `6b38444` | 2026-09-26 | docs(odd): record history migration verification evidence | not-applicable | upstream feature document |
| `cc6ecca` | 2026-09-26 | fix(history): preserve concurrent legacy migration data | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `15249c5` | 2026-09-26 | Merge remote-tracking branch 'origin/main' into fix/history-pr1391-adaptation | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `f6a832f` | 2026-09-26 | fix(history): preserve migration retry and tombstones | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `06c9915` | 2026-09-26 | Merge pull request #1435 from danielgap/fix/1011-thread-item-identity | informational | merge of `65466d5` |
| `1dd58f2` | 2026-09-26 | Merge pull request #1406 from carlosmoradev/fix/1403-profile-effort-key-tolerance | not-applicable | Pi model profiles |
| `565b3b6` | 2026-09-26 | Merge pull request #1465 from carlosmoradev/fix/1434-subagent-format-cost | informational | merge of `e57db24`, `a1c6777` |
| `9e6cdc8` | 2026-09-26 | Merge pull request #1464 from carlosmoradev/fix/1458-windows-vim-path-separator | not-applicable | Vim mode (Pi TUI) |
| `678016f` | 2026-09-26 | Merge pull request #1423 from AutanaSoft/fix/1176-shell-effective-profile | not-applicable | Pi model profiles |
| `fd050ad` | 2026-09-26 | Merge pull request #1455 from carolitascl/feat/history-slice-03-selector-v2 | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a23de44` | 2026-09-26 | Merge pull request #1454 from carolitascl/feat/history-slice-03-searchlist | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `12e6215` | 2026-09-26 | Merge pull request #1453 from carolitascl/feat/history-slice-03-openflow | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `91aea7c` | 2026-09-26 | Merge pull request #1392 from carolitascl/feat/history-slice-02-read | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `86500ee` | 2026-09-26 | Merge pull request #1390 from carolitascl/feat/history-slice-01-store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a1c6777` | 2026-09-26 | test(agents): update subagent cost fixture assertion to 3 decimals | not-applicable | upstream tests |
| `e57db24` | 2026-09-26 | fix(agents): format subagent cost with shared formatCost helper (#1434) | informational | `lib/agents-view.ts`: subagent cost formatted with the shared helper; `/odd-agents` shows no cost (Hermes hooks report none) |
| `df1cbbe` | 2026-09-26 | fix(vim): match Windows path separators in resolveVimRuntime (#1458) | not-applicable | Vim runtime path on Windows (Pi TUI) |
| `4d581c6` | 2026-09-26 | fix(shell): show only the selected status bar on narrow screens (#1462) | not-applicable | Pi status bar on narrow screens (`extensions/gentle-shell.ts`, `README.md`) |
| `9f05dff` | 2026-09-26 | Merge branch 'main' into fix/1176-shell-effective-profile | not-applicable | Pi model profiles |
| `32c1978` | 2026-09-26 | Merge pull request #1461 from decode2/fix/1162-subagent-message-staleness | not-applicable | Pi agents widget and RPC |
| `1eeca21` | 2026-09-26 | fix(agents): defer query consumption until reply acceptance (#1162) | not-applicable | Pi cross-orchestrator message queries (`extensions/gentle-agents.ts`); not ported (see the baseline entry) |
| `5981153` | 2026-09-25 | fix(history): strip-types-safe constructors for the node test runner | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e29fb43` | 2026-09-25 | Merge commit 'a225102f' into feat/history-slice-06-gc | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e95d63e` | 2026-09-25 | fix(agents): invalidate subagent messages and queries on task settlement (#1162) | not-applicable | Pi cross-orchestrator message and query invalidation (`extensions/gentle-agents.ts`) |
| `e302337` | 2026-09-25 | fix(history): modal delete confirm, read-only session rows, GENTLE_PI_HISTORY_ENABLE, hidden.json cap | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `7232863` | 2026-09-25 | fix(agents): treat a blank root selector as absent | not-applicable | Pi agents RPC root selector (`extensions/gentle-agents.ts`) |
| `146db16` | 2026-09-25 | Merge commit '89ac348' into feat/history-slice-05-delete | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `65466d5` | 2026-09-25 | perf(agents): reuse unchanged remote thread items across polls | informational | `lib/agents-view.ts`: reuses unchanged remote thread items across polls (Pi rendering cache); `/odd-agents` is a concept port that re-reads Hermes hooks and needs no cache |
| `78c7535` | 2026-09-25 | fix(shell): use lowercase profile source suffixes | not-applicable | Pi profile source labels (`extensions/gentle-shell.ts`) |
| `f32f132` | 2026-09-25 | docs(odd): record verified main integration | not-applicable | upstream feature document |
| `5d88e33` | 2026-09-25 | Merge remote-tracking branch 'upstream/main' into fix/1176-shell-effective-profile | not-applicable | Pi model profiles |
| `4f0178f` | 2026-09-25 | docs(odd): record verified profile fix | not-applicable | upstream feature document |
| `b5e0751` | 2026-09-25 | fix(shell): show repository-effective agent profile | not-applicable | Pi repository-effective agent profile (`extensions/gentle-shell.ts`) |
| `649711c` | 2026-09-25 | Merge commit '417b9fd' into feat/history-slice-04-seed | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `6ad6191` | 2026-09-24 | feat(history): add selector preview and mouse handling | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `8745414` | 2026-09-24 | feat(history): add selector search and list windowing | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `7f3aed8` | 2026-09-24 | feat(history): add the selector open flow | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a225102` | 2026-09-24 | docs(history): compaction is not a retention limit | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e2cca1f` | 2026-09-24 | fix(history): scope the gc slice to lifecycle work | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a500f39` | 2026-09-24 | Merge branch 'feat/history-slice-05-delete' into feat/history-slice-06-gc | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `417b9fd` | 2026-09-24 | fix(history): port fail-closed tombstones to the seed slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `89ac348` | 2026-09-24 | fix(history): restore fail-closed tombstones and honest delete UX | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `c4f20d5` | 2026-09-24 | Merge branch 'feat/history-slice-04-seed' into feat/history-slice-05-delete | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `f4b7a33` | 2026-09-24 | fix(history): gate legacy seeding/migration behind capture opt-in | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `2fcacf7` | 2026-09-24 | Merge branch 'feat/history-slice-05-delete' into feat/history-slice-06-gc | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `1f91268` | 2026-09-24 | Merge branch 'feat/history-slice-04-seed' into feat/history-slice-05-delete | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `653c01d` | 2026-09-24 | Merge branch 'feat/history-slice-03-selector' into feat/history-slice-04-seed | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `aae5d7d` | 2026-09-24 | Merge branch 'feat/history-slice-02-read' into feat/history-slice-03-selector | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `d50702d` | 2026-09-24 | Merge branch 'feat/history-slice-01-store' into feat/history-slice-02-read | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `ccbd4f6` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-06-gc | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `9fb1bd5` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-05-delete | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `674a160` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-04-seed | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `f11fdba` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-02-read | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `6786efd` | 2026-09-24 | chore(ci): re-trigger checks | not-applicable | upstream tests and CI |
| `6e27038` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-01-store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a663195` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `3cc57c7` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e81e194` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `aae37cb` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `892da55` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e787ce4` | 2026-09-24 | chore(readme): remove README delta from history slice | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a6b4722` | 2026-09-24 | Merge remote-tracking branch 'upstream/main' into feat/history-slice-03-selector | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `831bbe9` | 2026-09-24 | fix(history): make prompt capture opt-in and document the store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `5d85a8f` | 2026-09-24 | fix(history): make prompt capture opt-in and document the store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `041973d` | 2026-09-24 | fix(history): make prompt capture opt-in and document the store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `25a1dd1` | 2026-09-24 | fix(history): make prompt capture opt-in and document the store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `ecf148b` | 2026-09-24 | merge: sync slice-02 stack with slice-01 tip | not-applicable | merge of Pi TUI work listed in this table |
| `559cc7a` | 2026-09-24 | fix(models): accept effort as alias for thinking in profile routing entries (#1403) | not-applicable | Pi model profile routing (`effort` alias) |
| `5501d12` | 2026-09-24 | fix(history): fail closed on untrustworthy hidden.json tombstones | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `31e7d50` | 2026-09-24 | Merge upstream/main into feat/history-slice-01-store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `84c1232` | 2026-09-24 | fix(history): make prompt capture opt-in and document the store | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `ea7e33b` | 2026-09-23 | fix(history): satisfy upstream typecheck gate | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `353a99f` | 2026-09-23 | fix(history): satisfy upstream typecheck gate | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a22588f` | 2026-09-23 | fix(history): satisfy upstream typecheck gate | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `1c59b11` | 2026-09-23 | fix(history): restore review fixes clobbered by the upstream sync | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `c18271f` | 2026-09-21 | fix(test): match node:test TestFn callback type in skip wrappers | not-applicable | upstream tests and CI |
| `26bd9b5` | 2026-09-21 | test(history): remove machine-specific fixed paths from test fixtures | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `fdef2fc` | 2026-09-21 | fix(history): satisfy upstream typecheck gate | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `e5746ec` | 2026-09-21 | refactor(history): extract shared header counts helper | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `72b5adf` | 2026-09-21 | feat(history): sync extension with pi-history latest | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `c9c1c51` | 2026-09-18 | fix(history): pid-scoped compact filename; accurate GC threshold comment | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `7cc79b2` | 2026-09-18 | feat(history): tombstones, deletion, and privacy semantics | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `96443ee` | 2026-09-18 | feat(history): GC/compaction with active-writer and failure-path tests | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `6b61c98` | 2026-09-18 | fix(history): migration renames only after the seed write; init off the first-prompt path | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `c63caa5` | 2026-09-18 | feat(history): transcript migration and seeding | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `d354c8a` | 2026-09-18 | fix(history): intact astral characters, correct row padding, honest comments | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `366b179` | 2026-09-18 | feat(history): history selector TUI and command/shortcut wiring | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `73c55ff` | 2026-09-18 | docs(history): correct drainGlobal seed-ordering docblock | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `a5ff13d` | 2026-09-18 | feat(history): read, ordering, deduplication, and project/global query APIs | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `2b90751` | 2026-09-18 | fix(history): stable registry collision mappings | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |
| `9b56e0b` | 2026-09-18 | feat(history): per-instance JSONL store, project identity, storage tests | not-applicable | Pi prompt history store and selector (`/gentle:history`, `docs/prompt-history.md`); Hermes keeps its own session history |

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
| gentle-ai | `internal/components/agentguidance/strict_tdd.go` | informational | manages the legacy `strict-tdd-mode` section of system-prompt files (`SOUL.md` for Hermes, markdown-sections strategy); `internal/cli/run.go` calls it with `enabled=false`, so a newer gentle-ai run retires that section. hermes-odd writes no such block; `/odd-soul` removes it (T11 follow-up) |
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
| `e219644b` | 2026-09-25 | feat(workflow)!: retire SDD and OpenSpec in favor of ODD | informational | retires SDD and OpenSpec upstream: `routing.go`, `inject.go` and the Hermes orchestrator asset lose their SDD text (`internal/assets/hermes/sdd-orchestrator.md` becomes `orchestrator.md`, and no Go code injects it at the new head); hermes-odd already ships no SDD, so nothing to port beyond re-hashing and the canonical re-render; `/odd-soul` keeps removing the old `sdd-orchestrator` block of existing `SOUL.md` files. `work-unit-commits` loses its SDD section, matching the T10 port |
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
| Engram protocol block (`internal/assets/engram/protocol.md`, full variant) | ported as a lazy skill: `hermes-odd:engram-protocol`, own condensed wording bound to `mcp__engram__*` (when and what to save, topic keys, search before asking, session summary, after compaction); removed from `SOUL.md` by `/odd-soul`; a prompt-section line points to it while `engram_protocol` is `auto`. The slim, passive-capture and compact variants are not ported (they target runtimes with their own hooks) |
| CodeGraph guidance block (`CodeGraphGuidanceMarkdown` in `internal/components/communitytool/codegraph_guidance.go`) | ported as a lazy skill: `hermes-odd:codegraph` (worktree placement, required order, read-only surface); `gentle-ai codegraph init --cwd <root>` becomes the upstream CLI `codegraph init <root>` (codegraph 1.2.0); a prompt-section line points to it while `codegraph_guidance` is `auto` and CodeGraph is on `PATH` or configured as an MCP server |
| `remote-authorization` block (`remote_authorization.go`, `internal/assets/generic/remote-authorization-contract.md`) | kept in SOUL: lifted byte-identical, with its `gentle-ai:` markers, out of `agent-routing` into its place (a general safety rule the user keeps) |
| `sdd-orchestrator`, `sdd-session-preflight`, `agent-routing` blocks | removed by `/odd-soul apply confirm` (backup, atomic write, verification); hermes-odd ships no SDD and supplies ODD routing through its own section |
| gentle-ai `persona` block | kept; `/odd-soul plan persona` removes it only on request and only while a hermes-odd persona block exists |
| Re-adding by gentle-ai | not portable: `gentle-ai install` selecting Hermes or `gentle-ai sync --agent hermes` writes the blocks again; `/odd-soul` warns about it (binary-only rule) |

### 2026-09-25: T9a first-run setup (gentle-ai installer persona step)

The gentle-ai installer (`internal/tui/screens/*.go`) is a terminal wizard that
selects what gentle-ai writes into each agent's configuration. hermes-odd is
one Hermes plugin with a fixed surface, so only the steps that record a user
preference Hermes can apply are ported, over chat (CLI/TUI and Telegram).

| Area | Decision |
|---|---|
| Installer persona step (`internal/tui/screens/persona.go`: gentleman / neutral / custom) and the gentle-pi persona view (`GENTLEMAN_PERSONA_PROMPT`, `NEUTRAL_PERSONA_PROMPT` in `extensions/gentle-ai.ts`) | ported as the first-run setup: `hermes-odd:setup` asks once over `clarify` (Mentor rioplatense (voseo), Mentor neutral, My own text, None; no default and no recommended option), `/odd-setup persona <id>` previews and `confirm` writes; the persona is one `hermes-odd:persona` block at the top of `SOUL.md`, with a backup |
| Persona texts (`internal/assets/hermes/persona-gentleman.md`, `persona-neutral.md`) | ported in hermes-odd's own words (`hermes_odd/personas.py`): the behavior rules only. Not ported: the `## Identity` product identity, branding, author biography, tool preferences, and the Hermes skill-loading and Engram memory sections (Hermes loads plugin skills itself; the Engram protocol became the lazy skill `hermes-odd:engram-protocol` in T9b) |
| Installer strict TDD step (`internal/tui/screens/strict_tdd.go`) | ported as the setup's TDD question (off / strict / per project); it reached ODD as one `TDD mode:` line in the prompt section. Retired in T11 with the upstream picker (see the 2026-09-27 entry) |
| Engram setup and SOUL cleanup of gentle-ai blocks | preferences stored in T9a (`engram_protocol`, `soul_cleanup`); behavior shipped in T9b (see the T9b entry) |
| Installer presets (`internal/tui/screens/preset.go`: Memory Only, Dev Stack, Dev Stack + Polish, Custom) | not portable: they choose which gentle-ai components (SDD, skills, themes, logo, GGA) get installed into agent configurations; hermes-odd installs as one plugin and ships no SDD, themes or logo |
| Component selection and dependency tree (`skill_picker.go`, `community_tools.go`, `dependency_tree.go`, `opencode_plugins.go`) | not applicable: the plugin surface is fixed; Engram and CodeGraph are separate MCP servers the user installs in Hermes |
| Model pickers and model configuration (`model_picker.go`, `claude_model_picker.go`, `codex_model_picker.go`, `kiro_model_picker.go`, `model_config.go`, `profiles.go`) | not applicable: Hermes owns model selection (`hermes model`, `config.yaml`); hermes-odd never routes models |
| Review mode step (`review_mode.go`, `install_review_mode.go`) | already ported: `/odd-review-mode` (T7) |
| Backups screen (`backups.go`) | partly: every `SOUL.md` write keeps a `SOUL.md.hermes-odd-bak-<UTC timestamp>` copy (last 5); `/odd-soul restore` lists and restores them (T9b) |
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
| Review mode switch (gentle-pi review-mode view over `gentle-ai review mode`) | ported: `/odd-review-mode [status\|enable\|disable] [global\|clone] [project]`, concept port; `status` read-only, `enable`/`disable` need an explicit scope and are user-typed writes of gentle-ai's own switch |
| Native review facade (`gentle_review*` over `gentle-ai review start/status/...`) | blocked upstream: runtime eligibility; Hermes is refused with `immutable_review_transport_unsupported`. hermes-odd never passes another runtime's identity (`--agent pi` or any other). Availability is probed read-only and shown by `/odd-review-mode`, `/odd-status` and `/odd-doctor`; T8 waits on upstream |
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
| Pi agents view (gentle-shell `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts` `TaskRecord` model) | ported: `/odd-agents` (T3), concept port with no copied text, fed by Hermes `subagent_start`/`post_tool_call`/`subagent_stop` hooks |
| Pi agents view: stopping a running subagent | not portable: Hermes offers no safe plugin path from a command (`ctx.subagent_lifecycle.cancel` only accepts handles minted by its own `launch`; `tools.delegate_tool.interrupt_subagent` is internal, unscoped and in-process); users ask the agent to run `delegate_task` `action=stop` |
| Pi todo card + ODD feature document view (gentle-shell `extensions/gentle-todo.ts`, `lib/shell-todo.ts`) | ported: `/odd-tasks` (T4) as a plain-text viewer, concept port with no copied text; it reads `odd/tasks/*.md` of known projects (roots recorded from the prompt section's session `cwd`) and of the command process's own directory |
| Pi interactive `todo` tool | not portable: Hermes' native `todo` tool is used instead (the `odd-feature-tracking` skill maps feature tasks onto it) |
| Pi Gentle Changes capture and list (gentle-shell `lib/session-changes.ts`, `lib/shell-changes.ts`, `lib/shell-changes-view.ts`, Gentle Changes in `README.md` / `docs/gentle-shell.md`) | ported as text: `/odd-changes` (T5), concept port with no copied text; successful `write_file`/`patch` calls from Hermes' `post_tool_call` (main agent and subagents), per-file line counts computed at capture time, attribution, 24 h / 7 day windows, per-file timeline and `git diff --numstat`; like upstream, shell edits are not captured. No file content or diff is stored, so `write_file` removed lines are unknown |
| Pi Gentle Changes two-pane diff viewer (`lib/shell-changes-view.ts`: accordion, captured diff pane, `alt+g`, `o` to open in the editor) and before/after snapshots | not portable: Pi TUI overlay; hermes-odd commands answer plain text on every gateway and never store file content |
| Pi `gentle:status` (`extensions/gentle-ai.ts`) | ported: `/odd-status` (T6), concept port with no copied text: version, prompt section size, skills, subagents, changes, ODD features, gentle-ai binary against the lock minimum, cached RDD mode, supported upstreams |
| Pi `gentle:doctor` (`extensions/gentle-ai.ts`) | ported: `/odd-doctor` (T6), concept port with no copied text: pass/warn/fail checks with remedies for the gentle-ai binaries on `PATH`, RDD mode (`gentle-ai review mode status --json`), `SOUL.md` size, managed blocks and Hermes truncation, the plugin surface and `ctx.state`, the upstream lock and Hermes |
| Pi doctor/status checks for package assets, OpenSpec config, skill registry, model routing and the dev binary | not portable: Pi package and runtime plumbing (OpenSpec is SDD) |
| Pi views: review mode, persona | review mode ported: `/odd-review-mode` (T7); persona ported as the first-run setup (T9a, see the 2026-09-25 T9a entry; `/odd-commands` ported) |
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
| `2ac9c68` | feat(sidebar): add RDD status contract and renderer | partly ported (T6): `/odd-status` and `/odd-doctor` show the RDD mode in gentle-ai's own wording; the lineage labels (`Reviewing`, `Awaiting consent`, ...) are not applicable until native review exists on Hermes (T8, blocked upstream); the sidebar widget is not portable (Pi TUI) |
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
