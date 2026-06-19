"""Generate the fixture schematic symbol (``.kicad_sym``).

One pin per included probe point.  The pin *number* is the point ``id`` (so it
nets to the matching footprint pad) and the pin *name* is the human label.  Pins
are laid out in two vertical columns either side of a body rectangle, sorted for
a tidy, predictable schematic part.
"""

from __future__ import annotations

import re
from typing import List

from .fixture_model import Fixture, FixturePoint
from .kicad_format import (
    GENERATOR, GENERATOR_VERSION, SYMBOL_VERSION, font_effects, uid,
)
from .sexpr import Sym, dumps

GRID = 2.54           # pin pitch
PIN_LENGTH = 2.54
PIN_FONT = 1.27


def _natural_key(p: FixturePoint):
    """Sort like a human: TP2 before TP10, group by ref letters then number."""
    s = p.id
    parts = re.split(r"(\d+)", s)
    return [int(t) if t.isdigit() else t.lower() for t in parts]


def _pin_node(point: FixturePoint, x: float, y: float, angle: int):
    name = point.name or point.net or point.id
    return [
        Sym("pin"), Sym("passive"), Sym("line"),
        [Sym("at"), round(x, 4), round(y, 4), angle],
        [Sym("length"), PIN_LENGTH],
        [Sym("name"), name, font_effects(PIN_FONT, justify=None)],
        [Sym("number"), point.id, font_effects(PIN_FONT)],
    ]


def build_symbol(fixture: Fixture, name: str = "") -> str:
    name = name or (fixture.board + " Fixture")
    points = sorted(fixture.included_points(), key=_natural_key)

    n = len(points)
    n_left = (n + 1) // 2
    left = points[:n_left]
    right = points[n_left:]
    rows = max(len(left), len(right), 1)

    # Body rectangle sized to the taller column.
    half_h = (rows + 1) * GRID / 2.0
    half_w = 4 * GRID
    top = round(half_h, 3)
    bottom = round(-half_h, 3)

    sub = name + "_1_1"
    body = [
        Sym("symbol"), sub,
        [Sym("rectangle"),
         [Sym("start"), -half_w, top], [Sym("end"), half_w, bottom],
         [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
         [Sym("fill"), [Sym("type"), Sym("background")]]],
    ]

    # Left column: pins point right (angle 0), placed off the left edge.
    y = top - GRID
    for p in left:
        body.append(_pin_node(p, -half_w - PIN_LENGTH, y, 0))
        y -= GRID
    # Right column: pins point left (angle 180), placed off the right edge.
    y = top - GRID
    for p in right:
        body.append(_pin_node(p, half_w + PIN_LENGTH, y, 180))
        y -= GRID

    symbol = [
        Sym("symbol"), name,
        [Sym("pin_names"), [Sym("offset"), 1.016]],
        [Sym("exclude_from_sim"), False],
        [Sym("in_bom"), True],
        [Sym("on_board"), True],
        [Sym("property"), "Reference", "FX",
         [Sym("at"), -half_w, round(top + GRID, 3), 0], font_effects(1.27, justify="left")],
        [Sym("property"), "Value", name,
         [Sym("at"), -half_w, round(top + 2 * GRID, 3), 0],
         font_effects(1.27, justify="left")],
        [Sym("property"), "Footprint", "",
         [Sym("at"), 0, 0, 0], font_effects(1.27, hide=True)],
        [Sym("property"), "Datasheet", "",
         [Sym("at"), 0, 0, 0], font_effects(1.27, hide=True)],
        [Sym("property"), "Description",
         f"Bed-of-nails fixture interface for {fixture.board} "
         f"(rev {fixture.source_rev}); {n} probes.",
         [Sym("at"), 0, 0, 0], font_effects(1.27, hide=True)],
        body,
    ]

    lib = [
        Sym("kicad_symbol_lib"),
        [Sym("version"), SYMBOL_VERSION],
        [Sym("generator"), GENERATOR],
        [Sym("generator_version"), GENERATOR_VERSION],
        symbol,
    ]
    return dumps(lib) + "\n"


def write_symbol(fixture: Fixture, path: str, name: str = "") -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_symbol(fixture, name))
