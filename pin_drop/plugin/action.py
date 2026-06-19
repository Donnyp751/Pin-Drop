"""The pcbnew ActionPlugin: load the open board, reconcile, open the dialog."""

from __future__ import annotations

import os
import traceback

import pcbnew


class FixtureBuilderPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Pin Drop: Build/Update Bed-of-Nails Fixture"
        self.category = "Fixtures"
        self.description = (
            "Select and name test points / through-hole pins on the open DUT "
            "board, persist them to a reference file, and generate a fixture "
            "footprint + schematic symbol."
        )
        self.show_toolbar_button = True
        icon = os.path.join(os.path.dirname(__file__), "icon.png")
        self.icon_file_name = icon if os.path.exists(icon) else ""

    def Run(self):
        try:
            _run()
        except Exception:  # pragma: no cover - surfaced in a KiCad message box
            import wx
            wx.MessageBox(traceback.format_exc(), "Pin Drop error",
                          wx.OK | wx.ICON_ERROR)


def _run():
    import wx

    from .. import dut_reader, reconcile, workflow
    from ..fixture_model import Fixture
    from .dialog import FixtureDialog

    board = pcbnew.GetBoard()
    pcb_path = board.GetFileName()
    board_name = os.path.splitext(os.path.basename(pcb_path))[0] if pcb_path else "board"
    dut = dut_reader.read_board(board, board_name)

    ref_path = workflow.default_fixture_path(pcb_path) if pcb_path else \
        os.path.join(os.getcwd(), workflow.safe_name(board_name) + ".fixture.json")

    if os.path.exists(ref_path):
        fixture = Fixture.load(ref_path)
    else:
        fixture = workflow.new_fixture(dut, source_rev="", probe_side="top")

    report = reconcile.reconcile(fixture, dut)

    parent = wx.GetActiveWindow()
    dlg = FixtureDialog(parent, fixture=fixture, dut=dut, report=report,
                        ref_path=ref_path, board=board)
    dlg.ShowModal()
    dlg.Destroy()
