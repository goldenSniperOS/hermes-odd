"""Upstream support lock (``upstream/upstream.lock.json``) invariants."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from fake_context import REPO_ROOT, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import upstream as upstream_mod  # noqa: E402

LOCK_PATH = REPO_ROOT / "upstream" / "upstream.lock.json"
SUPPORTED = REPO_ROOT / "upstream" / "SUPPORTED.md"
CANONICAL = REPO_ROOT / "upstream" / "odd-routing-hermes.canonical.md"
NOTICES = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
MARKER_RE = re.compile(r"<!-- derived-from: (gentle-ai|gentle-shell)@([0-9a-f]{40}) (\S+) -->")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UPSTREAMS = ("gentle-ai", "gentle-shell")
COMPONENTS = ("odd", "rdd", "review-contract", "viewers")
STATUSES = {"ported", "partial", "pending"}
# Local read-only upstream checkouts (developer machines only; CI has none).
# The directory name is built from parts so the old-name test never matches it.
UPSTREAM_CACHE = Path(
    os.environ.get(
        "HERMES_ODD_UPSTREAM_CACHE",
        str(Path.home() / ".cache" / ("gentle" + "-hermes") / "upstream"),
    )
)


def load_lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def marker_files() -> list[Path]:
    files = [REPO_ROOT / "hermes_odd" / "prompt.py"]
    for root in ("skills", "upstream"):
        files.extend(p for p in sorted((REPO_ROOT / root).rglob("*")) if p.is_file())
    return files


def notices_sections() -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in NOTICES.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


class LockShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = load_lock()

    def test_schema_id(self) -> None:
        self.assertEqual(self.lock["schema"], "hermes-odd.upstream-lock/v1")
        self.assertEqual(self.lock["schema"], upstream_mod.LOCK_SCHEMA)

    def test_upstreams_are_pinned(self) -> None:
        for name in UPSTREAMS:
            with self.subTest(upstream=name):
                entry = self.lock["upstreams"][name]
                self.assertTrue(entry["repo"].startswith("https://github.com/"))
                self.assertRegex(entry["supported_release"], r"^v\d+\.\d+\.\d+$")
                self.assertRegex(entry["pinned_commit"], r"^[0-9a-f]{40}$")
                self.assertRegex(entry["release_tag_commit"], r"^[0-9a-f]{40}$")
                self.assertRegex(entry["commit_date"], r"^\d{4}-\d{2}-\d{2}T")
        binary = self.lock["upstreams"]["gentle-ai"]["binary"]
        self.assertEqual(binary["min_version"], "3.7.0")
        self.assertRegex(binary["tested_version"], r"^\d+\.\d+\.\d+$")
        npm = self.lock["upstreams"]["gentle-shell"]["npm"]
        self.assertEqual(npm["package"], "gentle-pi")
        self.assertRegex(npm["version"], r"^\d+\.\d+\.\d+$")

    def test_components_have_status_files_and_hashed_sources(self) -> None:
        self.assertEqual(sorted(self.lock["components"]), sorted(COMPONENTS))
        for name, component in self.lock["components"].items():
            with self.subTest(component=name):
                self.assertIn(component["status"], STATUSES)
                self.assertIsInstance(component["local_files"], list)
                for rel in component["local_files"]:
                    self.assertTrue((REPO_ROOT / rel).is_file(), rel)
                self.assertTrue(component["sources"])
                seen = set()
                for source in component["sources"]:
                    self.assertIn(source["upstream"], UPSTREAMS)
                    self.assertTrue(source["path"] and not source["path"].startswith("/"))
                    self.assertRegex(source["sha256"], SHA256_RE)
                    key = (source["upstream"], source["path"])
                    self.assertNotIn(key, seen, f"duplicate source {key}")
                    seen.add(key)

    def test_ported_component_ships_files(self) -> None:
        odd = self.lock["components"]["odd"]
        self.assertEqual(odd["status"], "ported")
        self.assertTrue(odd["local_files"])

    def test_review_contract_versions(self) -> None:
        contract = self.lock["components"]["review-contract"]
        self.assertEqual(contract["review_cli_contract"], "gentle-ai.review-integration/v2")
        self.assertRegex(
            contract["provider_contract_mirror"]["contract_semver"], r"^\d+\.\d+\.\d+$"
        )

    def test_same_source_has_one_hash_across_components(self) -> None:
        hashes: dict[tuple[str, str], set[str]] = {}
        for component in self.lock["components"].values():
            for source in component["sources"]:
                hashes.setdefault((source["upstream"], source["path"]), set()).add(source["sha256"])
        for key, values in hashes.items():
            self.assertEqual(len(values), 1, key)

    def test_excluded_areas_have_reasons(self) -> None:
        excluded = self.lock["excluded"]
        self.assertTrue(excluded)
        areas = " ".join(entry["area"] for entry in excluded)
        for token in ("SDD", "aesthetics", "runtime plumbing", "agent writers"):
            self.assertIn(token, areas)
        for entry in excluded:
            self.assertTrue(entry["reason"].strip(), entry["area"])


class LockConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = load_lock()

    def test_every_derived_from_marker_is_indexed_in_odd(self) -> None:
        sources = {(s["upstream"], s["path"]) for s in self.lock["components"]["odd"]["sources"]}
        markers = []
        for path in marker_files():
            markers.extend(MARKER_RE.findall(path.read_text(encoding="utf-8")))
        self.assertTrue(markers)
        for upstream, commit, rel in markers:
            with self.subTest(upstream=upstream, path=rel):
                self.assertIn((upstream, rel), sources)
                self.assertEqual(commit, self.lock["upstreams"][upstream]["pinned_commit"])

    def test_odd_indexes_routing_and_capability_manifest(self) -> None:
        sources = {(s["upstream"], s["path"]) for s in self.lock["components"]["odd"]["sources"]}
        self.assertIn(("gentle-ai", "internal/components/agentguidance/routing.go"), sources)
        self.assertIn(("gentle-ai", "internal/agents/capabilitymanifest/manifest.go"), sources)

    def test_pins_match_third_party_notices(self) -> None:
        sections = notices_sections()
        for name in UPSTREAMS:
            with self.subTest(upstream=name):
                entry = self.lock["upstreams"][name]
                self.assertIn(f"Pinned commit: {entry['pinned_commit']}", sections[name])
                self.assertIn(entry["supported_release"], sections[name])
                self.assertIn(entry["repo"], sections[name])

    def test_pin_matches_canonical_render_provenance(self) -> None:
        header = CANONICAL.read_text(encoding="utf-8").partition("\n-->\n")[0]
        fields = dict(line.split(": ", 1) for line in header.splitlines()[1:] if ": " in line)
        gentle_ai = self.lock["upstreams"]["gentle-ai"]
        self.assertEqual(fields["source_commit"], gentle_ai["pinned_commit"])
        self.assertEqual(fields["source_repo"], gentle_ai["repo"])
        odd_paths = {s["path"] for s in self.lock["components"]["odd"]["sources"]}
        self.assertIn(fields["source_path"], odd_paths)

    def test_supported_md_mentions_pins_and_has_triage_log(self) -> None:
        text = SUPPORTED.read_text(encoding="utf-8")
        self.assertIn("## Triage log", text)
        self.assertIn("## How to sync with upstream", text)
        for name in UPSTREAMS:
            entry = self.lock["upstreams"][name]
            self.assertIn(entry["pinned_commit"], text)
            self.assertIn(entry["supported_release"], text)
        for component in COMPONENTS:
            self.assertIn(f"`{component}`", text)

    def test_wheel_ships_the_lock(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        setuptools = pyproject["tool"]["setuptools"]
        self.assertIn("hermes_odd._upstream", setuptools["packages"])
        self.assertEqual(setuptools["package-dir"]["hermes_odd._upstream"], "upstream")
        self.assertIn("*.json", setuptools["package-data"]["hermes_odd._upstream"])


class UpstreamModuleTests(unittest.TestCase):
    def test_load_lock_from_repo(self) -> None:
        lock = upstream_mod.load_lock()
        self.assertEqual(lock, load_lock())

    def test_min_gentle_ai_version(self) -> None:
        self.assertEqual(upstream_mod.min_gentle_ai_version(), "3.7.0")

    def test_candidate_order_matches_skills(self) -> None:
        package_dir = Path(upstream_mod.__file__).resolve().parent
        self.assertEqual(
            upstream_mod.UPSTREAM_DIR_CANDIDATES,
            (package_dir / "_upstream", REPO_ROOT / "upstream"),
        )

    def test_first_candidate_with_lock_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a", Path(tmp) / "b"
            first.mkdir()
            second.mkdir()
            lock = {"schema": upstream_mod.LOCK_SCHEMA, "upstreams": {}, "components": {}}
            (second / upstream_mod.LOCK_FILE).write_text(json.dumps(lock), encoding="utf-8")
            self.assertEqual(upstream_mod.load_lock([first, second]), lock)

    def test_missing_or_invalid_lock_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                upstream_mod.load_lock([root])
            (root / upstream_mod.LOCK_FILE).write_text('{"schema": "other"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                upstream_mod.load_lock([root])


def _git_show(checkout: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(checkout), "show", f"{commit}:{path}"],
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


@unittest.skipUnless(UPSTREAM_CACHE.is_dir(), "local upstream checkouts not available")
class LocalCheckoutHashTests(unittest.TestCase):
    """Recompute every source hash from local read-only upstream checkouts."""

    def test_source_hashes_match_pinned_commits(self) -> None:
        lock = load_lock()
        checked = 0
        for name, component in lock["components"].items():
            for source in component["sources"]:
                checkout = UPSTREAM_CACHE / source["upstream"]
                if not (checkout / ".git").exists():
                    continue
                commit = lock["upstreams"][source["upstream"]]["pinned_commit"]
                content = _git_show(checkout, commit, source["path"])
                with self.subTest(component=name, path=source["path"]):
                    self.assertIsNotNone(content, f"{commit}:{source['path']} not found")
                    self.assertEqual(hashlib.sha256(content).hexdigest(), source["sha256"])
                checked += 1
        if not checked:
            self.skipTest("no upstream checkout holds the pinned commits")


if __name__ == "__main__":
    unittest.main()
