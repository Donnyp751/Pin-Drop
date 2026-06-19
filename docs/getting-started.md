# Getting started

This walks through building your first fixture, from a converted DUT board to a
footprint + symbol you can drop into a tester PCB.

## 1. Prerequisites

- **KiCad 10** installed (Pin Drop uses its `pcbnew` and `wx`).
- Your DUT board as a **`.kicad_pcb`**. If your source is Altium, convert it to
  KiCad first (File → Import, or KiCad's Altium importer). Pin Drop reads the
  KiCad file, not the Altium binary.

No `pip install` is needed — Pin Drop is pure standard library and runs inside
KiCad's bundled Python.

## 2. Install the plugin

From this repository:

```bash
python3 install_plugin.py
```

This drops a tiny loader stub into KiCad's plugin folder
(`~/.local/share/kicad/<version>/scripting/plugins/`) that points back here, so
updating Pin Drop is just `git pull`. In KiCad's **PCB Editor**, run
*Tools → External Plugins → Refresh Plugins*. You'll get a **"Pin Drop:
Build/Update Bed-of-Nails Fixture"** button/menu item.

To remove it: `python3 install_plugin.py --uninstall`.

## 3. Build a fixture (plugin)

1. Open your converted DUT board in the PCB Editor.
2. Run Pin Drop. On first run it lists every probe **candidate** (test points and
   through-hole pins).
3. For each point you want to probe: tick **Use**, set a **Name** (defaults to the
   net), pick a **Nail** type and **Side**.
   - Use the **View** filter and **Search** box to find specific points — e.g.
     type `J5` to bring up a terminal block's pins.
   - Selecting a row **highlights that pad** on the board canvas.
4. Click **Save reference** to write `<board>.fixture.json` next to your board.
5. Click **Generate footprint + symbol** and choose an output folder.

See the [Plugin guide](plugin.md) for the full dialog reference.

## 4. Build a fixture (CLI alternative)

Everything the plugin does is available headless:

```bash
# Capture all test points automatically into a new reference file
python3 -m pin_drop.cli init board.kicad_pcb --rev C --auto tp

# Generate the fixture library
python3 -m pin_drop.cli generate board.kicad_pcb --out ./fixture --name MyFixture
```

See the [CLI reference](cli.md) for all options.

## 5. Use it in your tester PCB

The generator writes two files:

- `<name>.pretty/<name>.kicad_mod` — the fixture footprint (all nail pads at the
  DUT coordinates, the board outline on `Edge.Cuts`, and mounting holes).
- `<name>.kicad_sym` — the matching schematic symbol (one named pin per nail).

Add the `.pretty` folder as a footprint library and the `.kicad_sym` as a symbol
library in your **tester** project. Place the symbol in your tester schematic;
because each pad number equals its pin number, the footprint and symbol associate
directly. Wire your test-signal circuitry to the named pins, then lay out the
tester PCB — the footprint already carries the probe positions, outline, and
mounting holes for you.

## 6. Next revision

When a new board revision arrives, re-convert it and run an **update** — Pin Drop
re-finds your points by `refdes + pad`, refreshes coordinates, and reports what
changed. See [Concepts → the reconcile model](concepts.md#the-reconcile-model).

```bash
python3 -m pin_drop.cli update board-revD.kicad_pcb --ref board.fixture.json
```
