"""The read-only ``recall`` provider view: state file, config, Engram health."""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from fake_context import ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd.recall import (  # noqa: E402
    ENGRAM_DEFAULT_URL,
    HEALTH_TIMEOUT_SECONDS,
    MAX_STATE_BYTES,
    EngramHealth,
    LastMemory,
    Recall,
    RecallInfo,
    age_text,
    engram_health,
    engram_mcp_configured,
    engram_url,
    fetch_health,
    load_global_config,
    provider_of,
    read_state,
)

# The real ``GET /health`` body of the Engram service.
HEALTH_BODY = (
    b'{"instance_id":"55e00f736d404dd6751d949d7f7127c1","service":"engram",'
    b'"status":"ok","version":"2.0.0"}'
)
EPOCH = 1767225600.0  # 2026-01-01T00:00:00+00:00
STATE = {
    "last_memory_id": 42,
    "last_action": "save",
    "project": "hermes-odd",
    "updated_at": "2026-01-01T00:00:00+00:00",
}
RECALL_CONFIG = {"memory": {"provider": "recall"}, "mcp_servers": {"engram": {}}}


class HomeCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def write_state(self, payload=STATE, *, raw: str | None = None) -> Path:
        path = self.home / "recall" / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw if raw is not None else json.dumps(payload), encoding="utf-8")
        return path


class ReadStateTests(HomeCase):
    def test_valid_state_is_parsed(self) -> None:
        self.write_state()
        expected = LastMemory(42, "save", "hermes-odd", STATE["updated_at"])
        self.assertEqual(read_state(self.home), expected)
        self.assertEqual(read_state(str(self.home)), expected)

    def test_extra_keys_are_ignored(self) -> None:
        self.write_state({**STATE, "future": True})
        self.assertEqual(read_state(self.home).memory_id, 42)

    def test_missing_home_or_file_is_none(self) -> None:
        self.assertIsNone(read_state(None))
        self.assertIsNone(read_state(self.home))
        (self.home / "recall" / "state.json").mkdir(parents=True)  # a dir, not a file
        self.assertIsNone(read_state(self.home))

    def test_malformed_content_is_none(self) -> None:
        for raw in ("", "{not json", "[1, 2]", '"text"', "{}"):
            with self.subTest(raw=raw):
                self.write_state(raw=raw)
                self.assertIsNone(read_state(self.home))
        self.write_state().write_bytes(b"\xff\xfe{}")  # not UTF-8
        self.assertIsNone(read_state(self.home))

    def test_wrong_types_or_missing_keys_are_none(self) -> None:
        cases = [
            {"last_memory_id": "42"},
            {"last_memory_id": 4.2},
            {"last_memory_id": True},
            {"last_action": 1},
            {"project": None},
            {"updated_at": 0},
        ]
        for change in cases:
            with self.subTest(change=change):
                self.write_state({**STATE, **change})
                self.assertIsNone(read_state(self.home))
        for key in STATE:
            with self.subTest(missing=key):
                self.write_state({k: v for k, v in STATE.items() if k != key})
                self.assertIsNone(read_state(self.home))

    def test_oversized_file_is_none(self) -> None:
        self.write_state({**STATE, "pad": "x" * MAX_STATE_BYTES})
        self.assertIsNone(read_state(self.home))


