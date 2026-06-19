"""Reconcile tests simulating a board revision (no KiCad required)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_drop import reconcile
from pin_drop.dut_reader import DutData, DutPad
from pin_drop.fixture_model import Fixture, FixturePoint


def _pad(ref, pad, net, x, y, kind="testpoint"):
    return DutPad(ref, pad, net, x, y, kind, 0.4, 1.0, 1.0,
                  "circle", True, False, True, False)


def _fixture():
    fx = Fixture(board="DEMO")
    for pid, ref, pad, net in [("TP1", "TP1", "1", "VCC"),
                               ("J1-3", "J1", "3", "DATA"),
                               ("TP9", "TP9", "1", "OLD")]:
        p = FixturePoint(id=pid, refdes=ref, pad=pad, name=net, net=net,
                         nail="1.3mm")
        p.x_mm, p.y_mm = 10.0, 10.0   # prior coordinates
        fx.add_point(p)
    return fx


class TestReconcile(unittest.TestCase):
    def setUp(self):
        # New revision: TP1 moved, J1-3 net changed, TP9 deleted, TP5 is new.
        self.dut = DutData(board_name="DEMO")
        self.dut.pads = [
            _pad("TP1", "1", "VCC", 12.5, 10.0),          # moved +2.5 in x
            _pad("J1", "3", "DATA2", 30.0, 70.0, "th_pin"),  # net changed
            _pad("TP5", "1", "RESET", 40.0, 40.0),        # new candidate
        ]
        self.fx = _fixture()

    def test_buckets(self):
        rep = reconcile.reconcile(self.fx, self.dut)
        matched_ids = [m.point.id for m in rep.matched]
        self.assertEqual(matched_ids, ["TP1"])
        self.assertTrue(rep.matched[0].moved)
        self.assertAlmostEqual(rep.matched[0].dx_mm, 2.5)

        self.assertEqual([n.point.id for n in rep.net_changed], ["J1-3"])
        self.assertEqual(rep.net_changed[0].old_net, "DATA")
        self.assertEqual(rep.net_changed[0].new_net, "DATA2")

        self.assertEqual([m.point.id for m in rep.missing], ["TP9"])

        self.assertEqual([c.dut_pad.refdes for c in rep.new], ["TP5"])
        self.assertEqual(rep.new[0].suggested_name, "RESET")
        self.assertFalse(rep.is_clean())

    def test_coords_refreshed(self):
        reconcile.reconcile(self.fx, self.dut)
        # TP1 coordinates refreshed from the live board.
        self.assertEqual(self.fx.point_by_id("TP1").x_mm, 12.5)

    def test_clean_when_unchanged(self):
        dut = DutData(board_name="DEMO")
        dut.pads = [_pad("TP1", "1", "VCC", 10.0, 10.0),
                    _pad("J1", "3", "DATA", 30.0, 70.0, "th_pin")]
        fx = Fixture(board="DEMO")
        for pid, ref, pad, net in [("TP1", "TP1", "1", "VCC"),
                                   ("J1-3", "J1", "3", "DATA")]:
            fx.add_point(FixturePoint(id=pid, refdes=ref, pad=pad, net=net))
        rep = reconcile.reconcile(fx, dut)
        self.assertTrue(rep.is_clean())
        self.assertEqual(len(rep.matched), 2)

    def test_apply_new_and_accept_nets(self):
        rep = reconcile.reconcile(self.fx, self.dut)
        reconcile.apply_new_candidates(self.fx, rep.new)
        self.assertIsNotNone(self.fx.point_by_key("TP5", "1"))
        # New TH-pin candidates default to 1.7mm; TP5 is a testpoint -> 1.3mm.
        self.assertEqual(self.fx.point_by_key("TP5", "1").nail, "1.3mm")

        reconcile.accept_net_changes(rep)
        self.assertEqual(self.fx.point_by_id("J1-3").net, "DATA2")


if __name__ == "__main__":
    unittest.main()
