"""Generate the fixture schematic symbol (``.kicad_sym``).

One pin per included probe point.  The pin *number* is the point ``id`` (so it
nets to the matching footprint pad) and the pin *name* is the human label.

Layout aims for a readable part:

* pins in two columns either side of a body rectangle;
* the body is sized to the longest pin name so opposing names never overlap;
* signals are grouped by a common prefix (``TRD0_P``/``TRD0_N`` together,
  ``Audio.*`` together, ...) and sorted naturally within a group;
* power/ground pins are split out into a block at the **bottom** of both
  columns, separated from the signals by a blank row;
* pins are two grid units long so numbers and names have room to breathe.
"""

from __future__ import annotations

import math
import re
from typing import List, Optional

from .fixture_model import Fixture, FixturePoint
from .kicad_format import (
    GENERATOR, GENERATOR_VERSION, SYMBOL_VERSION, font_effects, uid,
)
from .sexpr import Sym, dumps

GRID = 2.54                 # pin pitch
PIN_LENGTH = 2 * GRID       # 5.08 mm — long enough that names/numbers don't crowd
NAME_FONT = 1.27
NUMBER_FONT = 1.0
NAME_OFFSET = 1.016         # pin_names offset (name inset from the body edge)
CHAR_W = 0.72               # approx glyph advance as a fraction of font height
CENTER_GAP = GRID           # minimum clear space between opposing names
MIN_HALF_W = 4 * GRID       # don't let small symbols get too skinny

# Voltage-rail names like +3.3V, 5V, +12V, 3V3, 1V8.
_VOLT = re.compile(r"^[+-]?\d+(\.\d+)?V\d*$", re.I)
_POWER_WORDS = {
    "GND", "GROUND", "VSS", "VDD", "VCC", "VEE", "VBAT", "VBUS", "VPP", "VPD",
    "AGND", "DGND", "PGND", "GNDA", "GNDD", "VREF", "VDDA", "VSSA", "VCORE",
    "PWR", "POWER", "VIN",
}
_GROUND_WORDS = {"GND", "GROUND", "VSS", "AGND", "DGND", "PGND", "GNDA", "GNDD"}


def _label(p: FixturePoint) -> str:
    return p.name or p.net or p.id


def _natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _natural_key(p: FixturePoint):
    """Sort like a human: TP2 before TP10. (Kept for callers/tests.)"""
    return _natural(p.id)


def _is_power(label: str) -> bool:
    s = (label or "").strip().upper()
    if not s:
        return False
    if _VOLT.match(s):
        return True
    toks = [t for t in re.split(r"[ ._/\-]+", s) if t]
    return any(t in _POWER_WORDS for t in toks)


def _is_ground(label: str) -> bool:
    s = (label or "").strip().upper()
    toks = [t for t in re.split(r"[ ._/\-]+", s) if t]
    return any(t in _GROUND_WORDS for t in toks)


def _group_key(label: str) -> str:
    """A coarse grouping key: leading token with trailing digits/polarity removed."""
    s = (label or "").strip()
    if not s:
        return "~"
    s = re.sub(r"[_\-+]$", "", s)              # trailing polarity (+/-/_)
    s = re.sub(r"[_.\-/][PN]$", "", s)         # _P / _N differential suffix
    base = re.split(r"[._/\-]+", s)[0]         # first separator-delimited token
    base = re.sub(r"\d+$", "", base)           # strip trailing digits
    return base.upper() or s.upper()


def _ceil_grid(v: float) -> float:
    return math.ceil(v / GRID - 1e-9) * GRID


def _order(points: List[FixturePoint]):
    """Return (signals, power) each ordered for display."""
    signals = [p for p in points if not _is_power(_label(p))]
    power = [p for p in points if _is_power(_label(p))]
    signals.sort(key=lambda p: (_group_key(_label(p)), _natural(_label(p)), _natural(p.id)))
    # Power: positive rails first (grouped), grounds last.
    power.sort(key=lambda p: (_is_ground(_label(p)), _natural(_label(p))))
    return signals, power


def _split2(lst):
    h = (len(lst) + 1) // 2
    return lst[:h], lst[h:]


def _pin_node(point: FixturePoint, x: float, y: float, angle: int):
    return [
        Sym("pin"), Sym("passive"), Sym("line"),
        [Sym("at"), round(x, 4), round(y, 4), angle],
        [Sym("length"), PIN_LENGTH],
        [Sym("name"), _label(point), font_effects(NAME_FONT)],
        [Sym("number"), point.id, font_effects(NUMBER_FONT)],
    ]


def build_symbol(fixture: Fixture, name: str = "") -> str:
    name = name or (fixture.board + " Fixture")
    points = fixture.included_points()
    n = len(points)

    signals, power = _order(points)
    ls, rs = _split2(signals)
    lp, rp = _split2(power)

    # Each column: signals, a blank gap row, then power.
    gap: List[Optional[FixturePoint]] = [None]
    left_seq = ls + (gap if ls and lp else []) + lp
    right_seq = rs + (gap if rs and rp else []) + rp
    rows = max(len(left_seq), len(right_seq), 1)

    # Width: fit the longest name on each side without crossing the centre.
    widest = max((len(_label(p)) for p in points), default=4) * NAME_FONT * CHAR_W
    half_w = max(_ceil_grid(NAME_OFFSET + widest + CENTER_GAP), MIN_HALF_W)
    half_h = round((rows + 1) * GRID / 2.0, 3)
    top, bottom = half_h, -half_h
    x_conn = half_w + PIN_LENGTH

    sub = name + "_1_1"
    body = [
        Sym("symbol"), sub,
        [Sym("rectangle"),
         [Sym("start"), -half_w, top], [Sym("end"), half_w, bottom],
         [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
         [Sym("fill"), [Sym("type"), Sym("background")]]],
    ]

    def place(seq, x, angle):
        y = top - GRID
        for item in seq:
            if item is not None:
                body.append(_pin_node(item, x, y, angle))
            y -= GRID

    place(left_seq, -x_conn, 0)     # left column: pins point right
    place(right_seq, x_conn, 180)   # right column: pins point left

    symbol = [
        Sym("symbol"), name,
        [Sym("pin_names"), [Sym("offset"), NAME_OFFSET]],
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
