"""SOUL.md size, gentle-ai managed blocks and Hermes truncation math for ``/odd_doctor``.

gentle-ai's Hermes writer puts its managed blocks into ``<HERMES_HOME>/SOUL.md``
between ``<!-- gentle-ai:<name> -->`` and ``<!-- /gentle-ai:<name> -->``.
Hermes loads SOUL.md with ``agent/prompt_builder.py`` ``load_soul_md``: it
strips the text and truncates it with ``_truncate_content`` when it is longer
than the context-file cap, keeping the first 70% and the last 20% of the cap
and dropping the middle. Constants verified in ``agent/prompt_builder.py``:

* ``CONTEXT_FILE_MAX_CHARS = 20_000`` (floor);
* ``_CONTEXT_FILE_CHARS_PER_TOKEN = 4``;
* ``_CONTEXT_FILE_WINDOW_FRACTION = 0.06``;
* ``_CONTEXT_FILE_DYNAMIC_CEILING = 500_000``;
* ``CONTEXT_TRUNCATE_HEAD_RATIO = 0.7``, ``CONTEXT_TRUNCATE_TAIL_RATIO = 0.2``;
* an explicit top-level ``context_file_max_chars`` in ``config.yaml`` wins.

The model's context length comes from ``model.context_length`` in
``config.yaml`` or the ``context_length_cache.yaml`` entry for
``<model.default>@<model.base_url>`` (``agent/model_metadata.py``). Both files
are read with a line matcher for exactly those keys (no YAML, nothing else is
kept); ``.env``, ``auth.json`` and other secrets are never read. SOUL content
is only measured, never returned.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONTEXT_FILE_MAX_CHARS = 20_000
CHARS_PER_TOKEN = 4
WINDOW_FRACTION = 0.06
DYNAMIC_CEILING = 500_000
HEAD_RATIO = 0.7
TAIL_RATIO = 0.2
REFERENCE_CONTEXTS = (128_000, 200_000, 1_000_000)

MAX_SOUL_BYTES = 4 * 1024 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
MAX_BLOCKS = 32
_MARKER_RE = re.compile(r"<!--\s*(/?)gentle-ai:([a-z0-9][a-z0-9_-]{0,63})\s*-->")
_INT_RE = re.compile(r"^\d{1,9}$")


@dataclass(frozen=True)
class Block:
    name: str
    start: int  # offset in the stripped text
    end: int
    depth: int = 0
    closed: bool = True

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass
class SoulReport:
    path: Path
    exists: bool
    chars: int = 0  # stripped, as Hermes measures
    blocks: list[Block] = field(default_factory=list)
    error: str = ""

    @property
    def tokens(self) -> int:
        return (self.chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN

    @property
    def managed_chars(self) -> int:
        return sum(b.size for b in self.blocks if b.depth == 0)


@dataclass(frozen=True)
class ModelContext:
    model: str = ""
    context_length: int | None = None
    source: str = ""  # "config" | "cache" | ""
    pinned_cap: int | None = None  # context_file_max_chars


def hermes_home(environ: dict[str, str] | None = None) -> Path:
    """Hermes' home for this process, profile-aware.

    Uses ``hermes_constants.get_hermes_home()`` when Hermes already imported
    it (inside Hermes it always has; it honors the per-profile override),
    else ``HERMES_HOME``, else ``~/.hermes``. Never imports Hermes itself.
    """
    module = sys.modules.get("hermes_constants")
    getter = getattr(module, "get_hermes_home", None) if module is not None else None
    if callable(getter):
        try:
            return Path(getter())
        except Exception:  # noqa: BLE001 - fall back to the environment
            pass
    env = os.environ if environ is None else environ
    value = str(env.get("HERMES_HOME", "") or "").strip()
    return Path(value).expanduser() if value else Path.home() / ".hermes"


def truncation_cap(context_length: int | None, pinned: int | None = None) -> int:
    """Hermes' SOUL.md cap: ``max(20000, min(ctx*4*0.06, 500000))``."""
    if isinstance(pinned, int) and pinned > 0:
        return pinned
    if not isinstance(context_length, int) or context_length <= 0:
        return CONTEXT_FILE_MAX_CHARS
    budget = int(context_length * CHARS_PER_TOKEN * WINDOW_FRACTION)
    return max(CONTEXT_FILE_MAX_CHARS, min(budget, DYNAMIC_CEILING))


def kept_ranges(length: int, cap: int) -> tuple[int, int] | None:
    """``(head_end, tail_start)`` of what Hermes keeps, or ``None`` when it fits."""
    if length <= cap:
        return None
    head = int(cap * HEAD_RATIO)
    tail = int(cap * TAIL_RATIO)
    return head, length - tail


