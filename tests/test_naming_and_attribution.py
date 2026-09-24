"""Project naming (hermes-odd) and upstream attribution invariants."""

from __future__ import annotations

import re
import unittest

from fake_context import REPO_ROOT, FakeContext, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.commands import build_registry  # noqa: E402
from hermes_odd.prompt import SECTION_ID, SKILL_NAMESPACE, build_odd_section  # noqa: E402

# Built from parts so this file never matches its own pattern.
OLD_NAME_RE = re.compile("gentle" + r"[-_ ]" + "hermes", re.IGNORECASE)
EXCLUDED_DIRS = {".git", "__pycache__", ".codegraph", ".atl", "odd"}
DERIVED_RE = re.compile(r"<!-- derived-from: (gentle-ai|gentle-shell)@[0-9a-f]{40} ")
NOTICES = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
COPYRIGHT_LINES = {
    "gentle-ai": "Copyright (c) 2025 Gentleman Programming",
    "gentle-shell": "Copyright (c) 2025 Mario Zechner",
}


def repo_text_files():
    for path in sorted(REPO_ROOT.rglob("*")):
        rel = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts) or not path.is_file():
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def derived_files():
    """Map each upstream name to the repo files carrying its marker."""
    found = {name: set() for name in COPYRIGHT_LINES}
    for rel, text in repo_text_files():
        if rel.parts[0] == "tests" or rel.name == NOTICES.name:
            continue
        for upstream in DERIVED_RE.findall(text):
            found[upstream].add(rel.as_posix())
    return found


def notices_sections():
    sections = {}
    current = None
    for line in NOTICES.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


class OldNameTests(unittest.TestCase):
    def test_no_old_project_name_anywhere(self) -> None:
        offenders = [
            f"{rel}:{text[: m.start()].count(chr(10)) + 1}"
            for rel, text in repo_text_files()
            for m in OLD_NAME_RE.finditer(text)
        ]
        self.assertEqual(offenders, [])


class NamingTests(unittest.TestCase):
    def test_every_command_uses_odd_prefix(self) -> None:
        specs = build_registry().all()
        self.assertTrue(specs)
        for spec in specs:
            self.assertTrue(spec.name.startswith("odd_"), spec.name)
            self.assertTrue(spec.hermes_key.startswith("odd-"), spec.hermes_key)
        ctx = FakeContext()
        register(ctx)
        self.assertTrue(ctx.commands)
        for key in ctx.commands:
            self.assertTrue(key.startswith("odd-"), key)

    def test_section_id_and_skill_namespace(self) -> None:
        self.assertEqual(SECTION_ID, "hermes-odd-workflow")
        self.assertEqual(SKILL_NAMESPACE, "hermes-odd")
        section = build_odd_section()
        self.assertTrue(section.startswith("# ODD workflow (hermes-odd)"))
        refs = re.findall(r"\b([a-z0-9-]+):(odd-[a-z-]+|rdd-[a-z-]+)", section)
        self.assertTrue(refs)
        for namespace, name in refs:
            self.assertEqual(namespace, "hermes-odd", f"{namespace}:{name}")

    def test_manifest_name_and_homepage(self) -> None:
        manifest = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertRegex(manifest, r"(?m)^name: hermes-odd$")
        self.assertIn("homepage: https://github.com/goldenSniperOS/hermes-odd", manifest)


class AttributionTests(unittest.TestCase):
    def test_notices_exist_with_verbatim_copyright_lines(self) -> None:
        self.assertTrue(NOTICES.is_file())
        sections = notices_sections()
        for upstream, line in COPYRIGHT_LINES.items():
            with self.subTest(upstream=upstream):
                self.assertIn(upstream, sections)
                self.assertIn(line, sections[upstream])
                self.assertIn("Permission is hereby granted, free of charge", sections[upstream])

    def test_notices_list_every_derived_file_under_its_upstream(self) -> None:
        found = derived_files()
        self.assertTrue(found["gentle-ai"])
        self.assertTrue(found["gentle-shell"])
        sections = notices_sections()
        for upstream, files in found.items():
            for rel in sorted(files):
                with self.subTest(upstream=upstream, file=rel):
                    self.assertIn(f"`{rel}`", sections[upstream])

    def test_license_points_to_notices(self) -> None:
        license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n\nCopyright (c) 2026 goldenSniperOS"))
        self.assertIn("THIRD_PARTY_NOTICES.md", license_text)

    def test_readme_credits_and_non_affiliation(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for token in [
            "Gentle AI™",
            "Engram™",
            "https://github.com/Gentleman-Programming/gentle-ai",
            "https://github.com/Gentleman-Programming/gentle-shell",
            "https://github.com/NousResearch/hermes-agent",
            "## Credits and acknowledgements",
            "## Not affiliated",
            "gentle-ai sync --agent hermes",
        ]:
            self.assertIn(token, readme)


if __name__ == "__main__":
    unittest.main()
