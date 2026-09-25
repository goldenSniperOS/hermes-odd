"""Clean the gentle-ai managed blocks out of ``SOUL.md`` (``/odd_soul``, ``odd_soul_apply``).

gentle-ai's Hermes writer (``gentle-ai install`` selecting Hermes,
``gentle-ai sync --agent hermes``) puts its guidance into ``SOUL.md`` as
``<!-- gentle-ai:<name> -->`` blocks. Hermes sends ``SOUL.md`` with every
message and truncates it (see :mod:`hermes_odd.soul`); hermes-odd already
supplies ODD through its prompt section and lazy skills, so most of those
blocks are dead weight. The cleanup rules (user decisions):

====================================  ===================================================
top-level block                       action
====================================  ===================================================
``gentle-ai:sdd-orchestrator``        remove (with its nested ``sdd-session-preflight``)
``gentle-ai:sdd-session-preflight``   remove (when found on its own)
``gentle-ai:agent-routing``           remove, but **lift** its nested
                                      ``gentle-ai:remote-authorization`` block into
                                      its place (a general safety rule)
``gentle-ai:engram-protocol``         move to skill ``hermes-odd:engram-protocol``
``gentle-ai:codegraph-guidance``      move to skill ``hermes-odd:codegraph``
``gentle-ai:persona``                 keep; removed only on explicit request and only
                                      while a hermes-odd persona block exists
anything else                         keep (user text, unknown blocks, every
                                      ``hermes-odd:`` block)
====================================  ===================================================

The lifted block keeps its upstream ``gentle-ai:remote-authorization``
markers and bytes: the text is gentle-ai's canonical contract (relabelling
it ``hermes-odd:`` would claim ownership of text hermes-odd does not
maintain), the post-write check can prove it byte-identical, and gentle-ai's
marker tooling still recognizes it. A ``remote-authorization`` nested in a
removed block whose byte-identical copy is already kept at the top level is
dropped instead of lifted twice (a later ``gentle-ai sync`` re-adds
agent-routing with its nested copy).

Safety: markers are scanned strictly (every closer must close the innermost
open block of the same namespace and name); an unclosed, stray or crossed
marker refuses the whole plan and nothing changes. The file is read with
:func:`hermes_odd.soul_persona.read_soul_file` (symlink, > 4 MB and
non-UTF-8 refused) and written through :func:`hermes_odd.soul_persona.apply_plan`
(backup ``SOUL.md.hermes-odd-bak-<UTC>``, last 5 kept, atomic replace with
the original permissions). Before writing, and again on the written file:
every kept and lifted block is byte-identical and in order, removed blocks
are gone, and every user character outside blocks is unchanged (only the
blank lines around removed blocks change). SOUL content is never returned
in messages, only sizes and block names.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import soul as soul_mod
from . import soul_persona as sp

GENTLE_AI = soul_mod.GENTLE_AI
HERMES_ODD = soul_mod.HERMES_ODD

REMOVE, MOVE, KEEP = "remove", "move-to-skill", "keep"
LIFT, DROP = "lift", "drop-duplicate"
LIFTED_NAME = "remote-authorization"
PERSONA_NAME = "persona"
MAX_MARKERS = 128

# gentle-ai top-level block name -> (action, skill that now carries it).
RULES: dict[str, tuple[str, str]] = {
    "sdd-orchestrator": (REMOVE, ""),
    "sdd-session-preflight": (REMOVE, ""),
    "agent-routing": (REMOVE, ""),
    "engram-protocol": (MOVE, "hermes-odd:engram-protocol"),
    "codegraph-guidance": (MOVE, "hermes-odd:codegraph"),
}

BINARY_WARNING = (
    "gentle-ai re-adds these blocks if you later run `gentle-ai install` selecting "
    "Hermes or `gentle-ai sync --agent hermes`; hermes-odd needs only the gentle-ai "
    "binary (binary-only rule)."
)


@dataclass(frozen=True)
class Node:
    namespace: str
    name: str
    start: int
    end: int
    depth: int
    parent: int | None  # index into the node list

    @property
    def label(self) -> str:
        return f"{self.namespace}:{self.name}"

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass
class Item:
    """One top-level block and what the cleanup does with it."""

    label: str
    chars: int
    action: str = KEEP
    skill: str = ""
    nested: list[tuple[str, int]] = field(default_factory=list)
    lifted: list[tuple[str, int, str]] = field(default_factory=list)  # label, chars, LIFT|DROP
    note: str = ""

    @property
    def removes(self) -> bool:
        return self.action in (REMOVE, MOVE)

    @property
    def saved(self) -> int:
        """Block characters that leave SOUL.md (a lifted block stays)."""
        if not self.removes:
            return 0
        return self.chars - sum(chars for _label, chars, how in self.lifted if how == LIFT)


@dataclass
class CleanupPlan:
    path: Path
    exists: bool = False
    error: str = ""
    items: list[Item] = field(default_factory=list)
    before: str = ""
    after: str = ""
    mode: int = sp.NEW_FILE_MODE
    before_chars: int = 0  # measured like Hermes (stripped, no BOM)
    after_chars: int = 0
    user_chars: int = 0  # characters outside every block (newlines excluded)
    hermes_persona: bool = False
    remove_persona: bool = False  # requested
    persona_note: str = ""

    @property
    def writes(self) -> bool:
        return not self.error and self.exists and self.after != self.before

    @property
    def removable(self) -> list[Item]:
        return [item for item in self.items if item.removes]

    @property
    def gentle_persona(self) -> bool:
        return any(item.label == f"{GENTLE_AI}:{PERSONA_NAME}" for item in self.items)

    @property
    def persona_optional(self) -> bool:
        """The gentle-ai persona could be removed on request (hermes-odd persona active)."""
        return self.hermes_persona and any(
            item.label == f"{GENTLE_AI}:{PERSONA_NAME}" and not item.removes for item in self.items
        )

    @property
    def plan_id(self) -> str:
        """Digest of the current file and options: the tool's guard against a stale plan."""
        digest = hashlib.sha256(self.before.encode("utf-8"))
        digest.update(b"\0remove_persona=" + (b"1" if self.remove_persona else b"0"))
        return digest.hexdigest()[:12]


