"""Declarative slash-command registry for hermes-odd.

Every hermes-odd command is a :class:`CommandSpec` whose handler takes the raw
argument string and returns plain text. Handlers never call the model, so the
same text is returned in the CLI, the TUI and every gateway.

Naming (verified against hermes-agent source):

* ``PluginContext.register_command`` (``hermes_cli/plugins.py``) only
  lowercases, strips ``/`` and turns spaces into ``-``; the result is the
  exact key stored in the plugin command table.
* The CLI (``cli.py`` ``process_command``) and TUI
  (``tui_gateway/methods_tools.py``) look that key up verbatim.
* Gateways (``gateway/run.py`` plugin dispatch) look up
  ``command.replace("_", "-")``: a key registered with underscores is never
  found there.
* The Telegram menu (``hermes_cli/commands.py`` ``_sanitize_telegram_name``)
  shows ``-`` as ``_`` and keeps only ``[a-z0-9_]``, at most 32 characters.
  Plugin commands whose ``args_hint`` starts with ``<`` are left out of the
  menu (``_requires_argument``), so optional arguments use ``[...]``.

So a spec name is the Telegram-safe form users type in gateways
(``odd_commands``) and :func:`hermes_command_key` gives the hyphenated key
registered with Hermes (``odd-commands``). Gateways accept both
``/odd_commands`` and ``/odd-commands``; the CLI accepts the hyphen form.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

COMMAND_NAME_RE = re.compile(r"^[a-z0-9_]+$")
COMMAND_NAME_MAX_CHARS = 32

Handler = Callable[[str], str]


@dataclass(frozen=True)
class CommandSpec:
    """One hermes-odd slash command."""

    name: str
    description: str
    handler: Handler
    args_hint: str = ""
    group: str = ""  # heading in /odd_commands ("Viewers", "Review", "Health")

    @property
    def hermes_key(self) -> str:
        return hermes_command_key(self.name)


def hermes_command_key(name: str) -> str:
    """Return the key registered with Hermes for a Telegram-safe name."""
    return name.replace("_", "-")


def validate_command_name(name: str) -> None:
    if not isinstance(name, str) or not COMMAND_NAME_RE.fullmatch(name):
        raise ValueError(f"odd command name {name!r} must match [a-z0-9_]+")
    if len(name) > COMMAND_NAME_MAX_CHARS:
        raise ValueError(f"odd command name {name!r} exceeds {COMMAND_NAME_MAX_CHARS} characters")
    if name.startswith("_") or name.endswith("_") or "__" in name:
        # Telegram sanitization collapses and strips these, which would break
        # the round-trip back to the registered key.
        raise ValueError(f"odd command name {name!r} has leading, trailing or doubled '_'")


class CommandRegistry:
    """Ordered collection of :class:`CommandSpec` with unique names."""

    def __init__(self) -> None:
        self._specs: dict[str, CommandSpec] = {}

    def add(self, spec: CommandSpec) -> CommandSpec:
        validate_command_name(spec.name)
        if spec.name in self._specs:
            raise ValueError(f"odd command {spec.name!r} is already registered")
        if not callable(spec.handler):
            raise TypeError(f"odd command {spec.name!r} handler is not callable")
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    def all(self) -> list[CommandSpec]:
        return list(self._specs.values())

    def __iter__(self) -> Iterator[CommandSpec]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._specs)
