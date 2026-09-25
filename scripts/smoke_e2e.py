"""End-to-end smoke test against a real Hermes install.

Loads hermes-odd through Hermes' own ``PluginManager`` inside a throwaway
``HERMES_HOME`` and checks what the plugin registered:

* the plugin loaded without error;
* ``odd-commands`` is registered and its handler lists itself as plain text;
* the ``hermes-odd-workflow`` prompt section is registered, renders, and fits
  in 4000 characters;
* the ``hermes-odd:*`` skills (three ODD skills, ``rdd-review``,
  ``rdd-review-lenses`` and ``setup``) are registered;
* first-run setup: the fresh home renders the section with the
  setup-pending line; with a synthetic ``SOUL.md`` (user text plus a gentle-ai
  block) the ``odd_setup_apply`` tool is registered in Hermes' tool registry
  and dispatched through ``tools.registry.registry.dispatch``: a declined
  persona leaves ``SOUL.md`` untouched, a confirmed ``rioplatense`` persona
  writes one hermes-odd block at the top (after the H1), keeps every other
  byte, makes a backup and passes Hermes' own ``load_soul_md`` threat scan;
  the answers land in the throwaway ``config.yaml`` and pass Hermes'
  ``validate_config_schema``; ``/odd-setup status`` and ``/odd-doctor``
  reflect them, and the pending line is gone;
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
  the content never reaches state or output;
* ``/odd-status`` and ``/odd-doctor``: a synthetic ``SOUL.md`` with two
  gentle-ai managed blocks is written into the throwaway home; the status
  shows each summary line under 1,500 characters and the doctor reports
  every check, finds the synthetic blocks (not the real ``~/.hermes`` SOUL),
  never prints SOUL content or full home paths, and stays under 3,500
  characters. The doctor runs the real ``gentle-ai version`` and read-only
  ``gentle-ai review mode status`` from ``PATH``;
* ``/odd-soul``: a synthetic ``SOUL.md`` mirroring the real gentle-ai layout
  (user header, codegraph-guidance, persona, engram-protocol, sdd-orchestrator
  with a nested preflight, agent-routing with a nested remote-authorization)
  is planned (dry run, nothing written), dry-run through ``odd_soul_apply``
  via Hermes' tool registry, applied with ``apply confirm`` (backup, exact
  expected text, permissions kept), loaded whole by Hermes' own
  ``load_soul_md``, applied again (no-op) and restored from the backup;
* ``/odd-review-mode`` (status only, read-only) from inside a throwaway git
  repository: it reports the RDD mode and the native review availability line
  from the real ``gentle-ai`` on ``PATH`` (``gentle-ai review status ...
  --agent hermes``, refused in preflight by gentle-ai 3.7.0). ``enable`` and
  ``disable`` are never run by the smoke.

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
EXPECTED_SKILLS = [
    "codegraph",
    "engram-protocol",
    "odd-delegation",
    "odd-feature-tracking",
    "odd-workflow",
    "rdd-review",
    "rdd-review-lenses",
    "setup",
]
SETUP_PENDING_LINE = (
    "hermes-odd setup is pending: when the user is not mid-task, offer it once "
    "(load hermes-odd:setup); never interrupt work."
)
SETUP_SOUL = (
    "# Smoke agent\n\nUser line one: be kind.\n\n"
    "<!-- gentle-ai:persona -->\nOld gentle persona.\n<!-- /gentle-ai:persona -->\n"
    "User closing line.\n"
)
AGENT_HOOKS = ["on_session_start", "subagent_start", "post_tool_call", "subagent_stop"]
FAKE_SECRET = "sk-smoke-FAKE-SECRET-not-real"


class SmokeFailure(AssertionError):
    pass


def _repo_version() -> str:
    """Version declared in this checkout's hermes_odd/__init__.py."""
    import re

    text = (Path(__file__).resolve().parent.parent / "hermes_odd" / "__init__.py").read_text()
    match = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    return match.group(1) if match else "?"


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
    check(
        rendered[SECTION_ID].content.endswith(SETUP_PENDING_LINE),
        "a fresh home renders the section with the setup-pending line",
    )
    print("---- pending line ----")
    print(rendered[SECTION_ID].content.splitlines()[-1])
    print("----------------------")

    skills = manager.list_plugin_skills(PLUGIN)
    check(skills == EXPECTED_SKILLS, f"skills registered as {PLUGIN}:* -> {skills}")
    for name in EXPECTED_SKILLS:
        path = manager.find_plugin_skill(f"{PLUGIN}:{name}")
        check(path is not None and Path(path).is_file(), f"{PLUGIN}:{name} resolves to a file")

    run_agents_lifecycle(manager, temp_home)
    completed_section = run_setup(manager, temp_home, loaded)
    run_tasks_viewer(manager, temp_home, completed_section)
    run_changes_viewer(manager, temp_home)
    run_health(manager, temp_home)
    run_soul_cleanup(manager, temp_home, loaded)
    run_review_mode(manager, temp_home)


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


