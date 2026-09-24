"""Hermes ``register(ctx)`` wiring for gentle-hermes.

Registration must never crash Hermes startup: every step is guarded, and a
missing optional ``ctx`` method is skipped with a logged warning.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .commands import CommandRegistry, CommandSpec, build_registry

logger = logging.getLogger("gentle_hermes")


def _safe_handler(spec: CommandSpec) -> Callable[[str], str]:
    """Wrap a handler so it always returns plain text and never raises."""

    def handler(raw_args: str = "") -> str:
        try:
            result = spec.handler((raw_args or "").strip())
        except Exception as exc:  # noqa: BLE001 - surface as text, never raise
            logger.warning("gentle-hermes /%s failed: %s", spec.name, exc, exc_info=True)
            return f"/{spec.name} failed: {type(exc).__name__}: {exc}"
        if result is None:
            return ""
        return result if isinstance(result, str) else str(result)

    handler.__name__ = f"gentle_{spec.name}_handler"
    return handler


def register_commands(ctx: Any, registry: CommandRegistry) -> int:
    """Register every spec with Hermes; return how many succeeded."""
    register_command = getattr(ctx, "register_command", None)
    if not callable(register_command):
        logger.warning("gentle-hermes: ctx.register_command is unavailable; commands skipped")
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
            logger.warning("gentle-hermes: could not register /%s: %s", spec.name, exc)
    return registered


def register(ctx: Any) -> None:
    """Hermes plugin entry point."""
    try:
        registry = build_registry()
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("gentle-hermes: command registry failed to build: %s", exc)
        return
    register_commands(ctx, registry)