@dataclass
class CleanupResult:
    plan: CleanupPlan
    written: bool = False
    backup: Path | None = None
    rotated: list[Path] = field(default_factory=list)
    verified: bool = False
    error: str = ""


# -- strict marker scan -------------------------------------------------------


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan(text: str) -> tuple[list[Node], str]:
    """Every managed block in start order, strictly nested. ``(nodes, error)``."""
    entries: list[list] = []  # namespace, name, start, end, depth, parent
    stack: list[int] = []
    for count, match in enumerate(soul_mod.MARKER_RE.finditer(text), start=1):
        if count > MAX_MARKERS:
            return [], f"more than {MAX_MARKERS} managed markers"
        closing, namespace, name = match.group(1) == "/", match.group(2), match.group(3)
        if not closing:
            entries.append(
                [namespace, name, match.start(), -1, len(stack), stack[-1] if stack else None]
            )
            stack.append(len(entries) - 1)
            continue
        where = _line(text, match.start())
        if not stack:
            return [], f"a closing {namespace}:{name} marker at line {where} without its opener"
        top = entries[stack[-1]]
        if (top[0], top[1]) != (namespace, name):
            return [], (
                f"a closing {namespace}:{name} marker at line {where} that crosses "
                f"{top[0]}:{top[1]} opened at line {_line(text, top[2])}"
            )
        top[3] = match.end()
        stack.pop()
    if stack:
        top = entries[stack[-1]]
        return [], f"an unclosed {top[0]}:{top[1]} marker at line {_line(text, top[2])}"
    return [Node(*entry) for entry in entries], ""


def _descendants(nodes: list[Node], index: int) -> list[int]:
    found = []
    for i, node in enumerate(nodes):
        parent = node.parent
        while parent is not None:
            if parent == index:
                found.append(i)
                break
            parent = nodes[parent].parent
    return found


def _is_lifted(node: Node) -> bool:
    return (node.namespace, node.name) == (GENTLE_AI, LIFTED_NAME)


def _outermost_lifts(nodes: list[Node], index: int) -> list[int]:
    """``remote-authorization`` descendants of ``index`` not inside another one."""
    lifts = []
    for i in _descendants(nodes, index):
        if not _is_lifted(nodes[i]):
            continue
        parent = nodes[i].parent
        while parent is not None and parent != index and not _is_lifted(nodes[parent]):
            parent = nodes[parent].parent
        if parent == index:
            lifts.append(i)
    return lifts


