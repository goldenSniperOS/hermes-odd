"""Regression: no hermes-odd reply makes a Hermes gateway attach a local file.

Hermes gateways (``gateway/platforms/base.py`` ``extract_local_files``) send
every bare absolute or ``~/`` path with a deliverable extension that exists as
an attachment; paths inside inline code or fenced code blocks are ignored.
Telegram once received ``SOUL.md`` as a document from ``/odd_doctor``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_context import FakeContext, ensure_repo_on_path

ensure_repo_on_path()

from hermes_odd import register  # noqa: E402
from hermes_odd.commands.registry import CommandSpec  # noqa: E402
from hermes_odd.commands.safe_text import TRUNCATED, code_path, gateway_safe  # noqa: E402

# Copy of the gateway scanner. The gateway lists deliverable extensions
# (images, video, audio, documents incl. .md/.json/.txt/.yaml); any extension
# is a superset, because /odd-changes can show files of every kind.
GATEWAY_EXT = r"[A-Za-z0-9]+"
GATEWAY_PATH_RE = re.compile(
    r"(?<![/:\w.])(?:~/|/|[A-Za-z]:[/\\])(?:[\w.\-]+[/\\])*[\w.\-]+\.(?:" + GATEWAY_EXT + r")\b"
)
GATEWAY_CODE_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`")


def gateway_paths(text: str, skip_code: bool = True) -> list[str]:
    """Paths the gateway would try to attach (existence checked separately)."""
    spans = [m.span() for m in GATEWAY_CODE_RE.finditer(text)] if skip_code else []
    return [
        m.group(0)
        for m in GATEWAY_PATH_RE.finditer(text)
        if not any(start <= m.start() < end for start, end in spans)
    ]


def existing(paths: list[str]) -> list[str]:
    return [p for p in paths if os.path.isfile(os.path.expanduser(p))]


ARGS = (
    "",
    "all",
    "status",
    "plan",
    "plan persona",
    "restore",
    "restore 1",
    "~/.hermes/SOUL.md",
    "restore ~/.hermes/SOUL.md",
    "persona rioplatense",
)


class RegisteredRepliesTests(unittest.TestCase):
    def test_no_reply_carries_an_attachable_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = os.path.realpath(raw)
            hermes_home = Path(tmp) / ".hermes"
            hermes_home.mkdir()
            soul = hermes_home / "SOUL.md"
            soul.write_text("# Soul\nBe kind.\n", encoding="utf-8")
            (hermes_home / "SOUL.md.hermes-odd-bak-20260101T000000Z").write_text(
                "# Old soul\n", encoding="utf-8"
            )
            project = Path(tmp) / "work" / "demo"
            (project / ".git").mkdir(parents=True)
            changed = project / "notes.md"
            changed.write_text("x\n", encoding="utf-8")
            args = (*ARGS, str(soul), str(changed), "notes.md")
            env = {"HOME": tmp, "HERMES_HOME": str(hermes_home), "PATH": tmp}
            unprotected: list[str] = []
            with (
                mock.patch.dict(os.environ, env),
                mock.patch.dict(
                    "sys.modules",
                    {"hermes_constants": None, "hermes_cli": None, "hermes_cli.config": None},
                ),
                mock.patch("subprocess.run", side_effect=OSError("no")),
                mock.patch("urllib.request.urlopen", side_effect=OSError("no network")),
            ):
                ctx = FakeContext()
                register(ctx)
                ctx.fire("post_tool_call", **_write_call(str(changed)))
                for key, entry in sorted(ctx.commands.items()):
                    for arg in args:
                        out = entry["handler"](arg)
                        with self.subTest(command=key, args=arg):
                            self.assertIsInstance(out, str)
                            self.assertEqual(existing(gateway_paths(out)), [], out)
                            self.assertNotRegex(out, r"(?<![`\w])/odd[-_][a-z]", out)
                        unprotected += existing(gateway_paths(out, skip_code=False))
        # Not vacuous: replies did show existing files, only inside inline code.
        self.assertTrue(unprotected)


def _write_call(target: str) -> dict:
    return {
        "tool_name": "write_file",
        "args": {"path": target, "content": "x\n"},
        "result": json.dumps(
            {
                "bytes_written": 2,
                "verified": True,
                "resolved_path": target,
                "files_modified": [target],
            }
        ),
        "task_id": "run-main",
        "session_id": "s-main",
        "tool_call_id": "call-1",
        "turn_id": "turn-1",
        "duration_ms": 5,
        "status": "ok",
        "error_type": None,
        "error_message": None,
        "telemetry_schema_version": 1,
    }


class SafeTextTests(unittest.TestCase):
    def test_code_path_cannot_be_broken_open(self) -> None:
        self.assertEqual(code_path("~/a`b/SOUL.md"), "`~/a'b/SOUL.md`")
        self.assertEqual(code_path("a\nb"), "`a b`")
        self.assertEqual(code_path(""), "`?`")
        self.assertEqual(gateway_paths(code_path("/tmp/x`/y.md")), [])

    def test_bare_paths_and_commands_are_wrapped_once(self) -> None:
        text = gateway_safe("see ~/.hermes/SOUL.md, /tmp/a/b.json and /odd-soul plan")
        self.assertEqual(text, "see `~/.hermes/SOUL.md`, `/tmp/a/b.json` and `/odd-soul` plan")
        self.assertEqual(gateway_safe(text), text)
        self.assertEqual(
            gateway_safe("Reply `/odd-setup persona x confirm`"),
            "Reply `/odd-setup persona x confirm`",
        )
        self.assertEqual(gateway_safe("https://example.com/a.md"), "https://example.com/a.md")
        self.assertEqual(gateway_safe("/usr/bin and ~/.hermes"), "/usr/bin and ~/.hermes")

    def test_cap_holds_and_never_leaves_an_open_span(self) -> None:
        text = gateway_safe("x" * 90 + " /odd-doctor " + "y" * 20, max_chars=100)
        self.assertLessEqual(len(text), 100)
        self.assertTrue(text.endswith(TRUNCATED))
        self.assertEqual(text.count("`") % 2, 0)

    def test_failure_text_wraps_the_exception_path(self) -> None:
        def broken(raw_args: str) -> str:
            raise OSError("cannot read /tmp/x/SOUL.md")

        spec = CommandSpec(name="odd_broken", description="x", handler=broken)
        with self.assertLogs("hermes_odd", level="WARNING"):
            out = spec.handler("")
        self.assertEqual(out, "`/odd-broken` failed: OSError: cannot read `/tmp/x/SOUL.md`")


if __name__ == "__main__":
    unittest.main()
