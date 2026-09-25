"""Write, replace or remove the single hermes-odd persona block in ``SOUL.md``.

This is the only ``SOUL.md`` mutation hermes-odd makes today. The block is::

    <!-- hermes-odd:persona -->
    ...
    <!-- /hermes-odd:persona -->

Placement. Hermes truncates a long ``SOUL.md`` by keeping the first 70% and
the last 20% of its cap and dropping the middle (see :mod:`hermes_odd.soul`),
so the block goes at the **top**: right after a leading H1 line and/or a
leading HTML comment header (not a managed marker) and the blank lines after
it, otherwise at line 1. A block that already exists is replaced in place,
wherever the user moved it; persona ``none`` removes it.

Safety:

* the path is resolved exactly like :func:`hermes_odd.soul.hermes_home`
  (profile-aware Hermes home) plus ``SOUL.md``; a symlinked ``SOUL.md``, a
  file over 4 MB, a file that is not UTF-8 and unbalanced hermes-odd markers
  are refused, never rewritten;
* only the block's own bytes change. Before writing, the plan is checked:
  the text outside the block is byte-identical and every ``gentle-ai:`` block
  is unchanged (those belong to gentle-ai and to the later cleanup);
* before every write the current file is copied to
  ``SOUL.md.hermes-odd-bak-<UTC timestamp>`` (the last 5 are kept), then the
  new text is written atomically: a temporary file in the same directory,
  fsync, the original permissions, ``os.replace``;
* the newline style (``\\n`` or ``\\r\\n``) and a leading BOM are kept.

Everything is reported as values; nothing here raises to the caller.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import soul as soul_mod
from .personas import CLOSE_MARKER, OPEN_MARKER

SOUL_FILE = "SOUL.md"
BACKUP_INFIX = ".hermes-odd-bak-"
BACKUP_KEEP = 5
MAX_SOUL_BYTES = soul_mod.MAX_SOUL_BYTES
NEW_FILE_MODE = 0o600

_OUR_MARKER_RE = re.compile(r"<!--\s*(/?)hermes-odd:persona\s*-->")
_GENTLE_PERSONA_RE = re.compile(r"<!--\s*gentle-ai:persona\s*-->")
_ANY_MANAGED_RE = re.compile(r"<!--\s*/?[a-z0-9][a-z0-9_-]*:[a-z0-9][a-z0-9_-]*\s*-->")
_H1_RE = re.compile(r"# [^\n]*(?:\n|$)")

INSERT, REPLACE, REMOVE, UNCHANGED, NOTHING = "insert", "replace", "remove", "unchanged", "nothing"

Scanner = Callable[[str], list[str]]


@dataclass
class Plan:
    """What applying a block (or removing it) would do. ``error`` blocks writing."""

    path: Path
    exists: bool = False
    action: str = NOTHING
    placement: str = ""
    before: str = ""
    after: str = ""
    error: str = ""
    gentle_persona: bool = False  # a gentle-ai persona block coexists
    extra_removed: int = 0  # duplicate hermes-odd blocks dropped
    mode: int = NEW_FILE_MODE

    @property
    def writes(self) -> bool:
        return not self.error and self.action in (INSERT, REPLACE, REMOVE)


@dataclass
class Result:
    plan: Plan
    written: bool = False
    backup: Path | None = None
    rotated: list[Path] = field(default_factory=list)
    error: str = ""


def soul_path(home: Path | None = None) -> Path:
    """``<Hermes home>/SOUL.md``, resolved like ``/odd_doctor`` does."""
    return Path(home if home is not None else soul_mod.hermes_home()) / SOUL_FILE


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def header_end(text: str) -> tuple[int, str]:
    """Offset where a new block goes and a placement label.

    After an optional BOM, an optional leading H1 line and an optional
    leading HTML comment that is not a managed marker (each followed by
    blank lines), else 0. ``\\n`` and ``\\r\\n`` newlines both work.
    """
    pos = 1 if text.startswith("\ufeff") else 0
    labels = []
    match = _H1_RE.match(text, pos)
    if match:
        pos = match.end()
        labels.append("after the H1 heading")
        pos = _skip_blank_lines(text, pos)
    if text.startswith("<!--", pos) and not _ANY_MANAGED_RE.match(text, pos):
        close = text.find("-->", pos)
        if close != -1:
            pos = _skip_newline(text, close + 3)
            labels.append("after the leading comment")
            pos = _skip_blank_lines(text, pos)
    if not labels:
        return (1 if text.startswith("\ufeff") else 0), "at line 1"
    return pos, " and ".join(labels) if len(labels) == 1 else "after the H1 heading and comment"


def _skip_newline(text: str, pos: int) -> int:
    if text.startswith("\r\n", pos):
        return pos + 2
    if text.startswith("\n", pos):
        return pos + 1
    return pos


def _skip_blank_lines(text: str, pos: int) -> int:
    while True:
        end = text.find("\n", pos)
        if end == -1 or text[pos:end].strip():
            return pos
        pos = end + 1


def _gentle_blocks(text: str) -> list[str]:
    return [
        text[b.start : b.end]
        for b in soul_mod.parse_blocks(text)
        if b.namespace == soul_mod.GENTLE_AI
    ]


def _our_blocks(text: str) -> tuple[list[tuple[int, int]], str]:
    """Spans of complete hermes-odd persona blocks, or an error for unbalanced markers."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for match in _OUR_MARKER_RE.finditer(text):
        closing = match.group(1) == "/"
        if not closing:
            if start is not None:
                return [], "nested hermes-odd:persona markers"
            start = match.start()
        else:
            if start is None:
                return [], "a closing hermes-odd:persona marker without its opener"
            spans.append((start, match.end()))
            start = None
    if start is not None:
        return [], "an unclosed hermes-odd:persona marker"
    return spans, ""


