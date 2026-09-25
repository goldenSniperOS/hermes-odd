"""First-run setup for hermes-odd: preferences, the setup record and applying them.

Shared by the ``/odd_setup`` command, the ``odd_setup_apply`` tool and the
prompt section. Nothing here calls the model.

Preferences (plugin ``config_schema`` keys, see ``plugin.yaml``):

========================  ==========================================  ============
key                       values                                      default
========================  ==========================================  ============
``persona``               unset, rioplatense, neutral, custom, none  unset
``verbosity``             short, detailed                             short
``tdd_mode``              unset, off, strict, project                 unset
``engram_protocol``       auto, off                                   auto
``soul_cleanup``          unset, yes, later, no                       unset
``codegraph_guidance``    auto, off                                   auto
========================  ==========================================  ============

Storage:

* ``ctx.state`` key ``setup`` holds the setup record, schema
  ``hermes-odd.setup/v1``: ``version``, ``completed_at``, ``skipped``,
  ``answers`` (plus ``custom_text``, the sanitized own persona text, and
  ``source``). **Setup is pending while there is no record**; ``reset``
  clears it.
* ``ctx.set_config`` mirrors every answer to
  ``plugins.entries.hermes-odd.settings.<key>`` in ``config.yaml`` (Hermes
  writes it atomically under a lock). A managed install refuses the write
  (``PermissionError``) and older Hermes versions have no ``set_config``;
  both are reported and the answers stay in plugin state.
* The effective value of a key is ``ctx.get_config(key)`` when it holds a
  valid value (so an edited or administrator-managed ``config.yaml`` wins),
  else the setup record's answer, else the default.

Where each answer is applied: ``persona`` and ``verbosity`` as the single
hermes-odd block at the top of ``SOUL.md`` (:mod:`hermes_odd.soul_persona`);
``tdd_mode`` as one ``TDD mode:`` line in the prompt section;
``engram_protocol`` (``auto``) as one prompt-section line pointing to the
lazy skill ``hermes-odd:engram-protocol``; ``codegraph_guidance`` (``auto``)
as one line pointing to ``hermes-odd:codegraph`` while CodeGraph is present
(a ``codegraph`` binary on ``PATH`` or an ``mcp_servers.codegraph`` entry in
Hermes' ``config.yaml``); ``soul_cleanup`` ``yes`` makes the setup skill
show the ``odd_soul_apply`` dry run and apply it only after the user's
explicit yes (``later``/``no`` change nothing; ``/odd_soul plan`` any time).
Everything takes effect in the next new session, because Hermes builds
``SOUL.md`` and plugin sections into the prompt once per session.
"""

from __future__ import annotations

import datetime as _dt
import logging
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import personas
from . import soul as soul_mod
from . import soul_persona as sp
from .agents import MemoryBackend, resolve_backend

logger = logging.getLogger("hermes_odd")

SCHEMA = "hermes-odd.setup/v1"
STATE_KEY = "setup"
VERSION = 1

PREF_VALUES: dict[str, tuple[str, ...]] = {
    "persona": (personas.UNSET, *personas.PERSONA_CHOICES),
    "verbosity": personas.VERBOSITY_CHOICES,
    "tdd_mode": ("unset", "off", "strict", "project"),
    "engram_protocol": ("auto", "off"),
    "soul_cleanup": ("unset", "yes", "later", "no"),
    "codegraph_guidance": ("auto", "off"),
}
DEFAULTS: dict[str, str] = {
    "persona": personas.UNSET,
    "verbosity": "short",
    "tdd_mode": "unset",
    "engram_protocol": "auto",
    "soul_cleanup": "unset",
    "codegraph_guidance": "auto",
}
PREF_KEYS = tuple(PREF_VALUES)

APPLIED_WHERE = {
    "persona": "SOUL.md: one hermes-odd block at the top",
    "verbosity": "inside the SOUL.md persona block",
    "tdd_mode": "prompt section line 'TDD mode: <mode>'",
    "engram_protocol": "prompt section line pointing to hermes-odd:engram-protocol",
    "soul_cleanup": "/odd_soul: dry-run plan first, written only after an explicit yes",
    "codegraph_guidance": (
        "prompt section line pointing to hermes-odd:codegraph while CodeGraph is present"
    ),
}

NEXT_SESSION_NOTE = (
    "Takes effect in the next new session (/new or a new chat); the current "
    "session keeps the prompt it started with."
)

TDD_LINES = {
    "off": "TDD mode: off (user setup): ordinary functional checks, never no checks.",
    "strict": (
        "TDD mode: strict (user setup): observed RED before implementation, then GREEN, "
        "then REFACTOR; never invent evidence."
    ),
    "project": (
        "TDD mode: per project (user setup): detect the project's TDD config and test "
        "runner; if unclear, ask once."
    ),
}


def utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid(key: str, value: Any) -> bool:
    return isinstance(value, str) and value in PREF_VALUES.get(key, ())


@dataclass
class ConfigWrite:
    """Outcome of mirroring answers into ``config.yaml``."""

    state: str  # "saved" | "refused" | "unavailable" | "failed" | "skipped"
    detail: str = ""
    keys: list[str] = field(default_factory=list)

    def text(self) -> str:
        if self.state == "saved":
            return "config.yaml: saved under plugins.entries.hermes-odd.settings"
        if self.state == "skipped":
            return "config.yaml: nothing to save"
        if self.state == "unavailable":
            return (
                "config.yaml: not updated (this Hermes has no ctx.set_config); kept in plugin state"
            )
        reason = f" ({self.detail})" if self.detail else ""
        return f"config.yaml: not updated{reason}; kept in plugin state"


@dataclass
class ApplyOutcome:
    ok: bool
    lines: list[str]
    error: str = ""
    soul: sp.Result | None = None
    config: ConfigWrite | None = None
    warnings: list[str] = field(default_factory=list)
    persona_recorded: bool = False

    def text(self) -> str:
        return "\n".join(self.lines)


class Setup:
    """Setup record, preferences and application, with injectable seams."""

    def __init__(
        self,
        ctx: Any = None,
        backend: Any | None = None,
        *,
        home: Callable[[], Path] | None = None,
        scanner: Callable[[], sp.Scanner | None] = sp.hermes_scanner,
        now: Callable[[], str] = utc_now,
        clock: Callable[[], float] = time.time,
    ):
        self.ctx = ctx
        self._backend = backend if backend is not None else resolve_backend(ctx)
        self._fallback = MemoryBackend()
        self._using_fallback = False
        self._home = home
        self._scanner = scanner
        self._now = now
        self._clock = clock

    # -- record ------------------------------------------------------------

    def _backend_now(self) -> Any:
        return self._fallback if self._using_fallback else self._backend

    def record(self) -> dict[str, Any] | None:
        try:
            value = self._backend_now().get(STATE_KEY, None)
        except Exception as exc:  # noqa: BLE001 - never raise into Hermes
            logger.warning("hermes-odd: setup state unreadable (%s); using memory", exc)
            self._using_fallback = True
            value = self._fallback.get(STATE_KEY, None)
        if isinstance(value, Mapping) and value.get("schema") == SCHEMA:
            return dict(value)
        return None

    def _write(self, value: dict[str, Any] | None) -> None:
        try:
            self._backend_now().set(STATE_KEY, value)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hermes-odd: setup state not writable (%s); using memory", exc)
            self._using_fallback = True
            self._fallback.set(STATE_KEY, value)

    def pending(self) -> bool:
        return self.record() is None

    def answers(self) -> dict[str, str]:
        record = self.record() or {}
        raw = record.get("answers") if isinstance(record.get("answers"), Mapping) else {}
        return {k: v for k, v in raw.items() if k in PREF_VALUES and valid(k, v)}

    def custom_text(self) -> str:
        record = self.record() or {}
        value = record.get("custom_text")
        return value if isinstance(value, str) else ""

    # -- config ------------------------------------------------------------

    def config_value(self, key: str) -> str | None:
        getter = getattr(self.ctx, "get_config", None) if self.ctx is not None else None
        if not callable(getter):
            return None
        try:
            value = getter(key, None)
        except Exception:  # noqa: BLE001
            return None
        return value if valid(key, value) else None

    def effective(self) -> dict[str, tuple[str, str]]:
        """``key -> (value, source)`` with source ``config`` | ``setup`` | ``default``."""
        answers = self.answers()
        result = {}
        for key in PREF_KEYS:
            configured = self.config_value(key)
            if configured is not None:
                result[key] = (configured, "config")
            elif key in answers:
                result[key] = (answers[key], "setup")
            else:
                result[key] = (DEFAULTS[key], "default")
        return result

    def write_config(self, values: Mapping[str, str]) -> ConfigWrite:
        if not values:
            return ConfigWrite("skipped")
        setter = getattr(self.ctx, "set_config", None) if self.ctx is not None else None
        if not callable(setter):
            return ConfigWrite("unavailable")
        saved = []
        for key, value in values.items():
            try:
                setter(key, value)
                saved.append(key)
            except PermissionError as exc:
                detail = str(exc) or "managed install"
                return ConfigWrite("refused", _short(detail), saved)
            except Exception as exc:  # noqa: BLE001
                return ConfigWrite("failed", type(exc).__name__, saved)
        return ConfigWrite("saved", keys=saved)

    # -- section -------------------------------------------------------------

    def section_inputs(self) -> tuple[bool, str | None, list[str]]:
        """``(pending, TDD mode line or None, skill pointer lines)`` for the prompt
        section. Never raises."""
        try:
            pending = self.pending()
            effective = self.effective()
            tdd, _source = effective["tdd_mode"]
        except Exception:  # noqa: BLE001
            return False, None, []
        pointers: list[str] = []
        try:
            from .prompt import CODEGRAPH_POINTER, MEMORY_POINTER

            if effective["engram_protocol"][0] != "off":
                pointers.append(MEMORY_POINTER)
            if effective["codegraph_guidance"][0] != "off" and codegraph_available(self.home()):
                pointers.append(CODEGRAPH_POINTER)
        except Exception:  # noqa: BLE001
            logger.debug("hermes-odd: skill pointers failed", exc_info=True)
        return pending, TDD_LINES.get(tdd), pointers

    # -- transitions ---------------------------------------------------------

    def _save_record(
        self,
        answers: Mapping[str, str],
        *,
        source: str,
        custom_text: str | None = None,
        skipped: bool = False,
    ) -> dict[str, Any]:
        previous = self.record() or {}
        merged = dict(self.answers())
        merged.update({k: v for k, v in answers.items() if valid(k, v)})
        record = {
            "schema": SCHEMA,
            "version": VERSION,
            "completed_at": None if skipped else self._now(),
            "skipped": skipped,
            "answers": merged,
            "custom_text": previous.get("custom_text", "") if custom_text is None else custom_text,
            "source": source,
            "updated_at": self._now(),
        }
        if skipped and previous.get("completed_at"):
            record["completed_at"] = previous.get("completed_at")
        self._write(record)
        return record

    def skip(self) -> dict[str, Any]:
        return self._save_record({}, source="command", skipped=True)

    def reset(self) -> ConfigWrite:
        self._write(None)
        return self.write_config(
            {k: DEFAULTS[k] for k in PREF_KEYS if self.config_value(k) is not None}
        )

    def set_answers(self, answers: Mapping[str, str], source: str = "command") -> ConfigWrite:
        self._save_record(answers, source=source)
        return self.write_config(answers)

    # -- persona -------------------------------------------------------------

    def home(self) -> Path | None:
        if self._home is None:
            return None
        try:
            return Path(self._home())
        except Exception:  # noqa: BLE001
            return None

    def build_block(
        self, persona: str, verbosity: str, custom_text: str = ""
    ) -> tuple[str | None, str]:
        """``(block or None for no block, error)``."""
        if persona in (personas.NONE, personas.UNSET):
            return None, ""
        if persona == personas.CUSTOM:
            clean = personas.sanitize_custom_text(custom_text)
            if not clean:
                return None, "the own persona text is empty after sanitizing"
            if len(clean) > personas.CUSTOM_TEXT_MAX_CHARS:
                return None, (
                    f"the own persona text is {len(clean)} characters "
                    f"(at most {personas.CUSTOM_TEXT_MAX_CHARS})"
                )
            custom_text = clean
        block = personas.render_block(persona, verbosity, custom_text)
        scanner = None
        try:
            scanner = self._scanner()
        except Exception:  # noqa: BLE001
            scanner = None
        findings = sp.scan_block(block, scanner)
        if findings:
            return None, (
                "Hermes' SOUL.md safety scan would block the whole file with this text "
                f"({', '.join(sorted(set(findings))[:5])}); rephrase it"
            )
        return block, ""

    def plan_persona(
        self, persona: str, verbosity: str | None = None, custom_text: str | None = None
    ) -> tuple[sp.Plan | None, str, str | None]:
        """``(plan, error, block)`` for writing ``persona`` into SOUL.md."""
        style = verbosity or self.effective()["verbosity"][0]
        text = self.custom_text() if custom_text is None else custom_text
        block, error = self.build_block(persona, style, text)
        if error:
            return None, error, None
        plan = sp.plan_block(block, self.home())
        return plan, plan.error, block

    def apply(
        self,
        values: Mapping[str, Any],
        *,
        apply_persona: bool,
        source: str,
        persona_custom_text: str | None = None,
    ) -> ApplyOutcome:
        """Persist answers, optionally write the persona block, mark setup done.

        ``values`` must already be validated. The persona is recorded only
        when its SOUL.md change succeeds (or it is ``none`` with no block).
        """
        lines: list[str] = []
        warnings: list[str] = []
        answers = {k: v for k, v in values.items() if k in PREF_VALUES}
        persona = answers.pop("persona", None)
        soul_result: sp.Result | None = None
        custom_clean: str | None = None
        persona_line = ""
        if persona is not None:
            if persona == personas.CUSTOM:
                custom_clean = personas.sanitize_custom_text(
                    persona_custom_text if persona_custom_text is not None else self.custom_text()
                )
            if not apply_persona:
                persona_line = (
                    f"Persona: {personas.LABELS[persona]} not applied (not confirmed); "
                    "SOUL.md untouched."
                )
            else:
                style = answers.get("verbosity") or self.effective()["verbosity"][0]
                plan, error, _block = self.plan_persona(persona, style, custom_clean or "")
                if error or plan is None:
                    persona_line = f"Persona: not applied: {error}. SOUL.md untouched."
                    warnings.append(error)
                else:
                    soul_result = sp.apply_plan(plan)
                    if soul_result.error:
                        persona_line = f"Persona: not applied: {soul_result.error}."
                        warnings.append(soul_result.error)
                    else:
                        answers["persona"] = persona
                        persona_line = persona_summary(persona, plan, soul_result)
                        if plan.gentle_persona and persona != personas.NONE:
                            warnings.append(COEXIST_WARNING)
        record_custom = custom_clean if "persona" in answers and custom_clean else None
        self._save_record(answers, source=source, custom_text=record_custom)
        config = self.write_config(answers)
        for key in PREF_KEYS:
            if key == "persona":
                if persona_line:
                    lines.append(persona_line)
                continue
            if key in answers:
                lines.append(f"{LABEL[key]}: {answers[key]} ({APPLIED_WHERE[key]})")
        if "verbosity" in answers and "persona" not in answers and persona is None:
            status, _chars = sp.block_status(self.home())
            if status == "present":
                lines.append(
                    "The SOUL.md block still has the previous answer style: re-apply the "
                    "persona (/odd_setup persona <id> confirm) to rewrite it."
                )
        if answers.get("soul_cleanup") == "yes":
            lines.append(SOUL_CLEANUP_NEXT)
        lines.append(config.text())
        lines.extend(f"Warning: {w}" for w in warnings if w == COEXIST_WARNING)
        lines.append("Setup: complete.")
        lines.append(NEXT_SESSION_NOTE)
        return ApplyOutcome(
            True,
            lines,
            soul=soul_result,
            config=config,
            warnings=warnings,
            persona_recorded="persona" in answers,
        )


