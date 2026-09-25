"""Read ODD feature documents (``odd/tasks/<feature>.md``) for ``/odd_tasks``.

A feature document is the durable authority for one ODD feature (see
``skills/odd-feature-tracking``). This module turns one into a small,
read-only summary: title, task checkboxes, counts, next step and mtime.

The parser is deliberately forgiving and never executes or evaluates
anything; it only matches lines:

* **Title**: the first ``# `` heading (``# Feature: x`` -> ``x``); else the
  file stem.
* **Tasks**: top-level checkboxes (``- [ ]`` / ``- [x]``, also ``*``/``+``
  bullets and ``[X]``) under the ``## Tasks`` heading, until the next level-1
  or level-2 heading. Without a ``## Tasks`` heading every top-level checkbox
  in the document counts. Items indented deeper than the first item are
  nested and ignored; indented non-checkbox lines are continuation lines and
  ignored (the task title is its first line). Lines inside fenced code blocks
  are ignored.
* **Task id**: the first token when it looks like an id (``T1``, ``T2b``,
  ``10``, ``**T3**``); otherwise the id is empty and the whole line is the
  title.
* **Next step**: the first paragraph under ``## Next step`` (or
  ``## Next steps``).

Limits: at most :data:`MAX_FILE_BYTES` bytes are read per file (the rest is
ignored and the summary is marked truncated) and at most
:data:`MAX_FILES` documents per project, newest first. Symlinks are never
followed. Reading never raises: an unreadable file yields a summary with
``error`` set.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

TASKS_DIR = Path("odd") / "tasks"
MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 50
TITLE_MAX_CHARS = 160
NEXT_STEP_MAX_CHARS = 400
TASK_ID_MAX_CHARS = 12

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_CHECKBOX_RE = re.compile(r"^([ \t]*)[-*+][ \t]+\[([ xX])\][ \t]+(.*?)\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_TASK_ID_RE = re.compile(r"^[A-Za-z]{0,6}\d+[A-Za-z0-9._-]*$")
_FEATURE_PREFIX_RE = re.compile(r"^feature\s*:\s*", re.IGNORECASE)


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    done: bool


@dataclass
class FeatureDoc:
    """Summary of one feature document; ``error`` is set when unreadable."""

    feature: str
    path: Path
    title: str = ""
    tasks: list[Task] = field(default_factory=list)
    next_step: str = ""
    mtime: float | None = None
    truncated: bool = False
    has_tasks_heading: bool = False
    error: str = ""

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def done(self) -> int:
        return sum(1 for task in self.tasks if task.done)

    @property
    def next_task(self) -> Task | None:
        """The first unchecked task (the one in progress or up next)."""
        return next((task for task in self.tasks if not task.done), None)


def _clip(text: str, limit: int) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _indent_width(prefix: str) -> int:
    return len(prefix.expandtabs(4))


def split_task_id(text: str) -> tuple[str, str]:
    """``"T2b Upstream matrix"`` -> ``("T2b", "Upstream matrix")``."""
    head, _, rest = text.strip().partition(" ")
    token = head.strip("*`_").rstrip(":.)")
    if token and len(token) <= TASK_ID_MAX_CHARS and _TASK_ID_RE.match(token):
        return token, rest.strip()
    return "", text.strip()


def parse_feature_text(text: str, feature: str, path: Path | None = None) -> FeatureDoc:
    """Parse the text of a feature document. Never raises on content."""
    doc = FeatureDoc(feature=feature, path=path or Path(f"{feature}.md"))
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    fence: str | None = None
    section = ""  # lowercased level-2 heading text, "" before any
    in_tasks_heading = False
    tasks_in_section: list[Task] = []
    tasks_anywhere: list[Task] = []
    base_section: int | None = None
    base_anywhere: int | None = None
    next_lines: list[str] = []
    next_done = False

    for line in lines:
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            if (
                fence_match
                and fence_match.group(1)[0] == fence[0]
                and len(fence_match.group(1)) >= len(fence)
            ):
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            if section.startswith("next step") and next_lines:
                next_done = True
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            name = heading.group(2).strip()
            if level == 1 and not doc.title:
                doc.title = _clip(_FEATURE_PREFIX_RE.sub("", name), TITLE_MAX_CHARS)
            if level <= 2:
                section = name.lower() if level == 2 else ""
                in_tasks_heading = section == "tasks" or section.startswith("tasks ")
                if in_tasks_heading:
                    doc.has_tasks_heading = True
            if section.startswith("next step") and next_lines:
                next_done = True
            continue

        checkbox = _CHECKBOX_RE.match(line)
        if checkbox:
            indent = _indent_width(checkbox.group(1))
            task_id, title = split_task_id(checkbox.group(3))
            task = Task(
                id=task_id,
                title=_clip(title, TITLE_MAX_CHARS),
                done=checkbox.group(2) in "xX",
            )
            if base_anywhere is None:
                base_anywhere = indent
            if indent <= base_anywhere:
                tasks_anywhere.append(task)
            if in_tasks_heading:
                if base_section is None:
                    base_section = indent
                if indent <= base_section:
                    tasks_in_section.append(task)
            continue

        if section in ("next step", "next steps") and not next_done:
            if line.strip():
                next_lines.append(line.strip())
            elif next_lines:
                next_done = True

    doc.tasks = tasks_in_section if doc.has_tasks_heading else tasks_anywhere
    doc.next_step = _clip(" ".join(next_lines), NEXT_STEP_MAX_CHARS)
    if not doc.title:
        doc.title = feature
    return doc


def read_feature_doc(path: Path, max_bytes: int = MAX_FILE_BYTES) -> FeatureDoc:
    """Read and parse one feature document. Never raises."""
    feature = path.stem
    try:
        stat = path.lstat()
        with open(path, "rb") as handle:
            raw = handle.read(max_bytes + 1)
    except OSError as exc:
        return FeatureDoc(feature=feature, path=path, title=feature, error=type(exc).__name__)
    truncated = len(raw) > max_bytes
    text = raw[:max_bytes].decode("utf-8", errors="replace")
    try:
        doc = parse_feature_text(text, feature, path)
    except Exception as exc:  # noqa: BLE001 - defensive: parsing must never raise
        return FeatureDoc(feature=feature, path=path, title=feature, error=type(exc).__name__)
    doc.mtime = stat.st_mtime
    doc.truncated = truncated
    return doc


def tasks_dir(project_root: Path) -> Path:
    return project_root / TASKS_DIR


def has_tasks_dir(project_root: Path) -> bool:
    try:
        return tasks_dir(project_root).is_dir()
    except OSError:
        return False


def list_feature_docs(
    project_root: Path, max_files: int = MAX_FILES, max_bytes: int = MAX_FILE_BYTES
) -> tuple[list[FeatureDoc], int]:
    """Return ``(docs newest first, number of documents left out)``.

    Only regular ``*.md`` files directly in ``odd/tasks/`` are read; symlinks
    and subdirectories are skipped. Never raises.
    """
    directory = tasks_dir(project_root)
    entries: list[tuple[float, Path]] = []
    try:
        with os.scandir(directory) as scan:
            for entry in scan:
                try:
                    if not entry.name.endswith(".md") or entry.name.startswith("."):
                        continue
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        continue
                    mtime = entry.stat(follow_symlinks=False).st_mtime
                except OSError:
                    mtime = 0.0
                entries.append((mtime, Path(entry.path)))
    except OSError:
        return [], 0
    entries.sort(key=lambda item: (-item[0], item[1].name))
    docs = [read_feature_doc(path, max_bytes) for _, path in entries[:max_files]]
    return docs, max(0, len(entries) - max_files)
