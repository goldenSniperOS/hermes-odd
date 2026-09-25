"""``/odd_tasks``: plain-text view of ODD feature documents (Pi todo card).

Concept port of gentle-shell's todo card (``extensions/gentle-todo.ts``) and
the ODD feature document view: gentle-pi projects the feature tasks into a
Pi widget; Hermes has no widget a plugin command can drive on every gateway,
so this command reads ``odd/tasks/*.md`` directly and answers with plain
text. No upstream code or text is copied. The interactive ``todo`` tool is
not ported: Hermes' native ``todo`` is used instead (see
``skills/odd-feature-tracking``).

Projects come from :func:`hermes_odd.projects.resolve_projects`. Output uses
no Markdown and stays under :data:`OUTPUT_MAX_CHARS` so a Telegram reply
never needs splitting; the CLI and TUI show the same text.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..feature_docs import MAX_FILES, FeatureDoc, list_feature_docs
from ..projects import Project, ProjectStore, resolve_projects
from .registry import CommandSpec

OUTPUT_MAX_CHARS = 3500
MORE_RESERVE = 60
BAR_CELLS = 10
LINE_CHARS = 80
DETAIL_TASK_CHARS = 110

EMPTY_TEXT = (
    "No ODD feature documents found.\n"
    "ODD creates odd/tasks/<feature>.md in the project for substantial work "
    "(two or more implementation steps). Documents show up here once a Hermes "
    "session has run in that project, or when Hermes runs from inside it."
)


@dataclass
class ProjectDocs:
    project: Project
    docs: list[FeatureDoc]
    skipped: int = 0

    @property
    def newest(self) -> float:
        return max((d.mtime or 0.0 for d in self.docs), default=0.0)


def progress_bar(done: int, total: int, cells: int = BAR_CELLS) -> str:
    """``progress_bar(3, 5, 5)`` -> ``"▰▰▰▱▱ 3/5"``."""
    if total <= 0:
        return "no tasks"
    filled = min(cells, max(0, round(cells * done / total)))
    if done < total and filled == cells:
        filled = cells - 1  # never show a full bar for unfinished work
    if done > 0 and filled == 0:
        filled = 1
    return "▰" * filled + "▱" * (cells - filled) + f" {done}/{total}"


def format_age(mtime: float | None, now: float) -> str:
    if mtime is None:
        return "unknown"
    delta = max(0.0, now - mtime)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 30 * 86400:
        return f"{int(delta // 86400)}d ago"
    return time.strftime("%Y-%m-%d", time.localtime(mtime))


def path_tail(path: Path, parts: int = 2) -> str:
    """Last ``parts`` components, so full home paths are not sent to chats."""
    pieces = [p for p in path.parts if p not in ("/", "\\")]
    if len(pieces) <= parts:
        return str(path)
    return "…/" + "/".join(pieces[-parts:])


def _one_line(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _task_label(task) -> str:
    return f"{task.id} {task.title}".strip() if task.id else task.title


def _feature_block(doc: FeatureDoc, now: float) -> str:
    if doc.error:
        return f"⚠ {doc.feature}: unreadable ({doc.error})"
    head = f"{progress_bar(doc.done, doc.total)} {doc.feature} · {format_age(doc.mtime, now)}"
    nxt = doc.next_task
    if doc.total and nxt is None:
        tail = "  all tasks done"
    elif nxt is not None:
        tail = "  next: " + _one_line(_task_label(nxt), LINE_CHARS - 8)
    else:
        tail = "  (no task checkboxes)"
    return f"{head}\n{tail}"


def _fit(lines: list[str], blocks: list[str], footer: str, hidden: int = 0) -> str:
    text = "\n".join(lines)
    reserve = MORE_RESERVE + (len(footer) + 2 if footer else 0)
    shown = 0
    for block in blocks:
        candidate = f"{text}\n{block}" if text else block
        if len(candidate) + reserve > OUTPUT_MAX_CHARS:
            break
        text = candidate
        shown += 1
    more = len(blocks) - shown + hidden
    if more:
        text += f"\n… {more} more"
    if footer:
        text += f"\n\n{footer}"
    return text


def collect(
    store: ProjectStore | None,
    cwd_candidates: list[Path] | None = None,
    max_files: int = MAX_FILES,
) -> list[ProjectDocs]:
    """Read every resolved project's feature docs, newest project first."""
    result = []
    for project in resolve_projects(store, cwd_candidates):
        docs, skipped = list_feature_docs(project.root, max_files=max_files)
        if docs or skipped:
            result.append(ProjectDocs(project, docs, skipped))
    result.sort(key=lambda p: p.newest, reverse=True)
    return result


