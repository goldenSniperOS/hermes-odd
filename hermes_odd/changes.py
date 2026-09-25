"""Changed-file tracking for ``/odd_changes`` (concept port of gentle-shell Gentle Changes).

gentle-shell captures the successful write/edit tool calls of a Pi session
and its owned subagents (no repository scans, no background polling) and
shows them per worktree with line counts. hermes-odd keeps the same capture
model for Hermes, fed by the ``post_tool_call`` observer hook, and renders it
as plain text (see :mod:`hermes_odd.commands.changes`). No upstream code or
text is copied; upstream's before/after snapshots and diff viewer are not
ported (hermes-odd never stores file content).

Hermes file-mutating tools (verified in ``tools/file_tools.py``):

* ``write_file`` - args ``path``, ``content`` (full new content; the old
  content is not in the call). Result JSON: ``bytes_written``, ``verified``,
  ``resolved_path`` (absolute path actually written) and ``files_modified``
  ``[resolved_path]`` on success, ``error`` on failure.
* ``patch`` replace mode - args ``path``, ``old_string``, ``new_string``,
  ``replace_all`` (``mode`` omitted or ``"replace"``). Result JSON:
  ``success``, ``diff`` (``difflib`` unified diff with ``a/<abs>`` /
  ``b/<abs>`` headers), ``files_modified`` (absolute), ``resolved_path``,
  ``no_change`` for an edit already present, ``error`` on failure.
* ``patch`` V4A mode - args ``mode="patch"``, ``patch`` (``*** Update|Add|
  Delete|Move File:`` sections). Result JSON as above, with one diff section
  per file, ``files_modified`` holding every resolved path and
  ``files_created`` / ``files_deleted``.
* ``execute_code``'s ``hermes_tools.write_file`` / ``patch`` dispatch through
  ``handle_function_call``, so they reach ``post_tool_call`` as the same
  tool names. There is no notebook or multi-edit tool.

Terminal/shell commands (``terminal``, ``execute_code`` scripts writing files
directly) are **not** captured, like upstream.

Capture rules: only ``status == "ok"`` calls whose parsed result carries no
``error``, is not ``no_change`` and is not ``success: false``. Paths come from
the result's ``files_modified`` / ``resolved_path`` (Hermes resolved them
against the task's live terminal cwd, the session cwd override or
``TERMINAL_CWD``); only when the result is unparsable is ``args["path"]``
used, resolved against an absolute ``TERMINAL_CWD`` else ``os.getcwd()`` of
the hook process (which ignores a terminal ``cd``: a documented limit).

Line counts are computed at capture time and only the numbers are kept:
``patch`` from the unified diff in the result (hunk-length aware, so a
content line starting with ``+++`` or a missing final newline cannot skew
it), falling back to ``old_string``/``new_string`` or the V4A ``+``/``-``
lines; ``write_file`` counts the written lines as added and marks removed as
unknown (an overwrite's old content is never seen).

Privacy: entries hold the path, counts, tool name, timestamps, attribution
(``main`` or the subagent id, plus its role), session id and platform. File
content, diffs, ``old_string``/``new_string``/``patch`` text and results are
never stored or shown.

Storage: schema ``hermes-odd.changes/v1`` under the ``ctx.state`` key
``changes.v1``, with the same fallback and concurrency model as
:mod:`hermes_odd.agents`. Bounds: 200 files (least recently changed dropped
first), entries not changed for 7 days dropped, 12 timeline entries and 5
attributions per file.
"""

from __future__ import annotations

import copy
import difflib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import MemoryBackend, truncate
from .projects import git_root

logger = logging.getLogger("hermes_odd")

SCHEMA = "hermes-odd.changes/v1"
STATE_KEY = "changes.v1"

FILE_TOOLS = frozenset({"write_file", "patch"})
MAX_FILES = 200
MAX_TIMELINE = 12
MAX_ATTRIBUTION = 5
RETENTION_SECONDS = 7 * 24 * 3600
PATH_MAX_CHARS = 4096
ID_MAX_CHARS = 128
ROLE_MAX_CHARS = 40
MAX_RESULT_CHARS = 4 * 1024 * 1024
MAX_TARGETS = 50
GIT_TIMEOUT_SECONDS = 2.0
MAIN = "main"

_TERMINAL_CWD_SENTINELS = frozenset({"", ".", "./", "auto", "cwd"})
_HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_V4A_FILE_RE = re.compile(r"^\*\*\*\s*(Update|Add|Delete)\s+File:\s*(.+?)\s*$")


