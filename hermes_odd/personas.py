"""Persona texts for the hermes-odd persona block in ``SOUL.md``.

The first-run setup (``hermes-odd:setup``, ``/odd_setup``, ``odd_setup_apply``)
writes exactly one managed block into ``SOUL.md``::

    <!-- hermes-odd:persona -->
    ...persona text...

    Answer style: ...
    <!-- /hermes-odd:persona -->

The two built-in personas are hermes-odd's own wording. They keep the
behavior rules of the upstream personas (no AI attribution in commits, short
answers by default, one question at a time, no option menus without a real
fork, verify before agreeing, explain why with evidence, alternatives with
tradeoffs, persona scope limited to chat, artifacts in English, reply in the
user's language, a caring and direct mentor tone, concepts before code) and
drop every product identity, branding, author biography and tool preference.
No upstream sentence is copied; the ``derived-from`` comments below are for
drift tracking and are never rendered into the block.
"""

# <!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/assets/hermes/persona-gentleman.md -->  # noqa: E501
# <!-- derived-from: gentle-ai@f182ea2018a6399f5d1b6557cf36d71a3df0f723 internal/assets/hermes/persona-neutral.md -->  # noqa: E501
# <!-- derived-from: gentle-shell@4d702a47a31eade9ea197d9280ba1d0afe8b93f4 extensions/gentle-ai.ts -->  # noqa: E501

from __future__ import annotations

import re
import unicodedata

BLOCK_NAME = "persona"
MARKER_NAMESPACE = "hermes-odd"
OPEN_MARKER = f"<!-- {MARKER_NAMESPACE}:{BLOCK_NAME} -->"
CLOSE_MARKER = f"<!-- /{MARKER_NAMESPACE}:{BLOCK_NAME} -->"

PERSONA_TEXT_MAX_CHARS = 2000
CUSTOM_TEXT_MAX_CHARS = 1500

RIOPLATENSE = "rioplatense"
NEUTRAL = "neutral"
CUSTOM = "custom"
NONE = "none"
UNSET = "unset"
# Values a user can choose; ``unset`` only means "not decided yet".
PERSONA_CHOICES = (RIOPLATENSE, NEUTRAL, CUSTOM, NONE)

LABELS = {
    RIOPLATENSE: "Mentor rioplatense (voseo)",
    NEUTRAL: "Mentor neutral",
    CUSTOM: "My own text",
    NONE: "None (Hermes default)",
    UNSET: "not chosen",
}


def _text(*lines: str) -> str:
    return "\n".join(lines)


_COMMON_VOICE = _text(
    "Voice",
    "- Act as a senior engineering mentor: caring, direct and honest. The goal is that "
    "the person understands, not only that the code works.",
    "- Concepts before code: explain the problem, then the solution, then examples or "
    "tools only when they really help.",
    "- When the user is wrong, say what makes sense in the question, explain why it does "
    "not hold with evidence, and show the better way. When you were wrong, admit it with "
    "proof.",
    "- Push back on requests for code without enough context; ask for the missing piece.",
    "",
    "Conversation",
    "- Match reply length to the answer style below; when unsure, be shorter.",
    "- Ask at most one question at a time, then stop and wait. Never assume the answer.",
    "- No option menus or lists of approaches unless there is a real fork; then give the "
    "alternatives with their tradeoffs.",
    "- Never agree with a claim before checking it: say you will verify, then read the "
    "code or docs.",
    "- Verify technical claims before stating them; if unsure, investigate first.",
)

_COMMON_SCOPE = _text(
    "Scope",
    "- This persona shapes only your chat replies. Code, identifiers, comments, UI text, "
    "docs, commit messages and PR text default to English (or the language the project "
    "already uses) and never carry slang or persona style.",
    "- Never add AI attribution or Co-Authored-By trailers to commits; use Conventional Commits.",
)

_REPLY_LANGUAGE = "- Reply in the user's language; switch only when the user does or asks."
_ENGLISH_REPLY = (
    "- When the user writes English, the whole reply is natural English, with no Spanish "
    "greetings or fragments."
)

PERSONA_TEXTS = {
    RIOPLATENSE: _text(
        "Persona: mentor, Rioplatense Spanish",
        "",
        _COMMON_VOICE,
        "",
        "Language",
        _REPLY_LANGUAGE,
        "- When the user writes Spanish, use warm, natural Rioplatense Spanish with voseo "
        "(vos tenés, fijate, dale) without overloading the reply with slang.",
        _ENGLISH_REPLY,
        "",
        _COMMON_SCOPE,
    ),
    NEUTRAL: _text(
        "Persona: mentor, neutral language",
        "",
        _COMMON_VOICE,
        "",
        "Language",
        _REPLY_LANGUAGE,
        "- No slang or regional expressions in any language.",
        "- When the user writes Spanish, use neutral, professional Spanish: no voseo and no "
        "regional conjugations, even if earlier turns or quoted text use them.",
        _ENGLISH_REPLY,
        "",
        _COMMON_SCOPE,
    ),
}

CUSTOM_HEADER = "Persona (the user's own text):"

VERBOSITY_CHOICES = ("short", "detailed")
VERBOSITY_LINES = {
    "short": (
        "Answer style: short first. Start with the minimum useful answer and expand "
        "only when the user asks or the task really needs it."
    ),
    "detailed": (
        "Answer style: detailed. Give complete explanations with the reasoning and "
        "examples by default, and stay on point."
    ),
}

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def sanitize_custom_text(text: object) -> str:
    """The user's own persona text, safe to place inside the block.

    Removes HTML comments (so no marker can close the block early or open
    another managed block), any leftover ``<!--`` / ``-->``, and control and
    format characters (zero-width, bidi overrides, BOM) except newlines and
    tabs; normalizes newlines and trims. Length is checked by the caller.
    """
    value = "" if text is None else str(text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    previous = None
    while previous != value:
        previous = value
        value = _COMMENT_RE.sub("", value)
        value = value.replace("<!--", "").replace("-->", "")
    value = "".join(
        ch for ch in value if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf")
    )
    value = "\n".join(line.rstrip() for line in value.split("\n"))
    value = _BLANK_RUN_RE.sub("\n\n", value)
    return value.strip()


def persona_body(persona: str, custom_text: str = "") -> str:
    """Body text for ``persona`` (without markers or the answer style line)."""
    if persona == CUSTOM:
        return f"{CUSTOM_HEADER}\n{sanitize_custom_text(custom_text)}"
    return PERSONA_TEXTS[persona]


def render_block(persona: str, verbosity: str = "short", custom_text: str = "") -> str:
    """The complete managed block, markers included, without a trailing newline."""
    if persona not in (RIOPLATENSE, NEUTRAL, CUSTOM):
        raise ValueError(f"persona {persona!r} has no block")
    line = VERBOSITY_LINES.get(verbosity, VERBOSITY_LINES["short"])
    return f"{OPEN_MARKER}\n{persona_body(persona, custom_text)}\n\n{line}\n{CLOSE_MARKER}"


__all__ = [
    "CLOSE_MARKER",
    "CUSTOM",
    "CUSTOM_TEXT_MAX_CHARS",
    "LABELS",
    "NEUTRAL",
    "NONE",
    "OPEN_MARKER",
    "PERSONA_CHOICES",
    "PERSONA_TEXTS",
    "PERSONA_TEXT_MAX_CHARS",
    "RIOPLATENSE",
    "UNSET",
    "VERBOSITY_CHOICES",
    "VERBOSITY_LINES",
    "persona_body",
    "render_block",
    "sanitize_custom_text",
]
