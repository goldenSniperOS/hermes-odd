"""``/gentle_commands``: list every gentle command (Pi ``gentle:commands``)."""

from __future__ import annotations

from .registry import CommandRegistry, CommandSpec


def make_gentle_commands(registry: CommandRegistry) -> CommandSpec:
    def handler(raw_args: str) -> str:
        specs = registry.all()
        lines = ["gentle-hermes commands:"]
        for spec in specs:
            usage = f"/{spec.name}"
            if spec.args_hint:
                usage = f"{usage} {spec.args_hint}"
            lines.append(f"- {usage}: {spec.description}")
        lines.append("")
        lines.append(
            "Gateways accept /name or its hyphen form; the CLI uses the hyphen "
            "form (for example /gentle-commands)."
        )
        return "\n".join(lines)

    return CommandSpec(
        name="gentle_commands",
        description="List gentle-hermes commands",
        handler=handler,
    )
