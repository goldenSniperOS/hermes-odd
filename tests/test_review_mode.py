"""``/odd_review_mode``, the native review availability probe and the RDD skills."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import REPO_ROOT, FakeContext, FakeState, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.commands.review_mode import (  # noqa: E402
    OUTPUT_MAX_CHARS,
    ReviewModeCommand,
    parse_args,
    sanitize,
)
from hermes_odd.probes import (  # noqa: E402
    AGENT_ID,
    UNSUPPORTED_CODE,
    NativeReview,
    Prober,
    ProbeResult,
    native_review_command,
    parse_native_review,
    parse_runtimes,
    review_mode_command,
)
from hermes_odd.projects import ProjectStore  # noqa: E402
from hermes_odd.rdd import (  # noqa: E402
    DEFAULT_ADVERTISED,
    UNAVAILABLE_NOTE,
    advertised_runtimes,
    native_review_line,
    native_review_text,
)
from hermes_odd.skills import SKILLS_DIR, load_skill  # noqa: E402

HOME = os.path.expanduser("~")
BIN = "/opt/homebrew/bin/gentle-ai"
CAUSE = (
    "the active runtime is not eligible for immutable receipt review; exit receipt-driven "
    "review with `gentle-ai review mode disable --scope clone --cwd <repo>`; supported "
    "immutable review runtimes: {}"
)


def failure_json(code: str = UNSUPPORTED_CODE, runtimes: str = "claude-code, opencode, codex, pi"):
    import json

    return json.dumps(
        {
            "schema": "gentle-ai.review-integration.failure/v2",
            "contract": "gentle-ai.review-integration/v2",
            "operation": "review.status",
            "phase": "preflight",
            "code": code,
            "mutation_outcome": "not_started",
            "next_action": "stop",
            "cause": CAUSE.format(runtimes),
        },
        indent=2,
    )


def mode_json(effective="on", source="global", global_mode="on", clone="", operation="status"):
    import json

    return json.dumps(
        {
            "schema": "gentle-ai.review-mode/v1",
            "operation": operation,
            "scope": "both",
            "status": {
                "schema": "gentle-ai.rdd-mode-status/v1",
                "global": global_mode,
                "clone_local": clone,
                "effective": effective,
                "source": source,
            },
        }
    )


class Runner:
    """Fake gentle-ai: records every argv; answers per subcommand."""

    def __init__(self, native=None, native_state="failed", write=None, status=None):
        self.native = failure_json() if native is None else native
        self.native_state = native_state
        self.write = write or ProbeResult("ok", mode_json("off", "clone", "on", "off"), 0)
        self.status = status or ProbeResult("ok", mode_json(), 0)
        self.commands: list[list[str]] = []

    def __call__(self, command, timeout):
        self.commands.append(list(command))
        assert timeout <= 5.0, timeout
        if command[1:] == ["version"]:
            return ProbeResult("ok", "gentle-ai 3.7.0\n", 0)
        if command[1:4] == ["review", "mode", "status"]:
            return self.status
        if command[1:3] == ["review", "mode"] and command[3] in ("enable", "disable"):
            return self.write
        if command[1:3] == ["review", "status"]:
            return ProbeResult(self.native_state, self.native, 1)
        raise AssertionError(f"unexpected command {command}")

    def review_commands(self):
        return [c for c in self.commands if c[1:2] == ["review"]]


def git_repo(root: Path, name: str) -> Path:
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    return repo


def make_command(runner, repo=None, store=None, cwd=None, binaries=(BIN,)):
    prober = Prober(runner=runner, finder=lambda: list(binaries))
    return (
        ReviewModeCommand(prober, store, repo=lambda: repo, cwd_candidates=lambda: list(cwd or [])),
        prober,
    )


def assert_agent_is_hermes(test: unittest.TestCase, argv: list[str]) -> None:
    if "--agent" in argv:
        test.assertEqual(argv[argv.index("--agent") + 1], AGENT_ID, argv)
    test.assertNotIn("pi", [a for a in argv if not a.startswith("/")], argv)


class NativeReviewParsingTests(unittest.TestCase):
    def test_unsupported_code_is_unavailable_with_runtimes(self) -> None:
        native = parse_native_review(ProbeResult("failed", failure_json(), 1))
        self.assertEqual(native.state, "unavailable")
        self.assertEqual(native.code, UNSUPPORTED_CODE)
        self.assertEqual(native.runtimes, ("claude-code", "opencode", "codex", "pi"))

    def test_future_gentle_ai_accepting_hermes_is_detected(self) -> None:
        body = '{"schema": "gentle-ai.review-integration.status/v9", "transition": {}}'
        native = parse_native_review(ProbeResult("ok", body, 0))
        self.assertEqual(native.state, "available")
        text = native_review_line(native, "3.9.0")
        self.assertIn("available (detected)", text)
        self.assertIn("T8", text)
        self.assertIn("no native review runs", text)

    def test_other_failure_code_and_garbage_are_unknown(self) -> None:
        native = parse_native_review(ProbeResult("failed", failure_json("lock_busy"), 1))
        self.assertEqual((native.state, native.code), ("unknown", "lock_busy"))
        self.assertIn("lock_busy", native_review_text(native, "3.7.0"))
        for body in ("", "not json", "[1, 2]", '{"schema": 3}', "Error: boom"):
            with self.subTest(body=body):
                self.assertEqual(
                    parse_native_review(ProbeResult("failed", body, 1)).state, "unknown"
                )
        weird = failure_json(code="x" * 200)
        self.assertEqual(parse_native_review(ProbeResult("failed", weird, 1)).code, "")

    def test_timeout_and_missing(self) -> None:
        self.assertEqual(parse_native_review(ProbeResult("timeout")).state, "timeout")
        self.assertEqual(parse_native_review(ProbeResult("missing")).state, "no_binary")

    def test_json_after_noise_is_found(self) -> None:
        noisy = "warning: something\n" + failure_json() + "\n"
        self.assertEqual(parse_native_review(ProbeResult("failed", noisy, 1)).state, "unavailable")

    def test_runtime_names_are_sanitized(self) -> None:
        cause = "supported immutable review runtimes: claude-code, Evil Name!!, codex, codex"
        self.assertEqual(parse_runtimes(cause), ("claude-code", "codex"))
        self.assertEqual(parse_runtimes("nothing here"), ())


class NativeReviewTextTests(unittest.TestCase):
    def test_compiled_set_from_the_lock(self) -> None:
        self.assertEqual(advertised_runtimes(), DEFAULT_ADVERTISED)

    def test_environment_subset_still_names_the_compiled_set(self) -> None:
        native = NativeReview("unavailable", UNSUPPORTED_CODE, ("claude-code", "codex"))
        self.assertEqual(
            native_review_line(native, "3.7.0"),
            "Native review on Hermes: unavailable — gentle-ai 3.7.0 advertises immutable "
            "review only for claude-code, opencode, codex, pi",
        )

    def test_newer_runtime_list_is_reported_as_is(self) -> None:
        native = NativeReview("unavailable", UNSUPPORTED_CODE, ("claude-code", "newrt"))
        self.assertTrue(native_review_text(native, "4.0.0").endswith("only for claude-code, newrt"))

    def test_unknown_states(self) -> None:
        self.assertIn("timed out", native_review_text(NativeReview("timeout"), None))
        self.assertIn("git repository", native_review_text(NativeReview("no_repo"), None))
        self.assertIn("not probed", native_review_text(None, None))


class ArgvTests(unittest.TestCase):
    """hermes-odd never passes another runtime's identity to gentle-ai."""

    def test_constructed_argv(self) -> None:
        self.assertEqual(
            native_review_command(BIN, "/r"),
            [
                BIN,
                "review",
                "status",
                "--cwd",
                "/r",
                "--contract",
                "gentle-ai.review-integration/v2",
                "--agent",
                "hermes",
                "--next-transition",
            ],
        )
        self.assertEqual(
            review_mode_command(BIN, "disable", "clone", "/r"),
            [BIN, "review", "mode", "disable", "--scope", "clone", "--cwd", "/r", "--json"],
        )
        self.assertEqual(
            review_mode_command(BIN, "enable", "global"),
            [BIN, "review", "mode", "enable", "--scope", "global", "--json"],
        )
        self.assertEqual(
            review_mode_command(BIN, "status"), [BIN, "review", "mode", "status", "--json"]
        )
        for argv in (
            native_review_command(BIN, "/r"),
            review_mode_command(BIN, "status", repo="/r"),
            review_mode_command(BIN, "enable", "clone", "/r"),
        ):
            assert_agent_is_hermes(self, argv)

    def test_scope_is_required_for_writes(self) -> None:
        for scope in (None, "", "both", "repo"):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                review_mode_command(BIN, "enable", scope)
        with self.assertRaises(ValueError):
            review_mode_command(BIN, "start")

    def test_source_never_builds_another_agent(self) -> None:
        # Every "--agent" literal in the package is followed by AGENT_ID.
        for path in sorted((REPO_ROOT / "hermes_odd").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r'"--agent",\s*([^\s,\]]+)', text):
                with self.subTest(file=path.name):
                    self.assertEqual(match.group(1), "AGENT_ID")

    def test_agent_pi_only_appears_in_never_sentences(self) -> None:
        files = list((REPO_ROOT / "hermes_odd").rglob("*.py")) + list(SKILLS_DIR.rglob("*.md"))
        files += [REPO_ROOT / "README.md", REPO_ROOT / "docs" / "design.md"]
        for path in files:
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "--agent pi" in line:
                    with self.subTest(file=path.name, line=lineno):
                        self.assertIn("never", line.lower())

    def test_every_real_subprocess_call_uses_hermes_or_no_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            calls = []

            def fake_run(argv, **kwargs):
                calls.append(list(argv))
                if argv[1:3] == ["review", "status"]:
                    return subprocess.CompletedProcess(argv, 1, failure_json(), "Error")
                if argv[1:3] == ["review", "mode"]:
                    return subprocess.CompletedProcess(argv, 0, mode_json(), "")
                return subprocess.CompletedProcess(argv, 0, "gentle-ai 3.7.0\n", "")

            command = ReviewModeCommand(
                Prober(finder=lambda: [BIN]), None, repo=lambda: repo, cwd_candidates=lambda: []
            )
            with mock.patch("subprocess.run", side_effect=fake_run) as run:
                command.render("")
                command.render("disable clone")
                command.render("enable global")
            for call in run.call_args_list:
                self.assertFalse(call.kwargs["shell"])
                self.assertIs(call.kwargs["stdin"], subprocess.DEVNULL)
                self.assertLessEqual(call.kwargs["timeout"], 5.0)
                self.assertNotIn("AWS_PROFILE", call.kwargs["env"])
        review = [c for c in calls if c[1:2] == ["review"]]
        self.assertTrue(any(c[1:3] == ["review", "status"] for c in review))
        for argv in review:
            assert_agent_is_hermes(self, argv)


