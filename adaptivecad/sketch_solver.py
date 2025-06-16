"""Simple sketch solver using Gauss-Newton least-squares."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import math
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
        return np.array([
            x[2 * self.idx] - self.target.x,
            x[2 * self.idx + 1] - self.target.y,
        ])

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
            f.write(
                "0\nPOINT\n8\n0\n10\n{:.6f}\n20\n{:.6f}\n30\n0.0\n".format(p.x, p.y)
            )
        f.write("0\nENDSEC\n0\nEOF\n")


__all__ = [
    "Vec2",
    "Sketch",
    "FixedConstraint",
    "DistanceConstraint",
    "export_dxf",
]
