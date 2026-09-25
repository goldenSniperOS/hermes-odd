"""Feature-document parser, known projects and the ``/odd_tasks`` viewer."""

from __future__ import annotations

import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from fake_context import (
    REPO_ROOT,
    FakeContext,
    FakeState,
    ensure_repo_on_path,
    mark_setup_complete,
)

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.commands.tasks import (  # noqa: E402
    EMPTY_TEXT,
    OUTPUT_MAX_CHARS,
    format_age,
    make_odd_tasks,
    path_tail,
    progress_bar,
)
from hermes_odd.feature_docs import (  # noqa: E402
    list_feature_docs,
    parse_feature_text,
    read_feature_doc,
    split_task_id,
)
from hermes_odd.projects import (  # noqa: E402
    MAX_PROJECTS,
    SCHEMA,
    STATE_KEY,
    ProjectStore,
    git_root,
    process_cwd_candidates,
    resolve_projects,
)
from hermes_odd.prompt import ODD_SECTION, SECTION_ID, make_section_callable  # noqa: E402

REAL_DOC = REPO_ROOT / "odd" / "tasks" / "hermes-odd-port.md"
NOW = 1_790_000_000.0

SAMPLE = """\
# Feature: demo thing

## Objective

Do things.

## Tasks

- [x] T1 First task
      continued on a second line
- [ ] T2b Second task
  - [x] nested child ignored
- [X] T3: third with colon
* [ ] **T4** bold id
- [ ] no id here

```markdown
- [ ] T99 inside a fence is ignored
## Tasks
```

## Acceptance criteria

- [ ] not a task, other section

## Progress

- 2026: did stuff

## Next step

T2b second task, then
wrap up.

More text not in the first paragraph.
"""


def make_project(root: Path, docs: dict[str, str], git: bool = True) -> Path:
    tasks = root / "odd" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    if git:
        (root / ".git").mkdir(exist_ok=True)
    for name, text in docs.items():
        (tasks / f"{name}.md").write_text(text, encoding="utf-8")
    return root


def doc_text(title: str, done: int, total: int) -> str:
    lines = [f"# Feature: {title}", "", "## Tasks", ""]
    for i in range(1, total + 1):
        lines.append(f"- [{'x' if i <= done else ' '}] T{i} Task number {i}")
    return "\n".join(lines) + "\n"