def run_setup(manager, temp_home: Path, loaded) -> str:
    """First-run setup through Hermes' tool registry; returns the completed section."""
    import json
    import re

    from agent.prompt_builder import load_soul_md
    from hermes_cli.plugins import validate_config_schema
    from tools.registry import registry

    soul = temp_home / "SOUL.md"
    soul.write_text(SETUP_SOUL, encoding="utf-8")
    os.chmod(soul, 0o640)

    schema = loaded.manifest.config_schema
    check(
        sorted(schema)
        == [
            "codegraph_guidance",
            "engram_protocol",
            "persona",
            "soul_cleanup",
            "tdd_mode",
            "verbosity",
        ],
        f"Hermes parsed config_schema keys {sorted(schema)}",
    )
    check(schema["persona"].get("default") == "unset", "persona default is 'unset'")
    check("odd_setup_apply" in loaded.manifest.provides_tools, "manifest provides_tools lists it")
    check("odd_setup_apply" in manager._plugin_tool_names, "odd_setup_apply is a plugin tool")
    entry = registry.get_entry("odd_setup_apply", scope=manager.scope_key)
    check(
        entry is not None and entry.toolset == "hermes_odd", "tool registered, toolset hermes_odd"
    )

    def dispatch(args):
        raw = registry.dispatch("odd_setup_apply", args, scope=manager.scope_key)
        return json.loads(raw)

    bad = dispatch({"persona": "gentleman", "apply_persona_to_soul": True})
    check("error" in bad, f"invalid persona rejected: {bad.get('error')}")
    declined = dispatch({"persona": "rioplatense", "apply_persona_to_soul": False})
    check(declined.get("ok") and not declined["persona_applied"], "declined persona not applied")
    check(soul.read_text(encoding="utf-8") == SETUP_SOUL, "declined: SOUL.md byte-identical")
    check(not list(temp_home.glob("SOUL.md.hermes-odd-bak-*")), "declined: no backup")

    result = dispatch(
        {
            "persona": "rioplatense",
            "verbosity": "short",
            "engram_protocol": "auto",
            "soul_cleanup": "later",
            "apply_persona_to_soul": True,
        }
    )
    check(result.get("ok") and result["persona_applied"], f"confirmed apply: {result}")
    check("next new session" in result["note"], "tool result carries the next-session note")
    check("two personas now coexist" in result["summary"], "summary warns about two personas")
    text = soul.read_text(encoding="utf-8")
    check(
        text.startswith("# Smoke agent\n\n<!-- hermes-odd:persona -->\n"),
        "block written at the top, right after the H1",
    )
    stripped = re.sub(
        r"<!-- hermes-odd:persona -->.*?<!-- /hermes-odd:persona -->\n\n", "", text, flags=re.S
    )
    check(stripped == SETUP_SOUL, "everything outside the block is byte-identical")
    check(text.count("<!-- hermes-odd:persona -->") == 1, "exactly one hermes-odd block")
    backups = sorted(temp_home.glob("SOUL.md.hermes-odd-bak-*"))
    check(len(backups) == 1, f"one backup {backups[0].name if backups else '-'}")
    check(backups[0].read_text(encoding="utf-8") == SETUP_SOUL, "backup holds the original")
    check((soul.stat().st_mode & 0o777) == 0o640, "SOUL.md permissions kept (0640)")
    loaded_soul = load_soul_md(home_override=temp_home) or ""
    check(
        "BLOCKED" not in loaded_soul and "hermes-odd:persona" in loaded_soul,
        "Hermes' load_soul_md loads the new SOUL.md (threat scan passes)",
    )

    settings = manager_settings(temp_home)
    check(settings.get("persona") == "rioplatense", "config.yaml persona = rioplatense")
    warnings = validate_config_schema("hermes-odd", schema, settings)
    check(warnings == [], f"Hermes validate_config_schema: no warnings {warnings}")

    status = manager._plugin_commands["odd-setup"]["handler"]("status")
    check(status.startswith("hermes-odd setup: complete"), "/odd-setup status: complete")
    check(
        "Persona: Mentor rioplatense (voseo) · config" in status,
        "/odd-setup status reflects the persona from config.yaml",
    )
    check("SOUL cleanup of gentle-ai blocks: later" in status, "status shows the cleanup answer")
    check("hermes-odd persona block present" in status, "status sees the block")
    preview = manager._plugin_commands["odd-setup"]["handler"]("persona neutral")
    check("dry run, nothing written" in preview, "persona preview is a dry run")
    check(soul.read_text(encoding="utf-8") == text, "preview did not write")
    doctor = manager._plugin_commands["odd-doctor"]["handler"]("")
    check("hermes-odd persona block" in doctor and "(at the top)" in doctor, "doctor sees it")
    check("1 gentle-ai blocks" in doctor, "doctor counts gentle-ai blocks separately")

    rendered = {s.id: s for s in manager.render_system_prompt_sections({"platform": "cli"})}
    content = rendered[SECTION_ID].content
    check(SETUP_PENDING_LINE not in content, "the pending line is gone after completion")
    print("---- /odd-setup status output ----")
    print(status)
    print("---- /odd-setup persona neutral (dry run) ----")
    print(preview)
    print("---- SOUL.md after apply (head) ----")
    print(text[:2200])
    print("-----------------------------------")
    return content


