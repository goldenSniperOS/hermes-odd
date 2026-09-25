"""Changed-file capture (``post_tool_call``) and the ``/odd_changes`` viewer."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import FakeContext, FakeState, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import changes as changes_mod  # noqa: E402
from hermes_odd import register  # noqa: E402
from hermes_odd.agents import AgentStore  # noqa: E402
from hermes_odd.changes import (  # noqa: E402
    MAX_ATTRIBUTION,
    MAX_FILES,
    MAX_TIMELINE,
    SCHEMA,
    STATE_KEY,
    ChangeStore,
    FileOp,
    NumstatResult,
    count_lines,
    count_replace,
    extract_operations,
    git_numstat,
    parse_unified_diff,
    parse_v4a,
)
from hermes_odd.commands.changes import (  # noqa: E402
    OUTPUT_MAX_CHARS,
    make_odd_changes,
    render_list,
)

CANARY = "sk-test-FAKE-SECRET-0123456789"


class Clock:
    def __init__(self, start: float = 1_790_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def unified(path: str, old: str, new: str) -> str:
    """The diff Hermes' patch tool returns (``difflib``, ``a/``/``b/`` headers)."""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def write_call(path: str, content: str, resolved: str | None = None, **extra) -> dict:
    result = {"bytes_written": len(content), "verified": True}
    if resolved:
        result.update({"resolved_path": resolved, "files_modified": [resolved]})
    kwargs = {
        "tool_name": "write_file",
        "args": {"path": path, "content": content},
        "result": json.dumps(result),
        "task_id": "run-uuid-main",
        "session_id": "20260924_main",
        "tool_call_id": "call-1",
        "turn_id": "turn-1",
        "duration_ms": 5,
        "status": "ok",
        "error_type": None,
        "error_message": None,
        "telemetry_schema_version": 1,
    }
    kwargs.update(extra)
    return kwargs


def patch_call(path: str, old: str, new: str, file_text: tuple[str, str] | None = None, **extra):
    before, after = file_text or (old, new)
    result = {
        "success": True,
        "diff": unified(path, before, after),
        "files_modified": [path],
        "resolved_path": path,
    }
    kwargs = write_call(path, "")
    kwargs.update(
        {
            "tool_name": "patch",
            "args": {"path": path, "old_string": old, "new_string": new, "replace_all": False},
            "result": json.dumps(result),
        }
    )
    kwargs.update(extra)
    return kwargs