LABEL = {
    "persona": "Persona",
    "verbosity": "Answer style",
    "tdd_mode": "TDD mode",
    "engram_protocol": "Engram protocol",
    "soul_cleanup": "SOUL cleanup of gentle-ai blocks",
    "codegraph_guidance": "CodeGraph guidance",
}

COEXIST_WARNING = (
    "SOUL.md also has a gentle-ai persona block, so two personas now coexist. "
    "It was left untouched; /odd_soul plan persona previews removing it (with backup)."
)

SOUL_CLEANUP_NEXT = (
    "SOUL cleanup: next, show the odd_soul_apply dry run (confirm=false) and apply it "
    "only after the user's explicit yes; or type /odd_soul plan."
)


def persona_summary(persona: str, plan: sp.Plan, result: sp.Result) -> str:
    label = personas.LABELS.get(persona, persona)
    if plan.action == sp.REMOVE:
        text = "Persona: none; the hermes-odd block was removed from SOUL.md"
    elif plan.action == sp.NOTHING:
        text = "Persona: none; SOUL.md has no hermes-odd block (unchanged)"
    elif plan.action == sp.UNCHANGED:
        text = f"Persona: {label}; the SOUL.md block is already up to date"
    else:
        where = "replaced in place" if plan.action == sp.REPLACE else f"written {plan.placement}"
        text = f"Persona: {label}; SOUL.md block {where}"
    if result.backup is not None:
        text += f" (backup {result.backup.name})"
    return text + "."


