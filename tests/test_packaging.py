"""Packaging invariants: version surfaces, entry point and skill-dir resolution."""

from __future__ import annotations

import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from fake_context import REPO_ROOT, FakeContext, ensure_repo_on_path

ensure_repo_on_path()

import hermes_odd  # noqa: E402
from hermes_odd import skills as skills_mod  # noqa: E402

PYPROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
MANIFEST = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")


def manifest_version() -> str:
    match = re.search(r"(?m)^version:\s*(\S+)\s*$", MANIFEST)
    assert match, "plugin.yaml has no version"
    return match.group(1).strip("\"'")


class VersionSurfaceTests(unittest.TestCase):
    def test_all_version_surfaces_match(self) -> None:
        versions = {
            "pyproject.toml": PYPROJECT["project"]["version"],
            "plugin.yaml": manifest_version(),
            "hermes_odd.__version__": hermes_odd.__version__,
        }
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_version_is_semver(self) -> None:
        self.assertRegex(hermes_odd.__version__, r"^\d+\.\d+\.\d+$")

    def test_manifest_version_is_installable(self) -> None:
        # `hermes plugins install` (plugins_cmd._SUPPORTED_MANIFEST_VERSION)
        # accepts only manifest_version <= 1, although the loader reads v2
        # fields (config_schema, license, ...) regardless of the number.
        match = re.search(r"(?m)^manifest_version:\s*(\d+)\s*$", MANIFEST)
        self.assertIsNotNone(match, "plugin.yaml must declare manifest_version")
        self.assertLessEqual(int(match.group(1)), 1)

    def test_changelog_has_unreleased_section(self) -> None:
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", changelog)


class PyprojectTests(unittest.TestCase):
    def test_name_and_entry_point(self) -> None:
        project = PYPROJECT["project"]
        self.assertEqual(project["name"], "hermes-odd")
        self.assertEqual(project["dependencies"], [])
        eps = project["entry-points"]["hermes_agent.plugins"]
        self.assertEqual(eps, {"hermes-odd": "hermes_odd:register"})

    def test_wheel_maps_skills_and_upstream(self) -> None:
        setuptools = PYPROJECT["tool"]["setuptools"]
        self.assertIn("hermes_odd", setuptools["packages"])
        self.assertIn("hermes_odd.commands", setuptools["packages"])
        self.assertEqual(setuptools["package-dir"]["hermes_odd._skills"], "skills")
        self.assertEqual(setuptools["package-dir"]["hermes_odd._upstream"], "upstream")
        self.assertEqual(
            skills_mod.SKILLS_DIR_CANDIDATES[0],
            Path(skills_mod.__file__).resolve().parent / "_skills",
        )


class SkillsDirResolutionTests(unittest.TestCase):
    def test_git_clone_layout_resolves_repo_skills(self) -> None:
        self.assertEqual(skills_mod.SKILLS_DIR, REPO_ROOT / "skills")

    def test_first_candidate_with_skills_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            full = Path(tmp) / "full"
            (full / "x").mkdir(parents=True)
            (full / "x" / "SKILL.md").write_text("---\n---\n", encoding="utf-8")
            missing = Path(tmp) / "missing"
            self.assertEqual(skills_mod.resolve_skills_dir([missing, empty, full]), full)
            self.assertIsNone(skills_mod.resolve_skills_dir([missing, empty]))

    def test_missing_skills_dir_warns_and_registers_nothing(self) -> None:
        ctx = FakeContext()
        with self.assertLogs("hermes_odd", level="WARNING") as logs:
            self.assertEqual(skills_mod.register_skills(ctx, None), 0)
        self.assertIn("no skills directory found", "\n".join(logs.output))
        self.assertEqual(ctx.skills, {})


if __name__ == "__main__":
    unittest.main()
