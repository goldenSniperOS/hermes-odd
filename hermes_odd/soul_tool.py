"""Tool ``odd_soul_apply``: the model's only path to clean gentle-ai blocks out of SOUL.md.

A separate, single-purpose tool rather than another flag on
``odd_setup_apply``: the cleanup needs a dry run the model can show before
asking, and a guard that the applied plan is the one the user saw. So:

* ``confirm: false`` (dry run) returns the plan text and a ``plan_id``;
  nothing is written;
* ``confirm: true`` needs that ``plan_id``: it is a digest of the current
  ``SOUL.md`` and the options, so a file changed since the plan (or a plan
  never shown) is refused. It then backs up, writes and verifies like
  ``/odd_soul apply confirm``.

The ``hermes-odd:setup`` skill calls it when the setup answer
``soul_cleanup`` is ``yes``, and only calls ``confirm: true`` after the
user's explicit yes to the shown plan. The handler never raises; errors are
``{"error": ...}`` JSON like ``tools.registry.tool_error``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from . import soul as soul_mod
from . import soul_cleanup as sc
from .commands.soul import render_plan, render_result
from .setup import NEXT_SESSION_NOTE
from .setup_tool import TOOLSET, error_json

logger = logging.getLogger("hermes_odd")

TOOL_NAME = "odd_soul_apply"
EMOJI = "🧹"
ALLOWED_KEYS = ("confirm", "plan_id", "remove_gentle_persona")

DESCRIPTION = (
    "Clean the gentle-ai managed blocks out of SOUL.md (remove the workflow blocks, move "
    "the Engram and CodeGraph guidance to lazy skills, keep user text, persona blocks and "
    "remote-authorization). First call with confirm=false: returns the dry-run plan and a "
    "plan_id; show the plan to the user verbatim. Only after the user explicitly says yes, "
    "call again with confirm=true and that plan_id: backs up SOUL.md, writes it and "
    "verifies it. Takes effect in the next new session."
)

SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": (
                    "false = dry run (plan only, nothing written); true = apply, only after "
                    "the user explicitly confirmed the shown plan."
                ),
            },
            "plan_id": {
                "type": "string",
                "description": "The plan_id returned by the dry run; required with confirm=true.",
            },
            "remove_gentle_persona": {
                "type": "boolean",
                "description": (
                    "Also remove the old gentle-ai persona block; only when the user asked "
                    "for it and a hermes-odd persona block exists."
                ),
            },
        },
        "required": ["confirm"],
        "additionalProperties": False,
    },
}


class ArgsError(ValueError):
    pass


def validate_args(args: Any) -> tuple[bool, str, bool]:
    """``(confirm, plan_id, remove_persona)`` or :class:`ArgsError`."""
    if not isinstance(args, Mapping):
        raise ArgsError("arguments must be a JSON object")
    unknown = sorted(str(k) for k in args if k not in ALLOWED_KEYS)
    if unknown:
        raise ArgsError(f"unknown argument(s): {', '.join(unknown)}")
    confirm = args.get("confirm")
    if not isinstance(confirm, bool):
        raise ArgsError("confirm is required and must be true or false")
    plan_id = args.get("plan_id", "")
    if plan_id is None:
        plan_id = ""
    if not isinstance(plan_id, str):
        raise ArgsError("plan_id must be a string")
    if confirm and not plan_id.strip():
        raise ArgsError("confirm=true needs the plan_id of the dry run the user confirmed")
    persona = args.get("remove_gentle_persona", False)
    if persona is None:
        persona = False
    if not isinstance(persona, bool):
        raise ArgsError("remove_gentle_persona must be true or false")
    return confirm, plan_id.strip(), persona


def make_handler(
    home: Callable[[], Path | None] | None = None,
    model_context: Callable[[Path], soul_mod.ModelContext] = soul_mod.model_context,
):
    def resolve_home() -> Path | None:
        if home is None:
            return None
        value = home()
        return Path(value) if value is not None else None

    def handler(args: Any = None, **_kwargs: Any) -> str:
        try:
            confirm, plan_id, persona = validate_args(args if args is not None else {})
        except ArgsError as exc:
            return error_json(f"{TOOL_NAME}: {exc}; nothing was changed")
        except Exception as exc:  # noqa: BLE001 - never raise into Hermes
            return error_json(f"{TOOL_NAME}: invalid arguments ({type(exc).__name__})")
        try:
            where = resolve_home()
            plan = sc.plan_cleanup(where, remove_persona=persona)
            if plan.error:
                return error_json(f"{TOOL_NAME}: {plan.error}")
            if not confirm:
                try:
                    context = model_context(where if where is not None else soul_mod.hermes_home())
                except Exception:  # noqa: BLE001
                    context = soul_mod.ModelContext()
                return json.dumps(
                    {
                        "ok": True,
                        "dry_run": True,
                        "changes": plan.writes,
                        "plan_id": plan.plan_id if plan.writes else None,
                        "plan": render_plan(plan, context),
                        "next": (
                            "Show the plan to the user verbatim and ask for an explicit yes; "
                            "only then call again with confirm=true and this plan_id."
                            if plan.writes
                            else "Nothing to clean; do not call again."
                        ),
                    },
                    ensure_ascii=False,
                )
            if persona and plan.persona_note:
                return error_json(f"{TOOL_NAME}: {plan.persona_note} Nothing was changed.")
            if not plan.writes:
                return json.dumps(
                    {
                        "ok": True,
                        "applied": False,
                        "summary": render_result(sc.CleanupResult(plan)),
                    },
                    ensure_ascii=False,
                )
            if plan_id != plan.plan_id:
                return error_json(
                    f"{TOOL_NAME}: the plan_id does not match the current SOUL.md (it changed, "
                    "or the plan was not shown); run the dry run again and show it. Nothing "
                    "was changed."
                )
            result = sc.apply_cleanup(plan)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hermes-odd: %s failed: %s", TOOL_NAME, exc, exc_info=True)
            return error_json(f"{TOOL_NAME} failed: {type(exc).__name__}")
        if result.error and not result.written:
            return error_json(f"{TOOL_NAME}: {result.error}")
        return json.dumps(
            {
                "ok": True,
                "applied": result.written,
                "verified": result.verified,
                "backup": result.backup.name if result.backup else None,
                "summary": render_result(result),
                "note": NEXT_SESSION_NOTE,
            },
            ensure_ascii=False,
        )

    handler.__name__ = "hermes_odd_soul_apply"
    return handler


def register_soul_tool(ctx: Any) -> bool:
    register_tool = getattr(ctx, "register_tool", None)
    if not callable(register_tool):
        logger.warning("hermes-odd: ctx.register_tool is unavailable; %s skipped", TOOL_NAME)
        return False
    try:
        register_tool(
            name=TOOL_NAME,
            toolset=TOOLSET,
            schema=SCHEMA,
            handler=make_handler(),
            description=DESCRIPTION,
            emoji=EMOJI,
        )
    except Exception as exc:  # noqa: BLE001 - never break Hermes startup
        logger.warning("hermes-odd: could not register %s: %s", TOOL_NAME, exc)
        return False
    return True


__all__ = ["SCHEMA", "TOOL_NAME", "make_handler", "register_soul_tool", "validate_args"]
