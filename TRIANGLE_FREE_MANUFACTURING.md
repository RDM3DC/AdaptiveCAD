# Triangle-Free Direct Manufacturing

AdaptiveCAD now includes two tested vertical slices from one curve-native source
to both printer and CNC programs: the periodic Infinity Root loft and an
ordinary engineering frame bracket with analytic Boolean cuts, holes, and
fillets. These are usable proofs of a broader triangle-free stack, not yet a
general-purpose replacement for a production slicer or CAM system.

## What the vertical slice does

| Stage | Representation | Current implementation |
|---|---|---|
| Source | Periodic cubic-Bezier loft or analytic planar Boolean extrusion | `InfinityRootLoftSource`, `EngineeringBracketSource` |
| Shared IR | Lines, circular arcs, cubic Béziers, paths, layers | `adaptivecad.manufacturing.curve_ir` |
| Additive plan | Curve perimeters plus concentric or analytically clipped infill | `plan_additive_loft`, `plan_engineering_bracket_additive` |
| Subtractive plan | Analytic tool-radius-compensated finish contours | `plan_subtractive_waterlines`, `plan_engineering_bracket_subtractive` |
| Native post | G1 lines, G2/G3 arcs, common XY G5 cubic Béziers | `adaptivecad.manufacturing.gcode` |
| Compatibility post | Tolerance-controlled G1 machine motion | Same postprocessor, `linearized` mode |
| Audit | Entity counts, closure, source identity, forbidden-kind and scale gates | `audit_triangle_free_job`, `adaptivecad.manufacturing.contract` |

The authoritative IR has no face, facet, mesh, or triangle entity. Both jobs
carry the same deterministic `source_id`, which makes the shared-source claim
machine-checkable instead of just descriptive.

The stricter release contract and scale gate are specified in
[Triangle-Free Geometry Contract 1.0](TRIANGLE_FREE_GEOMETRY_CONTRACT.md).

## Infinity Root interpretation

The source preserves three different meanings:

- Integer root pages are canonical data from the exact lift tower.
- Fractional pages are declared gauge views and carry their gauge metadata.
- Cross-sections between declared pages are physical fabrication lofts. They
  are explicitly not claimed as additional fractional Infinity Root iterates.

The cross-section curves interpolate sampled Infinity Root profiles with
periodic cubic Béziers. They are smooth curve entities, but they are still a
numerical representation of the sampled source rather than symbolic exact
curves.

Printer perimeter centerlines and CNC tool-center waterlines are fitted along
the evaluated local normal of those boundary curves. The fitter adaptively
doubles cubic spans and records its maximum internal validation error and
tolerance in each path's metadata. This avoids treating a radial scale as
normal compensation on a deformed profile.

## Engineering bracket interpretation

The second benchmark is a 100 x 60 x 8 mm analytic extrusion. Its region is a
regularized difference between an R8 rounded rectangle, one 58 x 24 mm R4.5
rounded-rectangle opening, and four 6.5 mm circular holes. Lines and exact
circular arcs represent all eight fillets and all cut boundaries.

Additive perimeters are analytic offsets. Infill scanlines are clipped directly
against the rounded rectangles and circles rather than a raster or mesh.
Subtractive finish paths are exact tool-center offsets for the outer boundary,
central opening, and holes. This proves the architecture for this bounded 2.5D
class; it does not claim arbitrary 3D B-rep Boolean robustness.

## Run the benchmark

From the repository root:

```bash
python demo/triangle_free_infinity_root_manufacturing.py \
  --output-dir triangle_free_full_stack_output
```

Generate the ordinary engineering benchmark with:

```bash
python demo/triangle_free_engineering_bracket.py \
  --output-dir triangle_free_engineering_bracket_output
```

That generator writes the analytic source, additive and subtractive curve jobs,
native G2/G3 and tolerance-controlled G1 programs, the semantic/scale report,
an SVG preview, and a checksum-validated ZIP bundle.

The Infinity Root generator writes and validates:

| Artifact | Purpose |
|---|---|
| `infinity_root_additive_curve_job.json` | Authoritative additive curve job |
| `infinity_root_subtractive_curve_job.json` | Authoritative CNC curve job |
| `infinity_root_printer_native_g5.gcode` | Native cubic printer program |
| `infinity_root_printer_linearized.gcode` | G1 printer compatibility program |
| `infinity_root_cnc_native_g5.nc` | Native cubic CNC finish program |
| `infinity_root_cnc_linearized.nc` | G1 CNC compatibility program |
| `triangle_free_manufacturing_report.json` | Source, IR, and postprocessor audits |
| `triangle_free_full_stack.svg` / `.png` | Curve-only visual preview |
| `triangle_free_infinity_root_full_stack.zip` | Validated bundle with SHA-256 manifest |

Run the focused tests with:

```bash
python -m unittest discover -s tests -p 'test_triangle_free_manufacturing.py' -v
python -m unittest discover -s tests -p 'test_triangle_free_engineering_bracket.py' -v
```

## Controller and safety boundaries

The native files use the common XY cubic G5 convention documented in their
headers: I/J locate the first control point relative to the segment start, and
P/Q locate the second control point relative to the segment end. G-code
dialects are controller-specific. Confirm this convention and support for
extrusion on G5 before sending a native printer file to hardware.

That convention matches the official [Marlin G5 documentation](https://marlinfw.org/docs/gcode/G005.html)
and [LinuxCNC G5 documentation](https://linuxcnc.org/docs/html/gcode/g-code.html#gcode:g5).
Other firmware and controls may interpret or reject the same words differently.

Linearized mode is the compatibility path. It approximates curves with G1
motion to a configured chord tolerance, but it does not create a surface mesh
or triangles. Triangle-free does not mean approximation-free: sampled source
profiles, floating-point evaluation, controller interpolation, and physical
machine error still have tolerances.

The CNC output is deliberately limited to compensated finish waterlines. It is
not safe to run until a machinist defines and verifies stock, roughing,
workholding, tool geometry and length, work offsets, entry strategy, machine
limits, and collision clearance.

## Current boundary and next milestones

The current slices support the Infinity Root radial loft and a bounded analytic
2.5D Boolean extrusion. A general triangle-free manufacturing stack still
needs:

1. An OCC B-Rep section adapter that preserves analytic lines, arcs, ellipses,
   and NURBS instead of tessellating them.
2. A predictor-corrector contour tracer for implicit/SDF sources, with topology
   event handling and certified error bounds.
3. Robust planar arrangement, offset, clipping, nesting, and infill operations
   over the shared curve IR.
4. Full additive process planning and full CNC roughing, entry, rest machining,
   stock simulation, collision checking, and machine profiles.
5. Controller-specific postprocessor profiles and hardware validation fixtures.

The existing `adaptivecad.app.sdf_slicer` remains a separate grid-sampled,
marching-squares route. It also avoids a triangle input mesh, but its G1
contours are bounded by raster resolution and are not the curve-native route
described here.
