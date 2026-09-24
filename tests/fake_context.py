"""Test double for Hermes' ``PluginContext`` (no Hermes import)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent


def ensure_repo_on_path() -> None:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


class FakeContext:
    """Records every ``register_*`` call made by the plugin."""

    def __init__(self) -> None:
        self.commands: Dict[str, Dict[str, Any]] = {}
        self.hooks: List[tuple] = []
        self.prompt_sections: List[Dict[str, Any]] = []
        self.tools: List[Dict[str, Any]] = []
        self.calls: List[str] = []

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

    def register_system_prompt_section(self, id: str, content: Any, **kwargs: Any) -> None:
        self.calls.append("register_system_prompt_section")
        self.prompt_sections.append({"id": id, "content": content, **kwargs})

    def register_tool(self, **kwargs: Any) -> None:
        self.calls.append("register_tool")
        self.tools.append(kwargs)


class BareContext:
    """A ctx exposing none of the optional registration methods."""


class ExplodingContext(FakeContext):
    def register_command(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")