@dataclass(frozen=True)
class FileOp:
    """One captured mutation of one file (numbers only)."""

    path: str
    added: int
    removed: int | None  # None: unknown (write_file overwrite)


# -- line counting ---------------------------------------------------------


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_lines(text: Any) -> list[str]:
    """Split on ``\\n`` / ``\\r\\n`` / ``\\r``; a trailing newline adds no line."""
    if not isinstance(text, str) or not text:
        return []
    lines = _normalize_newlines(text).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def count_lines(text: Any) -> int:
    return len(split_lines(text))


def count_replace(old: Any, new: Any) -> tuple[int, int]:
    """``(added, removed)`` lines turning ``old`` into ``new`` (line diff)."""
    a, b = split_lines(old), split_lines(new)
    added = removed = 0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def _diff_header_path(raw: str) -> str | None:
    value = raw.split("\t", 1)[0].strip()
    if not value or value == "/dev/null":
        return None
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value or None


def parse_unified_diff(text: Any) -> list[tuple[str, int, int]]:
    """Per-file ``(path, added, removed)`` from a unified diff. Never raises.

    Counts come from the hunk header lengths minus the context lines, and a
    hunk is consumed by those lengths, so content lines that look like
    headers and ``difflib``'s missing-final-newline joins are handled.
    """
    if not isinstance(text, str) or not text:
        return []
    lines = _normalize_newlines(text).split("\n")
    sections: list[list[Any]] = []
    current: list[Any] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old = _diff_header_path(line[4:])
            new = _diff_header_path(lines[i + 1][4:])
            path = new if new is not None else old
            current = [path or "", 0, 0] if path else None
            if current is not None:
                sections.append(current)
            i += 2
            continue
        match = _HUNK_RE.match(line)
        if match and current is not None:
            old_len = int(match.group(1)) if match.group(1) is not None else 1
            new_len = int(match.group(2)) if match.group(2) is not None else 1
            old_left, new_left, context = old_len, new_len, 0
            i += 1
            while i < len(lines) and (old_left > 0 or new_left > 0):
                body = lines[i]
                if body.startswith(" ") and old_left > 0 and new_left > 0:
                    context += 1
                    old_left -= 1
                    new_left -= 1
                elif body.startswith("-") and old_left > 0:
                    old_left -= 1
                elif body.startswith("+") and new_left > 0:
                    new_left -= 1
                elif body.startswith("\\"):
                    pass
                else:
                    break
                i += 1
            current[1] += max(0, new_len - context)
            current[2] += max(0, old_len - context)
            continue
        i += 1
    return [(str(p), int(a), int(r)) for p, a, r in sections]


def parse_v4a(text: Any) -> list[tuple[str, int, int | None]]:
    """Per-file ``(path, added, removed)`` from V4A patch args (fallback)."""
    if not isinstance(text, str) or not text:
        return []
    sections: list[list[Any]] = []
    current: list[Any] | None = None
    for line in _normalize_newlines(text).split("\n"):
        match = _V4A_FILE_RE.match(line)
        if match:
            removed: int | None = None if match.group(1) == "Delete" else 0
            current = [match.group(2), 0, removed]
            sections.append(current)
        elif line.startswith("***") and not line.startswith(("*** End of File", "*** Move to")):
            current = None  # End Patch, Move File: no counted lines
        elif current is not None and line.startswith("+"):
            current[1] += 1
        elif current is not None and line.startswith("-") and current[2] is not None:
            current[2] += 1
    return [(str(p), int(a), r) for p, a, r in sections]


# -- paths -----------------------------------------------------------------


