# AdaptiveCAD tool-completion matrix

This is a scoped inventory, **not a declaration that the 200-task roadmap in
AGENTS.md is finished**. Baseline: main d6111436 and directional PR #72
fab09650018fbda0f45226b7f4aabb4a69fc6e27. No car/Inventor-GUI branch is modified.

## Added by the mesh-free toolkit

| Tool family | Delivered | Acceptance evidence / remaining boundary |
|---|---|---|
| Line/Bezier/circle/elliptic arc | Coefficient-based curve evaluator | Derivatives, trims, reversal, length controls |
| Edit operations | Copy/move/rotate/uniform scale/plane mirror | Immutable inputs; transform and reflection tests |
| Curve trim/split/reverse | Parameter-based | No intersection picking or boundary extension yet |
| Pattern tools | Rectangular and polar arrays | No duplicate full-circle seam; bounded sizes; transactional writes |
| Extrusion | Evaluated general profile sheet | Analytic derivatives; no caps/topology |
| Revolution | Arbitrary axis/origin, signed partial/full angle | Endpoint, derivative, sphere/torus tests |
| Loft | Exact two-profile ruled sheet | Profile boundary tests; not multi-section loft |
| Sweep | Fixed-orientation translation sheet | Path anchoring and derivative tests; not swept solid/transported frame |
| Surface inspection | Normal, metric, Gaussian/mean curvature, area | Known shapes and finite-difference checks; singular points rejected |
| Curve inspection | Length, scalar curvature, equal-length stations | Numerical comparisons and failures on undefined curvature |
| Metric inspection | Directional Pi from #72, angles, area, area-root | Flat and balanced nonflat controls |
| Metric paths | IVP geodesics, parallel transport | Independent numerical solver; no global shortest-path guarantee |
| Units | Explicit mm/cm/m/in/ft/ft_us | Unit and inverse-squared curvature scaling tests |
| Persistence/history | Strict separate JSON, undo/redo, atomic batches | Round-trip, duplicate/unknown/nonfinite rejection, rollback tests |
| User interface | Standalone workbench and explicit Qt menu bridge | GUI smoke test separate from core tests; main scene not auto-connected |
| Headless use | Runnable example + report + HTML wireframe | Real subprocess / refusal-to-overwrite tests |

## Existing implementations observed, not re-certified by this change

The app tree already includes boolean_ops.py, edge_tools.py, shell_tools.py,
array_tools.py, construction_tools.py, transform_tools.py, sketch_tools.py,
measurement_tools.py and sdf_slicer.py. Their presence does not establish full
CAD-grade completeness; this update neither replaces nor claims to validate them.

The inspected app/extrude_tools.py describes primitive approximations: its
revolve function does not use the supplied axis/angle to construct general
revolution geometry; loft/sweep return primitive lists. Those legacy behaviors
are unchanged. The new evaluated-sheet API avoids silently presenting those
approximations as exact profile modeling, without breaking current callers.

## Remaining work with acceptance gates

| Priority | Missing integration/capability | Completion gate |
|---|---|---|
| 1 | Main GUI selection, undo stack and feature browser integration | End-to-end create/edit/save/reopen tests in the intended GUI |
| 1 | Associative feature dependencies | Changing a profile recomputes dependent features with undo/redo |
| 1 | Topological faces, caps, sewing and validity | Closed oriented watertight solids and degenerate-case tests |
| 1 | Robust solid booleans and push-pull | Union/cut/intersection regression corpus, tangencies and thin features |
| 1 | Intersection-based trim/extend, offsets | Tolerance-aware curve/surface intersection and self-intersection tests |
| 2 | Fillets/chamfers/shell/draft/hole tools on exact solids | Geometry/topology tests, failure diagnostics, GUI picking |
| 2 | Multi-profile smooth loft and orientation-controlled sweep | Continuity/frame/twist/self-intersection tests |
| 2 | Sketch constraints, dimensions and snap coverage | Expand audited subset of the existing AGENTS.md tasks |
| 2 | Native AMA/STEP/DXF integration | Schema/version/units/topology round-trips without silent mesh fallback |
| 2 | Metric-to-embedded-face mapping and chart atlas | Compatible overlap maps, lengths/curvature and seam tests |
| 2 | Three-dimensional directional angular metric | Full matrix data and anisotropic curvature verification |
| 2 | Civil alignment recreation and printed-plan precision | US-survey-foot legacy fixtures, bearings/stations and residual budgets |
| 3 | Certified/adaptive precision and error propagation | Conservative bounds and failure on unresolved cases |
| 3 | Manufacturing pipelines | Stock, roughing, collision clearance, offsets and controller-dialect tests |
| 3 | Direct printer/controller integration | Hardware-specific validation; no uncertified toolpaths sent to a machine |
| ongoing | Repository-wide CI health | Repair pre-existing lint/type/test failures without suppressing checks |

No unsupported menu command is advertised as implemented. No generic Boolean,
fillet, shell or G-code placeholder is added by this change.
