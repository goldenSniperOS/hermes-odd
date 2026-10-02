"""Compact, always-on ODD system prompt section for Hermes.

Hermes renders plugin sections once per session through
``PluginManager.render_system_prompt_sections`` (``hermes_cli/plugins.py``):
text longer than ``max_chars`` is skipped, not truncated, and every plugin
shares an 8000-char aggregate budget. The section therefore stays well under
:data:`SECTION_BUDGET_CHARS` and points to lazy plugin skills for detail.

Derived from (drift tooling diffs these sources; the markers are not rendered
into the prompt to save budget):

<!-- derived-from: gentle-ai@5140c5f55baf91763198eb0bfca019c015e3b015 internal/components/agentguidance/routing.go -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 extensions/gentle-ai.ts -->
<!-- derived-from: gentle-shell@1f345106ff2931383451d4e05ec76d1259471884 assets/orchestrator.md -->
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

Organic Driven Development (ODD) is the default workflow: every request enters it unasked. Run it, never just describe it:
1. Authorize. Investigation, explanation, review, comparison and proposal-only requests stay read-only: no edits, no writer delegation. Ambiguous or conditional change intent: one clarification, then stop. Paths outside the project root and its worktrees need consent naming the absolute path.
2. Explore existing code and requirements proportionately.
3. Resolve uncertainty: research only a named one; one focused question only for a real product decision, then stop; at most one read-only challenge of a high-consequence premise.
4. Classify. Substantial = 2+ meaningful implementation steps or progress worth recovering. Small, understood work creates no task artifacts.
5. Track before the first write (substantial only): create `odd/tasks/<feature>.md` and its Engram mirror `odd/<feature>/tasks` (`mcp__engram__mem_save`), then rebuild `todo` from its tasks. No permission prompt; name the document and task count in one line.
6. Implement task by task, test-first when a relevant runnable deterministic test and a clear expected outcome exist: observed RED, GREEN, refactor (tests merely existing do not qualify); else state the exception, run proportionate checks. Never invent RED/GREEN or a runner. Check off only observed outcomes; update file, mirror and `todo` on every transition. Close each task with a Conventional Commit work-unit commit (tests and docs included) on the feature branch (branch first if on the default branch); record its id. Push, PR and merge are the user's decisions.
7. Close: verified outcome, every failed, skipped or pending check, next step. Verify per work-unit commit or PR slice, never per checkbox or whole branch.

Resume: `mcp__engram__mem_context`, then project- and feature-scoped `mcp__engram__mem_search`, then `mcp__engram__mem_get_observation`, the task file; reconcile first.

Mandatory delegation triggers via `delegate_task` (past one inline is a defect):
- Mapping: evidence past the evidence budget (at most 3 calls, ~10k tokens) or ~5+ sequential lookups -> a read-only explorer child (at most ~2k tokens back, path:line); spot-check once.
- Writer: 2+ non-trivial files -> one bounded writer child with `## Allowed edit surfaces`.
- Preparation: reading for a write, or broad research, goes with the writer.
- Incident: wrong cwd, worktree, git or tooling -> stop writes, diagnose separately.
- Long session: ~150k parent-context tokens (advisory) -> delegate the next unit; bound shell output.
- Verification: suites, builds or checks past the budget -> a verifier child.
Inline only within the budget or for one mechanical edit. Children have no chat or `clarify`, run in the background: send self-contained missions, one writer per worktree; verify their reports.

Blocking questions: `clarify` (one decision, closed choices, recommended first), else the full question and options as plain chat; then stop.

Language: reply in the user's language; code, comments, commits, docs and task files in English.

Formal SDD is not provided by this plugin.

Load with `skill_view` by qualified name, never a same-named bare skill: substantial work hermes-odd:odd-workflow, hermes-odd:odd-feature-tracking; delegating hermes-odd:odd-delegation; commits, PRs hermes-odd:work-unit-commits, hermes-odd:chained-pr; dual review hermes-odd:judgment-day.
"""


