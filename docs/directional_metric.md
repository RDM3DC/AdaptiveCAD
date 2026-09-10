# Direction-resolved Adaptive-pi metric patches

Status: **experimental intrinsic measurement API**, additive to the existing CAD
kernel. No existing geometry, GUI, file formats or Euclidean measurements are
replaced. No historical novelty or new physical law is claimed.

## What this improves

A circle's circumference average can hide directional differences. This module
retains them in an analytic coefficient model, evaluates the full metric and
Gaussian curvature, and measures native Bezier curves in that metric. The source
representation has no triangles. Numerical integration and optional grid sampling
are calculations *from* the coefficient model, not replacements for it.

This enables research on metric-aware surface measurements and path costs. It
does not automatically improve the accuracy of current solid/STEP operations,
render an embedded surface, correct survey alignments, or solve a manufacturing
path-planning problem. Normal coordinates are chart coordinates, not arbitrary
model-space XYZ points or an existing face's UV parameters.

## Run the example

From the repository root (Python 3.10+):

```sh
python -m examples.directional_metric_demo
python -m pytest -q --noconftest tests/test_directional_metric.py
```

The new evaluator uses the standard library. The optional grid adapter uses
NumPy; the focused tests require NumPy and pytest. Existing AdaptiveCAD package
imports retain their existing requirements. This change does not edit packaging
or install GUI dependencies.

Optional output: `python -m examples.directional_metric_demo --output report.json`.
The example refuses to overwrite an existing report. `--scale` sets the radius
and length scale in mm, not the value of pi.

## Representation and validity

With `L=length_scale`, `X=x/L`, `Y=y/L`, store a finite polynomial

```
A(X,Y) = sum(c_ij * X**i * Y**j)
g = [[1 + A*Y**2, -A*X*Y], [-A*X*Y, 1 + A*X**2]]
F = 1 + (X**2 + Y**2)*A
DirectionalPi(r,theta) = pi*sqrt(F)
```

The radial eigenvalue is 1 and the angular eigenvalue is F. At the origin,
`g=I` and `DirectionalPi=pi`; there is no polar 0/0 evaluation. Polynomial A is
smooth. Strict positivity is required over the declared disk.

Construction uses a conservative algebraic lower bound. With R=radius/L,
negative terms and any odd-power term contribute `abs(c)*R**(i+j+2)` to a possible
loss from F=1. Positive terms with both powers even cannot decrease F. If the
lower bound is not greater than 1e-12, construction fails. This may reject a
valid patch: reduce the radius or use a tighter future validator. It is a
sufficient algebraic condition evaluated in floating point, **not interval
arithmetic certification**. Evaluated points must also be finite and inside the
disk. No out-of-domain value is silently extrapolated.

Terms are immutable, canonicalized, unique, and limited to 256 terms of total
degree at most 32. This is an explicitly restricted family, not an exact finite
encoding of every smooth geometry. Angles are registered initial directions in
radians; do not reparameterize each circle separately.

### Analytic curvature without differencing

For each monomial value v with degree d, set

```
B = sum((d+2)*v)
C = sum((d+2)*(d+3)*v/2)
K = [-C/F + (X**2+Y**2)*(B/F)**2/4]/L**2
```

This follows by differentiating `J=r*sqrt(F)` in `K=-J_rr/J`. In particular,
`K(0,0)=-3*A(0,0)/L**2`. This is intrinsic Gaussian curvature, not the curvature
of a drawn curve or the extrinsic bending of an embedded face.

The averaged `circle_pi(r)` is `C_circle/(2*r)`. It is not a substitute for the
directional field. `sector_length`, `circle_pi`, and `bezier_length` return
`IntegralResult(value, estimated_error, evaluations)`. Error estimates come from
adaptive Simpson quadrature, are not certified bounds, and need convergence
checks for demanding applications. `abs_tol` for circle_pi controls the underlying
circumference integral in length units; its returned error is divided by 2r.
Failure to converge raises `IntegrationError` rather than reporting success.

## Native Bezier measurement

```python
from adaptivecad.geom.directional_metric import balanced_directional_patch
from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.linalg import Vec3

patch = balanced_directional_patch(length_scale=100.0, unit="mm")
curve = BezierCurve([Vec3(-30, 20, 0), Vec3(10, 45, 0), Vec3(50, 10, 0)])
result = patch.bezier_length(curve)
print(result.value, result.estimated_error)
```

