"""Subagent tracking (hooks + store) and the ``/odd_agents`` viewer."""

from __future__ import annotations

import json
import unittest

from fake_context import BareContext, FakeContext, FakeState, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import agents as agents_mod  # noqa: E402
from hermes_odd import register  # noqa: E402
from hermes_odd.agents import (  # noqa: E402
    SCHEMA,
    STATE_KEY,
    AgentStore,
    MemoryBackend,
    map_child_status,
    resolve_backend,
)
from hermes_odd.commands.agents import OUTPUT_MAX_CHARS, render_list  # noqa: E402

SECRET = "sk-test-FAKE-SECRET-0123456789"
PARENT = "20260924_140000_parent"


class Clock:
    def __init__(self, start: float = 1_790_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def start_kwargs(index: int = 0, hex8: str = "1a2b3c4d", **extra) -> dict:
    kwargs = {
        "parent_session_id": PARENT,
        "parent_turn_id": "turn-1",
        "parent_subagent_id": None,
        "child_session_id": f"child-session-{hex8}",
        "child_subagent_id": f"sa-{index}-{hex8}",
        "child_role": "leaf",
        "child_goal": "Map the auth module and report the login flow",
        "telemetry_schema_version": 1,
    }
    kwargs.update(extra)
    return kwargs


def tool_kwargs(task_id: str, name: str = "read_file", status: str = "ok", **extra) -> dict:
    kwargs = {
        "tool_name": name,
        "args": {"path": "lib/auth.py", "api_key": SECRET},
        "result": json.dumps({"content": f"token={SECRET}"}),
        "task_id": task_id,
        "session_id": "child-session",
        "tool_call_id": "call-1",
        "turn_id": "turn-1",
        "duration_ms": 120,
        "status": status,
        "error_type": "tool_error" if status == "error" else None,
        "error_message": f"failed with {SECRET}" if status == "error" else None,
    }
    kwargs.update(extra)
    return kwargs


def stop_kwargs(hex8: str = "1a2b3c4d", status: str = "completed", **extra) -> dict:
    kwargs = {
        "parent_session_id": PARENT,
        "parent_turn_id": "turn-1",
        "child_session_id": f"child-session-{hex8}",
        "child_role": "leaf",
        "child_summary": "Login goes through auth.login(); sessions live in redis.",
        "child_status": status,
        "tool_call_history": [
            {"tool_name": "read_file", "tool_input": f"path={SECRET}", "status": "ok"}
        ],
        "duration_ms": 95_000,
    }
    kwargs.update(extra)
    return kwargs


class PluginFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = FakeContext()
        register(self.ctx)
        self.handler = self.ctx.commands["odd-agents"]["handler"]

    def stored(self) -> dict:
        return self.ctx.state.get(STATE_KEY)


class LifecycleTests(PluginFixture):
    def test_start_tool_calls_stop_via_kwargs(self) -> None:
        self.ctx.fire("on_session_start", session_id=PARENT, model="m", platform="telegram")
        self.ctx.fire("subagent_start", **start_kwargs())
        record = self.stored()["records"][0]
        self.assertEqual(self.stored()["schema"], SCHEMA)
        self.assertEqual(record["status"], "running")
        self.assertEqual(record["platform"], "telegram")
        self.assertEqual(record["subagent_id"], "sa-0-1a2b3c4d")

        self.ctx.fire("post_tool_call", **tool_kwargs("sa-0-1a2b3c4d"))
        self.ctx.fire("post_tool_call", **tool_kwargs("sa-0-1a2b3c4d", "patch", status="error"))
        record = self.stored()["records"][0]
        self.assertEqual(record["tool_calls"], 2)
        self.assertEqual(record["last_tool"], {"name": "patch", "status": "error"})
        self.assertEqual([e["tool"] for e in record["timeline"]], ["read_file", "patch"])

        running = self.handler("")
        self.assertIn("● 1a2b3c4d leaf", running)
        self.assertIn("last: patch error · 2 tools", running)
        self.assertIn("1 running · 0 finished", running)

        self.ctx.fire("subagent_stop", **stop_kwargs())
        record = self.stored()["records"][0]
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["duration_ms"], 95_000)
        self.assertEqual(record["tool_calls"], 2)  # live count kept over history
        self.assertIn("auth.login()", record["summary"])
        self.assertIn("✓ 1a2b3c4d leaf · 1m35s", self.handler(""))

        # Tool calls after stop are ignored (child no longer active).
        self.ctx.fire("post_tool_call", **tool_kwargs("sa-0-1a2b3c4d"))
        self.assertEqual(self.stored()["records"][0]["tool_calls"], 2)

    def test_stop_correlates_by_child_session_id(self) -> None:
        self.ctx.fire("subagent_start", **start_kwargs(0, "aaaa1111"))
        self.ctx.fire("subagent_start", **start_kwargs(1, "bbbb2222"))
        self.ctx.fire("subagent_stop", **stop_kwargs("bbbb2222", status="timeout"))
        by_id = {r["subagent_id"]: r for r in self.stored()["records"]}
        self.assertEqual(by_id["sa-0-aaaa1111"]["status"], "running")
        self.assertEqual(by_id["sa-1-bbbb2222"]["status"], "timed_out")
        self.assertIn("timeout", by_id["sa-1-bbbb2222"]["error"])

    def test_unknown_task_id_is_ignored_without_io(self) -> None:
        self.ctx.fire("subagent_start", **start_kwargs())
        sets = self.ctx.state.sets
        self.ctx.fire("post_tool_call", **tool_kwargs("parent-task-uuid"))
        self.ctx.fire("post_tool_call", **tool_kwargs(""))
        self.assertEqual(self.ctx.state.sets, sets)
        self.assertEqual(self.stored()["records"][0]["tool_calls"], 0)

    def test_stop_without_start_backfills_from_metadata_history(self) -> None:
        self.ctx.fire("subagent_stop", **stop_kwargs("cccc3333", status="failed"))
        record = self.stored()["records"][0]
        self.assertTrue(record["subagent_id"].startswith("sx-"))
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["tool_calls"], 1)
        self.assertEqual(record["timeline"][0]["tool"], "read_file")

    def test_child_status_mapping(self) -> None:
        cases = {
            "completed": "completed",
            "failed": "failed",
            "error": "failed",
            "interrupted": "interrupted",
            "timeout": "timed_out",
            "weird": "failed",
            None: "failed",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(map_child_status(raw), expected)

    def test_nested_child_inherits_platform(self) -> None:
        self.ctx.fire("on_session_start", session_id=PARENT, platform="telegram")
        self.ctx.fire("subagent_start", **start_kwargs(0, "aaaa1111"))
        self.ctx.fire(
            "subagent_start",
            **start_kwargs(
                0,
                "dddd4444",
                parent_session_id="child-session-aaaa1111",
                parent_subagent_id="sa-0-aaaa1111",
                child_role="orchestrator",
            ),
        )
        by_id = {r["subagent_id"]: r for r in self.stored()["records"]}
        self.assertEqual(by_id["sa-0-dddd4444"]["platform"], "telegram")


class PrivacyTests(PluginFixture):
    def test_args_results_and_errors_never_stored_or_shown(self) -> None:
        self.ctx.fire("subagent_start", **start_kwargs())
        self.ctx.fire("post_tool_call", **tool_kwargs("sa-0-1a2b3c4d"))
        self.ctx.fire("post_tool_call", **tool_kwargs("sa-0-1a2b3c4d", status="error"))
        self.ctx.fire("subagent_stop", **stop_kwargs(tool_call_history=[{"tool_input": SECRET}]))
        self.assertNotIn(SECRET, self.ctx.state.dump())
        self.assertNotIn("lib/auth.py", self.ctx.state.dump())
        for args in ("", "all", "1a2b", "sa-0"):
            with self.subTest(args=args):
                self.assertNotIn(SECRET, self.handler(args))

    def test_goal_and_summary_are_truncated(self) -> None:
        self.ctx.fire("subagent_start", **start_kwargs(child_goal="g" * 1000))
        self.ctx.fire("subagent_stop", **stop_kwargs(child_summary="s" * 5000))
        record = self.stored()["records"][0]
        self.assertLessEqual(len(record["goal"]), agents_mod.GOAL_MAX_CHARS)
        self.assertLessEqual(len(record["summary"]), agents_mod.SUMMARY_MAX_CHARS)


class RetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.state = FakeState()
        self.store = AgentStore(self.state, clock=self.clock)

    def start(self, i: int) -> str:
        hex8 = f"{i:08x}"
        self.store.on_subagent_start(**start_kwargs(i, hex8))
        return hex8

    def test_timeline_is_bounded(self) -> None:
        self.start(1)
        for n in range(40):
            self.store.on_post_tool_call(**tool_kwargs("sa-1-00000001", f"tool_{n}"))
        record = self.store.records()[0]
        self.assertEqual(record["tool_calls"], 40)
        self.assertEqual(len(record["timeline"]), agents_mod.MAX_TIMELINE)
        self.assertEqual(record["timeline"][-1]["tool"], "tool_39")

    def test_at_most_50_records_oldest_finished_dropped_first(self) -> None:
        running = self.start(0)
        for i in range(1, 60):
            hex8 = self.start(i)
            self.store.on_subagent_stop(**stop_kwargs(hex8))
            self.clock.advance(1)
        records = self.store.records()
        self.assertEqual(len(records), agents_mod.MAX_RECORDS)
        ids = {r["subagent_id"] for r in records}
        self.assertIn(f"sa-0-{running}", ids)
        self.assertNotIn("sa-1-00000001", ids)
        self.assertIn("sa-59-0000003b", ids)

    def test_finished_records_pruned_after_24h(self) -> None:
        hex8 = self.start(1)
        self.store.on_subagent_stop(**stop_kwargs(hex8))
        self.clock.advance(23 * 3600)
        self.assertEqual(len(self.store.records()), 1)
        self.clock.advance(2 * 3600)
        self.assertEqual(self.store.records(), [])

    def test_stuck_running_marked_stale_not_deleted(self) -> None:
        self.start(1)
        self.clock.advance(7 * 3600)
        records = self.store.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "stale")
        self.assertIn("stale", records[0]["error"])
        self.assertIn("○ 00000001", render_list(records, self.clock()))

    def test_running_first_then_newest(self) -> None:
        old = self.start(1)
        self.clock.advance(10)
        self.start(2)
        self.clock.advance(10)
        newest = self.start(3)
        self.store.on_subagent_stop(**stop_kwargs(newest))
        self.store.on_subagent_stop(**stop_kwargs(old))
        order = [r["subagent_id"] for r in self.store.records()]
        self.assertEqual(order, ["sa-2-00000002", "sa-3-00000003", "sa-1-00000001"])

    def test_state_is_shared_between_store_instances(self) -> None:
        self.start(1)
        other = AgentStore(self.state, clock=self.clock)
        self.assertEqual(other.records()[0]["subagent_id"], "sa-1-00000001")


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.store = AgentStore(FakeState(), clock=self.clock)
        from hermes_odd.commands import build_registry

        self.handler = build_registry(self.store).get("odd_agents").handler

    def add(self, i: int, hex8: str, goal: str = "Do a thing", summary: str = "ok") -> None:
        self.store.on_subagent_start(**start_kwargs(i, hex8, child_goal=goal))
        self.store.on_subagent_stop(**stop_kwargs(hex8, child_summary=summary))

    def test_empty_state_text(self) -> None:
        text = self.handler("")
        self.assertIn("No subagents recorded yet", text)
        self.assertIn("delegate_task", text)
        self.assertEqual(self.handler("all"), text)

    def test_detail_by_prefix(self) -> None:
        self.add(0, "1a2b3c4d", summary="Found the login flow.")
        self.add(1, "9f8e7d6c")
        for prefix in ("1a2b", "sa-0-1a", "SA-0-1A2B3C4D", "1a2b3c4d"):
            with self.subTest(prefix=prefix):
                detail = self.handler(prefix)
                self.assertIn("sa-0-1a2b3c4d · completed", detail)
                self.assertIn("goal: Do a thing", detail)
                self.assertIn(f"parent session: {PARENT}", detail)
                self.assertIn("summary:\nFound the login flow.", detail)

    def test_ambiguous_and_not_found(self) -> None:
        self.add(0, "abcd0001")
        self.add(1, "abcd0002")
        ambiguous = self.handler("abcd")
        self.assertIn("ambiguous", ambiguous)
        self.assertIn("abcd0001", ambiguous)
        self.assertIn("abcd0002", ambiguous)
        self.assertIn("No subagent matches 'zzzz'", self.handler("zzzz"))

    def test_list_caps_at_ten_with_more_marker(self) -> None:
        for i in range(14):
            self.add(i, f"{i:08x}")
            self.clock.advance(1)
        text = self.handler("")
        self.assertEqual(text.count("\n  last: "), 10)
        self.assertIn("… 4 more (/odd_agents all)", text)
        self.assertIn("0 running · 14 finished", text)
        self.assertEqual(self.handler("all").count("✓ "), 14)

    def test_output_length_cap(self) -> None:
        for i in range(50):
            self.add(i, f"{i:08x}", goal="x" * 500, summary="y" * 5000)
        for args in ("", "all", "00000001"):
            with self.subTest(args=args):
                self.assertLessEqual(len(self.handler(args)), OUTPUT_MAX_CHARS)
        self.assertIn("more", self.handler("all"))

    def test_plain_text_no_markdown(self) -> None:
        self.add(0, "1a2b3c4d")
        for args in ("", "all", "1a2b"):
            text = self.handler(args)
            for token in ("|", "**", "```", "<"):
                self.assertNotIn(token, text)

    def test_stop_is_explained_not_executed(self) -> None:
        text = self.handler("stop 1a2b")
        self.assertIn("not available", text)
        self.assertIn("delegate_task action=stop", text)