class ParserTests(unittest.TestCase):
    def test_sample_document(self) -> None:
        doc = parse_feature_text(SAMPLE, "demo")
        self.assertEqual(doc.title, "demo thing")
        self.assertTrue(doc.has_tasks_heading)
        self.assertEqual([t.id for t in doc.tasks], ["T1", "T2b", "T3", "T4", ""])
        self.assertEqual([t.done for t in doc.tasks], [True, False, True, False, False])
        self.assertEqual(doc.tasks[0].title, "First task")
        self.assertEqual(doc.tasks[2].title, "third with colon")
        self.assertEqual(doc.tasks[4].title, "no id here")
        self.assertEqual((doc.done, doc.total), (2, 5))
        self.assertEqual(doc.next_task.id, "T2b")
        self.assertEqual(doc.next_step, "T2b second task, then wrap up.")

    def test_crlf_and_bom(self) -> None:
        doc = parse_feature_text("\ufeff" + SAMPLE.replace("\n", "\r\n"), "demo")
        self.assertEqual(doc.title, "demo thing")
        self.assertEqual([t.id for t in doc.tasks], ["T1", "T2b", "T3", "T4", ""])
        self.assertEqual(doc.next_step, "T2b second task, then wrap up.")

    def test_missing_tasks_heading_uses_top_level_checkboxes(self) -> None:
        doc = parse_feature_text("# Plain title\n\n- [x] A1 one\n  - [ ] sub\n- [ ] A2 two\n", "p")
        self.assertFalse(doc.has_tasks_heading)
        self.assertEqual(doc.title, "Plain title")
        self.assertEqual([(t.id, t.done) for t in doc.tasks], [("A1", True), ("A2", False)])
        self.assertEqual(doc.next_step, "")

    def test_no_title_falls_back_to_stem(self) -> None:
        doc = parse_feature_text("## Tasks\n- [ ] T1 x\n", "stem-name")
        self.assertEqual(doc.title, "stem-name")

    def test_empty_document(self) -> None:
        doc = parse_feature_text("", "empty")
        self.assertEqual((doc.total, doc.done, doc.next_task), (0, 0, None))

    def test_split_task_id(self) -> None:
        self.assertEqual(split_task_id("T10 Port skills"), ("T10", "Port skills"))
        self.assertEqual(split_task_id("`T2c` rename"), ("T2c", "rename"))
        self.assertEqual(split_task_id("12. numbered"), ("12", "numbered"))
        self.assertEqual(split_task_id("Write docs"), ("", "Write docs"))
        self.assertEqual(split_task_id("T"), ("", "T"))

    def test_real_feature_document(self) -> None:
        doc = read_feature_doc(REAL_DOC)
        self.assertEqual(doc.error, "")
        self.assertEqual(doc.feature, "hermes-odd-port")
        self.assertTrue(doc.title.startswith("hermes-odd port"))
        ids = [t.id for t in doc.tasks]
        self.assertEqual(ids[:6], ["T1", "T1b", "T2", "T2c", "T2b", "T3"])
        self.assertIn("T4", ids)
        self.assertIn("T10", ids)
        # The done flags must match the raw checkboxes of the Tasks section.
        text = REAL_DOC.read_text(encoding="utf-8")
        tasks_section = text.split("## Tasks", 1)[1].split("\n## ", 1)[0]
        expected = {}
        for line in tasks_section.splitlines():
            if line.startswith("- ["):
                expected[line[6:].split()[0]] = line[3] == "x"
        self.assertEqual({t.id: t.done for t in doc.tasks}, expected)
        self.assertIsNotNone(doc.mtime)

    def test_file_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.md"
            body = "# Feature: big\n\n## Tasks\n\n- [x] T1 first\n" + ("x" * 200 + "\n") * 50
            body += "- [ ] T2 beyond the limit\n"
            path.write_text(body, encoding="utf-8")
            doc = read_feature_doc(path, max_bytes=2048)
            self.assertTrue(doc.truncated)
            self.assertEqual([t.id for t in doc.tasks], ["T1"])

    def test_unreadable_file_reports_error(self) -> None:
        doc = read_feature_doc(Path("/nonexistent/odd/tasks/missing.md"))
        self.assertEqual(doc.error, "FileNotFoundError")
        self.assertEqual(doc.feature, "missing")


class ListDocsTests(unittest.TestCase):
    def test_file_limit_newest_first_and_skips_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), {f"f{i}": doc_text(f"f{i}", 0, 1) for i in range(5)})
            tasks = root / "odd" / "tasks"
            for i in range(5):
                os.utime(tasks / f"f{i}.md", (NOW + i, NOW + i))
            (tasks / "notes.txt").write_text("x", encoding="utf-8")
            (tasks / "link.md").symlink_to(tasks / "f0.md")
            (tasks / "sub.md").mkdir()
            docs, skipped = list_feature_docs(root, max_files=3)
            self.assertEqual([d.feature for d in docs], ["f4", "f3", "f2"])
            self.assertEqual(skipped, 2)

    def test_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_feature_docs(Path(tmp)), ([], 0))


