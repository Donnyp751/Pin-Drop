"""High-level orchestration shared by the CLI and the KiCad plugin.

Keeps the init / update / generate flows in one place so both front-ends behave
identically and the logic stays unit-testable without a GUI.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from . import nail_library, reconcile
from .dut_reader import KIND_TESTPOINT, KIND_TH_PIN, DutData
from .fixture_model import Fixture, FixturePoint, SIDE_TOP
from .generate_footprint import write_footprint
from .generate_symbol import write_symbol


def safe_name(text: str) -> str:
    """A filesystem/identifier-safe base name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def new_fixture(dut: DutData, source_rev: str = "", probe_side: str = SIDE_TOP,
                auto_add: Optional[str] = None) -> Fixture:
    """Create a fresh fixture for a DUT.

    ``auto_add``: ``None`` (empty), ``"tp"`` (all test points) or ``"all"``
    (test points + through-hole pins) to pre-populate candidate points.
    """
    fx = Fixture(board=dut.board_name, source_rev=source_rev, probe_side=probe_side)
    if auto_add:
        kinds = (KIND_TESTPOINT,) if auto_add == "tp" else (KIND_TESTPOINT, KIND_TH_PIN)
        for dp in dut.pads:
            if dp.kind not in kinds:
                continue
            # Boards can repeat a pad number (shields, mechanical pads); the
            # first occurrence wins — keep one probe per refdes+pad.
            if fx.point_by_key(dp.refdes, dp.pad) is not None:
                continue
            nail = (nail_library.DEFAULT_TH_NAIL if dp.kind == KIND_TH_PIN
                    else nail_library.DEFAULT_TP_NAIL)
            p = FixturePoint(
                id=fx.unique_id(dp.refdes, dp.pad), refdes=dp.refdes, pad=dp.pad,
                name=dp.net or "", net=dp.net, nail=nail, side=probe_side)
            p.x_mm, p.y_mm = dp.x_mm, dp.y_mm
            fx.add_point(p)
    return fx


def update_fixture(fixture: Fixture, dut: DutData, *, add_new: bool = False,
                   accept_nets: bool = False) -> reconcile.ReconcileReport:
    """Reconcile a fixture against a fresh DUT, optionally applying changes."""
    report = reconcile.reconcile(fixture, dut)
    if accept_nets:
        reconcile.accept_net_changes(report)
    if add_new:
        reconcile.apply_new_candidates(fixture, report.new)
    return report


def generate(fixture: Fixture, dut: DutData, out_dir: str,
             lib_name: str = "") -> Tuple[str, str, List[str], reconcile.ReconcileReport]:
    """Write the footprint (.pretty) and symbol; return paths, missing ids, report.

    Always reconciles first so coordinates are fresh and problems are surfaced.
    """
    report = reconcile.reconcile(fixture, dut)
    base = safe_name(lib_name or (fixture.board + "_Fixture"))
    pretty = os.path.join(out_dir, base + ".pretty")
    os.makedirs(pretty, exist_ok=True)
    fp_path = os.path.join(pretty, base + ".kicad_mod")
    sym_path = os.path.join(out_dir, base + ".kicad_sym")
    missing = write_footprint(fixture, dut, fp_path, name=base)
    write_symbol(fixture, sym_path, name=base)
    return fp_path, sym_path, missing, report


def default_fixture_path(pcb_path: str) -> str:
    """Conventional reference-file path next to a board."""
    name = os.path.splitext(os.path.basename(pcb_path))[0]
    return os.path.join(os.path.dirname(pcb_path), safe_name(name) + ".fixture.json")
