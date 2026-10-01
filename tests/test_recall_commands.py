"""The recall provider in ``/odd-doctor`` (memory check) and ``/odd-status`` (memory line)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fake_context import ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.commands.doctor import OK, WARN, Doctor, check_memory  # noqa: E402
from hermes_odd.commands.status import OUTPUT_MAX_CHARS, Status  # noqa: E402
from hermes_odd.probes import Prober  # noqa: E402
from hermes_odd.recall import EngramHealth, LastMemory, Recall, RecallInfo  # noqa: E402

EPOCH = 1767225600.0  # 2026-01-01T00:00:00+00:00
LAST = LastMemory(761, "saved", "hermes-odd", "2026-01-01T00:00:00+00:00")
URL = "http://127.0.0.1:7437"
UP = EngramHealth(True, "", "2.0.0")
DOWN = EngramHealth(False, "unreachable")


class FakeRecall:
    def __init__(
        self,
        provider="recall",
        mcp=False,
        last=LAST,
        health=UP,
        cached=None,
        url=URL,
        enabled=True,
    ) -> None:
        self._info = RecallInfo(provider, mcp, last, enabled)
        self._health, self._cached, self._url = health, cached, url
        self.probes = 0

    def cached_health(self) -> EngramHealth | None:
        return self._cached

    def info(self) -> RecallInfo:
        return self._info

    def health(self) -> EngramHealth:
        self.probes += 1
        return self._health

    def url(self) -> str:
        return self._url


RECALL_LINE = (
    "recall provider active; last #761 saved (hermes-odd, just now); Engram details: /recall"
)
BUILTIN_HINT = "optional: hermes-recall for automatic Engram recall"


def memory(recall, budget=6.0):
    return check_memory(recall, budget, EPOCH)


class DoctorMemoryCheckTests(unittest.TestCase):
    def test_active_recall_never_probes(self) -> None:
        for health in (UP, DOWN):
            with self.subTest(health=health):
                recall = FakeRecall(health=health, cached=health)
                check = memory(recall)
                self.assertEqual(check.level, OK)
                self.assertEqual(check.render(), f"✓  memory: {RECALL_LINE}")
                self.assertEqual(recall.probes, 0)

    def test_active_recall_without_a_last_memory(self) -> None:
        check = memory(FakeRecall(last=None))
        self.assertEqual(
            check.finding, "recall provider active; last: none yet; Engram details: /recall"
        )

    def test_active_recall_with_engram_mcp_warns_duplicate(self) -> None:
        recall = FakeRecall(mcp=True, health=DOWN)
        check = memory(recall)
        self.assertEqual(check.level, WARN)
        self.assertTrue(check.finding.startswith(RECALL_LINE + "; "))
        self.assertIn("duplicate Engram tools", check.finding)
        self.assertNotIn("mem_search", check.finding)  # no individual tool names
        self.assertEqual(check.hint, "optional: hermes mcp remove engram, then restart")
        self.assertEqual(recall.probes, 0)

    def test_not_active_without_engram_mcp_never_probes(self) -> None:
        cases = [
            ("", f"builtin memory (memory.provider: builtin); {BUILTIN_HINT}"),
            ("honcho", f"builtin memory (memory.provider: honcho); {BUILTIN_HINT}"),
        ]
        for provider, expected in cases:
            with self.subTest(provider=provider):
                recall = FakeRecall(provider=provider)
                check = memory(recall)
                self.assertEqual((check.level, check.finding), (OK, expected))
                self.assertEqual(recall.probes, 0)

    def test_disabled_recall_is_not_active(self) -> None:
        recall = FakeRecall(enabled=False)
        check = memory(recall)
        self.assertEqual(check.level, OK)
        self.assertEqual(
            check.finding,
            f"recall (disabled: memory.recall.enabled false); builtin memory; {BUILTIN_HINT}",
        )
        self.assertEqual(recall.probes, 0)
        check = memory(FakeRecall(enabled=False, mcp=True))  # the MCP server is the Engram path
        self.assertIn("builtin memory; Engram 2.0.0 at", check.finding)
        self.assertEqual(
            status_line(FakeRecall(enabled=False)),
            "Memory: recall (disabled: memory.recall.enabled false)",
        )

    def test_unknown_provider_never_probes(self) -> None:
        recall = FakeRecall(provider=None, mcp=True)
        check = memory(recall)
        self.assertEqual(check.level, OK)
        self.assertEqual(check.finding, "memory provider unknown (config unavailable)")
        self.assertEqual(recall.probes, 0)

    def test_not_active_with_engram_mcp_and_healthy(self) -> None:
        recall = FakeRecall(provider="", mcp=True)
        check = memory(recall)
        self.assertEqual(check.level, OK)
        self.assertEqual(
            check.finding,
            f"builtin memory (memory.provider: builtin); Engram 2.0.0 at {URL}; {BUILTIN_HINT}",
        )
        self.assertEqual(recall.probes, 1)

    def test_not_active_with_engram_mcp_and_down(self) -> None:
        check = memory(FakeRecall(provider="honcho", mcp=True, health=DOWN))
        self.assertEqual(check.level, WARN)
        self.assertIn(f"; Engram unreachable at {URL}; {BUILTIN_HINT}", check.finding)
        self.assertEqual(check.hint, "start it: engram serve")

    def test_out_of_budget_skips_the_probe(self) -> None:
        recall = FakeRecall(provider="", mcp=True)
        check = memory(recall, 0.5)
        self.assertEqual(check.level, WARN)
        self.assertIn("not probed", check.finding)
        self.assertEqual(check.hint, "run /odd-doctor again")
        self.assertEqual(recall.probes, 0)

    def test_out_of_budget_uses_a_fresh_cached_result(self) -> None:
        recall = FakeRecall(provider="", mcp=True, cached=DOWN)
        check = memory(recall, 0.5)
        self.assertIn(f"Engram unreachable at {URL}", check.finding)
        self.assertEqual(recall.probes, 0)

    def test_displayed_url_carries_no_credentials(self) -> None:
        recall = FakeRecall(provider="", mcp=True, url="https://user:secret@h:9/e?token=t#f")
        check = memory(recall)
        self.assertIn("at https://h:9/e", check.finding)
        for leaked in ("user", "secret", "token", "#f"):
            self.assertNotIn(leaked, check.finding)

    def test_doctor_reads_soul_from_the_recall_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SOUL.md").write_text("# soul\n", encoding="utf-8")
            recall = Recall(home=lambda: Path(tmp), config_source=lambda: None)
            doctor = Doctor(None, Prober(finder=lambda: []), recall=recall)
            self.assertEqual(doctor._home(), Path(tmp))
            self.assertIn("SOUL.md: ", doctor.render())

    def test_doctor_runs_it_within_the_deadline(self) -> None:
        ticks = iter([0.0] + [5.0] * 50)  # budget almost spent after the start
        with tempfile.TemporaryDirectory() as tmp:
            recall = FakeRecall(provider="", mcp=True)
            doctor = Doctor(
                None,
                Prober(finder=lambda: []),
                home=lambda: Path(tmp),
                monotonic=lambda: next(ticks),
                recall=recall,
            )
            text = doctor.render()
        self.assertIn(
            "⚠  memory: builtin memory (memory.provider: builtin); Engram health not probed", text
        )
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
                "Memory: recall · last #761 saved (hermes-odd, just now) · details: /recall",
            ),
            (
                FakeRecall(mcp=True),
                "Memory: recall · last #761 saved (hermes-odd, just now) · details: /recall",
            ),
            (FakeRecall(last=None), "Memory: recall · last: none yet · details: /recall"),
            (FakeRecall(provider=""), "Memory: builtin (hermes-recall not active)"),
            (FakeRecall(provider="", mcp=True), "Memory: builtin (hermes-recall not active)"),
            (FakeRecall(provider=None), "Memory: unknown"),
        ]
        for recall, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(status_line(recall), expected)
                self.assertEqual(recall.probes, 0)  # /odd-status never probes Engram

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
        calls = []

        def opener(url, timeout):
            calls.append(url)
            return b'{"status":"ok","version":"2.0.0"}'

        config = {"memory": {"provider": "recall"}, "mcp_servers": {}}
        with tempfile.TemporaryDirectory() as tmp:
            recall = Recall(
                home=lambda: Path(tmp), config_source=lambda: config, opener=opener, environ={}
            )
            registry = build_registry(prober=Prober(finder=lambda: []), recall=recall)
            run = {name: registry.get(name).handler for name in ("odd_status", "odd_doctor")}
            self.assertIn(
                "Memory: recall · last: none yet · details: /recall", run["odd_status"]("")
            )
            self.assertIn(
                "✓  memory: recall provider active; last: none yet", run["odd_doctor"]("")
            )
            self.assertEqual(calls, [])  # recall active: hermes-recall owns Engram health
            config.update(memory={"provider": ""}, mcp_servers={"engram": {}})
            for _ in range(2):
                doctor = run["odd_doctor"]("")
                status = run["odd_status"]("")
        self.assertIn(f"; Engram 2.0.0 at {URL}; optional: hermes-recall", doctor)
        self.assertIn("Memory: builtin (hermes-recall not active)", status)
        self.assertEqual(calls, [URL + "/health"])  # doctor only, one shared cached probe


if __name__ == "__main__":
    unittest.main()
