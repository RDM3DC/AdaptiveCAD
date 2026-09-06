"""Optional AdaptiveCAD Bezier -> CadQuery/OCP bridge, without tessellation.

Importing this module does not import CadQuery. Install the separate example
requirements only when using these adapters; no change to the OCC GUI is needed.
Control-point transfer preserves the polynomial curve, subject to floating-point
and OpenCascade tolerances. It is not a zero-numerical-error claim.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .bezier import BezierCurve

if TYPE_CHECKING:
    import cadquery as cq


def _cq():
    try:
        import cadquery
    except ImportError as exc:
        raise ImportError(
            "This optional bridge requires CadQuery/OCP. In a separate environment, "
            "run: python -m pip install -r examples/arp_gt01/requirements.txt"
        ) from exc
    return cadquery


def _positive(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return value


def bezier_edge(curve: BezierCurve, *, tolerance: float = 1e-8) -> cq.Edge:
    """Transfer a finite, nonconstant Bezier curve's poles, not sampled vertices.

    Validation samples compare parameters (not arc-length fractions). They do not
    create a mesh or certify a global error bound. Stationary tangents are allowed.
    """
    tolerance = _positive(tolerance, "tolerance")
    points = list(curve.control_points)
    if len(points) < 2 or len(points) > 26:
        raise ValueError("OpenCascade Bezier curves require 2 to 26 control points")
    if not all(math.isfinite(v) for p in points for v in (p.x, p.y, p.z)):
        raise ValueError("Control points must contain finite coordinates")
    if all(p == points[0] for p in points[1:]):
        raise ValueError("A constant Bezier curve cannot define an edge")
    cq = _cq()
    edge = cq.Edge.makeBezier([cq.Vector(p.x, p.y, p.z) for p in points])
    if not edge.isValid():
        raise ValueError("OpenCascade rejected the Bezier edge")
    error = bezier_bridge_error(curve, edge)
    if error > tolerance:
        raise ValueError(f"Bezier bridge sample error {error:g} exceeds {tolerance:g}")
    return edge


def bezier_bridge_error(curve: BezierCurve, edge: cq.Edge, *, samples: int = 9) -> float:
    """Maximum sampled Euclidean error in the input coordinate units."""
    if not isinstance(samples, int) or isinstance(samples, bool) or samples < 2:
        raise ValueError("samples must be an integer of at least 2")
    error = 0.0
    for j in range(samples):
        t = j / (samples - 1)
        p = curve.evaluate(t)
        q = edge.positionAt(t, mode="parameter")
        error = max(error, math.dist((p.x, p.y, p.z), (q.x, q.y, q.z)))
    return error


def bezier_wire(
    curves: Iterable[BezierCurve], *, closed: bool = False, tolerance: float = 1e-8
) -> cq.Wire:
    """Assemble ordered Bezier spans; reject disconnected/incorrectly closed paths."""
    tolerance = _positive(tolerance, "tolerance")
    curves = list(curves)
    if not curves:
        raise ValueError("At least one Bezier span is required")
    edges = [bezier_edge(curve, tolerance=tolerance) for curve in curves]
    pairs = list(zip(curves, curves[1:]))
    if closed:
        pairs.append((curves[-1], curves[0]))
    for left, right in pairs:
        if (left.evaluate(1) - right.evaluate(0)).norm() > tolerance:
            raise ValueError("Bezier spans are not connected in the supplied order")
    wire = _cq().Wire.assembleEdges(edges)
    if not wire.isValid() or (closed and not wire.IsClosed()):
        raise ValueError("OpenCascade did not produce the requested valid wire")
    return wire


def triangulated_face_count(shape: cq.Shape) -> int:
    """Count faces with attached display triangulations, not geometric surfaces."""
    _cq()
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    return sum(
        BRep_Tool.Triangulation_s(face.wrapped, TopLoc_Location()) is not None
        for face in shape.Faces()
    )


def export_brep_clean(shape: cq.Shape, path: str | Path) -> Path:
    """Export a geometry copy with no stored mesh, leaving the source untouched."""
    cq = _cq()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepTools import BRepTools

    if not shape.isValid():
        raise ValueError("Cannot export an invalid B-rep")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy = cq.Shape.cast(BRepBuilderAPI_Copy(shape.wrapped, True, False).Shape())
    BRepTools.Clean_s(copy.wrapped)
    if triangulated_face_count(copy):
        raise RuntimeError("Display triangulations remain in the export copy")
    if not copy.exportBrep(str(destination)):
        raise OSError(f"BREP export failed: {destination}")
    return destination
