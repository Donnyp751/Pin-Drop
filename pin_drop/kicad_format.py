"""Shared constants and small node builders for KiCad file generation.

Keeping the version tokens in one place makes it easy to bump them when KiCad's
file format moves on.  The values match what KiCad 10.0 itself writes (sampled
from the installed footprint/symbol libraries).
"""

from __future__ import annotations

import uuid as _uuid

from .sexpr import Sym

# File-format version tokens emitted by KiCad 10.0.
FOOTPRINT_VERSION = 20260206
SYMBOL_VERSION = 20251024
GENERATOR = "pin_drop"
GENERATOR_VERSION = "0.1"

# A fixed namespace so regenerating a fixture yields stable UUIDs (clean diffs).
_NS = _uuid.UUID("6f3b9c1e-2a4d-4b8e-9c1a-7d5e0f2b1a33")


def uid(*parts: str) -> str:
    """Deterministic UUID from the given string parts."""
    return str(_uuid.uuid5(_NS, "|".join(parts)))


def font_effects(size: float = 1.0, thickness: float = 0.15, *, justify=None,
                 hide: bool = False):
    font = [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), thickness]]
    node = [Sym("effects"), font]
    if justify:
        node.append([Sym("justify"), Sym(justify)])
    if hide:
        node.append([Sym("hide"), True])
    return node
