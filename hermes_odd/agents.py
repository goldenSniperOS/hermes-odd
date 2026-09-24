"""Subagent tracking for ``/odd_agents`` (concept port of gentle-shell Gentle Agents).

gentle-shell keeps one ``TaskRecord`` per Pi subagent (id, agent, label,
status, timestamps, last step, last activity, turns, tool calls, result or
error) and renders it as a card. hermes-odd keeps the same idea for Hermes'
``delegate_task`` children, fed by observer hooks and rendered as plain text
by ``/odd_agents`` (see :mod:`hermes_odd.commands.agents`). No Pi code or text
is copied.

Hook facts (verified against hermes-agent):

* ``subagent_start`` (``tools/delegate_tool.py``): ``parent_session_id``,
  ``parent_turn_id``, ``parent_subagent_id``, ``child_session_id``,
  ``child_subagent_id`` (``sa-<index>-<hex8>``), ``child_role``,
  ``child_goal``.
* ``post_tool_call`` (``model_tools.py``): ``tool_name``, ``args``,
  ``result``, ``task_id``, ``session_id``, ``tool_call_id``, ``turn_id``,
  ``duration_ms``, ``status`` (``ok``/``error``), ``error_type``,
  ``error_message``. A child runs with ``task_id == child_subagent_id``.
* ``subagent_stop`` (``tools/delegate_tool.py``, always on the parent
  thread): ``parent_session_id``, ``parent_turn_id``, ``child_session_id``,
  ``child_role``, ``child_summary``, ``child_status`` (``completed``,
  ``failed``, ``interrupted``, ``timeout``, ``error``),
  ``tool_call_history``, ``duration_ms``. There is **no** subagent id, so
  the record is found by ``child_session_id``.
* ``on_session_start``: ``session_id``, ``model``, ``platform``; fired only
  for brand-new sessions, so a resumed gateway session has no platform.

``pre_tool_call`` is deliberately not registered: Hermes fails it closed on
timeout, and this module only observes.

Privacy: records never hold tool arguments, tool results, tool error messages
or anything derived from them. Per tool call only the tool name, ok/error,
duration and time are kept. The goal is the parent's own delegation text
(truncated to 200 characters) and the summary is the child's own final
summary (truncated to 1,500 characters).

Storage: one JSON document (schema ``hermes-odd.agents/v1``) under the
``ctx.state`` key ``agents.v1``. ``ctx.state`` (``hermes_cli.plugins.PluginState``)
exposes ``get(key, default)`` and ``set(key, value)``; each call re-reads the
file under a cross-process lock and ``set`` enforces a 10 MB quota. A
read-modify-write here spans a ``get`` and a ``set``, so it is serialized by a
process-local lock only: concurrent writers in two processes of one profile
can drop one update (rare: a child always runs in its parent's process).
When ``ctx.state`` is missing or failing, an in-memory backend is used.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

logger = logging.getLogger("hermes_odd")

SCHEMA = "hermes-odd.agents/v1"
STATE_KEY = "agents.v1"

MAX_RECORDS = 50
MAX_TIMELINE = 15
GOAL_MAX_CHARS = 200
SUMMARY_MAX_CHARS = 1500
ROLE_MAX_CHARS = 40
TOOL_NAME_MAX_CHARS = 64
ID_MAX_CHARS = 128
FINISHED_TTL_SECONDS = 24 * 3600
STALE_AFTER_SECONDS = 6 * 3600
MAX_PLATFORM_SESSIONS = 256

RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
INTERRUPTED = "interrupted"
TIMED_OUT = "timed_out"
STALE = "stale"
STATUSES = (RUNNING, COMPLETED, FAILED, INTERRUPTED, TIMED_OUT, STALE)

# ``child_status`` values produced by delegate_task -> record status.
_CHILD_STATUS_MAP = {
    "completed": COMPLETED,
    "failed": FAILED,
    "error": FAILED,
    "interrupted": INTERRUPTED,
    "timeout": TIMED_OUT,
    "timed_out": TIMED_OUT,
}

HOOK_NAMES = ("on_session_start", "subagent_start", "post_tool_call", "subagent_stop")


def truncate(text: Any, limit: int) -> str:
    """Return ``text`` as a string of at most ``limit`` characters."""
    value = text if isinstance(text, str) else ("" if text is None else str(text))
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _clean_id(value: Any) -> str:
    return value.strip()[:ID_MAX_CHARS] if isinstance(value, str) else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value == value and value >= 0 else None  # drop NaN/negatives


def map_child_status(raw: Any) -> str:
    """Map a ``subagent_stop`` ``child_status`` to a record status."""
    key = raw.strip().lower() if isinstance(raw, str) else ""
    return _CHILD_STATUS_MAP.get(key, FAILED)


def _tool_status(raw: Any) -> str:
    return "error" if isinstance(raw, str) and raw.strip().lower() == "error" else "ok"


class MemoryBackend:
    """``get``/``set`` store used when ``ctx.state`` is unavailable."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self._data.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = copy.deepcopy(value)


