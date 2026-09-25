"""Tool ``odd_setup_apply``: the model's single write path for the first-run setup.

Registered with ``ctx.register_tool(name, toolset, schema, handler, ...)``
(``hermes_cli/plugins.py`` ``PluginContext.register_tool``). The schema is the
OpenAI function format Hermes uses (``name``, ``description``,
``parameters``). Hermes calls ``handler(args, **kwargs)`` through
``tools.registry.registry.dispatch`` and expects a string; errors are the
JSON ``{"error": "..."}`` shape of ``tools.registry.tool_error``. This handler
never raises: every failure is returned as that JSON.

The persona block is written into ``SOUL.md`` only when
``apply_persona_to_soul`` is ``true``; the ``hermes-odd:setup`` skill asks the
user for explicit confirmation first. Toolset ``hermes_odd`` follows the
bundled plugins' naming (``spotify``, ``google_meet``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from . import personas
from .setup import NEXT_SESSION_NOTE, PREF_VALUES, Setup

logger = logging.getLogger("hermes_odd")

TOOL_NAME = "odd_setup_apply"
TOOLSET = "hermes_odd"
EMOJI = "🧭"

INPUT_VALUES: dict[str, tuple[str, ...]] = {
    "persona": personas.PERSONA_CHOICES,
    "verbosity": PREF_VALUES["verbosity"],
    "tdd_mode": ("off", "strict", "project"),
    "engram_protocol": PREF_VALUES["engram_protocol"],
    "soul_cleanup": ("yes", "later", "no"),
}
ALLOWED_KEYS = (*INPUT_VALUES, "persona_custom_text", "apply_persona_to_soul")

DESCRIPTION = (
    "Apply the hermes-odd first-run setup after the user answered it (load the "
    "hermes-odd:setup skill first). Persists the answers and marks the setup done. "
    "Writes the persona into SOUL.md as one hermes-odd block, with a backup, ONLY when "
    "apply_persona_to_soul is true, which requires the user's explicit confirmation of "
    "the summary. Changes take effect in the next new session."
)

SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "persona": {
                "type": "string",
                "enum": list(INPUT_VALUES["persona"]),
                "description": (
                    "rioplatense = mentor, Rioplatense Spanish (voseo); neutral = mentor, "
                    "neutral language; custom = the user's own text in persona_custom_text; "
                    "none = no persona block (Hermes default). Omit if the user did not answer."
                ),
            },
            "persona_custom_text": {
                "type": "string",
                "maxLength": personas.CUSTOM_TEXT_MAX_CHARS,
                "description": "The user's own persona text, verbatim; only with persona=custom.",
            },
            "verbosity": {
                "type": "string",
                "enum": list(INPUT_VALUES["verbosity"]),
                "description": "Answer style: short first, or detailed.",
            },
            "tdd_mode": {
                "type": "string",
                "enum": list(INPUT_VALUES["tdd_mode"]),
                "description": (
                    "off, strict (RED, GREEN, REFACTOR) or project (detect the runner)."
                ),
            },
            "engram_protocol": {
                "type": "string",
                "enum": list(INPUT_VALUES["engram_protocol"]),
                "description": "auto (when mcp__engram__* tools exist) or off.",
            },
            "soul_cleanup": {
                "type": "string",
                "enum": list(INPUT_VALUES["soul_cleanup"]),
                "description": (
                    "yes = next, show the odd_soul_apply dry run and apply it only after the "
                    "user's explicit yes; later = the user runs /odd_soul later; no = keep."
                ),
            },
            "apply_persona_to_soul": {
                "type": "boolean",
                "description": (
                    "true only after the user explicitly confirmed writing the persona block "
                    "into SOUL.md; false persists the other answers and leaves SOUL.md untouched."
                ),
            },
        },
        "required": ["apply_persona_to_soul"],
        "additionalProperties": False,
    },
}


class ArgsError(ValueError):
    pass


def validate_args(args: Any) -> tuple[dict[str, str], str | None, bool]:
    """``(answers, custom_text, apply_persona)`` or :class:`ArgsError`."""
    if not isinstance(args, Mapping):
        raise ArgsError("arguments must be a JSON object")
    unknown = sorted(str(k) for k in args if k not in ALLOWED_KEYS)
    if unknown:
        raise ArgsError(f"unknown argument(s): {', '.join(unknown)}")
    apply_persona = args.get("apply_persona_to_soul")
    if not isinstance(apply_persona, bool):
        raise ArgsError("apply_persona_to_soul is required and must be true or false")
    answers: dict[str, str] = {}
    for key, allowed in INPUT_VALUES.items():
        if key not in args or args[key] is None:
            continue
        value = args[key]
        if not isinstance(value, str) or value not in allowed:
            raise ArgsError(f"{key} must be one of: {', '.join(allowed)}")
        answers[key] = value
    custom = args.get("persona_custom_text")
    if custom is not None and not isinstance(custom, str):
        raise ArgsError("persona_custom_text must be a string")
    if custom is not None and answers.get("persona") != personas.CUSTOM:
        raise ArgsError("persona_custom_text is only allowed with persona=custom")
    if answers.get("persona") == personas.CUSTOM:
        if not custom or not custom.strip():
            raise ArgsError("persona=custom needs the user's text in persona_custom_text")
        if len(custom) > personas.CUSTOM_TEXT_MAX_CHARS:
            raise ArgsError(
                f"persona_custom_text is {len(custom)} characters "
                f"(at most {personas.CUSTOM_TEXT_MAX_CHARS})"
            )
        if not personas.sanitize_custom_text(custom):
            raise ArgsError("persona_custom_text is empty after removing comments and markers")
    return answers, custom, apply_persona


def error_json(message: str) -> str:
    return json.dumps({"error": str(message)[:500], "ok": False}, ensure_ascii=False)


def make_handler(setup: Setup):
    def handler(args: Any = None, **_kwargs: Any) -> str:
        try:
            answers, custom, apply_persona = validate_args(args if args is not None else {})
        except ArgsError as exc:
            return error_json(f"odd_setup_apply: {exc}; nothing was changed")
        except Exception as exc:  # noqa: BLE001 - never raise into Hermes
            return error_json(f"odd_setup_apply: invalid arguments ({type(exc).__name__})")
        try:
            outcome = setup.apply(
                answers,
                apply_persona=apply_persona,
                source="tool",
                persona_custom_text=custom,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("hermes-odd: odd_setup_apply failed: %s", exc, exc_info=True)
            return error_json(f"odd_setup_apply failed: {type(exc).__name__}")
        soul = outcome.soul
        return json.dumps(
            {
                "ok": True,
                "summary": outcome.text(),
                "persona_applied": outcome.persona_recorded,
                "backup": soul.backup.name if soul and soul.backup else None,
                "config": outcome.config.state if outcome.config else None,
                "warnings": outcome.warnings,
                "next": (
                    "Call odd_soul_apply with confirm=false, show its plan verbatim and ask "
                    "for an explicit yes before confirm=true."
                    if answers.get("soul_cleanup") == "yes"
                    else None
                ),
                "note": NEXT_SESSION_NOTE,
            },
            ensure_ascii=False,
        )

    handler.__name__ = "hermes_odd_setup_apply"
    return handler


def register_setup_tool(ctx: Any, setup: Setup) -> bool:
    register_tool = getattr(ctx, "register_tool", None)
    if not callable(register_tool):
        logger.warning("hermes-odd: ctx.register_tool is unavailable; odd_setup_apply skipped")
        return False
    try:
        register_tool(
            name=TOOL_NAME,
            toolset=TOOLSET,
            schema=SCHEMA,
            handler=make_handler(setup),
            description=DESCRIPTION,
            emoji=EMOJI,
        )
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: could not register %s: %s", TOOL_NAME, exc)
        return False
    return True


__all__ = [
    "SCHEMA",
    "TOOL_NAME",
    "TOOLSET",
    "make_handler",
    "register_setup_tool",
    "validate_args",
]
