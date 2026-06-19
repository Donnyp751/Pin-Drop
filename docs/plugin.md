# Plugin guide

The Pin Drop action plugin runs inside KiCad's **PCB Editor** and is the most
ergonomic way to select and name probe points against the real board.

## Install / update / remove

```bash
python3 install_plugin.py              # install (auto-detect KiCad version dir)
python3 install_plugin.py --plugins-dir /path/to/scripting/plugins
python3 install_plugin.py --uninstall
```

The installer writes a small loader stub (`pin_drop_loader.py`) into KiCad's
plugin folder that adds this checkout to `sys.path` and registers the plugin. Run
*Tools → External Plugins → Refresh Plugins* in KiCad after installing or after a
`git pull`.

## Launching

1. Open your DUT `.kicad_pcb` in the PCB Editor.
2. *Tools → External Plugins → **Pin Drop: Build/Update Bed-of-Nails Fixture***
   (also available as a toolbar button).

On launch Pin Drop reads the open board, looks for `<board>.fixture.json` next to
it, and — if found — **reconciles** it against the current board before showing
the dialog. If not found, it starts a fresh fixture listing all candidates.

## The dialog

A single grid lists every relevant point — your existing fixture points plus the
new candidates surfaced by reconcile.

**Controls**

- **View** — filter the rows:
  - *All* — everything
  - *Annotated* — points already included in the fixture
  - *New candidates* — pads not yet in the fixture
  - *Needs review* — only net-changed and missing points
- **Search** — substring filter over ref, pad, net, name, and status.

**Columns**

| Column | Editable | Notes |
| --- | --- | --- |
| **Use** | ✓ | include this point in the fixture |
| **Ref** / **Pad** | | the identity (read-only) |
| **Net** | | live net from the board (read-only) |
| **Name** | ✓ | symbol pin label; defaults to the net |
| **Nail** | ✓ | nail type, from the fixture's library |
| **Side** | ✓ | `top` or `bottom` |
| **Status** | | reconcile result: `ok`, `moved …`, `NET a->b`, `MISSING`, `new` |

Rows that **need review** (net-changed or missing) are highlighted.

**Actions**

- Selecting a row **focuses the corresponding pad** on the board canvas.
- **Check shown / Uncheck shown** — bulk toggle the Use box on the filtered rows.
- **Save reference** — write `<board>.fixture.json`.
- **Generate footprint + symbol** — saves the reference, then prompts for an
  output directory and writes the `.kicad_mod` and `.kicad_sym`.
- **Close** — dismiss (unsaved edits are discarded).

## Tips

- To grab an awkward point like a terminal-block pin, search its refdes (e.g.
  `J5`), then tick the specific pad and rename it.
- Keeping a **net-changed** point checked when you Save accepts the new net as the
  stored value going forward.
- The plugin and the [CLI](cli.md) share the same reference file, so you can mix
  and match — annotate interactively, then script generation in CI, for example.

## Limitations

- Probe selection is from the candidate list (with search), not by free-form
  click-to-add on the canvas — that's a possible future enhancement.
- The dialog is exercised inside KiCad; there's no headless GUI test.
