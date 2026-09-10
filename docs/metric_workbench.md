# Adaptive-pi metric workbench

This workbench turns the directional measurement API from PR #72 into interactive
tools **inside the existing Playground and SDF applications**. It does not replace
either application's scene, solid history, or ordinary Euclidean tools.

## Start it

Use your existing AdaptiveCAD environment with PySide6 installed. Do not mix
CadQuery/OCP into the Playground's pythonocc-core environment just for these tools.
From the repository root:

```sh
python run_playground.py
# Or the existing SDF application:
python run_adaptivecad.py
# Equivalent explicit launcher:
python -m adaptivecad.gui.metric_launch --ui playground
```

Choose **Metric tools > Open metric workbench**. The new dock is initially hidden
so the existing layout is not replaced. `python -m adaptivecad.app` also launches
the SDF application with the dock; its previously missing module entry point is
now present. `run_gui.bat` routes the Playground to the new launcher and retains
its existing local conda settings. Direct legacy calls to `playground.main()` or
`app.launch_app()` are unchanged; embed with `install_metric_workbench(window)`
when using a custom launcher. Installation is idempotent.

## Tool groups

| Group | Implemented behavior |
|---|---|
| Patch | Flat/balanced/positive-center/negative-center presets, coefficient JSON editor, validation, import/export |
| Curves | Native Bezier control-point editing, rename, duplicate, reverse, split, delete, translation, rotation, positive uniform scale |
| Measurements | Intrinsic vector angle, point metric, Gaussian curvature, circle ratio, circumference, sector length, disk area |
| Curve inspection | Intrinsic length, speed, signed geodesic curvature, local Gaussian curvature; stationary points return undefined curvature |
| Trace | Initial-value geodesic, parallel transport, adaptive integration, boundary stop, actual distance, speed/norm diagnostics |
| Project | Strict versioned `.acmetric.json`, atomic save, independent bounded undo/redo, dirty-close prompts, complete unit conversion |
| Preview/report | Click-to-inspect chart, zoom/pan, sampled curvature display, native-curve preview, numerical trace preview, JSON reports with project hash and inputs |

The measurement and trace APIs do not depend on Qt, OCC or SciPy. The existing
package may have optional scientific imports; NumPy remains needed by the native
curve implementation. SciPy is used as an independent test reference, not by the
new geodesic integrator.

## First workflow

In Patch, select **Balanced directional** and press **Use preset**. The circle
average is pi while curvature varies by direction. In Curves, press **New curve**,
edit the native control points if desired, then **Apply editors**. Measure the
curve, reverse or split it, and undo/redo the model operation. In Trace, enter a
start point and launch direction, then trace. Turn on **Sampled curvature map**.
Save the project and export the report from the most recent calculation.

Patch and curve edits are validated as one candidate before being committed. This
allows shrinking the patch while adjusting a curve in the same transaction.
Other tools require applying or reverting drafts. Saving applies valid drafts;
invalid drafts never replace the previous file. A failed/cancelled save does not
silently discard dirty state. Reports and traces are invalidated by model changes.

Units: `mm`, `cm`, `m`, `in`, `ft` (international), `ft_us` (legacy U.S. survey).
Conversion rescales both patch dimensions and native control coordinates; it is
not a label change. Angles in GUI fields are degrees; API angles are radians.
Lengths use patch units, area uses squared units, Gaussian curvature inverse
squared units, and curve geodesic curvature inverse units. The table uses rational
unit definitions before conversion to floating point; numerical roundoff remains.

## Geometry contract

Coordinates are **registered local chart XY**, not arbitrary selected world XYZ.
The workbench does not attach the intrinsic metric to a CAD face or assert a 3D
embedding. A translated/rotated curve is an active edit inside a fixed metric;
it generally changes its intrinsic length. Unit conversion is a different operation.

For normalized X=x/L and Y=y/L, the patch coefficient field A defines

```text
g = I + A(X,Y) [[Y^2, -XY], [-XY, X^2]].
```

First metric derivatives and Christoffel symbols are evaluated analytically.
Geodesics solve the initial-value equation with step-doubled RK4, carrying a
parallel-transport vector alongside the path. The returned samples are numerical
trajectories. This is not a globally shortest-path boundary-value solver.

Source metric coefficients and native Bezier controls contain no triangles.
Preview line segments and curvature-map cells are display samples only. The
preview is not a manufacturing representation or a certification of extrema.

## API example

```python
from adaptivecad.geom.directional_metric import balanced_directional_patch
from adaptivecad.geom.metric_geodesic import trace_geodesic
from adaptivecad.geom.metric_tools import disk_area, segment_length
from adaptivecad.metric_project import MetricCurve, MetricProject

patch = balanced_directional_patch(length_scale=10, unit="mm")
curve = MetricCurve("Route", ((-4, 1), (0, 5), (4, 1)))
project = MetricProject(patch, (curve,))
project.save("route.acmetric.json")  # Refuses to overwrite by default.
print(patch.bezier_length(curve.native()))
print(disk_area(patch, 5))
print(segment_length(patch, (-4, 1), (4, 1)))  # Chart-straight segment only.
trace = trace_geodesic(patch, (-5, 2), (1, 0), 8)
print(trace.status, trace.distances[-1], trace.max_speed_error)
```

Use `overwrite=True` only for intentional replacement. Atomic saves flush/fsync
the temporary file before same-directory replacement; create-only saves use a
hardlink and fail closed if unavailable. This is not a collaborative-file locking
protocol or a guarantee against every storage/power failure.

## Numerical and resource limits

The inherited polynomial family is finite and conservative: a failed positivity
bound need not mean the mathematical metric is invalid. Curve controls must all
lie inside the disk (sufficient, not necessary, for the curve to lie inside).
Projects allow at most 128 curves, 32 controls per curve and 2 MB of JSON.

Integration estimates are not certified global bounds. Disk area allocates an
absolute error budget between angular and radial quadrature; its `rel_tol` is
validated but does not relax that stricter absolute target. Area stops after
200000 angular evaluations. Geodesic budget/underflow failures raise rather than
being reported as successful routes. Boundary status reports a shorter trace.
Long/high-degree calculations run synchronously with finite budgets; cancellable
workers and a large-document performance pass remain on the roadmap.

## Tests

```sh
python -m pytest -q --noconftest tests/test_directional_metric.py tests/test_metric_tools.py tests/test_metric_project.py tests/test_metric_workbench.py
```

Qt tests use real widgets and actions; without PySide6 they explicitly skip.
The dedicated CI installs it and captures a screenshot. The separate
`scripts.metric_app_smoke` command exercises dock attachment in each existing app
under a desktop/Xvfb. It does not certify the whole application's modeling or
OpenCascade behavior. See `metric_tools_roadmap.md` for work not yet implemented.
