"""Test double for Hermes' ``PluginContext`` (no Hermes import)."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def ensure_repo_on_path() -> None:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


class FakeState:
    """Dict-backed stand-in for ``PluginState`` (``get``/``set``, JSON only)."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.sets = 0

    def get(self, key: str, default: Any = None) -> Any:
        raw = self.data.get(key)
        return default if raw is None else json.loads(raw)

    def set(self, key: str, value: Any) -> None:
        # Round-trip through JSON like the real state file.
        self.data[key] = json.dumps(value, ensure_ascii=False)
        self.sets += 1

    def dump(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)


def mark_setup_complete(state: FakeState) -> None:
    """Store a completed first-run setup record (no answers): the section then
    renders exactly ``ODD_SECTION`` (no pending or TDD line)."""
    state.set(
        "setup",
        {
            "schema": "hermes-odd.setup/v1",
            "version": 1,
            "completed_at": "2026-01-01T00:00:00Z",
            "skipped": False,
            "answers": {},
        },
    )


class FakeContext:
    """Records every ``register_*`` call made by the plugin."""

    def __init__(self) -> None:
        self.state = FakeState()
        self.commands: dict[str, dict[str, Any]] = {}
        self.hooks: list[tuple] = []
        self.prompt_sections: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.skills: dict[str, dict[str, Any]] = {}
        self.calls: list[str] = []

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        args_hint: str = "",
        argument_mode: str | None = None,
    ) -> None:
        self.calls.append("register_command")
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "args_hint": args_hint,
            "argument_mode": argument_mode,
        }

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        self.calls.append("register_hook")
        self.hooks.append((hook_name, callback))

    def fire(self, hook_name: str, **kwargs: Any) -> None:
        """Invoke registered callbacks with kwargs, as ``invoke_hook`` does."""
        for name, callback in self.hooks:
            if name == hook_name:
                callback(**kwargs)

    def register_system_prompt_section(self, id: str, content: Any, **kwargs: Any) -> None:
        self.calls.append("register_system_prompt_section")
        self.prompt_sections.append({"id": id, "content": content, **kwargs})

    def register_skill(
        self,
        name: str,
        path: Path,
        description: str = "",
        frontmatter: Mapping[str, Any] | None = None,
    ) -> None:
        # Mirrors PluginContext.register_skill validation (hermes_cli/plugins.py).
        self.calls.append("register_skill")
        if ":" in name or not re.fullmatch(r"[a-zA-Z0-9_-]+", name or ""):
            raise ValueError(f"invalid skill name {name!r}")
        if not Path(path).exists():
            raise FileNotFoundError(path)
        self.skills[name] = {
            "path": Path(path),
            "description": description,
            "frontmatter": dict(frontmatter or {}),
        }

    def register_tool(self, **kwargs: Any) -> None:
        self.calls.append("register_tool")
        self.tools.append(kwargs)


class BareContext:
    """A ctx exposing none of the optional registration methods."""


class ExplodingContext(FakeContext):
    def register_command(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")
