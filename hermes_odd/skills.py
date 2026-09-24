"""Discovery and registration of the plugin's lazy skills.

Skills live in ``skills/`` at the repository root. Two install layouts are
supported (see :func:`resolve_skills_dir` and ``docs/design.md``):

* git clone (``hermes plugins install``): ``<plugin dir>/skills``;
* wheel (``pip install``, entry point ``hermes_agent.plugins``):
  ``pyproject.toml`` maps ``skills/`` to the data-only package
  ``hermes_odd/_skills``.

If neither exists, registration logs one warning and registers no skills;
it never raises.

Each ``skills/<name>/SKILL.md`` is registered with
``PluginContext.register_skill(name, path, description="", frontmatter=None)``
(``hermes_cli/plugins.py``). Hermes exposes it as ``hermes-odd:<name>``;
plugin skills stay out of the always-on skills index and load on demand via
``skill_view``.

Frontmatter follows the Hermes skill convention (``agent/skill_utils.py``
``parse_frontmatter``): ``name``, ``description``, ``version`` and
``metadata.hermes.{tags,category}``. Hermes parses it with YAML; this module
uses a small stdlib parser for the subset the shipped skills use (scalars,
quoted strings, flow lists and nested maps) so the plugin stays stdlib-only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("hermes_odd")

PACKAGE_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = PACKAGE_DIR.parent
SKILL_FILE = "SKILL.md"
# Candidate skill directories, most specific first: the wheel data package
# (inside ``hermes_odd``) wins over a root-level ``skills/`` so a stray
# ``site-packages/skills`` from another distribution is never picked up.
SKILLS_DIR_CANDIDATES = (PACKAGE_DIR / "_skills", PLUGIN_ROOT / "skills")
# Mirrors agent.skill_utils._NAMESPACE_RE.
SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
REQUIRED_KEYS = ("name", "description", "version")


def resolve_skills_dir(candidates: Sequence[Path] = SKILLS_DIR_CANDIDATES) -> Path | None:
    """Return the first candidate directory holding at least one skill."""
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob(f"*/{SKILL_FILE}")):
            return candidate
    return None


# ``None`` when the install carries no skills; register_skills then warns.
SKILLS_DIR: Path | None = resolve_skills_dir()


class FrontmatterError(ValueError):
    """Raised when a SKILL.md frontmatter block is missing or malformed."""


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: Path
    description: str
    frontmatter: dict[str, Any] = field(default_factory=dict)


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in "\"'" and value[-1] == value[0] and len(value) >= 2:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item) for item in inner.split(",")]
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the leading ``---`` block; return ``(frontmatter, body)``."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---\n"):
        raise FrontmatterError("SKILL.md must start with a '---' frontmatter fence")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise FrontmatterError("SKILL.md frontmatter is not closed by '---'")
    block = text[4:end]
    body = text[end + 5 :]

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for lineno, line in enumerate(block.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, rest = line.strip().partition(":")
        if not sep or not key or not SKILL_NAME_RE.match(key.replace(".", "_")):
            raise FrontmatterError(f"line {lineno}: expected 'key: value', got {line!r}")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise FrontmatterError(f"line {lineno}: bad indentation")
        parent = stack[-1][1]
        if rest.strip():
            parent[key] = _parse_scalar(rest)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return root, body


def load_skill(skill_dir: Path) -> SkillSpec:
    """Load and validate one skill directory."""
    path = skill_dir / SKILL_FILE
    frontmatter, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    for key in REQUIRED_KEYS:
        if not isinstance(frontmatter.get(key), str) or not frontmatter[key].strip():
            raise FrontmatterError(f"{path}: frontmatter needs a non-empty {key!r}")
    name = frontmatter["name"]
    if name != skill_dir.name:
        raise FrontmatterError(f"{path}: name {name!r} must match directory {skill_dir.name!r}")
    if not SKILL_NAME_RE.match(name):
        raise FrontmatterError(f"{path}: name {name!r} must match [a-zA-Z0-9_-]+")
    hermes = (
        (frontmatter.get("metadata") or {}).get("hermes")
        if isinstance(frontmatter.get("metadata"), dict)
        else None
    )
    if (
        not isinstance(hermes, dict)
        or not isinstance(hermes.get("tags"), list)
        or not hermes.get("category")
    ):
        raise FrontmatterError(f"{path}: frontmatter needs metadata.hermes.tags and .category")
    return SkillSpec(
        name=name, path=path, description=frontmatter["description"], frontmatter=frontmatter
    )


def discover_skills(skills_dir: Path | None = SKILLS_DIR) -> list[SkillSpec]:
    """Return every valid skill under ``skills_dir``; invalid ones are logged."""
    specs: list[SkillSpec] = []
    if skills_dir is None or not skills_dir.is_dir():
        return specs
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if not (skill_dir / SKILL_FILE).is_file():
            continue
        try:
            specs.append(load_skill(skill_dir))
        except (OSError, FrontmatterError) as exc:
            logger.warning("hermes-odd: skipping skill %s: %s", skill_dir.name, exc)
    return specs


def register_skills(ctx: Any, skills_dir: Path | None = SKILLS_DIR) -> int:
    """Register every shipped skill with Hermes; return how many succeeded."""
    register_skill = getattr(ctx, "register_skill", None)
    if not callable(register_skill):
        logger.warning("hermes-odd: ctx.register_skill is unavailable; skills skipped")
        return 0
    if skills_dir is None or not skills_dir.is_dir():
        logger.warning(
            "hermes-odd: no skills directory found (looked in %s); skills skipped",
            ", ".join(str(p) for p in SKILLS_DIR_CANDIDATES),
        )
        return 0
    registered = 0
    for spec in discover_skills(skills_dir):
        try:
            register_skill(
                spec.name,
                spec.path,
                description=spec.description,
                frontmatter=spec.frontmatter,
            )
            registered += 1
        except Exception as exc:  # noqa: BLE001 - never break Hermes startup
            logger.warning("hermes-odd: could not register skill %s: %s", spec.name, exc)
    return registered
