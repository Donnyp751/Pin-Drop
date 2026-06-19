"""wx dialog for selecting, naming and generating the fixture.

Presents one grid row per probe candidate -- existing fixture points plus the
new candidates surfaced by reconcile -- so the user can tick what to include,
name it, choose a nail type, and see the reconcile status (matched / moved /
net-changed / missing / new) at a glance.  Selecting a row focuses the
corresponding pad on the board canvas.
"""

from __future__ import annotations

import os

import pcbnew
import wx
import wx.grid

from .. import nail_library, workflow

COL_INC, COL_REF, COL_PAD, COL_NET, COL_NAME, COL_NAIL, COL_SIDE, COL_STATUS = range(8)
COLS = [
    ("Use", 45), ("Ref", 70), ("Pad", 50), ("Net", 130),
    ("Name", 150), ("Nail", 90), ("Side", 70), ("Status", 130),
]
SIDES = ["top", "bottom"]

VIEW_ALL = "All"
VIEW_ANNOTATED = "Annotated"
VIEW_NEW = "New candidates"
VIEW_REVIEW = "Needs review"
VIEWS = [VIEW_ALL, VIEW_ANNOTATED, VIEW_NEW, VIEW_REVIEW]


class _Row:
    __slots__ = ("point", "candidate", "refdes", "pad", "kind", "live_net",
                 "name", "nail", "side", "include", "status", "net_changed",
                 "missing", "live_xy")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def is_new(self):
        return self.candidate is not None

    @property
    def needs_review(self):
        return bool(self.missing or self.net_changed)