Control points must be in this chart's XY plane with z=0 and inside its disk.
The convex-hull property then keeps the whole Bezier in the disk. Nonplanar
curves are rejected, not projected. The existing analytic Bezier derivative is
used; stationary tangents and constant curves are accepted. These are intrinsic
lengths of the chart curve, not an inferred length on an unspecified solid.

## Grid adapter for existing anisotropic-distance tooling

```python
import numpy as np
from adaptivecad.geom.directional_metric import balanced_directional_patch

patch = balanced_directional_patch(length_scale=100.0)
xs = np.linspace(-50, 50, 41)
ys = np.linspace(-40, 40, 33)
G = patch.metric_grid(xs, ys)  # shape (41,33,2,2), G[i,j]=g(xs[i],ys[j])
hx, hy = xs[1]-xs[0], ys[1]-ys[0]
# G is compatible with adaptive_pi.aniso_fmm.anisotropic_fmm(G, source, hx, hy).
```

The grid axes must be uniformly spaced and increasing, and the rectangle must
fit in the disk. Preserve `hx`, `hy`, origins and axis ordering. The existing
FMM-lite solver is approximate; this PR does not repair or certify its update or
backtracer. Grid compatibility is not proof of shortest-path accuracy.

## Scaling, units and storage

`patch.scaled(s)` rescales all chart lengths. At corresponding points the metric
and directional pi are unchanged, lengths multiply by s, and K divides by s^2.
For unit conversion supply the correct factor and `unit` explicitly; changing a
label alone is not a conversion. All curve coordinates must be converted too.

`to_json` / `from_json` store only v1 schema metadata and polynomial coefficients.
They reject unknown keys/versions, duplicate keys/terms, nonfinite numbers and
invalid scales. There is no eval, pickle, generated code or silent lossy angular
averaging. This is a standalone schema, not yet integrated into AMA documents.

## Regression case and scientific scope

The balanced fixture uses

```
DirectionalPi = pi*(1 + epsilon*(r/L)**4*cos(2*theta))
```

with default epsilon=0.2. Its complete circle ratio is pi, while at r=0.75L the
curvature K*L^2 is approximately -2.116091 at 0 degrees and +2.402002 at 90 degrees.
This is an explicit counterexample to using one center's circle average as a
flatness test. The new code tests those formulas independently.

Local completeness is a statement about a **full admissible directional field**
on a geodesic normal disk. The bounded-degree implementation is a useful subset.
Global topology still needs patch identifications. A 3D volume needs the full
angular matrix, not just this surface scalar. Embedding, rendering, Boolean
operations, geodesic optimization and machine output remain separate tasks.

## Mathematical references

- R. E. Greene, UCLA, *Gauss Curvature and the Form of the Metric in Geodesic
  Polar Coordinates*: https://www.math.ucla.edu/~greene/Math120BGaussCurvPolCoord.pdf
- J. T. Moore, Cornell, *Riemannian metrics* (metric-based curve lengths and
  pullback/isometry): https://pi.math.cornell.edu/~justin/4540/metric.html

The implementation applies standard differential geometry to the directional
Adaptive-pi representation. It is not evidence that pi changes as a mathematical
constant, or that this representation is a new law of nature.

## Verification performed for this change

- 63 focused tests passed locally on Python 3.13.5.
- Twenty seeded random native cubic Beziers were also checked against SciPy's
  independent quadrature implementation using direct `sqrt(v.T @ g @ v)`;
  maximum absolute difference was about 1.3e-12 mm for L=1 mm.
- New Python files parsed successfully with Python 3.10 grammar.

Local tests used an isolated package fixture containing the retrieved upstream
Curve, BezierCurve and linalg source at commit
`d6111436fd8b1e8e9e26e9947b681b708f478af5`, not a full repository installation.
This does not claim the full pre-existing test suite, GUI or OpenCascade stack
passed. The dedicated workflow tests the actual checkout on Python 3.10/3.13;
its remote result must be checked separately. Internal numeric tests do not
constitute physical validation or establish historical mathematical novelty.
