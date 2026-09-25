"""scripts/check_upstream_drift.py against throwaway git repositories (no network)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import REPO_ROOT, ensure_repo_on_path

ensure_repo_on_path()

SCRIPT = REPO_ROOT / "scripts" / "check_upstream_drift.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "upstream-drift.yml"
TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "upstream_port_request.yml"


def load_script():
    spec = importlib.util.spec_from_file_location("check_upstream_drift", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module here
    spec.loader.exec_module(module)
    return module


drift = load_script()

ROUTING = "internal/components/agentguidance/routing.go"
JD_SKILL = "internal/assets/skills/judgment-day/SKILL.md"
PROTOCOL = "internal/assets/engram/protocol.md"
NEW_SKILL = "internal/assets/skills/new-skill/SKILL.md"
SHELL_SOURCE = "assets/orchestrator.md"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GitRepo:
    """A small non-bare repository used as an upstream ``origin``."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.ticks = 0
        path.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = (
            f"2026-01-{self.ticks + 1:02d}T12:00:00Z"
        )
        result = subprocess.run(
            ["git", "-C", str(self.path), "-c", "commit.gpgsign=false", *args],
            capture_output=True,
            check=True,
            env=env,
        )
        return result.stdout.decode().strip()

    def commit(self, message: str, write=None, delete=()) -> str:
        for rel, text in (write or {}).items():
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        for rel in delete:
            (self.path / rel).unlink()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.ticks += 1
        return self.git("rev-parse", "HEAD")


class DriftTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="hermes-odd-drift-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = mock.patch.dict(
            os.environ,
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Upstream",
                "GIT_AUTHOR_EMAIL": "upstream@example.invalid",
                "GIT_COMMITTER_NAME": "Upstream",
                "GIT_COMMITTER_EMAIL": "upstream@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )
        env.start()
        self.addCleanup(env.stop)
        self.cache = self.root / "cache"

        self.ai = GitRepo(self.root / "origin" / "gentle-ai")
        self.files = {
            ROUTING: "package agentguidance // v1\n",
            JD_SKILL: "# judge\n",
            PROTOCOL: "# protocol\n",
            "internal/assets/hermes/persona.md": "# persona\n",
        }
        self.pin = self.ai.commit("feat: baseline", self.files)
        self.shell = GitRepo(self.root / "origin" / "gentle-shell")
        self.shell_pin = self.shell.commit("feat: shell baseline", {SHELL_SOURCE: "# orch\n"})

    # -- helpers ----------------------------------------------------------

    def lock(self, **overrides) -> dict:
        ai_pin = overrides.get("ai_pin", self.pin)
        routing_sha = overrides.get("routing_sha", sha(self.files[ROUTING]))
        return {
            "schema": "hermes-odd.upstream-lock/v1",
            "updated": "2026-01-01",
            "upstreams": {
                "gentle-ai": {"repo": str(self.ai.path), "pinned_commit": ai_pin},
                "gentle-shell": {"repo": str(self.shell.path), "pinned_commit": self.shell_pin},
            },
            "components": {
                "odd": {
                    "sources": [
                        {"upstream": "gentle-ai", "path": ROUTING, "sha256": routing_sha},
                        {
                            "upstream": "gentle-shell",
                            "path": SHELL_SOURCE,
                            "sha256": sha("# orch\n"),
                        },
                    ]
                },
                "portable-skills": {
                    "sources": [
                        {"upstream": "gentle-ai", "path": JD_SKILL, "sha256": sha("# judge\n")},
                        {"upstream": "gentle-ai", "path": ROUTING, "sha256": routing_sha},
                    ]
                },
                "soul-cleanup": {
                    "sources": [
                        {"upstream": "gentle-ai", "path": PROTOCOL, "sha256": sha("# protocol\n")}
                    ]
                },
            },
        }

    def advance_gentle_ai(self) -> tuple[str, str]:
        changed = self.ai.commit(
            "feat(odd): default to test-first",
            {
                ROUTING: "package agentguidance // v2\n",
                NEW_SKILL: "# new\n",
                "internal/assets/skills/sdd-apply/SKILL.md": "# excluded\n",
                "internal/components/agentguidance/strict_tdd_test.go": "package x\n",
                "notes.txt": "unwatched\n",
            },
        )
        deleted = self.ai.commit("refactor: drop protocol", delete=[PROTOCOL])
        return changed, deleted

    def report(self, lock: dict | None = None, offline: bool = False) -> dict:
        return drift.build_report(lock or self.lock(), self.cache, offline=offline, now="T")

    @staticmethod
    def files_by_path(upstream_report: dict) -> dict:
        return {row["path"]: row for row in upstream_report["files"]}