class ProjectStoreTests(unittest.TestCase):
    def test_git_root_walks_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".git").mkdir()
            deep = root / "a" / "b"
            deep.mkdir(parents=True)
            self.assertEqual(git_root(deep), root)
            self.assertIsNone(git_root(root / "missing"))
            self.assertIsNone(git_root("relative/path"))

    def test_record_dedupes_most_recent_first_and_bounds(self) -> None:
        clock = iter(range(1000, 2000))
        state = FakeState()
        store = ProjectStore(state, clock=lambda: float(next(clock)))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            dirs = []
            for i in range(MAX_PROJECTS + 3):
                d = base / f"p{i}"
                (d / ".git").mkdir(parents=True)
                dirs.append(d)
                store.record(str(d / ""), "cli")
            store.record(str(dirs[5]), "telegram")
            known = store.known()
            self.assertEqual(len(known), MAX_PROJECTS)
            self.assertEqual(known[0].root, dirs[5])
            self.assertEqual(known[0].platform, "telegram")
            self.assertEqual(len({p.root for p in known}), MAX_PROJECTS)
            self.assertNotIn(dirs[0], [p.root for p in known])
            doc = state.get(STATE_KEY)
            self.assertEqual(doc["schema"], SCHEMA)

    def test_record_empty_cwd_uses_process_cwd(self) -> None:
        store = ProjectStore()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".git").mkdir()
            with mock.patch("os.getcwd", return_value=str(root)):
                self.assertEqual(store.record("", "cli"), root)
        self.assertEqual(store.known()[0].root, root)

    def test_record_never_raises_and_bad_state_is_ignored(self) -> None:
        class Broken:
            def get(self, key, default=None):
                raise OSError("disk")

            def set(self, key, value):
                raise OSError("disk")

        store = ProjectStore(Broken())
        with self.assertLogs("hermes_odd", level="WARNING"):
            store.record("/", "cli")
        self.assertEqual(store.known()[0].root, Path("/"))
        state = FakeState()
        state.set(STATE_KEY, {"schema": SCHEMA, "projects": [{"root": "rel"}, 5, {"root": 3}]})
        self.assertEqual(ProjectStore(state).known(), [])
        with mock.patch("os.getcwd", side_effect=OSError("gone")):
            self.assertIsNone(ProjectStore().record(None, None))

    def test_resolve_dedupes_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            with_docs = make_project(base / "a", {"x": doc_text("x", 1, 2)})
            without = base / "b"
            (without / ".git").mkdir(parents=True)
            store = ProjectStore()
            store.record(str(with_docs))
            store.record(str(without))
            projects = resolve_projects(store, [with_docs, without])
            self.assertEqual([p.root for p in projects], [with_docs])
            self.assertEqual(projects[0].source, "known")

    def test_process_cwd_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".git").mkdir()
            (root / "sub").mkdir()
            with mock.patch("os.getcwd", return_value=str(root / "sub")):
                self.assertEqual(process_cwd_candidates({"TERMINAL_CWD": str(root)}), [root])
                self.assertEqual(process_cwd_candidates({"TERMINAL_CWD": "/nope/x"}), [root])


class SectionRecordingTests(unittest.TestCase):
    def test_section_text_is_byte_identical(self) -> None:
        seen = []
        render = make_section_callable(seen.append)
        info = types.MappingProxyType({"platform": "telegram", "cwd": "/tmp"})
        rendered = render(info)
        self.assertEqual(rendered, ODD_SECTION.strip())
        self.assertEqual(rendered.encode("utf-8"), ODD_SECTION.strip().encode("utf-8"))
        self.assertEqual(seen, [info])
        self.assertEqual(make_section_callable()({}), ODD_SECTION.strip())

    def test_failing_observer_never_skips_section(self) -> None:
        def boom(info):
            raise RuntimeError("x")

        self.assertEqual(make_section_callable(boom)({"cwd": "/"}), ODD_SECTION.strip())

    def test_register_records_known_project_from_section(self) -> None:
        ctx = FakeContext()
        register(ctx)
        mark_setup_complete(ctx.state)  # no pending-setup line
        section = next(s for s in ctx.prompt_sections if s["id"] == SECTION_ID)
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp).resolve(), {"demo": doc_text("Demo", 1, 3)})
            info = types.MappingProxyType({"platform": "telegram", "cwd": str(root / "odd")})
            self.assertEqual(section["content"](info), ODD_SECTION.strip())
            stored = ctx.state.get(STATE_KEY)
            self.assertEqual(stored["projects"][0]["root"], str(root))
            self.assertEqual(stored["projects"][0]["platform"], "telegram")
            output = ctx.commands["odd-tasks"]["handler"]("")
            self.assertIn("demo", output)
            self.assertIn("▰", output)


class ViewerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def handler(self, roots, store=None):
        spec = make_odd_tasks(store, clock=lambda: NOW, cwd_candidates=lambda: list(roots))
        return spec.handler

    def test_progress_bar_and_helpers(self) -> None:
        self.assertEqual(progress_bar(3, 5, 5), "▰▰▰▱▱ 3/5")
        self.assertEqual(progress_bar(0, 0), "no tasks")
        self.assertEqual(progress_bar(9, 10, 5), "▰▰▰▰▱ 9/10")
        self.assertEqual(progress_bar(1, 100, 5), "▰▱▱▱▱ 1/100")
        self.assertEqual(format_age(NOW - 7200, NOW), "2h ago")
        self.assertEqual(format_age(None, NOW), "unknown")
        self.assertEqual(path_tail(Path("/Users/me/Apps/proj")), "…/Apps/proj")

    def test_empty_state(self) -> None:
        self.assertEqual(self.handler([])(""), EMPTY_TEXT)
        self.assertIn("odd/tasks/<feature>.md", EMPTY_TEXT)
        self.assertEqual(self.handler([])("anything"), EMPTY_TEXT)

    def test_overview_orders_by_mtime_and_shows_next(self) -> None:
        root = make_project(
            self.base / "proj", {"old": doc_text("Old", 2, 2), "new": doc_text("New", 1, 3)}
        )
        tasks = root / "odd" / "tasks"
        os.utime(tasks / "old.md", (NOW - 86400 * 2, NOW - 86400 * 2))
        os.utime(tasks / "new.md", (NOW - 120, NOW - 120))
        out = self.handler([root])("")
        self.assertIn("proj (…/", out)
        self.assertLess(out.index(" new ·"), out.index(" old ·"))
        self.assertIn("1/3 new · 2m ago", out)
        self.assertIn("next: T2 Task number 2", out)
        self.assertIn("all tasks done", out)
        self.assertNotIn("|", out)  # no Markdown tables

    def test_output_cap(self) -> None:
        long_task = "# Feature: f\n## Tasks\n- [ ] T1 " + "long title " * 10 + "\n"
        docs = {f"feature-with-a-long-name-{i:02d}": long_task for i in range(50)}
        root = make_project(self.base / "big", docs)
        out = self.handler([root])("")
        self.assertLessEqual(len(out), OUTPUT_MAX_CHARS)
        self.assertRegex(out, r"… \d+ more")
        many = "".join(f"- [ ] T{i} " + "z" * 100 + "\n" for i in range(80))
        make_project(self.base / "big", {"huge": "# Feature: huge\n## Tasks\n" + many})
        detail = self.handler([root])("huge")
        self.assertLessEqual(len(detail), OUTPUT_MAX_CHARS)
        self.assertRegex(detail, r"… \d+ more")
        self.assertIn("file: ", detail)

    def test_detail_prefix_ambiguous_not_found(self) -> None:
        a = make_project(
            self.base / "alpha",
            {"hermes-odd-port": SAMPLE, "hermes-odd-extra": doc_text("E", 0, 1)},
        )
        b = make_project(self.base / "beta", {"payments": doc_text("Pay", 0, 2)})
        handler = self.handler([a, b])
        detail = handler("hermes-odd-p")
        self.assertIn("demo thing", detail)
        self.assertIn("✓ T1 First task", detail)
        self.assertIn("○ T2b Second task  ← next", detail)
        self.assertIn("Next step: T2b second task", detail)
        self.assertIn("odd/tasks/hermes-odd-port.md", detail)
        ambiguous = handler("hermes-odd")
        self.assertIn("ambiguous", ambiguous)
        self.assertIn("alpha/hermes-odd-port", ambiguous)
        self.assertIn("demo thing", handler("alpha/hermes-odd-port"))
        self.assertIn("demo thing", handler("HERMES-ODD-PORT"))
        missing = handler("zzz")
        self.assertIn("No feature or project matches 'zzz'", missing)
        # Project filter: exact name, then prefix.
        project_view = handler("beta")
        self.assertIn("payments", project_view)
        self.assertNotIn("hermes-odd-port", project_view)
        self.assertIn("payments", handler("bet"))
        self.assertIn("payments", handler("beta/"))

    def test_same_feature_in_two_projects_is_ambiguous(self) -> None:
        a = make_project(self.base / "one", {"shared": doc_text("S", 0, 1)})
        b = make_project(self.base / "two", {"shared": doc_text("S", 1, 1)})
        out = self.handler([a, b])("shared")
        self.assertIn("ambiguous", out)
        self.assertIn("one/shared", out)
        self.assertIn("1/1", self.handler([a, b])("two/shared"))

    def test_handler_never_raises_on_unreadable_files(self) -> None:
        root = make_project(self.base / "p", {"ok": doc_text("Ok", 1, 1), "bad": "x"})
        with mock.patch(
            "hermes_odd.feature_docs.open", side_effect=PermissionError("denied"), create=True
        ):
            out = self.handler([root])("")
            detail = self.handler([root])("bad")
        self.assertIn("unreadable (PermissionError)", out)
        self.assertIn("unreadable (PermissionError)", detail)

    def test_registered_and_listed(self) -> None:
        registry = build_registry()
        spec = registry.get("odd_tasks")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.args_hint, "[feature|project]")
        self.assertIn("/odd_tasks [feature|project]", registry.get("odd_commands").handler(""))
        ctx = FakeContext()
        register(ctx)
        self.assertIn("odd-tasks", ctx.commands)
        self.assertEqual(ctx.commands["odd-tasks"]["args_hint"], "[feature|project]")


if __name__ == "__main__":
    unittest.main()
