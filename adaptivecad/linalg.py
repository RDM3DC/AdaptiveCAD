"""Basic linear algebra utilities for AdaptiveCAD.

This module includes simple classes for vectors, 4x4 affine matrices and
quaternions. It is intentionally lightweight so early parts of the
project can depend on it without external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List
import numpy as np


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def norm(self) -> float:
        return math.sqrt(self.dot(self))


class Matrix4:
    """Simple column-major 4x4 matrix."""

    def __init__(self, columns: Iterable[Iterable[float]] | None = None) -> None:
        if columns is None:
            # identity
            self.m = [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        else:
            self.m = [list(col) for col in columns]
            if len(self.m) != 4 or any(len(c) != 4 for c in self.m):
                raise ValueError("Matrix4 expects 4x4 values")

    def __matmul__(self, other: "Matrix4") -> "Matrix4":
        result = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                result[i][j] = sum(self.m[i][k] * other.m[k][j] for k in range(4))
        return Matrix4(result)

    def transform_point(self, p: Vec3) -> Vec3:
        x = self.m[0][0] * p.x + self.m[0][1] * p.y + self.m[0][2] * p.z + self.m[0][3]
        y = self.m[1][0] * p.x + self.m[1][1] * p.y + self.m[1][2] * p.z + self.m[1][3]
        z = self.m[2][0] * p.x + self.m[2][1] * p.y + self.m[2][2] * p.z + self.m[2][3]
        w = self.m[3][0] * p.x + self.m[3][1] * p.y + self.m[3][2] * p.z + self.m[3][3]
        if w != 0 and w != 1:
            return Vec3(x / w, y / w, z / w)
        return Vec3(x, y, z)


@dataclass
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    @staticmethod
    def from_axis_angle(axis: Vec3, angle_rad: float) -> "Quaternion":
        half = angle_rad / 2.0
        s = math.sin(half)
        return Quaternion(math.cos(half), axis.x * s, axis.y * s, axis.z * s)

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def __mul__(self, other: "Quaternion") -> "Quaternion":
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = other.w, other.x, other.y, other.z
        return Quaternion(
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        )

    def rotate(self, v: Vec3) -> Vec3:
        qv = Quaternion(0, v.x, v.y, v.z)
        qres = self * qv * self.conjugate()
        return Vec3(qres.x, qres.y, qres.z)


def polar_decompose(m: Matrix4) -> tuple[Matrix4, Matrix4]:
    """Return rotation and stretch matrices via polar decomposition."""
    # Only uses upper-left 3x3 part.
    import numpy as np

    R = np.array([[m.m[i][j] for j in range(3)] for i in range(3)], dtype=float)
    S = (R.T @ R) ** 0.5
    S_inv = np.linalg.inv(S)
    R = R @ S_inv

    rot = Matrix4([list(R[i]) + [0.0] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]])
    stretch = Matrix4([list(S[i]) + [0.0] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]])
    return rot, stretch


class VecN:
    """Simple N-dimensional vector built on NumPy arrays."""

    def __init__(self, coords: Iterable[float]):
        self.coords = np.asarray(list(coords), dtype=float)

    def __repr__(self) -> str:
        return f"VecN({self.coords.tolist()})"

    def __len__(self) -> int:
        return int(self.coords.size)

    def __iter__(self):
        return iter(self.coords)

    def __add__(self, other: "VecN") -> "VecN":
        if self.coords.size != other.coords.size:
            raise ValueError("Dimension mismatch")
        return VecN(self.coords + other.coords)

    def __sub__(self, other: "VecN") -> "VecN":
        if self.coords.size != other.coords.size:
            raise ValueError("Dimension mismatch")
        return VecN(self.coords - other.coords)

    def __mul__(self, scalar: float) -> "VecN":
        return VecN(self.coords * scalar)

    __rmul__ = __mul__

    def dot(self, other: "VecN") -> float:
        if self.coords.size != other.coords.size:
            raise ValueError("Dimension mismatch")
        return float(np.dot(self.coords, other.coords))

    def norm(self) -> float:
        return float(np.linalg.norm(self.coords))

    def dist(self, other: "VecN") -> float:
        if self.coords.size != other.coords.size:
            raise ValueError("Dimension mismatch")
        return float(np.linalg.norm(self.coords - other.coords))

    def dim(self) -> int:
        return int(self.coords.size)
