# Reference file format

The reference file (`<board>.fixture.json`) is the durable record of a fixture.
It is plain, pretty-printed JSON so it diffs cleanly and lives in version control
alongside your tester project.

## Top level

```jsonc
{
  "schema": 1,                       // format version
  "board": "264545 MPS-IP REV C",   // DUT board name
  "source_rev": "C",                // revision label (free text)
  "probe_side": "top",              // default side: "top" | "bottom"
  "units": "mm",
  "origin": "board_bbox_center",    // datum: "board_bbox_center" | "board_origin"
  "nail_types": { ... },             // embedded nail-type library (see below)
  "points": [ ... ]                  // the probe points
}
```

- **probe_side** — fixture default; `bottom` mirrors generated pads in X.
- **origin** — the datum the footprint/symbol are built around. `board_bbox_center`
  centers the fixture on the DUT bounding box; `board_origin` keeps the DUT origin.

## `nail_types`

A map of `key → nail definition`. These are the exact specs used to generate this
fixture, copied in for reproducibility. Each entry:

```jsonc
"1.3mm": {
  "key": "1.3mm",
  "description": "1.3 mm plated probe holder (accepts point or cup probe nails)",
  "drill_mm": 1.3,
  "pad_mm": 1.7,
  "shape": "circle",   // "circle" | "rect"
  "plated": true,      // false = NPTH
  "part_number": "",
  "model_3d": ""
}
```

See the [nail library](nail-library.md) for the meaning of each field.

## `points`

One entry per probe target:

```jsonc
{
  "id": "J5-7",        // unique; == footprint pad number == symbol pin number
  "refdes": "J5",      // identity (with pad) — the cross-revision match key
  "pad": "7",
  "name": "TRD1_P",    // symbol pin label
  "net": "TRD1_P",     // verification check; flagged if the live net differs
  "nail": "1.3mm",     // key into nail_types
  "side": "top",       // per-point side override
  "include": true,     // generate a pad/pin for this point?
  "notes": "",
  "x_mm": 81.4956,     // last-known coordinates (informational; auto-refreshed)
  "y_mm": 127.0381     // omitted until first reconciled against a board
}
```

### Field reference

| field | required | notes |
| --- | --- | --- |
| `id` | yes | stable token; pad number == pin number. Defaults to `refdes` (single-pad) or `refdes-pad`. |
| `refdes`, `pad` | yes | identity. Coordinates are re-found by this pair every revision. |
| `name` | no | symbol pin name; defaults to the net. |
| `net` | no | stored for verification, **not** identity. A live mismatch is reported, not silently applied. |
| `nail` | no | nail type key; defaults to `1.3mm`. |
| `side` | no | `top`/`bottom`; defaults to the fixture `probe_side`. |
| `include` | no | default `true`. Excluded points stay recorded but aren't generated. |
| `notes` | no | free text. |
| `x_mm`, `y_mm` | no | last-known position; refreshed on each reconcile so movement is visible in diffs. Never used for identity. |

## Editing by hand

The file is safe to hand-edit — for bulk renames, retargeting a point's
`refdes`/`pad`, or tuning `nail_types` dimensions. It can also be produced
entirely by the plugin or CLI; all three read and write the same schema.

A complete example: [`examples/mps-ip-rev-c.fixture.json`](../examples/mps-ip-rev-c.fixture.json).
