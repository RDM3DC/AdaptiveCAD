"""Utilities to export cross-section slices from AMA files."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

from .io.ama_reader import read_ama
from .analytic_slicer import slice_brep_for_layer

__all__ = ["export_slices_from_ama"]


def export_slices_from_ama(ama_path: str | os.PathLike, z_values: Iterable[float], out_dir: str | os.PathLike = "slices", fmt: str = "brep") -> list[Path]:
    """Export cross-section slices from an AMA file.

    Parameters
    ----------
    ama_path:
        Path to the AMA file to slice.
    z_values:
        Iterable of Z heights to slice at.
    out_dir:
        Directory where slice files are written.
    fmt:
        Output format: ``"brep"`` or ``"stl"``.

    Returns
    -------
    list[Path]
        List of paths to the generated slice files.

    Notes
    -----
    This function requires ``pythonocc-core`` for B-rep operations. If the
    dependency is missing, :class:`ImportError` will be raised.
    """
    try:
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepTools import breptools_Read, breptools_Write
        from OCC.Core.StlAPI import StlAPI_Writer
        from OCC.Core.TopoDS import TopoDS_Shape
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("pythonocc-core is required for slicing export") from exc

    ama = read_ama(str(ama_path))
    if not ama or not ama.parts:
        raise ValueError(f"No parts found in AMA file {ama_path}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[Path] = []

    for part in ama.parts:
        # Load BREP shape from bytes
        with tempfile.NamedTemporaryFile(suffix=".brep", delete=False) as tmp:
            tmp.write(part.brep_data or b"")
            tmp_path = tmp.name
        builder = BRep_Builder()
        shape = TopoDS_Shape()
        breptools_Read(shape, tmp_path, builder)
        os.remove(tmp_path)

        for z in z_values:
            slice_shape = slice_brep_for_layer(shape, float(z))
            base = f"{part.name}_z{z:g}"
            if fmt == "stl":
                path = out_dir / f"{base}.stl"
                writer = StlAPI_Writer()
                writer.Write(slice_shape, str(path))
            else:
                path = out_dir / f"{base}.brep"
                breptools_Write(slice_shape, str(path))
            results.append(path)
    return results
