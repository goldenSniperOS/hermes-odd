"""End-to-end smoke test against a real Hermes install.

Loads hermes-odd through Hermes' own ``PluginManager`` inside a throwaway
``HERMES_HOME`` and checks what the plugin registered:

* the plugin loaded without error;
* ``odd-commands`` is registered and its handler lists itself as plain text;
* the ``hermes-odd-workflow`` prompt section is registered, renders, and fits
  in 4000 characters;
* the three ``hermes-odd:*`` ODD skills are registered.

Isolation: the temporary home holds only a ``config.yaml`` that enables
``hermes-odd`` and a ``plugins/hermes-odd`` symlink to this checkout. Nothing
is read from or written to the real ``~/.hermes`` (no ``.env``, no config,
no credentials); there is no network, gateway, or model call. Bytecode
writing is disabled so neither this checkout nor the Hermes install gets
``__pycache__`` files.

Usage (run with the Hermes interpreter):

    ~/.hermes/hermes-agent/venv/bin/python scripts/smoke_e2e.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import os  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PLUGIN = "hermes-odd"
COMMAND_KEY = "odd-commands"
SECTION_ID = "hermes-odd-workflow"
SECTION_LIMIT = 4000
EXPECTED_SKILLS = ["odd-delegation", "odd-feature-tracking", "odd-workflow"]


class SmokeFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)
    print(f"ok: {message}")


def run(temp_home: Path) -> None:
    from hermes_cli.plugins import PluginManager
    from hermes_constants import get_hermes_home

    check(
        get_hermes_home().resolve() == temp_home.resolve(),
        f"Hermes resolves HERMES_HOME to the throwaway home {temp_home}",
    )

    # A fresh manager, not the process-global one: nothing else in this
    # process has discovered plugins, and the scope is bound to temp_home.
    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins.get(PLUGIN)
    check(loaded is not None, f"{PLUGIN} was discovered from {temp_home / 'plugins'}")
    check(loaded.enabled and not loaded.error, f"{PLUGIN} loaded (error={loaded.error!r})")
    check(
        Path(loaded.manifest.path).resolve() == REPO,
        f"{PLUGIN} loaded from this checkout ({REPO})",
    )

    command = manager._plugin_commands.get(COMMAND_KEY)
    check(command is not None, f"/{COMMAND_KEY} is registered")
    output = command["handler"]("")
    check(isinstance(output, str) and output.strip() != "", f"/{COMMAND_KEY} returns text")
    check("/odd_commands" in output, f"/{COMMAND_KEY} output lists itself")
    print("---- /odd-commands output ----")
    print(output)
    print("------------------------------")

    section = manager._system_prompt_sections.get(SECTION_ID)
    check(section is not None, f"prompt section {SECTION_ID!r} is registered")
    check(section.max_chars <= SECTION_LIMIT, f"section max_chars {section.max_chars} <= 4000")
    rendered = {s.id: s for s in manager.render_system_prompt_sections({"platform": "cli"})}
    check(SECTION_ID in rendered, f"Hermes renders {SECTION_ID!r} (not skipped)")
    size = len(rendered[SECTION_ID].content)
    check(size <= SECTION_LIMIT, f"rendered section is {size} chars (<= {SECTION_LIMIT})")

    skills = manager.list_plugin_skills(PLUGIN)
    check(skills == EXPECTED_SKILLS, f"skills registered as {PLUGIN}:* -> {skills}")
    for name in EXPECTED_SKILLS:
        path = manager.find_plugin_skill(f"{PLUGIN}:{name}")
        check(path is not None and Path(path).is_file(), f"{PLUGIN}:{name} resolves to a file")


def main() -> int:
    hermes_agent = Path(
        os.environ.get("HERMES_AGENT_DIR", Path.home() / ".hermes" / "hermes-agent")
    )
    temp_home = Path(tempfile.mkdtemp(prefix="hermes-odd-smoke-"))
    try:
        (temp_home / "plugins").mkdir()
        (temp_home / "plugins" / PLUGIN).symlink_to(REPO, target_is_directory=True)
        (temp_home / "config.yaml").write_text(
            f"plugins:\n  enabled:\n    - {PLUGIN}\n", encoding="utf-8"
        )
        # Must be set before any Hermes import: several modules resolve the
        # home (and load its .env) at import time.
        os.environ["HERMES_HOME"] = str(temp_home)
        os.environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
        os.environ.pop("HERMES_SAFE_MODE", None)
        if str(hermes_agent) not in sys.path:
            sys.path.append(str(hermes_agent))

        run(temp_home)
    except SmokeFailure as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        # Drop the symlink first so cleanup can never reach this checkout.
        link = temp_home / "plugins" / PLUGIN
        if link.is_symlink():
            link.unlink()
        shutil.rmtree(temp_home, ignore_errors=True)
    print("smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
