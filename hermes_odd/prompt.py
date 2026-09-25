"""Compact, always-on ODD system prompt section for Hermes.

Hermes renders plugin sections once per session through
``PluginManager.render_system_prompt_sections`` (``hermes_cli/plugins.py``):
text longer than ``max_chars`` is skipped, not truncated, and every plugin
shares an 8000-char aggregate budget. The section therefore stays well under
:data:`SECTION_BUDGET_CHARS` and points to lazy plugin skills for detail.

Derived from (drift tooling diffs these sources; the markers are not rendered
into the prompt to save budget):

<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 extensions/gentle-ai.ts -->
<!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 assets/orchestrator.md -->
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

logger = logging.getLogger("hermes_odd")

SECTION_ID = "hermes-odd-workflow"
SECTION_MAX_CHARS = 4000
# Hard budget enforced by tests; leaves headroom under SECTION_MAX_CHARS.
SECTION_BUDGET_CHARS = 3800

# Skills referenced by the section, namespaced the way Hermes exposes plugin
# skills (``<plugin>:<name>``) to ``skill_view``.
SKILL_NAMESPACE = "hermes-odd"

ODD_SECTION = """\
# ODD workflow (hermes-odd)

Organic Driven Development (ODD) is the default workflow. Every request enters it without the user asking. Run it; never only describe it:
1. Authorize. Investigation, explanation, review, comparison and proposal-only requests stay read-only: no edits, no writer delegation. Ambiguous or conditional change intent: ask one clarification, then stop and wait.
2. Explore existing code and requirements first, proportionately.
3. Resolve uncertainty. Research only for a named uncertainty; ask one focused question only for a real product decision, then stop; at most one read-only assumption challenge for a high-consequence premise.
4. Classify. Substantial = 2+ meaningful implementation steps or progress worth recovering. Small, understood work creates no task artifacts.
5. Track before the first write (substantial only): create `odd/tasks/<feature>.md` and its Engram mirror topic `odd/<feature>/tasks` (`mcp__engram__mem_save`), then rebuild the `todo` list from its tasks. No permission prompt; tell the user in one line which document and how many tasks.
6. Implement task by task with the configured TDD mode and checks. Check off only observed outcomes; update file, mirror and `todo` on every transition. Close each task with a Conventional Commit work-unit commit on the feature branch (branch first when on the default branch), tests and docs included; record the commit id. Push, PR and merge are the user's decisions.
7. Close: verified outcome, every failed, skipped or pending check, next step.

Resume: `mcp__engram__mem_context`, then project- and feature-scoped `mcp__engram__mem_search`, then `mcp__engram__mem_get_observation`, then the task file; reconcile before continuing.

Mandatory delegation triggers via `delegate_task` (not advisory; executing past one inline is a routing defect):
- Mapping: understanding needs 4+ files -> one read-only mapping child first.
- Writer: 2+ non-trivial files -> one bounded writer child with `## Allowed edit surfaces`.
- Preparation: reading that prepares a write, or broad research, goes with or ahead of the writer.
- Incident: wrong cwd, worktree, git or tooling -> diagnose separately before resuming.
- Long session: ~20 tool calls, 5 exploratory reads or 2 non-mechanical edits without delegating -> delegate the next unit.
- Verification: running check commands beyond a 1-3 file read-only check -> a verifier child.
Inline only for 1-3 known files or one mechanical edit. Children know nothing of this chat, cannot call clarify and run in the background: send self-contained missions, keep one writer per worktree, treat summaries as self-reports and verify them.

Blocking questions: use `clarify` (one decision, closed choices, recommended first). Without it, send the complete question and every option as plain chat, then stop and wait.

Language: reply in the user's language; code, comments, commits, docs and task files in English.

Review: native review runs only under the user-owned RDD switch; load hermes-odd:rdd-review.

Formal SDD is not provided by this plugin.

