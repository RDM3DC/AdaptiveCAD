"""Analytic B-rep slicing helpers."""
from __future__ import annotations

from typing import Any


def slice_brep_for_layer(shape: Any, z: float):
    """Return the intersection of ``shape`` with a horizontal plane.

    Parameters
    ----------
    shape:
        ``TopoDS_Shape`` instance to slice.
    z:
        Height of the slicing plane in model units.

    Returns
    -------
    Any
        The intersection edges as a ``TopoDS_Shape``.

    Notes
    -----
    This function requires ``pythonocc-core``. If the package is not
    installed, :class:`ImportError` is raised when the function is called.
    """
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCC.Core.gp import gp_Pln, gp_Ax3, gp_Dir, gp_Pnt
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("pythonocc-core is required for analytic slicing") from exc

    plane = gp_Pln(gp_Ax3(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)))
    section = BRepAlgoAPI_Section(shape, plane)
    section.ComputePCurveOn1(True)
    section.Approximation(True)
    section.Build()
    return section.Shape()


__all__ = ["slice_brep_for_layer"]
