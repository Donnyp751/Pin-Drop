# Nail library

A **nail type** describes the plated through-hole pad that gets placed on the
tester PCB so a spring probe (pogo pin) receptacle or a solder/press nail can be
soldered in. Each annotated point is assigned a nail type; the generator stamps
that geometry at the point's location.

Types are named by **hole size**: a nail is just a plated holder that a point- or
cup-tip probe presses into, so the drill diameter is what the footprint cares
about.

## Built-in types

| key | drill (mm) | pad (mm) | plated | intended use |
| --- | --- | --- | --- | --- |
| `1.3mm` | 1.30 | 1.70 | yes | probe holder for point/cup nails — **default for all probes** |
| `spring_mount` | 5.00 | 7.00 | yes | spring-loaded alignment guide hole |
| `mounting` | 5.00 | 7.00 | no | NPTH mechanical mounting hole for the DUT |

The defaults map both test-point and through-hole-pin candidates → `1.3mm`
(`DEFAULT_TP_NAIL` / `DEFAULT_TH_NAIL`).

`mounting` is special: actual mounting holes are detected on the DUT (as NPTH
pads or `MountingHole*` footprints) and reproduced with their real drill size (a
7 mm pad ring around it), so you don't assign this type by hand.

## Fields

Each nail type (`pin_drop/nail_library.py`, `NailType`) has:

| field | meaning |
| --- | --- |
| `key` | the name referenced from a point's `nail` |
| `description` | human note |
| `drill_mm` | finished hole diameter |
| `pad_mm` | copper pad (annular) diameter |
| `shape` | `circle` or `rect` |
| `plated` | plated through-hole (signal) vs NPTH (mechanical) |
| `part_number`, `model_3d` | optional, carried for future BOM/3D use |

`annular_ring_mm` is derived as `(pad_mm - drill_mm) / 2`.

## Customizing

Two ways to change geometry:

1. **Edit the defaults** in `pin_drop/nail_library.py` — affects new fixtures.
2. **Edit a fixture's embedded library** directly in its `.fixture.json` under
   `nail_types` — affects just that fixture, and is what gets used at generate
   time (the generator prefers the fixture's own definitions, falling back to the
   built-ins).

Because every fixture stores the nail definitions it uses, a generated fixture is
reproducible even if the built-in defaults change later.

> Dimensions are starting points. Tune `drill_mm`/`pad_mm` to your actual spring
> probe and its receptacle/solder tail before committing to a fab run.

## Adding a type

Add an entry to `DEFAULT_NAILS`:

```python
"2.0mm": NailType(
    key="2.0mm",
    description="2.0 mm plated probe hole",
    drill_mm=2.0,
    pad_mm=2.8,
),
```

It then appears in the plugin's **Nail** dropdown and can be referenced by points
in any new fixture.
