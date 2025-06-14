"""B-spline curve utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..linalg import Vec3


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


@dataclass
class BSplineCurve:
    control_points: List[Vec3]
    degree: int
    knots: List[float]

    def evaluate(self, u: float) -> Vec3:
        """Evaluate the B-spline curve at parameter u using the de Boor algorithm."""
        n = len(self.control_points) - 1
        k = _find_span(n, self.degree, u, self.knots)
        d = [self.control_points[j] for j in range(k - self.degree, k + 1)]
        for r in range(1, self.degree + 1):
            for j in range(self.degree, r - 1, -1):
                i = k - self.degree + j
                denom = self.knots[i + self.degree + 1 - r] - self.knots[i]
                if denom == 0:
                    alpha = 0.0
                else:
                    alpha = (u - self.knots[i]) / denom
                d[j] = (1 - alpha) * d[j - 1] + alpha * d[j]
        return d[self.degree]