def _skip_newlines(text: str, pos: int, count: int = 2) -> int:
    for _ in range(count):
        if text.startswith("\r\n", pos):
            pos += 2
        elif text.startswith("\n", pos):
            pos += 1
        else:
            break
    return pos


def user_text(text: str, nodes: list[Node]) -> str:
    """Every character outside top-level blocks, newlines dropped."""
    parts = []
    cursor = 0
    for node in nodes:
        if node.depth == 0:
            parts.append(text[cursor : node.start])
            cursor = node.end
    parts.append(text[cursor:])
    return "".join(parts).replace("\r", "").replace("\n", "")


def measure(text: str) -> int:
    """Characters Hermes counts (stripped, leading BOM dropped)."""
    return soul_mod.analyze_text(text, Path(sp.SOUL_FILE)).chars


# -- planning -----------------------------------------------------------------


def _classify(node: Node, hermes_persona: bool, remove_persona: bool) -> Item:
    item = Item(label=node.label, chars=node.size)
    if node.namespace == GENTLE_AI and node.name in RULES:
        item.action, item.skill = RULES[node.name]
    elif (node.namespace, node.name) == (GENTLE_AI, PERSONA_NAME):
        if remove_persona and hermes_persona:
            item.action = REMOVE
            item.note = "requested; the hermes-odd persona is active"
        elif hermes_persona:
            item.note = "optional removal: the hermes-odd persona is active"
    elif node.namespace == HERMES_ODD:
        item.note = "hermes-odd block"
    elif _is_lifted(node):
        item.note = "general safety rule"
    else:
        item.note = "not handled by the cleanup"
    return item


def plan_text(text: str, path: Path, *, remove_persona: bool = False) -> CleanupPlan:
    """Plan the cleanup of ``text`` (the whole file). Never writes."""
    plan = CleanupPlan(path=path, exists=True, before=text, after=text)
    plan.remove_persona = remove_persona
    nodes, error = scan(text)
    if error:
        plan.error = f"SOUL.md has {error}; fix it by hand, then retry (nothing was changed)"
        return plan
    plan.before_chars = plan.after_chars = measure(text)
    plan.user_chars = len(user_text(text, nodes))
    plan.hermes_persona = any((n.namespace, n.name) == (HERMES_ODD, PERSONA_NAME) for n in nodes)
    top = [(i, n) for i, n in enumerate(nodes) if n.depth == 0]
    if remove_persona and not plan.hermes_persona:
        plan.persona_note = (
            "The gentle-ai persona is kept: SOUL.md has no hermes-odd persona block "
            "(write one first with /odd_setup persona <id>)."
        )
    kept_lifts = {text[n.start : n.end] for _i, n in top if _is_lifted(n)}
    newline = "\r\n" if "\r\n" in text else "\n"

    out: list[str] = []
    cursor = 0
    for index, node in top:
        item = _classify(node, plan.hermes_persona, remove_persona)
        item.nested = [(nodes[c].label, nodes[c].size) for c in _descendants(nodes, index)]
        plan.items.append(item)
        if not item.removes:
            continue
        replacement = []
        for lift in _outermost_lifts(nodes, index):
            chunk = text[nodes[lift].start : nodes[lift].end]
            how = DROP if chunk in kept_lifts else LIFT
            item.lifted.append((nodes[lift].label, nodes[lift].size, how))
            if how == LIFT:
                kept_lifts.add(chunk)
                replacement.append(chunk)
        out.append(text[cursor : node.start])
        if replacement:
            out.append((newline * 2).join(replacement))
            cursor = node.end
        else:
            cursor = _skip_newlines(text, node.end)
    out.append(text[cursor:])
    after = "".join(out)
    if after != text:
        # Removing the last block must not leave blank lines at the end.
        core = after.rstrip("\r\n")
        after = core + text[len(text.rstrip("\r\n")) :] if core.strip("\ufeff") else ""
    check = verify(text, after, plan.items)
    if check:
        plan.error = f"internal check failed ({check}); SOUL.md left untouched"
        return plan
    plan.after = after
    plan.after_chars = measure(after)
    return plan