Before substantial work load with `skill_view`: hermes-odd:odd-workflow (routing, checks, delivery), hermes-odd:odd-feature-tracking (feature document, Engram mirror, resume, todo); before delegating: hermes-odd:odd-delegation (missions, edit surfaces).
"""


# Appended only while the first-run setup is pending (no ``setup`` record in
# ``ctx.state``); removed once setup is completed or skipped.
SETUP_PENDING_LINE = (
    "hermes-odd setup is pending: when the user is not mid-task, offer it once "
    "(load hermes-odd:setup); never interrupt work."
)
SETUP_PENDING_LINE_MAX_CHARS = 200

# Pointers to lazy skills, one line each, added by the setup preferences
# (``engram_protocol``, ``codegraph_guidance``); both default to ``auto``.
MEMORY_POINTER = (
    "Memory: with mcp__engram__* tools, load hermes-odd:engram-protocol "
    "(what to save, search first, session summary)."
)
CODEGRAPH_POINTER = (
    "Code structure: CodeGraph is present; load hermes-odd:codegraph before broad searches."
)
POINTER_LINES = (MEMORY_POINTER, CODEGRAPH_POINTER)
POINTER_LINE_MAX_CHARS = 160


def build_odd_section(
    session_info: Mapping[str, Any] | None = None,
    *,
    setup_pending: bool = False,
    tdd_line: str | None = None,
    pointers: Sequence[str] = (),
) -> str:
    """Return the compact ODD section.

    With no setup input the text is exactly ``ODD_SECTION.strip()``. Skill
    ``pointers`` (memory, CodeGraph), a ``tdd_line`` (the user's TDD mode
    from setup) and the setup-pending line are appended, one line each and
    in that order, only when present. ``session_info`` is accepted for the
    Hermes callable contract.
    """
    text = ODD_SECTION.strip()
    extra = [
        line
        for line in (*pointers, tdd_line, SETUP_PENDING_LINE if setup_pending else None)
        if line
    ]
    if extra:
        text += "\n\n" + "\n".join(extra)
    return text


SectionObserver = Callable[[Mapping[str, Any]], None]
# Returns ``(setup_pending, tdd_line or None[, pointer lines])``.
SetupInputs = Callable[[], tuple]


def make_section_callable(
    observer: SectionObserver | None = None,
    setup_inputs: SetupInputs | None = None,
) -> Callable[[Mapping[str, Any]], str]:
    """Return the callable registered as the section content.

    Hermes calls it once per new session with a read-only ``session_info``
    mapping (``session_id``, ``model``, ``provider``, ``platform``,
    ``profile_name``, ``cwd``). ``observer`` sees that mapping (``/odd_tasks``
    uses it to learn project roots); its failures are swallowed so the
    section is never skipped, and the observer cannot change the prompt.
    ``setup_inputs`` (the first-run setup) decides the optional TDD mode and
    setup-pending lines and the lazy-skill pointers; when it fails the
    section renders without them.
    """

    def render(session_info: Mapping[str, Any] | None = None) -> str:
        if observer is not None:
            try:
                observer(session_info if isinstance(session_info, Mapping) else {})
            except Exception:  # noqa: BLE001 - never skip the section
                logger.debug("hermes-odd: section observer failed", exc_info=True)
        pending, tdd_line, pointers = False, None, ()
        if setup_inputs is not None:
            try:
                values = tuple(setup_inputs())
                pending, tdd_line = values[0], values[1]
                if len(values) > 2:
                    pointers = tuple(p for p in values[2] if p in POINTER_LINES)
            except Exception:  # noqa: BLE001 - never skip the section
                logger.debug("hermes-odd: setup inputs failed", exc_info=True)
                pending, tdd_line, pointers = False, None, ()
        return build_odd_section(
            session_info, setup_pending=bool(pending), tdd_line=tdd_line, pointers=pointers
        )

    render.__name__ = "hermes_odd_workflow_section"
    return render
