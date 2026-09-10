# Remaining metric/CAD integration work

Scope audit against the current repository and PR #72. This is **not** a claim
that every task in the existing 200-task `AGENTS.md` roadmap has been completed.
Existing SDF/Playground tools and the separate car/CadQuery PR are not replaced.

## Implemented in the metric-workbench change

- [x] Local directional patch editor, import/export and presets.
- [x] Native Bezier edit/duplicate/reverse/split/transform/delete and measurements.
- [x] Intrinsic angle, area, Gaussian/geodesic curvature and connection API.
- [x] Initial-value geodesic tracing and parallel transport with diagnostics.
- [x] Explicit whole-project unit conversion including legacy U.S. survey feet.
- [x] Separate versioned project storage, atomic saves, bounded undo/redo and draft guards.
- [x] Dock/menu attachment to existing applications through supported launchers.
- [x] Sampled previews, reproducible JSON reports and regression/Qt tests.

## Next integration gates, in dependency order

1. **Registered CAD-face attachment.** Define a face-to-chart map and its inverse,
   declared units and domain. Test induced metric agreement, trimmed boundaries,
   singular coordinates, mirrored orientation and transformed instances. Never
   silently equate a world XY projection with intrinsic XY.
2. **Full document integration.** Add schema-versioned metric features and stable
   object IDs to native project/AMA storage, including reopen, undo, rename and
   references across feature edits. Preserve old file round trips.
3. **Geodesic endpoints and offsets.** Add a two-point boundary-value solver,
   alternative-path/cut-locus handling, offset self-intersection handling and
   convergence/failure reporting. Test multiple solutions rather than labeling
   every stationary path globally shortest.
4. **Multi-chart surfaces and 3D extension.** Store validated transition maps and
   topology; test metric pullbacks, inverse maps, loop consistency and chart-boundary
   transport. In 3D retain the full angular metric matrix, not just its determinant.
5. **Analytic face operations.** Add metric-aware trim/intersection/loft/sweep only
   after defining embedded geometry and tolerances. Existing Euclidean operations
   remain available; this update has not converted them into general intrinsic ones.
6. **Manufacturing adapter.** Map native paths into machine coordinates, include
   tool radius, stock, safe heights, units/feed policy, joint/travel limits and
   collision checks. Compare against independently simulated motion and controller
   behavior. The current traces are explicitly not G-code and must not be sent to
   a machine as if they were validated toolpaths.
7. **Survey alignment workflow.** Native line/arc/spiral reconstruction, station and
   offset queries, coordinate-reference metadata, exact unit definitions, printed
   precision/error budgets and reproducibility tests. Distinguish plan rounding,
   numerical error and inconsistent source geometry. No zero-error claim.
8. **Production interaction/performance.** Add cancellable computation workers,
   picking existing registered curves, control-point grips, snapping, dimension
   annotations and accessible legends. Measure large-document latency and exercise
   native Windows/Linux graphics plus OCC. Resolve existing repository-wide CI
   failures separately, without weakening checks.

## Explicit exclusions

No universal optics/material response, new physical force, fundamental-pi proof,
certified interval kernel, globally complete atlas, production machining approval,
or completion of all conventional CAD commands is asserted. The full application's
remaining conventional modeling gaps should be tracked separately from this
local-intrinsic geometry workbench, with their own acceptance tests.
