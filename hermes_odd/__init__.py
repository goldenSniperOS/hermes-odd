"""hermes-odd: ODD workflow support for Hermes."""

from __future__ import annotations

__version__ = "0.5.1"

from .plugin import register  # noqa: E402

__all__ = ["__version__", "register"]
