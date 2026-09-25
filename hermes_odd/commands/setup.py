"""``/odd_setup``: first-run setup status and direct setters (installer persona step).

Deterministic plain text; never calls the model. Subcommands:

* ``status`` (default): pending/complete/skipped, every answer with its
  effective value, source and where it is applied, and the SOUL.md block;
* ``skip``: mark the setup skipped (the agent stops offering it);
* ``reset``: clear the answers and make the setup pending again. The SOUL.md
  persona block is **not** removed (``/odd_setup persona none`` does that);
* ``persona <rioplatense|neutral|custom|none> [confirm]``: without
  ``confirm`` a dry-run preview of the SOUL.md change; only the ``confirm``
  form writes (backup first). ``custom`` reuses the own text given to the
  agent during setup;
* ``tdd <off|strict|project>``, ``engram <on|off>``,
  ``codegraph <auto|off>``, ``verbosity <short|detailed>``: store one answer.

The gentle-ai block cleanup of ``SOUL.md`` is ``/odd_soul``.

A setter or a confirmed persona completes the setup.
"""

from __future__ import annotations

from .. import personas
from .. import soul_persona as sp
from ..setup import APPLIED_WHERE, LABEL, NEXT_SESSION_NOTE, PREF_KEYS, Setup
from .doctor import display_path
from .registry import CommandSpec

OUTPUT_MAX_CHARS = 3500
USAGE = (
    "/odd_setup [status|skip|reset|persona <rioplatense|neutral|custom|none> [confirm]|"
    "tdd <off|strict|project>|engram <on|off>|codegraph <auto|off>|verbosity <short|detailed>]"
)
TDD_VALUES = ("off", "strict", "project")
ENGRAM_VALUES = {"on": "auto", "auto": "auto", "off": "off"}
CODEGRAPH_VALUES = ("auto", "off")


def _k(chars: int) -> str:
    return f"{chars / 1000:.1f}k" if chars >= 1000 else str(chars)


def _fit(text: str) -> str:
    if len(text) <= OUTPUT_MAX_CHARS:
        return text
    return text[: OUTPUT_MAX_CHARS - 1].rstrip() + "…"


def _value_label(key: str, value: str) -> str:
    if key == "persona":
        return personas.LABELS.get(value, value)
    if key == "engram_protocol" and value == "auto":
        return "auto (when mcp__engram__* tools exist)"
    if key == "codegraph_guidance" and value == "auto":
        return "auto (when CodeGraph is on PATH or configured)"
    if key == "tdd_mode" and value == "project":
        return "per project"
    return value


