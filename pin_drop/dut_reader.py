"""Read a DUT (device-under-test) KiCad board into a normalized, pcbnew-free form.

Everything KiCad-specific lives here.  ``pcbnew`` is imported lazily inside the
functions so the rest of the package (model, generators, reconcile) can be
imported and unit-tested without KiCad present.

The output is plain dataclasses in millimetres, with KiCad's coordinate
convention preserved (X right, **Y down**).  Downstream code applies the
fixture datum/mirror transform; the reader does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Candidate classification kinds.
KIND_TESTPOINT = "testpoint"   # TP* refs / single-pad footprints with exposed copper
KIND_TH_PIN = "th_pin"         # plated through-hole pin of a multi-pad part
KIND_SMD = "smd"               # surface-mount pad
KIND_MOUNTING = "mounting"     # non-plated hole (mounting / mechanical)

# Non-plated holes smaller than this are tooling/peg/via holes (switch pegs,
# fiducials), not board mounting holes, so they are not captured as mounts.
MOUNTING_MIN_DRILL_MM = 2.0


@dataclass
class DutPad:
    """One pad on the DUT, normalized to mm."""

    refdes: str
    pad: str
    net: str
    x_mm: float
    y_mm: float
    kind: str
    drill_mm: float          # 0 for SMD
    pad_w_mm: float
    pad_h_mm: float
    shape: str               # "circle", "rect", "oval", "roundrect", ...
    is_pth: bool
    is_npth: bool
    has_top_copper: bool     # probe-accessible from the top (component) side
    fp_flipped: bool         # parent footprint placed on bottom

    @property
    def match_key(self):
        return (self.refdes, str(self.pad))


@dataclass
class OutlineShape:
    """A single Edge.Cuts primitive, coordinates in mm."""

    type: str                       # segment | arc | circle | rect | poly
    pts: List = field(default_factory=list)   # list of (x,y); semantics per type
    radius_mm: float = 0.0          # circle only


@dataclass
class MountingHole:
    x_mm: float
    y_mm: float
    drill_mm: float
    refdes: str = ""


@dataclass
class DutData:
    board_name: str
    pads: List[DutPad] = field(default_factory=list)
    outline: List[OutlineShape] = field(default_factory=list)
    mounting_holes: List[MountingHole] = field(default_factory=list)
    bbox_mm: tuple = (0.0, 0.0, 0.0, 0.0)   # x, y, w, h

    @property
    def bbox_center_mm(self):
        x, y, w, h = self.bbox_mm
        return (x + w / 2.0, y + h / 2.0)

    def pad_by_key(self, refdes: str, pad: str) -> Optional[DutPad]:
        key = (refdes, str(pad))
        for p in self.pads:
            if p.match_key == key:
                return p
        return None


def _classify(refdes: str, pad_count: int, is_pth: bool, is_npth: bool,
              is_smd: bool, has_copper: bool) -> str:
    if is_npth or not has_copper and not is_smd:
        return KIND_MOUNTING
    ref_alpha = "".join(c for c in refdes if c.isalpha()).upper()
    if ref_alpha == "TP" or (pad_count == 1 and is_pth):
        return KIND_TESTPOINT
    if is_pth:
        return KIND_TH_PIN
    return KIND_SMD


def read_board(board, board_name: str = "") -> DutData:
    """Read an already-loaded ``pcbnew.BOARD`` into :class:`DutData`."""
    import pcbnew

    def mm(v):
        return round(pcbnew.ToMM(v), 6)

    shape_names = {
        getattr(pcbnew, "PAD_SHAPE_CIRCLE", 0): "circle",
        getattr(pcbnew, "PAD_SHAPE_RECTANGLE", getattr(pcbnew, "PAD_SHAPE_RECT", 1)): "rect",
        getattr(pcbnew, "PAD_SHAPE_OVAL", 2): "oval",
        getattr(pcbnew, "PAD_SHAPE_ROUNDRECT", 5): "roundrect",
    }

    data = DutData(board_name=board_name or board.GetFileName())

    for fp in board.GetFootprints():
        refdes = fp.GetReference()
        flipped = fp.IsFlipped()
        pad_count = fp.GetPadCount()
        for p in fp.Pads():
            attr = p.GetAttribute()
            is_pth = attr == pcbnew.PAD_ATTRIB_PTH
            is_npth = attr == pcbnew.PAD_ATTRIB_NPTH
            is_smd = attr == pcbnew.PAD_ATTRIB_SMD
            has_top = p.IsOnLayer(pcbnew.F_Cu)
            pos = p.GetPosition()
            size = p.GetSize()
            num = p.GetNumber()
            kind = _classify(refdes, pad_count, is_pth, is_npth, is_smd, has_top)

            if is_npth:
                # Non-plated holes are mechanical, never connection targets.
                # Only holes big enough to be real board mounts are captured;
                # small tooling/peg/via holes are ignored.
                hole_drill = mm(p.GetDrillSizeX())
                if hole_drill >= MOUNTING_MIN_DRILL_MM:
                    data.mounting_holes.append(MountingHole(
                        x_mm=mm(pos.x), y_mm=mm(pos.y),
                        drill_mm=hole_drill, refdes=refdes,
                    ))
                continue

            data.pads.append(DutPad(
                refdes=refdes,
                pad=num,
                net=p.GetNetname(),
                x_mm=mm(pos.x),
                y_mm=mm(pos.y),
                kind=kind,
                drill_mm=mm(p.GetDrillSizeX()) if (is_pth) else 0.0,
                pad_w_mm=mm(size.x),
                pad_h_mm=mm(size.y),
                shape=shape_names.get(p.GetShape(), "circle"),
                is_pth=is_pth,
                is_npth=is_npth,
                has_top_copper=has_top,
                fp_flipped=flipped,
            ))

    data.outline = _read_outline(board)
    data.mounting_holes.extend(_read_mounting_footprints(board, data))

    bb = board.GetBoardEdgesBoundingBox()
    data.bbox_mm = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight()))
    return data


def _read_outline(board) -> List[OutlineShape]:
    import pcbnew

    def mm(v):
        return round(pcbnew.ToMM(v), 6)

    def pt(vec):
        return (mm(vec.x), mm(vec.y))

    shapes: List[OutlineShape] = []
    for d in board.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not isinstance(d, pcbnew.PCB_SHAPE):
            continue
        st = d.GetShape()
        if st == pcbnew.SHAPE_T_SEGMENT:
            shapes.append(OutlineShape("segment", [pt(d.GetStart()), pt(d.GetEnd())]))
        elif st == pcbnew.SHAPE_T_ARC:
            shapes.append(OutlineShape(
                "arc", [pt(d.GetStart()), pt(d.GetArcMid()), pt(d.GetEnd())]))
        elif st == pcbnew.SHAPE_T_CIRCLE:
            shapes.append(OutlineShape(
                "circle", [pt(d.GetCenter())], radius_mm=mm(d.GetRadius())))
        elif st == pcbnew.SHAPE_T_RECT:
            shapes.append(OutlineShape("rect", [pt(d.GetStart()), pt(d.GetEnd())]))
        elif st == pcbnew.SHAPE_T_POLY:
            poly = d.GetPolyShape()
            for oi in range(poly.OutlineCount()):
                outline = poly.Outline(oi)
                pts = [(mm(outline.CPoint(i).x), mm(outline.CPoint(i).y))
                       for i in range(outline.PointCount())]
                shapes.append(OutlineShape("poly", pts))
    return shapes


def _read_mounting_footprints(board, data: DutData) -> List[MountingHole]:
    """Footprints whose name says 'MountingHole' but weren't caught as NPTH pads."""
    import pcbnew

    def mm(v):
        return round(pcbnew.ToMM(v), 6)

    seen = {(round(h.x_mm, 3), round(h.y_mm, 3)) for h in data.mounting_holes}
    holes: List[MountingHole] = []
    for fp in board.GetFootprints():
        fpid = fp.GetFPID().GetLibItemName().wx_str().lower()
        if "mountinghole" not in fpid:
            continue
        pos = fp.GetPosition()
        key = (round(mm(pos.x), 3), round(mm(pos.y), 3))
        if key in seen:
            continue
        drill = 0.0
        for p in fp.Pads():
            drill = max(drill, mm(p.GetDrillSizeX()))
        holes.append(MountingHole(mm(pos.x), mm(pos.y), drill, fp.GetReference()))
    return holes


def load_board(path: str) -> DutData:
    """Load a ``.kicad_pcb`` from disk (works headless) and read it."""
    import os
    import pcbnew

    board = pcbnew.LoadBoard(path)
    name = os.path.splitext(os.path.basename(path))[0]
    return read_board(board, board_name=name)
