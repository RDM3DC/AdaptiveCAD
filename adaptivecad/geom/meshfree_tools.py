"""Coefficient-based curves and evaluated surfaces; not a solid/B-rep kernel.

Authoritative objects contain no triangles. Surface constructors create a
parametric *sheet*, without caps, sewing, booleans or manufacturing guarantees.
All public angles are radians, parameters are in [0,1], and lengths use the
owning document's explicit unit. See docs/meshfree_tools.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction

from .directional_metric import IntegralResult, _finite, _integrate

ZERO = (0.0, 0.0, 0.0)
IDENTITY = ((1., 0., 0., 0.), (0., 1., 0., 0.),
            (0., 0., 1., 0.), (0., 0., 0., 1.))
UNITS = {"mm": Fraction(1, 1000), "cm": Fraction(1, 100), "m": Fraction(1),
         "in": Fraction(127, 5000), "ft": Fraction(381, 1250),
         "ft_us": Fraction(1200, 3937)}


def point(p):
    if hasattr(p, "x") and hasattr(p, "y") and hasattr(p, "z"):
        p = (p.x, p.y, p.z)
    try:
        result = tuple(_finite(x, "coordinate") for x in p)
    except TypeError as exc:
        raise ValueError("Expected three finite coordinates") from exc
    if len(result) != 3:
        raise ValueError("Expected three coordinates")
    return result


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def mul(a, t):
    return tuple(x * t for x in a)


def sub(a, b):
    return add(a, mul(b, -1))


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def norm(a):
    return math.hypot(*a)


def unit(a):
    a = point(a)
    n = norm(a)
    if n == 0 or not math.isfinite(n):
        raise ValueError("Direction must be finite and nonzero")
    return mul(a, 1 / n)


def parameter(t):
    t = _finite(t, "parameter")
    if not 0 <= t <= 1:
        raise ValueError("Parameter must lie in [0,1]")
    return t


def count(n, maximum=1000):
    if type(n) is not int or not 1 <= n <= maximum:
        raise ValueError(f"Count must be an integer in [1,{maximum}]")
    return n


def conversion_factor(source, target):
    if source not in UNITS or target not in UNITS:
        raise ValueError(f"Explicit unit required: {tuple(UNITS)}")
    return float(UNITS[source] / UNITS[target])


def matrix(m):
    try:
        m = tuple(tuple(_finite(v, "matrix entry") for v in row) for row in m)
    except TypeError as exc:
        raise ValueError("Expected affine 4x4 matrix") from exc
    if len(m) != 4 or any(len(row) != 4 for row in m) or m[3] != (0., 0., 0., 1.):
        raise ValueError("Expected affine 4x4 matrix with last row [0,0,0,1]")
    axes = [tuple(m[i][j] for i in range(3)) for j in range(3)]
    lengths = [norm(a) for a in axes]
    if any(s == 0 or not math.isfinite(s) for s in lengths):
        raise ValueError("Singular or overflowing transform")
    axes = [mul(a, 1/s) for a, s in zip(axes, lengths)]
    if abs(dot(axes[0], cross(axes[1], axes[2]))) < 1e-12:
        raise ValueError("Singular or near-singular transform")
    return m


def apply(m, p, vector=False):
    return point(tuple(dot(row[:3], p) + (0 if vector else row[3]) for row in m[:3]))


def compose(a, b):
    return matrix(tuple(tuple(math.fsum(a[i][k]*b[k][j] for k in range(4))
                              for j in range(4)) for i in range(4)))


def translation(delta):
    delta = point(delta)
    return tuple(tuple(IDENTITY[i][j] if j != 3 or i == 3 else delta[i]
                       for j in range(4)) for i in range(4))


def rotation(axis=(0, 0, 1), angle=0., origin=ZERO):
    a, angle, origin = unit(axis), _finite(angle, "angle"), point(origin)
    c, s = math.cos(angle), math.sin(angle)
    skew = ((0., -a[2], a[1]), (a[2], 0., -a[0]), (-a[1], a[0], 0.))
    rows = tuple(tuple(c*(i == j) + (1-c)*a[i]*a[j] + s*skew[i][j]
                       for j in range(3)) for i in range(3))
    return matrix(tuple(row + (origin[i] - dot(row, origin),)
                        for i, row in enumerate(rows)) + (IDENTITY[3],))


def scaling(factor, origin=ZERO):
    factor, origin = _finite(factor, "factor"), point(origin)
    if factor <= 0:
        raise ValueError("Scale must be positive; use mirror for reflection")
    return matrix(tuple(tuple(factor*(i == j) for j in range(3)) +
                        ((1-factor)*origin[i],) for i in range(3)) + (IDENTITY[3],))


def reflection(normal=(1, 0, 0), origin=ZERO):
    a, origin = unit(normal), point(origin)
    rows = tuple(tuple(float(i == j)-2*a[i]*a[j] for j in range(3)) for i in range(3))
    return matrix(tuple(row + (origin[i]-dot(row, origin),)
                        for i, row in enumerate(rows)) + (IDENTITY[3],))


def _casteljau(points, t):
    work = list(points)
    if not work:
        return ZERO
    while len(work) > 1:
        work = [add(mul(a, 1-t), mul(b, t)) for a, b in zip(work, work[1:])]
    return point(work[0])


@dataclass(frozen=True)
class Curve:
    """Immutable Bezier or elliptic arc, optionally trimmed/reversed.

    Arc points are (center, cosine_vector, sine_vector). The vectors need not
    be perpendicular after an affine transform. Bezier degree is at most 32.
    """
    kind: str
    points: tuple
    interval: tuple = (0., 1.)
    start: float = 0.
    sweep: float = math.tau

    def __post_init__(self):
        pts = tuple(point(p) for p in self.points)
        interval = tuple(parameter(t) for t in self.interval)
        if len(interval) != 2 or interval[0] == interval[1]:
            raise ValueError("Require two distinct trim parameters")
        if self.kind not in ("bezier", "arc"):
            raise ValueError("Unsupported curve kind")
        if self.kind == "bezier" and not 1 <= len(pts) <= 33:
            raise ValueError("Bezier requires 1..33 control points")
        start, sweep = _finite(self.start, "start"), _finite(self.sweep, "sweep")
        if self.kind == "arc":
            if len(pts) != 3 or norm(pts[1]) == 0 or norm(pts[2]) == 0:
                raise ValueError("Arc requires center and two nonzero frame vectors")
            if norm(cross(unit(pts[1]), unit(pts[2]))) < 1e-12:
                raise ValueError("Arc frame is singular")
            if sweep == 0 or abs(sweep) > math.tau:
                raise ValueError("Arc sweep must be nonzero and at most one full turn")
        object.__setattr__(self, "points", pts)
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "sweep", sweep)

    @classmethod
    def line(cls, start, end):
        return cls("bezier", (point(start), point(end)))

    @classmethod
    def from_native_bezier(cls, curve):
        """Copy the existing AdaptiveCAD BezierCurve control coefficients."""
        return cls("bezier", tuple(point(p) for p in curve.control_points))

    @classmethod
    def arc(cls, center=ZERO, radius=1., normal=(0, 0, 1), x_direction=(1, 0, 0),
            start=0., sweep=math.tau):
        n, radius = unit(normal), _finite(radius, "radius")
        if radius <= 0:
            raise ValueError("Radius must be positive")
        x = point(x_direction)
        x = unit(sub(x, mul(n, dot(n, x))))
        return cls("arc", (point(center), mul(x, radius), mul(cross(n, x), radius)),
                   start=start, sweep=sweep)

    def jet(self, t):
        """Position and analytic first/second derivatives with respect to t."""
        t = parameter(t)
        a, b = self.interval
        q, span = a + (b-a)*t, b-a
        if self.kind == "arc":
            c, x, y = self.points
            angle, w = self.start + self.sweep*q, self.sweep*span
            v = add(mul(x, math.cos(angle)), mul(y, math.sin(angle)))
            d = mul(add(mul(x, -math.sin(angle)), mul(y, math.cos(angle))), w)
            return point(add(c, v)), point(d), point(mul(v, -w*w))
        pts = self.points
        first = tuple(mul(sub(y, x), len(pts)-1) for x, y in zip(pts, pts[1:]))
        second = tuple(mul(sub(y, x), len(first)-1) for x, y in zip(first, first[1:]))
        return (_casteljau(pts, q), point(mul(_casteljau(first, q), span)),
                point(mul(_casteljau(second, q), span*span)))

    def evaluate(self, t):
        return self.jet(t)[0]

    def derivative(self, t):
        return self.jet(t)[1]

    def trim(self, start, stop):
        start, stop = parameter(start), parameter(stop)
        if start == stop:
            raise ValueError("Cannot create a zero-parameter-span trim")
        a, b = self.interval
        return replace(self, interval=(a+(b-a)*start, a+(b-a)*stop))

    def split(self, t):
        if not 0 < parameter(t) < 1:
            raise ValueError("Split must be strictly inside (0,1)")
        return self.trim(0, t), self.trim(t, 1)

    def reversed(self):
        return self.trim(1, 0)

    def transformed(self, transform):
        transform = matrix(transform)
        pts = tuple(apply(transform, p, self.kind == "arc" and i > 0)
                    for i, p in enumerate(self.points))
        return replace(self, points=pts)

    def length(self, *, abs_tol=1e-8, rel_tol=1e-9):
        return _integrate(lambda t: norm(self.derivative(t)), 0, 1, abs_tol, rel_tol,
                          panels=max(16, 2*len(self.points)))

    def curvature(self, t):
        _, d, dd = self.jet(t)
        speed = norm(d)
        if speed == 0:
            raise ValueError("Curvature undefined at a stationary point")
        return _finite(norm(cross(mul(d, 1/speed), mul(dd, 1/speed))) / speed,
                       "curvature")

    def stations(self, segments, *, abs_tol=1e-8):
        """Numerical equal-arclength division; returns (parameter, point) pairs."""
        count(segments, 256)
        tol = _finite(abs_tol, "abs_tol")
        if tol <= 0:
            raise ValueError("abs_tol must be positive")
        total = self.length(abs_tol=tol/8, rel_tol=0).value
        if total <= tol:
            raise ValueError("Curve is too short for the requested length tolerance")
        output = [(0., self.evaluate(0))]
        for i in range(1, segments):
            target, lo, hi = total*i/segments, 0., 1.
            for _ in range(64):
                t = (lo+hi)/2
                length = self.trim(0, t).length(abs_tol=tol/8, rel_tol=0).value
                if abs(length-target) <= tol/2:
                    break
                if length < target:
                    lo = t
                else:
                    hi = t
            else:
                raise ArithmeticError("Station parameter solve did not converge")
            output.append((t, self.evaluate(t)))
        return tuple(output + [(1., self.evaluate(1))])


@dataclass(frozen=True)
class Surface:
    """Evaluated sheet: extrusion, arbitrary-axis revolution, ruled loft,
    or fixed-orientation translation sweep. No solid/topology is implied.
    """
    kind: str
    profile: Curve
    guide: Curve | None = None
    vector: tuple = (0., 0., 1.)
    origin: tuple = ZERO
    angle: float = math.tau
    transform: tuple = IDENTITY

    def __post_init__(self):
        if self.kind not in ("extrude", "revolve", "loft", "sweep"):
            raise ValueError("Unsupported surface kind")
        if not isinstance(self.profile, Curve):
            raise ValueError("Expected a Curve profile")
        needs_guide = self.kind in ("loft", "sweep")
        if (needs_guide and not isinstance(self.guide, Curve)) or (not needs_guide and self.guide is not None):
            raise ValueError("Only loft/sweep require a Curve guide")
        vector, origin = point(self.vector), point(self.origin)
        angle = _finite(self.angle, "angle")
        if self.kind in ("extrude", "revolve"):
            unit(vector)
        if self.kind == "revolve":
            vector = unit(vector)
            if angle == 0 or abs(angle) > math.tau:
                raise ValueError("Revolution angle must be nonzero and <= one turn")
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "angle", angle)
        object.__setattr__(self, "transform", matrix(self.transform))

    def jet(self, u, v):
        """Position, Su, Sv, Suu, Suv, Svv; derivatives are analytic."""
        u, v = parameter(u), parameter(v)
        p, d, dd = self.profile.jet(u)
        if self.kind == "extrude":
            result = (add(p, mul(self.vector, v)), d, self.vector, dd, ZERO, ZERO)
        elif self.kind == "revolve":
            r = rotation(self.vector, self.angle*v)
            q, du, duu = apply(r, sub(p, self.origin), True), apply(r, d, True), apply(r, dd, True)
            dv = mul(cross(self.vector, q), self.angle)
            result = (add(self.origin, q), du, dv, duu,
                      mul(cross(self.vector, du), self.angle),
                      mul(cross(self.vector, dv), self.angle))
        elif self.kind == "loft":
            q, e, ee = self.guide.jet(u)
            result = (add(mul(p, 1-v), mul(q, v)), add(mul(d, 1-v), mul(e, v)),
                      sub(q, p), add(mul(dd, 1-v), mul(ee, v)), sub(e, d), ZERO)
        else:
            q, e, ee = self.guide.jet(v)
            result = (add(p, sub(q, self.guide.evaluate(0))), d, e, dd, ZERO, ee)
        return tuple(apply(self.transform, x, i != 0) for i, x in enumerate(result))

    def evaluate(self, u, v):
        return self.jet(u, v)[0]

    def differential(self, u, v):
        """Normal, first fundamental form, Gaussian and signed mean curvature."""
        _, a, b, aa, ab, bb = self.jet(u, v)
        la, lb = norm(a), norm(b)
        if la == 0 or lb == 0:
            raise ValueError("Singular surface parameterization")
        n = cross(mul(a, 1/la), mul(b, 1/lb))
        if norm(n) < 1e-12:
            raise ValueError("Singular or near-singular surface parameterization")
        n = unit(n)
        E, F, G = dot(a, a), dot(a, b), dot(b, b)
        area = norm(cross(a, b))
        determinant = area*area
        if determinant == 0 or not math.isfinite(determinant):
            raise ValueError("Surface scale is outside supported numerical range")
        e, f, g = dot(n, aa), dot(n, ab), dot(n, bb)
        K = _finite((e*g-f*f)/determinant, "Gaussian curvature")
        H = _finite((E*g-2*F*f+G*e)/(2*determinant), "mean curvature")
        return {"normal": n, "metric": ((E, F), (F, G)),
                "gaussian_curvature": K, "mean_curvature": H,
                "area_density": area}

    def transformed(self, transform):
        return replace(self, transform=compose(matrix(transform), self.transform))

    def area(self, *, abs_tol=1e-7, rel_tol=1e-8):
        """Parameter-domain area, counting multiplicity; not a solid area audit."""
        tol = _finite(abs_tol, "abs_tol")
        if tol <= 0:
            raise ValueError("abs_tol must be positive")
        inner_errors, calls = [], 0

        def at_u(u):
            nonlocal calls
            def integrand(v):
                _, a, b, *_ = self.jet(u, v)
                return norm(cross(a, b))
            result = _integrate(integrand, 0, 1, tol/4, rel_tol/4, panels=8)
            inner_errors.append(result.estimated_error)
            calls += result.evaluations
            return result.value

        result = _integrate(at_u, 0, 1, tol/2, rel_tol/2, panels=8)
        error = result.estimated_error + max(inner_errors, default=0)
        if error > max(tol, rel_tol*abs(result.value)):
            raise ArithmeticError("Nested area error estimate exceeds tolerance")
        return IntegralResult(result.value, error, calls)


def rectangular_array(entity, rows, columns, row_step=(0, 10, 0), column_step=(10, 0, 0)):
    count(rows)
    count(columns)
    if rows*columns > 1000:
        raise ValueError("Array exceeds 1000 instances")
    row_step, column_step = point(row_step), point(column_step)
    return tuple(entity.transformed(translation(add(mul(row_step, i), mul(column_step, j))))
                 for i in range(rows) for j in range(columns))


def polar_array(entity, instances, angle=math.tau, axis=(0, 0, 1), origin=ZERO):
    """Full turns omit the duplicate seam; partial arrays include both ends."""
    count(instances)
    angle = _finite(angle, "angle")
    if angle == 0 or abs(angle) > math.tau:
        raise ValueError("Array angle must be nonzero and at most one turn")
    denominator = instances if abs(angle) == math.tau else max(1, instances-1)
    return tuple(entity.transformed(rotation(axis, angle*i/denominator, origin))
                 for i in range(instances))


def wireframe(entity, samples=65, lines=9):
    """Display-only polylines. Never used as authoritative geometry or G-code."""
    count(samples, 1024)
    count(lines, 64)
    if samples < 2 or lines < 2:
        raise ValueError("Need at least two samples/lines")
    ts = [i/(samples-1) for i in range(samples)]
    if isinstance(entity, Curve):
        return (tuple(entity.evaluate(t) for t in ts),)
    if not isinstance(entity, Surface):
        raise ValueError("Expected Curve or Surface")
    paths = []
    for i in range(lines):
        s = i/(lines-1)
        paths.extend((tuple(entity.evaluate(s, t) for t in ts),
                      tuple(entity.evaluate(t, s) for t in ts)))
    return tuple(paths)