def expected_blocks(before: str, items: list[Item]) -> list[str]:
    """Top-level block bytes the cleaned text must hold, in order."""
    nodes, _ = scan(before)
    top = [(i, n) for i, n in enumerate(nodes) if n.depth == 0]
    expected = []
    for (index, node), item in zip(top, items, strict=True):
        if not item.removes:
            expected.append(before[node.start : node.end])
            continue
        lifts = _outermost_lifts(nodes, index)
        for lift, (_label, _chars, how) in zip(lifts, item.lifted, strict=True):
            if how == LIFT:
                expected.append(before[nodes[lift].start : nodes[lift].end])
    return expected


def verify(before: str, after: str, items: list[Item]) -> str:
    """Invariants between the original and the cleaned text ("" = hold)."""
    before_nodes, error = scan(before)
    if error:
        return error
    after_nodes, error = scan(after)
    if error:
        return f"the result would have {error}"
    actual = [after[n.start : n.end] for n in after_nodes if n.depth == 0]
    if actual != expected_blocks(before, items):
        return "kept blocks would not stay byte-identical and in order"
    removed = {item.label for item in items if item.removes}
    kept = {item.label for item in items if not item.removes}
    lifted = {label for item in items for label, _c, how in item.lifted if how == LIFT}
    for node in after_nodes:
        if node.depth == 0 and node.label in removed and node.label not in kept | lifted:
            return f"{node.label} would remain"
    if user_text(before, before_nodes) != user_text(after, after_nodes):
        return "text outside the blocks would change"
    return ""


def plan_cleanup(home: Path | None = None, *, remove_persona: bool = False) -> CleanupPlan:
    """Read ``<Hermes home>/SOUL.md`` and plan its cleanup. Reads only; never raises."""
    path = sp.soul_path(home)
    loaded = sp.read_soul_file(path)
    if loaded.error:
        return CleanupPlan(path=path, exists=loaded.exists, error=loaded.error)
    if not loaded.exists:
        return CleanupPlan(path=path, exists=False)
    try:
        plan = plan_text(loaded.text, path, remove_persona=remove_persona)
    except Exception as exc:  # noqa: BLE001 - never raise to the caller
        return CleanupPlan(path=path, exists=True, error=f"planning failed ({type(exc).__name__})")
    plan.mode = loaded.mode
    return plan


# -- applying and restoring ---------------------------------------------------


def _write(
    path: Path, before: str, after: str, mode: int, now: Callable[[], _dt.datetime]
) -> sp.Result:
    """Back up and write through the persona module's machinery."""
    target = sp.Plan(path=path, exists=True, action=sp.REPLACE, before=before, after=after)
    target.mode = mode
    return sp.apply_plan(target, now=now)


def _read_back(path: Path) -> str | None:
    loaded = sp.read_soul_file(path)
    return None if loaded.error or not loaded.exists else loaded.text


def apply_cleanup(
    plan: CleanupPlan,
    now: Callable[[], _dt.datetime] = lambda: _dt.datetime.now(_dt.UTC),
) -> CleanupResult:
    """Back up, write ``plan.after`` atomically, verify the written file. Never raises."""
    result = CleanupResult(plan=plan)
    if plan.error:
        result.error = plan.error
        return result
    if not plan.writes:
        return result
    try:
        current = _read_back(plan.path)
        if current != plan.before:
            result.error = "SOUL.md changed since the plan was made; run the plan again"
            return result
        written = _write(plan.path, plan.before, plan.after, plan.mode, now)
    except Exception as exc:  # noqa: BLE001
        result.error = f"SOUL.md could not be written ({type(exc).__name__}); it is unchanged"
        return result
    result.backup, result.rotated = written.backup, written.rotated
    if written.error:
        result.error = written.error
        return result
    result.written = True
    back = _read_back(plan.path)
    if back != plan.after:
        result.error = "post-write check failed: SOUL.md does not hold the planned text"
    else:
        check = verify(plan.before, back, plan.items)
        result.error = f"post-write check failed ({check})" if check else ""
    if result.error and result.backup is not None:
        result.error += f"; restore it with /odd_soul restore {result.backup.name}"
    result.verified = not result.error
    return result


@dataclass
class RestoreResult:
    path: Path
    chosen: Path | None = None
    written: bool = False
    backup: Path | None = None
    error: str = ""


