"""Differential and measurement tools for NormalMetricPatch (no surface meshes).

Chart coordinates and vector components must use the patch's declared unit.
These are intrinsic measurements, not a projection of world-space CAD objects.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .directional_metric import IntegralResult, NormalMetricPatch, _finite, _integrate

# Exact definitions; ft_us remains available for legacy survey data.
METRES_PER_UNIT = {
    "mm": Fraction(1, 1000), "cm": Fraction(1, 100), "m": Fraction(1),
    "in": Fraction(127, 5000), "ft": Fraction(381, 1250),
    "ft_us": Fraction(1200, 3937),
}


def unit_factor(source: str, target: str) -> float:
    """Explicit conversion; unknown labels fail instead of guessing."""
    if source not in METRES_PER_UNIT or target not in METRES_PER_UNIT:
        raise ValueError("Supported units: " + ", ".join(METRES_PER_UNIT))
    return float(METRES_PER_UNIT[source] / METRES_PER_UNIT[target])


def point(patch: NormalMetricPatch, xy) -> tuple[float, float]:
    if not isinstance(xy, (tuple, list)) or len(xy) != 2:
        raise ValueError("Expected two chart coordinates")
    x, y = _finite(xy[0], "x"), _finite(xy[1], "y")
    patch.metric(x, y)
    return x, y


def metric_derivatives(patch: NormalMetricPatch, x: float, y: float):
    """Return dg[k][i][j]=partial_k g_ij, analytically, including the center."""
    X, Y, A, _, _, _ = patch._state(x, y)
    ax = math.fsum(c * i * X ** (i - 1) * Y**j
                   for i, j, c in patch.terms if i)
    ay = math.fsum(c * j * X**i * Y ** (j - 1)
                   for i, j, c in patch.terms if j)
    inv = 1.0 / patch.length_scale
    dx = ((ax * Y * Y, -ax * X * Y - A * Y),
          (-ax * X * Y - A * Y, ax * X * X + 2 * A * X))
    dy = ((ay * Y * Y + 2 * A * Y, -ay * X * Y - A * X),
          (-ay * X * Y - A * X, ay * X * X))
    return tuple(tuple(tuple(_finite(v * inv, "metric derivative") for v in row)
                       for row in matrix) for matrix in (dx, dy))


def christoffel(patch: NormalMetricPatch, x: float, y: float):
    """Levi-Civita connection Gamma[k][i][j] in registered Cartesian coordinates."""
    g = patch.metric(x, y)
    # Use the known radial/transverse determinant rather than subtracting
    # two potentially large products of Cartesian metric coefficients.
    det = patch._state(x, y)[-1]
    inverse = ((g[1][1] / det, -g[0][1] / det),
               (-g[1][0] / det, g[0][0] / det))
    dg = metric_derivatives(patch, x, y)
    return tuple(tuple(tuple(_finite(0.5 * math.fsum(
        inverse[k][l] * (dg[i][l][j] + dg[j][l][i] - dg[l][i][j])
        for l in range(2)), "Christoffel symbol")
        for j in range(2)) for i in range(2)) for k in range(2))


def inner_product(patch: NormalMetricPatch, xy, u, v) -> float:
    x, y = point(patch, xy)
    if len(u) != 2 or len(v) != 2:
        raise ValueError("Vectors must have two components")
    u = tuple(_finite(c, "u") for c in u)
    v = tuple(_finite(c, "v") for c in v)
    g = patch.metric(x, y)
    return _finite(math.fsum(u[i] * g[i][j] * v[j]
                            for i in range(2) for j in range(2)), "inner product")


def angle_between(patch: NormalMetricPatch, xy, u, v) -> float:
    """Unsigned intrinsic angle in radians, in [0, pi]. Zero vectors fail."""
    uu, vv = inner_product(patch, xy, u, u), inner_product(patch, xy, v, v)
    if uu <= 0 or vv <= 0:
        raise ValueError("An angle requires two nonzero vectors")
    # Normalize each vector separately to avoid overflowing uu*vv.
    un = tuple(c / math.sqrt(uu) for c in u)
    vn = tuple(c / math.sqrt(vv) for c in v)
    return math.acos(max(-1.0, min(1.0, inner_product(patch, xy, un, vn))))


def segment_length(patch: NormalMetricPatch, start, stop, *, abs_tol=1e-9,
                   rel_tol=1e-9) -> IntegralResult:
    """Length of the chart-straight segment, NOT a shortest-distance claim."""
    a, b = point(patch, start), point(patch, stop)
    dx, dy = b[0] - a[0], b[1] - a[1]
    # The disk is convex, so endpoints certify that the whole segment is in-domain.
    return _integrate(lambda t: patch.speed(a[0] + t * dx, a[1] + t * dy, dx, dy),
                      0, 1, abs_tol, rel_tol)


def disk_area(patch: NormalMetricPatch, r: float, *, abs_tol=1e-8,
              rel_tol=1e-8) -> IntegralResult:
    """Area from integral_0^r C(s) ds. Errors are estimates, not certificates.

    Allocate half the absolute budget to angular quadrature and half to radial
    quadrature; include the maximum sampled inner error in the returned estimate.
    """
    r, abs_tol, rel_tol = (_finite(r, "radius"), _finite(abs_tol, "abs_tol"),
                          _finite(rel_tol, "rel_tol"))
    patch.directional_pi(r, 0)
    if abs_tol <= 0 or rel_tol < 0:
        raise ValueError("Require abs_tol > 0 and rel_tol >= 0")
    if r == 0:
        return IntegralResult(0.0, 0.0, 0)
    inner_errors, evaluations = [], 0

    def circumference(s):
        nonlocal evaluations
        result = patch.sector_length(s, abs_tol=abs_tol / (2 * r), rel_tol=0)
        inner_errors.append(result.estimated_error)
        evaluations += result.evaluations
        if evaluations > 200000:
            from .directional_metric import IntegrationError
            raise IntegrationError("Area exceeded 200000 angular evaluations")
        return result.value

    outer = _integrate(circumference, 0, r, abs_tol / 2, 0)
    return IntegralResult(outer.value, outer.estimated_error + r * max(inner_errors),
                          evaluations)


@dataclass(frozen=True)
class CurveAnalysis:
    """Local native-Bezier result. Curvature is undefined at stationary points."""
    x: float
    y: float
    speed: float
    geodesic_curvature: float | None
    gaussian_curvature: float


def analyze_bezier(patch: NormalMetricPatch, curve, t: float) -> CurveAnalysis:
    from .bezier import BezierCurve

    t = _finite(t, "t")
    if not 0 <= t <= 1 or not isinstance(curve, BezierCurve) or not curve.control_points:
        raise ValueError("Require a native Bezier curve and 0 <= t <= 1")
    for p in curve.control_points:
        if p.z != 0:
            raise ValueError("Bezier control points must have z=0 in this chart")
        point(patch, (p.x, p.y))
    p, v = curve.evaluate(t), curve.derivative(t)
    n = len(curve.control_points) - 1
    if n >= 2:
        controls = [n * (n - 1) * (curve.control_points[i + 2]
                    - 2 * curve.control_points[i + 1] + curve.control_points[i])
                    for i in range(n - 1)]
        acceleration = BezierCurve(controls).evaluate(t)
        a = (acceleration.x, acceleration.y)
    else:
        a = (0.0, 0.0)
    velocity = (v.x, v.y)
    speed = patch.speed(p.x, p.y, *velocity)
    kg = None
    if speed > 0:
        connection = christoffel(patch, p.x, p.y)
        cov_a = tuple(a[k] + math.fsum(connection[k][i][j] * velocity[i] * velocity[j]
                      for i in range(2) for j in range(2)) for k in range(2))
        det = patch._state(p.x, p.y)[-1]
        kg = _finite(math.sqrt(det) * (velocity[0] * cov_a[1] - velocity[1] * cov_a[0])
                     / speed**3, "geodesic curvature")
    return CurveAnalysis(p.x, p.y, speed, kg, patch.gaussian_curvature(p.x, p.y))