class FixtureDialog(wx.Dialog):
    def __init__(self, parent, fixture, dut, report, ref_path, board=None):
        super().__init__(parent, title="Pin Drop — Bed-of-Nails Fixture",
                         size=(820, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.fixture = fixture
        self.dut = dut
        self.report = report
        self.ref_path = ref_path
        self.board = board
        self.nail_choices = list(fixture.nail_types.keys()) or [nail_library.DEFAULT_TP_NAIL]

        self.rows = self._build_rows()
        self.visible = []
        self._build_ui()
        self._populate()

    # --- model ------------------------------------------------------------
    def _build_rows(self):
        moved = {m.point.id: m for m in self.report.matched}
        netchg = {n.point.id: n for n in self.report.net_changed}
        missing = {m.point.id for m in self.report.missing}
        rows = []
        for p in self.fixture.points:
            live = self.dut.pad_by_key(p.refdes, p.pad)
            if p.id in missing:
                status, live_net = "MISSING", p.net
                live_xy = (p.x_mm, p.y_mm)
                netc, miss = False, True
            elif p.id in netchg:
                nc = netchg[p.id]
                status = f"NET {nc.old_net}->{nc.new_net}"
                live_net = nc.new_net
                live_xy = (live.x_mm, live.y_mm)
                netc, miss = True, False
            else:
                m = moved.get(p.id)
                status = (f"moved {m.dx_mm:.1f},{m.dy_mm:.1f}"
                          if (m and m.moved) else "ok")
                live_net = live.net if live else p.net
                live_xy = (live.x_mm, live.y_mm) if live else (p.x_mm, p.y_mm)
                netc, miss = False, False
            rows.append(_Row(
                point=p, candidate=None, refdes=p.refdes, pad=p.pad,
                kind="", live_net=live_net, name=p.name, nail=p.nail,
                side=p.side, include=p.include, status=status,
                net_changed=netc, missing=miss, live_xy=live_xy))

        for c in self.report.new:
            dp = c.dut_pad
            rows.append(_Row(
                point=None, candidate=c, refdes=dp.refdes, pad=dp.pad,
                kind=dp.kind, live_net=dp.net, name=c.suggested_name,
                nail=(nail_library.DEFAULT_TH_NAIL if dp.kind == "th_pin"
                      else nail_library.DEFAULT_TP_NAIL),
                side=self.fixture.probe_side, include=False, status="new",
                net_changed=False, missing=False, live_xy=(dp.x_mm, dp.y_mm)))
        return rows

    def _filtered(self):
        view = self.view.GetStringSelection()
        needle = self.search.GetValue().strip().lower()
        out = []
        for r in self.rows:
            if view == VIEW_ANNOTATED and (r.is_new or not r.include):
                continue
            if view == VIEW_NEW and not r.is_new:
                continue
            if view == VIEW_REVIEW and not r.needs_review:
                continue
            if needle:
                hay = f"{r.refdes} {r.pad} {r.live_net} {r.name} {r.status}".lower()
                if needle not in hay:
                    continue
            out.append(r)
        return out

    # --- ui ---------------------------------------------------------------
    def _build_ui(self):
        root = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(wx.StaticText(self, label="View:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.view = wx.Choice(self, choices=VIEWS)
        self.view.SetSelection(0)
        self.view.Bind(wx.EVT_CHOICE, lambda e: self._populate())
        top.Add(self.view, 0, wx.ALL, 4)
        top.Add(wx.StaticText(self, label="Search:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.search = wx.TextCtrl(self)
        self.search.Bind(wx.EVT_TEXT, lambda e: self._populate())
        top.Add(self.search, 1, wx.ALL | wx.EXPAND, 4)
        root.Add(top, 0, wx.EXPAND)

        self.grid = wx.grid.Grid(self)
        self.grid.CreateGrid(0, len(COLS))
        for i, (label, w) in enumerate(COLS):
            self.grid.SetColLabelValue(i, label)
            self.grid.SetColSize(i, w)
        self.grid.SetRowLabelSize(0)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self._on_cell_changed)
        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self._on_select)
        root.Add(self.grid, 1, wx.EXPAND | wx.ALL, 4)

        self.summary = wx.StaticText(self, label=self.report.summary())
        root.Add(self.summary, 0, wx.ALL, 4)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        b_all = wx.Button(self, label="Check shown")
        b_all.Bind(wx.EVT_BUTTON, lambda e: self._bulk_check(True))
        b_none = wx.Button(self, label="Uncheck shown")
        b_none.Bind(wx.EVT_BUTTON, lambda e: self._bulk_check(False))
        b_save = wx.Button(self, label="Save reference")
        b_save.Bind(wx.EVT_BUTTON, self._on_save)
        b_gen = wx.Button(self, label="Generate footprint + symbol")
        b_gen.Bind(wx.EVT_BUTTON, self._on_generate)
        b_close = wx.Button(self, wx.ID_CLOSE, label="Close")
        b_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        for b in (b_all, b_none):
            btns.Add(b, 0, wx.ALL, 4)
        btns.AddStretchSpacer()
        for b in (b_save, b_gen, b_close):
            btns.Add(b, 0, wx.ALL, 4)
        root.Add(btns, 0, wx.EXPAND)

        self.SetSizer(root)

    def _populate(self):
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.visible = self._filtered()
        self.grid.AppendRows(len(self.visible))
        for r, row in enumerate(self.visible):
            self._set_row(r, row)
        self.grid.ForceRefresh()

    def _set_row(self, r, row):
        g = self.grid
        g.SetCellValue(r, COL_INC, "1" if row.include else "")
        g.SetCellRenderer(r, COL_INC, wx.grid.GridCellBoolRenderer())
        g.SetCellEditor(r, COL_INC, wx.grid.GridCellBoolEditor())
        g.SetCellValue(r, COL_REF, str(row.refdes))
        g.SetCellValue(r, COL_PAD, str(row.pad))
        g.SetCellValue(r, COL_NET, str(row.live_net or ""))
        g.SetCellValue(r, COL_NAME, str(row.name or ""))
        g.SetCellValue(r, COL_NAIL, str(row.nail))
        g.SetCellEditor(r, COL_NAIL, wx.grid.GridCellChoiceEditor(self.nail_choices, False))
        g.SetCellValue(r, COL_SIDE, str(row.side))
        g.SetCellEditor(r, COL_SIDE, wx.grid.GridCellChoiceEditor(SIDES, False))
        g.SetCellValue(r, COL_STATUS, str(row.status))
        for c in (COL_REF, COL_PAD, COL_NET, COL_STATUS):
            g.SetReadOnly(r, c, True)
        if row.needs_review:
            for c in range(len(COLS)):
                g.SetCellBackgroundColour(r, c, wx.Colour(255, 235, 200))

    # --- events -----------------------------------------------------------
    def _on_cell_changed(self, evt):
        r, c = evt.GetRow(), evt.GetCol()
        if r >= len(self.visible):
            return
        row = self.visible[r]
        val = self.grid.GetCellValue(r, c)
        if c == COL_INC:
            row.include = val in ("1", "yes", "true", "True")
        elif c == COL_NAME:
            row.name = val
        elif c == COL_NAIL:
            row.nail = val
        elif c == COL_SIDE:
            row.side = val
        evt.Skip()

    def _on_select(self, evt):
        r = evt.GetRow()
        if 0 <= r < len(self.visible):
            self._focus(self.visible[r])
        evt.Skip()

    def _bulk_check(self, state):
        for r, row in enumerate(self.visible):
            row.include = state
            self.grid.SetCellValue(r, COL_INC, "1" if state else "")
        self.grid.ForceRefresh()

    def _focus(self, row):
        if not self.board:
            return
        try:
            fp = self.board.FindFootprintByReference(row.refdes)
            if not fp:
                return
            target = None
            for p in fp.Pads():
                if p.GetNumber() == str(row.pad):
                    target = p
                    break
            pcbnew.FocusOnItem(target or fp)
        except Exception:
            pass

    # --- persistence ------------------------------------------------------
    def _commit(self):
        for row in self.rows:
            if row.point is not None:
                row.point.include = row.include
                row.point.name = row.name
                row.point.nail = row.nail
                row.point.side = row.side
                if row.live_xy and row.live_xy[0] is not None:
                    row.point.x_mm, row.point.y_mm = row.live_xy
                # Keeping a net-changed point included is treated as acceptance.
                if row.net_changed and row.include:
                    row.point.net = row.live_net
            elif row.include:  # new candidate, now chosen
                if self.fixture.point_by_key(row.refdes, row.pad) is None:
                    from ..fixture_model import FixturePoint
                    np = FixturePoint(
                        id=self.fixture.unique_id(row.refdes, row.pad),
                        refdes=row.refdes, pad=row.pad, name=row.name,
                        net=row.live_net, nail=row.nail, side=row.side)
                    np.x_mm, np.y_mm = row.live_xy
                    self.fixture.add_point(np)

    def _on_save(self, _evt):
        self._commit()
        self.fixture.save(self.ref_path)
        wx.MessageBox(f"Saved {len(self.fixture.included_points())} point(s) to:\n"
                      f"{self.ref_path}", "Saved", wx.OK | wx.ICON_INFORMATION)

    def _on_generate(self, _evt):
        self._commit()
        self.fixture.save(self.ref_path)
        dd = wx.DirDialog(self, "Output directory for the fixture library",
                          defaultPath=os.path.dirname(self.ref_path))
        if dd.ShowModal() != wx.ID_OK:
            dd.Destroy()
            return
        out = dd.GetPath()
        dd.Destroy()
        fp, sym, missing, report = workflow.generate(self.fixture, self.dut, out)
        msg = (f"Footprint:\n  {fp}\n\nSymbol:\n  {sym}\n\n{report.summary()}")
        if missing:
            msg += f"\n\nSkipped (no matching pad): {', '.join(missing)}"
        wx.MessageBox(msg, "Generated", wx.OK | wx.ICON_INFORMATION)
