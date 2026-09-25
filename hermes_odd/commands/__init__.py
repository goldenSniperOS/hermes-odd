"""ODD slash commands. Later tasks add specs in :func:`build_registry`."""

from __future__ import annotations

from ..agents import AgentStore, MemoryBackend
from ..changes import ChangeStore
from ..probes import Prober
from ..projects import ProjectStore
from ..runtime import RuntimeInfo
from ..setup import Setup
from .agents import make_odd_agents
from .changes import make_odd_changes
from .doctor import Doctor, make_odd_doctor
from .meta import make_odd_commands
from .registry import (
    COMMAND_NAME_RE,
    CommandRegistry,
    CommandSpec,
    hermes_command_key,
    validate_command_name,
)
from .review_mode import ReviewModeCommand, make_odd_review_mode
from .setup import SetupCommand, make_odd_setup
from .soul import SoulCommand, make_odd_soul
from .status import Status, make_odd_status
from .tasks import make_odd_tasks


def build_registry(
    agent_store: AgentStore | None = None,
    project_store: ProjectStore | None = None,
    change_store: ChangeStore | None = None,
    runtime: RuntimeInfo | None = None,
    prober: Prober | None = None,
    setup: Setup | None = None,
) -> CommandRegistry:
    """Return the registry holding every odd command.

    ``agent_store`` feeds ``/odd_agents``; without one an empty in-memory store
    is used (the command then answers that no subagents are recorded).
    ``project_store`` feeds ``/odd_tasks`` with known project roots; without
    one only the process's own directories are searched. ``change_store``
    feeds ``/odd_changes``; without one an empty in-memory store is used.
    ``runtime`` (what ``register`` registered) feeds ``/odd_status`` and
    ``/odd_doctor``; ``prober`` is the cached gentle-ai prober they share with
    ``/odd_review_mode`` (which resolves projects like ``/odd_tasks``).
    ``setup`` feeds ``/odd_setup``; without one an in-memory setup is used.
    ``/odd_soul`` works on the Hermes home's ``SOUL.md``.
    """
    agents = agent_store if agent_store is not None else AgentStore()
    changes = change_store if change_store is not None else ChangeStore(agent_store=agent_store)
    shared_prober = prober if prober is not None else Prober()
    registry = CommandRegistry()
    registry.add(make_odd_agents(agents))
    registry.add(make_odd_tasks(project_store))
    registry.add(make_odd_changes(changes))
    registry.add(make_odd_review_mode(ReviewModeCommand(shared_prober, project_store)))
    registry.add(
        make_odd_setup(SetupCommand(setup if setup is not None else Setup(backend=MemoryBackend())))
    )
    registry.add(make_odd_soul(SoulCommand()))
    registry.add(make_odd_status(Status(runtime, shared_prober, agents, changes, project_store)))
    registry.add(make_odd_doctor(Doctor(runtime, shared_prober, project_store=project_store)))
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
