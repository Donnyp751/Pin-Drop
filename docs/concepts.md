# Concepts

## The DUT

The **device under test** is the board you want to probe. Pin Drop reads it from a
KiCad `.kicad_pcb` via the `pcbnew` API and normalizes it into a small set of
data: a list of pads (with reference designator, pad number, net, position, drill,
side, and whether the pad is reachable from the top), the board outline from
`Edge.Cuts`, and any mounting holes.

Each pad is **classified** to drive sensible defaults:

| Kind | How it's detected | Default nail |
| --- | --- | --- |
| `testpoint` | reference starts with `TP`, or a single-pad plated through-hole part | `1.3mm` |
| `th_pin` | plated through-hole pad of a multi-pad part (connectors, terminal blocks) | `1.7mm` |
| `smd` | surface-mount pad | (not offered by default) |
| `mounting` | non-plated hole (NPTH) | carried over as a hole, not a probe |

By default only `testpoint` and `th_pin` pads are offered as probe candidates;
SMD pads are reachable but you'd add them deliberately.

## The reference file

The reference file (`<board>.fixture.json`) is the durable artifact — the thing
worth committing to version control. It records, for each probe point you chose:

- an **id** — the stable token used as both the footprint pad number and the
  symbol pin number (this is what nets them together),
- the **refdes + pad** — its identity (see below),
- the **net** — stored as a verification check,
- the **name** (the symbol pin label), **nail** type, **side**, and an
  **include** flag,
- the **last-known coordinates** — informational only, refreshed on every
  reconcile so you can see how far a probe moved between revisions.

It also embeds the **nail-type definitions** it uses, so a fixture regenerates
identically even if the built-in defaults later change. See the full
[reference-file format](reference-file.md).

## Identity: why `refdes + pad`

Every revision is a fresh Altium→KiCad conversion, so internal KiCad IDs (KIIDs)
are regenerated and positions move. Those can't identify a point across
revisions. **Reference designator + pad number** can: `R36` stays `R36`, `J5` pin
`7` stays `J5` pin `7`, `TP25` stays `TP25`. That pair is the match key.

The **net name** is *not* used as identity — it's a check. If `J5-7` is still
present but its net changed from `TRD1_P` to something else, that's a real
electrical change you should see, not a silent remap.

## Names and ids

- **id** — unique per fixture; defaults to the refdes for single-pad parts
  (`TP25`) or `refdes-pad` for multi-pin parts (`J5-7`). Becomes the footprint
  **pad number** and the symbol **pin number**.
- **name** — the human label; becomes the symbol **pin name** (e.g. `VPD`,
  `TRD1_P`). Defaults to the net.

## The reconcile model

When you point Pin Drop at a new board revision, it diffs the reference file
against the freshly read DUT and sorts every point into one of these buckets:

| Bucket | Meaning | Action |
| --- | --- | --- |
| **matched** | found by refdes+pad, net unchanged | coordinates refreshed silently |
| **moved** | matched, but the position changed | refreshed; reported so you can sanity-check |
| **net-changed** | pad still exists, but on a different net | **flagged for review** |
| **missing** | refdes+pad no longer on the board | you remap or drop it |
| **new** | a candidate (TP / TH pin) not yet annotated | offered for inclusion |

In the plugin, net-changed and missing rows are highlighted. In the CLI they're
printed; pass `--accept-nets` and/or `--add-new` to apply changes. Keeping a
net-changed point included is treated as accepting the new net.

The result: you re-annotate only the deltas, never the whole board.

## Probe side and the datum

The generated footprint is built around a **datum** — by default the center of
the DUT's bounding box (`origin: board_bbox_center`; `board_origin` keeps the
DUT's own origin instead).

- **top** (default): pads are placed at the DUT coordinates as seen from the top.
  No mirroring.
- **bottom**: pads are mirrored in X about the datum, matching what you see
  probing the solder side.

Side is tracked per point as well as a fixture default, so a clamshell-style
mix is representable.
