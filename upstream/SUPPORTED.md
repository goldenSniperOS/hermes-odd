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
| gentle-ai | v3.7.0 | `f182ea2018a6399f5d1b6557cf36d71a3df0f723` (2026-09-23) | 3.7.0 (tested 3.7.0) |
| gentle-shell (npm `gentle-pi` 3.7.0) | v3.7.0 | `4d702a47a31eade9ea197d9280ba1d0afe8b93f4` (2026-09-24, `v3.7.0-16-g4d702a4`) | 3.7.0 (pinned by gentle-pi 3.7.0) |

Notes:

- **gentle-ai tag vs pin.** The `v3.7.0` tag points at `6dee8f8`, which is not
  on gentle-ai's current `main` (its history was rewritten to drop the
  `.engram/` directory). The pin `f182ea2` is on `main`: its parent `204ccbd`
  has the tag's tree minus `.engram/`, and `f182ea2` only adds a README badge.
  Every indexed source hashes identically at the tag and at the pin.
- **gentle-shell pin.** 16 commits after the `v3.7.0` tag; triaged below.
- The gentle-ai binary is used only through `gentle-ai review` (RDD). Never
  run `gentle-ai install` for Hermes or `gentle-ai sync --agent hermes`.

## Component matrix

| Component | Status | hermes-odd surface | Upstream sources (pinned) |
|---|---|---|---|
| `odd` | ported | `hermes_odd/prompt.py` (section `hermes-odd-workflow`), `skills/odd-workflow`, `skills/odd-delegation`, `skills/odd-feature-tracking`, `upstream/odd-routing-hermes.canonical.md` | gentle-ai `internal/components/agentguidance/routing.go`, `internal/agents/capabilitymanifest/manifest.go`; gentle-shell `extensions/gentle-ai.ts`, `assets/orchestrator.md`, `assets/orchestrator-delegation.md`, `assets/orchestrator-skills.md`, `assets/orchestrator-memory.md` |
| `rdd` | pending (T7, T8) | planned `skills/rdd-review`, `odd_review` tool, `/odd_review_mode` | gentle-ai `internal/assets/skills/rdd-defect-workflow/SKILL.md`; gentle-shell `skills/rdd-defect-workflow/SKILL.md`, `docs/review-integration.md`, `extensions/gentle-ai.ts`, `lib/review-integration-v2.ts`, `lib/native-review-cli.ts` |
| `review-contract` | pending (T7, T8) | CLI contract `gentle-ai.review-integration/v2` (capabilities v2.6); provider contract mirror 1.2.0 | gentle-ai `contracts/review-provider-contract/CONTRACT_SEMVER`, `contracts/review-integration/v2/schemas/{capabilities-v2.6,start-v4,status-v9,consent-v3,transition-binding}.schema.json`; gentle-shell `contracts/review-provider-contract-mirror/provider-contract.lock.json`, `.../v1.2.0/bundle/orchestration/pi.md`, `scripts/gentle-ai-installer.mjs` |
| `viewers` | partial (T6 pending) | `/odd_commands`, `/odd_agents`, `/odd_tasks` and `/odd_changes` ship (`/odd_agents`, `/odd_tasks` and `/odd_changes` are concept ports, no copied text); `/odd_status`, `/odd_doctor` pending | gentle-shell `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts`, `docs/gentle-agents-activity.md`, `extensions/gentle-shell.ts`, `extensions/gentle-todo.ts`, `docs/gentle-shell.md`, `lib/shell-changes.ts`, `lib/shell-todo.ts`, `lib/review-sidebar-state.ts`, `lib/session-changes.ts`, `lib/shell-changes-view.ts`, `README.md` |

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
   component for review. (T10 automates this with a drift script.)
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
   `block_sha256`, and diff it against the previous render.
7. **Bump the lock**: `supported_release`, `pinned_commit`, `commit_date`,
   binary `min_version`/`tested_version`, and every `sources` sha256.
8. **CHANGELOG**: add a line under `## [Unreleased]` naming the new upstream
   versions and what was ported.
9. Run the tests; `tests/test_upstream_lock.py` cross-checks the lock, the
   markers, `THIRD_PARTY_NOTICES.md`, the canonical render and this file.

## Triage log

### 2026-09-24: baseline gentle-ai v3.7.0 and gentle-shell v3.7.0

Initial port at gentle-ai `f182ea2` (v3.7.0) and gentle-shell `4d702a4`
(v3.7.0+16, npm `gentle-pi` 3.7.0).