class SetupCommand:
    def __init__(self, setup: Setup):
        self.setup = setup

    # -- status --------------------------------------------------------------

    def soul_line(self) -> str:
        path = sp.soul_path(self.setup.home())
        status, chars = sp.block_status(self.setup.home())
        text = {
            "present": f"hermes-odd persona block present ({_k(chars)} chars)",
            "absent": "no hermes-odd persona block",
            "broken": "unbalanced hermes-odd markers (fix by hand)",
            "unreadable": "unreadable",
        }[status]
        plan = sp.plan_block(None, self.setup.home())
        if not plan.exists:
            text = "does not exist yet"
        elif plan.gentle_persona:
            text += " · a gentle-ai persona block coexists"
        return f"SOUL.md ({display_path(path)}): {text}"

    def status(self) -> str:
        record = self.setup.record()
        if record is None:
            head = "hermes-odd setup: pending (the agent offers it once when you are not mid-task)"
        elif record.get("skipped"):
            head = "hermes-odd setup: skipped"
        else:
            source = record.get("source") or "?"
            head = f"hermes-odd setup: complete ({record.get('completed_at') or '?'} via {source})"
        lines = [head, "", "Answers (value · source · where it applies):"]
        effective = self.setup.effective()
        for key in PREF_KEYS:
            value, source = effective[key]
            where = APPLIED_WHERE[key]
            if key == "tdd_mode" and value == "unset":
                where += " (no line while unset)"
            lines.append(f"- {LABEL[key]}: {_value_label(key, value)} · {source} · {where}")
        lines.append("")
        lines.append(self.soul_line())
        lines.append("")
        lines.append(
            "Set up: ask the agent (it loads hermes-odd:setup), or directly: "
            "/odd_setup persona <rioplatense|neutral|custom|none> · tdd <off|strict|project> · "
            "engram <on|off> · codegraph <auto|off> · verbosity <short|detailed> · skip · "
            "reset. SOUL cleanup of gentle-ai blocks: /odd_soul"
        )
        lines.append(NEXT_SESSION_NOTE)
        return _fit("\n".join(lines))

    # -- transitions ---------------------------------------------------------

    def skip(self) -> str:
        self.setup.skip()
        return (
            "hermes-odd setup skipped: the agent will not offer it again. Answers were kept.\n"
            "Run it later by asking the agent (hermes-odd:setup), or /odd_setup reset."
        )

    def reset(self) -> str:
        config = self.setup.reset()
        lines = [
            "hermes-odd setup reset: answers cleared, setup is pending again (the agent "
            "offers it once in the next new session).",
            "The SOUL.md persona block was not touched; remove it with "
            "/odd_setup persona none (then confirm).",
        ]
        if config.state != "skipped":
            lines.append(config.text().replace("saved under", "defaults restored under"))
        return "\n".join(lines)

    def set_one(self, key: str, value: str) -> str:
        outcome = self.setup.apply({key: value}, apply_persona=False, source="command")
        return _fit(outcome.text())

    def persona(self, persona: str, confirm: bool) -> str:
        custom = None
        if persona == personas.CUSTOM:
            custom = self.setup.custom_text()
            if not custom:
                return (
                    "No own persona text is stored yet. Give it to the agent during setup "
                    "(ask it to run hermes-odd:setup), then /odd_setup persona custom confirm "
                    "re-applies it."
                )
        if confirm:
            outcome = self.setup.apply(
                {"persona": persona},
                apply_persona=True,
                source="command",
                persona_custom_text=custom,
            )
            return _fit(outcome.text())
        return self.preview(persona, custom)

    def preview(self, persona: str, custom: str | None) -> str:
        plan, error, block = self.setup.plan_persona(persona, custom_text=custom)
        label = personas.LABELS[persona]
        lines = [f"Persona preview (dry run, nothing written): {label}"]
        if error or plan is None:
            lines.append(f"Cannot apply: {error}")
            return "\n".join(lines)
        where = display_path(plan.path)
        if plan.action == sp.INSERT:
            lines.append(f"SOUL.md ({where}): the block would be written {plan.placement}.")
        elif plan.action == sp.REPLACE:
            lines.append(f"SOUL.md ({where}): the hermes-odd block would be replaced in place.")
        elif plan.action == sp.REMOVE:
            lines.append(f"SOUL.md ({where}): the hermes-odd block would be removed.")
        elif plan.action == sp.UNCHANGED:
            lines.append(f"SOUL.md ({where}): the block is already up to date.")
        else:
            lines.append(f"SOUL.md ({where}): no hermes-odd block; nothing to remove.")
        if plan.writes and plan.exists:
            lines.append(
                f"A backup {sp.SOUL_FILE}{sp.BACKUP_INFIX}<UTC timestamp> is made first "
                f"(the last {sp.BACKUP_KEEP} are kept). Nothing else in SOUL.md changes."
            )
        if plan.gentle_persona and persona != personas.NONE:
            lines.append(
                "Warning: SOUL.md also has a gentle-ai persona block; both personas would "
                "coexist (/odd_soul plan persona previews removing the old one)."
            )
        if block:
            lines.extend(["", "---- block ----", block, "---------------"])
        lines.append("")
        lines.append(f"Reply `/odd_setup persona {persona} confirm` to write it.")
        return _fit("\n".join(lines))

    # -- dispatch ------------------------------------------------------------

    def handle(self, raw_args: str) -> str:
        words = (raw_args or "").split()
        head = words[0].lower() if words else "status"
        rest = [w.lower() for w in words[1:]]
        if head == "status" and not rest:
            return self.status()
        if head == "skip" and not rest:
            return self.skip()
        if head == "reset" and not rest:
            return self.reset()
        if head == "persona" and rest and rest[0] in personas.PERSONA_CHOICES:
            if len(rest) == 1:
                return self.persona(rest[0], confirm=False)
            if len(rest) == 2 and rest[1] == "confirm":
                return self.persona(rest[0], confirm=True)
        if head == "tdd" and len(rest) == 1 and rest[0] in TDD_VALUES:
            return self.set_one("tdd_mode", rest[0])
        if head == "engram" and len(rest) == 1 and rest[0] in ENGRAM_VALUES:
            return self.set_one("engram_protocol", ENGRAM_VALUES[rest[0]])
        if head == "codegraph" and len(rest) == 1 and rest[0] in CODEGRAPH_VALUES:
            return self.set_one("codegraph_guidance", rest[0])
        if head == "verbosity" and len(rest) == 1 and rest[0] in personas.VERBOSITY_CHOICES:
            return self.set_one("verbosity", rest[0])
        return f"Usage: {USAGE}"


def make_odd_setup(command: SetupCommand) -> CommandSpec:
    return CommandSpec(
        name="odd_setup",
        description="First-run setup: persona, answer style, TDD mode, Engram, SOUL cleanup",
        handler=command.handle,
        args_hint=(
            "[status|skip|reset|persona ID [confirm]|tdd off/strict/project|"
            "engram on/off|codegraph auto/off|verbosity short/detailed]"
        ),
        group="Setup",
    )


__all__ = ["SetupCommand", "USAGE", "make_odd_setup"]
