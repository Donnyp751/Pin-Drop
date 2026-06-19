# Pin Drop

**Drop a pin on every test point.** Pin Drop turns a KiCad board into a
**bed-of-nails test fixture** — it finds your test points and through-hole pins,
lets you select and name them, and generates a matching **PCB footprint** and
**schematic symbol** to build your tester around. Crucially, it remembers your
choices so the *next board revision* is a quick diff instead of starting over.

```
DUT .kicad_pcb  ──►  select & name points  ──►  <board>.fixture.json
                                                      │
                          ┌───────────────────────────┤
                          ▼                           ▼
                  fixture .kicad_mod          fixture .kicad_sym
                 (pads + outline +           (one named pin per
                  mounting holes)             nail; pin# == pad#)
                          └──────────► your tester PCB ◄──────────┘
```

## Why

Boards designed in Altium get re-delivered and re-converted to KiCad every
revision — producing an effectively brand-new `.kicad_pcb` with all-new internal
IDs, moved parts, added/removed components. Re-annotating a fixture by hand every
time is slow and error-prone.

Pin Drop records each probe point in a small, version-controllable **reference
file** keyed by `refdes + pad` (the thing that survives re-conversion), with the
net stored as a verification check. When a new revision lands, it **reconciles**:
coordinates refresh automatically, net changes get flagged, vanished points and
new candidates are surfaced — so you only touch what actually changed.

## What it does

- **Reads** a DUT `.kicad_pcb` via KiCad's `pcbnew` API: every test point,
  through-hole pin (incl. terminal-block pins), the board outline, and mounting
  holes.
- **Selects + names** each probe point and assigns a **nail type** — interactively
  in a KiCad plugin, or headless via the CLI.
- **Persists** everything to `<board>.fixture.json`.
- **Reconciles** that file against future revisions (*matched / moved /
  net-changed / missing / new*).
- **Generates** a `.kicad_mod` footprint (one pad per nail at the DUT location,
  plus the board outline on `Edge.Cuts` and mounting holes) and a `.kicad_sym`
  symbol (one named pin per nail). Pad number == pin number == point id, so the
  two net together in your tester schematic, where you wire up the test-signal
  circuitry.

Probe side defaults to **top** (component side, no mirroring); `bottom` mirrors
the footprint in X.

## Requirements

- **KiCad 10** (provides `pcbnew` for reading boards and `wx` for the plugin GUI).
- Python 3.9+. **No third-party Python dependencies** — Pin Drop uses only the
  standard library, so it runs inside KiCad's bundled interpreter with nothing to
  install.

## Quick start

Install the KiCad plugin (points back at this checkout, so `git pull` updates it):

```bash
python3 install_plugin.py        # auto-detects ~/.local/share/kicad/<ver>
```

Then in the KiCad **PCB Editor**: *Tools → External Plugins → Refresh Plugins*,
and run **"Pin Drop: Build/Update Bed-of-Nails Fixture"**.

Prefer the terminal? The CLI does the same end to end:

```bash
python3 -m pin_drop.cli init     board.kicad_pcb --rev C --auto tp
python3 -m pin_drop.cli update   board.kicad_pcb            # see the revision diff
python3 -m pin_drop.cli generate board.kicad_pcb --out ./fixture --name MyFixture
```

## Documentation

| Doc | Contents |
| --- | --- |
| [Getting started](docs/getting-started.md) | Install, first fixture, generate, drop into a tester PCB |
| [Concepts](docs/concepts.md) | DUT, the reference file, identity key, the reconcile model |
| [Plugin guide](docs/plugin.md) | The in-KiCad dialog: views, search, highlight, save, generate |
| [CLI reference](docs/cli.md) | `init` / `update` / `generate` flags and examples |
| [Nail library](docs/nail-library.md) | Built-in nail types and how to customize geometry |
| [Reference file format](docs/reference-file.md) | The `.fixture.json` schema, field by field |
| [Architecture](docs/architecture.md) | Module map and design decisions |

A worked example reference file lives at
[`examples/mps-ip-rev-c.fixture.json`](examples/mps-ip-rev-c.fixture.json).

## Tests

```bash
python3 -m unittest discover -s tests
```

The unit tests are KiCad-free (they hand-build the DUT data structures). The
plugin GUI is smoke-tested inside KiCad; the reader, generators, reconcile, and
CLI are verified end-to-end against a real board.

## Project status

Early but functional: footprint + symbol generation and the revision-reconcile
workflow are working and tested. See the docs for current capabilities and the
[Architecture](docs/architecture.md) doc for what's intentionally out of scope.
