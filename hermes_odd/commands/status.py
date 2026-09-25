"""``/odd_status``: one compact status message (Pi ``gentle:status``).

Concept port of gentle-shell's ``gentle:status`` (``extensions/gentle-ai.ts``):
what is active and at which version, in a few lines. It reads the plugin's own
records (prompt section, skills, the ``/odd_agents`` and ``/odd_changes``
stores, feature documents through the ``/odd_tasks`` resolution) and runs no
subprocess except the cached ``gentle-ai version`` probe and the cached,
read-only native review availability probe (``gentle-ai review status ...
--agent hermes``, see :mod:`hermes_odd.rdd`); the RDD mode is only shown when
``/odd_doctor`` or ``/odd_review_mode`` cached it in the last minute. The RDD wording
follows gentle-ai's ``receipt-driven development: <mode> (decided by
<source>)``. No upstream code or text is copied. Output stays under
:data:`OUTPUT_MAX_CHARS`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import __version__
from .. import upstream as upstream_mod
from ..agents import RUNNING, AgentStore
from ..changes import ChangeStore
from ..probes import Prober, is_below, process_repo
from ..projects import ProjectStore
from ..prompt import SECTION_ID, SECTION_MAX_CHARS
from ..rdd import native_review_line, probe_repo
from ..runtime import RuntimeInfo
from .changes import counts
from .doctor import display_path, review_mode_text, supported_text
from .registry import CommandSpec
from .tasks import collect

OUTPUT_MAX_CHARS = 1500
DAY = 24 * 3600


def _skills_line(runtime: RuntimeInfo | None) -> str:
    names = runtime.skills if runtime else []
    if not names:
        return "Skills: none registered"
    return f"Skills: {len(names)} ({', '.join(names)})"


def _agents_line(store: AgentStore | None) -> str:
    if store is None:
        return "Subagents: not tracked"
    records = store.records()
    running = sum(1 for r in records if r.get("status") == RUNNING)
    return f"Subagents: {running} running · {len(records) - running} finished (24 h)"


def _changes_line(store: ChangeStore | None) -> str:
    if store is None:
        return "Changes: not tracked"
    now = store.now()
    recent = [f for f in store.files() if now - float(f.get("last_at") or 0) <= DAY]
    added = sum(int(f.get("added") or 0) for f in recent)
    removed = sum(int(f.get("removed") or 0) for f in recent)
    unknown = any(f.get("removed_unknown") for f in recent)
    noun = "file" if len(recent) == 1 else "files"
    return f"Changes (24 h): {len(recent)} {noun} · {counts(added, removed, unknown)}"


def _features_line(project_store: ProjectStore | None, cwd: list[Path] | None) -> str:
    projects = collect(project_store, cwd)
    features = sum(len(p.docs) for p in projects)
    open_tasks = sum(max(0, d.total - d.done) for p in projects for d in p.docs)
    noun = "project" if len(projects) == 1 else "projects"
    return f"ODD features: {features} · {open_tasks} open tasks ({len(projects)} {noun})"


class Status:
    def __init__(
        self,
        runtime: RuntimeInfo | None = None,
        prober: Prober | None = None,
        agent_store: AgentStore | None = None,
        change_store: ChangeStore | None = None,
        project_store: ProjectStore | None = None,
        *,
        lock_loader: Callable[[], dict[str, Any]] = upstream_mod.load_lock,
        repo: Callable[[], Path | None] = process_repo,
        cwd_candidates: list[Path] | None = None,
    ):
        self.runtime = runtime
        self.prober = prober if prober is not None else Prober()
        self.agent_store = agent_store
        self.change_store = change_store
        self.project_store = project_store
        self._lock_loader = lock_loader
        self._repo = repo
        self._cwd = cwd_candidates

    def _lock(self) -> dict[str, Any] | None:
        try:
            return self._lock_loader()
        except Exception:  # noqa: BLE001
            return None

    def _binary_line(self, lock: dict[str, Any] | None) -> str:
        minimum = None
        if lock is not None:
            try:
                minimum = upstream_mod.min_gentle_ai_version(lock)
            except Exception:  # noqa: BLE001
                minimum = None
        info = self.prober.first_version()
        if info is None:
            return f"gentle-ai: ✗ not on PATH (min {minimum or '?'})"
        if info.version is None:
            return f"gentle-ai: ⚠ version unknown ({info.state}) (min {minimum or '?'})"
        below = is_below(info.version, minimum)
        mark = "✗" if below else ("✓" if below is False else "⚠")
        extra = " below" if below else ""
        where = display_path(info.path)
        return f"gentle-ai: {info.version} {mark}{extra} min {minimum or '?'} ({where})"

    def _rdd_line(self) -> str:
        try:
            repo = self._repo()
        except Exception:  # noqa: BLE001
            repo = None
        cached = self.prober.cached_review_mode(repo)
        if cached is None or cached.state != "ok":
            return "RDD: unknown here · run /odd_doctor"
        return f"RDD: {review_mode_text(cached)}"

    def _native_line(self) -> str:
        info = self.prober.first_version()
        native = self.prober.native_review(
            info.path if info else None, probe_repo(self.project_store, self._repo)
        )
        return native_review_line(native, info.version if info else None)

    def lines(self) -> list[str]:
        runtime = self.runtime
        lock = self._lock()
        section = (
            f"Prompt: {SECTION_ID} {runtime.section_chars}/{SECTION_MAX_CHARS} chars"
            if runtime and runtime.section_registered
            else "Prompt: section not registered ✗"
        )
        steps: list[tuple[str, Callable[[], str]]] = [
            ("Skills", lambda: _skills_line(runtime)),
            ("Subagents", lambda: _agents_line(self.agent_store)),
            ("Changes", lambda: _changes_line(self.change_store)),
            ("ODD features", lambda: _features_line(self.project_store, self._cwd)),
            ("gentle-ai", lambda: self._binary_line(lock)),
            ("RDD", self._rdd_line),
            ("Native review on Hermes", self._native_line),
            (
                "Upstream",
                lambda: f"Upstream: {supported_text(lock)}" if lock else "Upstream: lock ✗",
            ),
        ]
        lines = [f"hermes-odd {__version__} is active", section]
        for name, step in steps:
            try:
                lines.append(step())
            except Exception as exc:  # noqa: BLE001 - one line never breaks the status
                lines.append(f"{name}: unavailable ({type(exc).__name__})")
        lines.append("Problems? /odd_doctor")
        return lines

    def render(self) -> str:
        text = "\n".join(self.lines())
        if len(text) > OUTPUT_MAX_CHARS:
            text = text[: OUTPUT_MAX_CHARS - 1].rstrip() + "…"
        return text


def make_odd_status(status: Status) -> CommandSpec:
    def handler(raw_args: str) -> str:
        return status.render()

    return CommandSpec(
        name="odd_status",
        description="Compact status: versions, prompt budget, skills, activity, gentle-ai",
        handler=handler,
        group="Health",
    )


__all__ = ["Status", "make_odd_status"]
