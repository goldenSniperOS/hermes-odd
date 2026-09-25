"""``/odd_soul``: clean the gentle-ai blocks out of ``SOUL.md`` (dry run, backup, restore).

Deterministic plain text; never calls the model and never prints SOUL
content (block names and sizes only). Subcommands:

* ``status`` (default): every top-level block with its size and what the
  cleanup would do, the current truncation impact and the backups;
* ``plan [persona]``: dry-run preview: each block -> remove / move to skill /
  keep / lift, characters saved, the resulting size and the truncation
  before -> after for 128k, 200k, 1M and the configured model. ``persona``
  also removes the old gentle-ai persona, only while a hermes-odd persona
  block exists;
* ``apply [persona] confirm``: back up, write atomically, verify;
* ``restore [N|backup name]``: list the backups (newest first), or restore
  one (the current file is backed up first).

The rules live in :mod:`hermes_odd.soul_cleanup`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .. import soul as soul_mod
from .. import soul_cleanup as sc
from .. import soul_persona as sp
from ..setup import NEXT_SESSION_NOTE
from .doctor import display_path
from .registry import CommandSpec

OUTPUT_MAX_CHARS = 3500
USAGE = "/odd_soul [status|plan [persona]|apply [persona] confirm|restore [N|backup]]"
MAX_BACKUPS_LISTED = 5


def _k(chars: int) -> str:
    return f"{chars / 1000:.1f}k" if chars >= 1000 else str(chars)


def _tokens(chars: int) -> str:
    return _k((chars + soul_mod.CHARS_PER_TOKEN - 1) // soul_mod.CHARS_PER_TOKEN)


def _fit(text: str) -> str:
    if len(text) <= OUTPUT_MAX_CHARS:
        return text
    return text[: OUTPUT_MAX_CHARS - 1].rstrip() + "…"


def _short(label: str) -> str:
    return label.split(":", 1)[1] if label.startswith(f"{sc.GENTLE_AI}:") else label


def action_text(item: sc.Item, *, saved: bool) -> str:
    if item.action == sc.MOVE:
        text = f"move to skill {item.skill}"
    elif item.action == sc.REMOVE:
        text = "remove"
    else:
        text = "keep"
    for label, chars, how in item.lifted:
        if how == sc.LIFT:
            text += f"; lift {_short(label)} {_k(chars)} into its place (markers kept)"
        else:
            text += f"; drop its nested {_short(label)} (identical copy already kept)"
    if item.note and not item.removes:
        text += f" ({item.note})"
    if saved and item.removes:
        text += f" (−{_k(item.saved)})"
    return text


def item_line(item: sc.Item, *, saved: bool) -> str:
    nested = ""
    if item.nested:
        parts = [f"{_short(label)} {_k(chars)}" for label, chars in item.nested[:4]]
        more = len(item.nested) - 4
        nested = " (nested: " + ", ".join(parts) + (f", … {more} more" if more > 0 else "") + ")"
    return f"- {item.label} {_k(item.chars)}{nested} → {action_text(item, saved=saved)}"


def _impact_cell(fits: bool, lost: tuple[str, ...]) -> str:
    if fits:
        return "fits"
    if not lost:
        return "truncated (no managed block lost)"
    shown = ", ".join(lost[:4]) + (f", … {len(lost) - 4} more" if len(lost) > 4 else "")
    return f"truncated, loses {shown}"


def impact_lines(plan: sc.CleanupPlan, context: soul_mod.ModelContext, *, after: bool) -> list[str]:
    lines = []
    for row in sc.impacts(plan, context):
        now = _impact_cell(row.before_fits, row.before_lost)
        if after:
            later = _impact_cell(row.after_fits, row.after_lost)
            lines.append(f"- {row.label} (cap {row.cap:,}): {now} → {later}")
        else:
            lines.append(f"- {row.label} (cap {row.cap:,}): {now}")
    return lines


def render_plan(plan: sc.CleanupPlan, context: soul_mod.ModelContext) -> str:
    """The dry-run preview (shared with the ``odd_soul_apply`` tool)."""
    where = display_path(plan.path)
    head = f"SOUL.md cleanup plan (dry run, nothing written): {where}"
    if plan.error:
        return f"{head}\nCannot plan: {plan.error}"
    if not plan.exists:
        return f"{head}\nSOUL.md does not exist; nothing to clean."
    lines = [head]
    if plan.items:
        lines.append("Blocks (chars → action):")
        lines.extend(item_line(item, saved=True) for item in plan.items)
    else:
        lines.append("No managed blocks.")
    lines.append(
        f"User text outside blocks: {_k(plan.user_chars)} chars, kept byte-identical "
        "(only blank lines around removed blocks change)."
    )
    if plan.persona_note:
        lines.append(plan.persona_note)
    if not plan.writes:
        lines.append("Nothing to clean: no block the cleanup removes.")
        if plan.persona_optional:
            lines.append(
                "Optional: /odd_soul plan persona previews removing the old gentle-ai "
                "persona (the hermes-odd persona is active)."
            )
        return _fit("\n".join(lines))
    saved = plan.before_chars - plan.after_chars
    lines.append(
        f"Size: {plan.before_chars:,} → {plan.after_chars:,} chars (−{saved:,}; "
        f"~{_tokens(plan.before_chars)} → ~{_tokens(plan.after_chars)} tokens with every message)."
    )
    lines.append("Truncation by Hermes (now → after):")
    lines.extend(impact_lines(plan, context, after=True))
    if plan.persona_optional:
        lines.append(
            "Optional: /odd_soul plan persona also removes the old gentle-ai persona "
            "(the hermes-odd persona is active)."
        )
    lines.append(f"Warning: {sc.BINARY_WARNING}")
    persona = " persona" if plan.remove_persona and not plan.persona_note else ""
    lines.append(
        f"Apply: /odd_soul apply{persona} confirm (backup {sp.SOUL_FILE}{sp.BACKUP_INFIX}"
        f"<UTC timestamp> first, last {sp.BACKUP_KEEP} kept; atomic write, then verified). "
        "Undo: /odd_soul restore."
    )
    return _fit("\n".join(lines))


def render_result(result: sc.CleanupResult) -> str:
    plan = result.plan
    if result.error and not result.written:
        return f"SOUL.md cleanup not applied: {result.error}"
    if not result.written:
        return "SOUL.md cleanup: nothing to do (no block the cleanup removes); unchanged."
    backup = f" (backup {result.backup.name})" if result.backup else ""
    lines = [
        f"SOUL.md cleaned: {plan.before_chars:,} → {plan.after_chars:,} chars{backup}.",
    ]
    removed = [_short(i.label) for i in plan.items if i.action == sc.REMOVE]
    moved = [f"{_short(i.label)} → {i.skill}" for i in plan.items if i.action == sc.MOVE]
    lifted = [_short(label) for i in plan.items for label, _c, how in i.lifted if how == sc.LIFT]
    kept = [_short(i.label) for i in plan.items if not i.removes]
    if removed:
        lines.append("Removed: " + ", ".join(removed))
    if moved:
        lines.append("Moved to lazy skills: " + ", ".join(moved))
    if lifted:
        lines.append("Lifted (kept in place): " + ", ".join(lifted))
    if kept:
        lines.append("Kept: " + ", ".join(kept))
    if result.verified:
        lines.append(
            "Verified on disk: kept and lifted blocks byte-identical and in order, removed "
            "blocks gone, user text unchanged."
        )
    else:
        lines.append(f"Warning: {result.error}")
    if result.rotated:
        lines.append(f"Old backups rotated out: {len(result.rotated)}.")
    lines.append(f"Warning: {sc.BINARY_WARNING}")
    lines.append("Undo: /odd_soul restore 1 (the backup made now).")
    lines.append(NEXT_SESSION_NOTE)
    return _fit("\n".join(lines))


class SoulCommand:
    def __init__(
        self,
        home: Callable[[], Path | None] | None = None,
        model_context: Callable[[Path], soul_mod.ModelContext] = soul_mod.model_context,
    ):
        self._home = home
        self._model_context = model_context

    def home(self) -> Path | None:
        if self._home is None:
            return None
        try:
            value = self._home()
        except Exception:  # noqa: BLE001
            return None
        return Path(value) if value is not None else None

    def context(self) -> soul_mod.ModelContext:
        try:
            home = self.home()
            return self._model_context(home if home is not None else soul_mod.hermes_home())
        except Exception:  # noqa: BLE001
            return soul_mod.ModelContext()

    # -- subcommands ---------------------------------------------------------

    def status(self) -> str:
        plan = sc.plan_cleanup(self.home())
        where = display_path(plan.path)
        if plan.error:
            return f"SOUL.md cleanup status: {where}\nCannot read it: {plan.error}"
        if not plan.exists:
            return f"SOUL.md cleanup status: {where} does not exist; nothing to clean."
        lines = [
            f"SOUL.md cleanup status: {where} · {plan.before_chars:,} chars "
            f"(~{_tokens(plan.before_chars)} tokens)",
        ]
        if plan.items:
            lines.append("Blocks (chars → what the cleanup would do):")
            lines.extend(item_line(item, saved=False) for item in plan.items)
        else:
            lines.append("No managed blocks.")
        lines.append(f"User text outside blocks: {_k(plan.user_chars)} chars (always kept).")
        lines.append("Truncation by Hermes now:")
        lines.extend(impact_lines(plan, self.context(), after=False))
        found = sc.backups(self.home())
        if found:
            lines.append(f"Backups: {len(found)} (newest {found[0].name}); /odd_soul restore")
        else:
            lines.append("Backups: none")
        if plan.writes:
            lines.append(
                f"Next: /odd_soul plan (dry run; saves {plan.before_chars - plan.after_chars:,} "
                "chars)."
            )
        else:
            lines.append("Nothing to clean.")
        return _fit("\n".join(lines))

    def plan(self, persona: bool) -> str:
        return render_plan(sc.plan_cleanup(self.home(), remove_persona=persona), self.context())

    def apply(self, persona: bool) -> str:
        plan = sc.plan_cleanup(self.home(), remove_persona=persona)
        if plan.persona_note and persona:
            return f"SOUL.md cleanup not applied: {plan.persona_note}"
        return render_result(sc.apply_cleanup(plan))

    def restore(self, choice: str | None) -> str:
        home = self.home()
        if not choice:
            found = sc.backups(home)
            if not found:
                return "No hermes-odd SOUL.md backups yet."
            lines = ["SOUL.md backups (newest first):"]
            for number, path in enumerate(found[:MAX_BACKUPS_LISTED], start=1):
                try:
                    size = sc.measure(path.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    size = 0
                lines.append(f"{number}. {path.name} · {size:,} chars")
            lines.append(
                "Restore one: /odd_soul restore <N or name> (the current SOUL.md is backed up "
                "first, so it can be undone the same way)."
            )
            return "\n".join(lines)
        result = sc.restore_backup(choice, home)
        if result.error and not result.written:
            return f"SOUL.md not restored: {result.error}"
        backup = f"; the previous file is backup {result.backup.name}" if result.backup else ""
        name = result.chosen.name if result.chosen else choice
        text = f"SOUL.md restored from {name}{backup}."
        if result.error:
            text += f"\nWarning: {result.error}"
        return text + "\n" + NEXT_SESSION_NOTE

    # -- dispatch ------------------------------------------------------------

    def handle(self, raw_args: str) -> str:
        words = (raw_args or "").split()
        head = words[0].lower() if words else "status"
        rest = [w.lower() for w in words[1:]]
        if head == "status" and not rest:
            return self.status()
        if head == "plan" and rest in ([], ["persona"]):
            return self.plan(persona=bool(rest))
        if head == "apply":
            if rest in (["confirm"], ["persona", "confirm"]):
                return self.apply(persona=len(rest) == 2)
            if rest in ([], ["persona"]):
                return (
                    "Not applied: add `confirm` (/odd_soul apply"
                    + (" persona" if rest else "")
                    + " confirm) after reading /odd_soul plan."
                )
        if head == "restore" and len(words) <= 2:
            return self.restore(words[1] if len(words) == 2 else None)
        return f"Usage: {USAGE}"


def make_odd_soul(command: SoulCommand) -> CommandSpec:
    return CommandSpec(
        name="odd_soul",
        description="Clean gentle-ai blocks out of SOUL.md: status, dry-run plan, apply, restore",
        handler=command.handle,
        args_hint="[status|plan [persona]|apply [persona] confirm|restore [N]]",
        group="Setup",
    )


__all__ = ["SoulCommand", "USAGE", "make_odd_soul", "render_plan", "render_result"]
