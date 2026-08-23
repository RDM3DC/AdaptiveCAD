# AdaptiveCAD Triangle-Free Geometry Contract 1.0

## Purpose

AdaptiveCAD keeps one resolution-independent mathematical object from design
through manufacturing. A mesh may be generated as a disposable display or
legacy-export derivative, but it must never become authoritative design,
measurement, slicing, compensation, or toolpath geometry.

The machine-neutral contract is implemented by
`adaptivecad.manufacturing.curve_ir`, audited by
`adaptivecad.manufacturing.contract`, and structurally described by
`schemas/adaptivecad_curve_ir.schema.json`.

## Normative boundary

An authoritative manufacturing job passes only when all of the following are
true:

1. `triangle_mesh_input` is exactly `false`.
2. Source provenance declares `mesh_created` as exactly `false`.
3. Every manufacturing segment is an allowed analytic curve: line, circular
   arc, or cubic Bezier in contract version 1.0.
4. No triangle, facet, mesh-face, mesh-vertex, or triangle-index payload exists
   anywhere in the job graph.
5. Coordinates and tolerances are finite, units are explicit millimetres, and
   tolerance is positive.
6. Adjacent curves connect within the job tolerance; closed paths also close
   within that tolerance.
7. Recorded normal-offset error does not exceed its recorded fit tolerance.
8. Additive and subtractive derivatives retain the same stable source ID and
   byte-equivalent source provenance.

The JSON Schema performs structural validation. The semantic audit additionally
checks continuity, closure, provenance equality, nested forbidden payloads, and
recorded error bounds.

## Scale rule

Scaling acts on coordinates, curve radii, geometric tolerances, offsets,
tool/nozzle diameters, layer heights, and all other fields whose names end in
`_mm`. Feed rates, temperatures, spindle speeds, angles, IDs, roles, and
ordered curve topology do not change.

The release gate tests `0.001x`, `0.01x`, `1x`, `100x`, and `1000x`.
Every scaled job must:

- pass the semantic triangle-free audit;
- preserve the source ID;
- preserve the complete ordered topology signature;
- preserve segment, path, and layer counts;
- normalize to its original geometry within the floating-point round-trip
  limit; and
- scale geometric tolerance linearly.

This establishes resolution independence of the representation. It does not
claim that a physical cutter, nozzle, controller, or material can realize every
scale.

## Derived representations

The following are permitted only as one-way derivatives:

- transient GPU display tessellation;
- STL, OBJ, or mesh-based 3MF compatibility export;
- tolerance-controlled G1 controller linearization; and
- simulation or collision meshes explicitly marked non-authoritative.

No derivative may be re-imported automatically as the source for editing,
metrology, slicing, compensation, or manufacturing.

## Controller and machine boundary

G2, G3, and G5 are postprocessor dialects, not kernel geometry. A postprocessor
may preserve a supported native curve or linearize it within an explicit chord
tolerance. The curve IR remains authoritative in both cases.

Before executing generated files, verify the target controller's curve syntax,
machine origin, travel, extrusion convention, thermal settings, feeds, stock,
tooling, workholding, offsets, tool length, and collision safety. Included CNC
programs are finish contours only.

## Release gate

Generate the engineering benchmark:

```bash
python demo/triangle_free_engineering_bracket.py \
  --output-dir triangle_free_engineering_bracket_output
```

Re-run the independent gate:

```bash
python tools/verify_triangle_free_contract.py \
  triangle_free_engineering_bracket_output/engineering_bracket_additive_curve_job.json \
  triangle_free_engineering_bracket_output/engineering_bracket_subtractive_curve_job.json \
  --output triangle_free_engineering_bracket_output/reverified_contract_report.json
```

A release conforms only when the command exits with status zero and its report
contains `"passed": true`.

## Current engineering benchmark

The engineering frame bracket starts from one analytic 100 x 60 x 8 mm
extrusion containing a 58 x 24 mm rounded-rectangle opening, four 6.5 mm
through holes, and eight circular fillets. The additive job contains 40 layers,
6,616 paths, 1,920 circular arcs, and 6,776 lines. The subtractive finish job
contains four depth passes, 24 closed paths, 96 circular arcs, and 32 lines.

Both jobs retain source ID
`engineering-bracket-f37fc49df0bc7c2b74ee`, have identical source
provenance, and pass all ten job/scale cases from `0.001x` through `1000x`.

This is an intentionally bounded proof: analytic regularized difference for
planar rounded rectangles and circles followed by linear extrusion. Arbitrary
curved B-rep Booleans, shelling, variable fillets, loft trimming, and persistent
face naming remain later kernel milestones.
