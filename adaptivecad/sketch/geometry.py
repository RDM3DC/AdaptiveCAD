"""Core 2D geometry primitives and predicates used by the sketch module.

This module implements the first steps from the project roadmap in
``AGENTS.md`` by providing the foundational vector utilities,
orientation predicates and basic intersection helpers required by a
robust 2D sketch kernel.  The implementation is intentionally
dependency free so it can be reused both by the solver and higher level
editing tools without pulling in heavy numerical stacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, isclose, sin, sqrt
from typing import Iterable, Optional, Sequence, Tuple

# A single tolerance used throughout the predicates.  Individual
# functions accept optional overrides when tighter/looser tolerances are
# required by callers.
EPSILON: float = 1e-9


@dataclass(frozen=True)
class Vec2:
    """A lightweight immutable 2D vector."""

    x: float
    y: float

    # --- basic arithmetic -------------------------------------------------
    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec2":
        return Vec2(self.x / scalar, self.y / scalar)

    # --- vector operations -------------------------------------------------
    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vec2") -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return hypot(self.x, self.y)

    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self, eps: float = EPSILON) -> "Vec2":
        l = self.length()
        if l < eps:
            raise ValueError("Cannot normalise near zero-length vector")
        return self / l

    def distance_to(self, other: "Vec2") -> float:
        return (self - other).length()

    def almost_equals(self, other: "Vec2", eps: float = EPSILON) -> bool:
        return isclose(self.x, other.x, abs_tol=eps) and isclose(self.y, other.y, abs_tol=eps)


@dataclass(frozen=True)
class Mat3:
    """A 3x3 matrix storing row-major affine transforms."""

    m00: float
    m01: float
    m02: float
    m10: float
    m11: float
    m12: float
    m20: float
    m21: float
    m22: float

    def __matmul__(self, other: "Mat3") -> "Mat3":
        def dot_row_col(row: Sequence[float], col: Sequence[float]) -> float:
            return sum(a * b for a, b in zip(row, col))

        rows = (
            (self.m00, self.m01, self.m02),
            (self.m10, self.m11, self.m12),
            (self.m20, self.m21, self.m22),
        )
        cols = (
            (other.m00, other.m10, other.m20),
            (other.m01, other.m11, other.m21),
            (other.m02, other.m12, other.m22),
        )
        return Mat3(
            dot_row_col(rows[0], cols[0]),
            dot_row_col(rows[0], cols[1]),
            dot_row_col(rows[0], cols[2]),
            dot_row_col(rows[1], cols[0]),
            dot_row_col(rows[1], cols[1]),
            dot_row_col(rows[1], cols[2]),
            dot_row_col(rows[2], cols[0]),
            dot_row_col(rows[2], cols[1]),
            dot_row_col(rows[2], cols[2]),
        )

    def transform_point(self, p: Vec2) -> Vec2:
        x = self.m00 * p.x + self.m01 * p.y + self.m02
        y = self.m10 * p.x + self.m11 * p.y + self.m12
        w = self.m20 * p.x + self.m21 * p.y + self.m22
        if abs(w) < EPSILON:
            raise ValueError("Degenerate affine transform with w≈0")
        return Vec2(x / w, y / w)


class Transform2D:
    """Convenience wrappers for building and composing affine transforms."""

    __slots__ = ("_matrix",)

    def __init__(self, matrix: Optional[Mat3] = None) -> None:
        self._matrix = matrix or Mat3(
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
        )

    @property
    def matrix(self) -> Mat3:
        return self._matrix

    def apply(self, p: Vec2) -> Vec2:
        return self._matrix.transform_point(p)

    def combine(self, other: "Transform2D") -> "Transform2D":
        return Transform2D(self._matrix @ other._matrix)

    # --- factories --------------------------------------------------------
    @staticmethod
    def identity() -> "Transform2D":
        return Transform2D()

    @staticmethod
    def translation(dx: float, dy: float) -> "Transform2D":
        return Transform2D(Mat3(1.0, 0.0, dx, 0.0, 1.0, dy, 0.0, 0.0, 1.0))

    @staticmethod
    def scale(sx: float, sy: Optional[float] = None) -> "Transform2D":
        if sy is None:
            sy = sx
        return Transform2D(Mat3(sx, 0.0, 0.0, 0.0, sy, 0.0, 0.0, 0.0, 1.0))

    @staticmethod
    def rotation(theta: float) -> "Transform2D":
        c = cos(theta)
        s = sin(theta)
        return Transform2D(Mat3(c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0))


# --- Geometric predicates -------------------------------------------------


def orientation(a: Vec2, b: Vec2, c: Vec2) -> float:
    """Signed area (twice) of the triangle ABC."""

    return (b - a).cross(c - a)


def is_colinear(a: Vec2, b: Vec2, c: Vec2, eps: float = EPSILON) -> bool:
    return abs(orientation(a, b, c)) <= eps


def distance_point_to_line(p: Vec2, a: Vec2, b: Vec2) -> float:
    """Distance from point ``p`` to the infinite line AB."""

    ab = b - a
    area2 = abs(ab.cross(p - a))
    length = ab.length()
    if length < EPSILON:
        return p.distance_to(a)
    return area2 / length


# --- Intersection helpers -------------------------------------------------


@dataclass(frozen=True)
class Intersection:
    kind: str  # "none", "point", "segment"
    point: Optional[Vec2] = None
    segment: Optional[Tuple[Vec2, Vec2]] = None

    @staticmethod
    def none() -> "Intersection":
        return Intersection("none")

    @staticmethod
    def from_point(pt: Vec2) -> "Intersection":
        return Intersection("point", point=pt)

    @staticmethod
    def from_segment(a: Vec2, b: Vec2) -> "Intersection":
        return Intersection("segment", segment=(a, b))


# Install compatibility factories after dataclass has captured real None defaults.
# Instance payloads shadow these non-data descriptors, preserving both old APIs.
setattr(Intersection, "point", staticmethod(Intersection.from_point))
setattr(Intersection, "segment", staticmethod(Intersection.from_segment))

def _clip_projection(t: float, eps: float = EPSILON) -> bool:
    return -eps <= t <= 1.0 + eps


def segment_intersection(
    a0: Vec2, a1: Vec2, b0: Vec2, b1: Vec2, eps: float = EPSILON
) -> Intersection:
    """Return the intersection between two line segments."""

    r = a1 - a0
    s = b1 - b0
    denom = r.cross(s)
    qp = b0 - a0

    if abs(denom) <= eps:
        # Parallel or colinear
        if abs(qp.cross(r)) > eps:
            return Intersection.none()
        # Colinear - project to scalar parameter and look for overlap
        r_len_sq = r.length_squared()
        if r_len_sq <= eps:
            # Both segments degenerately points
            if a0.almost_equals(b0, eps):
                return Intersection.from_point(a0)
            return Intersection.none()

        t0 = qp.dot(r) / r_len_sq
        t1 = t0 + s.dot(r) / r_len_sq
        t_min, t_max = sorted((t0, t1))
        if t_max < -eps or t_min > 1.0 + eps:
            return Intersection.none()

        def clamp(t):
            return max(0.0, min(1.0, t))

        i0 = a0 + r * clamp(t_min)
        i1 = a0 + r * clamp(t_max)
        if i0.distance_to(i1) <= eps:
            return Intersection.from_point(i0)
        return Intersection.from_segment(i0, i1)

    t = qp.cross(s) / denom
    u = qp.cross(r) / denom
    if _clip_projection(t, eps) and _clip_projection(u, eps):
        return Intersection.from_point(a0 + r * t)
    return Intersection.none()


def line_circle_intersections(
    p: Vec2, direction: Vec2, center: Vec2, radius: float, eps: float = EPSILON
) -> Tuple[Vec2, ...]:
    """Compute intersections between an infinite line and a circle."""

    d = direction
    f = p - center
    a = d.dot(d)
    b = 2.0 * f.dot(d)
    c = f.dot(f) - radius * radius

    discriminant = b * b - 4.0 * a * c
    if discriminant < -eps:
        return tuple()
    if abs(discriminant) <= eps:
        t = -b / (2.0 * a)
        return (p + d * t,)

    sqrt_disc = sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)
    return (p + d * t1, p + d * t2)


def segment_circle_intersections(
    a: Vec2, b: Vec2, center: Vec2, radius: float, eps: float = EPSILON
) -> Tuple[Vec2, ...]:
    direction = b - a
    pts = []
    for pt in line_circle_intersections(a, direction, center, radius, eps):
        # Solve for t in a + d * t = pt
        t = (pt - a).dot(direction) / direction.dot(direction)
        if _clip_projection(t, eps):
            pts.append(pt)
    return tuple(pts)


def closest_point_on_segment(p: Vec2, a: Vec2, b: Vec2) -> Vec2:
    ab = b - a
    denom = ab.dot(ab)
    if denom <= EPSILON:
        return a
    t = (p - a).dot(ab) / denom
    t = max(0.0, min(1.0, t))
    return a + ab * t


def polyline_length(points: Iterable[Vec2]) -> float:
    total = 0.0
    prev: Optional[Vec2] = None
    for pt in points:
        if prev is not None:
            total += prev.distance_to(pt)
        prev = pt
    return total