class ProbeTests(unittest.TestCase):
    def test_probe_runs_only_inside_a_git_repository(self) -> None:
        runner = Runner()
        prober = Prober(runner=runner, finder=lambda: [BIN])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(prober.native_review(BIN, Path(tmp)).state, "no_repo")
            self.assertEqual(prober.native_review(BIN, None).state, "no_repo")
            self.assertEqual(prober.native_review(None, Path(tmp)).state, "no_binary")
            self.assertEqual(runner.commands, [])
            repo = git_repo(Path(tmp), "r")
            self.assertEqual(prober.native_review(BIN, repo).state, "unavailable")
            self.assertEqual(runner.commands[0][:5], [BIN, "review", "status", "--cwd", str(repo)])

    def test_probe_is_cached_for_60_seconds_per_binary(self) -> None:
        now = [0.0]
        runner = Runner()
        prober = Prober(runner=runner, clock=lambda: now[0], finder=lambda: [BIN])
        with tempfile.TemporaryDirectory() as tmp:
            a, b = git_repo(Path(tmp), "a"), git_repo(Path(tmp), "b")
            prober.native_review(BIN, a)
            prober.native_review(BIN, b)
            self.assertEqual(len(runner.commands), 1)
            self.assertEqual(prober.cached_native_review().state, "unavailable")
            now[0] += 61
            self.assertIsNone(prober.cached_native_review())
            prober.native_review(BIN, a)
            self.assertEqual(len(runner.commands), 2)


