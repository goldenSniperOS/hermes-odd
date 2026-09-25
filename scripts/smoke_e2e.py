"""End-to-end smoke test against a real Hermes install.

Loads hermes-odd through Hermes' own ``PluginManager`` inside a throwaway
``HERMES_HOME`` and checks what the plugin registered:

* the plugin loaded without error;
* ``odd-commands`` is registered and its handler lists itself as plain text;
* the ``hermes-odd-workflow`` prompt section is registered, renders, and fits
  in 4000 characters;
* the three ``hermes-odd:*`` ODD skills are registered;
* the subagent observer hooks are registered, and a synthetic
  ``subagent_start`` / ``post_tool_call`` / ``subagent_stop`` lifecycle
  dispatched through Hermes' own ``PluginManager.invoke_hook`` shows up in
  ``/odd-agents`` (list and detail), persisted in the throwaway home's
  ``plugin-data`` state, with the fake secret in the tool args never stored;
* ``/odd-tasks``: the section is rendered through Hermes' own path
  (``agent.system_prompt._plugin_session_info`` with a pinned session cwd,
  then ``PluginManager.render_system_prompt_sections``) for a throwaway git
  repository holding ``odd/tasks/demo.md``; the rendered text stays
  byte-identical, the repository is recorded as a known project, and
  ``/odd-tasks`` lists and details the demo feature;
* ``/odd-changes``: in a throwaway git repository with one committed file,
  a synthetic ``write_file`` (new file) and ``patch`` (edit of the committed
  file) are dispatched through ``PluginManager.invoke_hook("post_tool_call")``
  with Hermes' result shapes (``resolved_path``, ``files_modified``, the
  ``difflib`` unified diff); ``/odd-changes`` lists both with the right
  counts and attribution, the detail shows the timeline and the real
  ``git diff --numstat``, a failed call leaves no row, and the fake secret in
  the content never reaches state or output.

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
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PLUGIN = "hermes-odd"
COMMAND_KEY = "odd-commands"
SECTION_ID = "hermes-odd-workflow"
SECTION_LIMIT = 4000
EXPECTED_SKILLS = ["odd-delegation", "odd-feature-tracking", "odd-workflow"]
AGENT_HOOKS = ["on_session_start", "subagent_start", "post_tool_call", "subagent_stop"]
FAKE_SECRET = "sk-smoke-FAKE-SECRET-not-real"


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

    run_agents_lifecycle(manager, temp_home)
    run_tasks_viewer(manager, temp_home, rendered[SECTION_ID].content)
    run_changes_viewer(manager, temp_home)


def run_agents_lifecycle(manager, temp_home: Path) -> None:
    for hook in AGENT_HOOKS:
        check(bool(manager._hooks.get(hook)), f"hook {hook!r} is registered")
    check(not manager._hooks.get("pre_tool_call"), "pre_tool_call is not registered")

    parent = "smoke-parent-session"
    child = "smoke-child-session"
    subagent_id = "sa-0-5e0e5e0e"
    # Same kwargs shape as run_agent / delegate_tool / model_tools.
    manager.invoke_hook("on_session_start", session_id=parent, model="smoke", platform="telegram")
    manager.invoke_hook(
        "subagent_start",
        parent_session_id=parent,
        parent_turn_id="turn-1",
        parent_subagent_id=None,
        child_session_id=child,
        child_subagent_id=subagent_id,
        child_role="leaf",
        child_goal="Smoke: read the README and summarize the install steps",
    )
    for name, status in (("read_file", "ok"), ("search_files", "ok"), ("terminal", "error")):
        manager.invoke_hook(
            "post_tool_call",
            tool_name=name,
            args={"path": "README.md", "token": FAKE_SECRET},
            result=f'{{"content": "{FAKE_SECRET}"}}',
            task_id=subagent_id,
            session_id=child,
            tool_call_id=f"call-{name}",
            turn_id="turn-1",
            api_request_id="",
            duration_ms=42,
            status=status,
            error_type="tool_error" if status == "error" else None,
            error_message=FAKE_SECRET if status == "error" else None,
            middleware_trace=[],
        )
    manager.invoke_hook(
        "subagent_stop",
        parent_session_id=parent,
        parent_turn_id="turn-1",
        child_session_id=child,
        child_role="leaf",
        child_summary="Install with hermes plugins install; enable in config.yaml.",
        child_status="completed",
        tool_call_history=[{"tool_name": "read_file", "tool_input": FAKE_SECRET, "status": "ok"}],
        duration_ms=61_000,
    )

    command = manager._plugin_commands.get("odd-agents")
    check(command is not None, "/odd-agents is registered")
    listing = command["handler"]("")
    check("✓ 5e0e5e0e leaf" in listing, "/odd-agents lists the completed subagent")
    check("last: terminal error · 3 tools" in listing, "/odd-agents shows the last tool and count")
    detail = command["handler"]("5e0e")
    check("platform: telegram" in detail, "detail resolves the parent platform")
    check("summary:" in detail and "hermes plugins install" in detail, "detail shows the summary")
    print("---- /odd-agents output ----")
    print(listing)
    print("---- /odd-agents 5e0e output ----")
    print(detail)
    print("----------------------------")

    state_files = list((temp_home / "plugin-data").rglob("state.json"))
    check(len(state_files) == 1, f"agent state persisted under {temp_home / 'plugin-data'}")
    raw = state_files[0].read_text(encoding="utf-8")
    check("hermes-odd.agents/v1" in raw, "state document uses schema hermes-odd.agents/v1")
    check(FAKE_SECRET not in raw + listing + detail, "tool args and results never stored or shown")


DEMO_DOC = """\
# Feature: smoke demo