class IndexAndCacheTests(DriftTestCase):
    def test_sources_are_deduplicated_with_every_component(self) -> None:
        index, errors = drift.index_sources(self.lock())
        self.assertEqual(errors, [])
        self.assertEqual(len(index), 4)
        routing = index[("gentle-ai", ROUTING)]
        self.assertEqual(routing.components, ["odd", "portable-skills"])

    def test_two_hashes_for_one_source_is_an_error(self) -> None:
        lock = self.lock()
        lock["components"]["odd"]["sources"][0]["sha256"] = "0" * 64
        _, errors = drift.index_sources(lock)
        self.assertEqual(len(errors), 1)
        self.assertIn(ROUTING, errors[0])

    def test_cache_resolution_order(self) -> None:
        env = {drift.CACHE_ENV: str(self.root / "env")}
        self.assertEqual(drift.resolve_cache(str(self.root / "cli"), env), self.root / "cli")
        self.assertEqual(drift.resolve_cache(None, env), self.root / "env")
        self.assertEqual(drift.resolve_cache(None, {}), drift.DEFAULT_CACHE)
        self.assertEqual(drift.DEFAULT_CACHE.parts[-1], "upstream")

    def test_watch_globs_skip_sdd_and_tests(self) -> None:
        self.assertTrue(drift.is_candidate("gentle-ai", NEW_SKILL))
        self.assertTrue(drift.is_candidate("gentle-shell", "skills/new/SKILL.md"))
        self.assertFalse(drift.is_candidate("gentle-shell", "skills/new/deep/SKILL.md"))
        self.assertFalse(drift.is_candidate("gentle-ai", "internal/assets/skills/sdd-x/SKILL.md"))
        self.assertFalse(drift.is_candidate("gentle-shell", "assets/openspec-flow.md"))
        self.assertFalse(
            drift.is_candidate("gentle-ai", "internal/components/agentguidance/x_test.go")
        )
        self.assertFalse(drift.is_candidate("gentle-ai", "notes.txt"))


class CleanAndDriftTests(DriftTestCase):
    def test_clean_when_head_is_the_pin(self) -> None:
        report = self.report()
        self.assertEqual(report["schema"], "hermes-odd.upstream-drift/v1")
        self.assertEqual(report["status"], "clean", report["errors"])
        self.assertEqual(drift.exit_code(report), drift.EXIT_CLEAN)
        ai = report["upstreams"]["gentle-ai"]
        self.assertEqual(ai["default_branch"], "main")
        self.assertEqual(ai["head_commit"], self.pin)
        self.assertEqual({r["status"] for r in ai["files"]}, {"unchanged"})
        self.assertEqual(ai["commits_beyond_pin"], [])
        self.assertFalse(ai["needs_go_rerender"])
        self.assertTrue((self.cache / "gentle-ai" / ".git").is_dir())

    def test_changed_deleted_unchanged_candidates_and_rerender(self) -> None:
        changed, deleted = self.advance_gentle_ai()
        report = self.report()
        self.assertEqual(report["status"], "drift", report["errors"])
        self.assertEqual(drift.exit_code(report), drift.EXIT_DRIFT)
        self.assertEqual(drift.exit_code(report, exit_zero=True), drift.EXIT_CLEAN)
        ai = report["upstreams"]["gentle-ai"]
        self.assertEqual(ai["head_commit"], deleted)
        self.assertEqual([c["sha"] for c in ai["commits_beyond_pin"]], [deleted, changed])
        rows = self.files_by_path(ai)
        self.assertEqual(rows[ROUTING]["status"], "changed")
        self.assertEqual(rows[ROUTING]["components"], ["odd", "portable-skills"])
        self.assertEqual([c["sha"] for c in rows[ROUTING]["commits"]], [changed])
        self.assertEqual(rows[ROUTING]["commits"][0]["subject"], "feat(odd): default to test-first")
        self.assertEqual(rows[PROTOCOL]["status"], "deleted")
        self.assertIsNone(rows[PROTOCOL]["head_sha256"])
        self.assertEqual([c["sha"] for c in rows[PROTOCOL]["commits"]], [deleted])
        self.assertEqual(rows[JD_SKILL]["status"], "unchanged")
        self.assertEqual(rows[JD_SKILL]["commits"], [])
        self.assertEqual(ai["candidates"], [{"status": "added", "path": NEW_SKILL}])
        self.assertTrue(ai["needs_go_rerender"])
        self.assertEqual(ai["rerender_reasons"], [f"{ROUTING} changed"])
        self.assertEqual(report["upstreams"]["gentle-shell"]["files"][0]["status"], "unchanged")
        self.assertEqual(
            report["summary"],
            {"changed": 1, "deleted": 1, "unchanged": 2, "candidates": 1, "commits": 2},
        )

    def test_existing_checkout_is_fetched(self) -> None:
        self.assertEqual(self.report()["status"], "clean")
        _, head = self.advance_gentle_ai()
        report = self.report()
        self.assertEqual(report["upstreams"]["gentle-ai"]["head_commit"], head)
        self.assertEqual(report["status"], "drift")

    def test_offline_uses_the_existing_checkout_only(self) -> None:
        missing = self.report(offline=True)
        self.assertEqual(missing["status"], "error")
        self.assertIn("--offline", " ".join(missing["errors"]))
        self.report()  # clone
        self.advance_gentle_ai()
        offline = self.report(offline=True)
        self.assertEqual(offline["status"], "clean", offline["errors"])  # nothing fetched