class ConfigTests(unittest.TestCase):
    def test_provider_values(self) -> None:
        cases = [
            ({"memory": {"provider": "recall"}}, "recall"),
            ({"memory": {"provider": "  ReCall "}}, "recall"),
            ({"memory": {"provider": "honcho"}}, "honcho"),
            ({"memory": {"provider": ""}}, ""),
            ({"memory": {"provider": None}}, ""),
            ({"memory": {}}, None),
            ({"memory": "recall"}, None),
            ({"memory": {"provider": ["recall"]}}, None),
            ({}, None),
            (None, None),
            ("memory: recall", None),
        ]
        for config, expected in cases:
            with self.subTest(config=config):
                self.assertEqual(provider_of(config), expected)

    def test_engram_mcp_configured(self) -> None:
        cases = [
            ({"mcp_servers": {"engram": {"command": "engram"}}}, True),
            ({"mcp_servers": {"engram": None}}, True),
            ({"mcp_servers": {"github": {}}}, False),
            ({"mcp_servers": ["engram"]}, False),
            ({}, False),
            (None, False),
        ]
        for config, expected in cases:
            with self.subTest(config=config):
                self.assertIs(engram_mcp_configured(config), expected)

    def test_hostile_mapping_never_raises(self) -> None:
        class Hostile(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("boom")

        self.assertIsNone(provider_of(Hostile()))
        self.assertFalse(engram_mcp_configured(Hostile()))

    def test_load_global_config_outside_hermes_is_unknown(self) -> None:
        with mock.patch.dict(sys.modules, {"hermes_cli": None, "hermes_cli.config": None}):
            self.assertIsNone(load_global_config())

    def test_load_global_config_uses_the_hermes_readonly_loader(self) -> None:
        def fake_module(loader) -> types.ModuleType:
            module = types.ModuleType("hermes_cli.config")
            module.load_config_readonly = loader
            return module

        def boom():
            raise OSError("unreadable")

        cases = [(lambda: RECALL_CONFIG, RECALL_CONFIG), (lambda: "junk", None), (boom, None)]
        for loader, expected in cases:
            with self.subTest(expected=expected):
                modules = {"hermes_cli": types.ModuleType("hermes_cli")}
                modules["hermes_cli.config"] = fake_module(loader)
                with mock.patch.dict(sys.modules, modules):
                    self.assertEqual(load_global_config(), expected)


class AgeTextTests(unittest.TestCase):
    def test_buckets(self) -> None:
        cases = [(0, "just now"), (59, "just now"), (180, "3m ago"), (7200, "2h ago")]
        cases += [(5 * 86400 + 10, "5d ago"), (-600, "just now")]
        for offset, expected in cases:
            with self.subTest(offset=offset):
                self.assertEqual(age_text(STATE["updated_at"], EPOCH + offset), expected)

    def test_accepted_formats(self) -> None:
        for stamp in ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00", "2026-01-01T01:00:00+01:00"):
            with self.subTest(stamp=stamp):
                self.assertEqual(age_text(stamp, EPOCH + 120), "2m ago")

    def test_unparsable_is_empty(self) -> None:
        for stamp in ("", "yesterday", None, 123):
            with self.subTest(stamp=stamp):
                self.assertEqual(age_text(stamp, EPOCH), "")
        self.assertEqual(age_text(STATE["updated_at"], "now"), "")
        for now in (float("inf"), float("-inf"), float("nan")):
            self.assertEqual(age_text(STATE["updated_at"], now), "")


class FakeOpener:
    """Records calls; returns ``body`` or raises ``error``."""

    def __init__(self, body: bytes = HEALTH_BODY, error: BaseException | None = None) -> None:
        self.body, self.error, self.calls = body, error, []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self.body


class EngramHealthTests(unittest.TestCase):
    def test_real_body_is_ok_with_version(self) -> None:
        opener = FakeOpener()
        self.assertEqual(
            engram_health(ENGRAM_DEFAULT_URL + "/", opener), EngramHealth(True, "", "2.0.0")
        )
        self.assertEqual(opener.calls, [(ENGRAM_DEFAULT_URL + "/health", HEALTH_TIMEOUT_SECONDS)])
        self.assertLessEqual(HEALTH_TIMEOUT_SECONDS, 1.5)

    def test_bad_bodies(self) -> None:
        cases = [
            (b'{"status":"degraded","version":"2.0.0"}', EngramHealth(False, "not ok", "2.0.0")),
            (b"{}", EngramHealth(False, "not ok")),
            (b"not json", EngramHealth(False, "bad response")),
            (b"[]", EngramHealth(False, "bad response")),
            (b"", EngramHealth(False, "bad response")),
            (None, EngramHealth(False, "bad response")),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                self.assertEqual(engram_health(ENGRAM_DEFAULT_URL, FakeOpener(body)), expected)

    def test_transport_failures_fail_soft(self) -> None:
        cases = [
            (TimeoutError(), "timeout"),
            (urllib.error.URLError(TimeoutError()), "timeout"),
            (urllib.error.URLError(ConnectionRefusedError()), "unreachable"),
            (urllib.error.HTTPError("u", 500, "err", None, None), "bad response"),
            (ConnectionResetError(), "unreachable"),
            (RuntimeError("anything"), "unreachable"),
        ]
        for error, reason in cases:
            with self.subTest(error=error):
                health = engram_health(ENGRAM_DEFAULT_URL, FakeOpener(error=error))
                self.assertEqual(health, EngramHealth(False, reason))

    def test_default_opener_rejects_non_http_urls(self) -> None:
        with self.assertRaises(ValueError):
            fetch_health("file:///etc/hosts", 1.0)
        self.assertEqual(engram_health("ftp://example"), EngramHealth(False, "unreachable"))

    def test_engram_url(self) -> None:
        self.assertEqual(engram_url({}), ENGRAM_DEFAULT_URL)
        self.assertEqual(engram_url({"ENGRAM_URL": "   "}), ENGRAM_DEFAULT_URL)
        self.assertEqual(engram_url({"ENGRAM_URL": " http://h:1/ "}), "http://h:1")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RecallTests(HomeCase):
    def make(self, **kwargs) -> Recall:
        kwargs.setdefault("home", lambda: self.home)
        kwargs.setdefault("config_source", lambda: RECALL_CONFIG)
        kwargs.setdefault("opener", FakeOpener())
        kwargs.setdefault("environ", {})
        return Recall(**kwargs)

    def test_info_snapshot(self) -> None:
        self.write_state()
        info = self.make().info()
        self.assertEqual(info, RecallInfo("recall", True, read_state(self.home)))
        self.assertTrue(info.active)

    def test_inactive_providers(self) -> None:
        for provider in (None, "", "honcho"):
            with self.subTest(provider=provider):
                self.assertFalse(RecallInfo(provider, False, None).active)

    def test_info_fails_soft(self) -> None:
        def boom():
            raise RuntimeError("boom")

        self.write_state()
        self.assertEqual(self.make(home=boom).info(), RecallInfo("recall", True, None))
        unknown = RecallInfo(None, False, read_state(self.home))
        for source in (boom, lambda: 7):
            with self.subTest(source=source):
                self.assertEqual(self.make(config_source=source).info(), unknown)

    def test_default_home_comes_from_soul(self) -> None:
        self.write_state()
        with mock.patch.dict("os.environ", {"HERMES_HOME": str(self.home)}):
            with mock.patch.dict(sys.modules, {"hermes_constants": None}):
                recall = Recall(config_source=lambda: None, opener=FakeOpener())
                self.assertEqual(recall.info().last.memory_id, 42)

    def test_health_is_cached_per_ttl(self) -> None:
        clock, opener = FakeClock(), FakeOpener()
        recall = self.make(clock=clock, opener=opener, ttl=10.0)
        self.assertTrue(recall.health().ok)
        clock.now = 9.9
        recall.health()
        self.assertEqual(recall.probes, 1)
        clock.now = 10.0
        recall.health()
        self.assertEqual(recall.probes, 2)

    def test_health_failure_is_cached_too(self) -> None:
        recall = self.make(opener=FakeOpener(error=TimeoutError()))
        self.assertEqual(recall.health(), EngramHealth(False, "timeout"))
        recall.health()
        self.assertEqual(recall.probes, 1)

    def test_health_uses_engram_url_from_environ(self) -> None:
        opener = FakeOpener()
        self.make(opener=opener, environ={"ENGRAM_URL": "http://h:9"}).health()
        self.assertEqual(opener.calls[0][0], "http://h:9/health")


if __name__ == "__main__":
    unittest.main()
