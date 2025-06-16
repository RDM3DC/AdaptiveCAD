"""Geometry utilities for AdaptiveCAD."""

from .bezier import BezierCurve
from .bspline import BSplineCurve
from .hyperbolic import full_turn_deg, rotate_cmd, pi_a_over_pi
from .brep import EulerBRep, Vertex, Edge, Face, Solid

__all__ = [
    "BezierCurve",
    "BSplineCurve",
    "full_turn_deg",
    "rotate_cmd",
    "pi_a_over_pi",
    "EulerBRep",
    "Vertex",
    "Edge",
    "Face",
    "Solid",
]
from .hyperbolic import geodesic_distance, move_towards, HyperbolicConstraint

__all__.extend(
    [
        "geodesic_distance",
        "move_towards",
        "HyperbolicConstraint",
    ]
)
