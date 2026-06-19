"""Reconcile a saved fixture against a freshly converted DUT board.

This is what turns "every revision is a brand-new board" into "every revision is
a small diff".  Points are re-found by their ``(refdes, pad)`` key; coordinates
are refreshed from the live board; net changes are flagged for review; vanished
points and brand-new candidates are surfaced so the user only touches the deltas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import nail_library
from .dut_reader import KIND_TESTPOINT, KIND_TH_PIN, DutData, DutPad
from .fixture_model import Fixture, FixturePoint, make_point_id

# Default kinds offered as new candidates (connection targets, not SMD/mounting).
DEFAULT_CANDIDATE_KINDS = (KIND_TESTPOINT, KIND_TH_PIN)
MOVE_EPS_MM = 0.001


@dataclass
class Matched:
    point: FixturePoint
    dut_pad: DutPad
    moved: bool
    dx_mm: float
    dy_mm: float


@dataclass
class NetChanged:
    point: FixturePoint
    old_net: str
    new_net: str
    dut_pad: DutPad


@dataclass
class Missing:
    point: FixturePoint


@dataclass
class NewCandidate:
    dut_pad: DutPad
    suggested_id: str
    suggested_name: str


@dataclass
class ReconcileReport:
    matched: List[Matched] = field(default_factory=list)
    net_changed: List[NetChanged] = field(default_factory=list)
    missing: List[Missing] = field(default_factory=list)
    new: List[NewCandidate] = field(default_factory=list)

    def summary(self) -> str:
        moved = sum(1 for m in self.matched if m.moved)
        return (
            f"{len(self.matched)} matched ({moved} moved), "
            f"{len(self.net_changed)} net-changed, "
            f"{len(self.missing)} missing, "
            f"{len(self.new)} new candidate(s)"
        )

    def is_clean(self) -> bool:
        """True when nothing needs the user's attention (pure coordinate refresh)."""
        return not (self.net_changed or self.missing)


def reconcile(fixture: Fixture, dut: DutData,
              candidate_kinds=DEFAULT_CANDIDATE_KINDS,
              refresh_coords: bool = True) -> ReconcileReport:
    """Diff ``fixture`` against ``dut``.

    When ``refresh_coords`` is set (default), matched/net-changed points have
    their runtime ``x_mm``/``y_mm`` refreshed from the live board so a generate
    immediately uses current geometry.  The stored ``net`` is **not** silently
    overwritten on a net change -- that is left to the user to confirm.
    """
    report = ReconcileReport()
    annotated_keys = set()

    for point in fixture.points:
        annotated_keys.add(point.match_key)
        dp = dut.pad_by_key(point.refdes, point.pad)
        if dp is None:
            report.missing.append(Missing(point))
            continue

        if refresh_coords:
            dx = dp.x_mm - point.x_mm if point.x_mm is not None else 0.0
            dy = dp.y_mm - point.y_mm if point.y_mm is not None else 0.0
            had_prev = point.x_mm is not None
            point.x_mm, point.y_mm = dp.x_mm, dp.y_mm
        else:
            dx = dy = 0.0
            had_prev = False

        if point.net and dp.net and point.net != dp.net:
            report.net_changed.append(NetChanged(point, point.net, dp.net, dp))
        else:
            moved = had_prev and (abs(dx) > MOVE_EPS_MM or abs(dy) > MOVE_EPS_MM)
            report.matched.append(Matched(point, dp, moved, dx, dy))

    # New candidates: connection-target pads not already annotated.
    taken_ids = {p.id for p in fixture.points}
    for dp in dut.pads:
        if dp.kind not in candidate_kinds:
            continue
        if dp.match_key in annotated_keys:
            continue
        base = make_point_id(dp.refdes, dp.pad)
        suggested = base
        n = 2
        while suggested in taken_ids:
            suggested = f"{base}_{n}"
            n += 1
        taken_ids.add(suggested)
        report.new.append(NewCandidate(
            dut_pad=dp, suggested_id=suggested, suggested_name=dp.net or base))
    return report


def apply_new_candidates(fixture: Fixture, candidates: List[NewCandidate]) -> None:
    """Add the chosen new candidates to the fixture as included points."""
    for c in candidates:
        dp = c.dut_pad
        nail = (nail_library.DEFAULT_TH_NAIL if dp.kind == KIND_TH_PIN
                else nail_library.DEFAULT_TP_NAIL)
        point = FixturePoint(
            id=fixture.unique_id(dp.refdes, dp.pad),
            refdes=dp.refdes, pad=dp.pad, name=c.suggested_name,
            net=dp.net, nail=nail,
        )
        point.x_mm, point.y_mm = dp.x_mm, dp.y_mm
        fixture.add_point(point)


def accept_net_changes(report: ReconcileReport) -> None:
    """Overwrite stored nets with the live nets for all flagged net changes."""
    for nc in report.net_changed:
        nc.point.net = nc.new_net
