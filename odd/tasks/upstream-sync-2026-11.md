# Feature: upstream sync to gentle-ai main 1ab243c / gentle-pi main a1c4463 (hermes-odd v0.9.0)

Port every portable ODD/Engram guidance change upstream shipped after the v4.0.0 pin
(through gentle-ai v4.5.0 + main, gentle-pi v4.8.0 + main), then re-pin the lock.
No SDD, no Pi-only surfaces, no native review transport (Hermes still lacks it).

## Specs

- S1 "actualicemos el port al dia de hoy con todo lo nuevo." Port every portable change
  from the 2026-11-16 drift table: gentle-ai #5850, #6145 / gentle-shell #3286, #6069,
  #6072, #6073, #6070, #6084, #6090, #6091, #6071, gentle-shell #3244, #3292, plus any
  other portable guidance change the full pin..main triage finds.
- S2 Re-pin `upstream/upstream.lock.json` to today's upstream main (gentle-ai 1ab243c,
  gentle-shell a1c4463), hashes refreshed, every commit triaged in `upstream/SUPPORTED.md`
  (ported / not portable + reason).
- S3 The always-on prompt section stays within its 3800-character budget; detail goes to
  lazy skills.
- S4 Release prep v0.9.0: versions aligned (pyproject, plugin.yaml, `__version__`,
  CHANGELOG), tests, smoke and ruff green.

## T2 port map (parent decisions from T1)

Upstream diffs: `.atl/upstream-sync/` (gitignored; `render-main.md` is the current
`RenderRouting(model.AgentHermes)`, `ai-*.diff` gentle-ai v4.3.1..main, `shell-*.diff`
gentle-shell pin..main). Port in our own words, Hermes-correct (`delegate_task`,
`clarify`, `todo`, `terminal`, `mcp__engram__*` / recall `mem_*`). Never SDD, never
native review, Pi tools (`ask_user_choice`, codemode, `gentle_review*`) or
"Needs your decision" consent envelopes.