class TempRepo(unittest.TestCase):
    """A temporary git repository (``.git`` directory, no subprocess)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(os.path.realpath(self._tmp.name))
        self.repo = self.base / "work" / "demo-project"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "src").mkdir()
        self.file = str(self.repo / "src" / "app.py")
        self.clock = Clock()
        self.state = FakeState()
        self.agents = AgentStore(clock=self.clock)
        self.store = ChangeStore(self.state, clock=self.clock, agent_store=self.agents)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def only(self) -> dict:
        files = self.store.files()
        self.assertEqual(len(files), 1)
        return files[0]


class LineCountTests(unittest.TestCase):
    def test_count_lines(self) -> None:
        self.assertEqual(count_lines(""), 0)
        self.assertEqual(count_lines("a"), 1)
        self.assertEqual(count_lines("a\n"), 1)
        self.assertEqual(count_lines("a\nb"), 2)
        self.assertEqual(count_lines("a\r\nb\r\n"), 2)
        self.assertEqual(count_lines("a\rb\r"), 2)
        self.assertEqual(count_lines("\n\n"), 2)
        self.assertEqual(count_lines(None), 0)

    def test_count_replace(self) -> None:
        self.assertEqual(count_replace("a\nb", "a\nb\nc"), (1, 0))  # add
        self.assertEqual(count_replace("a\nb\nc", "a\nc"), (0, 1))  # remove
        self.assertEqual(count_replace("a\nb\nc", "a\nB\nc"), (1, 1))  # replace
        self.assertEqual(count_replace("x = 1", ""), (0, 1))  # delete match
        self.assertEqual(count_replace("a\r\nb\r\n", "a\nb\n"), (0, 0))  # CRLF only
        self.assertEqual(count_replace("a\nb\n", "a\nb"), (0, 0))  # trailing newline

    def test_unified_diff_counts(self) -> None:
        diff = unified("/r/f.py", "a\nb\nc\n", "a\nB\nc\nd\n")
        self.assertEqual(parse_unified_diff(diff), [("/r/f.py", 2, 1)])

    def test_unified_diff_new_and_deleted_file(self) -> None:
        add = unified("/r/new.py", "", "x\ny\n").replace("--- a//r/new.py", "--- /dev/null")
        self.assertEqual(parse_unified_diff(add), [("/r/new.py", 2, 0)])
        gone = "".join(
            difflib.unified_diff(["x\n", "y\n"], [], fromfile="a//r/old.py", tofile="/dev/null")
        )
        self.assertEqual(parse_unified_diff(gone), [("/r/old.py", 0, 2)])

    def test_unified_diff_header_lookalike_content(self) -> None:
        # Added "++ x" renders as "+++ x" and removed "-- y" as "--- y".
        diff = unified("/r/f.md", "keep\n-- y\n", "keep\n++ x\n")
        self.assertEqual(parse_unified_diff(diff), [("/r/f.md", 1, 1)])

    def test_unified_diff_missing_final_newline(self) -> None:
        # difflib joins "-a" and "+b" on one line when "a" has no newline.
        diff = unified("/r/f.txt", "a", "b\n")
        self.assertIn("-a+b", diff)
        self.assertEqual(parse_unified_diff(diff), [("/r/f.txt", 1, 1)])

    def test_unified_diff_crlf_and_multiple_files(self) -> None:
        diff = "\n".join(
            [unified("/r/a.py", "1\n2\n", "1\n"), unified("/r/b.py", "x\n", "x\ny\nz\n")]
        ).replace("\n", "\r\n")
        self.assertEqual(parse_unified_diff(diff), [("/r/a.py", 0, 1), ("/r/b.py", 2, 0)])

    def test_garbage_diff(self) -> None:
        self.assertEqual(parse_unified_diff("not a diff\n@@ nope"), [])
        self.assertEqual(parse_unified_diff(None), [])

    def test_v4a_args(self) -> None:
        patch = (
            "*** Begin Patch\n*** Update File: src/a.py\n@@ def f @@\n ctx\n-old\n+new\n+more\n"
            "*** Add File: src/b.py\n+one\n+two\n*** Delete File: src/c.py\n*** End Patch\n"
        )
        self.assertEqual(
            parse_v4a(patch), [("src/a.py", 2, 1), ("src/b.py", 2, 0), ("src/c.py", 0, None)]
        )


class ExtractTests(unittest.TestCase):
    def test_write_file_uses_resolved_path(self) -> None:
        call = write_call("src/app.py", "a\nb\n", resolved="/abs/repo/src/app.py")
        ops = extract_operations("write_file", call["args"], call["result"])
        self.assertEqual(ops, [FileOp("/abs/repo/src/app.py", 2, None)])

    def test_write_file_absolute_arg_when_result_unparsable(self) -> None:
        ops = extract_operations("write_file", {"path": "/abs/x/../y.txt", "content": "z"}, "?")
        self.assertEqual(ops, [FileOp("/abs/y.txt", 1, None)])

    def test_relative_arg_resolves_against_terminal_cwd(self) -> None:
        with mock.patch.dict(os.environ, {"TERMINAL_CWD": "/work/proj"}):
            ops = extract_operations("write_file", {"path": "src/a.py", "content": ""}, None)
        self.assertEqual(ops, [FileOp("/work/proj/src/a.py", 0, None)])

    def test_relative_arg_with_sentinel_terminal_cwd_uses_process_cwd(self) -> None:
        with mock.patch.dict(os.environ, {"TERMINAL_CWD": "."}):
            ops = extract_operations("write_file", {"path": "a.py", "content": "x"}, None)
        self.assertEqual(ops[0].path, os.path.join(os.getcwd(), "a.py"))

    def test_tilde_arg_expands(self) -> None:
        ops = extract_operations("write_file", {"path": "~/n.txt", "content": "x"}, None)
        self.assertEqual(ops[0].path, os.path.expanduser("~/n.txt"))

    def test_patch_replace_counts_from_result_diff(self) -> None:
        call = patch_call("/abs/f.py", "b", "B\nX", file_text=("a\nb\nc\n", "a\nB\nX\nc\n"))
        ops = extract_operations("patch", call["args"], call["result"])
        self.assertEqual(ops, [FileOp("/abs/f.py", 2, 1)])

    def test_patch_replace_all_uses_diff_not_args(self) -> None:
        before, after = "x\ny\nx\n", "z\ny\nz\n"
        call = patch_call("/abs/f.py", "x", "z", file_text=(before, after))
        call["args"]["replace_all"] = True
        ops = extract_operations("patch", call["args"], call["result"])
        self.assertEqual(ops, [FileOp("/abs/f.py", 2, 2)])

    def test_patch_replace_falls_back_to_args(self) -> None:
        args = {"path": "/abs/f.py", "old_string": "a\nb", "new_string": "a\nc\nd"}
        ops = extract_operations("patch", args, json.dumps({"success": True}))
        self.assertEqual(ops, [FileOp("/abs/f.py", 2, 1)])

    def test_patch_v4a_multi_file_from_result(self) -> None:
        diff = "\n".join(
            [unified("/r/src/a.py", "1\n2\n", "1\n3\n"), unified("/r/src/b.py", "", "n\n")]
        )
        result = {
            "success": True,
            "diff": diff,
            "files_modified": ["/r/src/a.py", "/r/src/b.py"],
            "files_created": ["/r/src/b.py"],
        }
        args = {"mode": "patch", "patch": "*** Begin Patch\n*** End Patch"}
        ops = extract_operations("patch", args, json.dumps(result))
        self.assertEqual(ops, [FileOp("/r/src/a.py", 1, 1), FileOp("/r/src/b.py", 1, 0)])

    def test_patch_v4a_falls_back_to_args(self) -> None:
        patch = "*** Begin Patch\n*** Update File: /r/a.py\n-x\n+y\n+z\n*** End Patch"
        ops = extract_operations("patch", {"mode": "patch", "patch": patch}, "not json")
        self.assertEqual(ops, [FileOp("/r/a.py", 2, 1)])

    def test_move_entries_are_skipped(self) -> None:
        result = {"success": True, "files_modified": ["/r/a.py -> /r/b.py", "/r/b.py"]}
        ops = extract_operations("patch", {"mode": "patch", "patch": ""}, json.dumps(result))
        self.assertEqual([op.path for op in ops], ["/r/b.py"])

    def test_failed_results_are_ignored(self) -> None:
        for result in (
            {"error": "Could not find old_string"},
            {"success": False, "error": "x"},
            {"success": True, "no_change": True, "note": "already applied"},
        ):
            with self.subTest(result=result):
                ops = extract_operations(
                    "patch", {"path": "/abs/f.py", "old_string": "a", "new_string": "b"}, result
                )
                self.assertEqual(ops, [])


class CaptureTests(TempRepo):
    def test_write_then_patch_accumulates(self) -> None:
        self.store.on_post_tool_call(**write_call("src/app.py", "a\nb\nc\n", resolved=self.file))
        self.clock.advance(60)
        self.store.on_post_tool_call(
            **patch_call(self.file, "b", "B\nX", file_text=("a\nb\nc\n", "a\nB\nX\nc\n"))
        )
        entry = self.only()
        self.assertEqual(entry["path"], self.file)
        self.assertEqual(entry["root"], str(self.repo))
        self.assertEqual(entry["rel"], "src/app.py")
        self.assertTrue(entry["in_git"])
        self.assertEqual((entry["ops"], entry["added"], entry["removed"]), (2, 5, 1))
        self.assertTrue(entry["removed_unknown"])
        self.assertEqual(entry["last_tool"], "patch")
        self.assertEqual(entry["first_at"] + 60, entry["last_at"])
        self.assertEqual([t["tool"] for t in entry["timeline"]], ["write_file", "patch"])
        doc = json.loads(self.state.data[STATE_KEY])
        self.assertEqual(doc["schema"], SCHEMA)

    def test_symlinked_spelling_matches_git_root(self) -> None:
        link = self.base / "link"
        link.symlink_to(self.repo, target_is_directory=True)
        self.store.on_post_tool_call(**write_call("x", "a", resolved=str(link / "src" / "x.py")))
        entry = self.only()
        self.assertEqual(entry["root"], str(self.repo))
        self.assertEqual(entry["rel"], "src/x.py")

    def test_outside_git_uses_directory(self) -> None:
        loose = self.base / "notes"
        loose.mkdir()
        self.store.on_post_tool_call(**write_call("n", "a", resolved=str(loose / "todo.txt")))
        entry = self.only()
        self.assertFalse(entry["in_git"])
        self.assertEqual((entry["root"], entry["rel"]), (str(loose), "todo.txt"))

    def test_failed_status_is_ignored(self) -> None:
        for status in ("error", "blocked", None):
            self.store.on_post_tool_call(**write_call("a", "x", resolved=self.file, status=status))
        self.assertEqual(self.store.files(), [])
        self.assertEqual(self.state.sets, 0)

    def test_non_file_tools_take_the_fast_path(self) -> None:
        for name in ("read_file", "terminal", "search_files", "execute_code", None):
            self.store.on_post_tool_call(**write_call("a", "x", resolved=self.file, tool_name=name))
        self.assertEqual(self.state.sets, 0)
        self.assertEqual(self.state.data, {})

    def test_attribution_main_and_subagent_with_enrichment(self) -> None:
        self.agents.on_session_start(session_id="20260924_main", platform="telegram")
        self.agents.on_subagent_start(
            parent_session_id="20260924_main",
            child_session_id="child-1",
            child_subagent_id="sa-0-1a2b3c4d",
            child_role="leaf",
            child_goal="Refactor the app module",
        )
        self.store.on_post_tool_call(**write_call("a", "x\n", resolved=self.file))
        self.clock.advance(5)
        self.store.on_post_tool_call(
            **write_call(
                "a", "y\n", resolved=self.file, task_id="sa-0-1a2b3c4d", session_id="child-1"
            )
        )
        entry = self.only()
        by = {a["id"]: a for a in entry["by"]}
        self.assertEqual(set(by), {"main", "sa-0-1a2b3c4d"})
        self.assertEqual(by["sa-0-1a2b3c4d"]["role"], "leaf")
        self.assertEqual(entry["platform"], "telegram")
        detail = make_odd_changes(self.store, numstat=lambda *a: NumstatResult("clean")).handler(
            "app.py"
        )
        self.assertIn("by: sa-1a2b3c4d leaf (1 edit), main (1 edit)", detail)
        self.assertIn("sa-1a2b3c4d goal: Refactor the app module", detail)
        self.assertIn("platform: telegram", detail)

    def test_unknown_non_sa_task_is_main(self) -> None:
        self.store.on_post_tool_call(**write_call("a", "x", resolved=self.file, task_id=""))
        self.assertEqual(self.only()["by"][0]["id"], "main")

    def test_privacy_no_content_in_state_or_output(self) -> None:
        text = f"api_key = '{CANARY}'\n"
        self.store.on_post_tool_call(**write_call("a", text, resolved=self.file))
        self.store.on_post_tool_call(
            **patch_call(self.file, text, f"# {CANARY} removed\n", file_text=(text, "x\n"))
        )
        v4a = f"*** Begin Patch\n*** Update File: {self.file}\n-{CANARY}\n+{CANARY}2\n*** End Patch"
        call = write_call("a", "")
        call.update(
            tool_name="patch",
            args={"mode": "patch", "patch": v4a},
            result=json.dumps({"success": True, "diff": unified(self.file, CANARY, CANARY + "2")}),
        )
        self.store.on_post_tool_call(**call)
        command = make_odd_changes(self.store, numstat=lambda *a: NumstatResult("ok", 1, 1))
        outputs = [command.handler(a) for a in ("", "all", "app", "demo-project")]
        blob = self.state.dump() + "".join(outputs)
        self.assertNotIn(CANARY, blob)
        self.assertNotIn("api_key", blob)

    def test_output_hides_full_home_paths(self) -> None:
        home = os.path.expanduser("~")
        self.store.record("write_file", [FileOp(os.path.join(home, "n.txt"), 1, None)])
        self.store.on_post_tool_call(**write_call("a", "x", resolved=self.file))
        listing = make_odd_changes(self.store).handler("")
        self.assertNotIn(str(self.base), listing)
        self.assertNotIn(home + os.sep, listing)
        self.assertIn("demo-project (…/work/demo-project)", listing)

    def test_handler_never_raises(self) -> None:
        self.store.on_post_tool_call()
        self.store.on_post_tool_call(tool_name="write_file", status="ok", args="junk", result=5)
        self.store.on_post_tool_call(tool_name="patch", status="ok", args={"path": 3}, result=[])
        with mock.patch.object(changes_mod, "locate", side_effect=RuntimeError("boom")):
            self.store.on_post_tool_call(**write_call("a", "x", resolved=self.file))

    def test_failing_backend_falls_back_to_memory(self) -> None:
        class Broken:
            def get(self, key, default=None):
                raise OSError("disk")

            def set(self, key, value):
                raise OSError("disk")

        store = ChangeStore(Broken(), clock=self.clock)
        with self.assertLogs("hermes_odd", level="WARNING"):
            store.on_post_tool_call(**write_call("a", "x", resolved=self.file))
        self.assertEqual(len(store.files()), 1)


class BoundsTests(TempRepo):
    def test_file_cap_drops_least_recent(self) -> None:
        for i in range(MAX_FILES + 5):
            self.clock.advance(1)
            self.store.record("write_file", [FileOp(str(self.repo / f"f{i}.txt"), 1, None)])
        files = self.store.files()
        self.assertEqual(len(files), MAX_FILES)
        names = {f["rel"] for f in files}
        self.assertNotIn("f0.txt", names)
        self.assertIn(f"f{MAX_FILES + 4}.txt", names)

    def test_seven_day_retention(self) -> None:
        self.store.record("write_file", [FileOp(str(self.repo / "old.txt"), 1, None)])
        self.clock.advance(6 * 86400)
        self.store.record("write_file", [FileOp(str(self.repo / "new.txt"), 1, None)])
        self.clock.advance(1 * 86400 + 60)
        self.assertEqual([f["rel"] for f in self.store.files()], ["new.txt"])

    def test_timeline_and_attribution_caps(self) -> None:
        for i in range(MAX_TIMELINE + 3):
            self.clock.advance(1)
            self.store.record(
                "write_file", [FileOp(self.file, 1, None)], task_id=f"sa-{i}-0000000{i % 10}"
            )
        entry = self.only()
        self.assertEqual(len(entry["timeline"]), MAX_TIMELINE)
        self.assertEqual(len(entry["by"]), MAX_ATTRIBUTION)
        self.assertEqual(entry["ops"], MAX_TIMELINE + 3)

    def test_clear(self) -> None:
        command = make_odd_changes(self.store)
        self.assertEqual(command.handler("clear"), "No recorded changes to clear.")
        self.store.record("write_file", [FileOp(self.file, 1, None)])
        self.store.record("write_file", [FileOp(str(self.repo / "b.txt"), 1, None)])
        self.assertIn("Cleared 2 recorded files", command.handler("clear"))
        self.assertEqual(self.store.files(), [])


class ViewerTests(TempRepo):
    def command(self, numstat=None):
        return make_odd_changes(self.store, numstat=numstat or (lambda *a: NumstatResult("clean")))

    def test_empty(self) -> None:
        text = self.command().handler("")
        self.assertIn("No file changes recorded (last 24 h)", text)
        self.assertIn("not tracked", text)

    def test_list_line_format_and_totals(self) -> None:
        self.store.record("write_file", [FileOp(self.file, 3, None)])
        self.clock.advance(180)
        self.store.record("patch", [FileOp(self.file, 2, 1)], task_id="sa-0-1a2b3c4d")
        self.store.record("patch", [FileOp(str(self.repo / "README.md"), 4, 0)])
        self.clock.advance(180)
        text = self.command().handler("")
        self.assertIn("Changes (last 24 h): 2 files · +9 −≥1 · 1 project", text)
        self.assertIn("demo-project (…/work/demo-project) · 2 files · +9 −≥1", text)
        self.assertIn("+5 −≥1  src/app.py  (2 edits · by sa-1a2b3c4d, main · 3m ago)", text)
        self.assertIn("+4 −0  README.md  (1 edit · by main · 3m ago)", text)
        self.assertIn("Terminal/shell edits and other tools are not tracked", text)

    def test_default_window_is_24h_and_all_is_7_days(self) -> None:
        self.store.record("write_file", [FileOp(self.file, 1, None)])
        self.clock.advance(2 * 86400)
        command = self.command()
        self.assertIn("No file changes recorded (last 24 h)", command.handler(""))
        self.assertIn("src/app.py", command.handler("all"))
        self.assertIn("last 7 days", command.handler("all"))

    def test_output_cap(self) -> None:
        for i in range(MAX_FILES):
            self.store.record("write_file", [FileOp(str(self.repo / f"file-{i:03}.txt"), 1, None)])
        text = self.command().handler("")
        self.assertLessEqual(len(text), OUTPUT_MAX_CHARS)
        self.assertRegex(text, r"… \d+ more \(/odd_changes all\)")
        self.assertIn("/odd_changes clear", text)

    def test_projects_grouped_newest_first(self) -> None:
        other = self.base / "other"
        (other / ".git").mkdir(parents=True)
        self.store.record("write_file", [FileOp(str(other / "a.txt"), 1, None)])
        self.clock.advance(10)
        self.store.record("write_file", [FileOp(self.file, 1, None)])
        text = render_list(self.store.files(), self.clock())
        self.assertLess(text.index("demo-project ("), text.index("other ("))

    def test_detail_timeline_and_git(self) -> None:
        self.store.record("write_file", [FileOp(self.file, 3, None)], session_id="s-1")
        self.clock.advance(60)
        self.store.record("patch", [FileOp(self.file, 2, 1)], task_id="sa-0-1a2b3c4d")
        seen = []

        def numstat(root, rel, in_git):
            seen.append((root, rel, in_git))
            return NumstatResult("ok", 7, 2)

        text = self.command(numstat).handler("src/app")
        self.assertIn("project: demo-project", text)
        self.assertIn("captured: 2 edits · +5 −≥1", text)
        self.assertRegex(text, r"\d\d:\d\d:\d\d write_file \+3 −\? main")
        self.assertRegex(text, r"\d\d:\d\d:\d\d patch \+2 −1 sa-1a2b3c4d")
        self.assertIn("git (uncommitted, not staged): +7 −2", text)
        self.assertEqual(seen, [(str(self.repo), "src/app.py", True)])

    def test_lookup_exact_prefix_substring_project(self) -> None:
        self.store.record("write_file", [FileOp(self.file, 1, None)])
        self.store.record("write_file", [FileOp(str(self.repo / "src" / "app_test.py"), 1, None)])
        command = self.command()
        self.assertTrue(command.handler("app.py").startswith("src/app.py\n"))
        self.assertIn("is ambiguous: 2 files match", command.handler("src/app"))
        self.assertTrue(command.handler("app_t").startswith("src/app_test.py"))
        self.assertTrue(command.handler("demo-project/src/app.py").startswith("src/app.py"))
        self.assertIn("demo-project (…/work/demo-project) · 2 files", command.handler("demo-proj"))
        self.assertIn("No recorded change matches 'nope.rs'", command.handler("nope.rs"))
        self.assertTrue(command.handler("test.py").startswith("src/app_test.py"))

    def test_lookup_without_records(self) -> None:
        self.assertIn("No file changes recorded", self.command().handler("x"))


class GitNumstatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.mkdir(os.path.join(self.root, ".git"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_with(self, **kwargs):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        for key, value in kwargs.items():
            setattr(completed, key, value)
        with (
            mock.patch.object(changes_mod.shutil, "which", return_value="/usr/bin/git"),
            mock.patch.object(changes_mod.subprocess, "run", return_value=completed) as run,
        ):
            result = git_numstat(self.root, "src/a.py")
        return result, run

    def test_ok_command_shape(self) -> None:
        result, run = self.run_with(stdout="12\t3\tsrc/a.py\n")
        self.assertEqual(result, NumstatResult("ok", 12, 3))
        args, kwargs = run.call_args
        command = args[0]
        self.assertEqual(command[0], "/usr/bin/git")
        self.assertEqual(command[command.index("-C") + 1], self.root)
        self.assertIn("--numstat", command)
        self.assertEqual(command[-2:], ["--", "src/a.py"])
        self.assertEqual(kwargs["timeout"], 2.0)
        self.assertFalse(kwargs["shell"])
        self.assertLessEqual(
            set(kwargs["env"]),
            {"PATH", "HOME", "LC_ALL", "GIT_TERMINAL_PROMPT", "GIT_OPTIONAL_LOCKS", "GIT_PAGER"},
        )

    def test_clean_binary_failed(self) -> None:
        self.assertEqual(self.run_with(stdout="")[0].state, "clean")
        self.assertEqual(self.run_with(stdout="-\t-\timg.png\n")[0].state, "binary")
        self.assertEqual(self.run_with(returncode=128)[0].state, "failed")
        self.assertEqual(self.run_with(stdout="garbage")[0].state, "failed")

    def test_timeout(self) -> None:
        with (
            mock.patch.object(changes_mod.shutil, "which", return_value="/usr/bin/git"),
            mock.patch.object(
                changes_mod.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=2),
            ),
        ):
            self.assertEqual(git_numstat(self.root, "a").state, "timeout")

    def test_os_error(self) -> None:
        with (
            mock.patch.object(changes_mod.shutil, "which", return_value="/usr/bin/git"),
            mock.patch.object(changes_mod.subprocess, "run", side_effect=OSError("nope")),
        ):
            self.assertEqual(git_numstat(self.root, "a").state, "failed")

    def test_non_git_and_missing_git_never_run(self) -> None:
        with mock.patch.object(changes_mod.subprocess, "run") as run:
            self.assertEqual(git_numstat(self.root, "a", in_git=False).state, "not_repo")
            with tempfile.TemporaryDirectory() as plain:
                self.assertEqual(git_numstat(plain, "a").state, "not_repo")
            with mock.patch.object(changes_mod.shutil, "which", return_value=None):
                self.assertEqual(git_numstat(self.root, "a").state, "no_git")
        run.assert_not_called()

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_real_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as repo:
            env = {"PATH": os.environ.get("PATH", ""), "HOME": repo, "GIT_CONFIG_NOSYSTEM": "1"}
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", repo]
            subprocess.run(["git", "init", "-q", repo], check=True, env=env)
            Path(repo, "a.txt").write_text("1\n2\n", encoding="utf-8")
            subprocess.run([*git, "add", "a.txt"], check=True, env=env)
            subprocess.run([*git, "commit", "-qm", "init"], check=True, env=env)
            Path(repo, "a.txt").write_text("1\n3\n4\n", encoding="utf-8")
            self.assertEqual(git_numstat(repo, "a.txt"), NumstatResult("ok", 2, 1))


class RegistrationTests(unittest.TestCase):
    def test_registered_and_listed(self) -> None:
        ctx = FakeContext()
        register(ctx)
        self.assertIn("odd-changes", ctx.commands)
        self.assertEqual(ctx.commands["odd-changes"]["args_hint"], "[file|project|all|clear]")
        listing = ctx.commands["odd-commands"]["handler"]("")
        self.assertIn("/odd_changes [file|project|all|clear]", listing)
        post = [cb for name, cb in ctx.hooks if name == "post_tool_call"]
        self.assertEqual(len(post), 2)  # subagent tracking + change capture

    def test_end_to_end_through_fake_hooks(self) -> None:
        ctx = FakeContext()
        register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            os.mkdir(os.path.join(root, ".git"))
            target = os.path.join(root, "x.py")
            ctx.fire("post_tool_call", **write_call("x.py", "a\nb\n", resolved=target))
            text = ctx.commands["odd-changes"]["handler"]("")
        self.assertIn("+2 −?  x.py  (1 edit · by main · just now)", text)
        self.assertIn(SCHEMA, ctx.state.dump())


if __name__ == "__main__":
    unittest.main()
