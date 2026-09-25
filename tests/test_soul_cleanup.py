"""SOUL cleanup of gentle-ai blocks: /odd_soul, odd_soul_apply, rules, backups, restore."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import REPO_ROOT, FakeContext, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import personas  # noqa: E402
from hermes_odd import soul as soul_mod  # noqa: E402
from hermes_odd import soul_cleanup as sc  # noqa: E402
from hermes_odd import soul_persona as sp  # noqa: E402
from hermes_odd.agents import MemoryBackend  # noqa: E402
from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.commands.doctor import OK, WARN, check_soul  # noqa: E402
from hermes_odd.commands.soul import SoulCommand, render_plan  # noqa: E402
from hermes_odd.plugin import register  # noqa: E402
from hermes_odd.setup import Setup  # noqa: E402
from hermes_odd.setup_tool import make_handler as make_setup_handler  # noqa: E402
from hermes_odd.skills import parse_frontmatter  # noqa: E402
from hermes_odd.soul_tool import SCHEMA as SOUL_SCHEMA  # noqa: E402
from hermes_odd.soul_tool import TOOL_NAME as SOUL_TOOL  # noqa: E402
from hermes_odd.soul_tool import make_handler  # noqa: E402

CANARY = "SECRET-SOUL-CONTENT-xyz"


def block(name: str, body: str, namespace: str = "gentle-ai") -> str:
    return f"<!-- {namespace}:{name} -->\n{body}<!-- /{namespace}:{name} -->"


HEADER = f"# Hermes agent\n\nUser intro line {CANARY}.\nSecond user line.\n\n"
CODEGRAPH = block("codegraph-guidance", f"## CodeGraph\ncodegraph rules {CANARY}\n")
PERSONA = block("persona", f"Old gentle persona {CANARY}.\n")
ENGRAM = block("engram-protocol", f"## Engram\nmemory rules {CANARY}\n")
PREFLIGHT = block("sdd-session-preflight", f"preflight {CANARY}\n")
ORCHESTRATOR = block("sdd-orchestrator", f"orchestrator {CANARY}\n{PREFLIGHT}\nmore\n")
REMOTE = block("remote-authorization", f"Remote actions need explicit authorization {CANARY}.\n")
ROUTING = block("agent-routing", f"## Routing\nrouting {CANARY}\n{REMOTE}\nend of routing\n")

# Mirrors the real layout: user header, then top-level blocks separated by a
# blank line, agent-routing last with remote-authorization nested at its end.
REAL_LIKE = (
    HEADER
    + CODEGRAPH
    + "\n\n"
    + PERSONA
    + "\n\n"
    + ENGRAM
    + "\n\n"
    + ORCHESTRATOR
    + "\n\n"
    + ROUTING
    + "\n"
)
EXPECTED = HEADER + PERSONA + "\n\n" + REMOTE + "\n"


class HomeCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.soul = self.home / "SOUL.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, text: str, mode: int = 0o640) -> None:
        self.soul.write_bytes(text.encode("utf-8"))
        os.chmod(self.soul, mode)

    def read(self) -> str:
        return self.soul.read_bytes().decode("utf-8")

    def backups(self) -> list[Path]:
        return sp.backup_paths(self.soul)

    def command(self) -> SoulCommand:
        return SoulCommand(home=lambda: self.home, model_context=lambda _h: soul_mod.ModelContext())


class PlanTests(HomeCase):
    def test_real_like_soul_exact_result(self) -> None:
        self.write(REAL_LIKE)
        plan = sc.plan_cleanup(self.home)
        self.assertEqual(plan.error, "")
        self.assertTrue(plan.writes)
        self.assertEqual(plan.after, EXPECTED)
        self.assertEqual(
            [(i.label, i.action, i.skill) for i in plan.items],
            [
                ("gentle-ai:codegraph-guidance", sc.MOVE, "hermes-odd:codegraph"),
                ("gentle-ai:persona", sc.KEEP, ""),
                ("gentle-ai:engram-protocol", sc.MOVE, "hermes-odd:engram-protocol"),
                ("gentle-ai:sdd-orchestrator", sc.REMOVE, ""),
                ("gentle-ai:agent-routing", sc.REMOVE, ""),
            ],
        )
        orchestrator, routing = plan.items[3], plan.items[4]
        self.assertEqual(orchestrator.nested, [("gentle-ai:sdd-session-preflight", len(PREFLIGHT))])
        self.assertEqual(orchestrator.saved, len(ORCHESTRATOR))
        self.assertEqual(routing.lifted, [("gentle-ai:remote-authorization", len(REMOTE), sc.LIFT)])
        self.assertEqual(routing.saved, len(ROUTING) - len(REMOTE))
        self.assertEqual(plan.before_chars, len(REAL_LIKE.strip()))
        self.assertEqual(plan.after_chars, len(EXPECTED.strip()))
        self.assertEqual(self.read(), REAL_LIKE)  # planning never writes
        self.assertEqual(self.backups(), [])

    def test_plan_output_lists_actions_sizes_and_warning(self) -> None:
        self.write(REAL_LIKE)
        text = self.command().handle("plan")
        for token in (
            "dry run, nothing written",
            "gentle-ai:codegraph-guidance",
            "move to skill hermes-odd:codegraph",
            "move to skill hermes-odd:engram-protocol",
            "gentle-ai:persona",
            "→ keep",
            "(nested: sdd-session-preflight",
            "lift remote-authorization",
            "markers kept",
            f"Size: {len(REAL_LIKE.strip()):,} → {len(EXPECTED.strip()):,} chars",
            "128k (cap 30,720): fits → fits",
            "gentle-ai sync --agent hermes",
            "gentle-ai install",
            "/odd_soul apply confirm",
            "SOUL.md.hermes-odd-bak-",
        ):
            self.assertIn(token, text)
        self.assertNotIn(CANARY, text)
        self.assertNotIn(str(self.home), text)
        self.assertLess(len(text), 3500)
        self.assertEqual(text, self.command().handle("plan"))  # deterministic
        self.assertEqual(self.read(), REAL_LIKE)

    def test_status_lists_blocks_truncation_and_next_step(self) -> None:
        self.write(REAL_LIKE)
        text = self.command().handle("")
        self.assertEqual(text, self.command().handle("status"))
        for token in (
            "SOUL.md cleanup status",
            "gentle-ai:sdd-orchestrator",
            "→ remove",
            "Truncation by Hermes now:",
            "- 1M (cap 240,000): fits",
            "Backups: none",
            "Next: /odd_soul plan",
        ):
            self.assertIn(token, text)
        self.assertNotIn(CANARY, text)

    def test_malformed_markers_refuse_and_change_nothing(self) -> None:
        cases = {
            "unclosed": HEADER + "<!-- gentle-ai:sdd-orchestrator -->\nno end\n",
            "without its opener": HEADER + "stray <!-- /gentle-ai:agent-routing -->\n",
            "crosses": (
                "<!-- gentle-ai:agent-routing -->\n<!-- gentle-ai:remote-authorization -->\n"
                "<!-- /gentle-ai:agent-routing -->\n<!-- /gentle-ai:remote-authorization -->\n"
            ),
            "unclosed hermes-odd": "<!-- hermes-odd:persona -->\n" + CODEGRAPH + "\n",
        }
        for word, text in cases.items():
            with self.subTest(word=word):
                self.write(text)
                plan = sc.plan_cleanup(self.home)
                self.assertIn(word.split()[0], plan.error)
                self.assertIn("nothing was changed", plan.error)
                self.assertFalse(plan.writes)
                self.assertFalse(sc.apply_cleanup(plan).written)
                self.assertIn("Cannot plan", self.command().handle("plan"))
                self.assertIn("not applied", self.command().handle("apply confirm"))
                self.assertEqual(self.read(), text)
                self.assertEqual(self.backups(), [])

    def test_line_numbers_in_errors_not_content(self) -> None:
        self.write("line one\n<!-- gentle-ai:engram-protocol -->\n" + CANARY + "\n")
        plan = sc.plan_cleanup(self.home)
        self.assertIn("line 2", plan.error)
        self.assertNotIn(CANARY, plan.error)

    def test_unknown_blocks_hermes_persona_and_user_text_kept(self) -> None:
        ours = personas.render_block("neutral")
        unknown = block("custom-notes", f"my notes {CANARY}\n")
        text = ours + "\n\nIntro.\n\n" + unknown + "\n\n" + ENGRAM + "\nTail line.\n"
        self.write(text)
        plan = sc.plan_cleanup(self.home)
        self.assertEqual(plan.after, ours + "\n\nIntro.\n\n" + unknown + "\n\nTail line.\n")
        labels = {i.label: i.action for i in plan.items}
        self.assertEqual(labels["hermes-odd:persona"], sc.KEEP)
        self.assertEqual(labels["gentle-ai:custom-notes"], sc.KEEP)

    def test_gentle_persona_removed_only_on_request_with_hermes_persona(self) -> None:
        # Without a hermes-odd persona the request is refused and the persona kept.
        self.write(PERSONA + "\n\n" + ENGRAM + "\n")
        plan = sc.plan_cleanup(self.home, remove_persona=True)
        self.assertIn("no hermes-odd persona block", plan.persona_note)
        self.assertIn(PERSONA, plan.after)
        refused = self.command().handle("apply persona confirm")
        self.assertIn("not applied", refused)
        self.assertEqual(self.read(), PERSONA + "\n\n" + ENGRAM + "\n")
        # With one, the default still keeps it and only offers the option.
        ours = personas.render_block("rioplatense")
        self.write(ours + "\n\n" + PERSONA + "\n\n" + ENGRAM + "\n")
        default = sc.plan_cleanup(self.home)
        self.assertIn(PERSONA, default.after)
        self.assertTrue(default.persona_optional)
        self.assertIn("/odd_soul plan persona", self.command().handle("plan"))
        requested = sc.plan_cleanup(self.home, remove_persona=True)
        self.assertEqual(requested.after, ours + "\n")
        self.assertIn("/odd_soul apply persona confirm", self.command().handle("plan persona"))
        done = self.command().handle("apply persona confirm")
        self.assertIn("SOUL.md cleaned", done)
        self.assertEqual(self.read(), ours + "\n")

    def test_persona_only_left_offers_the_option(self) -> None:
        ours = personas.render_block("neutral")
        self.write(ours + "\n\n" + PERSONA + "\n")
        plan = sc.plan_cleanup(self.home)
        self.assertFalse(plan.writes)
        text = self.command().handle("plan")
        self.assertIn("Nothing to clean", text)
        self.assertIn("/odd_soul plan persona", text)

    def test_duplicate_remote_authorization_is_not_lifted_twice(self) -> None:
        self.write(REMOTE + "\n\n" + ROUTING + "\n")
        plan = sc.plan_cleanup(self.home)
        self.assertEqual(plan.items[1].lifted[0][2], sc.DROP)
        self.assertEqual(plan.after, REMOTE + "\n")
        self.assertIn("identical copy already kept", self.command().handle("plan"))

    def test_standalone_preflight_and_crlf(self) -> None:
        text = ("Intro\n\n" + PREFLIGHT + "\n\n" + ROUTING + "\nTail\n").replace("\n", "\r\n")
        self.write(text)
        plan = sc.plan_cleanup(self.home)
        self.assertEqual(plan.after, ("Intro\n\n" + REMOTE + "\nTail\n").replace("\n", "\r\n"))
        self.assertNotIn("\n", plan.after.replace("\r\n", ""))

    def test_no_soul_and_empty_soul(self) -> None:
        self.assertIn("does not exist", self.command().handle("plan"))
        self.assertIn("does not exist", self.command().handle("status"))
        self.write("")
        plan = sc.plan_cleanup(self.home)
        self.assertFalse(plan.writes)
        self.assertIn("Nothing to clean", self.command().handle("plan"))

    def test_refuses_symlink_and_non_utf8(self) -> None:
        target = self.home / "real.md"
        target.write_text(REAL_LIKE, encoding="utf-8")
        self.soul.symlink_to(target)
        self.assertIn("symlink", sc.plan_cleanup(self.home).error)
        self.assertIn("not applied", self.command().handle("apply confirm"))
        self.assertEqual(target.read_text(encoding="utf-8"), REAL_LIKE)
        self.soul.unlink()
        self.soul.write_bytes(b"\xff\xfe" + REAL_LIKE.encode("utf-8"))
        self.assertIn("UTF-8", sc.plan_cleanup(self.home).error)


class TruncationTests(HomeCase):
    def big_soul(self) -> str:
        filler = "x" * 60_000
        return (
            HEADER
            + CODEGRAPH
            + "\n\n"
            + block("sdd-orchestrator", filler + "\n")
            + "\n\n"
            + ROUTING
        )

    def test_before_and_after_for_reference_and_configured_contexts(self) -> None:
        self.write(self.big_soul())
        plan = sc.plan_cleanup(self.home)
        context = soul_mod.ModelContext("m", 128_000, "cache")
        rows = sc.impacts(plan, context)
        self.assertEqual(
            [r.label for r in rows], ["128k", "200k", "1M", "configured m 128k (cache)"]
        )
        by_label = {r.label: r for r in rows}
        small = by_label["128k"]
        self.assertEqual(small.cap, 30_720)
        self.assertFalse(small.before_fits)
        self.assertIn("sdd-orchestrator (partly)", small.before_lost)
        self.assertTrue(small.after_fits)
        self.assertTrue(by_label["1M"].before_fits)
        self.assertEqual(by_label["configured m 128k (cache)"].cap, 30_720)
        text = render_plan(plan, context)
        self.assertIn("- 128k (cap 30,720): truncated, loses sdd-orchestrator (partly)", text)
        self.assertIn("→ fits", text)
        pinned = sc.impacts(plan, soul_mod.ModelContext("m", None, "", 25_000))
        self.assertEqual(pinned[-1].label, "configured (context_file_max_chars)")
        self.assertEqual(pinned[-1].cap, 25_000)


class ApplyTests(HomeCase):
    def test_apply_backup_verify_permissions_and_idempotence(self) -> None:
        self.write(REAL_LIKE, mode=0o604)
        text = self.command().handle("apply confirm")
        self.assertIn("SOUL.md cleaned", text)
        self.assertIn("Verified on disk", text)
        self.assertIn("Moved to lazy skills: codegraph-guidance → hermes-odd:codegraph", text)
        self.assertIn("Lifted (kept in place): remote-authorization", text)
        self.assertIn("gentle-ai sync --agent hermes", text)
        self.assertIn("next new session", text)
        self.assertNotIn(CANARY, text)
        self.assertEqual(self.read(), EXPECTED)
        self.assertEqual(stat.S_IMODE(self.soul.stat().st_mode), 0o604)
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), REAL_LIKE)
        self.assertRegex(backups[0].name, r"^SOUL\.md\.hermes-odd-bak-\d{8}T\d{6}Z")
        # Second apply: nothing to do, no new backup.
        again = self.command().handle("apply confirm")
        self.assertIn("nothing to do", again)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.read(), EXPECTED)
        # Hermes' loader sees the lifted block and the user text.
        report = soul_mod.read_soul(self.home)
        self.assertEqual([b.label for b in report.blocks], ["persona", "remote-authorization"])

    def test_apply_needs_confirm(self) -> None:
        self.write(REAL_LIKE)
        for raw in ("apply", "apply persona", "apply now", "apply confirm extra"):
            with self.subTest(raw=raw):
                out = self.command().handle(raw)
                self.assertTrue("Not applied" in out or out.startswith("Usage"), out)
        self.assertEqual(self.read(), REAL_LIKE)

    def test_stale_plan_is_refused(self) -> None:
        self.write(REAL_LIKE)
        plan = sc.plan_cleanup(self.home)
        self.write(REAL_LIKE + "edited\n")
        result = sc.apply_cleanup(plan)
        self.assertFalse(result.written)
        self.assertIn("changed since the plan", result.error)
        self.assertEqual(self.read(), REAL_LIKE + "edited\n")

    def test_atomic_write_failure_leaves_original(self) -> None:
        self.write(REAL_LIKE)
        with mock.patch("hermes_odd.soul_persona.os.replace", side_effect=OSError("disk")):
            out = self.command().handle("apply confirm")
        self.assertIn("not applied", out)
        self.assertEqual(self.read(), REAL_LIKE)
        self.assertEqual([p.name for p in self.home.iterdir() if "tmp" in p.name], [])

    def test_post_write_check_reports_a_bad_write(self) -> None:
        self.write(REAL_LIKE)
        plan = sc.plan_cleanup(self.home)
        real_write = sp.atomic_write

        def corrupt(path, text, mode):
            real_write(path, text + "tampered", mode)

        with mock.patch("hermes_odd.soul_persona.atomic_write", side_effect=corrupt):
            result = sc.apply_cleanup(plan)
        self.assertTrue(result.written)
        self.assertFalse(result.verified)
        self.assertIn("post-write check failed", result.error)
        self.assertIn("/odd_soul restore", result.error)

    def test_backups_rotate_to_five(self) -> None:
        base = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        for index in range(7):
            self.write(REAL_LIKE + f"note {index}\n")
            plan = sc.plan_cleanup(self.home)
            result = sc.apply_cleanup(plan, now=lambda i=index: base + _dt.timedelta(minutes=i))
            self.assertTrue(result.verified)
        backups = self.backups()
        self.assertEqual(len(backups), sp.BACKUP_KEEP)
        self.assertEqual(backups[0].name, "SOUL.md.hermes-odd-bak-20260101T000200Z")
        self.assertEqual(backups[-1].read_text(encoding="utf-8"), REAL_LIKE + "note 6\n")


class RestoreTests(HomeCase):
    def test_round_trip(self) -> None:
        self.write(REAL_LIKE)
        self.command().handle("apply confirm")
        listing = self.command().handle("restore")
        self.assertIn("1. SOUL.md.hermes-odd-bak-", listing)
        self.assertIn(f"{len(REAL_LIKE.strip()):,} chars", listing)
        restored = self.command().handle("restore 1")
        self.assertIn("SOUL.md restored from SOUL.md.hermes-odd-bak-", restored)
        self.assertIn("the previous file is backup", restored)
        self.assertEqual(self.read(), REAL_LIKE)
        backups = self.backups()
        self.assertEqual(len(backups), 2)
        self.assertEqual(
            sorted(p.read_text(encoding="utf-8") for p in backups), sorted([REAL_LIKE, EXPECTED])
        )
        # Undo the restore by name, the same way.
        newest = sc.backups(self.home)[0]
        self.assertEqual(newest.read_text(encoding="utf-8"), EXPECTED)
        self.command().handle(f"restore {newest.name}")
        self.assertEqual(self.read(), EXPECTED)

    def test_invalid_choices(self) -> None:
        self.assertIn("No hermes-odd SOUL.md backups", self.command().handle("restore"))
        self.write(REAL_LIKE)
        self.command().handle("apply confirm")
        for choice in ("9", "0", "../SOUL.md", "SOUL.md", str(self.soul)):
            with self.subTest(choice=choice):
                self.assertIn("not restored", self.command().handle(f"restore {choice}"))
        self.assertEqual(self.read(), EXPECTED)
        same = self.command().handle("restore 1")  # the backup holds the original
        self.assertIn("restored", same)
        # Newest first: 1 = the cleaned file just backed up, 2 = the original.
        self.assertIn("already matches", self.command().handle("restore 2"))


class DoctorTests(HomeCase):
    def test_doctor_recommends_the_plan_when_blocks_are_removable(self) -> None:
        self.write(REAL_LIKE)
        check = check_soul(self.home, soul_mod.ModelContext("m", 1_000_000, "config"))
        self.assertEqual(check.level, WARN)
        self.assertIn("/odd_soul plan", check.hint)
        self.assertIn("4 gentle-ai blocks to remove or move", check.hint)
        self.assertIn("gentle-ai sync --agent hermes", check.hint)
        self.assertNotIn("T9", check.hint)
        self.command().handle("apply confirm")
        check = check_soul(self.home, soul_mod.ModelContext("m", 1_000_000, "config"))
        self.assertNotIn("/odd_soul plan (dry run", check.hint)
        self.assertIn("/odd_soul keeps", check.hint)

    def test_doctor_names_malformed_markers(self) -> None:
        self.write(HEADER + "<!-- gentle-ai:sdd-orchestrator -->\n" + "x" * 40_000)
        check = check_soul(self.home, soul_mod.ModelContext("m", 128_000, "cache"))
        self.assertIn("/odd_soul cannot clean it", check.hint)

    def test_only_hermes_persona_left_passes(self) -> None:
        self.write(personas.render_block("neutral") + "\n\nBe kind.\n")
        check = check_soul(self.home, soul_mod.ModelContext("m", 1_000_000, "config"))
        self.assertEqual(check.level, OK)


class ToolTests(HomeCase):
    def call(self, args) -> dict:
        handler = make_handler(
            home=lambda: self.home, model_context=lambda _h: soul_mod.ModelContext()
        )
        raw = handler(args, task_id="t")
        self.assertIsInstance(raw, str)
        return json.loads(raw)

    def test_schema(self) -> None:
        self.assertEqual(SOUL_TOOL, "odd_soul_apply")
        params = SOUL_SCHEMA["parameters"]
        self.assertEqual(params["required"], ["confirm"])
        self.assertIs(params["additionalProperties"], False)
        self.assertEqual(set(params["properties"]), {"confirm", "plan_id", "remove_gentle_persona"})
        json.dumps(SOUL_SCHEMA)

    def test_dry_run_then_confirm_with_plan_id(self) -> None:
        self.write(REAL_LIKE)
        for bad in (None, {}, {"confirm": "yes"}, {"confirm": True}, {"confirm": False, "x": 1}):
            with self.subTest(args=bad):
                self.assertIn("error", self.call(bad))
        self.assertEqual(self.read(), REAL_LIKE)
        dry = self.call({"confirm": False})
        self.assertTrue(dry["ok"] and dry["dry_run"] and dry["changes"])
        self.assertRegex(dry["plan_id"], r"^[0-9a-f]{12}$")
        self.assertIn("dry run, nothing written", dry["plan"])
        self.assertIn("explicit yes", dry["next"])
        self.assertNotIn(CANARY, json.dumps(dry))
        self.assertEqual(self.read(), REAL_LIKE)
        wrong = self.call({"confirm": True, "plan_id": "000000000000"})
        self.assertIn("does not match", wrong["error"])
        self.assertEqual(self.read(), REAL_LIKE)
        done = self.call({"confirm": True, "plan_id": dry["plan_id"]})
        self.assertTrue(done["ok"] and done["applied"] and done["verified"])
        self.assertTrue(done["backup"].startswith("SOUL.md.hermes-odd-bak-"))
        self.assertEqual(self.read(), EXPECTED)
        again = self.call({"confirm": False})
        self.assertFalse(again["changes"])
        self.assertIsNone(again["plan_id"])

    def test_persona_option_and_changed_file(self) -> None:
        self.write(PERSONA + "\n\n" + ENGRAM + "\n")
        dry = self.call({"confirm": False, "remove_gentle_persona": True})
        refused = self.call(
            {"confirm": True, "plan_id": dry["plan_id"], "remove_gentle_persona": True}
        )
        self.assertIn("no hermes-odd persona block", refused["error"])
        dry = self.call({"confirm": False})
        self.write(PERSONA + "\n\n" + ENGRAM + "\nedited\n")
        stale = self.call({"confirm": True, "plan_id": dry["plan_id"]})
        self.assertIn("does not match", stale["error"])

    def test_handler_never_raises(self) -> None:
        self.write(REAL_LIKE)
        with (
            mock.patch("hermes_odd.soul_cleanup.plan_cleanup", side_effect=RuntimeError("x")),
            self.assertLogs("hermes_odd", level="WARNING"),
        ):
            out = self.call({"confirm": False})
        self.assertIn("failed: RuntimeError", out["error"])

    def test_setup_answer_yes_points_to_the_tool(self) -> None:
        setup = Setup(FakeContext(), home=lambda: self.home, scanner=lambda: None)
        raw = make_setup_handler(setup)(
            {"soul_cleanup": "yes", "apply_persona_to_soul": False}, task_id="t"
        )
        result = json.loads(raw)
        self.assertIn("odd_soul_apply", result["next"])
        self.assertIn("odd_soul_apply dry run", result["summary"])
        no = json.loads(
            make_setup_handler(setup)({"soul_cleanup": "no", "apply_persona_to_soul": False})
        )
        self.assertIsNone(no["next"])


class RegistrationTests(unittest.TestCase):
    def test_command_in_setup_group_and_tool_registered(self) -> None:
        ctx = FakeContext()
        register(ctx)
        self.assertIn("odd-soul", ctx.commands)
        self.assertTrue(ctx.commands["odd-soul"]["args_hint"].startswith("["))
        listing = ctx.commands["odd-commands"]["handler"]("")
        self.assertIn("/odd_soul", listing)
        self.assertEqual(build_registry().get("odd_soul").group, "Setup")
        tool = next(t for t in ctx.tools if t["name"] == SOUL_TOOL)
        self.assertEqual(tool["toolset"], "hermes_odd")

    def test_registered_handler_never_raises_and_never_leaks(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"HERMES_HOME": tmp}),
            mock.patch.dict("sys.modules", {"hermes_constants": None}),
        ):
            Path(tmp, "SOUL.md").write_text(REAL_LIKE, encoding="utf-8")
            ctx = FakeContext()
            register(ctx)
            handler = ctx.commands["odd-soul"]["handler"]
            for raw in (
                "",
                "status",
                "plan",
                "plan persona",
                "apply",
                "apply confirm",
                "apply confirm",
                "restore",
                "restore 1",
                "restore ../../outside/SOUL.md",
                "garbage \x00 args",
                "plan persona extra",
            ):
                out = handler(raw)
                self.assertIsInstance(out, str)
                self.assertTrue(out.strip())
                self.assertLess(len(out), 3500)
                self.assertNotIn(tmp, out)
                self.assertNotIn(CANARY, out)
            self.assertEqual(Path(tmp, "SOUL.md").read_text(encoding="utf-8"), REAL_LIKE)


class SkillTests(unittest.TestCase):
    def load(self, name: str) -> str:
        return (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_engram_protocol_skill(self) -> None:
        text = self.load("engram-protocol")
        fm, _body = parse_frontmatter(text)
        self.assertEqual(fm["name"], "engram-protocol")
        self.assertIn(
            "<!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 "
            "internal/assets/engram/protocol.md -->",
            text,
        )
        for token in (
            "mcp__engram__mem_save",
            "mcp__engram__mem_search",
            "mcp__engram__mem_context",
            "mcp__engram__mem_get_observation",
            "mcp__engram__mem_session_summary",
            "mcp__engram__mem_suggest_topic_key",
            "topic_key",
            "## When to save",
            "## What to save",
            "## Search before asking",
            "## Session close",
            "Engram™",
            "configured as `engram`",
        ):
            self.assertIn(token, text)
        self.assertLessEqual(len(text.encode("utf-8")), 12 * 1024)
        self.assertIsNone(re.search(r"sdd|openspec", text, re.I))
        # Every Engram tool name is bound the Hermes way, never bare.
        self.assertIsNone(re.search(r"(?<![_a-z])mem_save\(", text))

    def test_codegraph_skill(self) -> None:
        text = self.load("codegraph")
        fm, _body = parse_frontmatter(text)
        self.assertEqual(fm["name"], "codegraph")
        self.assertIn("internal/components/communitytool/codegraph_guidance.go -->", text)
        self.assertIn("`codegraph init <project-root>`", text)
        self.assertNotIn("gentle-ai codegraph", text)
        for token in (
            "## Worktree placement",
            "## Required order",
            "`.codegraph/`",
            "codegraph uninit",
            "mcp__codegraph__codegraph_explore",
        ):
            self.assertIn(token, text)
        self.assertLessEqual(len(text.encode("utf-8")), 12 * 1024)
        self.assertIsNone(re.search(r"sdd|openspec", text, re.I))


class SharedMachineryTests(unittest.TestCase):
    def test_cleanup_reuses_persona_io(self) -> None:
        source = (REPO_ROOT / "hermes_odd" / "soul_cleanup.py").read_text(encoding="utf-8")
        self.assertIn("sp.read_soul_file", source)
        self.assertIn("sp.apply_plan", source)
        for forbidden in ("os.replace", "tempfile", "shutil.copy"):
            self.assertNotIn(forbidden, source)

    def test_setup_state_unaffected(self) -> None:
        # The cleanup never touches plugin state.
        backend = MemoryBackend()
        Setup(backend=backend)
        self.assertIsNone(backend.get("setup", None))


if __name__ == "__main__":
    unittest.main()