def manager_settings(temp_home: Path) -> dict:
    import yaml

    config = yaml.safe_load((temp_home / "config.yaml").read_text(encoding="utf-8")) or {}
    entry = ((config.get("plugins") or {}).get("entries") or {}).get(PLUGIN) or {}
    return entry.get("settings") or {}


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
    prompt = prompt_modules[0]
    content = rendered[SECTION_ID].content
    base = prompt.ODD_SECTION.strip()
    extra = content[len(base) :].strip().splitlines() if content.startswith(base) else None
    check(
        extra is not None
        and extra[:1] == [prompt.MEMORY_POINTER]
        and all(line in prompt.POINTER_LINES for line in extra),
        "rendered section = ODD_SECTION byte for byte + the default skill pointer lines "
        f"({len(extra or [])})",
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


SOUL_TEXT = (
    "# Smoke soul\n\n<!-- gentle-ai:persona -->\nBe kind.\n<!-- /gentle-ai:persona -->\n"
    "<!-- gentle-ai:smoke-block -->\n"
    + "s" * 30_000
    + "\n<!-- /gentle-ai:smoke-block -->\n"
    + "tail " * 2_000
)


def run_health(manager, temp_home: Path) -> None:
    (temp_home / "SOUL.md").write_text(SOUL_TEXT, encoding="utf-8")
    status_cmd = manager._plugin_commands.get("odd-status")
    doctor_cmd = manager._plugin_commands.get("odd-doctor")
    check(status_cmd is not None and doctor_cmd is not None, "/odd-status and /odd-doctor exist")
    status = status_cmd["handler"]("")
    check(status.startswith("hermes-odd "), "/odd-status starts with the plugin version")
    check(f"Prompt: {SECTION_ID} " in status, "/odd-status shows the prompt section")
    check("Skills: 8 (" in status, "/odd-status counts the skills")
    check("Native review on Hermes: " in status, "/odd-status shows native review availability")
    check("Subagents: " in status and "Changes (24 h): 2 files" in status, "status reads stores")
    check("ODD features: " in status, "/odd-status counts feature documents")
    check("gentle-ai: " in status and "Upstream: gentle-ai v" in status, "binary + lock lines")
    check(len(status) < 1500, f"/odd-status is {len(status)} chars (< 1500)")
    doctor = doctor_cmd["handler"]("")
    for name in (
        "gentle-ai binary",
        "RDD mode",
        "Native review on Hermes",
        "SOUL.md",
        "plugin surface",
        "upstream lock",
    ):
        check(f"  {name}: " in doctor, f"/odd-doctor reports {name}")
    check(
        "3 gentle-ai blocks" not in doctor and "2 gentle-ai blocks" in doctor,
        "/odd-doctor finds the synthetic SOUL's 2 managed blocks in the throwaway home",
    )
    check("persona" in doctor and "smoke-block" in doctor, "doctor names the managed blocks")
    check("hooks 5/5" in doctor and "state ok (write+read)" in doctor, "plugin surface ok")
    check(
        f"hermes-odd {_repo_version()} enabled" in doctor, "doctor sees the plugin enabled via ctx"
    )
    check(len(doctor) < 3500, f"/odd-doctor is {len(doctor)} chars (< 3500)")
    check("Be kind." not in doctor and "sssss" not in doctor, "SOUL content is never printed")
    check(str(Path.home()) + "/" not in status + doctor, "no full home paths in the output")
    print("---- /odd-status output ----")
    print(status)
    print("---- /odd-doctor output ----")
    print(doctor)
    print("----------------------------")


def _block(name: str, body: str) -> str:
    return f"<!-- gentle-ai:{name} -->\n{body}<!-- /gentle-ai:{name} -->"


SOUL_REMOTE = _block("remote-authorization", "Remote actions need explicit authorization.\n")
SOUL_PERSONA = _block("persona", "Old gentle persona.\n")
SOUL_HEADER = "# Smoke agent\n\nUser line one: be kind.\nUser line two.\n\n"
# Mirrors the real layout gentle-ai writes: user header, codegraph-guidance,
# persona, engram-protocol, sdd-orchestrator (nested preflight) and
# agent-routing (nested remote-authorization) last, one blank line apart.
CLEANUP_SOUL = (
    SOUL_HEADER
    + _block("codegraph-guidance", "## CodeGraph\n" + "c" * 3_000 + "\n")
    + "\n\n"
    + SOUL_PERSONA
    + "\n\n"
    + _block("engram-protocol", "## Engram\n" + "e" * 9_000 + "\n")
    + "\n\n"
    + _block(
        "sdd-orchestrator",
        "o" * 40_000 + "\n" + _block("sdd-session-preflight", "p" * 2_000 + "\n") + "\n",
    )
    + "\n\n"
    + _block("agent-routing", "r" * 16_000 + "\n" + SOUL_REMOTE + "\nend\n")
    + "\n"
)
CLEANUP_EXPECTED = SOUL_HEADER + SOUL_PERSONA + "\n\n" + SOUL_REMOTE + "\n"


def run_soul_cleanup(manager, temp_home: Path, loaded) -> None:
    """/odd-soul plan, apply confirm, Hermes' own load_soul_md, then restore."""
    import json

    from agent.prompt_builder import load_soul_md
    from tools.registry import registry

    soul = temp_home / "SOUL.md"
    for old in temp_home.glob("SOUL.md.hermes-odd-bak-*"):
        old.unlink()
    soul.write_text(CLEANUP_SOUL, encoding="utf-8")
    os.chmod(soul, 0o640)
    command = manager._plugin_commands.get("odd-soul")
    check(command is not None, "/odd-soul is registered")
    listing = manager._plugin_commands[COMMAND_KEY]["handler"]("")
    check("- /odd_soul" in listing, "/odd-commands lists /odd_soul")
    check("odd_soul_apply" in loaded.manifest.provides_tools, "manifest lists odd_soul_apply")
    check("odd_soul_apply" in manager._plugin_tool_names, "odd_soul_apply is a plugin tool")

    loaded_before = load_soul_md(home_override=temp_home) or ""
    check(len(loaded_before) < len(CLEANUP_SOUL.strip()), "Hermes truncates the big SOUL.md")

    plan = command["handler"]("plan")
    check("dry run, nothing written" in plan, "/odd-soul plan is a dry run")
    check("move to skill hermes-odd:engram-protocol" in plan, "plan moves engram-protocol")
    check("move to skill hermes-odd:codegraph" in plan, "plan moves codegraph-guidance")
    check("lift remote-authorization" in plan, "plan lifts remote-authorization")
    check("gentle-ai sync --agent hermes" in plan, "plan warns about gentle-ai re-adding")
    check("128k (cap 30,720): truncated" in plan and "→ fits" in plan, "plan shows truncation")
    check("oooo" not in plan and "be kind" not in plan, "plan never prints SOUL content")
    check(soul.read_text(encoding="utf-8") == CLEANUP_SOUL, "plan did not write")

    raw = registry.dispatch("odd_soul_apply", {"confirm": False}, scope=manager.scope_key)
    dry = json.loads(raw)
    check(dry.get("dry_run") and dry.get("changes"), "odd_soul_apply dry run through Hermes")
    missing = json.loads(
        registry.dispatch("odd_soul_apply", {"confirm": True}, scope=manager.scope_key)
    )
    check("error" in missing, "odd_soul_apply confirm=true without plan_id is refused")
    check(soul.read_text(encoding="utf-8") == CLEANUP_SOUL, "tool dry run did not write")

    applied = command["handler"]("apply confirm")
    check("SOUL.md cleaned" in applied and "Verified on disk" in applied, "apply verified")
    text = soul.read_text(encoding="utf-8")
    check(text == CLEANUP_EXPECTED, "cleaned SOUL.md holds exactly user text, persona, remote-auth")
    check((soul.stat().st_mode & 0o777) == 0o640, "SOUL.md permissions kept (0640)")
    backups = sorted(temp_home.glob("SOUL.md.hermes-odd-bak-*"))
    check(len(backups) == 1, "one backup")
    check(backups[0].read_text(encoding="utf-8") == CLEANUP_SOUL, "backup holds the original")
    loaded_after = load_soul_md(home_override=temp_home) or ""
    check(
        "BLOCKED" not in loaded_after
        and "gentle-ai:remote-authorization" in loaded_after
        and "sdd-orchestrator" not in loaded_after
        and "User line two." in loaded_after,
        "Hermes' load_soul_md loads the cleaned SOUL.md whole (no truncation, scan passes)",
    )
    again = command["handler"]("apply confirm")
    check("nothing to do" in again, "second apply is a no-op")

    listing = command["handler"]("restore")
    check("1. SOUL.md.hermes-odd-bak-" in listing, "/odd-soul restore lists the backup")
    restored = command["handler"]("restore 1")
    check("SOUL.md restored from" in restored, "/odd-soul restore 1 restores")
    check(soul.read_text(encoding="utf-8") == CLEANUP_SOUL, "restore round-trips the original")
    check(len(list(temp_home.glob("SOUL.md.hermes-odd-bak-*"))) == 2, "restore backed up first")
    check(str(Path.home()) + "/" not in plan + applied + restored, "no full home paths")
    print("---- /odd-soul plan output ----")
    print(plan)
    print("---- /odd-soul apply confirm output ----")
    print(applied)
    print("--------------------------------")


def run_review_mode(manager, temp_home: Path) -> None:
    command = manager._plugin_commands.get("odd-review-mode")
    check(command is not None, "/odd-review-mode is registered")
    listing = manager._plugin_commands[COMMAND_KEY]["handler"]("")
    check("Review:\n- /odd_review_mode" in listing, "/odd-commands lists it under Review")
    if shutil.which("gentle-ai") is None:
        print("skip: gentle-ai not on PATH; /odd-review-mode status not exercised")
        return
    repo = temp_home / "review-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    previous = os.getcwd()
    saved_cwd = os.environ.pop("TERMINAL_CWD", None)
    try:
        os.chdir(repo)
        output = command["handler"]("status")
    finally:
        os.chdir(previous)
        if saved_cwd is not None:
            os.environ["TERMINAL_CWD"] = saved_cwd
    check(output.startswith("RDD review mode · review-repo"), "status targets the process repo")
    check("receipt-driven development: " in output, "status reports the RDD mode")
    check(
        "Native review on Hermes: unavailable — gentle-ai " in output
        and "advertises immutable review only for" in output,
        "status reports native review unavailable on Hermes (real gentle-ai)",
    )
    check("immutable_review_transport_unsupported" in output, "status shows the failure code")
    check(len(output) < 3500, f"/odd-review-mode is {len(output)} chars (< 3500)")
    check(str(Path.home()) + "/" not in output, "no full home paths in the output")
    print("---- /odd-review-mode status output ----")
    print(output)
    print("----------------------------------------")


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
