"""Unit tests for the dependency-free foundation modules."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_drop import nail_library
from pin_drop.fixture_model import Fixture, FixturePoint, make_point_id
from pin_drop.sexpr import Sym, dumps, fmt_num


class TestSexpr(unittest.TestCase):
    def test_fmt_num(self):
        self.assertEqual(fmt_num(0), "0")
        self.assertEqual(fmt_num(10), "10")
        self.assertEqual(fmt_num(10.16), "10.16")
        self.assertEqual(fmt_num(1.500000), "1.5")
        self.assertEqual(fmt_num(-0.0), "0")
        self.assertEqual(fmt_num(0.0), "0")

    def test_bool_renders_yes_no(self):
        self.assertEqual(dumps([Sym("hide"), True]), "(hide yes)")
        self.assertEqual(dumps([Sym("hide"), False]), "(hide no)")

    def test_inline_list(self):
        node = [Sym("at"), 1.0, 2.5, 90]
        self.assertEqual(dumps(node), "(at 1 2.5 90)")

    def test_quoting(self):
        self.assertEqual(dumps([Sym("layer"), "F.Cu"]), '(layer "F.Cu")')
        self.assertEqual(dumps("a\"b"), '"a\\"b"')

    def test_nested_indentation(self):
        node = [
            Sym("pad"), "1", Sym("thru_hole"), Sym("circle"),
            [Sym("at"), 0, 0],
            [Sym("size"), 1.7, 1.7],
            [Sym("drill"), 1.02],
        ]
        out = dumps(node)
        lines = out.splitlines()
        self.assertEqual(lines[0], '(pad "1" thru_hole circle')
        # Children indented by one tab, inline lists kept flat.
        self.assertIn("\t(at 0 0)", lines)
        self.assertIn("\t(size 1.7 1.7)", lines)
        self.assertIn("\t(drill 1.02)", lines)
        self.assertEqual(lines[-1], ")")


class TestNailLibrary(unittest.TestCase):
    def test_defaults_present(self):
        lib = nail_library.default_library()
        self.assertIn("1.3mm", lib)
        self.assertIn("1.7mm", lib)
        self.assertIn("spring_mount", lib)
        self.assertIn("mounting", lib)

    def test_spring_mount_is_large_plated_hole(self):
        nail = nail_library.DEFAULT_NAILS["spring_mount"]
        self.assertTrue(nail.plated)
        self.assertEqual((nail.drill_mm, nail.pad_mm), (5.0, 7.0))
        self.assertGreater(nail.drill_mm, nail_library.DEFAULT_NAILS["1.7mm"].drill_mm)

    def test_annular_ring(self):
        nail = nail_library.DEFAULT_NAILS["1.3mm"]
        self.assertAlmostEqual(nail.annular_ring_mm, (2.10 - 1.30) / 2.0)

    def test_roundtrip(self):
        lib = nail_library.default_library()
        data = nail_library.library_to_dict(lib)
        back = nail_library.library_from_dict(data)
        self.assertEqual(back["1.7mm"].drill_mm, lib["1.7mm"].drill_mm)
        self.assertFalse(back["mounting"].plated)


class TestFixtureModel(unittest.TestCase):
    def test_make_point_id(self):
        self.assertEqual(make_point_id("TP25", "1"), "TP25")
        self.assertEqual(make_point_id("J5", "7"), "J5-7")

    def test_unique_id(self):
        fx = Fixture(board="demo")
        fx.add_point(FixturePoint(id="TP25", refdes="TP25", pad="1"))
        # Same default base -> suffixed.
        self.assertEqual(fx.unique_id("TP25", "1"), "TP25_2")

    def test_match_key_and_lookup(self):
        fx = Fixture(board="demo")
        p = FixturePoint(id="J5-7", refdes="J5", pad="7", net="TRD1_P")
        fx.add_point(p)
        self.assertIs(fx.point_by_key("J5", "7"), p)
        self.assertIs(fx.point_by_id("J5-7"), p)
        self.assertIsNone(fx.point_by_key("J5", "8"))

    def test_duplicate_key_rejected(self):
        fx = Fixture(board="demo")
        fx.add_point(FixturePoint(id="TP1", refdes="TP1", pad="1"))
        with self.assertRaises(ValueError):
            fx.add_point(FixturePoint(id="x", refdes="TP1", pad="1"))

    def test_save_load_roundtrip(self):
        fx = Fixture(board="264545 MPS-IP REV C", source_rev="C", probe_side="top")
        fx.add_point(FixturePoint(
            id="TP25", refdes="TP25", pad="1", name="VPD", net="VPD", nail="1.3mm"
        ))
        fx.add_point(FixturePoint(
            id="J5-7", refdes="J5", pad="7", name="TRD1_P", net="TRD1_P", nail="1.7mm"
        ))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "demo.fixture.json")
            fx.save(path)
            back = Fixture.load(path)
        self.assertEqual(back.board, fx.board)
        self.assertEqual(len(back.points), 2)
        self.assertEqual(back.point_by_id("J5-7").nail, "1.7mm")
        self.assertEqual(back.point_by_id("TP25").net, "VPD")
        # xy is runtime-only, not persisted.
        self.assertIsNone(back.point_by_id("TP25").x_mm)


if __name__ == "__main__":
    unittest.main()
