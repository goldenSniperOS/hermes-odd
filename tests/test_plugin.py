from __future__ import annotations

import importlib.util
import re
import sys
import types
import unittest

from fake_context import REPO_ROOT, BareContext, ExplodingContext, FakeContext, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.commands import (  # noqa: E402
    CommandRegistry,
    CommandSpec,
    build_registry,
    hermes_command_key,
)

TELEGRAM_SAFE = re.compile(r"^[a-z0-9_]+$")


class RegisterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = FakeContext()
        register(self.ctx)

    def test_registers_odd_commands_under_hermes_key(self) -> None:
        self.assertIn("odd-commands", self.ctx.commands)
        self.assertTrue(self.ctx.commands["odd-commands"]["description"])

    def test_odd_commands_lists_itself_as_plain_text(self) -> None:
        output = self.ctx.commands["odd-commands"]["handler"]("")
        self.assertIsInstance(output, str)
        self.assertTrue(output.strip())
        self.assertIn("/odd_commands", output)
        self.assertIn("List hermes-odd commands", output)
        self.assertNotIn("<", output)  # no markup

    def test_output_is_identical_across_calls_and_args(self) -> None:
        handler = self.ctx.commands["odd-commands"]["handler"]
        self.assertEqual(handler(""), handler("  "))

    def test_every_spec_name_is_telegram_safe(self) -> None:
        for spec in build_registry():
            self.assertRegex(spec.name, TELEGRAM_SAFE)
            self.assertLessEqual(len(spec.name), 32)

    def test_registered_keys_round_trip_through_gateway_normalization(self) -> None:
        # gateway/run.py looks up command.replace("_", "-"); Telegram shows "-" as "_".
        for key in self.ctx.commands:
            telegram_name = key.replace("-", "_")
            self.assertRegex(telegram_name, TELEGRAM_SAFE)
            self.assertEqual(telegram_name.replace("_", "-"), key)

    def test_registers_observer_hooks_only(self) -> None:
        names = sorted(name for name, _ in self.ctx.hooks)
        # post_tool_call twice: subagent tracking and change capture are
        # separate callbacks (Hermes bounds and suppresses per callback).
        self.assertEqual(
            names,
            [
                "on_session_start",
                "post_tool_call",
                "post_tool_call",
                "subagent_start",
                "subagent_stop",
            ],
        )
        self.assertNotIn("pre_tool_call", names)  # fails closed on timeout in Hermes
        # The only tool is the first-run setup's write path.
        self.assertEqual([t["name"] for t in self.ctx.tools], ["odd_setup_apply"])

    def test_manifest_lists_the_registered_hooks(self) -> None:
        manifest = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        line = next(ln for ln in manifest.splitlines() if ln.startswith("provides_hooks:"))
        for name, _ in self.ctx.hooks:
            self.assertIn(name, line)

    def test_manifest_lists_the_registered_tools(self) -> None:
        manifest = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        line = next(ln for ln in manifest.splitlines() if ln.startswith("provides_tools:"))
        self.assertEqual(line, "provides_tools: [odd_setup_apply]")
        for tool in self.ctx.tools:
            self.assertIn(tool["name"], line)


class DefensiveRegistrationTests(unittest.TestCase):
    def test_missing_register_command_does_not_raise(self) -> None:
        with self.assertLogs("hermes_odd", level="WARNING"):
            register(BareContext())

    def test_raising_register_command_does_not_raise(self) -> None:
        with self.assertLogs("hermes_odd", level="WARNING"):
            register(ExplodingContext())

    def test_failing_handler_returns_text(self) -> None:
        from hermes_odd.plugin import register_commands

        def broken(raw_args: str) -> str:
            raise ValueError("bad input")

        registry = CommandRegistry()
        registry.add(CommandSpec(name="odd_broken", description="x", handler=broken))
        ctx = FakeContext()
        register_commands(ctx, registry)
        with self.assertLogs("hermes_odd", level="WARNING"):
            output = ctx.commands["odd-broken"]["handler"]("")
        self.assertIn("failed", output)


class RegistryValidationTests(unittest.TestCase):
    def test_rejects_unsafe_names(self) -> None:
        for bad in ["odd-x", "Odd", "odd x", "_odd", "odd__x", "a" * 33, ""]:
            with self.subTest(name=bad), self.assertRaises(ValueError):
                CommandRegistry().add(CommandSpec(name=bad, description="d", handler=str))

    def test_rejects_duplicates(self) -> None:
        registry = CommandRegistry()
        registry.add(CommandSpec(name="odd_x", description="d", handler=str))
        with self.assertRaises(ValueError):
            registry.add(CommandSpec(name="odd_x", description="d", handler=str))

    def test_hermes_key(self) -> None:
        self.assertEqual(hermes_command_key("odd_review_mode"), "odd-review-mode")


class DirectoryLoaderTests(unittest.TestCase):
    """Import the root __init__.py the way PluginManager._load_directory_module does."""

    NS = "hermes_odd_test_plugins"

    def tearDown(self) -> None:
        for name in [n for n in sys.modules if n == self.NS or n.startswith(self.NS + ".")]:
            del sys.modules[name]

    def test_root_entry_point_uses_relative_package_import(self) -> None:
        ns_pkg = types.ModuleType(self.NS)
        ns_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules[self.NS] = ns_pkg
        module_name = f"{self.NS}.hermes_odd"
        spec = importlib.util.spec_from_file_location(
            module_name,
            REPO_ROOT / "__init__.py",
            submodule_search_locations=[str(REPO_ROOT)],
        )
        module = importlib.util.module_from_spec(spec)
        module.__package__ = module_name
        module.__path__ = [str(REPO_ROOT)]  # type: ignore[attr-defined]
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self.assertTrue(module.register.__module__.startswith(module_name + "."))
        ctx = FakeContext()
        module.register(ctx)
        self.assertIn("odd-commands", ctx.commands)


if __name__ == "__main__":
    unittest.main()
