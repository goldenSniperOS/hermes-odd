"""``/odd_status``, ``/odd_doctor``, their probes and the SOUL.md truncation math."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import FakeContext, FakeState, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import __version__, register  # noqa: E402
from hermes_odd import soul as soul_mod  # noqa: E402
from hermes_odd.agents import AgentStore  # noqa: E402
from hermes_odd.changes import ChangeStore, FileOp  # noqa: E402
from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.commands.doctor import (  # noqa: E402
    BINARY_RULE,
    FAIL,
    OK,
    OUTPUT_MAX_CHARS,
    WARN,
    Doctor,
    check_binary,
    check_hermes,
    check_lock,
    check_plugin,
    check_review_mode,
    check_soul,
    display_path,
    probe_state,
)
from hermes_odd.commands.status import OUTPUT_MAX_CHARS as STATUS_MAX_CHARS  # noqa: E402
from hermes_odd.commands.status import Status  # noqa: E402
from hermes_odd.probes import (  # noqa: E402
    BinaryInfo,
    Prober,
    ProbeResult,
    ReviewMode,
    find_binaries,
    is_below,
    parse_version,
    probe_env,
    run_probe,
)
from hermes_odd.runtime import RuntimeInfo  # noqa: E402
from hermes_odd.upstream import load_lock  # noqa: E402

HOME = os.path.expanduser("~")
FAKE_SECRET = "sk-doctor-FAKE-SECRET-not-real"
REVIEW_JSON = (
    '{"schema": "gentle-ai.review-mode/v1", "operation": "status", "status": '
    '{"schema": "gentle-ai.rdd-mode-status/v1", "global": "on", "clone_local": "", '
    '"effective": "on", "source": "global"}}'
)

UNSUPPORTED_JSON = (
    '{"schema": "gentle-ai.review-integration.failure/v2", "contract": '
    '"gentle-ai.review-integration/v2", "operation": "review.status", "phase": "preflight", '
    '"code": "immutable_review_transport_unsupported", "next_action": "stop", "cause": '
    '"the active runtime is not eligible for immutable receipt review; exit receipt-driven '
    "review with `gentle-ai review mode disable --scope clone --cwd \\u003crepo\\u003e`; "
    'supported immutable review runtimes: claude-code, opencode, codex, pi"}'
)
NATIVE_LINE = (
    "Native review on Hermes: unavailable — gentle-ai 3.7.0 advertises immutable review "
    "only for claude-code, opencode, codex, pi"
)


class FakeRunner:
    """Maps a binary path to its ``version`` stdout; records every command."""

    def __init__(
        self, versions=None, review=REVIEW_JSON, review_state="ok", native=None, native_state=None
    ):
        self.versions = versions or {}
        self.review = review
        self.review_state = review_state
        self.native = UNSUPPORTED_JSON if native is None else native
        self.native_state = native_state or "failed"
        self.commands: list[list[str]] = []

    def __call__(self, command, timeout):
        self.commands.append(list(command))
        if command[1:] == ["version"]:
            value = self.versions.get(command[0])
            if isinstance(value, ProbeResult):
                return value
            return ProbeResult("ok", value or "", 0) if value is not None else ProbeResult("failed")
        if command[1:4] == ["review", "mode", "status"]:
            return ProbeResult(self.review_state, self.review, 0)
        if command[1:3] == ["review", "status"]:
            assert command[command.index("--agent") + 1] == "hermes", command
            return ProbeResult(self.native_state, self.native, 1)
        raise AssertionError(f"unexpected command {command}")


def prober_for(paths, versions, **kwargs) -> Prober:
    return Prober(runner=FakeRunner(versions, **kwargs), finder=lambda: list(paths))


class VersionParsingTests(unittest.TestCase):
    def test_parse_and_compare(self) -> None:
        self.assertEqual(parse_version("gentle-ai 3.7.0\n"), (3, 7, 0))
        self.assertEqual(parse_version("gentle-ai v3.10.2-rc.1"), (3, 10, 2))
        self.assertIsNone(parse_version("gentle-ai dev"))
        self.assertTrue(is_below("3.3.0", "3.7.0"))
        self.assertFalse(is_below("3.10.0", "3.7.0"))
        self.assertFalse(is_below("3.7.0", "3.7.0"))
        self.assertIsNone(is_below(None, "3.7.0"))

    def test_probe_env_is_minimal(self) -> None:
        env = probe_env({"PATH": "/bin", "HOME": "/h", "AWS_SECRET": FAKE_SECRET, "X": "y"})
        self.assertEqual(env, {"PATH": "/bin", "HOME": "/h", "LC_ALL": "C", "NO_COLOR": "1"})

    def test_run_probe_uses_no_shell_and_a_timeout(self) -> None:
        completed = subprocess.CompletedProcess(["x"], 0, "gentle-ai 3.7.0\n", "")
        with mock.patch("subprocess.run", return_value=completed) as run:
            result = run_probe(["/bin/gentle-ai", "version"], 3.0)
        self.assertEqual(result, ProbeResult("ok", "gentle-ai 3.7.0\n", 0))
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 3.0)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("AWS_PROFILE", kwargs["env"])

    def test_run_probe_timeout_and_missing(self) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 3)):
            self.assertEqual(run_probe(["x", "version"], 3).state, "timeout")
        with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            self.assertEqual(run_probe(["x", "version"], 3).state, "missing")
        with mock.patch("subprocess.run", side_effect=PermissionError()):
            self.assertEqual(run_probe(["x", "version"], 3).state, "failed")


class FindBinariesTests(unittest.TestCase):
    def test_scans_path_dedupes_and_keeps_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second, link_dir = root / "a", root / "b", root / "c"
            for d in (first, second, link_dir):
                d.mkdir()
            for d in (first, second):
                exe = d / "gentle-ai"
                exe.write_text("#!/bin/sh\n")
                exe.chmod(0o755)
            (link_dir / "gentle-ai").symlink_to(second / "gentle-ai")
            path = os.pathsep.join([str(first), str(second), str(link_dir), str(root / "none")])
            found = find_binaries({"PATH": path})
        self.assertEqual(found, [str(first / "gentle-ai"), str(second / "gentle-ai")])

    def test_empty_path(self) -> None:
        self.assertEqual(find_binaries({"PATH": ""}, which=lambda *a, **k: None), [])


class BinaryCheckTests(unittest.TestCase):
    def test_current_binary_passes(self) -> None:
        prober = prober_for(
            ["/opt/homebrew/bin/gentle-ai"], {"/opt/homebrew/bin/gentle-ai": "gentle-ai 3.7.1"}
        )
        check, first = check_binary(prober, "3.7.0", 3.0)
        self.assertEqual(check.level, OK)
        self.assertEqual(first.version, "3.7.1")
        self.assertIn("3.7.1 at …/homebrew/bin/gentle-ai (min 3.7.0)", check.finding)

    def test_below_min_fails_with_binary_only_hint(self) -> None:
        go = f"{HOME}/go/bin/gentle-ai"
        prober = prober_for([go], {go: "gentle-ai 3.3.0"})
        check, _ = check_binary(prober, "3.7.0", 3.0)
        self.assertEqual(check.level, FAIL)
        self.assertIn("brew upgrade gentleman-programming/tap/gentle-ai", check.hint)
        self.assertIn(BINARY_RULE, check.hint)
        self.assertIn("~/go/bin/gentle-ai", check.finding)
        self.assertNotIn(HOME, check.render())

    def test_stale_binary_shadowing_a_newer_one(self) -> None:
        go, brew = f"{HOME}/go/bin/gentle-ai", "/opt/homebrew/bin/gentle-ai"
        prober = prober_for([go, brew], {go: "gentle-ai 3.3.0", brew: "gentle-ai 3.7.0"})
        check, first = check_binary(prober, "3.7.0", 3.0)
        self.assertEqual(check.level, FAIL)  # the first on PATH is what runs
        self.assertEqual(first.path, go)
        self.assertIn("also on PATH: …/homebrew/bin/gentle-ai 3.7.0", check.finding)
        self.assertIn("shadows a newer 3.7.0", check.hint)
        self.assertIn("never run `gentle-ai install`", check.hint)

    def test_multiple_differing_binaries_warn(self) -> None:
        a, b = "/usr/local/bin/gentle-ai", "/opt/homebrew/bin/gentle-ai"
        prober = prober_for([a, b], {a: "gentle-ai 3.8.0", b: "gentle-ai 3.7.0"})
        check, _ = check_binary(prober, "3.7.0", 3.0)
        self.assertEqual(check.level, WARN)
        self.assertIn("keep one", check.hint)

    def test_timeout_and_missing(self) -> None:
        a = "/usr/local/bin/gentle-ai"
        prober = prober_for([a], {a: ProbeResult("timeout")})
        check, _ = check_binary(prober, "3.7.0", 3.0)
        self.assertEqual(check.level, WARN)
        self.assertIn("version timed out", check.finding)
        check, first = check_binary(prober_for([], {}), "3.7.0", 3.0)
        self.assertEqual(check.level, FAIL)
        self.assertIsNone(first)
        self.assertIn("not found on PATH", check.finding)
        self.assertIn(BINARY_RULE, check.hint)


class CachingTests(unittest.TestCase):
    def test_probes_are_cached_for_60_seconds(self) -> None:
        now = [100.0]
        runner = FakeRunner({"/x/gentle-ai": "gentle-ai 3.7.0"})
        prober = Prober(runner=runner, clock=lambda: now[0], finder=lambda: ["/x/gentle-ai"])
        prober.first_version()
        prober.first_version()
        self.assertEqual(len(runner.commands), 1)
        now[0] += 59
        prober.first_version()
        self.assertEqual(len(runner.commands), 1)
        now[0] += 2
        prober.first_version()
        self.assertEqual(len(runner.commands), 2)

    def test_review_mode_cache_is_visible_to_status(self) -> None:
        now = [0.0]
        prober = Prober(runner=FakeRunner(), clock=lambda: now[0], finder=lambda: [])
        repo = Path("/work/repo")
        self.assertIsNone(prober.cached_review_mode(repo))
        prober.review_mode("/x/gentle-ai", repo)
        self.assertEqual(prober.cached_review_mode(repo).effective, "on")
        now[0] += 61
        self.assertIsNone(prober.cached_review_mode(repo))


class ReviewModeTests(unittest.TestCase):
    binary = BinaryInfo("/x/gentle-ai", "3.7.0", "ok")

    def test_on_reports_source_and_uses_read_only_flags(self) -> None:
        runner = FakeRunner()
        prober = Prober(runner=runner, finder=lambda: [])
        check = check_review_mode(prober, self.binary, Path("/work/myrepo"), 3.0)
        self.assertEqual(check.level, OK)
        self.assertIn("receipt-driven development on (decided by global) · myrepo", check.finding)
        self.assertEqual(
            runner.commands[0],
            ["/x/gentle-ai", "review", "mode", "status", "--cwd", "/work/myrepo", "--json"],
        )

    def test_unknown_states(self) -> None:
        prober = Prober(runner=FakeRunner(), finder=lambda: [])
        self.assertIn(
            "not in a git repository", check_review_mode(prober, self.binary, None, 3).finding
        )
        self.assertIn("gentle-ai missing", check_review_mode(prober, None, Path("/r"), 3).finding)
        bad = Prober(runner=FakeRunner(review="not json"), finder=lambda: [])
        self.assertEqual(check_review_mode(bad, self.binary, Path("/r"), 3).level, WARN)
        slow = Prober(runner=FakeRunner(review_state="timeout"), finder=lambda: [])
        self.assertIn("timed out", check_review_mode(slow, self.binary, Path("/r"), 3).finding)
        self.assertIn("time budget", check_review_mode(prober, self.binary, Path("/r"), 0).finding)


def synthetic_soul(sizes: dict[str, int], preamble: int = 500, trailer: int = 0) -> str:
    parts = ["# Soul\n" + "p" * preamble]
    for name, size in sizes.items():
        parts.append(f"<!-- gentle-ai:{name} -->\n" + "x" * size + f"\n<!-- /gentle-ai:{name} -->")
    parts.append("closing words" + "t" * trailer)
    return "\n".join(parts)


class SoulMathTests(unittest.TestCase):
    def test_cap_matches_hermes_constants(self) -> None:
        self.assertEqual(soul_mod.truncation_cap(None), 20_000)
        self.assertEqual(soul_mod.truncation_cap(50_000), 20_000)  # floor
        self.assertEqual(soul_mod.truncation_cap(128_000), 30_720)
        self.assertEqual(soul_mod.truncation_cap(200_000), 48_000)
        self.assertEqual(soul_mod.truncation_cap(1_000_000), 240_000)
        self.assertEqual(soul_mod.truncation_cap(10_000_000), 500_000)  # ceiling
        self.assertEqual(soul_mod.truncation_cap(128_000, pinned=90_000), 90_000)

    def test_kept_ranges_70_20(self) -> None:
        self.assertIsNone(soul_mod.kept_ranges(30_000, 30_720))
        self.assertEqual(soul_mod.kept_ranges(88_483, 30_720), (21_504, 88_483 - 6_144))

    def test_blocks_nested_unclosed_and_dropped(self) -> None:
        text = (
            "a" * 100
            + "<!-- gentle-ai:persona -->"
            + "b" * 50
            + "<!-- /gentle-ai:persona -->"
            + "<!-- gentle-ai:outer --><!-- gentle-ai:inner -->c<!-- /gentle-ai:inner -->"
            + "d" * 30_000
            + "<!-- /gentle-ai:outer -->"
            + "<!-- gentle-ai:tail -->"
            + "e" * 10
        )
        blocks = soul_mod.parse_blocks(text)
        names = [(b.name, b.depth, b.closed) for b in blocks]
        self.assertEqual(
            names,
            [("persona", 0, True), ("outer", 0, True), ("inner", 1, True), ("tail", 0, False)],
        )
        lost = soul_mod.dropped_blocks(blocks, len(text), 20_000)
        self.assertEqual([(b.name, how) for b, how in lost], [("outer", "partly")])

    def test_block_entirely_in_the_middle_is_dropped(self) -> None:
        text = synthetic_soul({"persona": 1_000, "big": 60_000, "routing": 5_000}, trailer=7_000)
        report = soul_mod.analyze_text(text, Path("/h/SOUL.md"))
        lost = dict(
            (b.name, how) for b, how in soul_mod.dropped_blocks(report.blocks, report.chars, 30_720)
        )
        self.assertEqual(lost, {"big": "partly", "routing": "dropped"})
        self.assertNotIn("persona", lost)  # in the kept head
        tail = synthetic_soul({"persona": 1_000, "big": 60_000, "end": 3_000})
        report = soul_mod.analyze_text(tail, Path("/h/SOUL.md"))
        names = [b.name for b, _ in soul_mod.dropped_blocks(report.blocks, report.chars, 30_720)]
        self.assertNotIn("end", names)  # in the kept tail

    def test_bom_and_whitespace_are_not_counted(self) -> None:
        report = soul_mod.analyze_text("\n\ufeffabc  \n", Path("/h/SOUL.md"))
        self.assertEqual(report.chars, 3)


class ModelContextTests(unittest.TestCase):
    def test_reads_only_model_keys_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.yaml").write_text(
                "model:\n  default: global.x-model\n  provider: bedrock\n"
                "  base_url: https://example.invalid/\n  api_key: " + FAKE_SECRET + "\n"
                "other:\n  default: nope\n",
                encoding="utf-8",
            )
            (home / "context_length_cache.yaml").write_text(
                "context_lengths:\n  global.x-model@https://example.invalid: 200000\n"
                "  us.y-model:0@https://example.invalid: 128000\n",
                encoding="utf-8",
            )
            ctx = soul_mod.model_context(home)
            self.assertEqual(
                (ctx.model, ctx.context_length, ctx.source), ("global.x-model", 200_000, "cache")
            )
            (home / "config.yaml").write_text(
                "model: plain-model\ncontext_file_max_chars: 70000\n", encoding="utf-8"
            )
            ctx = soul_mod.model_context(home)
            self.assertEqual(
                (ctx.model, ctx.context_length, ctx.pinned_cap), ("plain-model", None, 70_000)
            )
            (home / "config.yaml").write_text("model:\n  context_length: 64000\n", encoding="utf-8")
            self.assertEqual(soul_mod.model_context(home).context_length, 64_000)
            self.assertEqual(soul_mod.model_context(home / "missing"), soul_mod.ModelContext())

    def test_hermes_home_resolution(self) -> None:
        with mock.patch.dict("sys.modules", {"hermes_constants": None}):
            self.assertEqual(soul_mod.hermes_home({"HERMES_HOME": "/p/home"}), Path("/p/home"))
            self.assertEqual(soul_mod.hermes_home({}), Path.home() / ".hermes")


class SoulCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, text: str) -> None:
        (self.home / "SOUL.md").write_text(text, encoding="utf-8")

    def test_no_soul_passes(self) -> None:
        check = check_soul(self.home, soul_mod.ModelContext())
        self.assertEqual(check.level, OK)
        self.assertIn("none at", check.finding)

    def test_truncated_soul_names_lost_blocks(self) -> None:
        self.write(
            synthetic_soul({"persona": 1_000, "big": 60_000, "routing": 5_000, "end": 4_000})
            + FAKE_SECRET
        )
        check = check_soul(self.home, soul_mod.ModelContext("m", 128_000, "cache"))
        self.assertEqual(check.level, WARN)
        self.assertIn(
            "Cap 30,720 (m 128k (cache)): truncated, loses big (partly), routing", check.finding
        )
        self.assertIn("4 gentle-ai blocks", check.finding)
        self.assertIn("T9", check.hint)
        self.assertIn("/odd_soul", check.hint)
        self.assertNotIn(FAKE_SECRET, check.render())
        self.assertNotIn("xxxx", check.render())

    def test_unknown_context_shows_cap_table(self) -> None:
        self.write(synthetic_soul({"big": 60_000}))
        check = check_soul(self.home, soul_mod.ModelContext())
        self.assertIn("128k 30,720 ✗ | 200k 48,000 ✗ | 1M 240,000 ✓", check.finding)
        self.assertIn("at 128k loses big", check.finding)
        self.assertEqual(check.level, WARN)

    def test_fitting_soul_without_blocks_passes(self) -> None:
        self.write("be kind\n")
        check = check_soul(self.home, soul_mod.ModelContext("m", 1_000_000, "config"))
        self.assertEqual(check.level, OK)
        self.assertIn("fits", check.finding)

    def test_fitting_soul_with_blocks_warns(self) -> None:
        self.write(synthetic_soul({"persona": 1_000}))
        check = check_soul(self.home, soul_mod.ModelContext("m", 1_000_000, "config"))
        self.assertEqual(check.level, WARN)
        self.assertIn("sent with every message", check.finding)


class BrokenState:
    def get(self, key, default=None):
        raise RuntimeError("corrupt")

    def set(self, key, value):
        raise RuntimeError("corrupt")


class PluginCheckTests(unittest.TestCase):
    def test_state_probe_writes_reads_and_restores(self) -> None:
        ctx = FakeContext()
        ctx.state.set("doctor.probe", {"old": 1})
        self.assertEqual(probe_state(ctx), "ok")
        self.assertEqual(ctx.state.get("doctor.probe"), {"old": 1})

    def test_state_probe_fallbacks(self) -> None:
        self.assertEqual(probe_state(object()), "memory")
        ctx = FakeContext()
        ctx.state = BrokenState()
        self.assertEqual(probe_state(ctx), "failed: RuntimeError")

    def test_registered_plugin_passes(self) -> None:
        ctx = FakeContext()
        register(ctx)
        runtime = _runtime_of(ctx)
        check = check_plugin(runtime)
        self.assertEqual(check.level, OK, check.finding)
        self.assertIn("section hermes-odd-workflow", check.finding)
        self.assertIn("(all plugins share 8000)", check.finding)
        self.assertIn("skills 5 (clone)", check.finding)
        self.assertIn("hooks 5/5", check.finding)
        self.assertIn("state ok", check.finding)

    def test_memory_fallback_is_reported(self) -> None:
        store = AgentStore(BrokenState())
        store.records()
        runtime = RuntimeInfo(
            ctx=object(),
            section_registered=True,
            section_chars=100,
            skills=["a"],
            hooks_expected=5,
            hooks_registered=5,
            stores={"agents": store},
        )
        check = check_plugin(runtime)
        self.assertEqual(check.level, WARN)
        self.assertIn("state in memory", check.finding)
        self.assertIn("memory fallback active for agents", check.finding)

    def test_missing_section_fails(self) -> None:
        check = check_plugin(RuntimeInfo(skills=["a"], hooks_expected=1, hooks_registered=1))
        self.assertEqual(check.level, FAIL)


class LockAndHermesTests(unittest.TestCase):
    def test_lock_ok_and_stale(self) -> None:
        lock = load_lock()
        now = 1_790_000_000.0  # 2026-09-21T...
        check, data = check_lock(lambda: lock, now)
        self.assertIsNotNone(data)
        self.assertIn("gentle-ai v3.7.0 @f182ea2 · gentle-shell v3.7.0 @4d702a4", check.finding)
        check, _ = check_lock(lambda: lock, now + 90 * 86400)
        self.assertEqual(check.level, WARN)
        self.assertIn("upstream/SUPPORTED.md", check.hint)

    def test_lock_missing_or_invalid(self) -> None:
        def missing():
            raise FileNotFoundError("gone")

        def invalid():
            raise ValueError("schema")

        self.assertEqual(check_lock(missing, 0)[0].level, FAIL)
        self.assertEqual(check_lock(invalid, 0)[0].level, FAIL)

    def test_hermes_version_and_enabled(self) -> None:
        ctx = FakeContext()
        ctx.plugin_id = "hermes-odd"
        ctx.has_plugin = lambda name: name == "hermes-odd"
        check = check_hermes(RuntimeInfo(ctx=ctx), lambda: "0.21.0")
        self.assertIn("Hermes 0.21.0; hermes-odd", check.finding)
        self.assertIn("enabled", check.finding)
        ctx.has_plugin = lambda name: False
        self.assertEqual(check_hermes(RuntimeInfo(ctx=ctx), lambda: None).level, WARN)


def _runtime_of(ctx: FakeContext) -> RuntimeInfo:
    status = ctx.commands["odd-status"]["handler"]
    # The status closure holds the Status; reach the runtime through it.
    for cell in status.__closure__ or []:
        spec = cell.cell_contents
        handler = getattr(spec, "handler", None)
        for inner in getattr(handler, "__closure__", None) or []:
            value = inner.cell_contents
            if isinstance(value, Status):
                return value.runtime
    raise AssertionError("runtime not found")


def make_doctor(tmp: Path, runtime=None, versions=None, repo=None, soul: str | None = None):
    if soul is not None:
        (tmp / "SOUL.md").write_text(soul, encoding="utf-8")
    go = f"{HOME}/go/bin/gentle-ai"
    prober = prober_for([go], versions if versions is not None else {go: "gentle-ai 3.3.0"})
    return Doctor(
        runtime,
        prober,
        home=lambda: tmp,
        repo=lambda: repo,
        version_of=lambda: "0.21.0",
        model_context=lambda home: soul_mod.ModelContext("m", 200_000, "cache"),
    )


class DoctorReportTests(unittest.TestCase):
    def test_full_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = FakeContext()
            register(ctx)
            repo = Path(tmp) / "proj"
            (repo / ".git").mkdir(parents=True)
            doctor = make_doctor(
                Path(tmp),
                _runtime_of(ctx),
                versions={f"{HOME}/go/bin/gentle-ai": "gentle-ai 3.7.0"},
                repo=repo,
                soul=synthetic_soul({"persona": 1_000, "sdd-thing": 60_000}),
            )
            text = doctor.render()
        self.assertTrue(text.startswith("hermes-odd doctor (read-only)"))
        for name in (
            "gentle-ai binary",
            "RDD mode",
            "SOUL.md",
            "plugin surface",
            "Native review on Hermes",
            "upstream lock",
            "Hermes",
        ):
            self.assertIn(f"  {name}: ", text)
        self.assertIn("✓  gentle-ai binary: 3.7.0", text)
        self.assertIn(f"⚠  {NATIVE_LINE} (immutable_review_transport_unsupported)", text)
        self.assertIn("hermes-odd:rdd-review", text)
        self.assertIn("✓  RDD mode: receipt-driven development on (decided by global) · proj", text)
        self.assertIn("   fix: ", text)
        self.assertLessEqual(len(text), OUTPUT_MAX_CHARS)
        self.assertNotIn(HOME, text)
        self.assertNotIn(tmp, text)

    def test_a_raising_check_is_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doctor = make_doctor(Path(tmp))

            def boom():
                raise RuntimeError("x")

            doctor._home = boom
            text = doctor.render()
        self.assertIn("⚠  SOUL.md: check failed (RuntimeError)", text)

    def test_output_is_capped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            many = {f"block-{i:02d}-{'n' * 40}": 10 for i in range(30)}
            doctor = make_doctor(Path(tmp), soul=synthetic_soul(many))
            text = doctor.render()
        self.assertLessEqual(len(text), OUTPUT_MAX_CHARS)
        self.assertIn("… 22 more", text)


class StatusTests(unittest.TestCase):
    def test_aggregates_fake_stores(self) -> None:
        now = [10_000_000.0]
        agents = AgentStore(FakeState(), clock=lambda: now[0])
        agents.on_subagent_start(
            child_session_id="c1", child_subagent_id="sa-0-aaaaaaaa", child_goal="g"
        )
        agents.on_subagent_start(
            child_session_id="c2", child_subagent_id="sa-1-bbbbbbbb", child_goal="g"
        )
        agents.on_subagent_stop(child_session_id="c2", child_status="completed", duration_ms=5)
        changes = ChangeStore(FakeState(), clock=lambda: now[0])
        with tempfile.TemporaryDirectory() as tmp:
            changes.record("patch", [FileOp(f"{tmp}/a.py", 3, 1)])
            changes.record("write_file", [FileOp(f"{tmp}/b.py", 2, None)])
            root = Path(tmp) / "proj"
            (root / "odd" / "tasks").mkdir(parents=True)
            (root / "odd" / "tasks" / "f.md").write_text(
                "# F\n\n## Tasks\n\n- [x] T1 a\n- [ ] T2 b\n- [ ] T3 c\n", encoding="utf-8"
            )
            go = f"{HOME}/go/bin/gentle-ai"
            prober = prober_for([go], {go: "gentle-ai 3.7.0"})
            runtime = RuntimeInfo(
                section_registered=True, section_chars=3332, skills=["odd-workflow"]
            )
            status = Status(
                runtime,
                prober,
                agents,
                changes,
                None,
                cwd_candidates=[root],
                repo=lambda: Path("/work/proj"),
            )
            text = status.render()
            self.assertIn("RDD: unknown here · run /odd_doctor", text)
            prober.review_mode(go, Path("/work/proj"))
            text2 = status.render()
        self.assertIn(f"hermes-odd {__version__} is active", text)
        self.assertIn("Prompt: hermes-odd-workflow 3332/4000 chars", text)
        self.assertIn("Skills: 1 (odd-workflow)", text)
        self.assertIn("Subagents: 1 running · 1 finished (24 h)", text)
        self.assertIn("Changes (24 h): 2 files · +5 −≥1", text)
        self.assertIn("ODD features: 1 · 2 open tasks (1 project)", text)
        self.assertIn("gentle-ai: 3.7.0 ✓ min 3.7.0 (~/go/bin/gentle-ai)", text)
        self.assertIn("Upstream: gentle-ai v3.7.0", text)
        self.assertIn("Problems? /odd_doctor", text)
        self.assertIn("RDD: on (decided by global) · proj", text2)
        self.assertLessEqual(len(text), STATUS_MAX_CHARS)
        self.assertNotIn(HOME, text + text2)
        # Only the cached version probe ran (one run for status twice).
        self.assertEqual(prober.runs, 2)  # version once + the explicit review probe

    def test_status_shows_native_review_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "proj"
            (repo / ".git").mkdir(parents=True)
            go = f"{HOME}/go/bin/gentle-ai"
            prober = prober_for([go], {go: "gentle-ai 3.7.0"})
            status = Status(None, prober, cwd_candidates=[], repo=lambda: repo)
            text = status.render()
            again = status.render()
        self.assertIn(NATIVE_LINE, text)
        self.assertEqual(text, again)
        self.assertEqual(prober.runs, 2)  # version + native probe, both cached
        self.assertLessEqual(len(text), STATUS_MAX_CHARS)
        self.assertNotIn(tmp, text)

    def test_status_native_line_without_repo(self) -> None:
        go = f"{HOME}/go/bin/gentle-ai"
        status = Status(
            None, prober_for([go], {go: "gentle-ai 3.7.0"}), cwd_candidates=[], repo=lambda: None
        )
        self.assertIn(
            "Native review on Hermes: unknown (the probe needs a git repository", status.render()
        )

    def test_status_without_stores_or_binary(self) -> None:
        status = Status(None, prober_for([], {}), cwd_candidates=[], repo=lambda: None)
        text = status.render()
        self.assertIn("Prompt: section not registered ✗", text)
        self.assertIn("Subagents: not tracked", text)
        self.assertIn("gentle-ai: ✗ not on PATH (min 3.7.0)", text)

    def test_failing_store_does_not_break_status(self) -> None:
        class Boom:
            def records(self):
                raise RuntimeError("x")

        status = Status(None, prober_for([], {}), Boom(), cwd_candidates=[], repo=lambda: None)
        self.assertIn("Subagents: unavailable (RuntimeError)", status.render())


class CommandsListingTests(unittest.TestCase):
    def test_groups_and_every_command_listed(self) -> None:
        registry = build_registry()
        text = registry.get("odd_commands").handler("")
        self.assertLess(text.index("Viewers:"), text.index("Health:"))
        for spec in registry:
            self.assertIn(f"/{spec.name}", text)
            self.assertIn(spec.group, ("Viewers", "Review", "Health"))
        self.assertLess(text.index("Review:"), text.index("Health:"))
        self.assertIn("/odd_review_mode [status|enable|disable] [global|clone] [project]", text)
        self.assertEqual(registry.get("odd_review_mode").group, "Review")
        self.assertEqual(
            [s.name for s in registry],
            [
                "odd_agents",
                "odd_tasks",
                "odd_changes",
                "odd_review_mode",
                "odd_status",
                "odd_doctor",
                "odd_commands",
            ],
        )

    def test_registered_handlers_never_raise(self) -> None:
        ctx = FakeContext()
        register(ctx)
        with tempfile.TemporaryDirectory() as tmp:
            env = {"HERMES_HOME": tmp, "PATH": tmp}
            for key in ("odd-status", "odd-doctor", "odd-commands", "odd-review-mode"):
                with (
                    mock.patch.dict(os.environ, env),
                    mock.patch.dict("sys.modules", {"hermes_constants": None}),
                    mock.patch("subprocess.run", side_effect=OSError("no")),
                ):
                    out = ctx.commands[key]["handler"]("anything")
                self.assertIsInstance(out, str)
                self.assertTrue(out.strip())
                self.assertNotIn(HOME + "/", out)
                self.assertNotIn(tmp, out)


class DisplayPathTests(unittest.TestCase):
    def test_never_a_full_home_path(self) -> None:
        self.assertEqual(display_path(f"{HOME}/go/bin/gentle-ai"), "~/go/bin/gentle-ai")
        self.assertEqual(display_path(HOME), "~")
        self.assertEqual(display_path("/opt/homebrew/bin/gentle-ai"), "…/homebrew/bin/gentle-ai")
        self.assertEqual(display_path("/usr/bin"), "/usr/bin")
        # Regression: Linux CI temp homes (/tmp/tmpXXXX) must never be printed in full.
        self.assertEqual(display_path("/tmp/tmp79f4j516/SOUL.md"), "…/tmp79f4j516/SOUL.md")


class ReviewModeTextTests(unittest.TestCase):
    def test_wording(self) -> None:
        from hermes_odd.commands.doctor import review_mode_text

        self.assertEqual(
            review_mode_text(ReviewMode("ok", "off", "clone", "/r/x")), "off (decided by clone) · x"
        )
        self.assertEqual(review_mode_text(None), "unknown")


if __name__ == "__main__":
    unittest.main()
