"""Mesh-free, direction-resolved intrinsic metrics on a normal-coordinate disk.

This is an additive experimental measurement API, not an embedded CAD face or
an alternative value for math.pi. See docs/directional_metric.md for scope.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Callable


class IntegrationError(ArithmeticError):
    """The numerical integration budget was exhausted; no result is accepted."""


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} is outside the supported numerical range") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class IntegralResult:
    """Numerical integral and estimated absolute error (not a certified bound)."""

    value: float
    estimated_error: float
    evaluations: int


def _integrate(
    f: Callable[[float], float], start: float, stop: float,
    abs_tol: float, rel_tol: float, panels: int = 8, max_depth: int = 16,
) -> IntegralResult:
    """Panel-seeded adaptive Simpson quadrature, with explicit failure."""
    start, stop = _finite(start, "start"), _finite(stop, "stop")
    abs_tol, rel_tol = _finite(abs_tol, "abs_tol"), _finite(rel_tol, "rel_tol")
    if stop < start or abs_tol <= 0 or rel_tol < 0:
        raise ValueError("Require start <= stop, abs_tol > 0 and rel_tol >= 0")
    if isinstance(max_depth, bool) or not isinstance(max_depth, Integral) or max_depth < 0:
        raise ValueError("max_depth must be a nonnegative integer")
    if start == stop:
        return IntegralResult(0.0, 0.0, 0)
    count = 0

    def evaluate(t: float) -> float:
        nonlocal count
        count += 1
        if count > 200000:
            raise IntegrationError("Quadrature exceeded 200000 evaluations")
        return _finite(f(t), "integrand")

    def refine(a, b, fa, fm, fb, whole, tolerance, depth):
        mid = (a + b) / 2
        fl, fr = evaluate((a + mid) / 2), evaluate((mid + b) / 2)
        left = (mid - a) * (fa + 4 * fl + fm) / 6
        right = (b - mid) * (fm + 4 * fr + fb) / 6
        delta = left + right - whole
        if abs(delta) <= 15 * tolerance:
            return left + right + delta / 15, abs(delta) / 15
        if depth == 0 or mid == a or mid == b:
            raise IntegrationError("Quadrature did not converge; relax tolerance or increase depth")
        lv, le = refine(a, mid, fa, fl, fm, left, tolerance / 2, depth - 1)
        rv, re = refine(mid, b, fm, fr, fb, right, tolerance / 2, depth - 1)
        return lv + rv, le + re

    seeds = []
    for i in range(panels):
        a = start + (stop - start) * i / panels
        b = start + (stop - start) * (i + 1) / panels
        fa, fm, fb = evaluate(a), evaluate((a + b) / 2), evaluate(b)
        whole = (b - a) * (fa + 4 * fm + fb) / 6
        seeds.append((a, b, fa, fm, fb, whole))
    budget = max(abs_tol, rel_tol * abs(math.fsum(s[-1] for s in seeds)))
    values, errors = [], []
    for seed in seeds:
        value, error = refine(*seed, budget / panels, max_depth)
        values.append(value)
        errors.append(error)
    value, error = math.fsum(values), math.fsum(errors)
    if error > max(abs_tol, rel_tol * abs(value)):
        raise IntegrationError("Final error estimate exceeds requested tolerance")
    return IntegralResult(_finite(value, "integral"), error, count)


@dataclass(frozen=True)
class NormalMetricPatch:
    """A finite polynomial family of smooth centered two-dimensional metrics.

    With X=x/length_scale, Y=y/length_scale and A=sum(c*X**i*Y**j),
    g = I + A * [[Y**2, -X*Y], [-X*Y, X**2]].

    terms is an iterable of (i, j, c), with dimensionless coefficients. All
    positions, radius and length_scale use the stated unit; no conversion is
    implicit. A conservative sufficient positivity test is required over the
    whole disk. Some valid metrics are rejected when this bound is inconclusive.
    Floating-point evaluation is not interval-certified. This polynomial family
    does NOT represent every smooth metric exactly.
    """

    terms: tuple[tuple[int, int, float], ...] = ()
    length_scale: float = 1.0
    radius: float = 1.0
    unit: str = "mm"

    def __post_init__(self):
        scale, radius = _finite(self.length_scale, "length_scale"), _finite(self.radius, "radius")
        if scale <= 0 or radius <= 0:
            raise ValueError("length_scale and radius must be positive")
        if not isinstance(self.unit, str) or not self.unit.strip() or len(self.unit) > 64:
            raise ValueError("unit must be a nonempty label of at most 64 characters")
        _finite(radius / scale, "normalized radius")
        rows = tuple(self.terms)
        if len(rows) > 256:
            raise ValueError("At most 256 polynomial terms are supported")
        clean, seen = [], set()
        for row in rows:
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise ValueError("Each term must be (x_power, y_power, coefficient)")
            i, j, c = row
            if any(isinstance(v, bool) or not isinstance(v, Integral) or v < 0 for v in (i, j)):
                raise ValueError("Polynomial powers must be nonnegative integers")
            i, j = int(i), int(j)
            if i + j > 32 or (i, j) in seen:
                raise ValueError("Require unique terms and total polynomial degree <= 32")
            seen.add((i, j))
            c = _finite(c, "coefficient")
            if c != 0:
                clean.append((i, j, c))
        object.__setattr__(self, "terms", tuple(sorted(clean)))
        object.__setattr__(self, "length_scale", scale)
        object.__setattr__(self, "radius", radius)
        if self.positivity_lower_bound() <= 1e-12:
            raise ValueError("Positivity bound inconclusive or nonpositive; reduce the patch radius")

    def positivity_lower_bound(self) -> float:
        """Sufficient algebraic lower bound on the transverse eigenvalue.

        Positive even-power terms cannot decrease it. Other terms are bounded
        using |X|,|Y| <= radius/length_scale. Computed in floating point.
        """
        rho = self.radius / self.length_scale
        try:
            losses = [abs(c) * rho ** (i + j + 2) for i, j, c in self.terms
                      if c < 0 or i % 2 or j % 2]
            bound = 1.0 - math.fsum(losses)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Patch scale is outside the supported numerical range") from exc
        return _finite(bound, "positivity bound")

    def _state(self, x: float, y: float):
        x, y = _finite(x, "x"), _finite(y, "y")
        if math.hypot(x, y) > self.radius:
            raise ValueError("Point lies outside the declared metric disk")
        X, Y = x / self.length_scale, y / self.length_scale
        try:
            values = [(i + j, c * X**i * Y**j) for i, j, c in self.terms]
            A = math.fsum(v for _, v in values)
            B = math.fsum((d + 2) * v for d, v in values)
            C = math.fsum(0.5 * (d + 2) * (d + 3) * v for d, v in values)
            F = 1.0 + (X * X + Y * Y) * A
        except (OverflowError, ValueError) as exc:
            raise ValueError("Polynomial evaluation overflow") from exc
        if not all(math.isfinite(v) for v in (X, Y, A, B, C, F)) or F <= 0:
            raise ValueError("Metric is nonfinite or not positive definite")
        return X, Y, A, B, C, F

    def metric(self, x: float, y: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """Full Cartesian metric, including the cross term; regular at (0,0)."""
        X, Y, A, _, _, _ = self._state(x, y)
        cross = -A * X * Y
        return ((1 + A * Y * Y, cross), (cross, 1 + A * X * X))

    def directional_pi(self, r: float, theta: float) -> float:
        """Pi_a(r,theta)=pi*J/r; theta is the registered launch angle in radians."""
        r, theta = _finite(r, "r"), _finite(theta, "theta")
        if r < 0 or r > self.radius:
            raise ValueError("Require 0 <= r <= radius")
        if r == 0:
            return math.pi
        # Trig rounding at the boundary must not make an admissible radius fail.
        x, y = r * math.cos(theta), r * math.sin(theta)
        norm = math.hypot(x, y)
        if norm > self.radius:
            inner = math.nextafter(self.radius, 0.0)
            x, y = x * inner / norm, y * inner / norm
        return math.pi * math.sqrt(self._state(x, y)[-1])

    def gaussian_curvature(self, x: float, y: float) -> float:
        """Intrinsic Gaussian curvature in unit^-2, including the exact center limit."""
        X, Y, _, B, C, F = self._state(x, y)
        k = -C / F + (X * X + Y * Y) * (B / F) ** 2 / 4
        return _finite(k / self.length_scale / self.length_scale, "curvature")

    def speed(self, x: float, y: float, vx: float, vy: float) -> float:
        """sqrt(v^T g v), evaluated in a stable radial/transverse frame."""
        X, Y, _, _, _, F = self._state(x, y)
        vx, vy = _finite(vx, "vx"), _finite(vy, "vy")
        r = math.hypot(X, Y)
        if r == 0:
            return math.hypot(vx, vy)
        nx, ny = X / r, Y / r
        return _finite(math.hypot(nx * vx + ny * vy,
                                 math.sqrt(F) * (-ny * vx + nx * vy)), "speed")

    def sector_length(self, r, theta0=0.0, theta1=2 * math.pi, *,
                      abs_tol=1e-9, rel_tol=1e-9, max_depth=16) -> IntegralResult:
        """Arc length on a geodesic circle, using quadrature, not triangle facets."""
        r = _finite(r, "r")
        self.directional_pi(r, 0.0)  # Validate radius even for zero-width integrals.
        degree = max((i + j for i, j, _ in self.terms), default=0)
        return _integrate(lambda t: r * self.directional_pi(r, t) / math.pi,
                          theta0, theta1, abs_tol, rel_tol,
                          panels=max(8, 2 * (degree + 4)), max_depth=max_depth)

    def circle_pi(self, r, *, abs_tol=1e-9, rel_tol=1e-9, max_depth=16) -> IntegralResult:
        """Original C/(2r) ratio; differs from the directional field."""
        r = _finite(r, "r")
        result = self.sector_length(r, abs_tol=abs_tol, rel_tol=rel_tol, max_depth=max_depth)
        if r == 0:
            return IntegralResult(math.pi, 0.0, result.evaluations)
        return IntegralResult(result.value / (2 * r), result.estimated_error / (2 * r),
                              result.evaluations)

    def bezier_length(self, curve, *, abs_tol=1e-9, rel_tol=1e-9, max_depth=16) -> IntegralResult:
        """Measure a native BezierCurve whose control points are chart XY coordinates.

        No world-space surface projection is performed. All control points must
        have z=0 and lie inside the disk; its convexity then contains the curve.
        Uses the native analytic Bezier derivative, including stationary points.
        """
        from .bezier import BezierCurve

        if not isinstance(curve, BezierCurve) or not curve.control_points:
            raise ValueError("Expected a nonempty native BezierCurve")
        for p in curve.control_points:
            if _finite(p.z, "control point z") != 0:
                raise ValueError("Bezier must be expressed in chart XY, with z=0")
            self._state(p.x, p.y)

        def integrand(t):
            p, v = curve.evaluate(t), curve.derivative(t)
            return self.speed(p.x, p.y, v.x, v.y)

        return _integrate(integrand, 0.0, 1.0, abs_tol, rel_tol, max_depth=max_depth)

    def metric_grid(self, xs, ys):
        """Optional NumPy adapter: G[i,j]=metric(xs[i],ys[j]) for aniso_fmm.

        Sampling is a solver input, NOT the authoritative geometry. Both axes
        must be uniformly spaced and increasing; the entire rectangle must fit
        inside this disk. The grid does not solve or certify geodesics itself.
        """
        import numpy as np

        axes = []
        for name, values in (("xs", xs), ("ys", ys)):
            axis = np.asarray([_finite(v, name) for v in values], dtype=float)
            if axis.ndim != 1 or len(axis) < 2:
                raise ValueError("Grid axes must be one-dimensional with at least two values")
            delta = np.diff(axis)
            if not np.all(delta > 0) or not np.allclose(delta, delta[0], rtol=1e-9, atol=0):
                raise ValueError("Grid axes must be increasing and uniformly spaced")
            axes.append(axis)
        xs, ys = axes
        for x in (xs[0], xs[-1]):
            for y in (ys[0], ys[-1]):
                self._state(x, y)
        return np.asarray([[self.metric(x, y) for y in ys] for x in xs])

    def scaled(self, factor: float, *, unit: str | None = None) -> NormalMetricPatch:
        """Uniformly scale chart lengths, retaining its dimensionless geometry.

        Used for resizing, or for unit conversion when the caller supplies the
        correct factor and new unit label. No unit conversion is inferred.
        """
        factor = _finite(factor, "factor")
        if factor <= 0:
            raise ValueError("factor must be positive")
        return NormalMetricPatch(self.terms, self.length_scale * factor,
                                 self.radius * factor, self.unit if unit is None else unit)

    def to_json(self) -> str:
        """Versioned coefficients only: no sampled mesh, pickle or executable expression."""
        return json.dumps({"schema": "adaptivecad.normal_metric_patch", "version": 1,
                           "terms": self.terms, "length_scale": self.length_scale,
                           "radius": self.radius, "unit": self.unit},
                          sort_keys=True, allow_nan=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> NormalMetricPatch:
        """Load the strict v1 schema. Unknown keys/versions and duplicate keys fail."""
        if not isinstance(text, str) or len(text) > 100000:
            raise ValueError("Expected a JSON string of at most 100000 characters")

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError(f"Duplicate JSON key: {key}")
                result[key] = value
            return result

        obj = json.loads(text, object_pairs_hook=pairs)
        keys = {"schema", "version", "terms", "length_scale", "radius", "unit"}
        if (not isinstance(obj, dict) or set(obj) != keys
                or obj["schema"] != "adaptivecad.normal_metric_patch"
                or type(obj["version"]) is not int or obj["version"] != 1
                or not isinstance(obj["terms"], list)):
            raise ValueError("Not a supported normal_metric_patch v1 record")
        return cls(obj["terms"], obj["length_scale"], obj["radius"], obj["unit"])


def balanced_directional_patch(epsilon=0.2, length_scale=1.0, unit="mm") -> NormalMetricPatch:
    """Regression fixture: circle_pi=pi, but Gaussian curvature changes with angle."""
    e = _finite(epsilon, "epsilon")
    terms = ((2, 0, 2 * e), (0, 2, -2 * e), (6, 0, e * e),
             (4, 2, -e * e), (2, 4, -e * e), (0, 6, e * e))
    return NormalMetricPatch(terms, length_scale, length_scale, unit)
