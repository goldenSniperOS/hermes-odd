from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from fake_context import (
    REPO_ROOT,
    BareContext,
    FakeContext,
    default_section,
    ensure_repo_on_path,
    mark_setup_complete,
    no_codegraph,
)

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.plugin import register_prompt_section  # noqa: E402
from hermes_odd.prompt import (  # noqa: E402
    SECTION_BUDGET_CHARS,
    SECTION_ID,
    SECTION_MAX_CHARS,
    SKILL_NAMESPACE,
    build_odd_section,
)
from hermes_odd.skills import (  # noqa: E402
    SKILLS_DIR,
    FrontmatterError,
    discover_skills,
    load_skill,
    parse_frontmatter,
    register_skills,
)

SDD_RE = re.compile(r"sdd|openspec", re.IGNORECASE)
ALLOWED_SDD_SENTENCE = "Formal SDD is not provided by this plugin."
# Skills the section may name before their task ships them (none pending).
PENDING_SKILLS: set = set()
SKILL_REF_RE = re.compile(re.escape(SKILL_NAMESPACE) + r":([a-zA-Z0-9_-]+)")


def shipped_skill_names() -> set:
    return {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}


class PromptSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section = build_odd_section({"platform": "telegram"})

    def test_section_within_hard_budget(self) -> None:
        self.assertLessEqual(len(self.section), SECTION_BUDGET_CHARS)
        self.assertLessEqual(SECTION_BUDGET_CHARS, SECTION_MAX_CHARS)
        self.assertLessEqual(SECTION_MAX_CHARS, 4000)  # Hermes MAX_SYSTEM_PROMPT_SECTION_CHARS

    def test_section_is_stripped_and_free_of_reserved_markers(self) -> None:
        self.assertEqual(self.section, self.section.strip())
        self.assertNotIn("hermes-plugin-sections:", self.section)

    def test_section_mentions_sdd_only_in_allowed_sentence(self) -> None:
        self.assertEqual(self.section.count(ALLOWED_SDD_SENTENCE), 1)
        remainder = self.section.replace(ALLOWED_SDD_SENTENCE, "")
        self.assertIsNone(SDD_RE.search(remainder), SDD_RE.findall(remainder))

    def test_section_binds_hermes_tools_and_triggers(self) -> None:
        for token in [
            "delegate_task",
            "`todo`",
            "`clarify`",
            "mcp__engram__mem_save",
            "mcp__engram__mem_context",
            "mcp__engram__mem_search",
            "mcp__engram__mem_get_observation",
            "odd/tasks/<feature>.md",
            "odd/<feature>/tasks",
            "evidence budget",
            "~150k",
        ]:
            self.assertIn(token, self.section)

    def test_section_triggers_are_conditional(self) -> None:
        """gentle-ai v4.2.0: no trigger holds by default; in doubt, work inline."""
        self.assertIn("no trigger holds by default", self.section)
        self.assertIn("in doubt, work inline", self.section)
        self.assertNotIn("Mandatory delegation triggers", self.section)
        self.assertNotIn("past one inline is a defect", self.section)

    def test_section_writer_needs_a_named_reason(self) -> None:
        self.assertIn("2+ independent units", self.section)
        self.assertIn("~100+ changed lines", self.section)
        self.assertIn("never task size or file count", self.section)
        self.assertNotIn("2+ non-trivial files", self.section)

    def test_section_verifier_only_for_named_high_risk_item(self) -> None:
        self.assertIn("names a high-risk item", self.section)
        self.assertIn("cannot be rebuilt", self.section)
        self.assertNotIn("-> a verifier child", self.section)
        # T13: RDD references removed from the prompt section
        self.assertNotIn("RDD switch", self.section)
        self.assertNotIn("rdd-review", self.section)

    def test_every_referenced_skill_is_shipped(self) -> None:
        referenced = set(SKILL_REF_RE.findall(self.section))
        self.assertIn("odd-workflow", referenced)
        self.assertIn("odd-feature-tracking", referenced)
        self.assertIn("odd-delegation", referenced)
        self.assertNotIn("rdd-review", referenced)
        missing = referenced - shipped_skill_names() - PENDING_SKILLS
        self.assertEqual(missing, set())

    def test_pending_skills_are_not_shipped_yet_or_list_is_stale(self) -> None:
        self.assertEqual(PENDING_SKILLS & shipped_skill_names(), set())