- R1 Continuity (#6145/#3286): authorized in-scope steps continue without per-step
  approval; a pending child is a wait, its completion resumes the work; stop only for a
  real human decision, explicit stop, denial or exhausted limit, and only for the work it
  covers; hedged wording is not a stop; missing proof blocks the completion claim, not
  independent authorized work; resolving an incident never cancels the objective.
  prompt step 7 (one sentence) + `odd-workflow` full text; `odd-delegation` section 3
  "Needs your decision" line becomes: unit stays `partial`, naming the decision;
  independent work continues.
- R2 Informed short approval (#5850): clarify only what the human needs to understand
  the action; a short "yes"/"go ahead" accepts the immediately preceding concrete
  proposal, no re-ask; a preference alone is not authorization; approval never covers
  publish or destructive steps. prompt step 1 (one sentence) + `odd-workflow` 1 and 4.
- R3 Task Size (render-main "Task Size"): small = understood (one batch, at most 3 calls,
  ~10k tokens), contained risk, resumable from the request plus `git diff`; large only
  when that resume test fails; counts never decide; small path inline with no feature
  document, mirror or commits unless asked; large gets tracking, writers only by the
  Writer trigger. Replaces "Substantial" everywhere (prompt steps 4-5 and Load line,
  `odd-workflow`, `odd-feature-tracking`). Risk line: before `Risk: none` check shared
  code (item 3) — already present, keep.
- R4 Writers (#6070/#6084): "launched together in one turn"; every new writer launch
  carries `## Allowed edit surfaces` (a steer/continuation passes the full list again);
  a rejected launch is repaired once for what it names, never resent unchanged; the
  parent adds a requested path itself when it serves the authorized objective without
  ownership/concurrency conflict, asking the human only for new scope, outside repos,
  destructive steps or a denial. Parallel writers + Invariants bullets from render-main
  go to `odd-delegation` (same tree, disjoint surfaces, parent owns git, no repo-wide
  formatters/installs by writers, shared file one owner, per-diff surface check, one
  seam check; prompts name helpers and invariants to reuse).
- R5 Verify by change kind (#6072/#3101): the verifier mission names the change kind;
  the verifier does not re-run the writer's suite; runs spec examples and parent-
  authorized commands plus its own probes, mutating ones against isolated state
  (`mktemp -d`), stored data unchanged by rejected commands; a user-reported failure is
  reproduced at baseline first; returned probes become tests through the writer.
  `odd-delegation` section 3.
- R6 Children (#6090/#3092): a resumed/steered child does not re-read skills or specs it
  already read unless changed; reports at most ~2k tokens, never restating task, spec or
  unchanged files; pass only skills matching the unit (no commit skill to a child that
  won't commit); children check `git status --short` for tool caches/scratch they made
  and name leftovers instead of deleting; test scratch outside the worktree.
  `odd-delegation` mission template.
- R7 Tracking (#6073/#3083 + render-main): the file is the source, mirror and `todo` are
  projections; targeted edits, never whole-file rewrites; read back with the normal read
  tool; never author reconciliation scripts; after a failed sync check which writes
  applied and never replay one; a drifted mirror is refreshed, never a blocker; mirror
  once per task transition (plus material plan change and close), Log entries between
  transitions go to the file only; obsolete tasks `dropped`, externally waiting
  `blocked` with the unblock condition (Hermes `todo` has `cancelled`; map dropped ->
  `cancelled`). Document layout: header, `## Specs` (`S#` quoting the user verbatim, no
  unrequested requirements), `## Tasks` (ID, `S#`, route, commit), `## Log` last (L1 =
  original request verbatim; a requirement change appends Log, rewrites only its `S#`,
  reopens only its task); hand off by reference (`Spec: odd/tasks/<f>.md, T2, S3-S4`,
  read until `## Log`, report which `S#` were covered). prompt step 6 wording;
  `odd-feature-tracking` template, mirror, `todo` sections; `odd-delegation` template.
- R8 Engram (#6069): `engram-protocol` "When to save": no "right after"; a request with
  several fixes is saved once when done unless one has a non-obvious root cause; the
  save may share a turn; self-check saves before the final answer.
- R9 Commits (#6071 + render-main step 6): `work-unit-commits` drops "implementation" as
  a trigger word if present; work units in reviewable slices of about 400 authored
  changed lines; a unit whose Risk line names a high-risk item gets its own commit; a
  user's line limit is a ceiling, never an exact-count gate.
- R10 Tests (render-main test-first bullet): one RED test per requested rule; one test per
  touched existing command/option proving previous behavior; differential check against
  a `mktemp -d` baseline copy only when shared code changed; update help/docs when a
  command, option or message changes. `odd-workflow` section 6.
- R11 (#6091) explicit user request: `advisory-review-lenses` runs when the user asks even
  if no rule would offer it (likely already present; confirm, add one line if not).
- Budget: always-on section (`build_odd_section()` with no pointers) <= 3800; the full
  render with both pointers and the setup line must stay < 4000 (now 3450 / 3784), so
  net prompt growth <= ~150 chars; compress elsewhere in the section to pay.
- Derived-from markers and the lock stay at the old pins in T2; T3 re-pins them.

## Tasks

- [x] T1 [S1,S2] Triage pin..main guidance diffs and map each to a hermes-odd target — inline/explore — no commit
- [x] T2 [S1,S3] Port behavior rules (prompt + odd-* skills + engram-protocol), tests first — delegated (context backstop) — commit a21df73; RED 11/11, GREEN 423 OK, ruff clean; section 3455 / full 3789
- [x] T3 [S2] Re-pin lock + SUPPORTED.md triage log — delegated (context backstop) — commit c3d4412; 423 OK, drift script clean
- [x] T2b [S1] Port Engram #2022/#5663 and CodeGraph #4151/12c1a157/e6a6e949/69da4962 guidance (found by T3 triage), tests first — inline — commit 8f6ceea; RED 3/3, GREEN 426 OK, smoke OK
- [x] T4 [S4] Release prep v0.9.0, CI — inline — commit eee452c; 426 OK, smoke OK, ruff clean; CI green (3.11, 3.12); tag v0.9.0 released with 4 assets

## Log

- L1 (user, 2026-11-16): "Dale arranca, actualicemos el port al dia de hoy con todo lo nuevo."
- L6 Feature closed 2026-11-16: v0.9.0 released. Follow-ups outside scope: hermes-recall prompt sync for #6069/#2022; live install update (`hermes plugins update hermes-odd`).
- L5 T3 done (c3d4412). Worker flagged portable Engram/CodeGraph changes outside the T2 map; per L1 "con todo lo nuevo" they are ported as T2b, not marked not portable.
- L4 T2 done 2026-11-16 (a21df73). Full render ceiling is 3800 (tests/test_setup.py:189), not 4000: ~11 chars left.
- L3 T1 done 2026-11-16: explorer mapping (task mwjs1uwg-2-hbcs) -> T2 port map above.
  Context backstop fired at ~160k parent tokens -> T2 delegated to one writer.
- L2 Drift table delivered 2026-11-16 (Engram `hermes-odd/upstream/drift-check`, id 804);
  user accepted the proposal: behavior port commit + re-pin, include unreleased #6145.
