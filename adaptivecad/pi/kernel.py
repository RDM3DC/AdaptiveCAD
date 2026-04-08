"""
AdaptiveCAD πₐ kernel
- Single source of truth for Adaptive-π (πₐ) geometry across plugins and tools.
- Treat πₐ as a slowly varying function of local curvature and scale.

Public API:
- PiAParams: dataclass with (beta, s0, clamp)
- pi_a(kappa, scale, params) -> float
- adaptive_arc_length(radius, angle_rad, kappa, scale, params) -> float
- make_adaptive_circle(radius, n, kappa, scale, params) -> np.ndarray[(n,2)]
- polar_pi_a(theta, kappa, scale, params, angular_amplitude, angular_frequency, phase) -> float
- make_polar_adaptive_circle(...) -> np.ndarray[(n,2)]
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

__all__ = [
    "PiAParams",
    "pi_a",
    "polar_pi_a",
    "adaptive_arc_length",
    "make_adaptive_circle",
    "make_polar_adaptive_circle",
    "__version__",
]
__version__ = "0.1.0"


@dataclass
class PiAParams:
    """
    Parameters for an example πₐ model.
    beta: curvature sensitivity
    s0:   reference scale (meters) separating macro/micro regimes
    clamp: max fractional deviation from π (>=0), keeps model bounded
    """

    beta: float = 0.2
    s0: float = 1.0
    clamp: float = 0.3


def _clamp(x: float, lo: float, hi: float) -> float:
    return hi if x > hi else lo if x < lo else x


def pi_a(kappa: float, scale: float = 1.0, params: PiAParams = PiAParams()) -> float:
    """
    Adaptive π model (baseline exemplar):
        πₐ = π * (1 + beta * (kappa * scale / s0)^2), clamped to ±clamp.
    - kappa: curvature [1/m]
    - scale: characteristic length [m]
    """
    base = math.pi
    s0 = max(params.s0, 1e-9)
    frac = params.beta * (kappa * (scale / s0)) ** 2
    frac = _clamp(frac, -params.clamp, params.clamp)
    return base * (1.0 + frac)


def adaptive_arc_length(
    radius: float, angle_rad: float, kappa: float, scale: float, params: PiAParams = PiAParams()
) -> float:
    """Arc length with πₐ scaling: for small angles, L = angle * r; we modulate by πₐ/π."""
    pa = pi_a(kappa, scale, params)
    return float(angle_rad * radius * (pa / math.pi))


def polar_pi_a(
    theta: float | Iterable[float] | np.ndarray,
    kappa: float = 0.0,
    scale: float = 1.0,
    params: PiAParams = PiAParams(),
    *,
    angular_amplitude: float = 0.3,
    angular_frequency: int = 3,
    phase: float = 0.0,
) -> float | np.ndarray:
    """Return a position-dependent πₐ field sampled over polar angle.

    The baseline AdaptiveCAD πₐ model is still the core driver. This helper adds
    a bounded angular modulation so a circular primitive can warp analytically in
    polar coordinates instead of only applying one uniform global scale.
    """

    base = pi_a(kappa, scale, params)
    theta_arr = np.asarray(theta, dtype=float)
    amp = _clamp(float(angular_amplitude), -0.95, 0.95)
    freq = max(1, int(angular_frequency))
    modulation = 1.0 + amp * np.sin(freq * theta_arr + float(phase))
    modulation = np.clip(modulation, 0.05, None)
    values = base * modulation
    if np.isscalar(theta) or theta_arr.ndim == 0:
        return float(values)
    return values


def make_adaptive_circle(
    radius: float,
    n: int = 128,
    kappa: float = 0.0,
    scale: float = 1.0,
    params: PiAParams = PiAParams(),
) -> np.ndarray:
    """
    Generate a polyline approximating a circle with adaptive π scaling (uniform over the loop).
    Returns Nx2 numpy array in meters.
    """
    pts = np.zeros((n, 2), dtype=float)
    pa = pi_a(kappa, scale, params)
    # scale the full angle 2π by pa/π so circumference stretches/shrinks coherently
    total_angle = 2.0 * math.pi * (pa / math.pi)
    for i in range(n):
        theta = total_angle * (i / float(n))
        pts[i, 0] = radius * math.cos(theta)
        pts[i, 1] = radius * math.sin(theta)
    return pts


def make_polar_adaptive_circle(
    radius: float,
    n: int = 128,
    kappa: float = 0.0,
    scale: float = 1.0,
    params: PiAParams = PiAParams(),
    *,
    angular_amplitude: float = 0.3,
    angular_frequency: int = 3,
    phase: float = 0.0,
) -> np.ndarray:
    """Generate a closed 2D profile whose local radius is driven by a polar πₐ field.

    We interpret the adaptive π field as a local radius multiplier:

        r(θ) = R * πₐ(θ) / π

    When angular_amplitude is zero, the result collapses to the existing uniform
    πₐ circle semantics while still keeping one sample per requested segment.
    """

    theta = np.linspace(0.0, 2.0 * math.pi, int(n), endpoint=False)
    local_pi = polar_pi_a(
        theta,
        kappa=kappa,
        scale=scale,
        params=params,
        angular_amplitude=angular_amplitude,
        angular_frequency=angular_frequency,
        phase=phase,
    )
    local_radius = float(radius) * (np.asarray(local_pi, dtype=float) / math.pi)
    pts = np.column_stack([local_radius * np.cos(theta), local_radius * np.sin(theta)])
    return pts.astype(float, copy=False)
