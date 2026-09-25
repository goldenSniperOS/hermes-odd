"""What ``register(ctx)`` actually registered, for ``/odd_status`` and ``/odd_doctor``.

The commands report the plugin's own surface (prompt section, skills, hooks,
state backend) from this record instead of guessing: ``register`` fills it in
as each step succeeds or fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuntimeInfo:
    ctx: Any = None
    section_registered: bool = False
    section_chars: int = 0
    skills_dir: Path | None = None
    skills: list[str] = field(default_factory=list)  # registered names
    hooks_expected: int = 0
    hooks_registered: int = 0
    commands_registered: int = 0
    tools_registered: int = 0
    stores: dict[str, Any] = field(default_factory=dict)  # name -> store

    def skills_layout(self) -> str:
        """``wheel`` (``hermes_odd/_skills``), ``clone`` (``<plugin>/skills``) or ``none``."""
        if self.skills_dir is None:
            return "none"
        return "wheel" if self.skills_dir.name == "_skills" else "clone"

    def fallback_stores(self) -> list[str]:
        """Stores that switched to the in-memory backend (``ctx.state`` failed)."""
        names = []
        for name, store in self.stores.items():
            if getattr(store, "_using_fallback", False):
                names.append(name)
        return names
