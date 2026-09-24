"""``/odd_agents``: plain-text view of Hermes subagents (Pi ``gentle:agents``).

Concept port of the gentle-shell Gentle Agents card: one compact block per
``delegate_task`` child, a detail view per id, and an ``all`` history. The
text uses no Markdown and stays under :data:`OUTPUT_MAX_CHARS` so a
Telegram reply (4096 characters) never needs splitting; the CLI and TUI show
the same text.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from ..agents import (
    COMPLETED,
    FAILED,
    INTERRUPTED,
    MAX_RECORDS,
    MAX_TIMELINE,
    RUNNING,
    STALE,
    TIMED_OUT,
    AgentStore,
)
from .registry import CommandSpec

OUTPUT_MAX_CHARS = 3500
LIST_LIMIT = 10
GOAL_LINE_CHARS = 72

GLYPHS = {
    RUNNING: "●",
    COMPLETED: "✓",
    FAILED: "✗",
    INTERRUPTED: "⊘",
    TIMED_OUT: "⏱",
    STALE: "○",
}

EMPTY_TEXT = (
    "No subagents recorded yet.\n"
    "Subagents appear here when the agent delegates work with delegate_task; "
    "running and recent runs (last 24 h) are listed."
)

STOP_TEXT = (
    "/odd_agents stop is not available: Hermes offers no safe plugin API to "
    "interrupt a delegate_task child from a command. Ask the agent to stop it "
    "(delegate_task action=stop) in the conversation that started it."
)


def _glyph(status: Any) -> str:
    return GLYPHS.get(status, "?")


def short_id(subagent_id: Any) -> str:
    """``sa-0-1a2b3c4d`` -> ``1a2b3c4d``; other ids are returned unchanged."""
    value = str(subagent_id or "")
    head, _, tail = value.rpartition("-")
    return tail if head and tail else value


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "-"
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _elapsed(record: dict[str, Any], now: float) -> str:
    if record.get("status") == RUNNING:
        started = record.get("started_at")
        return format_duration(now - started if isinstance(started, (int, float)) else None)
    duration = record.get("duration_ms")
    if isinstance(duration, (int, float)):
        return format_duration(duration / 1000)
    return "-"


def _one_line(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _clock(ts: Any) -> str:
    if not isinstance(ts, (int, float)):
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _last_tool(record: dict[str, Any]) -> str:
    last = record.get("last_tool")
    count = record.get("tool_calls") or 0
    noun = "tool" if count == 1 else "tools"
    if isinstance(last, dict) and last.get("name"):
        return f"last: {last['name']} {last.get('status', 'ok')} · {count} {noun}"
    return f"last: - · {count} {noun}"


MORE_MARKER_RESERVE = 40


def _fit(
    blocks: Iterable[str],
    header: list[str],
    footer: str = "",
    hidden: int = 0,
    more_hint: str = " (/odd_agents all)",
) -> str:
    """Join blocks under the size cap, ending with ``… N more`` when cut.

    ``hidden`` counts items left out before fitting (for example past the
    list limit); they are added to the marker.
    """
    blocks = list(blocks)
    text = "\n".join(header)
    reserve = MORE_MARKER_RESERVE + (len(footer) + 2 if footer else 0)
    shown = 0
    for block in blocks:
        candidate = f"{text}\n{block}"
        if len(candidate) + reserve > OUTPUT_MAX_CHARS:
            break
        text = candidate
        shown += 1
    more = len(blocks) - shown + hidden
    if more:
        text += f"\n… {more} more{more_hint}"
    if footer:
        text += f"\n\n{footer}"
    return text


def _counts(records: list[dict[str, Any]]) -> str:
    running = sum(1 for r in records if r.get("status") == RUNNING)
    return f"Subagents: {running} running · {len(records) - running} finished"


def render_list(records: list[dict[str, Any]], now: float) -> str:
    if not records:
        return EMPTY_TEXT
    blocks = []
    for record in records:
        role = record.get("role") or "leaf"
        head = f"{_glyph(record.get('status'))} {short_id(record.get('subagent_id'))} {role}"
        head += f" · {_elapsed(record, now)}"
        goal = _one_line(record.get("goal"), GOAL_LINE_CHARS) or "(no goal recorded)"
        blocks.append(f"{head}\n  {goal}\n  {_last_tool(record)}")
    return _fit(
        blocks[:LIST_LIMIT],
        [_counts(records), ""],
        "Details: /odd_agents [id] · history: /odd_agents all",
        hidden=max(0, len(blocks) - LIST_LIMIT),
    )


def render_all(records: list[dict[str, Any]], now: float) -> str:
    if not records:
        return EMPTY_TEXT
    lines = []
    for record in records[:MAX_RECORDS]:
        lines.append(
            f"{_glyph(record.get('status'))} {short_id(record.get('subagent_id'))} "
            f"{record.get('role') or 'leaf'} · {_elapsed(record, now)} · "
            f"{_one_line(record.get('goal'), 60) or '(no goal)'}"
        )
    return _fit(
        lines,
        [_counts(records) + " (last 24 h, up to 50)", ""],
        hidden=max(0, len(records) - MAX_RECORDS),
        more_hint="",
    )


def match_records(records: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    needle = prefix.strip().lower()
    if not needle:
        return []
    exact = [r for r in records if str(r.get("subagent_id", "")).lower() == needle]
    if exact:
        return exact
    return [
        r
        for r in records
        if str(r.get("subagent_id", "")).lower().startswith(needle)
        or short_id(r.get("subagent_id")).lower().startswith(needle)
    ]


def render_detail(record: dict[str, Any], now: float) -> str:
    status = record.get("status") or "?"
    lines = [
        f"{_glyph(status)} {record.get('subagent_id')} · {status}",
        f"role: {record.get('role') or 'leaf'}",
        f"goal: {_one_line(record.get('goal'), 400) or '-'}",
    ]
    started = record.get("started_at")
    ago = format_duration(now - started) if isinstance(started, (int, float)) else "-"
    lines.append(f"started: {_clock(started)} ({ago} ago)")
    if status == RUNNING:
        lines.append(f"running for: {_elapsed(record, now)}")
    else:
        lines.append(f"ended: {_clock(record.get('ended_at'))} · took {_elapsed(record, now)}")
    parent = record.get("parent_session_id") or "-"
    platform = record.get("platform") or "unknown"
    lines.append(f"parent session: {parent} · platform: {platform}")
    last_activity = record.get("last_activity_at")
    activity = (
        f"{format_duration(now - last_activity)} ago"
        if isinstance(last_activity, (int, float))
        else "-"
    )
    lines.append(f"{_last_tool(record)} · activity {activity}")
    timeline = [e for e in record.get("timeline") or [] if isinstance(e, dict)]
    if timeline:
        lines.append(f"timeline (last {MAX_TIMELINE}):")
        for entry in timeline[-MAX_TIMELINE:]:
            at = entry.get("at")
            stamp = time.strftime("%H:%M:%S", time.localtime(at)) if at else "--:--:--"
            duration = entry.get("duration_ms")
            took = f" {duration}ms" if isinstance(duration, int) else ""
            lines.append(f"  {stamp} {entry.get('tool')} {entry.get('status')}{took}")
    if record.get("summary"):
        lines.append("summary:")
        lines.append(str(record["summary"]))
    if record.get("error"):
        lines.append(f"error: {record['error']}")
    text = "\n".join(lines)
    if len(text) > OUTPUT_MAX_CHARS:
        cut = len(text) - (OUTPUT_MAX_CHARS - 40)
        text = text[: OUTPUT_MAX_CHARS - 40].rstrip() + f"\n… {cut} more characters"
    return text


def render_lookup(records: list[dict[str, Any]], prefix: str, now: float) -> str:
    matches = match_records(records, prefix)
    shown = _one_line(prefix, 40)
    if not matches:
        return (
            f"No subagent matches '{shown}'. Run /odd_agents to list recent ids "
            "(finished runs are kept for 24 h)."
        )
    if len(matches) > 1:
        ids = ", ".join(short_id(r.get("subagent_id")) for r in matches[:10])
        more = f" and {len(matches) - 10} more" if len(matches) > 10 else ""
        return (
            f"'{shown}' is ambiguous: {len(matches)} subagents match ({ids}{more}). "
            "Use more characters."
        )
    return render_detail(matches[0], now)


def make_odd_agents(store: AgentStore) -> CommandSpec:
    def handler(raw_args: str) -> str:
        args = (raw_args or "").strip()
        words = args.split()
        if words and words[0].lower() == "stop":
            return STOP_TEXT
        records = store.records()
        now = store.now()
        if not args:
            return render_list(records, now)
        if args.lower() == "all":
            return render_all(records, now)
        return render_lookup(records, words[0], now)

    return CommandSpec(
        name="odd_agents",
        description="Show what your subagents are doing and what they did",
        handler=handler,
        args_hint="[id|all]",
    )
