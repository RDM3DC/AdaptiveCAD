"""Bezier curve utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..linalg import Vec3


@dataclass
class BezierCurve:
    control_points: List[Vec3]

    def evaluate(self, u: float) -> Vec3:
        """Evaluate the curve at parameter u using de Casteljau."""
        points = self.control_points
        n = len(points)
        tmp = [p for p in points]
        for r in range(1, n):
            for i in range(n - r):
                tmp[i] = tmp[i] * (1 - u) + tmp[i + 1] * u
        return tmp[0]

    def subdivide(self, u: float) -> tuple["BezierCurve", "BezierCurve"]:
        """Subdivide the curve into two at parameter u."""
        points = self.control_points
        n = len(points)
        left = []
        right = []
        tmp = [p for p in points]
        left.append(tmp[0])
        right.append(tmp[-1])
        for r in range(1, n):
            for i in range(n - r):
                tmp[i] = tmp[i] * (1 - u) + tmp[i + 1] * u
            left.append(tmp[0])
            right.append(tmp[n - r - 1])
        right.reverse()
        return BezierCurve(left), BezierCurve(right)
