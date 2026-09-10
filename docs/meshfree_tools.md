# Mesh-free tools: curves, evaluated sheets, and directional metric operations

## Status and launch

For both workbenches in one window, use `python run_workbenches.py`; see
`integrated_workbenches.md` for the namespace migration and save boundaries.

This is an **additive workbench/API** layered on PR #72's directional metric
module. It does not replace existing GUI commands, scenes, AMA files, or solids.
The top-level roadmap is not complete; see `TOOL_COMPLETION_MATRIX.md`.

```sh
python -m examples.meshfree_toolkit_demo --out meshfree_demo_output
python -m adaptivecad.gui.meshfree_workbench
python -m pytest -q --noconftest tests/test_directional_metric.py tests/test_meshfree_tools.py tests/test_meshfree_workbench.py
```

The GUI needs PySide6 in the existing AdaptiveCAD environment. Core new modules
use the standard library, subject to existing package-level dependencies. Tests
use NumPy/pytest; SciPy is used only as an independent test reference. The real
Qt test requires PySide6 and uses `QT_QPA_PLATFORM=offscreen` in CI.

The demo writes an editable `document.json`, `report.json`, and display-only
`preview.html`. It refuses to overwrite files. Load `document.json` with the
workbench's Open button. Select a template, edit its parameters and source names,
and Apply. All public API and command angles are **radians**. A JSON array of
commands executes as one atomic, undoable transaction. Name collisions fail
unless `"replace": true` is supplied explicitly.

The workbench displays every document entity in one shared projection and scale.
Click a wireframe to select its document object; use **Fit all** to restore the
whole-document view and **Delete selected** for an undoable deletion. Selection
is retained by object name across commands and history changes when that object
still exists.

For an opt-in menu in an existing Qt window, after constructing the window:

```python
from adaptivecad.gui.meshfree_workbench import install_meshfree_tools
install_meshfree_tools(window)
```

This adds a launcher for a **separate document**, not an automatic import of the
main window's current selection. The bridge is idempotent. No existing launcher
or GUI file is changed automatically.

### Coexistence with the metric dock

PR #74's `install_metric_workbench(window)` attaches a `QDockWidget` to an
existing Playground or SDF host and owns an independent `MetricProject`. This
mesh-free launcher owns a `ToolDocument` and its own undo/save history. The combined
integration installs both tools additively in the existing host: retain
this launcher, attach the metric dock once, and do not replace either document
model or create another host application.

There is no implicit synchronization between the two documents. A future bridge
may explicitly validate and copy compatible metric or curve data, but selection,
undo/redo, dirty state, and persistence remain owned by their source workbench
until a shared transaction and serialization contract is defined.

## Authoritative representations

`adaptivecad.geom.meshfree_tools.Curve` is immutable and stores Bezier control
coefficients (degree <=32), or an elliptic-arc frame, plus a parameter interval.
Line is a degree-one Bezier. `Curve.from_native_bezier(existing_curve)` copies the
repository's existing `BezierCurve` coefficients without tessellation.

Trim/reverse/split are exact parameter re-mappings of the stored curve, subject
to floating-point arithmetic. They are **not intersection-based trim/extend**.
Length and equal-arclength stations are numerical quadrature/root solves, not
certified error bounds. Stationary points have no defined scalar curvature.

Surfaces evaluate these constructions directly, with analytic first and second
partial derivatives (u,v in [0,1]):

| Constructor | Definition | Important boundary |
|---|---|---|
| Extrude | `S(u,v)=C(u)+v*d` | A swept sheet, not a capped solid |
| Revolve | `S=o+R_axis(angle*v)*(C(u)-o)` | Honors origin, arbitrary axis and signed partial angle |
| Ruled loft | `S=(1-v)*C0(u)+v*C1(u)` | Two registered profiles, not a multi-section smooth loft |
| Translation sweep | `S=C(u)+P(v)-P(0)` | Fixed profile orientation, not a Frenet/rotation-minimizing pipe |

`Surface.differential` returns oriented normal, first fundamental form, Gaussian
curvature, signed mean curvature and area density. Singular parameterizations
raise instead of returning a plausible normal. Surface constructors do not
promise regularity or absence of self-intersections at every parameter value.

`Surface.area` integrates the parameter domain. It counts multiplicity when a
sheet overlaps itself and is not a union area or a watertight-solid audit.
Numerical error estimates, floating-point representability, and derivative
conditioning remain relevant. There is no claim of zero error.

