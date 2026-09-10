# Send selected curve to metric tools

This extends the integrated workbenches. It is a **one-time copy** from the
model window's `ToolDocument` into the receiving dock's `MetricProject`, not
selected OCC-face attachment, a live feature link, or a new document format.

## Use

Launch `python run_workbenches.py --demo` on this branch. In the modeling
window select a **line or polynomial Bezier**, then choose **Metric transfer >
Send selected curve to metric tools...**. Select XY, XZ, YZ or Custom; specify
the origin (in source model units), two perpendicular axis directions and the
maximum plane residual (also in source units). Review the displayed target
unit and disk radius. Press **Preview mapping (no changes)**, confirm the
mapping checkbox, then **Copy to metric project**. Cancel makes no changes.

A successful copy selects the new curve in the metric dock. Use **Measure
selected curve** there; use that dock's **Undo model** to undo the copy.
Modeling undo does not undo metric operations. Save the receiving project
separately as `.acmetric.json`.

The stock modeling demo begins on a circle, which is deliberately unsupported
by this transfer. For an immediately valid default-XY example, apply this
command in the model editor and select `chart_test`:

```json
{"op":"bezier","name":"chart_test","points":[[-0.4,0,0],[0,0.4,0],[0.4,0,0]]}
```

This fits the default radius-1 mm metric patch. Existing 10-20 mm demo geometry
does not fit it automatically: choose an appropriate metric patch first.
The demo `profile` lies in XZ; select XZ explicitly and configure a sufficiently
large patch before copying. There is no silent normalization, clipping or
patch expansion.

For Playground/SDF hosts, open the mesh-free model window from **Mesh-free
Tools**; its transfer menu targets the original host's metric dock. It does
not read the host's OCC/SDF selected face or replace its scene.

## Mapping and guarantees

For a retained Bezier control point p and declared plane origin o, the mapped
coordinates are

```
q = unit_factor(source_unit, target_unit) *
    [dot(p-o, normalized_X), dot(p-o, normalized_Y)]
```

Axes are required to be perpendicular within 1e-12 normalized dot product;
normalization roundoff is removed and the final frame is recorded. Skew
mappings are rejected. The maximum off-plane control residual must not exceed
the user-entered tolerance. Any accepted residual is explicitly removed and
reported. A zero tolerance is allowed; these are floating-point checks, not
certified predicates. Large world origins can limit representable precision.

Stored trim/reverse intervals are converted to native controls using de
Casteljau subdivision, preserving the parameter direction. No display samples
or curve fitting become the transferred definition. Degree 0..31 is supported
because the existing receiving format accepts 1..32 controls. Degree 32,
arcs/ellipses, surfaces and unsupported objects fail instead of being silently
approximated. Curved metrics are not claimed to preserve Euclidean lengths:
the mapping places coordinates in a user-chosen geometry, not on an inferred
physical embedding.

All mapped controls must lie in the metric disk. The convex-hull property
bounds the full Bezier; this is conservative and can reject a valid curve
whose controls lie outside. The same control-hull principle bounds normal
residuals. No finite sample test is used as a proof of whole-curve containment.
Unit conversion uses the existing exact-ratio definitions followed by floats.
`ft_us` and `ft` remain distinct.

## Transactions and receipts

The preview is immutable and nonmutating. Confirmation rechecks source and
target snapshots, all geometry and limits, then commits one receiving history
entry. Unapplied metric drafts must first be applied or reverted. Name clashes,
capacity limits, invalid inputs, and stale snapshots cannot overwrite existing
curves or advance the receiving history. A changed document requires reopening
the dialog so displayed units and parameters cannot become misleading.

**Metric transfer > Export last transfer receipt...** exports a JSON audit
record using the existing atomic/overwrite-confirming export path. It records
source geometry, source and target unit labels, the normalized mapping,
residual, transferred controls, and source/before/after project SHA-256 hashes.
This is the last successful copy, not live provenance; undoing it or editing a
project later does not rewrite that historical receipt. Export it before
closing to retain it. Model/project formats and their independent persistence
contracts are unchanged; no automatic receipt file is written.

## Test

```sh
python -m pytest -q --noconftest tests/test_metric_curve_transfer.py tests/test_curve_transfer_ui.py
```

The dedicated Curve transfer workflow requires real Qt and SciPy and runs these
and all prior integrated suites in one process on Windows and Ubuntu. Its
artifacts contain JUnit results and an actual dialog screenshot. Local Qt skips
must not be reported as successful GUI execution. Repository-wide lint failures
are separate from this focused validation. No manufacturing validation, global
surface registration, or physical/fundamental-geometry claim is made.
