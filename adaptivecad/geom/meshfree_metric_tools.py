"""Measurements and local initial-value geodesics for NormalMetricPatch.

Numerical paths are not globally shortest-path certificates or machine paths.
Metric coefficients remain authoritative; path samples are numerical results.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .directional_metric import IntegralResult, NormalMetricPatch, _finite, _integrate


def _pair(values, name):
    try:
        values = tuple(_finite(v, name) for v in values)
    except TypeError as exc:
        raise ValueError(f"{name} must contain two finite numbers") from exc
    if len(values) != 2:
        raise ValueError(f"{name} must contain two numbers")
    return values


def metric_derivatives(patch, x, y):
    """Analytic dg[k][i][j], derivative with respect to coordinate k."""
    patch.metric(x, y)  # validate domain and positivity before computation
    L = patch.length_scale
    X, Y = x/L, y/L
    A = math.fsum(c*X**i*Y**j for i, j, c in patch.terms)
    Ax = math.fsum(c*i*X**(i-1)*Y**j for i, j, c in patch.terms if i)
    Ay = math.fsum(c*j*X**i*Y**(j-1) for i, j, c in patch.terms if j)
    dx = ((Ax*Y*Y, -Ax*X*Y-A*Y), (-Ax*X*Y-A*Y, Ax*X*X+2*A*X))
    dy = ((Ay*Y*Y+2*A*Y, -Ay*X*Y-A*X), (-Ay*X*Y-A*X, Ay*X*X))
    return tuple(tuple(tuple(_finite(v/L, "metric derivative") for v in row)
                       for row in d) for d in (dx, dy))


def connection(patch, x, y):
    """Christoffel symbols Gamma[k][i][j] in Cartesian chart coordinates."""
    g = patch.metric(x, y)
    dg = metric_derivatives(patch, x, y)
    det = g[0][0]*g[1][1]-g[0][1]**2
    if not math.isfinite(det) or det <= 0:
        raise ValueError("Metric inversion is numerically singular")
    inv = ((g[1][1]/det, -g[0][1]/det), (-g[0][1]/det, g[0][0]/det))
    return tuple(tuple(tuple(0.5*math.fsum(inv[k][a]*(dg[i][a][j]+dg[j][a][i]-dg[a][i][j])
                                                for a in range(2))
                              for j in range(2)) for i in range(2)) for k in range(2))


def angle_between(patch, position, a, b):
    """Unsigned metric angle in radians at a single chart position."""
    x, y = _pair(position, "position")
    a, b = _pair(a, "a"), _pair(b, "b")
    sa, sb = patch.speed(x, y, *a), patch.speed(x, y, *b)
    if sa == 0 or sb == 0:
        raise ValueError("Angle requires nonzero tangent vectors")
    g = patch.metric(x, y)
    cosine = math.fsum((a[i]/sa)*g[i][j]*(b[j]/sb) for i in range(2) for j in range(2))
    return math.acos(max(-1., min(1., _finite(cosine, "angle cosine"))))


def segment_length(patch, start, end, *, abs_tol=1e-9, rel_tol=1e-9):
    """Length of the specified straight chart segment, NOT geodesic distance."""
    a, b = _pair(start, "start"), _pair(end, "end")
    patch.metric(*a)
    patch.metric(*b)
    v = (b[0]-a[0], b[1]-a[1])
    return _integrate(lambda t: patch.speed(a[0]+t*v[0], a[1]+t*v[1], *v),
                      0, 1, abs_tol, rel_tol)


def disk_area(patch, radius, *, abs_tol=1e-8, rel_tol=1e-8):
    """Intrinsic disk area from integrating circumference; error is estimated."""
    radius, tol = _finite(radius, "radius"), _finite(abs_tol, "abs_tol")
    patch.directional_pi(radius, 0)
    if tol <= 0:
        raise ValueError("abs_tol must be positive")
    inner_errors, evaluations = [], 0

    def circumference(r):
        nonlocal evaluations
        result = patch.sector_length(r, abs_tol=tol/(4*max(radius, 1e-100)), rel_tol=rel_tol/4)
        inner_errors.append(result.estimated_error)
        evaluations += result.evaluations
        return result.value

    result = _integrate(circumference, 0, radius, tol/2, rel_tol/2)
    error = result.estimated_error + radius*max(inner_errors, default=0)
    if error > max(tol, rel_tol*abs(result.value)):
        raise ArithmeticError("Nested area error estimate exceeds tolerance")
    return IntegralResult(result.value, error, evaluations)


def area_radius(patch, area, *, radius_tol=1e-7, area_tol=1e-8):
    """Numerical inverse of disk_area on this declared patch, with a bracket."""
    area = _finite(area, "area")
    rt, at = _finite(radius_tol, "radius_tol"), _finite(area_tol, "area_tol")
    if area < 0 or rt <= 0 or at <= 0:
        raise ValueError("Area must be nonnegative and tolerances positive")
    if area == 0:
        return 0.
    maximum = disk_area(patch, patch.radius, abs_tol=at/8, rel_tol=0).value
    if area > maximum:
        raise ValueError("Requested area exceeds this patch")
    lo, hi = 0., patch.radius
    for _ in range(80):
        mid = (lo+hi)/2
        value = disk_area(patch, mid, abs_tol=at/8, rel_tol=0).value
        if abs(value-area) <= at and hi-lo <= 2*rt:
            return mid
        if value < area:
            lo = mid
        else:
            hi = mid
    raise ArithmeticError("Area-to-radius solve did not converge")


@dataclass(frozen=True)
class GeodesicResult:
    """Accepted adaptive samples, completed length, and numerical diagnostics."""
    arclengths: tuple
    positions: tuple
    tangents: tuple
    transported_vectors: tuple
    length: float
    max_speed_drift: float
    evaluations: int


def trace_geodesic(patch: NormalMetricPatch, start, direction, length, *,
                   transport=None, tolerance=1e-8, max_steps=20000):
    """Initial-value geodesic with optional parallel transport, adaptive RK4.

    Direction is normalized to metric unit speed. The path must remain inside
    the declared disk. A domain exit or exhausted budget raises, never returns
    an incomplete path as successful. Error control is dimensionless relative
    to length_scale, not a certified bound. No endpoint shooting is performed.
    """
    start, direction = _pair(start, "start"), _pair(direction, "direction")
    length, tol = _finite(length, "length"), _finite(tolerance, "tolerance")
    if length < 0 or not 1e-12 <= tol <= 1e-3:
        raise ValueError("Require length >= 0 and 1e-12 <= tolerance <= 1e-3")
    if type(max_steps) is not int or not 1 <= max_steps <= 100000:
        raise ValueError("max_steps must be an integer in [1,100000]")
    speed = patch.speed(*start, *direction)
    if speed == 0:
        raise ValueError("Geodesic direction must be nonzero")
    vec = () if transport is None else _pair(transport, "transport")
    state = start + tuple(v/speed for v in direction) + vec
    L = patch.length_scale
    scales = (L, L, 1., 1.) + (() if not vec else (max(1., math.hypot(*vec)),)*2)
    s, h, evaluations = 0., min(length, L/20), 0
    lengths, states = [0.], [state]

    def rhs(y):
        nonlocal evaluations
        evaluations += 1
        if evaluations > 500000:
            raise ArithmeticError("Geodesic evaluation budget exhausted")
        gamma = connection(patch, y[0], y[1])
        v = y[2:4]
        acc = tuple(-math.fsum(gamma[k][i][j]*v[i]*v[j] for i in range(2) for j in range(2))
                    for k in range(2))
        if len(y) == 4:
            return v + acc
        w = y[4:6]
        dw = tuple(-math.fsum(gamma[k][i][j]*v[i]*w[j] for i in range(2) for j in range(2))
                   for k in range(2))
        return v + acc + dw

    def rk4(y, step):
        k1 = rhs(y)
        k2 = rhs(tuple(a+step*b/2 for a, b in zip(y, k1)))
        k3 = rhs(tuple(a+step*b/2 for a, b in zip(y, k2)))
        k4 = rhs(tuple(a+step*b for a, b in zip(y, k3)))
        return tuple(a+step*(b+2*c+2*d+e)/6 for a, b, c, d, e in zip(y, k1, k2, k3, k4))

    for _ in range(max_steps):
        if s >= length:
            break
        h = min(h, length-s)
        if h <= max(L, length)*1e-14 or s+h == s:
            raise ArithmeticError("Step collapsed near disk boundary or stiff geometry")
        try:
            full = rk4(state, h)
            half = rk4(rk4(state, h/2), h/2)
            correction = tuple((b-a)/15 for a, b in zip(full, half))
            trial = tuple(a+b for a, b in zip(half, correction))
            patch.metric(trial[0], trial[1])
            if not all(math.isfinite(v) for v in trial):
                raise ValueError("Nonfinite geodesic state")
        except ValueError:
            h /= 2
            continue
        error = max(abs(e)/scale for e, scale in zip(correction, scales))
        if error > tol:
            h *= max(0.1, 0.8*(tol/error)**0.2)
            continue
        s += h
        state = trial
        states.append(state)
        lengths.append(s)
        h *= 2 if error == 0 else min(2., max(0.5, 0.9*(tol/error)**0.2))
    if s < length:
        raise ArithmeticError("Geodesic step budget exhausted")
    drift = max(abs(patch.speed(y[0], y[1], y[2], y[3])-1) for y in states)
    if drift > max(1e-6, 100*tol):
        raise ArithmeticError("Geodesic unit-speed drift exceeds acceptance threshold")
    return GeodesicResult(tuple(lengths), tuple(y[:2] for y in states),
                          tuple(y[2:4] for y in states), tuple(y[4:] for y in states),
                          length, drift, evaluations)
