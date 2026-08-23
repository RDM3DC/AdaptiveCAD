# Infinity Root Geometry in AdaptiveCAD

AdaptiveCAD now treats Infinity Root Calculus as a geometry and path descriptor,
not as a replacement CAD kernel or a replacement metric.

The core operator is:

```text
R[f](x) = x f'(x) / f(x)
        = d log(f) / d log(x)
```

For a positive profile, the sampled root jet is:

```text
J_(n,b)(f) = (f(b), Rf(b), ..., R^(n-1)f(b); R^n f)
```

AdaptiveCAD stores the positive basepoint constants and sampled terminal
function, then reconstructs the entire integer tower by nested normalized lifts.

## The important CAD rule

| Data | AdaptiveCAD status | Gauge allowed? |
|---|---|---:|
| Integer height `0, 1, ..., n` | `canonical_integer` | No |
| Non-integer height such as `1.5` | `gauge_view` | Required |

This rule is enforced in code. Asking for a non-integer level without a gauge
raises an error. Attaching a gauge to an integer level also raises an error.

The built-in `positive_power_mean` gauge is a local visualization interpolation:

```text
p = 0  -> pointwise log-linear mean
p = 1  -> pointwise arithmetic mean
```

The two choices agree at the integer endpoints but generally produce different
intermediate geometry. The metadata explicitly says:

```text
mathematical_status = local_visualization_gauge
abel_equation_verified = false
```

AdaptiveCAD therefore does not claim that this display interpolation is a
coordinate-free fractional iterate or a verified solution of Abel's equation.
A future verified Abel coordinate must receive its own gauge ID and implementation.

## What was added

The module `adaptivecad.geometry.infinity_root` provides:

- `RootJetSamples` — serializable root-jet data and exact discrete decoder;
- `CanonicalRootTower` — the integer operator backbone;
- `tower_from_profile_samples` — a finite-difference estimator for an existing
  positive CAD scalar profile;
- `FractionalGaugeSpec` — explicit provenance for non-integer views;
- `make_infinity_root_profile` — a closed AdaptiveCAD profile dictionary;
- `make_infinity_root_book` — a stack of canonical pages and optional gauge pages;
- `profile_curvature_metrics` — discrete perimeter and curvature measurements;
- `compare_fractional_gauge_curvature` — a direct gauge-survival audit;
- `infinity_root_book_obj` — quad-only OBJ preview export.

Every generated profile uses:

```text
metric = inherit
role   = geometry_descriptor_not_metric_kernel
```

That keeps Infinity Root data compatible with Euclidean, pi_a, or later metric
kernels without silently changing any of them.

## Curvature result

Local curvature does not survive a change of fractional gauge. In general, the
following values change:

- perimeter;
- pointwise curvature;
- RMS curvature;
- maximum curvature;
- absolute total curvature if a page becomes nonconvex.

One quantity does survive while the page remains a regular simple closed planar
curve with the same orientation:

```text
signed total curvature = 2 pi × turning number
```

For the generated Infinity Book pages, the turning number is `1`, so the signed
total curvature remains `2 pi` across the tested gauges. This is the classical
turning-tangent theorem, not a new Infinity Root invariant. The software records
that scope explicitly and does not extend the claim to Gaussian curvature of the
3D loft.

## Quick use

```python
import numpy as np

from adaptivecad.geometry.infinity_root import (
    FractionalGaugeSpec,
    make_exact_lift_tower,
    make_infinity_root_book,
)

x = tuple(np.geomspace(0.55, 1.8, 181))
tower = make_exact_lift_tower(x, depth=3, residue=1.0)

book = make_infinity_root_book(
    tower,
    fractional_pages=(
        (0.5, FractionalGaugeSpec.power_mean(0.0)),
        (1.5, FractionalGaugeSpec.power_mean(0.0)),
        (2.5, FractionalGaugeSpec.power_mean(0.0)),
    ),
)
```

The top-level `root_jet` is the reconstructive data. Each page separately records
whether it is canonical or gauge-dependent.

## Run the Infinity Book demo

From the repository root:

```text
python demo/infinity_root_book.py --output-dir infinity_root_demo
```

It writes:

- `infinity_root_book.json` — root jet, page provenance, curvature, and topology;
- `infinity_root_book.obj` — a quad-only preview loft with no triangle faces;
- `infinity_root_book.svg` — a dependency-free isometric preview.

The JSON also compares the selected gauge with a second power-mean gauge at
height `0.5`, reporting which curvature metrics survived within numerical
tolerance and which changed.

Use `--integer-only` to generate only the canonical pages.

## Numerical boundary

There are two distinct routes:

1. `RootJetSamples.decode()` uses nested trapezoidal lifts in `log(x)`. Within
   that declared sampled integration model, encoding, decoding, and basepoint
   transport are reversible to floating-point precision.
2. `tower_from_profile_samples()` estimates derivatives from arbitrary samples.
   Its integer levels approximate the continuum operator and carry the source
   label `finite_difference_log_grid_estimate`.

No absolute value or positivity clamp is used to force a failed root. If an
intermediate estimated level is nonpositive, AdaptiveCAD reports that the sampled
profile does not satisfy the positive-admissibility requirement.

## Verification

```text
python -m pytest -q tests/test_infinity_root_geometry.py
```

The focused suite checks root-jet reconstruction, basepoint transport,
serialization, sampled root estimation, gauge enforcement, curvature survival,
profile metadata, and quad-only Infinity Book topology.