def flat(text: str) -> str:
    """Collapse whitespace so phrases match across Markdown line wraps."""
    return " ".join(text.split())


def recall_section(skill: str) -> str:
    """A skill's ``## With the recall provider`` section, flattened, or ``""``."""
    text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    _head, sep, section = text.partition("## With the recall provider")
    return flat(section.split("\n## ", 1)[0]) if sep else ""


class SkillFileTests(unittest.TestCase):
    def test_engram_protocol_covers_the_recall_provider(self) -> None:
        section = recall_section("engram-protocol")
        self.assertTrue(section)
        for phrase in (
            "automatic",
            "plain `mem_*` tools",
            "topic keys",
            "prefer the provider",
            # hermes-recall v0.5.0: session and project are injected, Engram v3
            # mem_update needs the owning project, finalize closes the session.
            "injects the session id and project",
            "`mem_update`",
            "`expected_project`",
            "`mem_get_observation`",
            "`mem_session_finalize`",
        ):
            self.assertIn(phrase, section)
        self.assertNotIn("mcp__engram__", section.replace("`mcp__engram__` prefix", ""))

    def test_engram_protocol_names_expected_project_for_mem_update(self) -> None:
        text = (SKILLS_DIR / "engram-protocol" / "SKILL.md").read_text(encoding="utf-8")
        row_start = "| `mcp__engram__mem_update`"
        table_row = next(ln for ln in text.splitlines() if ln.startswith(row_start))
        self.assertIn("`expected_project`", table_row)
        topic_keys = text[text.index("## Topic keys") :].split("\n## ", 1)[0]
        self.assertIn("`expected_project`", topic_keys)

    def test_feature_tracking_covers_the_recall_provider(self) -> None:
        text = flat((SKILLS_DIR / "odd-feature-tracking" / "SKILL.md").read_text(encoding="utf-8"))
        section = recall_section("odd-feature-tracking")
        self.assertTrue(section)
        for phrase in (
            "plain `mem_*`",
            "`mem_save`",
            "`mem_search`",
            "`mem_get_observation`",
            "`mem_context`",
            "`mem_update`",
            "`expected_project`",
            "`mem_review`",
            "injects the session and project",
            "mirror pending",
        ):
            self.assertIn(phrase, section)
        # The MCP binding stays for setups without recall.
        self.assertIn("`mcp__engram__mem_save`", text)
        self.assertIn("`mcp__engram__mem_update` — `id`, `expected_project`", text)

    def test_delegation_routes_child_memory_through_the_parent_with_recall(self) -> None:
        text = flat((SKILLS_DIR / "odd-delegation" / "SKILL.md").read_text(encoding="utf-8"))
        for phrase in (
            "With the recall provider",
            "refuses writes outside the primary agent",
            "final summary",
            "the parent saves them with `mem_save`",
        ):
            self.assertIn(phrase, text)
        # The MCP instruction stays for setups where the tools reach the child.
        self.assertIn("`mcp__engram__mem_save`", text)

    def test_odd_workflow_triggers_follow_v4_3(self) -> None:
        text = (SKILLS_DIR / "odd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("no trigger holds by default", text)
        self.assertIn("roughly 100+ changed lines", text)
        self.assertIn("cannot be rebuilt", text)
        self.assertNotIn("non-trivial files", text)
        self.assertNotIn("Mandatory, not advisory.", text)

    def test_odd_delegation_verifier_only_for_named_item(self) -> None:
        text = (SKILLS_DIR / "odd-delegation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("names the high-risk item", text)
        self.assertNotIn("raises the tier", text)
        self.assertNotIn("High or unclear", text)

    def test_no_skill_claims_rdd_on_hermes(self) -> None:
        """T13: upstream excludes Hermes from RDD; skills only offer advisory review."""
        for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            body = "\n".join(
                ln
                for ln in path.read_text(encoding="utf-8").splitlines()
                if not ln.startswith("<!-- derived-from:")
            )
            with self.subTest(skill=path.parent.name):
                self.assertNotRegex(body, r"\bRDD\b|receipt-driven|rdd-review|odd-review-mode")

    def test_every_skill_has_valid_frontmatter(self) -> None:
        dirs = sorted(p.parent for p in SKILLS_DIR.glob("*/SKILL.md"))
        self.assertTrue(dirs)
        for skill_dir in dirs:
            with self.subTest(skill=skill_dir.name):
                spec = load_skill(skill_dir)
                self.assertEqual(spec.name, skill_dir.name)
                self.assertTrue(spec.description)
                self.assertLessEqual(len(spec.description), 1024)
                hermes = spec.frontmatter["metadata"]["hermes"]
                self.assertTrue(hermes["tags"])
                self.assertTrue(hermes["category"])

    def test_skills_carry_no_sdd_instructions(self) -> None:
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8").replace(ALLOWED_SDD_SENTENCE, "")
                self.assertIsNone(SDD_RE.search(text), SDD_RE.findall(text))
                # Only the SDD-free port may name its own trigger phrase.
                if path.parent.name != "judgment-day":
                    self.assertNotIn("judgment day", text.lower())

    def test_skills_stay_small(self) -> None:
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            with self.subTest(skill=path.parent.name):
                self.assertLessEqual(len(path.read_bytes()), 12 * 1024)

    def test_skills_avoid_hermes_injection_patterns(self) -> None:
        # tools/skills_tool.py _INJECTION_PATTERNS logs a warning on load.
        # Split literal: Hermes' install scanner (tools/plugin_guard.py) blocks
        # a plugin whose files contain this phrase verbatim, tests included.
        patterns = [
            "ignore previous " + "instructions",
            "ignore all previous",
            "you are now",
            "disregard your",
            "forget your instructions",
            "new instructions:",
            "system prompt:",
            "<system>",
            "]]>",
        ]
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8").lower()
            for pattern in patterns:
                self.assertNotIn(pattern, text, f"{path.parent.name}: {pattern}")


PORTABLE_SKILLS = ("judgment-day", "work-unit-commits", "chained-pr")
# A portable skill name without the ``hermes-odd:`` prefix points to a
# same-named bare skill outside this plugin (for example in ~/.hermes/skills).
BARE_REF_RE = re.compile(r"(?<![:\w-])(judgment-day|work-unit-commits|chained-pr)(?![\w-])")


class PortableSkillTests(unittest.TestCase):
    def test_section_points_to_portable_skills_by_qualified_name(self) -> None:
        section = build_odd_section()
        for name in PORTABLE_SKILLS:
            self.assertIn(f"{SKILL_NAMESPACE}:{name}", section)
        self.assertIn("never a same-named bare skill", section)

    def test_skills_reference_portable_skills_only_qualified(self) -> None:
        for path in SKILLS_DIR.glob("*/SKILL.md"):
            _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            body = re.sub(r"<!-- derived-from: .*? -->", "", body)
            with self.subTest(skill=path.parent.name):
                bare = [m.group(1) for m in BARE_REF_RE.finditer(body)]
                self.assertEqual(bare, [], "reference hermes-odd:<name>, not a bare skill")

    def test_oversized_delivery_menu_offers_a_single_pr_last(self) -> None:
        # gentle-shell 2843a599: three ordered outcomes in the user's language,
        # the single PR least recommended and outside the chain strategies.
        text = (SKILLS_DIR / "chained-pr" / "SKILL.md").read_text(encoding="utf-8")
        menu = text[text.index("## 2. Oversized delivery menu") :]
        menu = menu[: menu.index("\n## 3.")]
        tokens = ("feature-branch-chain", "stacked-to-main", "single-pr")
        order = [menu.index(f"(`{token}`)") for token in tokens]
        self.assertEqual(order, sorted(order))
        for token in (
            "least recommended",
            "user's language",
            "not a chain strategy",
            "Never switch to `exception-ok`",
            "destination repository's",
        ):
            self.assertIn(token, menu)

    def test_judgment_day_is_advisory_and_bounded(self) -> None:
        raw = (SKILLS_DIR / "judgment-day" / "SKILL.md").read_text(encoding="utf-8")
        text = " ".join(raw.split())
        for token in (
            "no receipt",
            "no delivery authority",
            "delegate_task",
            "exactly once with `clarify`",
            "at most two",
            "There is no third round",
            "hermes-odd:advisory-review-lenses",
            "never run both",
            "JUDGMENT: APPROVED",
            "JUDGMENT: ESCALATED",
        ):
            self.assertIn(token, text)

    def test_commit_rules_live_in_one_skill(self) -> None:
        workflow = (SKILLS_DIR / "odd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        commits = (SKILLS_DIR / "work-unit-commits" / "SKILL.md").read_text(encoding="utf-8")
        chained = (SKILLS_DIR / "chained-pr" / "SKILL.md").read_text(encoding="utf-8")
        # The advisory per-task heuristic and the delivery strategies each
        # have one home; odd-workflow only points to them.
        self.assertIn("Never shrink a diff cosmetically", commits)
        self.assertNotIn("planning heuristic", workflow)
        self.assertNotIn("planning heuristic", chained)
        for token in ("`ask-on-risk` (default)", "`feature-branch-chain`", "400"):
            self.assertIn(token, chained)
        self.assertNotIn("`ask-on-risk` (default)", workflow)
        self.assertIn("hermes-odd:work-unit-commits", workflow)
        self.assertIn("hermes-odd:chained-pr", workflow)


def skill_text(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def skill_part(name: str, heading: str) -> str:
    """One ``## `` section of a skill, flattened."""
    text = skill_text(name)
    return flat(text[text.index(heading) :].split("\n## ", 1)[0])


class UpstreamSync202611Tests(unittest.TestCase):
    """Upstream sync 2026-11 (gentle-ai 1ab243c, gentle-shell a1c4463), T2."""

    def setUp(self) -> None:
        self.section = flat(build_odd_section())

    def test_r1_authorized_work_continues(self) -> None:
        # gentle-ai #6145 / gentle-shell #3286
        self.assertIn("pending child is a wait", self.section)
        self.assertIn("the work it covers", self.section)
        workflow = flat(skill_text("odd-workflow"))
        for phrase in (
            "without per-step approval",
            "pending child is a wait",
            "Hedged wording is not a stop",
            "never independent authorized work",
            "blocks the completion claim",
            "never cancels the objective",
        ):
            self.assertIn(phrase, workflow)
        delegation = flat(skill_text("odd-delegation"))
        self.assertNotIn("**Needs your decision**", delegation)
        self.assertIn("stays `partial`", delegation)

    def test_r2_informed_short_approval(self) -> None:
        # gentle-ai #5850
        self.assertIn("immediately preceding concrete proposal", self.section)
        workflow = flat(skill_text("odd-workflow"))
        for phrase in (
            "immediately preceding concrete proposal",
            "never re-ask",
            "preference alone is not authorization",
            "publish or destructive",
            "needs to understand",
        ):
            self.assertIn(phrase, workflow)

    def test_r3_task_size_replaces_substantial(self) -> None:
        for phrase in ("resumable", "`git diff`", "large only when"):
            self.assertIn(phrase, self.section)
        workflow = flat(skill_text("odd-workflow"))
        for phrase in ("Task size", "resume test", "`git diff` alone", "never decide"):
            self.assertIn(phrase, workflow)
        for path in [*SKILLS_DIR.glob("*/SKILL.md")]:
            with self.subTest(skill=path.parent.name):
                self.assertNotIn("substantial", path.read_text(encoding="utf-8").lower())
        self.assertNotIn("substantial", self.section.lower())

    def test_r4_writers_launch_together_with_surfaces(self) -> None:
        # gentle-ai #6070 / #6084
        self.assertIn("in one turn", self.section)
        delegation = flat(skill_text("odd-delegation"))
        for phrase in (
            "in one turn",
            "passes the full list again",
            "repaired once",
            "never resent unchanged",
            "adds the path itself",
            "the parent owns git",
            "repository-wide formatters",
            "one owner",
            "one seam check",
            "helpers",
        ):
            self.assertIn(phrase, delegation)
        self.assertNotIn("Never run two writers in the same worktree", delegation)

    def test_r5_verifier_works_by_change_kind(self) -> None:
        # gentle-ai #6072 / gentle-shell #3101
        verify = skill_part("odd-delegation", "## 3.")
        for phrase in (
            "change kind",
            "does not re-run the writer's suite",
            "`mktemp -d`",
            "rejected command",
            "at the baseline",
            "become tests",
        ):
            self.assertIn(phrase, verify)

    def test_r6_children_do_not_re_read_and_report_briefly(self) -> None:
        # gentle-ai #6090 / gentle-shell #3092
        delegation = flat(skill_text("odd-delegation"))
        for phrase in (
            "does not re-read",
            "~2k tokens",
            "never restating",
            "`git status --short`",
            "outside the worktree",
            "no commit skill",
        ):
            self.assertIn(phrase, delegation)

    def test_r7_file_is_the_source(self) -> None:
        # gentle-ai #6073 / gentle-shell #3083
        self.assertIn("file is the source", self.section)
        tracking = flat(skill_text("odd-feature-tracking"))
        for phrase in (
            "file is the source",
            "never author reconciliation scripts",
            "never replay",
            "once per task transition",
            "## Specs",
            "## Log",
            "verbatim",
            "`dropped`",
            "`blocked`",
            "read until `## Log`",
        ):
            self.assertIn(phrase, tracking)
        self.assertLess(tracking.index("## Tasks"), tracking.index("## Log"))
        delegation = flat(skill_text("odd-delegation"))
        self.assertIn("read until `## Log`", delegation)
        self.assertIn("which `S#`", delegation)

    def test_r8_engram_saves_once_before_the_answer(self) -> None:
        # gentle-ai #6069
        when = skill_part("engram-protocol", "## When to save")
        for phrase in ("saved once", "share a turn", "before your final answer"):
            self.assertIn(phrase, when)
        self.assertNotIn("right after", skill_text("engram-protocol"))

    def test_r9_commit_slices_and_ceiling(self) -> None:
        # gentle-ai #6071 + render step 6
        text = skill_text("work-unit-commits")
        commits = flat(text)
        for phrase in ("ceiling", "its own commit", "high-risk item"):
            self.assertIn(phrase, commits)
        fm, _ = parse_frontmatter(text)
        self.assertNotIn("implementation", fm["description"].lower())

    def test_r10_tests_per_rule_and_preserved_behavior(self) -> None:
        checks = skill_part("odd-workflow", "## 6.")
        for phrase in (
            "one RED test per requested rule",
            "previous behavior",
            "differential check",
            "`mktemp -d`",
            "help text",
        ):
            self.assertIn(phrase, checks)

    def test_r11_explicit_request_runs_advisory_review(self) -> None:
        # gentle-ai #6091
        when = skill_part("advisory-review-lenses", "## When to run it")
        self.assertIn("even when no rule", when)


class FrontmatterParserTests(unittest.TestCase):
    def test_parses_nested_metadata_and_lists(self) -> None:
        fm, body = parse_frontmatter(
            '---\nname: x\ndescription: "a: b"\nmetadata:\n  hermes:\n'
            "    tags: [one, two]\n    category: c\n---\nbody\n"
        )
        self.assertEqual(fm["description"], "a: b")
        self.assertEqual(fm["metadata"]["hermes"]["tags"], ["one", "two"])
        self.assertEqual(body, "body\n")

    def test_rejects_missing_fence(self) -> None:
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("# no frontmatter\n")

    def test_invalid_skill_is_skipped_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad-skill"
            bad.mkdir()
            (bad / "SKILL.md").write_text("---\nname: other\n---\n", encoding="utf-8")
            with self.assertLogs("hermes_odd", level="WARNING"):
                self.assertEqual(discover_skills(Path(tmp)), [])


class RegistrationTests(unittest.TestCase):
    def test_register_adds_section_and_all_skills(self) -> None:
        ctx = FakeContext()
        register(ctx)
        self.assertEqual(len(ctx.prompt_sections), 1)
        section = ctx.prompt_sections[0]
        self.assertEqual(section["id"], SECTION_ID)
        self.assertEqual(section["max_chars"], SECTION_MAX_CHARS)
        self.assertTrue(callable(section["content"]))
        # A fresh install is pending setup; once complete the text is the base
        # section plus the default Engram pointer (no CodeGraph here).
        with no_codegraph():
            self.assertEqual(
                section["content"]({"platform": "cli", "cwd": ""}), default_section(pending=True)
            )
            mark_setup_complete(ctx.state)
            self.assertEqual(section["content"]({"platform": "cli", "cwd": ""}), default_section())
        self.assertTrue(default_section().startswith(build_odd_section()))
        self.assertEqual(set(ctx.skills), shipped_skill_names())
        for name, entry in ctx.skills.items():
            self.assertEqual(entry["path"], SKILLS_DIR / name / "SKILL.md")
            self.assertTrue(entry["description"])
            self.assertEqual(entry["frontmatter"]["name"], name)
        self.assertIn("odd-commands", ctx.commands)

    def test_section_id_is_hermes_valid(self) -> None:
        self.assertRegex(SECTION_ID, r"^[a-z0-9][a-z0-9._-]{0,127}$")

    def test_missing_methods_are_skipped_without_raising(self) -> None:
        with self.assertLogs("hermes_odd", level="WARNING") as logs:
            register(BareContext())
        joined = "\n".join(logs.output)
        self.assertIn("register_system_prompt_section is unavailable", joined)
        self.assertIn("register_skill is unavailable", joined)

    def test_raising_section_and_skill_registration_do_not_raise(self) -> None:
        class Raising(FakeContext):
            def register_system_prompt_section(self, *a, **k):
                raise ValueError("duplicate")

            def register_skill(self, *a, **k):
                raise ValueError("bad")

        ctx = Raising()
        with self.assertLogs("hermes_odd", level="WARNING"):
            register(ctx)
        self.assertIn("odd-commands", ctx.commands)
        self.assertFalse(register_prompt_section(Raising()))
        self.assertEqual(register_skills(Raising()), 0)


class CanonicalProvenanceTests(unittest.TestCase):
    def test_vendored_render_matches_its_sha(self) -> None:
        import hashlib

        raw = (REPO_ROOT / "upstream" / "odd-routing-hermes.canonical.md").read_text(
            encoding="utf-8"
        )
        header, _, body = raw.partition("\n-->\n")
        fields = dict(line.split(": ", 1) for line in header.splitlines()[1:] if ": " in line)
        self.assertEqual(fields["agent_id"], "hermes")
        self.assertRegex(fields["source_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), fields["block_sha256"])
        self.assertTrue(body.startswith("## Implementation Routing"))

    def test_hermes_render_is_odd_only_and_test_first(self) -> None:
        # gentle-ai 5ffb65fc: Hermes is not an RDD runtime, so its render has
        # no review clauses; 55e3abf1: one default applicable test-first policy.
        raw = (REPO_ROOT / "upstream" / "odd-routing-hermes.canonical.md").read_text(
            encoding="utf-8"
        )
        body = raw.partition("\n-->\n")[2]
        for gone in ("gentle-ai review", "receipt", "RDD", "configured TDD", "SDD"):
            self.assertNotIn(gone, body)
        self.assertIn("the default applicable test-first policy", body)
        self.assertIn("Verification covers a work-unit commit or a PR slice", body)
        # hermes-odd carries the same policy in its own words, and no TDD mode.
        section = build_odd_section()
        workflow = (SKILLS_DIR / "odd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        delegation = (SKILLS_DIR / "odd-delegation" / "SKILL.md").read_text(encoding="utf-8")
        for text in (section, workflow, delegation):
            self.assertNotIn("TDD mode", text)
            self.assertNotIn("configured TDD", text)
            self.assertIn("RED", text)
        self.assertIn("Presence is not applicability", workflow)
        self.assertIn("Test-first: applies, runner <exact command> | exception:", delegation)
        # T13: RDD review line removed from the prompt section
        self.assertNotIn("no native RDD review on Hermes", section)

    def test_routing_uses_the_evidence_budget(self) -> None:
        # gentle-ai 991c3d06 / gentle-shell 14bd2356: an evidence budget
        # replaces the 1-3 / 4+ file counts and the tool-call backstop.
        raw = (REPO_ROOT / "upstream" / "odd-routing-hermes.canonical.md").read_text(
            encoding="utf-8"
        )
        body = raw.partition("\n-->\n")[2]
        section = build_odd_section()
        workflow = (SKILLS_DIR / "odd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        for text in (body, section, workflow):
            for token in ("at most 3 calls", "~10k tokens", "~2k tokens", "~150k"):
                self.assertIn(token, text.replace("approximately ", "~"))
            for gone in (
                "4+ files",
                "4 or more files",
                "20 tool calls",
                "1-3 known files",
                "1–3 files",
                "1-3 file",
            ):
                self.assertNotIn(gone, text)

    def test_work_stays_inside_the_project_root(self) -> None:
        # gentle-shell e2d85a47: work outside the project root needs explicit,
        # per-target consent. Hermes has no guard hook, so this is guidance.
        section = build_odd_section()
        workflow = (SKILLS_DIR / "odd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("outside the project root", section)
        self.assertIn("absolute path", section)
        for token in (
            "outside the project root",
            "absolute path",
            "same clone",
            "per target",
            "not standing consent",
        ):
            self.assertIn(token, workflow)


class UpstreamSync202611LateTests(unittest.TestCase):
    """T2b: Engram and CodeGraph guidance found by the T16 triage."""

    def setUp(self) -> None:
        self.engram = (SKILLS_DIR / "engram-protocol" / "SKILL.md").read_text(encoding="utf-8")
        self.codegraph = (SKILLS_DIR / "codegraph" / "SKILL.md").read_text(encoding="utf-8")

    def test_engram_resolves_project_before_first_read(self) -> None:
        # gentle-ai 1c76e86a (#2022)
        flat = " ".join(self.engram.split())
        for token in (
            "wait for its result",
            "`available_projects`",
            "never pass it as `project`",
            "Never invent a project name",
            "explicitly asks to recall",
        ):
            self.assertIn(token, flat)

    def test_engram_content_is_one_string(self) -> None:
        # gentle-ai 4bae61e2 (#5663)
        flat = " ".join(self.engram.split())
        self.assertIn("one plain string", flat)
        self.assertIn('"What: ', flat)

    def test_codegraph_worktree_init_target_and_fresh_cli_reads(self) -> None:
        # gentle-ai bc27d9e0 (#4151), 12c1a157, e6a6e949, 69da4962
        flat = " ".join(self.codegraph.split())
        for token in (
            "immediate parent directory of the repository root",
            "working directory is authoritative",
            "never retry initialization against the parent",
            "codegraph sync -q <project-root>",
            "do not auto-sync",
        ):
            self.assertIn(token, flat)


if __name__ == "__main__":
    unittest.main()
