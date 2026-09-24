"""Hermes plugin entry point for ``hermes plugins install``.

The installer clones this repository into ``~/.hermes/plugins/hermes-odd``
and Hermes imports this file as ``hermes_plugins.hermes_odd`` with the
plugin directory as the package ``__path__`` (see
``PluginManager._load_directory_module`` in ``hermes_cli/plugins.py``), so the
relative import below resolves the ``hermes_odd`` package shipped next to
this file. Tests and other flat imports put the repository root on
``sys.path`` and use the absolute import instead.
"""

from __future__ import annotations

try:  # loaded as a package by the Hermes plugin loader
    from .hermes_odd import __version__, register
except ImportError:  # imported flat (repository root on sys.path)
    from hermes_odd import __version__, register

__all__ = ["__version__", "register"]
