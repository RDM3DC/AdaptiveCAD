"""Hyperbolic geometry utilities.

This module provides simple helpers for working with negative curvature
(\kappa < 0) scenarios, as referenced in the repository README.  The
functions implement the formulas for "adaptive" angle budgeting in a
hyperbolic workspace.
"""

from __future__ import annotations

import math

PI_E = math.pi


def full_turn_deg(r: float, kappa: float) -> float:
    """Return degrees in one revolution at hyperbolic radius ``r``.

    Parameters
    ----------
    r:
        Geodesic radius from the origin.
    kappa:
        Curvature radius of the workspace (|kappa| > 0).

    Returns
    -------
    float
        Number of Euclidean degrees corresponding to 2\pi_a at ``r``.
    """
    return 360.0 * kappa * math.sinh(r / kappa) / r


def rotate_cmd(delta_deg_a: float, r: float, kappa: float) -> float:
    """Convert a rotation request in adaptive degrees to Euclidean radians."""
    d_full = full_turn_deg(r, kappa)
    frac = delta_deg_a / d_full
    return frac * 2 * math.pi


def pi_a_over_pi(r: float, kappa: float) -> float:
    """Return the ratio \pi_a/\pi at radius ``r``."""
    if r == 0:
        return 1.0
    return (kappa * math.sinh(r / kappa)) / r


def geodesic_distance(
    p1: tuple[float, float, float], p2: tuple[float, float, float], kappa: float
) -> float:
    """Return the πₐ geodesic distance between ``p1`` and ``p2``."""
    r1 = math.sqrt(p1[0] ** 2 + p1[1] ** 2 + p1[2] ** 2)
    r2 = math.sqrt(p2[0] ** 2 + p2[1] ** 2 + p2[2] ** 2)
    if r1 == 0:
        return r2
    if r2 == 0:
        return r1
    dot = p1[0] * p2[0] + p1[1] * p2[1] + p1[2] * p2[2]
    cos_theta = max(min(dot / (r1 * r2), 1.0), -1.0)
    cosh_val = (
        math.cosh(r1 / kappa) * math.cosh(r2 / kappa)
        - math.sinh(r1 / kappa) * math.sinh(r2 / kappa) * cos_theta
    )
    cosh_val = max(cosh_val, 1.0)
    return kappa * math.acosh(cosh_val)


def move_towards(
    p: tuple[float, float, float],
    target: tuple[float, float, float],
    kappa: float,
    step: float,
) -> tuple[float, float, float]:
    """Move ``p`` towards ``target`` along the hyperbolic geodesic by ``step``."""
    dist = geodesic_distance(p, target, kappa)
    if dist == 0 or step <= 0:
        return p
    frac = min(step / dist, 1.0)
    return (
        p[0] + frac * (target[0] - p[0]),
        p[1] + frac * (target[1] - p[1]),
        p[2] + frac * (target[2] - p[2]),
    )


class HyperbolicConstraint:
    """Constraint that drags a point toward a target using the πₐ metric."""

    def __init__(self, target: tuple[float, float, float], kappa: float):
        self.target = target
        self.kappa = kappa

    def update(
        self, point: tuple[float, float, float], step: float = 0.1
    ) -> tuple[float, float, float]:
        return move_towards(point, self.target, self.kappa, step)
