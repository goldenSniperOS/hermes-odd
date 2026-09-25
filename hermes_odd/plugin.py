"""Hermes ``register(ctx)`` wiring for hermes-odd.

Registration must never crash Hermes startup: every step is guarded, and a
missing optional ``ctx`` method is skipped with a logged warning.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from . import skills as skills_mod
from .agents import HOOK_NAMES, AgentStore, register_agent_hooks, resolve_backend
from .changes import ChangeStore, register_change_hooks
from .commands import CommandRegistry, CommandSpec, build_registry
from .projects import ProjectStore
from .prompt import (
    SECTION_ID,
    SECTION_MAX_CHARS,
    SectionObserver,
    build_odd_section,
    make_section_callable,
)
from .runtime import RuntimeInfo

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


def register_prompt_section(ctx: Any, observer: SectionObserver | None = None) -> bool:
    """Register the compact always-on ODD section; return whether it succeeded.

    The content is a callable so ``observer`` (the ``/odd_tasks`` project
    recorder) sees each session's ``cwd``; the rendered text is unchanged.
    """
    register_section = getattr(ctx, "register_system_prompt_section", None)
    if not callable(register_section):
        logger.warning(
            "hermes-odd: ctx.register_system_prompt_section is unavailable; ODD section skipped"
        )
        return False
    try:
        register_section(SECTION_ID, make_section_callable(observer), max_chars=SECTION_MAX_CHARS)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: could not register the ODD section: %s", exc)
        return False
    return True


def register(ctx: Any) -> None:
    """Hermes plugin entry point."""
    runtime = RuntimeInfo(ctx=ctx, hooks_expected=len(HOOK_NAMES) + 1)
    project_store: ProjectStore | None = None
    try:
        project_store = ProjectStore(resolve_backend(ctx))
        runtime.stores["projects"] = project_store
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: project tracking failed to start: %s", exc)
    runtime.section_registered = register_prompt_section(
        ctx, project_store.on_section_render if project_store is not None else None
    )
    runtime.section_chars = len(build_odd_section())
    try:
        runtime.skills_dir = skills_mod.SKILLS_DIR
        skills_mod.register_skills(ctx, skills_mod.SKILLS_DIR, runtime.skills)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: skill registration failed: %s", exc)
    agent_store: AgentStore | None = None
    try:
        agent_store = AgentStore(resolve_backend(ctx))
        runtime.stores["agents"] = agent_store
        runtime.hooks_registered += register_agent_hooks(ctx, agent_store)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: subagent tracking failed to start: %s", exc)
    change_store: ChangeStore | None = None
    try:
        change_store = ChangeStore(resolve_backend(ctx), agent_store=agent_store)
        runtime.stores["changes"] = change_store
        runtime.hooks_registered += int(register_change_hooks(ctx, change_store))
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: change tracking failed to start: %s", exc)
    try:
        registry = build_registry(agent_store, project_store, change_store, runtime=runtime)
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: command registry failed to build: %s", exc)
        return
    runtime.commands_registered = register_commands(ctx, registry)
