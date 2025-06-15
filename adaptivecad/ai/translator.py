"""Convert AI JSON specs into simple geometry objects."""

from __future__ import annotations

import sympy as sp
from dataclasses import dataclass
from typing import Any, Dict, List

from adaptivecad.geom.bspline import BSplineCurve
from adaptivecad.linalg import Vec3


class ImplicitSurface:
    """Minimal implicit surface placeholder."""

    def __init__(self, expression: str | sp.Expr, domain: Dict[str, List[float]], iso_level: float = 0.0) -> None:
        self.expression = sp.sympify(expression)
        self.domain = domain
        self.iso_level = iso_level

    def is_manifold(self) -> bool:  # pragma: no cover - placeholder
        return True


@dataclass
class ExtrudedSolid:
    profile: Any
    height: float

    def is_manifold(self) -> bool:  # pragma: no cover - placeholder
        return True


def build_geometry(spec: Dict[str, Any]) -> Any:
    """Build geometry object from JSON spec."""
    kind = spec.get("kind")
    prim = spec.get("primitive")
    params = spec.get("parameters", {})

    if kind == "curve" and prim == "bspline":
        cps = [Vec3(*pt) for pt in params["control_pts"]]
        degree = int(params.get("degree", 3))
        knots = params.get("knots")
        return BSplineCurve(cps, degree, knots)

    if kind == "surface" and prim == "implicit":
        eqn = params["equation"]
        domain = params.get("domain", {})
        iso_level = float(params.get("iso_level", 0.0))
        return ImplicitSurface(eqn, domain, iso_level)

    if kind == "solid" and prim == "extrude":
        profile = build_geometry(params["profile"])
        height = float(params["height"])
        return ExtrudedSolid(profile, height)

    raise ValueError(f"Unsupported spec {kind}/{prim}")
