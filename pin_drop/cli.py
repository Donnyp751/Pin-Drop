"""Headless command-line front-end for pin_drop.

    python -m pin_drop.cli init   <board.kicad_pcb> [--ref f.json] [--rev C] [--auto tp|all]
    python -m pin_drop.cli update <board.kicad_pcb> [--ref f.json] [--add-new] [--accept-nets]
    python -m pin_drop.cli generate <board.kicad_pcb> [--ref f.json] [--out DIR] [--name NAME]

Loading a board requires KiCad's ``pcbnew`` Python module (works headless on a
machine with KiCad installed).  The generators/reconcile themselves are
pcbnew-free, so unit tests do not need KiCad.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import workflow
from .fixture_model import Fixture


def _load_dut(pcb_path: str):
    from . import dut_reader  # lazy: needs pcbnew
    return dut_reader.load_board(pcb_path)


def _ref_path(args) -> str:
    return args.ref or workflow.default_fixture_path(args.pcb)


def cmd_init(args) -> int:
    ref = _ref_path(args)
    if os.path.exists(ref) and not args.force:
        print(f"refusing to overwrite existing {ref} (use --force)", file=sys.stderr)
        return 1
    dut = _load_dut(args.pcb)
    fx = workflow.new_fixture(dut, source_rev=args.rev, probe_side=args.side,
                              auto_add=args.auto)
    fx.save(ref)
    print(f"created {ref}: {len(fx.points)} point(s), "
          f"{len(dut.pads)} pads / {len(dut.mounting_holes)} mounting holes on board")
    return 0


def cmd_update(args) -> int:
    ref = _ref_path(args)
    fx = Fixture.load(ref)
    dut = _load_dut(args.pcb)
    report = workflow.update_fixture(fx, dut, add_new=args.add_new,
                                     accept_nets=args.accept_nets)
    print(report.summary())
    for nc in report.net_changed:
        print(f"  NET CHANGED {nc.point.id}: {nc.old_net!r} -> {nc.new_net!r}"
              + ("  [accepted]" if args.accept_nets else "  [review]"))
    for m in report.missing:
        print(f"  MISSING {m.point.id} ({m.point.refdes}-{m.point.pad})")
    if args.add_new:
        for c in report.new:
            print(f"  ADDED {c.suggested_id} ({c.dut_pad.refdes}-{c.dut_pad.pad}) "
                  f"net={c.dut_pad.net}")
    elif report.new:
        print(f"  ({len(report.new)} new candidate(s); pass --add-new to include)")
    if args.add_new or args.accept_nets:
        fx.save(ref)
        print(f"saved {ref}")
    return 0


def cmd_generate(args) -> int:
    ref = _ref_path(args)
    fx = Fixture.load(ref)
    dut = _load_dut(args.pcb)
    out = args.out or os.path.dirname(os.path.abspath(ref))
    fp_path, sym_path, missing, report = workflow.generate(fx, dut, out, lib_name=args.name)
    print(f"footprint: {fp_path}")
    print(f"symbol:    {sym_path}")
    print(f"reconcile: {report.summary()}")
    if missing:
        print(f"WARNING: {len(missing)} point(s) had no matching pad and were "
              f"skipped: {', '.join(missing)}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pin_drop", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("pcb", help="path to the DUT .kicad_pcb")
        sp.add_argument("--ref", help="fixture reference file (default: next to board)")

    pi = sub.add_parser("init", help="create a new fixture reference file")
    common(pi)
    pi.add_argument("--rev", default="", help="source revision label")
    pi.add_argument("--side", default="top", choices=["top", "bottom"])
    pi.add_argument("--auto", choices=["tp", "all"],
                    help="pre-populate test points (tp) or test points + TH pins (all)")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    pu = sub.add_parser("update", help="reconcile a fixture against a new board revision")
    common(pu)
    pu.add_argument("--add-new", action="store_true", help="add new candidates")
    pu.add_argument("--accept-nets", action="store_true", help="accept net changes")
    pu.set_defaults(func=cmd_update)

    pg = sub.add_parser("generate", help="write the fixture footprint + symbol")
    common(pg)
    pg.add_argument("--out", help="output directory (default: alongside ref file)")
    pg.add_argument("--name", default="", help="library/part base name")
    pg.set_defaults(func=cmd_generate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
