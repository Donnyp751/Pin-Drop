"""KiCad action-plugin entry point for pin_drop.

KiCad discovers plugins by importing modules in its plugin search paths.  The
recommended install is a tiny loader stub (see ``install_plugin.py``) that puts
this repo on ``sys.path`` and calls :func:`register_plugins`, so the package can
live anywhere and be updated in place.
"""

from __future__ import annotations


def register_plugins() -> None:
    """Instantiate and register the action plugin(s) with KiCad."""
    from .action import FixtureBuilderPlugin

    FixtureBuilderPlugin().register()
