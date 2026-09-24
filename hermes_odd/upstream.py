"""Read the upstream support lock (``upstream/upstream.lock.json``).

The lock is the authoritative, machine-checked record of which gentle-ai and
gentle-shell versions hermes-odd supports and which upstream files each
component derives from; ``upstream/SUPPORTED.md`` is its human counterpart
with the triage log. ``/odd_doctor`` will use :func:`min_gentle_ai_version`
to check the installed ``gentle-ai`` binary.

The lock lives in ``upstream/`` at the repository root. As with the skills
(see :mod:`hermes_odd.skills`), two install layouts are supported and the
wheel data package wins:

* wheel: ``pyproject.toml`` maps ``upstream/`` to ``hermes_odd/_upstream``;
* git clone (``hermes plugins install``): ``<plugin dir>/upstream``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = PACKAGE_DIR.parent
LOCK_FILE = "upstream.lock.json"
LOCK_SCHEMA = "hermes-odd.upstream-lock/v1"
# Most specific first, mirroring ``skills.SKILLS_DIR_CANDIDATES``.
UPSTREAM_DIR_CANDIDATES = (PACKAGE_DIR / "_upstream", PLUGIN_ROOT / "upstream")


def resolve_lock_path(candidates: Sequence[Path] = UPSTREAM_DIR_CANDIDATES) -> Path | None:
    """Return the first candidate directory's lock file that exists."""
    for candidate in candidates:
        path = candidate / LOCK_FILE
        if path.is_file():
            return path
    return None


def load_lock(candidates: Sequence[Path] = UPSTREAM_DIR_CANDIDATES) -> dict[str, Any]:
    """Load and minimally validate the upstream lock.

    Raises ``FileNotFoundError`` when no candidate holds the lock and
    ``ValueError`` when it is not a ``hermes-odd.upstream-lock/v1`` object.
    """
    path = resolve_lock_path(candidates)
    if path is None:
        looked = ", ".join(str(c / LOCK_FILE) for c in candidates)
        raise FileNotFoundError(f"hermes-odd: upstream lock not found (looked in {looked})")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != LOCK_SCHEMA:
        raise ValueError(f"{path}: expected schema {LOCK_SCHEMA!r}")
    if not isinstance(data.get("upstreams"), dict) or not isinstance(data.get("components"), dict):
        raise ValueError(f"{path}: lock needs 'upstreams' and 'components' objects")
    return data


def min_gentle_ai_version(lock: Mapping[str, Any] | None = None) -> str:
    """Return the minimum supported ``gentle-ai`` binary version (e.g. ``"3.7.0"``)."""
    data = load_lock() if lock is None else lock
    return str(data["upstreams"]["gentle-ai"]["binary"]["min_version"])