| Area | Decision |
|---|---|
| ODD protocol, delegation triggers, resume order, feature tracking (gentle-ai `routing.go`; gentle-shell `assets/orchestrator*.md`, `extensions/gentle-ai.ts`) | ported: compact section + `odd-*` skills, bound to `delegate_task`, `clarify`, `mcp__engram__*` |
| Canonical `RenderRouting(model.AgentHermes)` | ported: vendored verbatim in `upstream/odd-routing-hermes.canonical.md` for drift comparison |
| RDD review lifecycle (`gentle_review*` facade, `rdd-defect-workflow`, review CLI contract v2, provider contract mirror 1.2.0) | pending: T7, T8 |
| Pi agents view (gentle-shell `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts` `TaskRecord` model) | ported: `/odd_agents` (T3), concept port with no copied text, fed by Hermes `subagent_start`/`post_tool_call`/`subagent_stop` hooks |
| Pi agents view: stopping a running subagent | not portable: Hermes offers no safe plugin path from a command (`ctx.subagent_lifecycle.cancel` only accepts handles minted by its own `launch`; `tools.delegate_tool.interrupt_subagent` is internal, unscoped and in-process); users ask the agent to run `delegate_task` `action=stop` |
| Pi todo card + ODD feature document view (gentle-shell `extensions/gentle-todo.ts`, `lib/shell-todo.ts`) | ported: `/odd_tasks` (T4) as a plain-text viewer, concept port with no copied text; it reads `odd/tasks/*.md` of known projects (roots recorded from the prompt section's session `cwd`) and of the command process's own directory |
| Pi interactive `todo` tool | not portable: Hermes' native `todo` tool is used instead (the `odd-feature-tracking` skill maps feature tasks onto it) |
| Pi Gentle Changes capture and list (gentle-shell `lib/session-changes.ts`, `lib/shell-changes.ts`, `lib/shell-changes-view.ts`, Gentle Changes in `README.md` / `docs/gentle-shell.md`) | ported as text: `/odd_changes` (T5), concept port with no copied text; successful `write_file`/`patch` calls from Hermes' `post_tool_call` (main agent and subagents), per-file line counts computed at capture time, attribution, 24 h / 7 day windows, per-file timeline and `git diff --numstat`; like upstream, shell edits are not captured. No file content or diff is stored, so `write_file` removed lines are unknown |
| Pi Gentle Changes two-pane diff viewer (`lib/shell-changes-view.ts`: accordion, captured diff pane, `alt+g`, `o` to open in the editor) and before/after snapshots | not portable: Pi TUI overlay; hermes-odd commands answer plain text on every gateway and never store file content |
| Pi views: status, doctor, review mode, persona | pending: T6, T7, T9 (`/odd_commands` ported) |
| gentle-ai `internal/assets/skills/hermes-ephemeral-delegation` | pending: T10 review against `odd-delegation`; its frontmatter declares Apache-2.0, confirm licensing before deriving |
| gentle-ai `internal/assets/hermes/persona-*.md` | pending: T9 (`/odd_persona`) |
| SDD assets, agents, chains, skills, commands, preflight | not portable: hermes-odd ships no SDD |
| Themes, banners, animations, TUI widgets, shortcuts, double-esc cancel | not portable: Pi terminal UI |
| Dev binary, bundled gentle-ai download, telemetry, Pi model profiles/routing, Pi package installers | not portable: Pi runtime plumbing |
| gentle-ai `install`/`sync` agent writers for Hermes | not portable: they write SDD-heavy `SOUL.md` that Hermes truncates |

### 2026-09-24: gentle-shell v3.7.0..4d702a4 (unreleased, 16 commits)

Included in the pin; decisions below record what hermes-odd takes from each.

| Commit | Subject | Decision |
|---|---|---|
| `2ac9c68` | feat(sidebar): add RDD status contract and renderer | pending: T6/T7, reuse the review-status wording for `/odd_status`; the sidebar widget is not portable (Pi TUI) |
| `8becfd8` | fix(sidebar): distinguish pending reviews and accept replayed starts | pending: T6/T7, same as `2ac9c68` (pending vs replayed START semantics) |
| `b019517` | feat(agents): require user consent before cross-orchestrator communication (#1364) | not portable: gates Pi `orchestrator_send_message` between Pi sessions; hermes-odd adds no inter-session messaging tool |
| `4210e56` | fix(agents): sanitize consent prompt, derive concrete reason, and handle prompt session change (#1364) | not portable: same Pi messaging consent as `b019517` |
| `46abadb` | docs(odd): record Gentle Shell v3.7.0 publication | not applicable: upstream feature document |
| `be2d7b1` | Merge pull request #1319 (feat/rdd-status-sidebar-01-contract-renderer) | pending: T6/T7, merge of `2ac9c68`/`8becfd8` |
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

### 2026-09-24: seen beyond the pins (not yet supported)

Observed on upstream `main` after the pins; the pins stay where they are until
the next sync triages these properly.

gentle-ai `f182ea2..40b35ee` (7 commits, unreleased):

| Commit | Subject | Decision |
|---|---|---|
| `c2ed12a5` | fix(review): stop restarting escalated original targets | pending: T8, review CLI behavior (needs a binary release) |
| `8edb9d98` | docs(odd): record issue 4433 verification evidence | not applicable: upstream feature document |
| `465452eb` | Merge pull request #4963 (fix/4433-terminal-start-conflict-current) | pending: T8, merge of `c2ed12a5` |
| `0281553d` | fix(telemetry): skip zero-delta series in runtime metrics | not portable: telemetry |
| `480f2e3b` | fix(telemetry): evict idle runtime metric series after a TTL | not portable: telemetry |
| `c7651af5` | docs(telemetry): record the cardinality fix delivery and deploy | not applicable: upstream feature document |
| `40b35ee2` | fix(telemetry): render expired runtime series before evicting them | not portable: telemetry |

gentle-shell `4d702a4..a923264` (5 commits, unreleased):

| Commit | Subject | Decision |
|---|---|---|
| `cc5fbd9` | refactor(shell): remove SDD surfaces and retain user safety | pending: next sync; changes `assets/orchestrator*.md`, `extensions/gentle-ai.ts` and `extensions/gentle-agents.ts` (indexed `odd` and `viewers` sources) |
| `7c95eb4` | docs(odd): record Shell verification and review blocker | not applicable: upstream feature document |
| `0822e74` | test(shell): record isolated packed installer proof | not applicable: upstream feature document |
| `2201956` | chore: integrate Shell main into ODD retirement | pending: next sync, merge of `main` into `cc5fbd9` |
| `a923264` | Merge pull request #1408 (feat/remove-sdd-odd-only) | pending: next sync, merge of `cc5fbd9` |
