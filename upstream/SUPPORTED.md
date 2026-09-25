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
| `rdd` | partial (T7 ported, T8 blocked upstream) | `/odd_review_mode` (`hermes_odd/commands/review_mode.py`, `hermes_odd/rdd.py`, probes in `hermes_odd/probes.py`), `skills/rdd-review`, `skills/rdd-review-lenses`; planned `odd_review` facade | gentle-ai `internal/assets/skills/rdd-defect-workflow/SKILL.md`, `internal/agents/capabilitymanifest/manifest.go`, `internal/cli/review_transport_capability.go`; gentle-shell `skills/rdd-defect-workflow/SKILL.md`, `docs/review-integration.md`, `extensions/gentle-ai.ts`, `lib/review-integration-v2.ts`, `lib/native-review-cli.ts`, `assets/agents/review-{risk,resilience,readability,reliability}.md`, `assets/chains/4r-review.chain.md` |
| `review-contract` | pending (T8, blocked upstream) | CLI contract `gentle-ai.review-integration/v2` (capabilities v2.6); provider contract mirror 1.2.0; verified: `--agent hermes` fails with `gentle-ai.review-integration.failure/v2` `immutable_review_transport_unsupported` | gentle-ai `contracts/review-provider-contract/CONTRACT_SEMVER`, `contracts/review-integration/v2/schemas/{capabilities-v2.6,start-v4,status-v9,consent-v3,transition-binding}.schema.json`; gentle-shell `contracts/review-provider-contract-mirror/provider-contract.lock.json`, `.../v1.2.0/bundle/orchestration/pi.md`, `scripts/gentle-ai-installer.mjs` |
| `viewers` | ported | Viewers `/odd_agents`, `/odd_tasks`, `/odd_changes`; Health `/odd_status`, `/odd_doctor`, `/odd_commands` (all concept ports, no copied text) | gentle-shell `extensions/gentle-ai.ts`, `extensions/gentle-agents.ts`, `lib/agents-protocol.ts`, `lib/agents-view.ts`, `docs/gentle-agents-activity.md`, `extensions/gentle-shell.ts`, `extensions/gentle-todo.ts`, `docs/gentle-shell.md`, `lib/shell-changes.ts`, `lib/shell-todo.ts`, `lib/review-sidebar-state.ts`, `lib/session-changes.ts`, `lib/shell-changes-view.ts`, `README.md` |
| `persona` | ported (T9a) | First-run setup: skill `skills/setup` (one `clarify` call), `/odd_setup` (`hermes_odd/commands/setup.py`), tool `odd_setup_apply` (`hermes_odd/setup_tool.py`), preferences and setup record (`hermes_odd/setup.py`), plugin `config_schema`, and one `<!-- hermes-odd:persona -->` block at the top of `SOUL.md` (`hermes_odd/soul_persona.py`, texts in `hermes_odd/personas.py`, own wording) | gentle-ai `internal/assets/hermes/persona-gentleman.md`, `internal/assets/hermes/persona-neutral.md`; gentle-shell `extensions/gentle-ai.ts` (`GENTLEMAN_PERSONA_PROMPT`, `NEUTRAL_PERSONA_PROMPT`) |
| `soul-cleanup` | ported (T9b) | `/odd_soul` (`hermes_odd/commands/soul.py`), tool `odd_soul_apply` (`hermes_odd/soul_tool.py`), cleanup rules and verification (`hermes_odd/soul_cleanup.py`, concept port), lazy skills `skills/engram-protocol` and `skills/codegraph` (own wording), one pointer line each in the prompt section | gentle-ai `internal/assets/engram/protocol.md`, `internal/components/communitytool/codegraph_guidance.go`, `internal/components/agentguidance/inject.go`, `internal/components/agentguidance/remote_authorization.go`, `internal/assets/generic/remote-authorization-contract.md` |

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
| Installer strict TDD step (`internal/tui/screens/strict_tdd.go`) | ported as the setup's TDD question (off / strict / per project); it reaches ODD as one `TDD mode:` line in the prompt section, read by `hermes-odd:odd-workflow` |
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
| gentle-ai `internal/assets/skills/hermes-ephemeral-delegation` | pending: T10 review against `odd-delegation`; its frontmatter declares Apache-2.0, confirm licensing before deriving |
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
