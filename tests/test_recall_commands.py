"""The recall provider in ``/odd-doctor`` (memory check) and ``/odd-status`` (memory line)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.commands.doctor import OK, WARN, Doctor, check_memory  # noqa: E402
from hermes_odd.commands.status import OUTPUT_MAX_CHARS, Status  # noqa: E402
from hermes_odd.probes import Prober  # noqa: E402
from hermes_odd.recall import EngramHealth, LastMemory, RecallInfo  # noqa: E402

EPOCH = 1767225600.0  # 2026-01-01T00:00:00+00:00
LAST = LastMemory(761, "saved", "hermes-odd", "2026-01-01T00:00:00+00:00")
URL = "http://127.0.0.1:7437"
UP = EngramHealth(True, "", "2.0.0")
DOWN = EngramHealth(False, "unreachable")


class FakeRecall:
    def __init__(self, provider="recall", mcp=False, last=LAST, health=UP) -> None:
        self._info = RecallInfo(provider, mcp, last)
        self._health = health
        self.probes = 0

    def info(self) -> RecallInfo:
        return self._info

    def health(self) -> EngramHealth:
        self.probes += 1
        return self._health

    def url(self) -> str:
        return URL


class DoctorMemoryCheckTests(unittest.TestCase):
    def test_active_and_healthy(self) -> None:
        check = check_memory(FakeRecall(), 6.0)
        self.assertEqual(check.level, OK)
        self.assertEqual(
            check.render(), f"✓  memory: recall provider active; Engram 2.0.0 at {URL}"
        )

    def test_active_and_down(self) -> None:
        check = check_memory(FakeRecall(health=DOWN), 6.0)
        self.assertEqual(check.level, WARN)
        self.assertIn(f"Engram unreachable at {URL}", check.finding)
        self.assertEqual(check.hint, "start it: engram serve")

    def test_duplicate_mcp_combines_with_down(self) -> None:
        check = check_memory(FakeRecall(mcp=True, health=DOWN), 6.0)
        self.assertEqual(check.level, WARN)
        self.assertIn("duplicate Engram tools", check.finding)
        self.assertEqual(
            check.hint, "start it: engram serve; optional: hermes mcp remove engram, then restart"
        )
        self.assertNotIn("mem_search", check.finding)  # no individual tool names

    def test_duplicate_mcp_with_healthy_engram_warns(self) -> None:
        check = check_memory(FakeRecall(mcp=True), 6.0)
        self.assertEqual(check.level, WARN)
        self.assertEqual(check.hint, "optional: hermes mcp remove engram, then restart")

    def test_inactive_and_unknown_never_probe(self) -> None:
        cases = [
            ("", "builtin memory (memory.provider: builtin); optional: hermes-recall"),
            ("honcho", "builtin memory (memory.provider: honcho); optional: hermes-recall"),
            (None, "memory provider unknown (config unavailable)"),
        ]
        for provider, expected in cases:
            with self.subTest(provider=provider):
                recall = FakeRecall(provider=provider, mcp=True)
                check = check_memory(recall, 6.0)
                self.assertEqual(check.level, OK)
                self.assertTrue(check.finding.startswith(expected))
                self.assertEqual(recall.probes, 0)

    def test_out_of_budget_skips_the_probe(self) -> None:
        recall = FakeRecall()
        check = check_memory(recall, 0.5)
        self.assertEqual(check.level, WARN)
        self.assertIn("not probed", check.finding)
        self.assertEqual(recall.probes, 0)

    def test_doctor_runs_it_within_the_deadline(self) -> None:
        ticks = iter([0.0] + [5.0] * 50)  # budget almost spent after the start
        with tempfile.TemporaryDirectory() as tmp:
            recall = FakeRecall()
            doctor = Doctor(
                None,
                Prober(finder=lambda: []),
                home=lambda: Path(tmp),
                monotonic=lambda: next(ticks),
                recall=recall,
            )
            text = doctor.render()
        self.assertIn("⚠  memory: recall provider active; Engram health not probed", text)
        self.assertEqual(recall.probes, 0)

    def test_a_raising_recall_is_reported(self) -> None:
        class Boom(FakeRecall):
            def info(self):
                raise RuntimeError("x")

        with tempfile.TemporaryDirectory() as tmp:
            text = Doctor(
                None, Prober(finder=lambda: []), home=lambda: Path(tmp), recall=Boom()
            ).render()
        self.assertIn("⚠  memory: check failed (RuntimeError)", text)


def status_line(recall) -> str:
    status = Status(
        None, Prober(finder=lambda: []), cwd_candidates=[], recall=recall, clock=lambda: EPOCH
    )
    lines = [line for line in status.lines() if line.startswith("Memory:")]
    return lines[0]


class StatusMemoryLineTests(unittest.TestCase):
    def test_lines(self) -> None:
        cases = [
            (
                FakeRecall(),
                "Memory: recall · Engram 2.0.0 ✓ · last #761 saved (hermes-odd, just now)",
            ),
            (FakeRecall(health=DOWN), "Memory: recall · Engram ✗ unreachable · last #761 saved"),
            (FakeRecall(last=None), "Memory: recall · Engram 2.0.0 ✓ · last: none yet"),
            (FakeRecall(provider=""), "Memory: builtin (hermes-recall not active)"),
            (FakeRecall(provider=None), "Memory: unknown"),
        ]
        for recall, expected in cases:
            with self.subTest(expected=expected):
                self.assertTrue(status_line(recall).startswith(expected))

    def test_age_and_long_fields_stay_compact(self) -> None:
        last = LastMemory(7, "x" * 500, "p" * 500, "2025-12-31T23:57:00Z")
        line = status_line(FakeRecall(last=last))
        self.assertIn("3m ago)", line)
        self.assertLess(len(line), 140)
        status = Status(
            None, Prober(finder=lambda: []), cwd_candidates=[], recall=FakeRecall(last=last)
        )
        self.assertLessEqual(len(status.render()), OUTPUT_MAX_CHARS)

    def test_registry_shares_one_recall(self) -> None:
        recall = FakeRecall(provider=None)
        registry = build_registry(prober=Prober(finder=lambda: []), recall=recall)
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"HERMES_HOME": tmp}),
            mock.patch.dict("sys.modules", {"hermes_constants": None}),
        ):
            status = registry.get("odd_status").handler("")
            doctor = registry.get("odd_doctor").handler("")
        self.assertIn("Memory: unknown", status)
        self.assertIn("memory provider unknown", doctor)


if __name__ == "__main__":
    unittest.main()
