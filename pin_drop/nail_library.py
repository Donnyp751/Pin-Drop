"""Named library of probe/nail types.

Each :class:`NailType` describes the *plated through-hole pad* that gets placed on
the tester PCB so a spring probe (pogo pin) receptacle or a solder/press nail can
be soldered into it.  The geometry is what the footprint generator stamps down at
each annotated point.

The defaults below are sensible starting values (in millimetres) for common
0.100"/2.54mm-class probes; tune ``drill_mm`` / ``pad_mm`` to the exact probe and
receptacle you settle on.  The set of types actually used by a fixture is copied
into its reference file (see :mod:`pin_drop.fixture_model`) so a generated
fixture is reproducible even if these defaults later change.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict


@dataclass(frozen=True)
class NailType:
    """A through-hole pad spec for one class of probe/nail."""

    key: str
    description: str
    drill_mm: float          # finished hole diameter for the probe receptacle/tail
    pad_mm: float            # copper pad (annular) diameter
    shape: str = "circle"    # "circle" or "rect" (KiCad pad shape token)
    plated: bool = True       # plated through-hole (signal) vs NPTH (mounting)
    part_number: str = ""     # optional vendor PN, carried into 3D/BOM later
    model_3d: str = ""        # optional path to a .step/.wrl model

    @property
    def annular_ring_mm(self) -> float:
        """Radial copper around the hole; negative means pad smaller than drill."""
        return (self.pad_mm - self.drill_mm) / 2.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NailType":
        fields = {f: data[f] for f in (
            "key", "description", "drill_mm", "pad_mm",
        )}
        for opt in ("shape", "plated", "part_number", "model_3d"):
            if opt in data:
                fields[opt] = data[opt]
        return cls(**fields)


# --- Default library --------------------------------------------------------
# These keys are referenced from a fixture's points ("nail": "<key>").

# Keys are the hole size: a nail is just a plated holder that a point- or cup-tip
# probe presses into, so the drill size is what the footprint cares about.
DEFAULT_TP_NAIL = "1.3mm"   # default probe holder for all probes (TPs + TH pins)
DEFAULT_TH_NAIL = "1.3mm"

DEFAULT_NAILS: Dict[str, NailType] = {
    "1.3mm": NailType(
        key="1.3mm",
        description="1.3 mm plated probe holder (accepts point or cup probe nails)",
        drill_mm=1.30,
        pad_mm=1.70,
    ),
    "spring_mount": NailType(
        key="spring_mount",
        description="Spring-loaded alignment mount: larger plated guide hole",
        drill_mm=5.00,
        pad_mm=7.00,
    ),
    "mounting": NailType(
        key="mounting",
        description="DUT mechanical mounting hole (5 mm, non-plated)",
        drill_mm=5.00,
        pad_mm=7.00,
        plated=False,
    ),
}


def default_library() -> Dict[str, NailType]:
    """Return a fresh copy of the default nail library."""
    return dict(DEFAULT_NAILS)


def library_to_dict(library: Dict[str, NailType]) -> dict:
    return {key: nail.to_dict() for key, nail in library.items()}


def library_from_dict(data: dict) -> Dict[str, NailType]:
    return {key: NailType.from_dict(spec) for key, spec in data.items()}