class ParseArgsTests(unittest.TestCase):
    def test_forms(self) -> None:
        self.assertEqual(parse_args(""), ("status", None, None, None))
        self.assertEqual(parse_args("disable clone proj"), ("disable", "clone", "proj", None))
        self.assertEqual(parse_args("GLOBAL Enable"), ("enable", "global", None, None))
        self.assertEqual(parse_args("proj"), ("status", None, "proj", None))
        self.assertIn("Too many arguments", parse_args("a b c")[3])


class StatusCommandTests(unittest.TestCase):
    def test_status_in_a_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            runner = Runner(native=failure_json(runtimes="claude-code, codex"))
            command, _ = make_command(runner, repo=repo)
            text = command.render("")
        self.assertTrue(text.startswith("RDD review mode · proj ("))
        self.assertIn("receipt-driven development: on (decided by global)", text)
        self.assertIn("sources: global on · clone unset", text)
        self.assertIn(
            "Native review on Hermes: unavailable — gentle-ai 3.7.0 advertises immutable "
            "review only for claude-code, opencode, codex, pi",
            text,
        )
        self.assertIn("gentle-ai code: immutable_review_transport_unsupported", text)
        self.assertIn("eligible in this environment: claude-code, codex", text)
        self.assertIn(UNAVAILABLE_NOTE, text)
        self.assertIn("hermes-odd:rdd-review", text)
        self.assertLessEqual(len(text), OUTPUT_MAX_CHARS)
        self.assertNotIn(tmp, text)
        self.assertNotIn(HOME + "/", text)
        self.assertEqual(
            runner.review_commands()[0],
            [BIN, "review", "mode", "status", "--cwd", str(repo), "--json"],
        )
        for argv in runner.review_commands():
            assert_agent_is_hermes(self, argv)
        # Status never writes.
        self.assertFalse([c for c in runner.commands if c[3:4] in (["enable"], ["disable"])])

    def test_status_available_does_not_start_a_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            runner = Runner(
                native='{"schema": "gentle-ai.review-integration.status/v9"}', native_state="ok"
            )
            command, _ = make_command(runner, repo=repo)
            text = command.render("status")
        self.assertIn("available (detected)", text)
        self.assertIn("T8", text)
        subcommands = {tuple(c[1:3]) for c in runner.review_commands()}
        self.assertEqual(subcommands, {("review", "mode"), ("review", "status")})

    def test_status_without_repository_reads_the_global_switch(self) -> None:
        runner = Runner(status=ProbeResult("ok", mode_json("off", "global", "off"), 0))
        command, _ = make_command(runner, repo=None)
        text = command.render("")
        self.assertIn("no git repository here (global switch only)", text)
        self.assertIn("receipt-driven development: off (decided by global)", text)
        self.assertIn("Native review on Hermes: unknown (the probe needs a git repository", text)
        self.assertEqual(runner.review_commands(), [[BIN, "review", "mode", "status", "--json"]])

    def test_status_timeout_and_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            runner = Runner(native_state="timeout", status=ProbeResult("timeout"))
            text = make_command(runner, repo=repo)[0].render("")
        self.assertIn("unknown (gentle-ai timed out)", text)
        self.assertIn("Native review on Hermes: unknown (gentle-ai timed out)", text)
        missing = make_command(Runner(), repo=None, binaries=())[0].render("")
        self.assertIn("gentle-ai: not found on PATH", missing)

    def test_project_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(FakeState())
            alpha, alpine, beta = (git_repo(root, n) for n in ("alpha", "alpine", "beta"))
            plain = root / "plain"
            plain.mkdir()
            for path in (alpha, alpine, beta, plain):
                store.record(str(path))
            runner = Runner()
            command, _ = make_command(runner, repo=None, store=store)
            self.assertTrue(command.render("beta").startswith("RDD review mode · beta ("))
            self.assertTrue(command.render("ALPHA").startswith("RDD review mode · alpha ("))
            self.assertIn("is ambiguous", command.render("alp"))
            missing = command.render("nothing")
            self.assertIn("No known git project matches 'nothing'", missing)
            self.assertNotIn("plain", missing)  # not a git repository
            self.assertNotIn(tmp, command.render("alp") + missing)
            # Without a project the native probe borrows the latest known git root.
            text = command.render("")
            self.assertIn("Native review on Hermes: unavailable", text)


