"""Receipt-driven development (RDD) on Hermes: shared wording and repository choice.

Used by ``/odd_review_mode``, ``/odd_status`` and ``/odd_doctor``. gentle-ai
advertises its native immutable review only for runtimes that can launch a
fresh, constrained reviewer and prove that boundary before review START
(``internal/agents/capabilitymanifest/manifest.go``,
``ContractReviewTransportV1`` / ``ContractImmutableReviewExecutorV1``).
Hermes is not one of them in gentle-ai 3.7.0, so the availability probe
(:meth:`hermes_odd.probes.Prober.native_review`) reports
``immutable_review_transport_unsupported``. hermes-odd reports that honestly
and never impersonates another runtime; the native review facade is T8,
blocked on upstream eligibility.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import upstream as upstream_mod
from .probes import NativeReview, git_repo_root, process_repo
from .projects import ProjectStore

LABEL = "Native review on Hermes"
UNAVAILABLE_NOTE = "native review unavailable on Hermes (gentle-ai runtime eligibility)"
# Compiled into gentle-ai 3.7.0 (capability manifest); the lock is authoritative.
DEFAULT_ADVERTISED = ("claude-code", "opencode", "codex", "pi")


def advertised_runtimes() -> tuple[str, ...]:
    """Runtimes the pinned gentle-ai advertises immutable review for (lock
    ``review-contract.immutable_review_runtimes``)."""
    try:
        lock = upstream_mod.load_lock()
        names = lock["components"]["review-contract"]["immutable_review_runtimes"]
        if isinstance(names, list) and names and all(isinstance(n, str) for n in names):
            return tuple(names)
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_ADVERTISED


def eligible_runtimes(native: NativeReview) -> tuple[str, ...]:
    """What to name as eligible: the compiled set, unless gentle-ai reports a
    runtime outside it (a newer binary), then what it reports.

    gentle-ai's refusal lists only the runtimes eligible in the probing
    environment (Pi needs its host relay, OpenCode a V1 runtime), a subset of
    the compiled set."""
    advertised = advertised_runtimes()
    reported = native.runtimes
    if reported and not set(reported) <= set(advertised):
        return reported
    return advertised


def native_review_text(native: NativeReview | None, version: str | None) -> str:
    """The availability wording without the label, e.g. ``unavailable — gentle-ai
    3.7.0 advertises immutable review only for claude-code, opencode, codex, pi``."""
    ver = f"gentle-ai {version}" if version else "gentle-ai"
    if native is None:
        return "unknown (not probed)"
    if native.state == "unavailable":
        return f"unavailable — {ver} advertises immutable review only for " + ", ".join(
            eligible_runtimes(native)
        )
    if native.state == "available":
        return (
            f"available (detected) — {ver} accepts --agent hermes, but the hermes-odd "
            "review facade (T8) is pending: no native review runs from Hermes yet"
        )
    reason = {
        "timeout": "gentle-ai timed out",
        "no_binary": "gentle-ai missing",
        "no_repo": "the probe needs a git repository; run it from a project or name one",
    }.get(native.state)
    if reason is None:
        reason = native.detail or "gentle-ai probe failed"
        if native.code:
            reason += f": {native.code}"
    return f"unknown ({reason})"


def native_review_line(native: NativeReview | None, version: str | None) -> str:
    return f"{LABEL}: {native_review_text(native, version)}"


def known_git_roots(store: ProjectStore | None) -> list[Path]:
    """Known project roots (most recent first) that are real git repositories."""
    roots: list[Path] = []
    if store is None:
        return roots
    try:
        projects = store.known()
    except Exception:  # noqa: BLE001
        return roots
    for project in projects:
        try:
            root = git_repo_root(project.root)
        except Exception:  # noqa: BLE001
            continue
        if root is not None and root not in roots:
            roots.append(root)
    return roots


def probe_repo(
    store: ProjectStore | None, repo: Callable[[], Path | None] = process_repo
) -> Path | None:
    """A git repository to run the availability probe from: the command
    process's own repository, else the most recent known project."""
    try:
        own = repo()
    except Exception:  # noqa: BLE001
        own = None
    if own is not None:
        return own
    roots = known_git_roots(store)
    return roots[0] if roots else None


__all__ = [
    "DEFAULT_ADVERTISED",
    "LABEL",
    "advertised_runtimes",
    "eligible_runtimes",
    "UNAVAILABLE_NOTE",
    "known_git_roots",
    "native_review_line",
    "native_review_text",
    "probe_repo",
]