def _mcp_server_configured(lines: list[str], name: str) -> bool:
    """Whether Hermes' ``config.yaml`` has ``mcp_servers.<name>`` (key names only)."""
    in_servers = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key = line.strip().partition(":")[0].strip().strip("\"'")
        if indent == 0:
            in_servers = key == "mcp_servers"
        elif in_servers and indent == 2 and key == name:
            return True
    return False


def codegraph_available(home: Path | None = None) -> bool:
    """A ``codegraph`` binary on ``PATH`` or an ``mcp_servers.codegraph`` entry in
    ``<Hermes home>/config.yaml``. Never raises; reads only key names."""
    try:
        if shutil.which("codegraph"):
            return True
        where = home if home is not None else soul_mod.hermes_home()
        return _mcp_server_configured(
            soul_mod._read_small(Path(where) / "config.yaml"), "codegraph"
        )
    except Exception:  # noqa: BLE001
        return False


def _short(text: str, limit: int = 160) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


__all__ = [
    "APPLIED_WHERE",
    "COEXIST_WARNING",
    "DEFAULTS",
    "NEXT_SESSION_NOTE",
    "PREF_KEYS",
    "PREF_VALUES",
    "SCHEMA",
    "STATE_KEY",
    "SOUL_CLEANUP_NEXT",
    "Setup",
    "TDD_LINES",
    "codegraph_available",
    "valid",
]