class WriteCommandTests(unittest.TestCase):
    def test_scope_is_required(self) -> None:
        runner = Runner()
        command, _ = make_command(runner, repo=Path("/nowhere"))
        for args in ("enable", "disable"):
            with self.subTest(args=args):
                text = command.render(args)
                self.assertIn("needs an explicit scope", text)
                self.assertIn("No change was made", text)
                self.assertIn(f"/odd_review_mode {args} global", text)
                self.assertIn(f"/odd_review_mode {args} clone", text)
        self.assertEqual(runner.commands, [])

    def test_clone_without_repository_is_refused(self) -> None:
        runner = Runner()
        command, _ = make_command(runner, repo=None)
        text = command.render("disable clone")
        self.assertIn("Refused: the clone switch needs a git repository", text)
        self.assertIn("No change was made", text)
        self.assertEqual(runner.commands, [])

    def test_disable_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            runner = Runner()
            command, prober = make_command(runner, repo=repo)
            command.render("")  # caches the mode
            text = command.render("disable clone")
            after = command.render("")
        writes = [c for c in runner.commands if c[3:4] == ["disable"]]
        self.assertEqual(
            writes,
            [[BIN, "review", "mode", "disable", "--scope", "clone", "--cwd", str(repo), "--json"]],
        )
        self.assertIn("RDD review mode disabled (scope clone) · proj", text)
        self.assertIn("receipt-driven development: off (decided by clone)", text)
        self.assertIn("sources: global on · clone off", text)
        self.assertIn("Applies to future candidates only.", text)
        # The cached status was dropped: status ran again after the write.
        statuses = [c for c in runner.commands if c[1:4] == ["review", "mode", "status"]]
        self.assertEqual(len(statuses), 2)
        self.assertIn("RDD review mode · proj", after)
        self.assertNotIn(tmp, text)

    def test_enable_global_without_repository(self) -> None:
        runner = Runner(write=ProbeResult("ok", mode_json("on", "global", "on", "", "enable"), 0))
        command, _ = make_command(runner, repo=None)
        text = command.render("enable global")
        self.assertEqual(
            [c for c in runner.commands if c[3:4] == ["enable"]],
            [[BIN, "review", "mode", "enable", "--scope", "global", "--json"]],
        )
        self.assertIn("RDD review mode enabled (scope global)", text)

    def test_enable_clone_explains_opt_out_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            write = ProbeResult("ok", mode_json("off", "global", "off", "", "enable"), 0)
            text = make_command(Runner(write=write), repo=repo)[0].render("enable clone")
        self.assertIn("A clone can only opt out", text)
        self.assertIn("Still off: any off wins", text)

    def test_errors_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            stderr = (
                f"Error: the clone-local review mode path {HOME}/secret/place/mode.json is "
                f"unsafe; run `chmod 600 {tmp}/proj/.git/gentle-ai/mode` " + "x" * 2000
            )
            runner = Runner(write=ProbeResult("failed", "", 1, stderr))
            text = make_command(runner, repo=repo)[0].render("disable clone")
        self.assertIn("gentle-ai review mode disable --scope clone failed · proj", text)
        self.assertIn("~/secret/place/mode.json", text)
        self.assertNotIn(HOME + "/", text)
        self.assertNotIn(tmp, text)
        self.assertLess(len(text), 600)

    def test_timeout_and_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            slow = make_command(Runner(write=ProbeResult("timeout")), repo=repo)[0]
            self.assertIn("timed out after 5 s", slow.render("disable clone"))
            odd = make_command(Runner(write=ProbeResult("ok", "garbage", 0)), repo=repo)[0]
            self.assertIn("JSON result was unreadable", odd.render("disable global"))
        missing = make_command(Runner(), repo=None, binaries=())[0]
        self.assertIn(
            "gentle-ai not found on PATH; nothing was changed", missing.render("enable global")
        )

    def test_sanitize(self) -> None:
        self.assertEqual(sanitize(f"at {HOME}/x/y"), "at ~/x/y")
        self.assertEqual(sanitize("at /var/lib/deep/dir/file"), "at …/deep/dir/file")
        self.assertEqual(sanitize("a\n  b"), "a b")
        self.assertLessEqual(len(sanitize("y" * 1000)), 400)