## Tasks

- [x] T1 Create the demo repository
- [ ] T2 Show it in /odd_tasks
      (continuation line)

## Next step

T2 show it.
"""


def run_tasks_viewer(manager, temp_home: Path, baseline_section: str) -> None:
    import types

    from agent.runtime_cwd import clear_session_cwd, set_session_cwd
    from agent.system_prompt import _plugin_session_info

    repo = temp_home / "work" / "demo-project"
    (repo / "odd" / "tasks").mkdir(parents=True)
    try:
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        (repo / ".git").mkdir(exist_ok=True)
    (repo / "odd" / "tasks" / "demo.md").write_text(DEMO_DOC, encoding="utf-8")

    agent = types.SimpleNamespace(
        session_id="smoke-tasks-session", model="smoke", provider="", platform="telegram"
    )
    set_session_cwd(str(repo / "odd"))
    try:
        info = _plugin_session_info(agent)
    finally:
        clear_session_cwd()
    check(info.get("cwd") == str(repo / "odd"), f"Hermes session info carries cwd {info['cwd']}")
    rendered = {s.id: s for s in manager.render_system_prompt_sections(info)}
    check(SECTION_ID in rendered, "section still renders with a session cwd")
    check(
        rendered[SECTION_ID].content.encode("utf-8") == baseline_section.encode("utf-8"),
        "section text is byte-identical with and without a session cwd",
    )
    prompt_modules = [
        m
        for name, m in sys.modules.items()
        if name.endswith("hermes_odd.prompt") and hasattr(m, "ODD_SECTION")
    ]
    check(bool(prompt_modules), "the loaded plugin's prompt module is importable")
    check(
        rendered[SECTION_ID].content == prompt_modules[0].ODD_SECTION.strip(),
        "rendered section equals ODD_SECTION byte for byte",
    )

    command = manager._plugin_commands.get("odd-tasks")
    check(command is not None, "/odd-tasks is registered")
    listing = command["handler"]("")
    check("demo-project (" in listing, "/odd-tasks lists the recorded project")
    check("1/2 demo" in listing, "/odd-tasks shows the demo feature progress")
    check("next: T2 Show it in /odd_tasks" in listing, "/odd-tasks shows the next task")
    detail = command["handler"]("demo")
    check("✓ T1 Create the demo repository" in detail, "detail marks the done task")
    check("○ T2 Show it in /odd_tasks  ← next" in detail, "detail marks the next task")
    check("Next step: T2 show it." in detail, "detail shows the next step")
    print("---- /odd-tasks output ----")
    print(listing)
    print("---- /odd-tasks demo output ----")
    print(detail)
    print("---------------------------")
    raw = next((temp_home / "plugin-data").rglob("state.json")).read_text(encoding="utf-8")
    check("hermes-odd.projects/v1" in raw, "known projects persisted in plugin state")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.invalid", "-C", str(repo)]
        + list(args),
        check=True,
        capture_output=True,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(repo), "GIT_CONFIG_NOSYSTEM": "1"},
    )


def run_changes_viewer(manager, temp_home: Path) -> None:
    import difflib
    import json

    check(
        len(manager._hooks.get("post_tool_call") or []) >= 2,
        "post_tool_call has separate callbacks for agents and changes",
    )
    repo = (temp_home / "work" / "changes-project").resolve()
    (repo / "src").mkdir(parents=True)
    app = repo / "src" / "app.py"
    before = "def main():\n    return 1\n"
    app.write_text(before, encoding="utf-8")
    try:
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        _git(repo, "add", "src/app.py")
        _git(repo, "commit", "-qm", "init")
        has_git = True
    except (OSError, subprocess.CalledProcessError):
        (repo / ".git").mkdir(exist_ok=True)
        has_git = False

    def fire(tool, args, result, status="ok", task_id="smoke-main-run"):
        manager.invoke_hook(
            "post_tool_call",
            tool_name=tool,
            args=args,
            result=json.dumps(result),
            task_id=task_id,
            session_id="smoke-changes-session",
            tool_call_id=f"call-{tool}",
            turn_id="turn-1",
            api_request_id="",
            duration_ms=7,
            status=status,
            error_type=None if status == "ok" else "tool_error",
            error_message=None,
            middleware_trace=[],
        )

    notes = repo / "src" / "notes.txt"
    content = f"one\ntwo\nkey={FAKE_SECRET}\n"
    notes.write_text(content, encoding="utf-8")
    fire(
        "write_file",
        {"path": "src/notes.txt", "content": content},
        {
            "bytes_written": len(content),
            "resolved_path": str(notes),
            "files_modified": [str(notes)],
        },
    )
    after = f"def main():\n    # {FAKE_SECRET}\n    return 2\n"
    app.write_text(after, encoding="utf-8")
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), f"a/{app}", f"b/{app}"
        )
    )
    fire(
        "patch",
        {"path": "src/app.py", "old_string": "    return 1", "new_string": after},
        {"success": True, "diff": diff, "files_modified": [str(app)], "resolved_path": str(app)},
        task_id="sa-0-5e0e5e0e",
    )
    fire(
        "patch",
        {"path": "src/missing.py", "old_string": "x", "new_string": "y"},
        {"error": "Could not find a match"},
        status="error",
    )

    command = manager._plugin_commands.get("odd-changes")
    check(command is not None, "/odd-changes is registered")
    listing = command["handler"]("")
    check("changes-project (" in listing, "/odd-changes groups by the git project")
    check(
        "+3 −?  src/notes.txt  (1 edit · by main" in listing,
        "/odd-changes lists the write_file with +3 −? (overwrite)",
    )
    check(
        "+2 −1  src/app.py  (1 edit · by sa-5e0e5e0e" in listing,
        "/odd-changes lists the subagent patch with +2 −1",
    )
    check("missing.py" not in listing, "a failed patch leaves no row")
    detail = command["handler"]("app.py")
    check("patch +2 −1 sa-5e0e5e0e" in detail, "detail shows the timeline entry")
    if has_git:
        check(
            "git (uncommitted, not staged): +2 −1" in detail,
            "detail shows the real git diff --numstat",
        )
    print("---- /odd-changes output ----")
    print(listing)
    print("---- /odd-changes app.py output ----")
    print(detail)
    print("-----------------------------")
    raw = next((temp_home / "plugin-data").rglob("state.json")).read_text(encoding="utf-8")
    check("hermes-odd.changes/v1" in raw, "changes persisted in plugin state")
    check(FAKE_SECRET not in raw + listing + detail, "file content never stored or shown")


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