Move, rotate, uniform scale, plane mirror, rectangular arrays and polar arrays
preserve evaluated curves/surfaces. Full-turn polar arrays omit a duplicate seam;
partial arrays include both angular endpoints. Arrays and documents are limited
to 1000 objects. The public affine transform API also supports nonsingular
nonuniform transforms; the workbench's scale template is uniform.

`wireframe` samples curves/isoparametric lines for **display only**. It never
becomes the stored model and is never silently used as a manufacturing toolpath.

## Document and transactions

`ToolDocument` uses `adaptivecad.meshfree_tool_document`, version 1. It stores
named coefficient-based entities, explicit units and an optional metric patch.
It rejects unknown schema versions/keys, duplicate keys/names, nonfinite
geometry, unsupported types and executable expressions. Input is capped at
2 MB. It is a new experimental format, not AMA integration or STEP export.

`ToolSession.execute_many` validates all commands before committing one snapshot.
An invalid command leaves the document and undo/redo history unchanged. A new
successful edit clears redo. History retains 100 snapshots. Generated surfaces
copy immutable profile definitions; editing a source name later does **not**
recompute dependent features. An associative feature graph is separate work.

Units: `mm`, `cm`, `m`, `in`, `ft`, `ft_us`. `ft` means international foot,
0.3048 m exactly; `ft_us` means legacy US survey foot, 1200/3937 m exactly.
Conversion uses exact rational definitions followed by floating-point evaluation.
No ambiguous `feet` alias and no silent relabeling. Unit conversion scales all
world geometry and the metric's radius/length scale; curvature scales inversely
with squared length. Legacy US-survey-foot support is not advice to use that
retired unit in a new regulated survey.

## Directional metric tools

`adaptivecad.geom.meshfree_metric_tools` provides:

- Analytic Cartesian metric derivatives and Christoffel connection.
- Metric angle between tangent vectors at one point.
- Intrinsic length of a specified straight chart segment (not shortest distance).
- Intrinsic disk area and inverse area-to-radius solve inside the declared disk.
- Initial-value geodesic tracing with optional parallel transport and diagnostics.

```python
from adaptivecad.geom.directional_metric import balanced_directional_patch
from adaptivecad.geom.meshfree_metric_tools import trace_geodesic, disk_area

patch = balanced_directional_patch(length_scale=1.0, unit="mm")
ray = trace_geodesic(patch, (-0.2, 0.2), (1, 0.1), 0.5,
                     transport=(0, 1), tolerance=1e-9)
assert ray.length == 0.5
print(ray.positions[-1], ray.max_speed_drift)
print(disk_area(patch, 0.75))
```

The geodesic solver uses RK4 step doubling, dimensionless local error control,
metric-unit-speed initialization and a speed-drift acceptance gate. Coordinates
are **chart XY**, not arbitrary world XYZ or a projection onto a CAD face. A
path that leaves the patch, becomes numerically unresolvable, or exhausts its
budget raises. It does not return a truncated path labeled successful.

This is not a globally shortest-path solver, endpoint shooter, cut-locus
resolver, certified integrator, or machine trajectory. The optional transported
vector satisfies the connection's parallel-transport equation along that path.
Stored path samples are a numerical result, not a new mesh-based definition of
the geometry. General chart gluing and 3D angular-matrix metrics are not included.

## Verification and sources

Tests cover finite-difference comparisons to analytic derivatives, known
cylinder/sphere/torus geometry, transformations, units, serialization, atomic
rollback/undo/redo, invalid-input handling, independent SciPy DOP853 geodesics
using finite-difference metric derivatives, and a real optional Qt workbench.
Local test results and GitHub CI must be distinguished: skipping unavailable Qt
is not equivalent to testing Qt. No machine, OpenCascade solid or manufacturing
validation is claimed.

Standard constructions and reference documentation:

- Open CASCADE linear extrusion: https://dev.opencascade.org/doc/refman/html/class_geom___surface_of_linear_extrusion.html
- SciPy solve_ivp (independent numerical comparison): https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- NIST length-unit definitions: https://www.nist.gov/pml/us-surveyfoot
- Prior formulas, representation and caveats: `docs/directional_metric.md`.

These implement established geometry in AdaptiveCAD's representation. They do
not establish new fundamental physics or change the mathematical constant pi.
