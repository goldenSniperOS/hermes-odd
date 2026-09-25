"""``/odd_changes``: plain-text view of files the agent changed (Pi ``gentle:changes``).

Concept port of gentle-shell's Gentle Changes: files captured from
successful ``write_file`` / ``patch`` calls of the main agent and its
subagents, grouped by project with line counts and attribution. The Pi
two-pane diff viewer is not ported (Pi TUI; hermes-odd stores no content).
Output uses no Markdown and stays under :data:`OUTPUT_MAX_CHARS`, so a
Telegram reply never needs splitting; the CLI and TUI show the same text.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..changes import MAIN, MAX_TIMELINE, ChangeStore, NumstatResult, git_numstat
from .agents import short_id
from .registry import CommandSpec
from .tasks import format_age, path_tail

OUTPUT_MAX_CHARS = 3500
MORE_RESERVE = 60
DEFAULT_WINDOW = 24 * 3600
ALL_WINDOW = 7 * 24 * 3600
LINE_PATH_CHARS = 70
GOAL_CHARS = 120

SCOPE_NOTE = (
    "Captured from successful write_file and patch calls (main agent and "
    "subagents). Terminal/shell edits and other tools are not tracked, so a "
    "missing file does not mean a clean tree. −? = full overwrite, removed "
    "lines unknown."
)
LIST_HINT = "Details: /odd_changes [file] · 7 days: /odd_changes all · forget: /odd_changes clear"


def _one_line(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _removed(count: int, unknown: bool) -> str:
    if unknown:
        return "−?" if count == 0 else f"−≥{count}"
    return f"−{count}"


def counts(added: Any, removed: Any, unknown: bool = False) -> str:
    return f"+{int(added or 0)} {_removed(int(removed or 0), unknown)}"


def display_root(root: str) -> str:
    """Root as ``…/parent/name`` (or ``~``), never a full home path."""
    path = Path(root)
    home = Path(os.path.expanduser("~"))
    if path == home:
        return "~"
    tail = path_tail(path)
    if tail == str(path) and len(path.parts) > 1:
        return "…/" + path.name if path.name else tail
    return tail


def project_name(entry: dict[str, Any]) -> str:
    root = str(entry.get("root") or "")
    return Path(root).name or root or "?"


def attribution_label(item: dict[str, Any], with_role: bool = False) -> str:
    ident = str(item.get("id") or MAIN)
    if ident == MAIN:
        return MAIN
    label = f"sa-{short_id(ident)}" if ident.startswith("sa-") else ident
    role = item.get("role")
    return f"{label} {role}" if with_role and role else label


def _by(entry: dict[str, Any]) -> str:
    items = [a for a in entry.get("by") or [] if isinstance(a, dict)]
    items.sort(key=lambda a: a.get("last_at") or 0, reverse=True)
    return ", ".join(attribution_label(a) for a in items) or MAIN


def _edits(n: Any) -> str:
    n = int(n or 0)
    return f"{n} edit" if n == 1 else f"{n} edits"


def file_line(entry: dict[str, Any], now: float) -> str:
    rel = _one_line(entry.get("rel") or entry.get("path"), LINE_PATH_CHARS)
    stats = counts(entry.get("added"), entry.get("removed"), bool(entry.get("removed_unknown")))
    return (
        f"{stats}  {rel}  ({_edits(entry.get('ops'))} · by {_by(entry)} · "
        f"{format_age(entry.get('last_at'), now)})"
    )


def _group(files: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in files:  # already newest first
        groups.setdefault(str(entry.get("root") or ""), []).append(entry)
    return list(groups.items())


def _totals(files: list[dict[str, Any]]) -> str:
    added = sum(int(f.get("added") or 0) for f in files)
    removed = sum(int(f.get("removed") or 0) for f in files)
    unknown = any(f.get("removed_unknown") for f in files)
    noun = "file" if len(files) == 1 else "files"
    return f"{len(files)} {noun} · {counts(added, removed, unknown)}"


def _window_label(window: float) -> str:
    return "last 7 days" if window >= ALL_WINDOW else "last 24 h"


def empty_text(window: float) -> str:
    return f"No file changes recorded ({_window_label(window)}).\n{SCOPE_NOTE}"


def render_list(files: list[dict[str, Any]], now: float, window: float = DEFAULT_WINDOW) -> str:
    recent = [f for f in files if now - (f.get("last_at") or 0) <= window]
    if not recent:
        return empty_text(window)
    groups = _group(recent)
    noun = "project" if len(groups) == 1 else "projects"
    text = f"Changes ({_window_label(window)}): {_totals(recent)} · {len(groups)} {noun}"
    footer = f"{SCOPE_NOTE}\n{LIST_HINT}"
    reserve = MORE_RESERVE + len(footer) + 2
    shown = 0
    stop = False
    for root, entries in groups:
        header = f"\n{project_name(entries[0])} ({display_root(root)}) · {_totals(entries)}"
        if len(text) + len(header) + reserve > OUTPUT_MAX_CHARS:
            break
        text += "\n" + header
        for entry in entries:
            line = file_line(entry, now)
            if len(text) + len(line) + 1 + reserve > OUTPUT_MAX_CHARS:
                stop = True
                break
            text += "\n" + line
            shown += 1
        if stop:
            break
    more = len(recent) - shown
    if more:
        text += f"\n… {more} more" + ("" if window >= ALL_WINDOW else " (/odd_changes all)")
    return f"{text}\n\n{footer}"


def _clock(ts: Any, now: float) -> str:
    if not isinstance(ts, (int, float)):
        return "--:--:--"
    fmt = "%H:%M:%S" if now - ts < 20 * 3600 else "%m-%d %H:%M"
    return time.strftime(fmt, time.localtime(ts))


def git_line(result: NumstatResult) -> str:
    return {
        "ok": f"git (uncommitted, not staged): +{result.added} −{result.removed}",
        "clean": (
            "git: no unstaged changes for this file (it may be committed, staged or untracked)"
        ),
        "binary": "git: binary change (no line counts)",
        "no_git": "git: not available",
        "not_repo": "git: not inside a git repository",
        "timeout": "git: timed out after 2 s",
    }.get(result.state, "git: diff --numstat failed")


def render_detail(
    entry: dict[str, Any],
    now: float,
    store: ChangeStore | None = None,
    numstat: Callable[[str, str, bool], NumstatResult] = git_numstat,
) -> str:
    stats = counts(entry.get("added"), entry.get("removed"), bool(entry.get("removed_unknown")))
    lines = [
        _one_line(entry.get("rel") or entry.get("path"), 200),
        f"project: {project_name(entry)} ({display_root(str(entry.get('root') or ''))})",
        f"captured: {_edits(entry.get('ops'))} · {stats}"
        f" · first {_clock(entry.get('first_at'), now)}"
        f" · last {format_age(entry.get('last_at'), now)}",
    ]
    items = [a for a in entry.get("by") or [] if isinstance(a, dict)]
    items.sort(key=lambda a: a.get("last_at") or 0, reverse=True)
    lines.append(
        "by: " + ", ".join(f"{attribution_label(a, True)} ({_edits(a.get('ops'))})" for a in items)
    )
    for item in items:
        record = store.agent(str(item.get("id") or "")) if store is not None else None
        if record and record.get("goal"):
            label = attribution_label(item)
            lines.append(f"  {label} goal: {_one_line(record['goal'], GOAL_CHARS)}")
    session = _one_line(entry.get("session_id"), 60) or "-"
    lines.append(f"platform: {entry.get('platform') or 'unknown'} · session: {session}")
    timeline = [e for e in entry.get("timeline") or [] if isinstance(e, dict)]
    if timeline:
        lines.append(f"timeline (last {MAX_TIMELINE}):")
        for item in timeline[-MAX_TIMELINE:]:
            removed = item.get("removed")
            lines.append(
                f"  {_clock(item.get('at'), now)} {item.get('tool')} "
                f"{counts(item.get('added'), removed or 0, removed is None)} "
                f"{attribution_label({'id': item.get('by')})}"
            )
    lines.append(
        git_line(
            numstat(
                str(entry.get("root") or ""),
                str(entry.get("rel") or ""),
                bool(entry.get("in_git")),
            )
        )
    )
    lines.append("")
    lines.append("Counts come from captured tool calls; terminal/shell edits are not included.")
    text = "\n".join(lines)
    if len(text) > OUTPUT_MAX_CHARS:
        text = text[: OUTPUT_MAX_CHARS - 40].rstrip() + "\n… truncated"
    return text


def _key(entry: dict[str, Any]) -> str:
    return f"{project_name(entry)}/{entry.get('rel') or ''}".lower()


def render_lookup(
    store: ChangeStore,
    files: list[dict[str, Any]],
    query: str,
    now: float,
    numstat: Callable[[str, str, bool], NumstatResult] = git_numstat,
) -> str:
    shown = _one_line(query, 60)
    needle = query.strip().lower()
    if not files:
        return empty_text(ALL_WINDOW)

    def rel(entry: dict[str, Any]) -> str:
        return str(entry.get("rel") or "").lower()

    exact = [
        f
        for f in files
        if needle in (rel(f), _key(f), os.path.basename(rel(f)), str(f.get("path")).lower())
    ]
    if len(exact) == 1:
        return render_detail(exact[0], now, store, numstat)
    projects = [f for f in files if project_name(f).lower() == needle]
    if not exact and projects:
        return render_list(projects, now, ALL_WINDOW)
    candidates = exact or [f for f in files if rel(f).startswith(needle)]
    if not candidates and "/" not in needle:
        by_project = [f for f in files if project_name(f).lower().startswith(needle)]
        names = {project_name(f) for f in by_project}
        if len(names) == 1:
            return render_list(by_project, now, ALL_WINDOW)
        if len(names) > 1:
            return (
                f"'{shown}' is ambiguous: {len(names)} projects match "
                f"({', '.join(sorted(names)[:10])})."
            )
    candidates = candidates or [f for f in files if needle in _key(f)]
    if len(candidates) == 1:
        return render_detail(candidates[0], now, store, numstat)
    if len(candidates) > 1:
        names = ", ".join(f"{project_name(f)}/{f.get('rel')}" for f in candidates[:10])
        more = f" and {len(candidates) - 10} more" if len(candidates) > 10 else ""
        return (
            f"'{shown}' is ambiguous: {len(candidates)} files match ({names}{more}). "
            "Use more of the path or project/path."
        )
    return (
        f"No recorded change matches '{shown}'. Run /odd_changes all to list the "
        "last 7 days (changes are kept for 7 days)."
    )


def make_odd_changes(
    store: ChangeStore,
    numstat: Callable[[str, str, bool], NumstatResult] = git_numstat,
) -> CommandSpec:
    def handler(raw_args: str) -> str:
        args = (raw_args or "").strip()
        words = args.split()
        head = words[0].lower() if words else ""
        if head == "clear":
            cleared = store.clear()
            if not cleared:
                return "No recorded changes to clear."
            noun = "file" if cleared == 1 else "files"
            return f"Cleared {cleared} recorded {noun}. Files on disk are untouched."
        files = store.files()
        now = store.now()
        if not words:
            return render_list(files, now, DEFAULT_WINDOW)
        if head == "all":
            return render_list(files, now, ALL_WINDOW)
        return render_lookup(store, files, words[0], now, numstat)

    return CommandSpec(
        name="odd_changes",
        description="Show which files the agent and its subagents changed",
        handler=handler,
        args_hint="[file|project|all|clear]",
        group="Viewers",
    )
