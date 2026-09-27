"""``/odd-commands``: list every hermes-odd command (Pi ``gentle:commands``)."""

from __future__ import annotations

from .registry import CommandRegistry, CommandSpec

GROUP_ORDER = ("Viewers", "Review", "Setup", "Health")


def make_odd_commands(registry: CommandRegistry) -> CommandSpec:
    def handler(raw_args: str) -> str:
        specs = registry.all()
        groups: dict[str, list[CommandSpec]] = {}
        for spec in specs:
            groups.setdefault(spec.group or "Other", []).append(spec)
        order = [g for g in GROUP_ORDER if g in groups] + [
            g for g in groups if g not in GROUP_ORDER
        ]
        lines = ["hermes-odd commands:"]
        for group in order:
            lines.append("")
            lines.append(f"{group}:")
            for spec in groups[group]:
                usage = f"/{spec.hermes_key}"
                if spec.args_hint:
                    usage = f"{usage} {spec.args_hint}"
                lines.append(f"- {usage}: {spec.description}")
        lines.append("")
        lines.append(
            "Gateways also accept the underscore form Telegram's menu shows "
            "(for example /odd_commands); the CLI accepts only the hyphen form."
        )
        return "\n".join(lines)

    return CommandSpec(
        name="odd_commands",
        description="List hermes-odd commands",
        handler=handler,
        group="Health",
    )