def _span_with_trailing_newlines(text: str, start: int, end: int) -> tuple[int, int]:
    """Extend a block span over up to two following newlines (what insert adds)."""
    for _ in range(2):
        end = _skip_newline(text, end)
    return start, end


def plan_block(block: str | None, home: Path | None = None) -> Plan:
    """Plan writing ``block`` (``None`` = remove). Reads only; never raises."""
    path = soul_path(home)
    plan = Plan(path=path)
    try:
        if path.is_symlink():
            plan.exists = True
            plan.error = "SOUL.md is a symlink; hermes-odd will not replace it"
            return plan
        if path.exists() and not path.is_file():
            plan.exists = True
            plan.error = "SOUL.md is not a regular file"
            return plan
        raw = b""
        if path.is_file():
            plan.exists = True
            plan.mode = stat.S_IMODE(path.stat().st_mode)
            with open(path, "rb") as handle:
                raw = handle.read(MAX_SOUL_BYTES + 1)
            if len(raw) > MAX_SOUL_BYTES:
                plan.error = "SOUL.md is larger than 4 MB; hermes-odd will not rewrite it"
                return plan
        try:
            original = raw.decode("utf-8")
        except UnicodeDecodeError:
            plan.error = "SOUL.md is not valid UTF-8; hermes-odd will not rewrite it"
            return plan
    except OSError as exc:
        plan.error = f"SOUL.md could not be read ({type(exc).__name__})"
        return plan

    newline = _newline(original)
    text = original
    plan.before = original
    plan.gentle_persona = bool(_GENTLE_PERSONA_RE.search(text))
    spans, error = _our_blocks(text)
    if error:
        plan.error = f"SOUL.md has {error}; fix it by hand, then retry"
        return plan

    if block is None:
        if not spans:
            plan.action = NOTHING
            plan.after = original
            return plan
        after = text
        for start, end in reversed(spans):
            s, e = _span_with_trailing_newlines(after, start, end)
            after = after[:s] + after[e:]
        plan.action = REMOVE
        plan.placement = "removed"
    else:
        block_lf = block.replace("\r\n", "\n").replace("\n", newline)
        if spans:
            first_start, first_end = spans[0]
            after = text
            for start, end in reversed(spans[1:]):
                s, e = _span_with_trailing_newlines(after, start, end)
                after = after[:s] + after[e:]
            plan.extra_removed = len(spans) - 1
            after = after[:first_start] + block_lf + after[first_end:]
            plan.action = UNCHANGED if after == text else REPLACE
            plan.placement = "in place"
        else:
            offset, placement = header_end(text)
            prefix = text[:offset]
            if prefix and not prefix.endswith("\n"):
                prefix += newline * 2
            rest = text[offset:]
            separator = newline * 2 if rest else newline
            after = prefix + block_lf + separator + rest
            plan.action = INSERT
            plan.placement = placement

    check = _verify(text, after, block)
    if check:
        plan.error = f"internal check failed ({check}); SOUL.md left untouched"
        return plan
    plan.after = after
    return plan