def _fallback_base(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    raw = str(env.get("TERMINAL_CWD", "") or "").strip()
    if raw.lower() not in _TERMINAL_CWD_SENTINELS:
        expanded = os.path.expanduser(raw)
        if os.path.isabs(expanded):
            return expanded
    return os.getcwd()


def normalize_path(raw: Any, base: str | None = None) -> str | None:
    """Absolute, normalized path (no symlink resolution); ``None`` if unusable."""
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value or len(value) > PATH_MAX_CHARS or "\0" in value or "\n" in value:
        return None
    value = os.path.expanduser(value)
    if not os.path.isabs(value):
        try:
            value = os.path.join(base if base is not None else _fallback_base(), value)
        except OSError:
            return None
    return os.path.normpath(value)


def _same_or_suffix(target: str, candidate: str) -> bool:
    if not candidate:
        return False
    if os.path.isabs(candidate):
        return os.path.normpath(candidate) == target
    tail = os.path.normpath(candidate)
    if tail in (".", "") or tail.startswith(".." + os.sep) or tail == "..":
        return False
    return target == tail or target.endswith(os.sep + tail)


def locate(path: str) -> tuple[str, str, bool]:
    """``(root, rel, in_git)`` for an absolute file path. Never raises.

    ``root`` is the git top-level of the file's own directory (nearest
    ancestor holding ``.git``, no subprocess); outside git it is the file's
    directory and ``rel`` its name.
    """
    parent = os.path.dirname(path) or path
    probe = parent
    for _ in range(64):
        if os.path.isdir(probe):
            break
        up = os.path.dirname(probe)
        if up == probe:
            break
        probe = up
    root_path = git_root(probe) if os.path.isdir(probe) else None
    if root_path is None or not (root_path / ".git").exists():
        return parent, os.path.basename(path), False
    root = str(root_path)
    try:
        # git_root resolves symlinks (e.g. /var -> /private/var); match it.
        real = os.path.join(str(Path(probe).resolve()), os.path.relpath(path, probe))
    except (OSError, RuntimeError, ValueError):
        real = path
    rel = os.path.relpath(os.path.normpath(real), root)
    if rel.startswith(".."):
        rel = os.path.basename(path)
    return root, rel, True


# -- operation extraction ----------------------------------------------------


def _parse_result(result: Any) -> dict[str, Any] | None:
    if isinstance(result, Mapping):
        return dict(result)
    if isinstance(result, str) and result and len(result) <= MAX_RESULT_CHARS:
        try:
            parsed = json.loads(result)
        except (ValueError, RecursionError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _result_targets(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    raw: list[Any] = []
    modified = result.get("files_modified")
    if isinstance(modified, list):
        raw.extend(modified)
    raw.append(result.get("resolved_path"))
    targets: list[str] = []
    for item in raw:
        if not isinstance(item, str) or " -> " in item or not os.path.isabs(item):
            continue
        path = normalize_path(item)
        if path and path not in targets:
            targets.append(path)
    return targets[:MAX_TARGETS]


def extract_operations(tool: str, args: Mapping[str, Any], result: Any) -> list[FileOp]:
    """The files one successful call changed, with line counts. Never stores text."""
    parsed = _parse_result(result)
    if parsed is not None and (
        parsed.get("error") or parsed.get("no_change") or parsed.get("success") is False
    ):
        return []
    targets = _result_targets(parsed)
    if tool == "write_file":
        path = targets[0] if targets else normalize_path(args.get("path"))
        return [FileOp(path, count_lines(args.get("content")), None)] if path else []
    if tool != "patch":
        return []
    mode = args.get("mode") or "replace"
    diff_stats = parse_unified_diff(parsed.get("diff")) if parsed else []
    if mode == "patch":
        arg_stats = parse_v4a(args.get("patch"))
        if not targets:
            targets = [p for p in (normalize_path(s[0]) for s in arg_stats) if p]
    else:
        added, removed = count_replace(args.get("old_string"), args.get("new_string"))
        arg_stats = [(str(args.get("path") or ""), added, removed)]
        if not targets:
            path = normalize_path(args.get("path"))
            targets = [path] if path else []
    ops: list[FileOp] = []
    for target in targets[:MAX_TARGETS]:
        stat: tuple[str, int, int | None] | None = None
        for candidate in diff_stats:
            if _same_or_suffix(target, candidate[0]):
                stat = candidate
                break
        if stat is None and len(targets) == 1 and len(diff_stats) == 1:
            stat = diff_stats[0]
        if stat is None:
            for candidate in arg_stats:
                if _same_or_suffix(target, candidate[0]) or (
                    len(targets) == 1 and len(arg_stats) == 1
                ):
                    stat = candidate
                    break
        added, removed = (stat[1], stat[2]) if stat is not None else (0, 0)
        ops.append(FileOp(target, added, removed))
    return ops


# -- git numstat (read-only, bounded) ---------------------------------------


@dataclass(frozen=True)
class NumstatResult:
    state: str  # "ok" | "clean" | "binary" | "no_git" | "not_repo" | "timeout" | "failed"
    added: int = 0
    removed: int = 0


def _git_env() -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
    }
    home = os.environ.get("HOME")
    if home:
        env["HOME"] = home  # for safe.directory in the user's git config
    return env


def git_numstat(root: str, rel: str, in_git: bool = True) -> NumstatResult:
    """Uncommitted (working tree vs index) numstat of one file. Never raises.

    Runs ``git -C <root> diff --numstat -- <rel>`` without a shell, with a
    minimal environment and a hard 2 s timeout; external diff drivers,
    textconv and fsmonitor are disabled. Only the two numbers are read.
    """
    if not in_git or not os.path.exists(os.path.join(root, ".git")):
        return NumstatResult("not_repo")
    git = shutil.which("git")
    if not git:
        return NumstatResult("no_git")
    command = [
        git,
        "-c",
        "core.fsmonitor=false",
        "-C",
        root,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--numstat",
        "--",
        rel,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=_git_env(),
            stdin=subprocess.DEVNULL,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return NumstatResult("timeout")
    except (OSError, ValueError, subprocess.SubprocessError):
        return NumstatResult("failed")
    if completed.returncode != 0:
        return NumstatResult("failed")
    first = (completed.stdout or "").strip().split("\n", 1)[0]
    if not first:
        return NumstatResult("clean")
    parts = first.split("\t")
    if len(parts) < 2:
        return NumstatResult("failed")
    if parts[0] == "-" and parts[1] == "-":
        return NumstatResult("binary")
    try:
        return NumstatResult("ok", int(parts[0]), int(parts[1]))
    except ValueError:
        return NumstatResult("failed")


# -- store -------------------------------------------------------------------


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value == value and value >= 0 else None


def _clean_id(value: Any) -> str:
    return value.strip()[:ID_MAX_CHARS] if isinstance(value, str) else ""


def _empty_document() -> dict[str, Any]:
    return {"schema": SCHEMA, "files": []}


class ChangeStore:
    """Bounded store of changed files plus the ``post_tool_call`` handler."""

    def __init__(
        self,
        backend: Any | None = None,
        clock: Callable[[], float] = time.time,
        agent_store: Any | None = None,
    ):
        self._backend = backend if backend is not None else MemoryBackend()
        self._fallback = MemoryBackend()
        self._using_fallback = False
        self._clock = clock
        self._agents = agent_store
        self._lock = threading.RLock()

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
        files = doc.get("files")
        doc["files"] = [
            f
            for f in (files if isinstance(files, list) else [])
            if isinstance(f, dict) and isinstance(f.get("path"), str)
        ]
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
            logger.warning("hermes-odd: change state unavailable (%s); using memory", exc)
            try:
                current = self._backend.get(STATE_KEY, None)
            except Exception:  # noqa: BLE001
                current = None
            if isinstance(current, dict):
                self._fallback.set(STATE_KEY, current)
        self._using_fallback = True

    @staticmethod
    def _prune(files: list[dict[str, Any]], now: float) -> bool:
        keep = [f for f in files if now - (_number(f.get("last_at")) or 0.0) <= RETENTION_SECONDS]
        changed = len(keep) != len(files)
        if len(keep) > MAX_FILES:
            keep.sort(key=lambda f: _number(f.get("last_at")) or 0.0)
            del keep[: len(keep) - MAX_FILES]
            changed = True
        files[:] = keep
        return changed

    # -- reads -------------------------------------------------------------

    def files(self) -> list[dict[str, Any]]:
        """Pruned entries, most recently changed first."""
        with self._lock:
            doc = self._load()
            if self._prune(doc["files"], self._clock()):
                self._save(doc)
            files = copy.deepcopy(doc["files"])
        files.sort(key=lambda f: _number(f.get("last_at")) or 0.0, reverse=True)
        return files

    def now(self) -> float:
        return self._clock()

    def agent(self, subagent_id: str) -> dict[str, Any] | None:
        """T3 agent record for enrichment (role, goal), when available."""
        lookup = getattr(self._agents, "lookup", None)
        if not callable(lookup) or not subagent_id or subagent_id == MAIN:
            return None
        try:
            record = lookup(subagent_id)
        except Exception:  # noqa: BLE001
            return None
        return record if isinstance(record, dict) else None

    def clear(self) -> int:
        """Forget every recorded change; return how many files were cleared."""
        with self._lock:
            count = len(self._load()["files"])
            self._save(_empty_document())
        return count

    # -- capture -----------------------------------------------------------

    def _attribution(self, task_id: str) -> tuple[str, str]:
        if not task_id:
            return MAIN, ""
        is_child = task_id.startswith(("sa-", "sx-"))
        if not is_child:
            active = getattr(self._agents, "is_active", None)
            try:
                is_child = bool(callable(active) and active(task_id))
            except Exception:  # noqa: BLE001
                is_child = False
        if not is_child:
            return MAIN, ""
        record = self.agent(task_id)
        role = truncate(record.get("role"), ROLE_MAX_CHARS) if record else ""
        return task_id, role

    def _platform(self, session_id: str) -> str:
        platform_for = getattr(self._agents, "platform_for", None)
        if not callable(platform_for) or not session_id:
            return ""
        try:
            return truncate(platform_for(session_id), 32)
        except Exception:  # noqa: BLE001
            return ""

    def record(
        self,
        tool: str,
        ops: list[FileOp],
        task_id: str = "",
        session_id: str = "",
    ) -> int:
        """Record captured operations; return how many files were updated."""
        if not ops:
            return 0
        by, role = self._attribution(task_id)
        platform = self._platform(session_id)
        located = [(op, *locate(op.path)) for op in ops]
        with self._lock:
            doc = self._load()
            now = self._clock()
            files = doc["files"]
            index = {f["path"]: f for f in files}
            for op, root, rel, in_git in located:
                entry = index.get(op.path)
                if entry is None:
                    entry = {
                        "path": op.path,
                        "root": root,
                        "rel": rel,
                        "in_git": in_git,
                        "ops": 0,
                        "added": 0,
                        "removed": 0,
                        "removed_unknown": False,
                        "first_at": now,
                        "last_at": now,
                        "last_tool": tool,
                        "by": [],
                        "session_id": "",
                        "platform": "",
                        "timeline": [],
                    }
                    files.append(entry)
                    index[op.path] = entry
                entry["ops"] = int(_number(entry.get("ops")) or 0) + 1
                entry["added"] = int(_number(entry.get("added")) or 0) + op.added
                if op.removed is None:
                    entry["removed_unknown"] = True
                else:
                    entry["removed"] = int(_number(entry.get("removed")) or 0) + op.removed
                entry["last_at"] = now
                entry["last_tool"] = tool
                entry["root"], entry["rel"], entry["in_git"] = root, rel, in_git
                if session_id:
                    entry["session_id"] = session_id
                if platform:
                    entry["platform"] = platform
                attribution = [a for a in entry.get("by") or [] if isinstance(a, dict)]
                for item in attribution:
                    if item.get("id") == by:
                        item["ops"] = int(_number(item.get("ops")) or 0) + 1
                        item["last_at"] = now
                        if role:
                            item["role"] = role
                        break
                else:
                    attribution.append({"id": by, "role": role, "ops": 1, "last_at": now})
                attribution.sort(key=lambda a: _number(a.get("last_at")) or 0.0)
                entry["by"] = attribution[-MAX_ATTRIBUTION:]
                timeline = [e for e in entry.get("timeline") or [] if isinstance(e, dict)]
                timeline.append(
                    {"at": now, "tool": tool, "added": op.added, "removed": op.removed, "by": by}
                )
                entry["timeline"] = timeline[-MAX_TIMELINE:]
            self._prune(files, now)
            self._save(doc)
        return len(located)

    def on_post_tool_call(self, **kwargs: Any) -> None:
        """``post_tool_call`` observer. Fast path for non-file tools; never raises."""
        try:
            tool = kwargs.get("tool_name")
            if tool not in FILE_TOOLS:
                return
            if kwargs.get("status") != "ok":
                return
            args = kwargs.get("args")
            ops = extract_operations(
                tool, args if isinstance(args, Mapping) else {}, kwargs.get("result")
            )
            if ops:
                self.record(
                    tool,
                    ops,
                    task_id=_clean_id(kwargs.get("task_id")),
                    session_id=_clean_id(kwargs.get("session_id")),
                )
        except Exception:  # noqa: BLE001 - hooks never raise
            logger.debug("hermes-odd changes post_tool_call failed", exc_info=True)


def register_change_hooks(ctx: Any, store: ChangeStore) -> bool:
    """Register the change observer as its own ``post_tool_call`` callback.

    Hermes keeps a list of callbacks per hook (``register_hook`` appends), and
    ``invoke_hook`` bounds, skips-while-running and suppresses after a
    timeout **per callback**; a separate callback keeps change capture and
    subagent tracking independent. Never raises.
    """
    register_hook = getattr(ctx, "register_hook", None)
    if not callable(register_hook):
        logger.warning("hermes-odd: ctx.register_hook is unavailable; /odd_changes stays empty")
        return False
    try:
        register_hook("post_tool_call", store.on_post_tool_call)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: could not register the change hook: %s", exc)
        return False
    return True
