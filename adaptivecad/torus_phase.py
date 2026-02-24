"""Phase-aware torus utilities.

This module is intentionally lightweight and dependency-minimal (numpy only).
It provides:
- Branch-safe wrapping/unwrapping for angles (S^1)
- Winding counters (S^1 lift to R)
- Simple Z2 parity tracking for branch-cut crossings
- A CAM-friendly path representation on T^2 = S^1 x S^1

The goal is to make "torus-native" workflows (unwrap → optimize → rewrap)
first-class, without tying this to any particular UI or backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Literal, Tuple

import numpy as np

PhaseSpace = Literal["wrapped", "unwrapped"]

__all__ = [
    "wrap_to_pi",
    "wrap_to_2pi",
    "unwrap_1d",
    "unwrap_2d",
    "WindingCounter1D",
    "WindingCounter2D",
    "ParityTracker",
    "TorusPath",
    "torus_embed_xyz",
]


TAU = 2.0 * math.pi


def wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    """Map angles to (-pi, pi] elementwise."""

    if isinstance(angle, (float, int)):
        return (float(angle) + math.pi) % TAU - math.pi
    arr = np.asarray(angle, dtype=float)
    return (arr + math.pi) % TAU - math.pi


def wrap_to_2pi(angle: np.ndarray | float) -> np.ndarray | float:
    """Map angles to [0, 2pi) elementwise."""

    if isinstance(angle, (float, int)):
        return float(angle) % TAU
    arr = np.asarray(angle, dtype=float)
    return arr % TAU


def unwrap_1d(angles_wrapped: Iterable[float] | np.ndarray, *, start: float | None = None) -> np.ndarray:
    """Unwrap a wrapped angle sequence into a continuous lifted sequence.

    Args:
        angles_wrapped: Sequence of angles, assumed equivalent modulo 2π.
        start: Optional starting unwrapped value. If provided, the sequence is
            lifted to start near this value.

    Returns:
        Unwrapped angles (same length) as float64 numpy array.
    """

    a = np.asarray(list(angles_wrapped), dtype=float)
    if a.size == 0:
        return a.astype(np.float64)

    out = np.empty_like(a, dtype=np.float64)
    out[0] = float(a[0])

    if start is not None:
        # Lift the first sample near `start`.
        k = round((float(start) - out[0]) / TAU)
        out[0] = out[0] + k * TAU

    for i in range(1, a.size):
        raw_delta = float(a[i] - a[i - 1])
        delta = float(wrap_to_pi(raw_delta))
        out[i] = out[i - 1] + delta

    return out


def unwrap_2d(theta_phi_wrapped: np.ndarray, *, start: Tuple[float, float] | None = None) -> np.ndarray:
    """Unwrap a T^2 sequence (theta, phi) into R^2, branch-safe.

    Args:
        theta_phi_wrapped: (N,2) array of wrapped angles.
        start: Optional starting unwrapped (theta, phi).

    Returns:
        (N,2) unwrapped array.
    """

    tp = np.asarray(theta_phi_wrapped, dtype=float)
    if tp.ndim != 2 or tp.shape[1] != 2:
        raise ValueError("theta_phi_wrapped must have shape (N,2)")

    th0 = None if start is None else float(start[0])
    ph0 = None if start is None else float(start[1])
    th = unwrap_1d(tp[:, 0], start=th0)
    ph = unwrap_1d(tp[:, 1], start=ph0)
    return np.column_stack([th, ph]).astype(np.float64)


@dataclass
class WindingCounter1D:
    """Track winding on S^1 as samples stream in."""

    last_unwrapped: float | None = None
    winding: int = 0

    def update(self, angle_wrapped: float) -> float:
        """Feed next wrapped sample; returns the unwrapped value."""

        a = float(angle_wrapped)
        if self.last_unwrapped is None:
            self.last_unwrapped = a
            self.winding = 0
            return self.last_unwrapped

        prev_wrapped = wrap_to_pi(self.last_unwrapped)
        raw_delta = a - float(prev_wrapped)
        delta = float(wrap_to_pi(raw_delta))
        unwrapped = float(self.last_unwrapped + delta)

        # Count winding by looking at total turns relative to principal value.
        self.winding = int(round(unwrapped / TAU))
        self.last_unwrapped = unwrapped
        return unwrapped


@dataclass
class WindingCounter2D:
    """Track winding on T^2 as samples stream in."""

    theta: WindingCounter1D = field(default_factory=WindingCounter1D)
    phi: WindingCounter1D = field(default_factory=WindingCounter1D)

    def update(self, theta_wrapped: float, phi_wrapped: float) -> Tuple[float, float]:
        th = self.theta.update(theta_wrapped)
        ph = self.phi.update(phi_wrapped)
        return th, ph

    @property
    def winding_theta(self) -> int:
        return int(self.theta.winding)

    @property
    def winding_phi(self) -> int:
        return int(self.phi.winding)


@dataclass
class ParityTracker:
    """Z2 parity for branch-cut crossings.

    This is a simple, robust proxy: we toggle parity when an unwrap step
    requires adding/subtracting a 2π jump (i.e., when raw delta differs from the
    principal-branch delta).

    Interpretation: parity=0 means "no odd number of branch crossings so far",
    parity=1 means "odd number".
    """

    last_wrapped: float | None = None
    parity: int = 0

    def update(self, angle_wrapped: float) -> int:
        a = float(angle_wrapped)
        if self.last_wrapped is None:
            self.last_wrapped = a
            self.parity = 0
            return self.parity

        raw_delta = a - float(self.last_wrapped)
        delta = float(wrap_to_pi(raw_delta))
        jump = raw_delta - delta
        # jump should be near k*2π. Toggle if k is odd.
        k = int(round(jump / TAU))
        if (k % 2) != 0:
            self.parity ^= 1
        self.last_wrapped = a
        return self.parity


def torus_embed_xyz(
    theta: np.ndarray | float,
    phi: np.ndarray | float,
    *,
    R: float,
    r: float,
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> np.ndarray:
    """Embed torus angles (theta, phi) into 3D (Z-axis torus).

    Standard embedding:
        x = (R + r cos(phi)) cos(theta)
        y = (R + r cos(phi)) sin(theta)
        z = r sin(phi)

    Args:
        theta: longitudinal angle.
        phi: meridional angle.
        R: major radius.
        r: minor radius.
        center: translation.

    Returns:
        (...,3) array of xyz.
    """

    th = np.asarray(theta, dtype=float)
    ph = np.asarray(phi, dtype=float)
    # Broadcast.
    th, ph = np.broadcast_arrays(th, ph)

    cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    tube = R + r * np.cos(ph)
    x = tube * np.cos(th) + cx
    y = tube * np.sin(th) + cy
    z = r * np.sin(ph) + cz
    return np.stack([x, y, z], axis=-1).astype(np.float64)


@dataclass(frozen=True)
class TorusPath:
    """A path parameterized on a torus in angle coordinates.

    `angles` is stored as (N,2) where columns are (theta, phi).
    """

    angles: np.ndarray  # (N,2)
    phase_space: PhaseSpace = "wrapped"

    def __post_init__(self) -> None:
        arr = np.asarray(self.angles, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("angles must have shape (N,2)")
        object.__setattr__(self, "angles", arr.astype(np.float64))

    def unwrap(self, *, start: Tuple[float, float] | None = None) -> "TorusPath":
        if self.phase_space == "unwrapped":
            return self
        return TorusPath(unwrap_2d(self.angles, start=start), phase_space="unwrapped")

    def rewrap(self) -> "TorusPath":
        if self.phase_space == "wrapped":
            return self
        wrapped = np.column_stack([wrap_to_pi(self.angles[:, 0]), wrap_to_pi(self.angles[:, 1])])
        return TorusPath(wrapped, phase_space="wrapped")

    def windings(self) -> Tuple[int, int]:
        """Return integer windings (theta_w, phi_w) using endpoints."""

        unwrapped = self.unwrap().angles
        dth = float(unwrapped[-1, 0] - unwrapped[0, 0])
        dph = float(unwrapped[-1, 1] - unwrapped[0, 1])
        return int(round(dth / TAU)), int(round(dph / TAU))

    def interpolate(self, n: int) -> "TorusPath":
        """Phase-safe resampling by unwrapping then linear interpolation."""

        n = int(n)
        if n <= 1:
            raise ValueError("n must be >= 2")
        u = self.unwrap().angles
        t_old = np.linspace(0.0, 1.0, u.shape[0])
        t_new = np.linspace(0.0, 1.0, n)
        th = np.interp(t_new, t_old, u[:, 0])
        ph = np.interp(t_new, t_old, u[:, 1])
        return TorusPath(np.column_stack([th, ph]), phase_space="unwrapped").rewrap()

    def to_xyz(self, *, R: float, r: float, center: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> np.ndarray:
        a = self.angles
        return torus_embed_xyz(a[:, 0], a[:, 1], R=R, r=r, center=center)
