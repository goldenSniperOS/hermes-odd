"""Hermes ``register(ctx)`` wiring for hermes-odd.

Registration must never crash Hermes startup: every step is guarded, and a
missing optional ``ctx`` method is skipped with a logged warning.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .commands import CommandRegistry, CommandSpec, build_registry
from .prompt import SECTION_ID, SECTION_MAX_CHARS, build_odd_section
from .skills import register_skills

logger = logging.getLogger("hermes_odd")


def _safe_handler(spec: CommandSpec) -> Callable[[str], str]:
    """Wrap a handler so it always returns plain text and never raises."""

    def handler(raw_args: str = "") -> str:
        try:
            result = spec.handler((raw_args or "").strip())
        except Exception as exc:  # noqa: BLE001 - surface as text, never raise
            logger.warning("hermes-odd /%s failed: %s", spec.name, exc, exc_info=True)
            return f"/{spec.name} failed: {type(exc).__name__}: {exc}"
        if result is None:
            return ""
        return result if isinstance(result, str) else str(result)

    handler.__name__ = f"hermes_odd_{spec.name}_handler"
    return handler


def register_commands(ctx: Any, registry: CommandRegistry) -> int:
    """Register every spec with Hermes; return how many succeeded."""
    register_command = getattr(ctx, "register_command", None)
    if not callable(register_command):
        logger.warning("hermes-odd: ctx.register_command is unavailable; commands skipped")
        return 0
    registered = 0
    for spec in registry:
        try:
            register_command(
                spec.hermes_key,
                _safe_handler(spec),
                description=spec.description,
                args_hint=spec.args_hint,
            )
            registered += 1
        except Exception as exc:  # noqa: BLE001 - never break Hermes startup
            logger.warning("hermes-odd: could not register /%s: %s", spec.name, exc)
    return registered


def register_prompt_section(ctx: Any) -> bool:
    """Register the compact always-on ODD section; return whether it succeeded."""
    register_section = getattr(ctx, "register_system_prompt_section", None)
    if not callable(register_section):
        logger.warning(
            "hermes-odd: ctx.register_system_prompt_section is unavailable; ODD section skipped"
        )
        return False
    try:
        register_section(SECTION_ID, build_odd_section(), max_chars=SECTION_MAX_CHARS)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: could not register the ODD section: %s", exc)
        return False
    return True


def register(ctx: Any) -> None:
    """Hermes plugin entry point."""
    register_prompt_section(ctx)
    try:
        register_skills(ctx)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: skill registration failed: %s", exc)
    try:
        registry = build_registry()
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: command registry failed to build: %s", exc)
        return
    register_commands(ctx, registry)