class RobustnessTests(unittest.TestCase):
    def test_handlers_never_raise_on_malformed_kwargs(self) -> None:
        store = AgentStore(FakeState())
        junk = [
            {},
            {"child_subagent_id": 5, "child_session_id": ["x"]},
            {"child_subagent_id": "sa-0-x", "child_goal": object(), "child_role": 3},
            {"task_id": None, "tool_name": None, "duration_ms": "fast"},
            {"child_session_id": "c", "duration_ms": float("nan"), "tool_call_history": "x"},
            {"child_session_id": "c", "tool_call_history": [1, None, {"status": 3}]},
            {"session_id": 1, "platform": {}},
        ]
        for kwargs in junk:
            store.on_session_start(**kwargs)
            store.on_subagent_start(**kwargs)
            store.on_post_tool_call(**kwargs)
            store.on_subagent_stop(**kwargs)
        store.records()

    def test_failing_state_falls_back_to_memory(self) -> None:
        class Broken:
            def get(self, key, default=None):
                raise RuntimeError("corrupt")

            def set(self, key, value):
                raise ValueError("quota")

        store = AgentStore(Broken())
        with self.assertLogs("hermes_odd", level="WARNING"):
            store.on_subagent_start(**start_kwargs())
        self.assertEqual(store.records()[0]["subagent_id"], "sa-0-1a2b3c4d")

    def test_corrupt_document_is_ignored(self) -> None:
        state = FakeState()
        state.set(STATE_KEY, {"schema": "other", "records": [{"x": 1}]})
        self.assertEqual(AgentStore(state).records(), [])

    def test_backend_resolution(self) -> None:
        ctx = FakeContext()
        self.assertIs(resolve_backend(ctx), ctx.state)
        with self.assertLogs("hermes_odd", level="WARNING"):
            self.assertIsInstance(resolve_backend(BareContext()), MemoryBackend)

    def test_bare_context_registers_without_hooks(self) -> None:
        with self.assertLogs("hermes_odd", level="WARNING"):
            register(BareContext())


class CommandListingTests(unittest.TestCase):
    def test_odd_agents_is_listed_in_odd_commands(self) -> None:
        ctx = FakeContext()
        register(ctx)
        self.assertIn("odd-agents", ctx.commands)
        self.assertEqual(ctx.commands["odd-agents"]["args_hint"], "[id|all]")
        listing = ctx.commands["odd-commands"]["handler"]("")
        self.assertIn("/odd_agents [id|all]", listing)


if __name__ == "__main__":
    unittest.main()
