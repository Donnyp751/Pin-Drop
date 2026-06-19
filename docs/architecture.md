# Architecture

Pin Drop is a small Python package that runs both inside KiCad (as an action
plugin) and standalone (as a CLI). The design goals: keep KiCad-specific code
isolated, keep the rest unit-testable without KiCad, and depend on nothing but
the standard library so it runs in KiCad's bundled interpreter.

## Module map

| Module | Role | Needs KiCad? |
| --- | --- | --- |
| `sexpr.py` | minimal S-expression writer (KiCad file syntax) | no |
| `kicad_format.py` | KiCad 10 version tokens + node helpers | no |
| `nail_library.py` | named nail/probe geometry presets | no |
| `fixture_model.py` | the `.fixture.json` model (load/save, identity) | no |
| `dut_reader.py` | `pcbnew` → normalized pads / outline / mounting holes | **yes** (lazy import) |
| `reconcile.py` | diff a fixture against a fresh board | no |
| `generate_footprint.py` | emit `.kicad_mod` | no |
| `generate_symbol.py` | emit `.kicad_sym` | no |
| `workflow.py` | shared init / update / generate orchestration | no |
| `cli.py` | headless front-end | via `dut_reader` |
| `plugin/action.py` | the `pcbnew.ActionPlugin` entry point | **yes** |
| `plugin/dialog.py` | the wx selection/generation dialog | **yes** |

Only `dut_reader`, `cli`, and `plugin/*` touch KiCad; `dut_reader` imports
`pcbnew` lazily inside its functions, so importing the rest of the package never
requires KiCad. That's what lets the test suite hand-build `DutData` and exercise
the generators and reconcile logic with no KiCad present.

## Data flow

```
            pcbnew BOARD
                 │  dut_reader.read_board / load_board
                 ▼
            DutData  ──────────────┐
   (pads, outline, mounting holes) │
                 │                 │ reconcile.reconcile
   fixture_model.Fixture ◄─────────┘   (refresh coords, classify)
   (<board>.fixture.json)              ReconcileReport
                 │
   generate_footprint.build_footprint ─► .kicad_mod
   generate_symbol.build_symbol      ─► .kicad_sym
```

`workflow.py` ties these together (`new_fixture`, `update_fixture`, `generate`)
so the CLI and plugin behave identically.

## Key decisions

- **Read KiCad, not Altium.** KiCad files are text S-expressions with a real
  Python API; Altium `.PcbDoc` is an opaque binary. The expected workflow is to
  convert Altium → KiCad first.
- **Identity is `refdes + pad`.** It's the only thing stable across the
  per-revision re-conversion. Net is a check, not an identifier. Positions and
  KIIDs are never used for identity. See [Concepts](concepts.md).
- **Write S-expressions directly.** Eeschema has no Python API, and generating a
  standalone footprint via `pcbnew` is awkward, so both `.kicad_mod` and
  `.kicad_sym` are emitted by a tiny in-repo writer. This also keeps generation
  KiCad-free and dependency-free.
- **Pad number == pin number == point id.** This is what associates the generated
  footprint and symbol in the tester schematic.
- **Stdlib only.** No third-party Python deps, so the plugin loads in KiCad's
  interpreter with nothing to install. The reference file is JSON (not YAML) for
  the same reason.
- **Deterministic UUIDs.** Generated KiCad UUIDs are derived (uuid5) from stable
  strings so regenerating a fixture produces clean diffs.

## File-format versions

`kicad_format.py` pins the format tokens Pin Drop emits, sampled from KiCad 10:
footprint `version 20260206`, symbol `version 20251024`, `generator "pin_drop"`.
Bump these here if you target a newer KiCad format.

## Out of scope (for now)

- Auto-placing a breakout/connector or generating a full tester PCB.
- Click-to-add probe selection on the canvas (selection is via the candidate list
  + search).
- 3D models for probes and a fixture BOM.
