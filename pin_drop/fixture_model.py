"""The fixture reference file: the durable, revision-independent artifact.

A :class:`Fixture` records every probe point the user has chosen on the DUT,
keyed by ``(refdes, pad)`` -- the thing that survives an Altium->KiCad
re-conversion -- plus the net name as a verification check.  Physical
coordinates are deliberately **not** part of a point's identity; they are
refreshed from the live board at generate/update time (see
:mod:`pin_drop.reconcile`).

Stored as pretty-printed JSON so it diffs cleanly and lives happily in version
control next to the tester project.  JSON (not YAML) keeps us dependency-free
inside KiCad's bundled interpreter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import nail_library

SCHEMA_VERSION = 1

# Probe sides; "top" means no X-mirror, "bottom" means mirror about the datum.
SIDE_TOP = "top"
SIDE_BOTTOM = "bottom"


def make_point_id(refdes: str, pad: str) -> str:
    """Default fixture id for a target: ``TP25`` for single pads, ``J5-7`` else."""
    if not pad or str(pad) == "1":
        return refdes
    return f"{refdes}-{pad}"


@dataclass
class FixturePoint:
    """One annotated probe target.

    ``id`` is the stable token used for BOTH the generated footprint pad number
    and the schematic symbol pin number, which is what nets the two together in
    the tester schematic.  ``name`` is the human label (the symbol pin name).
    """

    id: str
    refdes: str
    pad: str
    name: str = ""
    net: str = ""
    nail: str = nail_library.DEFAULT_TP_NAIL
    side: str = SIDE_TOP
    include: bool = True
    notes: str = ""

    # Last-known coordinates: refreshed from the live board on every reconcile.
    # Not part of identity (matching is by refdes+pad); persisted only so the
    # tool can report how far a probe moved between revisions.
    x_mm: Optional[float] = field(default=None, repr=False)
    y_mm: Optional[float] = field(default=None, repr=False)

    @property
    def match_key(self) -> Tuple[str, str]:
        return (self.refdes, str(self.pad))

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "refdes": self.refdes,
            "pad": str(self.pad),
            "name": self.name,
            "net": self.net,
            "nail": self.nail,
            "side": self.side,
            "include": self.include,
            "notes": self.notes,
        }
        if self.x_mm is not None and self.y_mm is not None:
            d["x_mm"] = round(self.x_mm, 4)
            d["y_mm"] = round(self.y_mm, 4)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "FixturePoint":
        p = cls(
            id=data["id"],
            refdes=data["refdes"],
            pad=str(data["pad"]),
            name=data.get("name", ""),
            net=data.get("net", ""),
            nail=data.get("nail", nail_library.DEFAULT_TP_NAIL),
            side=data.get("side", SIDE_TOP),
            include=data.get("include", True),
            notes=data.get("notes", ""),
        )
        p.x_mm = data.get("x_mm")
        p.y_mm = data.get("y_mm")
        return p


@dataclass
class Fixture:
    """The whole reference file."""

    board: str = ""
    source_rev: str = ""
    probe_side: str = SIDE_TOP
    units: str = "mm"
    origin: str = "board_bbox_center"
    schema: int = SCHEMA_VERSION
    nail_types: Dict[str, nail_library.NailType] = field(
        default_factory=nail_library.default_library
    )
    points: List[FixturePoint] = field(default_factory=list)
    # Position keys of auto-detected DUT mounting holes the user has disabled,
    # so a disabled hole stays disabled across revisions (see MountingHole.key).
    mounting_excludes: List[str] = field(default_factory=list)

    # --- lookups ----------------------------------------------------------
    def point_by_key(self, refdes: str, pad: str) -> Optional[FixturePoint]:
        key = (refdes, str(pad))
        for p in self.points:
            if p.match_key == key:
                return p
        return None

    def point_by_id(self, point_id: str) -> Optional[FixturePoint]:
        for p in self.points:
            if p.id == point_id:
                return p
        return None

    def unique_id(self, refdes: str, pad: str) -> str:
        """Allocate a fixture id that does not collide with existing points."""
        base = make_point_id(refdes, pad)
        existing = {p.id for p in self.points}
        if base not in existing:
            return base
        n = 2
        while f"{base}_{n}" in existing:
            n += 1
        return f"{base}_{n}"

    def add_point(self, point: FixturePoint) -> None:
        if self.point_by_key(point.refdes, point.pad) is not None:
            raise ValueError(f"point {point.refdes}-{point.pad} already present")
        self.points.append(point)

    def included_points(self) -> List[FixturePoint]:
        return [p for p in self.points if p.include]

    # --- serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "board": self.board,
            "source_rev": self.source_rev,
            "probe_side": self.probe_side,
            "units": self.units,
            "origin": self.origin,
            "nail_types": nail_library.library_to_dict(self.nail_types),
            "points": [p.to_dict() for p in self.points],
            "mounting_excludes": list(self.mounting_excludes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Fixture":
        nails = (
            nail_library.library_from_dict(data["nail_types"])
            if data.get("nail_types")
            else nail_library.default_library()
        )
        fixture = cls(
            board=data.get("board", ""),
            source_rev=data.get("source_rev", ""),
            probe_side=data.get("probe_side", SIDE_TOP),
            units=data.get("units", "mm"),
            origin=data.get("origin", "board_bbox_center"),
            schema=data.get("schema", SCHEMA_VERSION),
            nail_types=nails,
            points=[FixturePoint.from_dict(p) for p in data.get("points", [])],
            mounting_excludes=list(data.get("mounting_excludes", [])),
        )
        return fixture

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    @classmethod
    def load(cls, path: str) -> "Fixture":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
