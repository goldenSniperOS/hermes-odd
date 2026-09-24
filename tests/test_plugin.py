from __future__ import annotations

import importlib.util
import re
import sys
import types
import unittest

from fake_context import REPO_ROOT, BareContext, ExplodingContext, FakeContext, ensure_repo_on_path

ensure_repo_on_path()

from gentle_hermes import register  # noqa: E402
from gentle_hermes.commands import (  # noqa: E402
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

    def test_registers_gentle_commands_under_hermes_key(self) -> None:
        self.assertIn("gentle-commands", self.ctx.commands)
        self.assertTrue(self.ctx.commands["gentle-commands"]["description"])

    def test_gentle_commands_lists_itself_as_plain_text(self) -> None:
        output = self.ctx.commands["gentle-commands"]["handler"]("")
        self.assertIsInstance(output, str)
        self.assertTrue(output.strip())
        self.assertIn("/gentle_commands", output)
        self.assertIn("List gentle-hermes commands", output)
        self.assertNotIn("<", output)  # no markup

    def test_output_is_identical_across_calls_and_args(self) -> None:
        handler = self.ctx.commands["gentle-commands"]["handler"]
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

    def test_no_other_surfaces_registered_yet(self) -> None:
        self.assertEqual(self.ctx.hooks, [])
        self.assertEqual(self.ctx.prompt_sections, [])
        self.assertEqual(self.ctx.tools, [])


class DefensiveRegistrationTests(unittest.TestCase):
    def test_missing_register_command_does_not_raise(self) -> None:
        with self.assertLogs("gentle_hermes", level="WARNING"):
            register(BareContext())

    def test_raising_register_command_does_not_raise(self) -> None:
        with self.assertLogs("gentle_hermes", level="WARNING"):
            register(ExplodingContext())

    def test_failing_handler_returns_text(self) -> None:
        from gentle_hermes.plugin import register_commands

        def broken(raw_args: str) -> str:
            raise ValueError("bad input")

        registry = CommandRegistry()
        registry.add(CommandSpec(name="gentle_broken", description="x", handler=broken))
        ctx = FakeContext()
        register_commands(ctx, registry)
        with self.assertLogs("gentle_hermes", level="WARNING"):
            output = ctx.commands["gentle-broken"]["handler"]("")
        self.assertIn("failed", output)


class RegistryValidationTests(unittest.TestCase):
    def test_rejects_unsafe_names(self) -> None:
        for bad in ["gentle-x", "Gentle", "gentle x", "_gentle", "gentle__x", "a" * 33, ""]:
            with self.subTest(name=bad), self.assertRaises(ValueError):
                CommandRegistry().add(CommandSpec(name=bad, description="d", handler=str))

    def test_rejects_duplicates(self) -> None:
        registry = CommandRegistry()
        registry.add(CommandSpec(name="gentle_x", description="d", handler=str))
        with self.assertRaises(ValueError):
            registry.add(CommandSpec(name="gentle_x", description="d", handler=str))

    def test_hermes_key(self) -> None:
        self.assertEqual(hermes_command_key("gentle_review_mode"), "gentle-review-mode")


class DirectoryLoaderTests(unittest.TestCase):
    """Import the root __init__.py the way PluginManager._load_directory_module does."""

    NS = "gentle_test_hermes_plugins"

    def tearDown(self) -> None:
        for name in [n for n in sys.modules if n == self.NS or n.startswith(self.NS + ".")]:
            del sys.modules[name]

    def test_root_entry_point_uses_relative_package_import(self) -> None:
        ns_pkg = types.ModuleType(self.NS)
        ns_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules[self.NS] = ns_pkg
        module_name = f"{self.NS}.gentle_hermes"
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
        self.assertIn("gentle-commands", ctx.commands)


if __name__ == "__main__":
    unittest.main()
