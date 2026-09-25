"""ODD slash commands. Later tasks add specs in :func:`build_registry`."""

from __future__ import annotations

from ..agents import AgentStore
from ..projects import ProjectStore
from .agents import make_odd_agents
from .meta import make_odd_commands
from .registry import (
    COMMAND_NAME_RE,
    CommandRegistry,
    CommandSpec,
    hermes_command_key,
    validate_command_name,
)
from .tasks import make_odd_tasks


def build_registry(
    agent_store: AgentStore | None = None, project_store: ProjectStore | None = None
) -> CommandRegistry:
    """Return the registry holding every odd command.

    ``agent_store`` feeds ``/odd_agents``; without one an empty in-memory store
    is used (the command then answers that no subagents are recorded).
    ``project_store`` feeds ``/odd_tasks`` with known project roots; without
    one only the process's own directories are searched.
    """
    registry = CommandRegistry()
    registry.add(make_odd_commands(registry))
    registry.add(make_odd_agents(agent_store if agent_store is not None else AgentStore()))
    registry.add(make_odd_tasks(project_store))
    return registry


__all__ = [
    "COMMAND_NAME_RE",
    "CommandRegistry",
    "CommandSpec",
    "build_registry",
    "hermes_command_key",
    "validate_command_name",
]
