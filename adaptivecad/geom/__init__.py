"""Geometry utilities for AdaptiveCAD."""

from .bezier import BezierCurve
from .brep import Edge, EulerBRep, Face, Solid, Vertex
from .bspline import BSplineCurve
from .curve import Curve
from .hyperbolic import full_turn_deg, pi_a_over_pi, rotate_cmd

__all__ = [
    "BezierCurve",
    "BSplineCurve",
    "Curve",
    "full_turn_deg",
    "rotate_cmd",
    "pi_a_over_pi",
    "EulerBRep",
    "Vertex",
    "Edge",
    "Face",
    "Solid",
]
from .hyperbolic import HyperbolicConstraint as HyperbolicConstraint
from .hyperbolic import geodesic_distance as geodesic_distance
from .hyperbolic import move_towards as move_towards

__all__.extend(
    [
        "geodesic_distance",
        "move_towards",
        "HyperbolicConstraint",
    ]
)
