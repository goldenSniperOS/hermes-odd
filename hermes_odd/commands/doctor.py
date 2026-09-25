"""``/odd_doctor``: read-only health report (Pi ``gentle:doctor``).

Concept port of gentle-shell's ``gentle:doctor`` (``extensions/gentle-ai.ts``):
one line per check with a pass/warn/fail mark and a remedy when it is not a
pass. The checks are Hermes-specific (gentle-ai binary, RDD mode, SOUL.md
truncation, the plugin's own surface, the upstream lock, Hermes itself); no
upstream code or text is copied. Nothing here writes outside the plugin's own
``ctx.state`` probe key, runs ``gentle-ai install``/``sync``, or reads
``.env``/``auth.json``. Output is plain text under :data:`OUTPUT_MAX_CHARS`.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import soul as soul_mod
from .. import upstream as upstream_mod
from ..probes import BinaryInfo, Prober, ReviewMode, is_below, parse_version, process_repo
from ..prompt import SECTION_ID, SECTION_MAX_CHARS
from ..runtime import RuntimeInfo
from .registry import CommandSpec
from .tasks import path_tail

OUTPUT_MAX_CHARS = 3500
TOTAL_BUDGET_SECONDS = 6.0
PLUGIN_SECTIONS_TOTAL_CHARS = 8000
LOCK_STALE_DAYS = 30
STATE_PROBE_KEY = "doctor.probe"
MAX_LISTED_BLOCKS = 8

OK, WARN, FAIL = "ok", "warn", "fail"
GLYPHS = {OK: "✓", WARN: "⚠", FAIL: "✗"}

BINARY_RULE = (
    "Binary only: never run `gentle-ai install` for Hermes or `gentle-ai sync --agent hermes`."
)
UPGRADE_HINT = "brew upgrade gentleman-programming/tap/gentle-ai"
INSTALL_HINT = "brew install gentleman-programming/tap/gentle-ai"
SOUL_HINT = (
    "hermes-odd already supplies ODD through its prompt section; the SOUL.md "
    "migration (strip gentle-ai blocks, with backup and dry-run) arrives in T9 "
    "as /odd_soul. Until then trim SOUL.md by hand or pin context_file_max_chars."
)


@dataclass(frozen=True)
class Check:
    level: str
    name: str
    finding: str
    hint: str = ""

    def render(self) -> str:
        line = f"{GLYPHS.get(self.level, '?')}  {self.name}: {self.finding}"
        if self.level != OK and self.hint:
            line += f"\n   fix: {self.hint}"
        return line


def display_path(path: Any) -> str:
    """``~/rel`` under the home directory; short system paths (two components,
    such as ``/usr/bin``) as is; anything deeper as a tail of at most three
    components that always drops the first directory, so a gateway reply never
    carries a full path (``/tmp/x/SOUL.md`` -> ``…/x/SOUL.md``)."""
    try:
        p = Path(str(path))
        home = Path(os.path.expanduser("~"))
        try:
            rel = p.relative_to(home)
            return "~" if str(rel) == "." else f"~/{rel}"
        except ValueError:
            depth = len([part for part in p.parts if part not in ("/", "\\")])
            if depth <= 2:
                return str(p)  # short system paths such as /usr/bin carry nothing private
            return path_tail(p, min(3, depth - 1))
    except Exception:  # noqa: BLE001
        return "?"


def _k(chars: int) -> str:
    return f"{chars / 1000:.1f}k" if chars >= 1000 else str(chars)


def _ctx_label(tokens: int) -> str:
    return f"{tokens // 1_000_000}M" if tokens % 1_000_000 == 0 else f"{tokens // 1000}k"


# -- 1. gentle-ai binary ---------------------------------------------------


def _info_label(info: BinaryInfo) -> str:
    return info.version or {"timeout": "version timed out", "unparsed": "version unreadable"}.get(
        info.state, "version failed"
    )


def check_binary(
    prober: Prober, minimum: str | None, timeout: float
) -> tuple[Check, BinaryInfo | None]:
    paths = prober.binaries()
    if not paths:
        return (
            Check(
                FAIL,
                "gentle-ai binary",
                f"not found on PATH (RDD needs gentle-ai >= {minimum or '?'})",
                f"install the binary: {INSTALL_HINT}. {BINARY_RULE}",
            ),
            None,
        )
    infos = prober.versions(paths, timeout)
    first = infos[0]
    finding = f"{_info_label(first)} at {display_path(first.path)} (min {minimum or '?'})"
    others = [f"{display_path(i.path)} {_info_label(i)}" for i in infos[1:]]
    if others:
        finding += "; also on PATH: " + ", ".join(others)
    known = {i.version for i in infos if i.version}
    newer = [
        i for i in infos[1:] if i.version and first.version and is_below(first.version, i.version)
    ]
    below = is_below(first.version, minimum)
    hints = []
    if newer:
        hints.append(
            f"{display_path(first.path)} shadows a newer {newer[0].version} at "
            f"{display_path(newer[0].path)}: remove the stale one or put the newer first on PATH"
        )
    if below:
        hints.append(f"upgrade: {UPGRADE_HINT}")
        if len(infos) > 1 and not newer:
            hints.append(f"{display_path(first.path)} runs first; remove it if it is a stale copy")
    if below:
        level = FAIL
    elif first.version is None or len(known) > 1:
        level = WARN
        if first.version is None:
            hints.append("check that `gentle-ai version` runs")
        elif not newer:
            hints.append("several different gentle-ai binaries are on PATH; keep one")
    else:
        level = OK
    hint = "; ".join(hints)
    return Check(
        level, "gentle-ai binary", finding, f"{hint}. {BINARY_RULE}" if hint else ""
    ), first


# -- 2. RDD mode -----------------------------------------------------------


def review_mode_text(mode: ReviewMode | None) -> str:
    """``on (decided by global) · repo``; wording follows gentle-ai's own
    ``receipt-driven development: <effective> (decided by <source>)``."""
    if mode is None:
        return "unknown"
    name = Path(mode.repo).name if mode.repo else ""
    if mode.state == "ok":
        source = f" (decided by {mode.source[:20]})" if mode.source else ""
        return f"{mode.effective}{source}" + (f" · {name}" if name else "")
    reason = {
        "no_repo": "not in a git repository",
        "no_binary": "gentle-ai missing",
        "timeout": "gentle-ai timed out",
    }.get(mode.state, "gentle-ai review mode status failed")
    return f"unknown ({reason})"


def check_review_mode(
    prober: Prober, binary: BinaryInfo | None, repo: Path | None, timeout: float
) -> Check:
    if timeout <= 0.1:
        return Check(WARN, "RDD mode", "unknown (time budget spent)", "run /odd_doctor again")
    mode = prober.review_mode(binary.path if binary else None, repo, timeout)
    text = review_mode_text(mode)
    if mode.state == "ok":
        return Check(OK, "RDD mode", f"receipt-driven development {text}")
    if mode.state == "no_repo":
        hint = (
            "the command process is not inside a git repository (gateways run from "
            "their launch directory); run /odd_doctor from the CLI inside the project"
        )
    elif mode.state == "no_binary":
        hint = "install gentle-ai (see the binary check)"
    else:
        hint = "run `gentle-ai review mode status` in the repository to see the error"
    return Check(WARN, "RDD mode", text, hint)


# -- 3. SOUL.md ------------------------------------------------------------


def _blocks_text(report: soul_mod.SoulReport) -> str:
    top = [b for b in report.blocks if b.depth == 0]
    parts = [f"{b.name} {_k(b.size)}" + ("" if b.closed else " unclosed") for b in top]
    more = len(parts) - MAX_LISTED_BLOCKS
    text = ", ".join(parts[:MAX_LISTED_BLOCKS])
    return text + (f", … {more} more" if more > 0 else "")


def _lost_text(report: soul_mod.SoulReport, cap: int) -> str:
    lost = soul_mod.dropped_blocks(report.blocks, report.chars, cap)
    if not lost:
        return "no managed block lost"
    names = [f"{b.name}{'' if how == 'dropped' else ' (partly)'}" for b, how in lost]
    more = len(names) - MAX_LISTED_BLOCKS
    return (
        "loses " + ", ".join(names[:MAX_LISTED_BLOCKS]) + (f", … {more} more" if more > 0 else "")
    )


def check_soul(home: Path, context: soul_mod.ModelContext | None = None) -> Check:
    report = soul_mod.read_soul(home)
    where = display_path(report.path)
    if not report.exists:
        return Check(OK, "SOUL.md", f"none at {where} (nothing to truncate)")
    if report.error:
        return Check(
            WARN, "SOUL.md", f"{where} unreadable ({report.error})", "check its permissions"
        )
    ctx = context if context is not None else soul_mod.model_context(home)
    finding = f"{where} {report.chars:,} chars (~{_k(report.tokens)} tokens)"
    if report.blocks:
        managed = [b for b in report.blocks if b.depth == 0]
        finding += (
            f"; {len(managed)} gentle-ai blocks {_k(report.managed_chars)}: {_blocks_text(report)}"
        )
    truncated = False
    if ctx.pinned_cap or ctx.context_length:
        cap = soul_mod.truncation_cap(ctx.context_length, ctx.pinned_cap)
        if ctx.pinned_cap:
            basis = "context_file_max_chars"
        else:
            basis = f"{ctx.model or 'model'} {_ctx_label(ctx.context_length)} ({ctx.source})"
        if report.chars > cap:
            truncated = True
            finding += f". Cap {cap:,} ({basis}): truncated, {_lost_text(report, cap)}"
        else:
            finding += f". Cap {cap:,} ({basis}): fits"
    else:
        cells = []
        smallest_cut = None
        for tokens in soul_mod.REFERENCE_CONTEXTS:
            cap = soul_mod.truncation_cap(tokens)
            cut = report.chars > cap
            cells.append(f"{_ctx_label(tokens)} {cap:,} {'✗' if cut else '✓'}")
            if cut and smallest_cut is None:
                smallest_cut = (tokens, cap)
        finding += ". Model context unknown; cap " + " | ".join(cells)
        if smallest_cut is not None:
            truncated = True
            finding += f"; at {_ctx_label(smallest_cut[0])} {_lost_text(report, smallest_cut[1])}"
    if truncated:
        return Check(WARN, "SOUL.md", finding, SOUL_HINT)
    if report.blocks:
        return Check(
            WARN,
            "SOUL.md",
            finding + " (sent with every message)",
            SOUL_HINT,
        )
    return Check(OK, "SOUL.md", finding)


# -- 4. plugin surface -----------------------------------------------------


def probe_state(ctx: Any, clock: Callable[[], float] = time.time) -> str:
    """Write, read back and restore one probe key. ``ok`` | ``memory`` | ``failed: <type>``."""
    state = getattr(ctx, "state", None) if ctx is not None else None
    if not (callable(getattr(state, "get", None)) and callable(getattr(state, "set", None))):
        return "memory"
    try:
        previous = state.get(STATE_PROBE_KEY, None)
        token = {"at": clock()}
        state.set(STATE_PROBE_KEY, token)
        ok = state.get(STATE_PROBE_KEY, None) == token
        state.set(STATE_PROBE_KEY, previous)
    except Exception as exc:  # noqa: BLE001
        return f"failed: {type(exc).__name__}"
    return "ok" if ok else "failed: read-back mismatch"


def check_plugin(runtime: RuntimeInfo | None) -> Check:
    if runtime is None:
        return Check(WARN, "plugin surface", "not registered through register(ctx)", "")
    level = OK
    hints = []
    if runtime.section_registered:
        section = f"section {SECTION_ID} {runtime.section_chars}/{SECTION_MAX_CHARS}"
        if runtime.section_chars > SECTION_MAX_CHARS:
            level = FAIL
            hints.append("the section is over 4000 chars and Hermes skips it: update hermes-odd")
    else:
        section = f"section {SECTION_ID} NOT registered"
        level = FAIL
        hints.append("check the Hermes log for 'hermes-odd' warnings")
    section += f" (all plugins share {PLUGIN_SECTIONS_TOTAL_CHARS})"
    skills = f"skills {len(runtime.skills)} ({runtime.skills_layout()})"
    if not runtime.skills:
        level = FAIL if level == FAIL else WARN
        hints.append("no skills registered: reinstall hermes-odd")
    hooks = f"hooks {runtime.hooks_registered}/{runtime.hooks_expected}"
    if runtime.hooks_registered < runtime.hooks_expected:
        level = FAIL if level == FAIL else WARN
        hints.append("some hooks failed to register: /odd_agents and /odd_changes may stay empty")
    state = probe_state(runtime.ctx)
    fallback = runtime.fallback_stores()
    if state == "ok" and not fallback:
        state_text = "state ok (write+read)"
    else:
        level = FAIL if level == FAIL else WARN
        if state == "memory":
            state_text = "state in memory (ctx.state unavailable)"
        else:
            state_text = f"state {state}"
        if fallback:
            state_text += f"; memory fallback active for {', '.join(fallback)}"
        hints.append("records are lost on restart; check <HERMES_HOME>/plugin-data permissions")
    finding = f"{section}; {skills}; {hooks}; {state_text}"
    return Check(level, "plugin surface", finding, "; ".join(hints))


# -- 5. upstream lock ------------------------------------------------------


def _days_since(date: Any, now: float) -> int | None:
    try:
        when = _dt.datetime.fromisoformat(str(date).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.UTC)
    return max(0, int((now - when.timestamp()) // 86400))


def supported_text(lock: dict[str, Any]) -> str:
    upstreams = lock.get("upstreams") or {}
    parts = []
    for name in ("gentle-ai", "gentle-shell"):
        entry = upstreams.get(name) or {}
        release = entry.get("supported_release", "?")
        commit = str(entry.get("pinned_commit", ""))[:7]
        parts.append(f"{name} {release}" + (f" @{commit}" if commit else ""))
    return " · ".join(parts)


def check_lock(loader: Callable[[], dict[str, Any]], now: float) -> tuple[Check, dict | None]:
    try:
        lock = loader()
    except FileNotFoundError:
        return Check(FAIL, "upstream lock", "missing", "reinstall hermes-odd"), None
    except (ValueError, OSError) as exc:
        return Check(FAIL, "upstream lock", f"invalid ({type(exc).__name__})", "reinstall"), None
    days = [
        d
        for d in (
            _days_since((lock.get("upstreams") or {}).get(n, {}).get("commit_date"), now)
            for n in ("gentle-ai", "gentle-shell")
        )
        if d is not None
    ]
    age = max(days) if days else None
    finding = f"schema ok; {supported_text(lock)}"
    finding += f"; pinned {age} d ago" if age is not None else "; pin date unknown"
    if age is not None and age > LOCK_STALE_DAYS:
        return (
            Check(
                WARN,
                "upstream lock",
                finding,
                "run the sync procedure in upstream/SUPPORTED.md (How to sync with upstream)",
            ),
            lock,
        )
    return Check(OK, "upstream lock", finding), lock


# -- 6. Hermes -------------------------------------------------------------


def hermes_version() -> str | None:
    module = sys.modules.get("hermes_cli")
    version = getattr(module, "__version__", None) if module is not None else None
    if isinstance(version, str) and version:
        return version
    try:
        from importlib import metadata

        return metadata.version("hermes-agent")
    except Exception:  # noqa: BLE001
        return None


def plugin_enabled(ctx: Any) -> bool | None:
    has_plugin = getattr(ctx, "has_plugin", None) if ctx is not None else None
    plugin_id = getattr(ctx, "plugin_id", None) if ctx is not None else None
    if not callable(has_plugin) or not isinstance(plugin_id, str):
        return None
    try:
        return bool(has_plugin(plugin_id))
    except Exception:  # noqa: BLE001
        return None


def check_hermes(runtime: RuntimeInfo | None, version_of: Callable[[], str | None]) -> Check:
    from .. import __version__

    version = version_of()
    enabled = plugin_enabled(runtime.ctx if runtime else None)
    state = {True: "enabled", False: "not enabled", None: "enabled state unknown"}[enabled]
    finding = f"Hermes {version or 'version unknown'}; hermes-odd {__version__} {state}"
    if enabled is False:
        return Check(WARN, "Hermes", finding, "enable it: hermes plugins enable hermes-odd")
    return Check(OK, "Hermes", finding)


# -- report ----------------------------------------------------------------


def fit(text: str, limit: int = OUTPUT_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = len(text) - (limit - 40)
    return text[: limit - 40].rstrip() + f"\n… {cut} more characters"


class Doctor:
    """Runs the checks with injectable probes (tests replace every seam)."""

    def __init__(
        self,
        runtime: RuntimeInfo | None = None,
        prober: Prober | None = None,
        *,
        home: Callable[[], Path] = soul_mod.hermes_home,
        repo: Callable[[], Path | None] = process_repo,
        lock_loader: Callable[[], dict[str, Any]] = upstream_mod.load_lock,
        version_of: Callable[[], str | None] = hermes_version,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
        model_context: Callable[[Path], soul_mod.ModelContext] = soul_mod.model_context,
    ):
        self.runtime = runtime
        self.prober = prober if prober is not None else Prober()
        self._home = home
        self._repo = repo
        self._lock_loader = lock_loader
        self._version_of = version_of
        self._clock = clock
        self._monotonic = monotonic
        self._model_context = model_context

    def minimum(self) -> str | None:
        try:
            return upstream_mod.min_gentle_ai_version(self._lock_loader())
        except Exception:  # noqa: BLE001
            return None

    def checks(self) -> list[Check]:
        started = self._monotonic()

        def remaining() -> float:
            return TOTAL_BUDGET_SECONDS - (self._monotonic() - started)

        results: list[Check] = []
        guarded: list[tuple[str, Callable[[], Check]]] = []
        first: list[BinaryInfo | None] = [None]

        def binary() -> Check:
            check, first[0] = check_binary(self.prober, self.minimum(), min(3.0, remaining()))
            return check

        def home() -> Path:
            return Path(self._home())

        guarded.append(("gentle-ai binary", binary))
        guarded.append(
            (
                "RDD mode",
                lambda: check_review_mode(
                    self.prober, first[0], self._repo(), min(3.0, remaining())
                ),
            )
        )
        guarded.append(("SOUL.md", lambda: check_soul(home(), self._model_context(home()))))
        guarded.append(("plugin surface", lambda: check_plugin(self.runtime)))
        guarded.append(("upstream lock", lambda: check_lock(self._lock_loader, self._clock())[0]))
        guarded.append(("Hermes", lambda: check_hermes(self.runtime, self._version_of)))
        for name, run in guarded:
            try:
                results.append(run())
            except Exception as exc:  # noqa: BLE001 - one check never breaks the report
                results.append(Check(WARN, name, f"check failed ({type(exc).__name__})", ""))
        return results

    def render(self) -> str:
        checks = self.checks()
        counts = {level: sum(1 for c in checks if c.level == level) for level in GLYPHS}
        lines = [
            "hermes-odd doctor (read-only)",
            f"{counts[OK]} ok · {counts[WARN]} warn · {counts[FAIL]} fail",
            "",
        ]
        lines.extend(c.render() for c in checks)
        lines.append("")
        lines.append("Summary: /odd_status")
        return fit("\n".join(lines))


def make_odd_doctor(doctor: Doctor) -> CommandSpec:
    def handler(raw_args: str) -> str:
        return doctor.render()

    return CommandSpec(
        name="odd_doctor",
        description="Read-only health report: gentle-ai binary, RDD mode, SOUL.md, plugin",
        handler=handler,
        group="Health",
    )


__all__ = [
    "Check",
    "Doctor",
    "check_binary",
    "check_hermes",
    "check_lock",
    "check_plugin",
    "check_review_mode",
    "check_soul",
    "display_path",
    "make_odd_doctor",
    "parse_version",
    "probe_state",
    "review_mode_text",
    "supported_text",
]
