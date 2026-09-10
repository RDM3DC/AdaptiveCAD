# Integrated modeling and Adaptive-pi workbenches

## One branch, one modeling window

```sh
python run_workbenches.py
# Existing model, no rewrite or conversion:
python run_workbenches.py --document meshfree_demo_output/document.json
# In-memory modeling example; writes nothing until you choose Save as:
python run_workbenches.py --demo
# Optional independently saved metric project:
python run_workbenches.py --document model.json --metric-project chart.acmetric.json
```

This reuses the existing `meshfree_workbench.Workbench` window, including the
PR #75 whole-document viewport and selection-lifetime fixes. Choose **Metric
tools > Open metric workbench** to show the existing PR #74 dock alongside it.
No new solid-modeling application, third document type, or automatic chart/world
mapping is introduced. The demo's large 3D curves are NOT attached to the metric
chart. A metric curve must be created explicitly in the dock's local XY chart.

The existing `python run_playground.py` and `python run_adaptivecad.py` launchers
now install both menus in their original host. **Mesh-free Tools > Mesh-free
Tool Workbench** opens the separate modeling document window; **Metric tools**
opens the independent dock. Existing host scene membership is not rewritten.

## Save boundaries and safety

The modeling window's **Save as** writes its existing `ToolDocument` JSON;
the dock's **Save / Save as** writes its existing `.acmetric.json` `MetricProject`.
They do not save each other, share undo/redo, or copy source definitions. Save
both when working on both. File paths passed at launch are read and validated
before any window is constructed. There is no autosave or silent migration.

In integrated launchers, unsaved committed modeling changes prompt
Save/Discard/Cancel before close or replacement. A failed or cancelled save
blocks the operation. Returning to the saved snapshot by undo/redo removes the
model's dirty indicator. The dock retains its original draft-validation and
save-cancel protections. Closing a host also checks its modeling child.
Command-template text is an input buffer, not a model and not persisted by the
model Save button. Keep important command scripts in their own files.

The original standalone `python -m adaptivecad.gui.meshfree_workbench` and
low-level `create_workbench()` keep their previous opt-in integration contract;
use `guard_unsaved=True` for the new close/replacement protection. The combined
launcher enables it automatically. There is still no protection against a
forced process kill or operating-system failure.

## Resolving the two metric APIs

PR #73 and PR #74 independently added different APIs at
`adaptivecad/geom/metric_tools.py`. They cannot safely overwrite one another.
This integration retains the dock's PR #74 module at that path and moves the
PR #73 math byte-for-byte to **`adaptivecad.geom.meshfree_metric_tools`**.
Toolkit example, tests, and documentation imports are updated explicitly.

For existing PR #73 scripts, change:

```python
# Old experimental toolkit import:
# from adaptivecad.geom.metric_tools import trace_geodesic, disk_area
from adaptivecad.geom.meshfree_metric_tools import trace_geodesic, disk_area
```

The dock continues to use `adaptivecad.geom.metric_tools` plus
`adaptivecad.geom.metric_geodesic`. The toolkit tracer returns `positions` and
raises on a boundary exit; the dock tracer returns `points` and a boundary
status. Neither is swapped in for the other. Both are numerical local
initial-value solvers, not certified global shortest-path or machine tools.
No numerical formula, unit definition, geometry schema, or original test
assertion was changed to make these APIs coexist.

## Verification

The new workflow runs both original toolsets and integration regressions in the
same Python process with real Qt and SciPy. New tests check both numerical API
contracts, independent histories and serialization, installer idempotency,
close cancellation, failed/cancelled saves, saved-state undo/redo, invalid-file
rejection before prompting, child-window protection, and a real combined view.
Screenshots and JUnit results are workflow artifacts. Existing selection-crash
regressions remain enabled. Actual run outcomes belong in the PR report; a
workflow definition alone is not evidence that tests passed.

The existing main-host smoke workflow is retained. Its Playground mode may use
the repository's fallback when OpenCascade is absent. Full OpenCascade solids,
GPU-driver behavior, CAM output and a repository-wide clean CI result are not
certified by these focused tests.

## Next acceptance gate

An explicit, validated native-curve transfer using a declared chart mapping,
units and out-of-domain checks can follow. It must be a user-visible copy with
undo on the receiving side, not automatic reinterpretation of selected world
XYZ as chart XY. Native solid operations, shared feature recomputation and
manufacturing remain separate work.