def backups(home: Path | None = None) -> list[Path]:
    """hermes-odd backups of SOUL.md, newest first."""
    return list(reversed(sp.backup_paths(sp.soul_path(home))))


def resolve_backup(choice: str, home: Path | None = None) -> Path | None:
    """A backup by list number (1 = newest) or exact file name; never a path."""
    found = backups(home)
    value = (choice or "").strip()
    if value.isdigit():
        number = int(value)
        return found[number - 1] if 1 <= number <= len(found) else None
    return next((p for p in found if p.name == value), None)


def restore_backup(
    choice: str,
    home: Path | None = None,
    now: Callable[[], _dt.datetime] = lambda: _dt.datetime.now(_dt.UTC),
) -> RestoreResult:
    """Restore a chosen backup; the current SOUL.md is backed up first. Never raises."""
    path = sp.soul_path(home)
    result = RestoreResult(path=path)
    chosen = resolve_backup(choice, home)
    if chosen is None:
        result.error = f"no backup {choice!r}; /odd_soul restore lists them"
        return result
    result.chosen = chosen
    try:
        source = sp.read_soul_file(chosen)
        if source.error or not source.exists:
            result.error = f"the backup cannot be used ({source.error or 'missing'})"
            return result
        current = sp.read_soul_file(path)
        if current.error:
            result.error = current.error
            return result
        if current.exists and current.text == source.text:
            result.error = "SOUL.md already matches that backup; nothing to restore"
            return result
        mode = current.mode if current.exists else source.mode
        if current.exists:
            written = _write(path, current.text, source.text, mode, now)
        else:
            target = sp.Plan(path=path, exists=False, action=sp.INSERT, after=source.text)
            target.mode = mode
            written = sp.apply_plan(target, now=now)
    except Exception as exc:  # noqa: BLE001
        result.error = f"restore failed ({type(exc).__name__}); SOUL.md is unchanged"
        return result
    result.backup = written.backup
    if written.error:
        result.error = written.error
        return result
    result.written = True
    if _read_back(path) != source.text:
        result.error = "post-write check failed: SOUL.md does not match the backup"
    return result


# -- truncation impact --------------------------------------------------------


@dataclass(frozen=True)
class Impact:
    label: str  # "128k", "1M", or "<model> 1M (cache)"
    cap: int
    before_fits: bool
    after_fits: bool
    before_lost: tuple[str, ...]
    after_lost: tuple[str, ...]


def _ctx_label(tokens: int) -> str:
    return f"{tokens // 1_000_000}M" if tokens % 1_000_000 == 0 else f"{tokens // 1000}k"


def _lost(text: str, cap: int) -> tuple[bool, tuple[str, ...]]:
    report = soul_mod.analyze_text(text, Path(sp.SOUL_FILE))
    if report.chars <= cap:
        return True, ()
    lost = soul_mod.dropped_blocks(report.blocks, report.chars, cap)
    return False, tuple(f"{b.label}{'' if how == 'dropped' else ' (partly)'}" for b, how in lost)


def impacts(plan: CleanupPlan, context: soul_mod.ModelContext | None = None) -> list[Impact]:
    """Truncation before/after for 128k, 200k, 1M and the configured model."""
    rows = []
    cells: list[tuple[str, int]] = [
        (_ctx_label(t), soul_mod.truncation_cap(t)) for t in soul_mod.REFERENCE_CONTEXTS
    ]
    if context is not None and (context.context_length or context.pinned_cap):
        if context.pinned_cap:
            label = "configured (context_file_max_chars)"
        else:
            label = (
                f"configured {context.model or 'model'} "
                f"{_ctx_label(context.context_length)} ({context.source})"
            )
        cells.append((label, soul_mod.truncation_cap(context.context_length, context.pinned_cap)))
    for label, cap in cells:
        before_fits, before_lost = _lost(plan.before, cap)
        after_fits, after_lost = _lost(plan.after, cap)
        rows.append(Impact(label, cap, before_fits, after_fits, before_lost, after_lost))
    return rows


__all__ = [
    "BINARY_WARNING",
    "CleanupPlan",
    "CleanupResult",
    "Impact",
    "Item",
    "RULES",
    "apply_cleanup",
    "backups",
    "impacts",
    "measure",
    "plan_cleanup",
    "plan_text",
    "resolve_backup",
    "restore_backup",
    "scan",
    "verify",
]
