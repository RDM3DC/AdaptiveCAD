from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from adaptivecad.pi.kernel import PiAParams, make_polar_adaptive_circle


def pi_circle_points(
    radius: float, cx: float = 0.0, cy: float = 0.0, segments: int = 256
) -> List[Tuple[float, float]]:
    """Sample a circle into evenly spaced points (carrying pi_a semantics elsewhere)."""
    pts: List[Tuple[float, float]] = []
    for i in range(segments):
        t = (2.0 * math.pi) * (i / segments)
        x = cx + radius * math.cos(t)
        y = cy + radius * math.sin(t)
        pts.append((x, y))
    return pts


def make_pi_circle_profile(
    radius: float,
    cx: float = 0.0,
    cy: float = 0.0,
    segments: int = 256,
) -> Dict[str, Any]:
    """Build a profile dict flagged as pi_a superellipse representing a circle."""
    return {
        "type": "profile",
        "family": "pi_a:superellipse",
        "params": {"a": radius, "b": radius, "n": 2.0, "cx": cx, "cy": cy},
        "metric": "pi_a",
        "closed": True,
        "points": pi_circle_points(radius, cx, cy, segments),
    }


def polar_pi_circle_points(
    radius: float,
    cx: float = 0.0,
    cy: float = 0.0,
    segments: int = 256,
    *,
    kappa: float = 0.0,
    scale: float | None = None,
    params: PiAParams | None = None,
    angular_amplitude: float = 0.3,
    angular_frequency: int = 3,
    phase: float = 0.0,
) -> List[Tuple[float, float]]:
    """Sample a polar adaptive π circle into points for sketch/profile consumers."""

    params = params or PiAParams()
    pts = make_polar_adaptive_circle(
        radius,
        n=int(segments),
        kappa=float(kappa),
        scale=float(radius if scale is None else scale),
        params=params,
        angular_amplitude=float(angular_amplitude),
        angular_frequency=int(angular_frequency),
        phase=float(phase),
    )
    return [(float(cx + x), float(cy + y)) for x, y in pts]


def make_polar_pi_circle_profile(
    radius: float,
    cx: float = 0.0,
    cy: float = 0.0,
    segments: int = 256,
    *,
    kappa: float = 0.0,
    scale: float | None = None,
    params: PiAParams | None = None,
    angular_amplitude: float = 0.3,
    angular_frequency: int = 3,
    phase: float = 0.0,
) -> Dict[str, Any]:
    """Build a profile dict for a polar-adaptive π shape.

    This is a first-class analytic profile rather than a generic circle tagged with
    pi_a metadata, so downstream tools can distinguish a warped boundary from a
    uniform metric circle.
    """

    params = params or PiAParams()
    resolved_scale = float(radius if scale is None else scale)
    return {
        "type": "profile",
        "family": "pi_a:polar_circle",
        "params": {
            "radius": radius,
            "cx": cx,
            "cy": cy,
            "kappa": kappa,
            "scale": resolved_scale,
            "beta": params.beta,
            "s0": params.s0,
            "clamp": params.clamp,
            "angular_amplitude": angular_amplitude,
            "angular_frequency": angular_frequency,
            "phase": phase,
        },
        "metric": "pi_a",
        "closed": True,
        "points": polar_pi_circle_points(
            radius,
            cx,
            cy,
            segments,
            kappa=kappa,
            scale=resolved_scale,
            params=params,
            angular_amplitude=angular_amplitude,
            angular_frequency=angular_frequency,
            phase=phase,
        ),
    }


def upgrade_profile_meta_to_pia(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *profile* with pi_a metric metadata applied (idempotent)."""
    upgraded = dict(profile)
    upgraded["metric"] = "pi_a"
    upgraded.setdefault("family", "pi_a:generic")
    return upgraded
