# AdaptiveCAD model workspace UI

An Inventor-inspired presentation layer on the integrated mesh-free model window, based on PR #78. It does not replace the geometry kernel, legacy solid host, metric project, or selection implementation.

## Launch

```sh
python run_workbenches.py --demo
python run_workbenches.py --document model.json --metric-project chart.acmetric.json
```

The prior layout remains available with `--classic-ui`. Existing Playground/SDF hosts retain their central solid scene and menus. Their existing Mesh-free Tools action opens the upgraded model child; no additional host application is introduced.

## Workspace

- **Model ribbon:** model Open/Save as, Line, Bezier, Circle/arc, Extrude sheet, Revolve sheet, ruled Loft and translation Sweep.
- **Modify ribbon:** model Undo/Redo, Move/copy, Copy, Rotate, Scale, Mirror, parameter Trim, Split, Reverse, rectangular/polar arrays and confirmed Delete.
- **Inspect ribbon:** model measurement, existing metric dock, original selected-curve transfer and receipt actions, explicit model unit conversion.
- **View ribbon:** Fit all, zoom, advanced command console, dock layout save/restore/reset, and command search.

The left model browser is the existing selection list with a name filter. Filtering hides only browser rows, never model geometry. The right inspector shows read-only native definition data. It is not a live associative feature tree or a geometric certificate. Docks can float, close, and be recovered from Workspace. The metric dock shares a full-height tab with the inspector in the combined model window, rather than being squeezed above it. Save/Restore layout explicitly writes/reads UI preferences only; it is not a project save and is not automatic.

`Ctrl+K` opens command search. With the model viewport or browser focused, `Ctrl+Z`, `Ctrl+Y`, `Delete`, and `F` operate on the model. These model bindings are widget-scoped so they do not capture text-editor or metric-dock undo.

## Parameters and safety

Tools open retained Qt parameter dialogs, with model units and radians stated. Vector fields accept `x, y, z`. Bezier controls accept one such row per line or a strict JSON matrix, with 1..32 controls. Expressions, nonfinite numbers, and noninteger array counts are rejected. Decimal radii and scale factors are allowed. `ft_us` remains distinct from international `ft`.

Validate executes the real backend in an isolated temporary ToolSession. Apply revalidates and makes one atomic commit to the existing model session. Names are never overwritten by these forms. The dialog captures the model session and snapshot; changing or replacing the model invalidates its inputs until the dialog is reopened. Cancel commits nothing. One parameter dialog is retained at a time, so opening another command raises the existing dialog instead of discarding its inputs.

Model and metric histories/saves remain independent. The existing curve-transfer preview, confirmation, unit/domain checks, and receipt handling are reused rather than reimplemented. Metric edits and model transforms are not silently synchronized. The original strict-JSON command editor remains available for advanced atomic batches; its draft text is not saved project data.

## Scope

This builds the UI, not missing CAD algorithms. Surface constructors still produce evaluated sheets rather than capped/watertight solids. Move and transform forms create named result snapshots, not live feature links. The viewport retains the existing sampled isometric wireframe and in-place selection behavior; there is no new orbit renderer, ViewCube, shaded solids, constraint editor, associative dimension system, robust booleans or CAM output. The browser's native definitions remain authoritative; screen samples are for display only.

## Verification

The dedicated Model workspace UI workflow requires real Qt and SciPy on Windows/Python 3.10 and Ubuntu/Python 3.13. It runs the prior 329 feature/runtime/conditioning cases plus 39 form-adapter and 14 real-Qt UI cases in one process, checks repository Ruff and formatting/imports on new files, and captures actual widget screenshots. Inspect the latest workflow result; a workflow definition is not evidence that it has passed.

The first actual Qt run passed 379/380 cases, with one new layout-storage test failure and one Black formatting difference. The test wrongly expected the organization/application QSettings constructor to honor the global default format. It now injects real file-backed settings into a temporary directory and verifies persistence, restoration, and unchanged documents without altering global Qt configuration. No assertion was removed. Two additional tests exercise real metric-editor text undo and full-height metric/inspector tab placement. Screenshot review also led to better title/status contrast and compact parameter dialogs.

The local headless source snapshot passed 314 selected cases (275 previous core cases plus 39 new form cases). Qt is not available in the local build environment; local GUI cases are skips, not GUI passes. Repository-wide Black/isort/mypy and the legacy ray_march fast-test mismatch remain separate PR #78 release blockers. This UI branch does not suppress, weaken, or repair those gates.
