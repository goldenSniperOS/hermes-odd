"""``/odd_review_mode``: show or flip gentle-ai's RDD review switch (Pi ``gentle:review-mode``).

Concept port of gentle-pi's review-mode view: it wraps the real ``gentle-ai
review mode status|enable|disable`` CLI (schema ``gentle-ai.review-mode/v1``)
and adds what matters on Hermes, the native review availability (see
:mod:`hermes_odd.rdd`). No upstream code or text is copied.

* ``status`` (default) is read-only: the effective mode and its source for the
  target repository, both sources, and the native review availability line.
* ``enable``/``disable`` are explicit, user-typed writes of gentle-ai's own
  switch and nothing else. The scope (``global`` or ``clone``) is required;
  ``clone`` needs a resolvable git repository.

The target repository is an explicit project name (exact, then prefix) among
the known projects (``/odd_tasks`` resolution), else the command process's own
git repository. hermes-odd never passes ``--agent pi`` or any other runtime's
identity to gentle-ai. Output is plain text under :data:`OUTPUT_MAX_CHARS` and
never carries a full home path.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from ..probes import (
    MUTATION_TIMEOUT_SECONDS,
    REVIEW_MODE_ACTIONS,
    REVIEW_MODE_SCOPES,
    Prober,
    ReviewMode,
    git_repo_root,
    process_repo,
)
from ..projects import ProjectStore, process_cwd_candidates
from ..rdd import UNAVAILABLE_NOTE, known_git_roots, native_review_line
from .doctor import display_path, review_mode_text
from .registry import CommandSpec
from .tasks import path_tail

OUTPUT_MAX_CHARS = 3500
MESSAGE_MAX_CHARS = 400
USAGE = "/odd_review_mode [status|enable|disable] [global|clone] [project]"
_ABS_PATH_RE = re.compile(r"(?<![\w~.])/[^\s'\"`,;:()]+")


def sanitize(text: str, limit: int = MESSAGE_MAX_CHARS) -> str:
    """One line, home as ``~``, other absolute paths shortened, bounded."""
    value = " ".join(str(text or "").split())
    home = os.path.expanduser("~")
    if home and home != "/":
        value = value.replace(home, "~")
    value = _ABS_PATH_RE.sub(lambda m: display_path(m.group(0)), value)
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value


def parse_args(raw: str) -> tuple[str, str | None, str | None, str | None]:
    """``(action, scope, project, error)``; the action defaults to ``status``."""
    action: str | None = None
    scope: str | None = None
    project: str | None = None
    for token in (raw or "").split():
        low = token.lower()
        if low in REVIEW_MODE_ACTIONS and action is None:
            action = low
        elif low in REVIEW_MODE_SCOPES and scope is None:
            scope = low
        elif project is None:
            project = token
        else:
            return "status", None, None, f"Too many arguments. Usage: {USAGE}"
    return action or "status", scope, project, None


def _modes_line(mode: ReviewMode) -> str:
    global_text = mode.global_mode or "unset (default on)"
    clone = mode.clone_local or "unset"
    return f"sources: global {global_text} · clone {clone}"


def _mode_line(mode: ReviewMode) -> str:
    text = review_mode_text(mode)
    if mode.state == "ok" and mode.repo:
        text = text.rsplit(" · ", 1)[0]
    return f"receipt-driven development: {text}"


def fit(text: str) -> str:
    if len(text) <= OUTPUT_MAX_CHARS:
        return text
    return text[: OUTPUT_MAX_CHARS - 1].rstrip() + "…"


class ReviewModeCommand:
    """Handler state with injectable seams (tests replace the prober and repos)."""

    def __init__(
        self,
        prober: Prober | None = None,
        project_store: ProjectStore | None = None,
        *,
        repo: Callable[[], Path | None] = process_repo,
        cwd_candidates: Callable[[], list[Path]] = process_cwd_candidates,
    ):
        self.prober = prober if prober is not None else Prober()
        self.project_store = project_store
        self._repo = repo
        self._cwd_candidates = cwd_candidates

    # -- target ------------------------------------------------------------

    def candidates(self) -> list[Path]:
        roots = known_git_roots(self.project_store)
        try:
            extra = list(self._cwd_candidates())
        except Exception:  # noqa: BLE001
            extra = []
        for item in extra:
            root = git_repo_root(item)
            if root is not None and root not in roots:
                roots.append(root)
        return roots

    def resolve(self, query: str | None) -> tuple[Path | None, str | None]:
        """``(root, error)``. No query: the process repository (may be ``None``)."""
        if not query:
            try:
                return self._repo(), None
            except Exception:  # noqa: BLE001
                return None, None
        roots = self.candidates()
        needle = query.strip().lower()
        shown = sanitize(query, 60)
        for exact in (True, False):
            matches = [
                r
                for r in roots
                if (r.name.lower() == needle if exact else r.name.lower().startswith(needle))
            ]
            if len(matches) == 1:
                return matches[0], None
            if len(matches) > 1:
                names = ", ".join(f"{r.name} ({path_tail(r)})" for r in matches[:6])
                return None, f"'{shown}' is ambiguous: {names}. Use more characters."
        known = ", ".join(r.name for r in roots[:10]) or "none yet"
        return None, (
            f"No known git project matches '{shown}'. Known: {known}. Projects become "
            "known once a Hermes session ran in them; from the CLI, run inside the repository."
        )

    # -- rendering ---------------------------------------------------------

    def _header(self, root: Path | None) -> str:
        if root is None:
            return "RDD review mode · no git repository here (global switch only)"
        return f"RDD review mode · {root.name} ({path_tail(root)})"

    def _native_lines(self, binary: str, version: str | None, root: Path | None) -> list[str]:
        probe_root = root
        if probe_root is None:
            roots = known_git_roots(self.project_store)
            probe_root = roots[0] if roots else None
        native = self.prober.native_review(binary, probe_root)
        lines = [native_review_line(native, version)]
        if native.code:
            detail = f"  gentle-ai code: {native.code}"
            if native.runtimes:
                detail += " · eligible in this environment: " + ", ".join(native.runtimes)
            lines.append(detail)
        if native.state == "unavailable":
            lines.append(
                "With RDD on, each candidate (one work-unit commit or PR slice) is reported "
                f'once as "{UNAVAILABLE_NOTE}" and continues under ordinary repository '
                "policy (tests, CI, human review). hermes-odd never impersonates another "
                "runtime and never fakes a receipt."
            )
            lines.append(
                "Optional advisory 4R review (no receipt) when you ask for it: "
                "skill hermes-odd:rdd-review."
            )
        return lines

    def status(self, root: Path | None) -> str:
        info = self.prober.first_version()
        if info is None:
            return (
                f"{self._header(root)}\ngentle-ai: not found on PATH, so the RDD switch "
                "cannot be read. Install the binary: "
                "brew install gentleman-programming/tap/gentle-ai"
            )
        if root is not None:
            mode = self.prober.review_mode(info.path, root)
        else:
            mode = self.prober.global_review_mode(info.path)
        lines = [self._header(root)]
        if mode.state == "ok":
            lines.append(_mode_line(mode))
            lines.append(_modes_line(mode))
        else:
            lines.append(f"receipt-driven development: {review_mode_text(mode)}")
        lines.extend(self._native_lines(info.path, info.version, root))
        lines.append("Change: /odd_review_mode enable|disable global|clone [project]")
        return fit("\n".join(lines))

    def write(self, action: str, scope: str | None, root: Path | None, query: str | None) -> str:
        if scope is None:
            target = f" {query}" if query else ""
            return (
                f"Refused: /odd_review_mode {action} needs an explicit scope. No change was made.\n"
                f"- /odd_review_mode {action} global{target}: your global switch "
                "(every repository of this user)\n"
                f"- /odd_review_mode {action} clone{target}: only this clone of the repository"
            )
        if scope == "clone" and root is None:
            known = ", ".join(r.name for r in self.candidates()[:10]) or "none yet"
            return (
                "Refused: the clone switch needs a git repository and none was resolved. "
                f"Name a known project (known: {known}) or run from inside the repository. "
                "No change was made."
            )
        info = self.prober.first_version()
        if info is None:
            return "gentle-ai not found on PATH; nothing was changed."
        mode, result = self.prober.set_review_mode(info.path, action, scope, root)
        where = f" · {root.name}" if root is not None else ""
        if result.state == "timeout":
            return (
                f"gentle-ai review mode {action} timed out after "
                f"{MUTATION_TIMEOUT_SECONDS:.0f} s; the switch may or may not have changed. "
                "Check with /odd_review_mode status."
            )
        if result.state != "ok":
            reason = sanitize(result.stderr) or "no error message"
            text = f"gentle-ai review mode {action} --scope {scope} failed{where}: {reason}"
            if mode.state == "ok":
                text += f"\nNow: {_mode_line(mode)}; {_modes_line(mode)}"
            return fit(text)
        if mode.state != "ok":
            return (
                f"gentle-ai review mode {action} --scope {scope} ran{where}, but its JSON "
                "result was unreadable. Check with /odd_review_mode status."
            )
        verb = "enabled" if action == "enable" else "disabled"
        lines = [
            f"RDD review mode {verb} (scope {scope}){where}",
            _mode_line(mode),
            _modes_line(mode),
        ]
        if action == "enable" and scope == "clone":
            lines.append(
                "A clone can only opt out: enable clears this clone's override; "
                "the global switch decides."
            )
        if action == "enable" and mode.effective == "off":
            lines.append("Still off: any off wins (the other source is off).")
        lines.append("Applies to future candidates only.")
        lines.append(
            "Native review on Hermes is unaffected by this switch: /odd_review_mode status"
        )
        return fit("\n".join(lines))

    def render(self, raw_args: str) -> str:
        action, scope, query, error = parse_args(raw_args)
        if error:
            return error
        root, error = self.resolve(query)
        if error:
            return error
        if action == "status":
            return self.status(root)
        return self.write(action, scope, root, query)


def make_odd_review_mode(command: ReviewModeCommand) -> CommandSpec:
    return CommandSpec(
        name="odd_review_mode",
        description="RDD review switch (gentle-ai review mode) and native review on Hermes",
        handler=command.render,
        args_hint="[status|enable|disable] [global|clone] [project]",
        group="Review",
    )


__all__ = ["ReviewModeCommand", "USAGE", "make_odd_review_mode", "parse_args", "sanitize"]
