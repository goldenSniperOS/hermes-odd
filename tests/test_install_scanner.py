"""Guards that ``hermes plugins install`` does not block this repository.

``hermes plugins install`` runs ``tools.plugin_guard.scan_plugin`` on the
cloned tree. GitHub sources get ``community`` trust, so any high-severity
finding yields a ``caution`` verdict and blocks the install.

The full scanner check needs Hermes and only runs with its venv interpreter::

    ~/.hermes/hermes-agent/venv/bin/python -m unittest tests.test_install_scanner -v

``HERMES_AGENT_DIR`` overrides the Hermes checkout location. The stdlib-only
check below guards the known blocker on CI, where Hermes is absent.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Computed here (not imported from fake_context) so the module also runs as
# ``tests.test_install_scanner`` from the repository root.
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = "goldenSniperOS/hermes-odd"
HERMES_AGENT_DIR = Path(
    os.environ.get("HERMES_AGENT_DIR", str(Path.home() / ".hermes" / "hermes-agent"))
).expanduser()
# Built from parts so this file never matches its own pattern.
PRIVILEGE_WORD_RE = re.compile(r"\b" + "su" + "do" + r"\b", re.IGNORECASE)
THIS_FILE = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()


def _load_plugin_guard():
    """Import ``tools.plugin_guard`` from Hermes, or return ``None``."""
    added = False
    if HERMES_AGENT_DIR.is_dir() and str(HERMES_AGENT_DIR) not in sys.path:
        sys.path.insert(0, str(HERMES_AGENT_DIR))
        added = True
    try:
        from tools import plugin_guard
    except Exception:
        if added:
            sys.path.remove(str(HERMES_AGENT_DIR))
        return None
    return plugin_guard


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def copy_tracked_tree(dest: Path) -> None:
    for name in tracked_files():
        src = REPO_ROOT / name
        if not src.is_file() or src.is_symlink():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


plugin_guard = _load_plugin_guard()


@unittest.skipIf(plugin_guard is None, "tools.plugin_guard (Hermes) is not importable")
class InstallScannerTests(unittest.TestCase):
    def test_tracked_tree_scans_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "hermes-odd"
            plugin_dir.mkdir()
            copy_tracked_tree(plugin_dir)
            result = plugin_guard.scan_plugin(plugin_dir, SOURCE)
        blocking = [
            f"{f.severity} {f.pattern_id} {f.file}:{f.line} {f.match!r}"
            for f in result.findings
            if f.severity in {"high", "critical"}
        ]
        self.assertEqual(
            result.verdict,
            "safe",
            "install scanner verdict is not safe; high/critical findings:\n"
            + "\n".join(blocking or ["(none; check lower-severity findings)"]),
        )


class KnownBlockerTests(unittest.TestCase):
    def test_no_tracked_text_file_mentions_privilege_escalation_word(self) -> None:
        hits = []
        for name in tracked_files():
            if name == THIS_FILE:
                continue
            path = REPO_ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if PRIVILEGE_WORD_RE.search(line):
                    hits.append(f"{name}:{lineno}: {line.strip()}")
        self.assertEqual(
            hits,
            [],
            "the Hermes install scanner flags this word as high severity:\n" + "\n".join(hits),
        )


if __name__ == "__main__":
    unittest.main()