class ErrorTests(DriftTestCase):
    def assert_error(self, report: dict, needle: str) -> None:
        self.assertEqual(report["status"], "error")
        self.assertEqual(drift.exit_code(report), drift.EXIT_ERROR)
        self.assertEqual(drift.exit_code(report, exit_zero=True), drift.EXIT_ERROR)
        self.assertIn(needle, " ".join(report["errors"]))

    def test_missing_pin(self) -> None:
        self.assert_error(self.report(self.lock(ai_pin="0" * 40)), "does not exist upstream")

    def test_pin_not_an_ancestor_of_head(self) -> None:
        self.ai.git("checkout", "-q", "-b", "rewritten")
        side = self.ai.commit("feat: side history", {"side.txt": "x\n"})
        self.ai.git("checkout", "-q", "main")
        self.ai.commit("feat: main moves on", {"main.txt": "y\n"})
        self.assert_error(self.report(self.lock(ai_pin=side)), "not an ancestor")

    def test_lock_hash_mismatch_at_the_pin(self) -> None:
        self.assert_error(self.report(self.lock(routing_sha="f" * 64)), "at the pin")

    def test_source_missing_at_the_pin(self) -> None:
        lock = self.lock()
        lock["components"]["soul-cleanup"]["sources"][0]["path"] = "missing.md"
        self.assert_error(self.report(lock), "does not exist at the pin")


class OutputTests(DriftTestCase):
    def test_markdown_uses_the_port_request_headings(self) -> None:
        self.advance_gentle_ai()
        text = drift.render_markdown(self.report())
        headings = re.findall(r"(?m)^### (.+)$", text)
        self.assertEqual(tuple(headings), drift.ISSUE_HEADINGS)
        self.assertIn(f"`{ROUTING}` | changed | odd, portable-skills", text)
        self.assertIn(f"`{NEW_SKILL}`", text)
        self.assertIn("Go re-render needed", text)

    def test_headings_match_the_issue_template(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        labels = tuple(re.findall(r"(?m)^\s+label: (.+)$", template))
        self.assertEqual(labels, drift.ISSUE_HEADINGS)

    def test_main_writes_json_and_returns_the_exit_code(self) -> None:
        self.advance_gentle_ai()
        lock_path = self.root / "upstream.lock.json"
        lock_path.write_text(json.dumps(self.lock()), encoding="utf-8")
        out = self.root / "report.json"
        argv = ["--lock", str(lock_path), "--cache", str(self.cache), "--format", "json"]
        self.assertEqual(drift.main([*argv, "--output", str(out)]), drift.EXIT_DRIFT)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], drift.REPORT_SCHEMA)
        self.assertEqual(data["status"], "drift")
        self.assertEqual(drift.main([*argv, "--output", str(out), "--exit-zero"]), 0)
        md = self.root / "report.md"
        drift.main(["--lock", str(lock_path), "--cache", str(self.cache), "--output", str(md)])
        self.assertTrue(md.read_text(encoding="utf-8").startswith("Upstream drift report"))

    def test_unreadable_lock_is_an_error(self) -> None:
        bad = self.root / "bad.json"
        bad.write_text('{"schema": "other"}', encoding="utf-8")
        with mock.patch("sys.stderr"):
            self.assertEqual(drift.main(["--lock", str(bad)]), drift.EXIT_ERROR)


class WorkflowTests(unittest.TestCase):
    def test_scheduled_workflow_contract(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "schedule:",
            "cron:",
            "workflow_dispatch:",
            "contents: read",
            "issues: write",
            "concurrency:",
            "scripts/check_upstream_drift.py",
            "HERMES_ODD_UPSTREAM_CACHE",
            drift.ISSUE_TITLE,
            "gh label create",
            "--force",
            "--body-file",
        ):
            self.assertIn(token, text)
        # Exit code 2 (error) fails the job; 1 (drift) opens or updates the issue.
        self.assertIn('"$code" -ge 2', text)
        self.assertIn("steps.drift.outputs.code == '1'", text)


if __name__ == "__main__":
    unittest.main()