def resolve_backend(ctx: Any) -> Any:
    """Return ``ctx.state`` when it offers ``get``/``set``, else a memory backend."""
    try:
        state = getattr(ctx, "state", None)
    except Exception as exc:  # noqa: BLE001 - state is optional
        logger.warning("hermes-odd: ctx.state failed (%s); agent records stay in memory", exc)
        return MemoryBackend()
    if callable(getattr(state, "get", None)) and callable(getattr(state, "set", None)):
        return state
    logger.warning("hermes-odd: ctx.state is unavailable; agent records stay in memory")
    return MemoryBackend()


def _empty_document() -> dict[str, Any]:
    return {"schema": SCHEMA, "records": []}


class AgentStore:
    """Bounded store of subagent records plus the hook handlers that feed it."""

    def __init__(self, backend: Any | None = None, clock: Callable[[], float] = time.time):
        self._backend = backend if backend is not None else MemoryBackend()
        self._fallback = MemoryBackend()
        self._using_fallback = False
        self._clock = clock
        self._lock = threading.RLock()
        # In-process only: children always run in their parent's process, so
        # post_tool_call filtering never needs to read state.
        self._active: set[str] = set()
        self._platforms: OrderedDict[str, str] = OrderedDict()

    # -- persistence -------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        doc: Any = None
        if not self._using_fallback:
            try:
                doc = self._backend.get(STATE_KEY, None)
            except Exception as exc:  # noqa: BLE001 - fall back, never raise
                self._switch_to_fallback(exc)
        if self._using_fallback:
            doc = self._fallback.get(STATE_KEY, None)
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return _empty_document()
        records = doc.get("records")
        if not isinstance(records, list):
            records = []
        doc["records"] = [r for r in records if isinstance(r, dict)]
        return doc

    def _save(self, doc: dict[str, Any]) -> None:
        if not self._using_fallback:
            try:
                self._backend.set(STATE_KEY, doc)
                return
            except Exception as exc:  # noqa: BLE001 - fall back, never raise
                self._switch_to_fallback(exc)
        self._fallback.set(STATE_KEY, doc)

    def _switch_to_fallback(self, exc: Exception) -> None:
        if not self._using_fallback:
            logger.warning("hermes-odd: agent state unavailable (%s); using memory", exc)
            try:
                current = self._backend.get(STATE_KEY, None)
            except Exception:  # noqa: BLE001
                current = None
            if isinstance(current, dict):
                self._fallback.set(STATE_KEY, current)
        self._using_fallback = True

    def _mutate(self, change: Callable[[list[dict[str, Any]], float], bool]) -> None:
        with self._lock:
            doc = self._load()
            now = self._clock()
            changed = change(doc["records"], now)
            pruned = self._prune(doc["records"], now)
            if changed or pruned:
                self._save(doc)

    # -- retention ---------------------------------------------------------

    @staticmethod
    def _prune(records: list[dict[str, Any]], now: float) -> bool:
        """Mark stuck runs stale, drop old finished runs, cap the count."""
        changed = False
        for record in records:
            started = _number(record.get("started_at")) or 0.0
            if record.get("status") == RUNNING and now - started > STALE_AFTER_SECONDS:
                record["status"] = STALE
                record["error"] = "no stop event within 6 h; marked stale"
                changed = True
        keep = []
        for record in records:
            if record.get("status") == RUNNING:
                keep.append(record)
                continue
            last = _number(record.get("ended_at")) or _number(record.get("last_activity_at"))
            if last is None or now - last <= FINISHED_TTL_SECONDS:
                keep.append(record)
        if len(keep) != len(records):
            changed = True
        if len(keep) > MAX_RECORDS:
            # Oldest finished first, then oldest running.
            keep.sort(
                key=lambda r: (r.get("status") == RUNNING, _number(r.get("started_at")) or 0.0)
            )
            del keep[: len(keep) - MAX_RECORDS]
            changed = True
        records[:] = keep
        return changed

    # -- reads -------------------------------------------------------------

    def records(self) -> list[dict[str, Any]]:
        """Return pruned records, running first, newest first."""
        with self._lock:
            doc = self._load()
            if self._prune(doc["records"], self._clock()):
                self._save(doc)
            records = copy.deepcopy(doc["records"])
        records.sort(key=lambda r: _number(r.get("started_at")) or 0.0, reverse=True)
        records.sort(key=lambda r: r.get("status") != RUNNING)
        return records

    def now(self) -> float:
        return self._clock()

    # -- hook handlers (never raise) ---------------------------------------

    def on_session_start(self, **kwargs: Any) -> None:
        try:
            session_id = _clean_id(kwargs.get("session_id"))
            platform = truncate(kwargs.get("platform"), 32)
            if session_id and platform:
                with self._lock:
                    self._platforms[session_id] = platform
                    self._platforms.move_to_end(session_id)
                    while len(self._platforms) > MAX_PLATFORM_SESSIONS:
                        self._platforms.popitem(last=False)
        except Exception:  # noqa: BLE001 - hooks never raise
            logger.debug("hermes-odd on_session_start failed", exc_info=True)

    def on_subagent_start(self, **kwargs: Any) -> None:
        try:
            subagent_id = _clean_id(kwargs.get("child_subagent_id"))
            child_session_id = _clean_id(kwargs.get("child_session_id"))
            if not subagent_id and child_session_id:
                subagent_id = _synthetic_id(child_session_id)
            if not subagent_id:
                return
            parent_session_id = _clean_id(kwargs.get("parent_session_id"))

            def change(records: list[dict[str, Any]], now: float) -> bool:
                platform = self._platforms.get(parent_session_id, "")
                if not platform:
                    for other in records:
                        if parent_session_id and other.get("child_session_id") == parent_session_id:
                            platform = other.get("platform") or ""
                            break
                records[:] = [r for r in records if r.get("subagent_id") != subagent_id]
                records.append(
                    {
                        "subagent_id": subagent_id,
                        "child_session_id": child_session_id,
                        "parent_session_id": parent_session_id,
                        "parent_subagent_id": _clean_id(kwargs.get("parent_subagent_id")),
                        "platform": platform,
                        "role": truncate(kwargs.get("child_role"), ROLE_MAX_CHARS) or "leaf",
                        "goal": truncate(kwargs.get("child_goal"), GOAL_MAX_CHARS),
                        "status": RUNNING,
                        "started_at": now,
                        "ended_at": None,
                        "duration_ms": None,
                        "tool_calls": 0,
                        "last_tool": None,
                        "last_activity_at": now,
                        "timeline": [],
                        "summary": "",
                        "error": "",
                    }
                )
                return True

            with self._lock:
                self._active.add(subagent_id)
                self._mutate(change)
        except Exception:  # noqa: BLE001 - hooks never raise
            logger.debug("hermes-odd subagent_start failed", exc_info=True)

    def on_post_tool_call(self, **kwargs: Any) -> None:
        try:
            task_id = _clean_id(kwargs.get("task_id"))
            if not task_id or task_id not in self._active:
                return  # parent or unrelated tool call: ignored without I/O
            # Only the name, ok/error and duration are read. ``args``,
            # ``result`` and ``error_message`` are never touched.
            name = truncate(kwargs.get("tool_name"), TOOL_NAME_MAX_CHARS) or "unknown"
            status = _tool_status(kwargs.get("status"))
            duration = _number(kwargs.get("duration_ms"))

            def change(records: list[dict[str, Any]], now: float) -> bool:
                for record in records:
                    if record.get("subagent_id") == task_id and record.get("status") == RUNNING:
                        entry = {
                            "tool": name,
                            "status": status,
                            "duration_ms": int(duration) if duration is not None else None,
                            "at": now,
                        }
                        timeline = [e for e in record.get("timeline") or [] if isinstance(e, dict)]
                        timeline.append(entry)
                        record["timeline"] = timeline[-MAX_TIMELINE:]
                        record["tool_calls"] = int(_number(record.get("tool_calls")) or 0) + 1
                        record["last_tool"] = {"name": name, "status": status}
                        record["last_activity_at"] = now
                        return True
                return False

            self._mutate(change)
        except Exception:  # noqa: BLE001 - hooks never raise
            logger.debug("hermes-odd post_tool_call failed", exc_info=True)

    def on_subagent_stop(self, **kwargs: Any) -> None:
        try:
            child_session_id = _clean_id(kwargs.get("child_session_id"))
            if not child_session_id:
                return
            raw_status = kwargs.get("child_status")
            status = map_child_status(raw_status)
            summary = truncate(kwargs.get("child_summary"), SUMMARY_MAX_CHARS)
            duration = _number(kwargs.get("duration_ms"))
            history = kwargs.get("tool_call_history")
            history = history if isinstance(history, list) else []
            finished: list[str] = []

            def change(records: list[dict[str, Any]], now: float) -> bool:
                matches = [r for r in records if r.get("child_session_id") == child_session_id]
                running = [r for r in matches if r.get("status") == RUNNING]
                if running or matches:
                    record = (running or matches)[-1]
                else:
                    record = {
                        "subagent_id": _synthetic_id(child_session_id),
                        "child_session_id": child_session_id,
                        "parent_session_id": _clean_id(kwargs.get("parent_session_id")),
                        "parent_subagent_id": "",
                        "platform": "",
                        "role": truncate(kwargs.get("child_role"), ROLE_MAX_CHARS) or "leaf",
                        "goal": "",
                        "started_at": None,
                        "tool_calls": 0,
                        "last_tool": None,
                        "timeline": [],
                    }
                    records.append(record)
                started = _number(record.get("started_at"))
                if duration is None and started is not None:
                    record["duration_ms"] = int((now - started) * 1000)
                else:
                    record["duration_ms"] = int(duration) if duration is not None else None
                if started is None and duration is not None:
                    record["started_at"] = now - duration / 1000
                record["status"] = status
                record["ended_at"] = now
                record["last_activity_at"] = now
                record["summary"] = summary
                raw = truncate(raw_status, 32) or "?"
                record["error"] = "" if status == COMPLETED else f"child status: {raw}"
                if not record.get("tool_calls") and history:
                    # Missed live events (e.g. plugin loaded mid-run): use the
                    # metadata-only history, names and ok/error only.
                    timeline = []
                    for item in history:
                        if isinstance(item, Mapping):
                            timeline.append(
                                {
                                    "tool": truncate(item.get("tool_name"), TOOL_NAME_MAX_CHARS)
                                    or "unknown",
                                    "status": _tool_status(item.get("status")),
                                    "duration_ms": None,
                                    "at": None,
                                }
                            )
                    record["tool_calls"] = len(timeline)
                    record["timeline"] = timeline[-MAX_TIMELINE:]
                    if timeline:
                        last = timeline[-1]
                        record["last_tool"] = {"name": last["tool"], "status": last["status"]}
                finished.append(str(record.get("subagent_id") or ""))
                return True

            self._mutate(change)
            with self._lock:
                for subagent_id in finished:
                    self._active.discard(subagent_id)
        except Exception:  # noqa: BLE001 - hooks never raise
            logger.debug("hermes-odd subagent_stop failed", exc_info=True)


def _synthetic_id(child_session_id: str) -> str:
    digest = hashlib.sha256(child_session_id.encode("utf-8")).hexdigest()[:8]
    return f"sx-{digest}"


def register_agent_hooks(ctx: Any, store: AgentStore) -> int:
    """Register the observer hooks; return how many succeeded. Never raises."""
    register_hook = getattr(ctx, "register_hook", None)
    if not callable(register_hook):
        logger.warning("hermes-odd: ctx.register_hook is unavailable; /odd_agents stays empty")
        return 0
    callbacks = {
        "on_session_start": store.on_session_start,
        "subagent_start": store.on_subagent_start,
        "post_tool_call": store.on_post_tool_call,
        "subagent_stop": store.on_subagent_stop,
    }
    registered = 0
    for name in HOOK_NAMES:
        try:
            register_hook(name, callbacks[name])
            registered += 1
        except Exception as exc:  # noqa: BLE001 - never break Hermes startup
            logger.warning("hermes-odd: could not register hook %s: %s", name, exc)
    return registered
