"""Known ODD projects for ``/odd_tasks``.

Hermes command handlers receive only ``raw_args``: no session, no cwd. So
``/odd_tasks`` combines two sources of project roots (see ``docs/design.md``,
"Project resolution"):

1. **Known projects**, recorded when Hermes renders the ``hermes-odd-workflow``
   prompt section. Its callable receives ``session_info["cwd"]``
   (``agent/system_prompt.py`` ``_plugin_session_info``: the session cwd
   override, else ``TERMINAL_CWD``, else empty). An empty value falls back
   to ``os.getcwd()`` of the rendering process, which is the directory
   Hermes itself uses for context files in that case. The git top-level of
   that directory (nearest ancestor holding ``.git``, else the directory
   itself) is stored in ``ctx.state`` with the platform and time, most
   recent first, at most :data:`MAX_PROJECTS`.
2. **The command process's own directory**: ``TERMINAL_CWD`` (the CLI
   exports its launch directory; the gateway bridges ``terminal.cwd``) and
   ``os.getcwd()``, each mapped to its git top-level.

Candidates are deduplicated by resolved path and only those containing
``odd/tasks/`` are shown. Recording never raises: a failing recorder must not
make Hermes skip the prompt section (a raising section callable is skipped).
"""

from __future__ import annotations

import copy
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import MemoryBackend
from .feature_docs import has_tasks_dir

logger = logging.getLogger("hermes_odd")

SCHEMA = "hermes-odd.projects/v1"
STATE_KEY = "projects.v1"
MAX_PROJECTS = 10
MAX_PARENT_WALK = 64
PLATFORM_MAX_CHARS = 32
PATH_MAX_CHARS = 4096


@dataclass(frozen=True)
class Project:
    root: Path
    platform: str = ""
    last_seen: float | None = None
    source: str = "known"  # "known" | "cwd"

    @property
    def name(self) -> str:
        return self.root.name or str(self.root)


def git_root(start: Path | str) -> Path | None:
    """Return the nearest ancestor of ``start`` holding ``.git``, else ``start``.

    Pure filesystem walk (no subprocess). ``None`` when ``start`` is not an
    existing directory.
    """
    try:
        path = Path(start).expanduser()
        if not path.is_absolute() or not path.is_dir():
            return None
        path = path.resolve()
        current = path
        for _ in range(MAX_PARENT_WALK):
            if (current / ".git").exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        return path
    except (OSError, RuntimeError, ValueError):
        return None


def process_cwd_candidates(environ: Mapping[str, str] | None = None) -> list[Path]:
    """Directories the command process itself points at, as git roots."""
    env = os.environ if environ is None else environ
    raw: list[str] = []
    terminal_cwd = str(env.get("TERMINAL_CWD", "") or "").strip()
    if terminal_cwd:
        raw.append(terminal_cwd)
    try:
        raw.append(os.getcwd())
    except OSError:
        pass
    roots: list[Path] = []
    for item in raw:
        root = git_root(item)
        if root is not None and root not in roots:
            roots.append(root)
    return roots


class ProjectStore:
    """Bounded most-recent-first list of project roots seen by the section."""

    def __init__(self, backend: Any | None = None, clock: Callable[[], float] = time.time):
        self._backend = backend if backend is not None else MemoryBackend()
        self._fallback = MemoryBackend()
        self._using_fallback = False
        self._clock = clock
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        doc: Any = None
        if not self._using_fallback:
            try:
                doc = self._backend.get(STATE_KEY, None)
            except Exception as exc:  # noqa: BLE001 - fall back, never raise
                self._switch_to_fallback(exc)
        if self._using_fallback:
            doc = self._fallback.get(STATE_KEY, None)
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return []
        entries = doc.get("projects")
        if not isinstance(entries, list):
            return []
        valid = []
        for entry in entries:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("root"), str)
                and 0 < len(entry["root"]) <= PATH_MAX_CHARS
                and os.path.isabs(entry["root"])
            ):
                valid.append(entry)
        return valid[:MAX_PROJECTS]

    def _save(self, entries: list[dict[str, Any]]) -> None:
        doc = {"schema": SCHEMA, "projects": entries[:MAX_PROJECTS]}
        if not self._using_fallback:
            try:
                self._backend.set(STATE_KEY, doc)
                return
            except Exception as exc:  # noqa: BLE001 - fall back, never raise
                self._switch_to_fallback(exc)
        self._fallback.set(STATE_KEY, copy.deepcopy(doc))

    def _switch_to_fallback(self, exc: Exception) -> None:
        if not self._using_fallback:
            logger.warning("hermes-odd: project state unavailable (%s); using memory", exc)
        self._using_fallback = True

    def record(self, cwd: Any, platform: Any = "") -> Path | None:
        """Record the git root of ``cwd``; return it. Never raises."""
        try:
            raw = cwd.strip() if isinstance(cwd, str) else ""
            if not raw:
                raw = os.getcwd()
            root = git_root(raw)
            if root is None:
                return None
            label = platform.strip()[:PLATFORM_MAX_CHARS] if isinstance(platform, str) else ""
            with self._lock:
                entries = [e for e in self._load() if e.get("root") != str(root)]
                entries.insert(
                    0, {"root": str(root), "platform": label, "last_seen": self._clock()}
                )
                self._save(entries[:MAX_PROJECTS])
            return root
        except Exception:  # noqa: BLE001 - recording must never break the prompt
            logger.debug("hermes-odd: recording the project root failed", exc_info=True)
            return None

    def on_section_render(self, session_info: Mapping[str, Any] | None) -> None:
        """Prompt-section observer: record the session's working directory."""
        info = session_info if isinstance(session_info, Mapping) else {}
        self.record(info.get("cwd"), info.get("platform"))

    def known(self) -> list[Project]:
        """Recorded projects, most recent first. Never raises."""
        try:
            with self._lock:
                entries = self._load()
        except Exception:  # noqa: BLE001
            return []
        projects = []
        for entry in entries:
            last_seen = entry.get("last_seen")
            projects.append(
                Project(
                    root=Path(entry["root"]),
                    platform=str(entry.get("platform") or ""),
                    last_seen=float(last_seen)
                    if isinstance(last_seen, (int, float)) and not isinstance(last_seen, bool)
                    else None,
                )
            )
        return projects


def resolve_projects(
    store: ProjectStore | None,
    cwd_candidates: list[Path] | None = None,
    has_tasks: Callable[[Path], bool] = has_tasks_dir,
) -> list[Project]:
    """Known projects then the process directories, deduplicated, filtered
    to those holding ``odd/tasks/``. Never raises."""
    candidates: list[Project] = list(store.known()) if store is not None else []
    for root in process_cwd_candidates() if cwd_candidates is None else cwd_candidates:
        candidates.append(Project(root=root, source="cwd"))
    seen: set[str] = set()
    projects: list[Project] = []
    for project in candidates:
        try:
            key = str(project.root.resolve())
        except (OSError, RuntimeError):
            key = str(project.root)
        if key in seen:
            continue
        seen.add(key)
        try:
            if has_tasks(project.root):
                projects.append(project)
        except Exception:  # noqa: BLE001
            continue
    return projects