class RegistrationTests(unittest.TestCase):
    def test_doctor_native_check_levels(self) -> None:
        from hermes_odd.commands.doctor import OK, WARN, check_native_review
        from hermes_odd.probes import BinaryInfo

        binary = BinaryInfo(BIN, "3.7.0", "ok")
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp), "proj")
            prober = Prober(runner=Runner(), finder=lambda: [BIN])
            on = check_native_review(prober, binary, repo, 3.0, rdd_on=True)
            off = check_native_review(prober, binary, repo, 3.0, rdd_on=False)
            spent = check_native_review(prober, binary, repo, 0.0)
            no_repo = check_native_review(Prober(runner=Runner()), binary, None, 3.0)
        self.assertEqual(on.level, WARN)
        self.assertIn("not a local fault", on.hint)
        self.assertEqual(off.level, OK)
        self.assertIn("RDD is off", off.finding)
        self.assertIn("time budget", spent.finding)
        self.assertIn("inside a git project", no_repo.hint)

    def test_registered_and_listed(self) -> None:
        ctx = FakeContext()
        register(ctx)
        entry = ctx.commands["odd-review-mode"]
        self.assertEqual(entry["args_hint"], "[status|enable|disable] [global|clone] [project]")
        self.assertFalse(entry["args_hint"].startswith("<"))
        listing = ctx.commands["odd-commands"]["handler"]("")
        self.assertIn("Review:\n- /odd_review_mode", listing)


class RddSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.review = (SKILLS_DIR / "rdd-review" / "SKILL.md").read_text(encoding="utf-8")
        self.lenses = (SKILLS_DIR / "rdd-review-lenses" / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter(self) -> None:
        for name in ("rdd-review", "rdd-review-lenses"):
            spec = load_skill(SKILLS_DIR / name)
            self.assertEqual(spec.name, name)
            self.assertIn("rdd", spec.frontmatter["metadata"]["hermes"]["tags"])

    def test_protocol_is_honest(self) -> None:
        for token in (
            "Gentle AI",
            "work-unit commit or one PR slice",
            "Never a TODO checkbox",
            "gentle-ai review mode status --json",
            "immutable_review_transport_unsupported",
            UNAVAILABLE_NOTE,
            "ordinary repository policy",
            "Never impersonate another runtime",
            "Never fake",
            "advisory review — no receipt",
            "git show <sha>",
            "delegate_task",
            "hermes-odd:rdd-review-lenses",
            "/odd_review_mode",
            "never authorizes",
        ):
            self.assertIn(token, self.review)

    def test_lenses_cover_the_4r(self) -> None:
        for token in ("## R1 Risk", "## R2 Readability", "## R3 Reliability", "## R4 Resilience"):
            self.assertIn(token, self.lenses)
        self.assertIn("advisory review — no receipt", self.lenses)
        self.assertIn("git show <sha>", self.lenses)
        # The Pi-only ledger tooling is not carried over.
        self.assertNotIn("gentle_review_scope", self.lenses)
        self.assertNotIn("initial_review_tree", self.lenses)

    def test_no_other_runtime_identity_is_suggested(self) -> None:
        for text in (self.review, self.lenses):
            for line in text.splitlines():
                if re.search(r"--agent\s+(?!hermes\b)\S", line):
                    self.assertIn("never", line.lower(), line)


if __name__ == "__main__":
    unittest.main()