def render_overview(projects: list[ProjectDocs], now: float) -> str:
    if not projects:
        return EMPTY_TEXT
    features = sum(len(p.docs) + p.skipped for p in projects)
    noun_p = "project" if len(projects) == 1 else "projects"
    noun_f = "feature" if features == 1 else "features"
    header = [f"ODD features: {len(projects)} {noun_p} · {features} {noun_f}"]
    blocks: list[str] = []
    for entry in projects:
        blocks.append(f"\n{entry.project.name} ({path_tail(entry.project.root)})")
        for doc in entry.docs:
            blocks.append(_feature_block(doc, now))
        if entry.skipped:
            blocks.append(f"  … {entry.skipped} older documents not read (limit {MAX_FILES})")
    return _fit(header, blocks, "Details: /odd_tasks [feature] · filter: /odd_tasks [project]")


def render_detail(entry: ProjectDocs, doc: FeatureDoc, now: float) -> str:
    rel = f"{path_tail(entry.project.root)}/odd/tasks/{doc.path.name}"
    if doc.error:
        return f"⚠ {doc.feature}: unreadable ({doc.error})\nfile: {rel}"
    lines = [
        doc.title,
        f"feature: {doc.feature} · project: {entry.project.name}",
        f"{progress_bar(doc.done, doc.total)} done · updated {format_age(doc.mtime, now)}",
        "",
    ]
    nxt = doc.next_task
    task_lines = []
    for task in doc.tasks:
        mark = "✓" if task.done else "○"
        suffix = "  ← next" if task is nxt else ""
        task_lines.append(f"{mark} {_one_line(_task_label(task), DETAIL_TASK_CHARS)}{suffix}")
    if not task_lines:
        task_lines.append("(no task checkboxes found)")
    footer_lines = []
    if doc.next_step:
        footer_lines.append(f"Next step: {doc.next_step}")
    if doc.truncated:
        footer_lines.append("(document larger than 256 KB; only the start was read)")
    footer_lines.append(f"file: {rel}")
    return _fit(lines, task_lines, "\n".join(footer_lines))


def _match(items: list[tuple[ProjectDocs, FeatureDoc]], needle: str, exact: bool):
    if exact:
        return [(p, d) for p, d in items if d.feature.lower() == needle]
    return [(p, d) for p, d in items if d.feature.lower().startswith(needle)]


def render_lookup(projects: list[ProjectDocs], query: str, now: float) -> str:
    shown = _one_line(query, 60)
    needle = query.strip().lower()
    items = [(p, d) for p in projects for d in p.docs]
    project_filter = ""
    if "/" in needle:
        project_filter, _, needle = needle.rpartition("/")
        items = [(p, d) for p, d in items if p.project.name.lower() == project_filter]
        if not needle:
            scoped = [p for p in projects if p.project.name.lower() == project_filter]
            if scoped:
                return render_overview(scoped, now)
    for exact in (True, False):
        matches = _match(items, needle, exact)
        if len(matches) == 1:
            return render_detail(matches[0][0], matches[0][1], now)
        if len(matches) > 1:
            names = ", ".join(f"{p.project.name}/{d.feature}" for p, d in matches[:10])
            more = f" and {len(matches) - 10} more" if len(matches) > 10 else ""
            return (
                f"'{shown}' is ambiguous: {len(matches)} features match ({names}{more}). "
                "Use more characters or project/feature."
            )
        if not project_filter:
            by_project = [
                p
                for p in projects
                if (p.project.name.lower() == needle)
                or (not exact and p.project.name.lower().startswith(needle))
            ]
            if len(by_project) == 1 or (by_project and exact):
                return render_overview(by_project, now)
            if len(by_project) > 1:
                names = ", ".join(p.project.name for p in by_project[:10])
                return f"'{shown}' is ambiguous: {len(by_project)} projects match ({names})."
    if not projects:
        return EMPTY_TEXT
    available = ", ".join(d.feature for _, d in items[:10]) or "none"
    return (
        f"No feature or project matches '{shown}'. Features: {available}. Run /odd_tasks to list."
    )


def make_odd_tasks(
    store: ProjectStore | None,
    clock: Callable[[], float] = time.time,
    cwd_candidates: Callable[[], list[Path]] | None = None,
) -> CommandSpec:
    def handler(raw_args: str) -> str:
        args = (raw_args or "").strip()
        candidates = cwd_candidates() if cwd_candidates is not None else None
        projects = collect(store, candidates)
        now = clock()
        if not args:
            return render_overview(projects, now)
        return render_lookup(projects, args.split()[0], now)

    return CommandSpec(
        name="odd_tasks",
        description="Show ODD feature documents and task progress",
        handler=handler,
        args_hint="[feature|project]",
    )
