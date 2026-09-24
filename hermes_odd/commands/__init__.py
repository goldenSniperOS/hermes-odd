"""ODD slash commands. Later tasks add specs in :func:`build_registry`."""

from __future__ import annotations

from .meta import make_odd_commands
from .registry import (
    COMMAND_NAME_RE,
    CommandRegistry,
    CommandSpec,
    hermes_command_key,
    validate_command_name,
)


def build_registry() -> CommandRegistry:
    """Return the registry holding every odd command."""
    registry = CommandRegistry()
    registry.add(make_odd_commands(registry))
    return registry


__all__ = [
    "COMMAND_NAME_RE",
    "CommandRegistry",
    "CommandSpec",
    "build_registry",
    "hermes_command_key",
    "validate_command_name",
]
