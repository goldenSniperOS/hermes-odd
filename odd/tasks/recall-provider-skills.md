# Feature: recall provider skills (hermes-odd v0.7.1)

## Objective

Align the lazy skills with hermes-recall v0.5.0, whose `recall` memory provider
exposes Engram's agent tools as plain `mem_*` provider tools and replaces the
Engram MCP server.

## Problem

`odd-feature-tracking` and `odd-delegation` only named `mcp__engram__*` tools.
With recall active those tools do not exist, so the mirror would be marked
pending and children would be told to save memories that recall refuses.

## Scope

- `odd-feature-tracking`: "With the recall provider" section.
- `odd-delegation`: children return discoveries; the parent saves them.
- `engram-protocol`: injected session/project, `mem_update` `expected_project`,
  `mem_session_finalize`.
- Setup option wording covers recall's `mem_*` tools.
- Release v0.7.1 (versions, CHANGELOG); no push or tag.

## Non-goals

- Changing the always-on prompt (`MEMORY_POINTER_RECALL` already adapts).
- Editing hermes-recall.

## Tasks

- [x] T1 Recall guidance in the three skills and the setup wording, tests first.
- [x] T2 Release prep v0.7.1.

## Checks

Test-first: RED observed (6 failures in `test_prompt_and_skills` and
`test_setup`) before the skill edits; GREEN with python3.14 (406 tests OK).
Under the Hermes venv two pre-existing tests fail because they read the real
`~/.hermes` config, where `memory.provider` is `recall`
(`test_register_adds_section_and_all_skills`,
`test_register_records_known_project_from_section`).

`scripts/smoke_e2e.py` passes 74 checks (skills registered included) and then
stops at "/odd-tasks shows the next task": since `b87fdd9` (v0.7.0)
`gateway_safe` renders `/odd-tasks` in inline code, and the smoke still
expects plain text. This is unrelated to this feature and left for a follow-up.

## Next step

Parent reviews, pushes, tags v0.7.1 after CI on `main`.
