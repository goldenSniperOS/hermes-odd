"""ODD slash commands. Later tasks add specs in :func:`build_registry`."""

from __future__ import annotations

from ..agents import AgentStore
from .agents import make_odd_agents
from .meta import make_odd_commands
from .registry import (
    COMMAND_NAME_RE,
    CommandRegistry,
    CommandSpec,
    hermes_command_key,
    validate_command_name,
)


def build_registry(agent_store: AgentStore | None = None) -> CommandRegistry:
    """Return the registry holding every odd command.

    ``agent_store`` feeds ``/odd_agents``; without one an empty in-memory store
    is used (the command then answers that no subagents are recorded).
    """
    registry = CommandRegistry()
    registry.add(make_odd_commands(registry))
    registry.add(make_odd_agents(agent_store if agent_store is not None else AgentStore()))
    return registry


__all__ = [
    "COMMAND_NAME_RE",
    "CommandRegistry",
    "CommandSpec",
    "build_registry",
    "hermes_command_key",
    "validate_command_name",
]