# Appended only while the first-run setup is pending (no ``setup`` record in
# ``ctx.state``); removed once setup is completed or skipped.
SETUP_PENDING_LINE = (
    "hermes-odd setup is pending: offer it once when the user is not mid-task "
    "(load hermes-odd:setup); never interrupt work."
)
SETUP_PENDING_LINE_MAX_CHARS = 200

# Pointers to lazy skills, one line each, added by the setup preferences
# (``engram_protocol``, ``codegraph_guidance``); both default to ``auto``.
# The memory pointer has two mutually exclusive variants: the recall one
# replaces the default while the hermes-recall provider is active.
MEMORY_POINTER = (
    "Memory: with mcp__engram__* tools, load hermes-odd:engram-protocol before saving or searching."
)
MEMORY_POINTER_RECALL = (
    "Memory: the recall provider injects Engram context every turn; "
    "save decisions and discoveries per hermes-odd:engram-protocol."
)
CODEGRAPH_POINTER = (
    "Code structure: CodeGraph is present; load hermes-odd:codegraph before broad searches."
)
# Every known pointer: the render allow-list. At most one memory variant is
# rendered (the recall one wins).
POINTER_LINES = (MEMORY_POINTER, MEMORY_POINTER_RECALL, CODEGRAPH_POINTER)
POINTER_LINE_MAX_CHARS = 160


def build_odd_section(
    session_info: Mapping[str, Any] | None = None,
    *,
    setup_pending: bool = False,
    pointers: Sequence[str] = (),
) -> str:
    """Return the compact ODD section.

    With no setup input the text is exactly ``ODD_SECTION.strip()``. Skill
    ``pointers`` (memory, CodeGraph) and the setup-pending line are appended,
    one line each and in that order, only when present. ``session_info`` is
    accepted for the Hermes callable contract.
    """
    text = ODD_SECTION.strip()
    extra = [line for line in (*pointers, SETUP_PENDING_LINE if setup_pending else None) if line]
    if extra:
        text += "\n\n" + "\n".join(extra)
    return text


SectionObserver = Callable[[Mapping[str, Any]], None]
# Returns ``(setup_pending, pointer lines)``.
SetupInputs = Callable[[], tuple]


def make_section_callable(
    observer: SectionObserver | None = None,
    setup_inputs: SetupInputs | None = None,
) -> Callable[[Mapping[str, Any]], str]:
    """Return the callable registered as the section content.

    Hermes calls it once per new session with a read-only ``session_info``
    mapping (``session_id``, ``model``, ``provider``, ``platform``,
    ``profile_name``, ``cwd``). ``observer`` sees that mapping (``/odd-tasks``
    uses it to learn project roots); its failures are swallowed so the
    section is never skipped, and the observer cannot change the prompt.
    ``setup_inputs`` (the first-run setup) decides the setup-pending line and
    the lazy-skill pointers; when it fails the section renders without them.
    """

    def render(session_info: Mapping[str, Any] | None = None) -> str:
        if observer is not None:
            try:
                observer(session_info if isinstance(session_info, Mapping) else {})
            except Exception:  # noqa: BLE001 - never skip the section
                logger.debug("hermes-odd: section observer failed", exc_info=True)
        pending, pointers = False, ()
        if setup_inputs is not None:
            try:
                values = tuple(setup_inputs())
                pending = values[0]
                if len(values) > 1:
                    pointers = tuple(p for p in values[1] if p in POINTER_LINES)
                    if MEMORY_POINTER_RECALL in pointers:
                        pointers = tuple(p for p in pointers if p != MEMORY_POINTER)
            except Exception:  # noqa: BLE001 - never skip the section
                logger.debug("hermes-odd: setup inputs failed", exc_info=True)
                pending, pointers = False, ()
        return build_odd_section(session_info, setup_pending=bool(pending), pointers=pointers)

    render.__name__ = "hermes_odd_workflow_section"
    return render
