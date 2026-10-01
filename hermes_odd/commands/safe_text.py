"""Gateway-safe reply text for every hermes-odd command.

Hermes gateways (``gateway/platforms/base.py`` ``extract_local_files``) scan
each reply for bare absolute or ``~/`` paths that end in a deliverable
extension and, when the file exists, send it as an attachment and drop the
path from the text. Paths inside inline code or fenced code blocks are left
alone. So every path a hermes-odd reply shows goes through :func:`code_path`
(an inline code span), and :func:`gateway_safe` (applied to every
:class:`~hermes_odd.commands.registry.CommandSpec` handler result) is the
safety net: it wraps any remaining bare path, and every ``/odd-...`` command
reference, in inline code.

Command references stay in the hyphen form: the CLI looks the registered key
(``odd-doctor``) up verbatim, while gateways accept ``-`` and ``_``. Inside
inline code Telegram does not auto-link ``/odd`` alone (a tap would send
``/odd``), and the text stays copyable.
"""

from __future__ import annotations

import re

TRUNCATED = "\n… truncated"
_FENCE_CLOSE = "\n```"

# Inline code as the gateway sees it, plus fenced blocks (never touched).
_CODE_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`")
# Same shape as the gateway path scanner, but for any extension.
_PATH_RE = re.compile(r"(?<![/:\w.])(?:~/|/|[A-Za-z]:[/\\])(?:[\w.\-]+[/\\])*[\w.\-]+\.\w+\b")
_COMMAND_RE = re.compile(r"(?<![\w/`])/odd(?:[-_][a-z0-9]+)+\b")


def code_path(path: object) -> str:
    """``path`` as one inline code span that nothing can break open."""
    text = " ".join(str(path).replace("`", "'").split()) or "?"
    return f"`{text}`"


def _wrap_plain(text: str) -> str:
    text = _PATH_RE.sub(lambda m: code_path(m.group(0)), text)
    return _COMMAND_RE.sub(lambda m: f"`{m.group(0)}`", text)


def _protect(text: str) -> str:
    out: list[str] = []
    last = 0
    for match in _CODE_RE.finditer(text):
        out.append(_wrap_plain(text[last : match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_wrap_plain(text[last:]))
    return "".join(out)


def gateway_safe(text: str, max_chars: int | None = None) -> str:
    """Wrap bare paths and command references; keep ``max_chars`` if given.

    The cap applies after wrapping (which adds backticks). A longer reply is
    cut at a line boundary when one lies in the second half, then ends with
    ``TRUNCATED``. A fenced block cut open is closed; an inline code span cut
    open is dropped from its backtick on.
    """
    safe = _protect(text)
    if max_chars is None or len(safe) <= max_chars:
        return safe
    budget = max(0, max_chars - len(TRUNCATED) - len(_FENCE_CLOSE))
    cut = safe[:budget]
    newline = cut.rfind("\n")
    if newline >= budget // 2:
        cut = cut[:newline]
    stray = _CODE_RE.sub(lambda m: " " * len(m.group(0)), cut).find("`")
    if stray >= 0 and cut.startswith("```", stray) and "\n" in cut[stray:]:
        return cut.rstrip() + _FENCE_CLOSE + TRUNCATED
    if stray >= 0:
        cut = cut[:stray]
    return cut.rstrip() + TRUNCATED


__all__ = ["code_path", "gateway_safe"]
