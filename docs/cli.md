# CLI reference

The CLI mirrors the plugin for headless / scripted use:

```bash
python3 -m pin_drop.cli <command> <board.kicad_pcb> [options]
```

Loading a board requires KiCad's `pcbnew` on the Python path (true on any machine
with KiCad installed). Generation and reconcile themselves are `pcbnew`-free.

All commands accept `--ref PATH` to point at the reference file; it defaults to
`<board-name>.fixture.json` next to the board.

## `init` — create a reference file

```bash
python3 -m pin_drop.cli init board.kicad_pcb [--rev C] [--side top|bottom]
                                             [--auto tp|all] [--force]
```

| Option | Meaning |
| --- | --- |
| `--rev` | source revision label stored in the file |
| `--side` | probe side / mirroring (`top` default) |
| `--auto tp` | pre-populate **all test points** |
| `--auto all` | pre-populate **test points + through-hole pins** |
| `--force` | overwrite an existing reference file |

Without `--auto`, an empty fixture is created (add points in the plugin, or by
running `update --add-new`).

```text
$ python3 -m pin_drop.cli init board.kicad_pcb --rev C --auto tp
created board.fixture.json: 41 point(s), 739 pads / 10 mounting holes on board
```

## `update` — reconcile against a new revision

```bash
python3 -m pin_drop.cli update board.kicad_pcb [--add-new] [--accept-nets]
```

Prints the reconcile summary and the details for net-changed / missing points.

| Option | Meaning |
| --- | --- |
| (none) | report only — the file is not modified |
| `--add-new` | add all new candidates and save |
| `--accept-nets` | overwrite stored nets with the live nets and save |

```text
$ python3 -m pin_drop.cli update board-revD.kicad_pcb --ref board.fixture.json
39 matched (1 moved), 1 net-changed, 1 missing, 69 new candidate(s)
  NET CHANGED TP27: 'VSS' -> 'VPD'  [review]
  MISSING TP11 (TP11-1)
  (69 new candidate(s); pass --add-new to include)
```

## `generate` — write the fixture footprint + symbol

```bash
python3 -m pin_drop.cli generate board.kicad_pcb [--out DIR] [--name NAME]
```

| Option | Meaning |
| --- | --- |
| `--out` | output directory (default: alongside the reference file) |
| `--name` | base name for the library/part (default: `<board>_Fixture`) |

Generate always reconciles first, so coordinates are fresh and problems are
reported. It writes `<NAME>.pretty/<NAME>.kicad_mod` and `<NAME>.kicad_sym`, and
warns about any included point with no matching pad on the current board.

```text
$ python3 -m pin_drop.cli generate board.kicad_pcb --out ./fixture --name MyFixture
footprint: ./fixture/MyFixture.pretty/MyFixture.kicad_mod
symbol:    ./fixture/MyFixture.kicad_sym
reconcile: 41 matched (0 moved), 0 net-changed, 0 missing, 69 new candidate(s)
```

## Typical revision loop

```bash
# first time
python3 -m pin_drop.cli init     v1.kicad_pcb --rev 1 --auto tp
# (refine names/nails in the plugin)
python3 -m pin_drop.cli generate v1.kicad_pcb --name MyFixture

# new revision
python3 -m pin_drop.cli update   v2.kicad_pcb --ref v1.fixture.json   # review
python3 -m pin_drop.cli update   v2.kicad_pcb --ref v1.fixture.json --accept-nets --add-new
python3 -m pin_drop.cli generate v2.kicad_pcb --ref v1.fixture.json --name MyFixture
```
