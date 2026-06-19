"""Generator tests using a hand-built DutData (no KiCad required)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_drop import generate_footprint, generate_symbol
from pin_drop.dut_reader import DutData, DutPad, MountingHole, OutlineShape
from pin_drop.fixture_model import Fixture, FixturePoint


def _demo_dut() -> DutData:
    d = DutData(board_name="DEMO")
    # 100x80 board with origin at (10,10); center (60,50).
    d.bbox_mm = (10.0, 10.0, 100.0, 80.0)
    d.outline = [
        OutlineShape("segment", [(10, 10), (110, 10)]),
        OutlineShape("segment", [(110, 10), (110, 90)]),
        OutlineShape("segment", [(110, 90), (10, 90)]),
        OutlineShape("segment", [(10, 90), (10, 10)]),
    ]
    d.pads = [
        DutPad("TP1", "1", "VCC", 60.0, 50.0, "testpoint", 0.4, 1.0, 1.0,
               "circle", True, False, True, False),
        DutPad("J1", "3", "DATA", 30.0, 70.0, "th_pin", 1.0, 1.6, 1.6,
               "circle", True, False, True, False),
    ]
    d.mounting_holes = [MountingHole(15.0, 15.0, 3.2), MountingHole(105.0, 85.0, 3.2)]
    return d


def _demo_fixture() -> Fixture:
    fx = Fixture(board="DEMO", source_rev="A", probe_side="top")
    fx.add_point(FixturePoint(id="TP1", refdes="TP1", pad="1", name="VCC",
                              net="VCC", nail="1.3mm"))
    fx.add_point(FixturePoint(id="J1-3", refdes="J1", pad="3", name="DATA",
                              net="DATA", nail="1.7mm"))
    return fx


def _balanced(text: str) -> bool:
    depth = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_str


class TestFootprint(unittest.TestCase):
    def test_build(self):
        dut, fx = _demo_dut(), _demo_fixture()
        text = generate_footprint.build_footprint(fx, dut, name="DEMO Fixture")
        self.assertTrue(_balanced(text))
        self.assertEqual(generate_footprint.build_footprint.last_missing, [])
        # Probe pad numbered by id, with the cup nail drill.
        self.assertIn('(pad "TP1" thru_hole circle', text)
        self.assertIn('(pad "J1-3" thru_hole circle', text)
        self.assertIn("(drill 1.7)", text)        # 1.7mm (J1-3)
        self.assertIn("(drill 1.3)", text)        # 1.3mm (TP1)
        # Mounting holes are NPTH.
        self.assertIn("np_thru_hole", text)
        # Outline copied to Edge.Cuts, centered on datum (TP1 at center -> 0,0).
        self.assertIn('(layer "Edge.Cuts")', text)
        self.assertIn("(at 0 0)", text)

    def test_missing_pad_reported(self):
        dut = _demo_dut()
        fx = _demo_fixture()
        fx.add_point(FixturePoint(id="TP9", refdes="TP9", pad="1", nail="1.3mm"))
        generate_footprint.build_footprint(fx, dut)
        self.assertEqual(generate_footprint.build_footprint.last_missing, ["TP9"])

    def test_bottom_side_mirrors_x(self):
        dut = _demo_dut()
        fx = _demo_fixture()
        fx.probe_side = "bottom"
        for p in fx.points:
            p.side = "bottom"
        text = generate_footprint.build_footprint(fx, dut)
        # J1/3 at x=30, center x=60 -> top:-30, bottom:+30
        self.assertIn("(at 30 20)", text)


class TestSymbol(unittest.TestCase):
    def test_build(self):
        fx = _demo_fixture()
        text = generate_symbol.build_symbol(fx, name="DEMO Fixture")
        self.assertTrue(_balanced(text))
        self.assertIn("(kicad_symbol_lib", text)
        # pin number == id, pin name == label
        self.assertIn('(number "TP1"', text)
        self.assertIn('(name "VCC"', text)
        self.assertIn('(number "J1-3"', text)
        self.assertIn('(name "DATA"', text)

    def test_natural_sort(self):
        fx = Fixture(board="X")
        for n in ("TP10", "TP2", "TP1"):
            fx.add_point(FixturePoint(id=n, refdes=n, pad="1"))
        ordered = [p.id for p in sorted(fx.points, key=generate_symbol._natural_key)]
        self.assertEqual(ordered, ["TP1", "TP2", "TP10"])

    def test_power_detection(self):
        for label in ("GND", "+3.3V", "+5V", "+12V", "3V3", "VSS", "VCC",
                      "AGND", "Audio_GND"):
            self.assertTrue(generate_symbol._is_power(label), label)
        for label in ("TRD0_P", "Audio.LineOutN", "NetJ7_58", "RESET", "VPDATA"):
            self.assertFalse(generate_symbol._is_power(label), label)

    def test_grouping_clusters_prefixes(self):
        self.assertEqual(generate_symbol._group_key("TRD0_P"),
                         generate_symbol._group_key("TRD1_N"))
        self.assertEqual(generate_symbol._group_key("Audio.LineOutP"),
                         generate_symbol._group_key("Audio.LineInL"))

    def test_power_ordered_after_signals(self):
        fx = Fixture(board="X")
        rows = [("TP1", "DATA"), ("J1-1", "GND"), ("TP2", "TRD0_P"),
                ("J1-2", "+3.3V")]
        for pid, nm in rows:
            fx.add_point(FixturePoint(id=pid, refdes=pid, pad="1", name=nm))
        signals, power = generate_symbol._order(fx.points)
        self.assertEqual({p.name for p in power}, {"GND", "+3.3V"})
        self.assertEqual({p.name for p in signals}, {"DATA", "TRD0_P"})

    def test_body_widens_for_long_names(self):
        narrow = Fixture(board="X")
        narrow.add_point(FixturePoint(id="A", refdes="A", pad="1", name="A"))
        wide = Fixture(board="X")
        wide.add_point(FixturePoint(id="B", refdes="B", pad="1",
                                    name="Audio.LineOutNegative_Long"))
        # The wider symbol must have a larger body rectangle (more negative start x).
        import re as _re
        def start_x(text):
            m = _re.search(r"\(rectangle\s+\(start (-?[\d.]+)", text)
            return float(m.group(1))
        self.assertLess(start_x(generate_symbol.build_symbol(wide)),
                        start_x(generate_symbol.build_symbol(narrow)))


if __name__ == "__main__":
    unittest.main()
