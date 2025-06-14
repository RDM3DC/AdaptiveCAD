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
