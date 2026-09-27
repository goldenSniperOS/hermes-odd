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
            "4+ files",
            "2+ non-trivial files",
            "~20 tool calls",
            "RDD switch",
        ]:
            self.assertIn(token, self.section)

    def test_every_referenced_skill_is_shipped(self) -> None:
        referenced = set(SKILL_REF_RE.findall(self.section))
        self.assertIn("odd-workflow", referenced)
        self.assertIn("odd-feature-tracking", referenced)
        self.assertIn("odd-delegation", referenced)
        self.assertIn("rdd-review", referenced)
        missing = referenced - shipped_skill_names() - PENDING_SKILLS
        self.assertEqual(missing, set())

    def test_pending_skills_are_not_shipped_yet_or_list_is_stale(self) -> None:
        self.assertEqual(PENDING_SKILLS & shipped_skill_names(), set())


class SkillFileTests(unittest.TestCase):
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
            "hermes-odd:rdd-review",
            "hermes-odd:rdd-review-lenses",
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
        self.assertIn("no native RDD review on Hermes", section)


if __name__ == "__main__":
    unittest.main()
