from __future__ import annotations


"""Simple command framework for the AdaptiveCAD GUI.

This module defines primitives for creating and manipulating geometry in the
GUI playground.  All GUI dependencies are imported lazily so the rest of the
package can be used without installing ``pythonocc-core`` or ``PyQt``.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from adaptivecad.io.gcode_generator import ama_to_gcode, SimpleMilling
from adaptivecad.gcode_generator import generate_gcode_from_shape

# Optional OCC imports for geometry creation
try:
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.TopoDS import TopoDS_Shape
except Exception:  # pragma: no cover - OCC not installed
    gp_Pnt = None
    BRepPrimAPI_MakeBox = None
    BRepPrimAPI_MakeCylinder = None
    TopoDS_Shape = object

# ---------------------------------------------------------------------------
# Optional GUI helpers
# ---------------------------------------------------------------------------

def _require_command_modules():
    """Import optional GUI modules required for command execution."""
    try:
        from PySide6.QtWidgets import QInputDialog, QFileDialog
        from OCC.Core.BRepPrimAPI import (
            BRepPrimAPI_MakeBox,
            BRepPrimAPI_MakeCylinder,
        )
        from OCC.Core.StlAPI import StlAPI_Writer
    except Exception as exc:  # pragma: no cover - import error path
        raise RuntimeError(
            "GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6"
        ) from exc

    return (
        QInputDialog,
        QFileDialog,
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        StlAPI_Writer,
    )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    """Record for a model feature."""

    name: str
    params: Dict[str, Any]
    shape: Any  # OCC TopoDS_Shape


# Global in-memory document tree
DOCUMENT: List[Feature] = []


def rebuild_scene(display) -> None:
    """Re-display all shapes in the document."""
    display.EraseAll()
    for feat in DOCUMENT:
        display.DisplayShape(feat.shape, update=False)
    display.FitAll()


# ---------------------------------------------------------------------------
# Command classes
# ---------------------------------------------------------------------------

class BaseCmd:
    """Base command interface."""

    title = "Base"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        raise NotImplementedError


class NewBoxCmd(BaseCmd):
    title = "Box"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            QInputDialog,
            _,
            BRepPrimAPI_MakeBox,
            _,
            _,
        ) = _require_command_modules()

        l, ok = QInputDialog.getDouble(mw.win, "Box", "Length (mm)", 50, 1)
        if not ok:
            return
        w, ok = QInputDialog.getDouble(mw.win, "Box", "Width (mm)", 50, 1)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(mw.win, "Box", "Height (mm)", 20, 1)
        if not ok:
            return

        shape = BRepPrimAPI_MakeBox(l, w, h).Shape()
        DOCUMENT.append(Feature("Box", {"l": l, "w": w, "h": h}, shape))
        rebuild_scene(mw.view._display)


class NewCylCmd(BaseCmd):
    title = "Cylinder"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            QInputDialog,
            _,
            _,
            BRepPrimAPI_MakeCylinder,
            _,
        ) = _require_command_modules()

        r, ok = QInputDialog.getDouble(mw.win, "Cylinder", "Radius (mm)", 10, 1)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(mw.win, "Cylinder", "Height (mm)", 40, 1)
        if not ok:
            return

        shape = BRepPrimAPI_MakeCylinder(r, h).Shape()
        DOCUMENT.append(Feature("Cyl", {"r": r, "h": h}, shape))
        rebuild_scene(mw.view._display)


class ExportStlCmd(BaseCmd):
    title = "Export STL"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            _,
            QFileDialog,
            _,
            _,
            StlAPI_Writer,
        ) = _require_command_modules()

        if not DOCUMENT:
            return

        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save STL", filter="STL (*.stl)"
        )
        if not path:
            return

        writer = StlAPI_Writer()
        err = writer.Write(DOCUMENT[-1].shape, path)
        if err == 1:
            mw.win.statusBar().showMessage(f"STL saved ➡ {path}")
        else:
            mw.win.statusBar().showMessage("Failed to save STL")


class ExportAmaCmd(BaseCmd):
    title = "Export AMA"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            _,
            QFileDialog,
            _,
            _,
            _,
        ) = _require_command_modules()

        if not DOCUMENT:
            return

        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save AMA", filter="AMA (*.ama)"
        )
        if not path:
            return

        from adaptivecad.io.ama_writer import write_ama  # lazy import

        write_ama(DOCUMENT, path)
        mw.win.statusBar().showMessage(f"AMA saved ➡ {path}")


class ExportGCodeCmd(BaseCmd):
    title = "Export G-code"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        import tempfile
        import os
        (
            QInputDialog,
            QFileDialog,
            _,
            _,
            _,
        ) = _require_command_modules()

        if not DOCUMENT:
            return

        # First, we need to save as AMA temporarily
        with tempfile.NamedTemporaryFile(suffix=".ama", delete=False) as tmp_ama:
            tmp_ama_path = tmp_ama.name

        # Write the current document to the temporary AMA file
        from adaptivecad.io.ama_writer import write_ama  # lazy import

        write_ama(DOCUMENT, tmp_ama_path)
        
        # Ask for G-code settings
        safe_height, ok1 = QInputDialog.getDouble(
            mw.win, "Safe Height (mm)", "Enter safe height for rapid movements:", 10.0, 1.0, 100.0, 1
        )
        if not ok1:
            os.remove(tmp_ama_path)
            return
            
        cut_depth, ok2 = QInputDialog.getDouble(
            mw.win, "Cut Depth (mm)", "Enter cutting depth:", 1.0, 0.1, 20.0, 1
        )
        if not ok2:
            os.remove(tmp_ama_path)
            return
            
        feed_rate, ok3 = QInputDialog.getDouble(
            mw.win, "Feed Rate (mm/min)", "Enter feed rate:", 100.0, 10.0, 1000.0, 1
        )
        if not ok3:
            os.remove(tmp_ama_path)
            return
            
        tool_diameter, ok4 = QInputDialog.getDouble(
            mw.win, "Tool Diameter (mm)", "Enter tool diameter:", 3.0, 0.1, 20.0, 1
        )
        if not ok4:
            os.remove(tmp_ama_path)
            return

        # Get the output path for the G-code
        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save G-code", filter="G-code (*.gcode *.nc)"
        )
        if not path:
            os.remove(tmp_ama_path)
            return
        
        try:
            # Create milling strategy with user settings
            strategy = SimpleMilling(
                safe_height=safe_height,
                cut_depth=cut_depth,
                feed_rate=feed_rate,
                tool_diameter=tool_diameter
            )
            
            # Generate G-code
            ama_to_gcode(tmp_ama_path, path, strategy)
            mw.win.statusBar().showMessage(f"G-code saved ➡ {path}")
        except Exception as e:
            mw.win.statusBar().showMessage(f"Failed to save G-code: {str(e)}")
        finally:
            # Clean up temporary AMA file
            os.remove(tmp_ama_path)


class ExportGCodeDirectCmd(BaseCmd):
    title = "Export G-code (CAD)"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        """Generate G-code directly from the CAD shape without creating an AMA file."""
        (
            QInputDialog,
            QFileDialog,
            _,
            _,
            _,
        ) = _require_command_modules()

        if not DOCUMENT:
            mw.win.statusBar().showMessage("No shapes to export!")
            return

        # Get the last shape in DOCUMENT for this example
        # In a more complex application, you'd let the user select which shape to export
        shape = DOCUMENT[-1].shape
        shape_name = DOCUMENT[-1].name

        # Ask for G-code parameters
        safe_height, ok1 = QInputDialog.getDouble(
            mw.win, "Safe Height (mm)", "Enter safe height for rapid movements:", 10.0, 1.0, 100.0, 1
        )
        if not ok1:
            return
            
        cut_depth, ok2 = QInputDialog.getDouble(
            mw.win, "Cut Depth (mm)", "Enter cutting depth:", 1.0, 0.1, 20.0, 1
        )
        if not ok2:
            return
            
        tool_diameter, ok3 = QInputDialog.getDouble(
            mw.win, "Tool Diameter (mm)", "Enter tool diameter:", 6.0, 0.1, 20.0, 1
        )
        if not ok3:
            return

        # Get the output path
        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save G-code", filter="G-code (*.gcode *.nc)"
        )
        if not path:
            return

        # Generate G-code directly from the shape
        try:
            # Generate G-code string
            gcode = generate_gcode_from_shape(shape, shape_name, tool_diameter)
            
            # Save to file
            with open(path, 'w') as f:
                f.write(gcode)
                
            mw.win.statusBar().showMessage(f"G-code (direct) saved ➡ {path}")
        except Exception as e:
            mw.win.statusBar().showMessage(f"Failed to generate G-code: {str(e)}")


# ---------------------------------------------------------------------------
# Curve commands
# ---------------------------------------------------------------------------

class NewBezierCmd(BaseCmd):
    title = "Bezier Curve"

    def run(self, mw) -> None:
        try:
            from OCC.Core.Geom import Geom_BezierCurve
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            from OCC.Core.TColgp import TColgp_Array1OfPnt
            from OCC.Core.gp import gp_Pnt
        except ImportError:
            mw.win.statusBar().showMessage("Bezier API missing – button disabled")
            return

        # Simple point picker dialog (replace with snap-assisted dialog for production)
        from PySide6.QtWidgets import QInputDialog
        points = []
        for i in range(3):
            x, ok = QInputDialog.getDouble(mw.win, f"Bezier Point {i+1}", "X (mm)", 0.0)
            if not ok:
                return
            y, ok = QInputDialog.getDouble(mw.win, f"Bezier Point {i+1}", "Y (mm)", 0.0)
            if not ok:
                return
            z, ok = QInputDialog.getDouble(mw.win, f"Bezier Point {i+1}", "Z (mm)", 0.0)
            if not ok:
                return
            points.append(gp_Pnt(x, y, z))

        arr = TColgp_Array1OfPnt(1, len(points))
        for i, p in enumerate(points, 1):
            arr.SetValue(i, p)
        curve = Geom_BezierCurve(arr)
        edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        DOCUMENT.append(Feature("Bezier", {"points": [[p.X(), p.Y(), p.Z()] for p in points]}, edge))
        rebuild_scene(mw.view._display)


class NewBSplineCmd(BaseCmd):
    title = "B-spline Curve"

    def run(self, mw) -> None:
        try:
            from OCC.Core.Geom import Geom_BSplineCurve
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            from OCC.Core.TColgp import TColgp_Array1OfPnt
            from OCC.Core.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
            from OCC.Core.gp import gp_Pnt
        except ImportError:
            mw.win.statusBar().showMessage("BSpline API missing – button disabled")
            return

        from PySide6.QtWidgets import QInputDialog
        points = []
        for i in range(4):
            x, ok = QInputDialog.getDouble(mw.win, f"B-spline Point {i+1}", "X (mm)", 0.0)
            if not ok:
                return
            y, ok = QInputDialog.getDouble(mw.win, f"B-spline Point {i+1}", "Y (mm)", 0.0)
            if not ok:
                return
            z, ok = QInputDialog.getDouble(mw.win, f"B-spline Point {i+1}", "Z (mm)", 0.0)
            if not ok:
                return
            points.append(gp_Pnt(x, y, z))

        degree = 3
        arr = TColgp_Array1OfPnt(1, len(points))
        for i, p in enumerate(points, 1):
            arr.SetValue(i, p)
        knots = TColStd_Array1OfReal(1, 2)
        knots.SetValue(1, 0.0)
        knots.SetValue(2, 1.0)
        mults = TColStd_Array1OfInteger(1, 2)
        mults.SetValue(1, degree+1)
        mults.SetValue(2, degree+1)
        curve = Geom_BSplineCurve(arr, knots, mults, degree)
        edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        DOCUMENT.append(Feature("BSpline", {"points": [[p.X(), p.Y(), p.Z()] for p in points]}, edge))
        rebuild_scene(mw.view._display)