def dropped_blocks(blocks: list[Block], length: int, cap: int) -> list[tuple[Block, str]]:
    """Top-level blocks losing text to truncation: ``(block, "dropped"|"partly")``."""
    kept = kept_ranges(length, cap)
    if kept is None:
        return []
    head_end, tail_start = kept
    result = []
    for block in blocks:
        if block.depth != 0:
            continue
        lost_start, lost_end = max(block.start, head_end), min(block.end, tail_start)
        if lost_end <= lost_start:
            continue
        whole = block.start >= head_end and block.end <= tail_start
        result.append((block, "dropped" if whole else "partly"))
    return result


def parse_blocks(text: str) -> list[Block]:
    """Managed ``gentle-ai:<name>`` blocks (nesting-aware; unclosed runs to EOF)."""
    blocks: list[Block] = []
    stack: list[tuple[str, int]] = []
    for match in _MARKER_RE.finditer(text):
        closing, name = match.group(1) == "/", match.group(2)
        if not closing:
            stack.append((name, match.start()))
            continue
        for index in range(len(stack) - 1, -1, -1):
            if stack[index][0] == name:
                open_name, start = stack[index]
                depth = index
                del stack[index:]
                blocks.append(Block(open_name, start, match.end(), depth))
                break
        if len(blocks) >= MAX_BLOCKS:
            break
    for depth, (name, start) in enumerate(stack):
        blocks.append(Block(name, start, len(text), depth, closed=False))
    blocks.sort(key=lambda b: (b.start, b.depth))
    return blocks[:MAX_BLOCKS]


def analyze_text(text: str, path: Path) -> SoulReport:
    # load_soul_md strips, then _scan_context_content drops a leading BOM.
    stripped = text.strip()
    if stripped.startswith("\ufeff"):
        stripped = stripped[1:]
    return SoulReport(path, True, len(stripped), parse_blocks(stripped))


def read_soul(home: Path) -> SoulReport:
    """Measure ``<home>/SOUL.md``. Never raises; content is not kept."""
    path = home / "SOUL.md"
    try:
        if not path.is_file():
            return SoulReport(path, False)
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_SOUL_BYTES)
    except OSError as exc:
        return SoulReport(path, True, error=type(exc).__name__)
    return analyze_text(text, path)


def _read_small(path: Path) -> list[str]:
    try:
        if not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
            return []
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _scalar(raw: str) -> str:
    value = raw.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def parse_config_lines(lines: list[str]) -> dict[str, str]:
    """Extract only ``model``/``model.default``/``model.base_url``/
    ``model.context_length`` and top-level ``context_file_max_chars``."""
    found: dict[str, str] = {}
    in_model = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, rest = line.strip().partition(":")
        if not sep:
            continue
        if indent == 0:
            in_model = key == "model"
            if key == "model" and rest.strip():
                found["model.default"] = _scalar(rest)
                in_model = False
            elif key == "context_file_max_chars":
                found["context_file_max_chars"] = _scalar(rest)
            continue
        if in_model and indent == 2 and key in ("default", "base_url", "context_length"):
            found[f"model.{key}"] = _scalar(rest)
    return found


def _as_int(value: str | None) -> int | None:
    if value and _INT_RE.match(value):
        number = int(value)
        return number if number > 0 else None
    return None


def cached_context_length(lines: list[str], model: str, base_url: str) -> int | None:
    """``context_lengths`` entry for ``<model>@<base_url>``; else the single
    value shared by every entry of that model."""
    if not model:
        return None
    wanted = f"{model}@{(base_url or '').rstrip('/')}"
    values: dict[str, int] = {}
    for line in lines:
        if not line.startswith("  ") or ":" not in line:
            continue
        key, _, value = line.strip().rpartition(":")
        key = _scalar(key)
        number = _as_int(_scalar(value))
        if number is not None:
            values[key] = number
    for key in (wanted, wanted + "/"):
        if key in values:
            return values[key]
    same = {v for k, v in values.items() if k.rpartition("@")[0] == model}
    return same.pop() if len(same) == 1 else None


def model_context(home: Path) -> ModelContext:
    """Default model and its context length from Hermes' files. Never raises."""
    try:
        config = parse_config_lines(_read_small(home / "config.yaml"))
        model = config.get("model.default", "")
        pinned = _as_int(config.get("context_file_max_chars"))
        explicit = _as_int(config.get("model.context_length"))
        if explicit:
            return ModelContext(model, explicit, "config", pinned)
        cached = cached_context_length(
            _read_small(home / "context_length_cache.yaml"), model, config.get("model.base_url", "")
        )
        if cached:
            return ModelContext(model, cached, "cache", pinned)
        return ModelContext(model, None, "", pinned)
    except Exception:  # noqa: BLE001
        return ModelContext()
