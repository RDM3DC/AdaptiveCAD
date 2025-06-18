"""B-spline curve utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..linalg import Vec3
from .curve import Curve


def _find_span(n: int, degree: int, u: float, knots: List[float]) -> int:
    """Return knot span index."""
    if u >= knots[n + 1]:
        return n
    if u <= knots[degree]:
        return degree
    low = degree
    high = n + 1
    mid = (low + high) // 2
    while u < knots[mid] or u >= knots[mid + 1]:
        if u < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def _basis_functions(span: int, u: float, degree: int, knots: List[float]) -> List[float]:
    """Calculate B-spline basis functions."""
    N = [0.0] * (degree + 1)
    left = [0.0] * (degree + 1)
    right = [0.0] * (degree + 1)

    N[0] = 1.0
    for j in range(1, degree + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            temp = N[r] / (right[r + 1] + left[j - r])
            N[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        N[j] = saved
    return N


@dataclass
class BSplineCurve(Curve):
    control_points: List[Vec3]
    degree: int
    knots: List[float]

    def evaluate(self, u: float) -> Vec3:
        """Evaluate the B-spline curve at parameter u using the de Boor algorithm."""
        n = len(self.control_points) - 1
        span = _find_span(n, self.degree, u, self.knots)
        N = _basis_functions(span, u, self.degree, self.knots)
        point = Vec3(0.0, 0.0, 0.0)
        for i in range(self.degree + 1):
            point += self.control_points[span - self.degree + i] * N[i]
        return point

    def derivative(self, u: float) -> Vec3:
        """Compute the first derivative of the B-spline curve at parameter u."""
        n = len(self.control_points) - 1
        p = self.degree
        if p == 0:
            return Vec3(0.0, 0.0, 0.0)

        span = _find_span(n, p, u, self.knots)
        ders_ctrl = [Vec3(0.0, 0.0, 0.0) for _ in range(p)]
        for i in range(p):
            denom = self.knots[span + i + 1] - self.knots[span - p + i + 1]
            coef = p / denom if denom != 0 else 0.0
            ders_ctrl[i] = (self.control_points[span - p + i + 1] - self.control_points[span - p + i]) * coef

        ders_curve = BSplineCurve(ders_ctrl, p - 1, self.knots[1:-1])
        return ders_curve.evaluate(u)