def _verify(before: str, after: str, block: str | None) -> str:
    """Invariants that must hold before any write."""
    if _gentle_blocks(before) != _gentle_blocks(after):
        return "gentle-ai blocks would change"
    spans, error = _our_blocks(after)
    if error:
        return error
    if block is None:
        if spans:
            return "a hermes-odd block would remain"
    elif len(spans) != 1:
        return "the result must hold exactly one hermes-odd block"

    # Outside our blocks the text is byte-identical, up to the trailing
    # separator newlines that insert adds and remove drops.
    def outside(text: str) -> str:
        found, _ = _our_blocks(text)
        for start, end in reversed(found):
            s, e = _span_with_trailing_newlines(text, start, end)
            text = text[:s] + text[e:]
        return text.rstrip("\r\n")

    if outside(before) != outside(after):
        return "text outside the block would change"
    return ""


def scan_block(block: str, scanner: Scanner | None) -> list[str]:
    """Hermes' own context-file threat scan of the block (empty = clean)."""
    if scanner is None:
        return []
    try:
        return list(scanner(block) or [])
    except Exception:  # noqa: BLE001 - a failing scanner never blocks setup
        return []


def hermes_scanner() -> Scanner | None:
    """``tools.threat_patterns.scan_for_threats`` (scope ``context``) when Hermes
    is loaded in this process; ``None`` otherwise (tests, standalone)."""
    import sys

    if "hermes_cli" not in sys.modules and "tools.threat_patterns" not in sys.modules:
        return None
    try:
        from tools.threat_patterns import scan_for_threats  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return None
    return lambda text: scan_for_threats(text, scope="context")


def _utc_stamp(now: _dt.datetime) -> str:
    return now.astimezone(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def backup_paths(path: Path) -> list[Path]:
    """Existing hermes-odd backups of ``path``, oldest first."""
    try:
        found = [
            p
            for p in path.parent.glob(f"{path.name}{BACKUP_INFIX}*")
            if p.is_file() and not p.is_symlink()
        ]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.name)


def _backup(path: Path, now: _dt.datetime) -> Path:
    base = path.with_name(f"{path.name}{BACKUP_INFIX}{_utc_stamp(now)}")
    target = base
    counter = 1
    while target.exists():
        target = base.with_name(f"{base.name}-{counter}")
        counter += 1
    shutil.copy2(path, target)
    return target


def _rotate(path: Path, keep: int = BACKUP_KEEP) -> list[Path]:
    backups = backup_paths(path)
    removed = []
    for old in backups[: max(0, len(backups) - keep)]:
        try:
            old.unlink()
            removed.append(old)
        except OSError:
            pass
    return removed


def atomic_write(path: Path, text: str, mode: int) -> None:
    """Temp file in the same directory, fsync, chmod ``mode``, ``os.replace``."""
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.hermes-odd-tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def apply_plan(
    plan: Plan,
    now: Callable[[], _dt.datetime] = lambda: _dt.datetime.now(_dt.UTC),
) -> Result:
    """Back up, then write ``plan.after`` atomically. Never raises."""
    result = Result(plan=plan)
    if plan.error:
        result.error = plan.error
        return result
    if not plan.writes:
        return result
    try:
        if plan.exists:
            result.backup = _backup(plan.path, now())
            result.rotated = _rotate(plan.path)
        else:
            plan.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(plan.path, plan.after, plan.mode)
        result.written = True
    except OSError as exc:
        result.error = f"SOUL.md could not be written ({type(exc).__name__}); it is unchanged"
    return result


def block_status(home: Path | None = None) -> tuple[str, int]:
    """``("present"|"absent"|"unreadable"|"broken", chars)`` of our block."""
    plan = plan_block(None, home)
    if plan.error:
        return ("broken" if "marker" in plan.error else "unreadable"), 0
    spans, _ = _our_blocks(plan.before)
    if not spans:
        return "absent", 0
    start, end = spans[0]
    return "present", end - start


__all__ = [
    "BACKUP_INFIX",
    "BACKUP_KEEP",
    "Plan",
    "Result",
    "apply_plan",
    "atomic_write",
    "backup_paths",
    "block_status",
    "header_end",
    "hermes_scanner",
    "plan_block",
    "scan_block",
    "soul_path",
    "OPEN_MARKER",
    "CLOSE_MARKER",
]
