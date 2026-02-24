"""Simple sketch solver using Gauss-Newton least-squares."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class Vec2:
    x: float
    y: float


class Constraint:
    """Base constraint class."""

    def residual(self, x: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        raise NotImplementedError


@dataclass
class FixedConstraint(Constraint):
    idx: int
    target: Vec2

    def residual(self, x: np.ndarray) -> np.ndarray:
        return np.array(
            [
                x[2 * self.idx] - self.target.x,
                x[2 * self.idx + 1] - self.target.y,
            ]
        )

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        J = np.zeros((2, n))
        J[0, 2 * self.idx] = 1.0
        J[1, 2 * self.idx + 1] = 1.0
        return J


@dataclass
class DistanceConstraint(Constraint):
    idx1: int
    idx2: int
    distance: float

    def residual(self, x: np.ndarray) -> np.ndarray:
        xi, yi = x[2 * self.idx1], x[2 * self.idx1 + 1]
        xj, yj = x[2 * self.idx2], x[2 * self.idx2 + 1]
        d = math.hypot(xi - xj, yi - yj)
        return np.array([d - self.distance])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        xi, yi = x[2 * self.idx1], x[2 * self.idx1 + 1]
        xj, yj = x[2 * self.idx2], x[2 * self.idx2 + 1]
        dx = xi - xj
        dy = yi - yj
        dist = math.hypot(dx, dy)
        n = len(x)
        J = np.zeros((1, n))
        if dist == 0:
            return J
        J[0, 2 * self.idx1] = dx / dist
        J[0, 2 * self.idx1 + 1] = dy / dist
        J[0, 2 * self.idx2] = -dx / dist
        J[0, 2 * self.idx2 + 1] = -dy / dist
        return J


@dataclass
class CoincidentConstraint(Constraint):
    idx1: int
    idx2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        xi, yi = x[2 * self.idx1], x[2 * self.idx1 + 1]
        xj, yj = x[2 * self.idx2], x[2 * self.idx2 + 1]
        return np.array([xi - xj, yi - yj])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        J = np.zeros((2, n))
        J[0, 2 * self.idx1] = 1.0
        J[0, 2 * self.idx2] = -1.0
        J[1, 2 * self.idx1 + 1] = 1.0
        J[1, 2 * self.idx2 + 1] = -1.0
        return J


@dataclass
class HorizontalConstraint(Constraint):
    idx1: int
    idx2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        yi = x[2 * self.idx1 + 1]
        yj = x[2 * self.idx2 + 1]
        return np.array([yi - yj])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        J = np.zeros((1, n))
        J[0, 2 * self.idx1 + 1] = 1.0
        J[0, 2 * self.idx2 + 1] = -1.0
        return J


@dataclass
class VerticalConstraint(Constraint):
    idx1: int
    idx2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        xi = x[2 * self.idx1]
        xj = x[2 * self.idx2]
        return np.array([xi - xj])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        J = np.zeros((1, n))
        J[0, 2 * self.idx1] = 1.0
        J[0, 2 * self.idx2] = -1.0
        return J


@dataclass
class ParallelConstraint(Constraint):
    a1: int
    a2: int
    b1: int
    b2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x4, y3 - y4
        return np.array([dx1 * dy2 - dy1 * dx2])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x4, y3 - y4
        n = len(x)
        J = np.zeros((1, n))
        J[0, 2 * self.a1] = dy2
        J[0, 2 * self.a2] = -dy2
        J[0, 2 * self.a1 + 1] = -dx2
        J[0, 2 * self.a2 + 1] = dx2
        J[0, 2 * self.b1] = -dy1
        J[0, 2 * self.b2] = dy1
        J[0, 2 * self.b1 + 1] = dx1
        J[0, 2 * self.b2 + 1] = -dx1
        return J


@dataclass
class PerpendicularConstraint(Constraint):
    a1: int
    a2: int
    b1: int
    b2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x4, y3 - y4
        return np.array([dx1 * dx2 + dy1 * dy2])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x4, y3 - y4
        n = len(x)
        J = np.zeros((1, n))
        J[0, 2 * self.a1] = dx2
        J[0, 2 * self.a2] = -dx2
        J[0, 2 * self.a1 + 1] = dy2
        J[0, 2 * self.a2 + 1] = -dy2
        J[0, 2 * self.b1] = dx1
        J[0, 2 * self.b2] = -dx1
        J[0, 2 * self.b1 + 1] = dy1
        J[0, 2 * self.b2 + 1] = -dy1
        return J


@dataclass
class EqualLengthConstraint(Constraint):
    a1: int
    a2: int
    b1: int
    b2: int

    def residual(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        d1 = math.hypot(x1 - x2, y1 - y2)
        d2 = math.hypot(x3 - x4, y3 - y4)
        return np.array([d1 - d2])

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        x1, y1 = x[2 * self.a1], x[2 * self.a1 + 1]
        x2, y2 = x[2 * self.a2], x[2 * self.a2 + 1]
        x3, y3 = x[2 * self.b1], x[2 * self.b1 + 1]
        x4, y4 = x[2 * self.b2], x[2 * self.b2 + 1]
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x4, y3 - y4
        d1 = math.hypot(dx1, dy1)
        d2 = math.hypot(dx2, dy2)
        n = len(x)
        J = np.zeros((1, n))
        if d1 > 1e-12:
            J[0, 2 * self.a1] = dx1 / d1
            J[0, 2 * self.a2] = -dx1 / d1
            J[0, 2 * self.a1 + 1] = dy1 / d1
            J[0, 2 * self.a2 + 1] = -dy1 / d1
        if d2 > 1e-12:
            J[0, 2 * self.b1] = -dx2 / d2
            J[0, 2 * self.b2] = dx2 / d2
            J[0, 2 * self.b1 + 1] = -dy2 / d2
            J[0, 2 * self.b2 + 1] = dy2 / d2
        return J


class Sketch:
    def __init__(self) -> None:
        self.points: List[Vec2] = []
        self.constraints: List[Constraint] = []

    def add_point(self, x: float, y: float) -> int:
        self.points.append(Vec2(x, y))
        return len(self.points) - 1

    def add_constraint(self, cons: Constraint) -> None:
        self.constraints.append(cons)

    def solve_least_squares(self, iterations: int = 10, tol: float = 1e-9) -> None:
        if not self.points:
            return
        x = np.array([c for p in self.points for c in (p.x, p.y)], dtype=float)
        for _ in range(iterations):
            residuals = []
            jacs = []
            for cons in self.constraints:
                residuals.append(cons.residual(x))
                jacs.append(cons.jacobian(x))
            r = np.concatenate(residuals) if residuals else np.zeros(0)
            J = np.vstack(jacs) if jacs else np.zeros((0, len(x)))
            if J.size == 0:
                break
            dx, *_ = np.linalg.lstsq(J, -r, rcond=None)
            x += dx
            if np.linalg.norm(dx) < tol:
                break
        for i, p in enumerate(self.points):
            p.x, p.y = float(x[2 * i]), float(x[2 * i + 1])

    def solve(self, iterations: int = 10, tol: float = 1e-9) -> None:
        """Alias for :meth:`solve_least_squares`."""
        return self.solve_least_squares(iterations=iterations, tol=tol)


def export_dxf(sketch: Sketch, path: str) -> None:
    """Export sketch points and distance constraints to a minimal DXF."""
    with open(path, "w") as f:
        f.write("0\nSECTION\n2\nENTITIES\n")
        for cons in sketch.constraints:
            if isinstance(cons, DistanceConstraint):
                p1 = sketch.points[cons.idx1]
                p2 = sketch.points[cons.idx2]
                f.write(
                    "0\nLINE\n8\n0\n10\n{:.6f}\n20\n{:.6f}\n11\n{:.6f}\n21\n{:.6f}\n".format(
                        p1.x, p1.y, p2.x, p2.y
                    )
                )
        for p in sketch.points:
            f.write("0\nPOINT\n8\n0\n10\n{:.6f}\n20\n{:.6f}\n30\n0.0\n".format(p.x, p.y))
        f.write("0\nENDSEC\n0\nEOF\n")


__all__ = [
    "Vec2",
    "Sketch",
    "FixedConstraint",
    "DistanceConstraint",
    "CoincidentConstraint",
    "HorizontalConstraint",
    "VerticalConstraint",
    "ParallelConstraint",
    "PerpendicularConstraint",
    "EqualLengthConstraint",
    "export_dxf",
]
