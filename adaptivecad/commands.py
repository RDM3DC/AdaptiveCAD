from __future__ import annotations


"""Simple command framework for the AdaptiveCAD GUI.

This module defines primitives for creating and manipulating geometry in the
GUI playground.  All GUI dependencies are imported lazily so the rest of the
package can be used without installing ``pythonocc-core`` or ``PyQt``.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from adaptivecad.gcode_generator import generate_gcode_from_shape

try:  # Optional OCC dependency
    from OCC.Core.gp import gp_Pnt  # type: ignore
    from OCC.Core.BRepPrimAPI import (  # type: ignore
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
    )
    from OCC.Core.TopoDS import TopoDS_Shape  # type: ignore
except Exception:  # pragma: no cover - optional dependency missing
    gp_Pnt = None  # type: ignore
    BRepPrimAPI_MakeBox = BRepPrimAPI_MakeCylinder = None  # type: ignore
    TopoDS_Shape = object  # type: ignore
from adaptivecad.nd_math import identityN

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
    local_transform: Any = None
    dim: int = None
    parent: 'Feature' = None  # Parent feature for hierarchy
    children: list = None


    def __post_init__(self):
        # Set dim from params if not provided
        if self.dim is None:
            self.dim = self.params.get('dim', 3)
        # Set local_transform to identity if not provided
        if self.local_transform is None:
            self.local_transform = identityN(self.dim)
        else:
            import numpy as np
            self.local_transform = np.asarray(self.local_transform)
        if self.children is None:
            self.children = []

    def set_parent(self, parent):
        if self.parent is not None and self in self.parent.children:
            self.parent.children.remove(self)
        self.parent = parent
        if parent is not None and self not in parent.children:
            parent.children.append(self)

    def world_transform(self):
        import numpy as np
        t = np.array(self.local_transform)
        p = self.parent
        while p is not None:
            t = np.dot(p.local_transform, t)
            p = p.parent
        return t


    def as_dict(self):
        d = dict(
            name=self.name,
            params=self.params,
            dim=self.dim,
            local_transform=self.local_transform.tolist(),
            parent=self.parent.name if self.parent else None
        )
        return d


# Global in-memory document tree
DOCUMENT: List[Feature] = []


def rebuild_scene(display) -> None:
    """Re-display only active shapes in the document (hide consumed ones)."""
    from adaptivecad.display_utils import smoother_display
    display.EraseAll()
    # Find all consumed targets (by Move/Boolean features)
    consumed = set()
    for i, feat in enumerate(DOCUMENT):
        if feat.name in ("Move", "Cut", "Union", "Intersect"):
            target = feat.params.get("target")
            if isinstance(target, int):
                consumed.add(target)
            elif isinstance(target, str) and target.isdigit():
                consumed.add(int(target))
            tool = feat.params.get("tool")
            if isinstance(tool, int):
                consumed.add(tool)
            elif isinstance(tool, str) and tool.isdigit():
                consumed.add(int(tool))
    # Only display features not consumed by a later feature
    for i, feat in enumerate(DOCUMENT):
        if i not in consumed:
            smoother_display(display, feat.shape)
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

        from adaptivecad.io.ama_writer import write_ama
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
        from adaptivecad.io.ama_writer import write_ama
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
            from adaptivecad.io.gcode_generator import SimpleMilling, ama_to_gcode
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


# ---------------------------------------------------------------------------
# Move/Transform command
# ---------------------------------------------------------------------------

class MoveCmd(BaseCmd):
    title = "Move"

    def run(self, mw) -> None:
        if not DOCUMENT:
            mw.win.statusBar().showMessage("No shapes to move!")
            return
        # Let user select a shape by index (simple for now)
        from PySide6.QtWidgets import QInputDialog
        items = [f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT)]
        idx, ok = QInputDialog.getItem(mw.win, "Select Shape to Move", "Shape:", items, 0, False)
        if not ok:
            return
        shape_idx = int(idx.split(":")[0])
        shape = DOCUMENT[shape_idx].shape
        # Get translation values
        dx, ok = QInputDialog.getDouble(mw.win, "Move", "dx (mm)", 10.0)
        if not ok:
            return
        dy, ok = QInputDialog.getDouble(mw.win, "Move", "dy (mm)", 0.0)
        if not ok:
            return
        dz, ok = QInputDialog.getDouble(mw.win, "Move", "dz (mm)", 0.0)
        if not ok:
            return
        # Apply translation
        from OCC.Core.gp import gp_Trsf, gp_Vec
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        trsf = gp_Trsf(); trsf.SetTranslation(gp_Vec(dx, dy, dz))
        moved_shape = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
        DOCUMENT.append(Feature("Move", {"target": shape_idx, "dx": dx, "dy": dy, "dz": dz}, moved_shape))
        rebuild_scene(mw.view._display)


# ---------------------------------------------------------------------------
# Boolean (Union, Cut) commands
# ---------------------------------------------------------------------------

class UnionCmd(BaseCmd):
    title = "Union"
    def run(self, mw) -> None:
        if len(DOCUMENT) < 2:
            mw.win.statusBar().showMessage("Need at least two shapes for Union!")
            return
        from PySide6.QtWidgets import QInputDialog
        items = [f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT)]
        idx1, ok = QInputDialog.getItem(mw.win, "Select Target (A)", "Target:", items, 0, False)
        if not ok:
            return
        idx2, ok = QInputDialog.getItem(mw.win, "Select Tool (B)", "Tool:", items, 1, False)
        if not ok:
            return
        i1 = int(idx1.split(":")[0])
        i2 = int(idx2.split(":")[0])
        a = DOCUMENT[i1].shape
        b = DOCUMENT[i2].shape
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
        fused = BRepAlgoAPI_Fuse(a, b).Shape()
        DOCUMENT.append(Feature("Union", {"target": i1, "tool": i2}, fused))
        rebuild_scene(mw.view._display)

class CutCmd(BaseCmd):
    title = "Cut"
    def run(self, mw) -> None:
        if len(DOCUMENT) < 2:
            mw.win.statusBar().showMessage("Need at least two shapes for Cut!")
            return
        from PySide6.QtWidgets import QInputDialog
        items = [f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT)]
        idx1, ok = QInputDialog.getItem(mw.win, "Select Target (A)", "Target:", items, 0, False)
        if not ok:
            return
        idx2, ok = QInputDialog.getItem(mw.win, "Select Tool (B)", "Tool:", items, 1, False)
        if not ok:
            return
        i1 = int(idx1.split(":")[0])
        i2 = int(idx2.split(":")[0])
        a = DOCUMENT[i1].shape
        b = DOCUMENT[i2].shape
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        cut = BRepAlgoAPI_Cut(a, b).Shape()
        DOCUMENT.append(Feature("Cut", {"target": i1, "tool": i2}, cut))
        rebuild_scene(mw.view._display)


# ---------------------------------------------------------------------------
# NDBox and NDField commands
# ---------------------------------------------------------------------------

class NewNDBoxCmd(BaseCmd):
    title = "ND Box"
    def run(self, mw) -> None:
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.ndbox import NDBox
        # Ask for dimension
        dim, ok = QInputDialog.getInt(mw.win, "ND Box", "Dimension (N):", 3, 1)
        if not ok:
            return
        # Ask for center and size as comma-separated
        center_str, ok = QInputDialog.getText(mw.win, "ND Box", f"Center (comma-separated, {dim} values):", text=','.join(['0']*dim))
        if not ok:
            return
        size_str, ok = QInputDialog.getText(mw.win, "ND Box", f"Size (comma-separated, {dim} values):", text=','.join(['10']*dim))
        if not ok:
            return
        center = [float(x) for x in center_str.split(',')]
        size = [float(x) for x in size_str.split(',')]
        box = NDBox(center, size)
        DOCUMENT.append(Feature("NDBox", {"center": center, "size": size, "dim": dim}, box))
        rebuild_scene(mw.view._display)

class NewNDFieldCmd(BaseCmd):
    title = "ND Field"
    def run(self, mw) -> None:
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.ndfield import NDField
        # Ask for dimension
        dim, ok = QInputDialog.getInt(mw.win, "ND Field", "Dimension (N):", 3, 1)
        if not ok:
            return
        # Ask for grid shape as comma-separated
        grid_str, ok = QInputDialog.getText(mw.win, "ND Field", f"Grid shape (comma-separated, {dim} values):", text=','.join(['2']*dim))
        if not ok:
            return
        grid_shape = [int(x) for x in grid_str.split(',')]
        num_vals = 1
        for n in grid_shape:
            num_vals *= n
        # Ask for values as comma-separated (default: zeros)
        values_str, ok = QInputDialog.getText(mw.win, "ND Field", f"Values (comma-separated, {num_vals} values):", text=','.join(['0']*num_vals))
        if not ok:
            return
        values = [float(x) for x in values_str.split(',')]
        field = NDField(grid_shape, values)
        DOCUMENT.append(Feature("NDField", {"grid_shape": grid_shape, "values": values, "dim": dim}, field))
        rebuild_scene(mw.view._display)


# ---------------------------------------------------------------------------
# Ball and Torus commands
# ---------------------------------------------------------------------------

class NewBallCmd(BaseCmd):
    title = "Ball"
    def run(self, mw):
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.primitives import make_ball
        center_str, ok = QInputDialog.getText(mw.win, "Ball Center", "Center (x,y,z):", text="0,0,0")
        if not ok:
            return
        center = [float(x) for x in center_str.split(",")]
        radius, ok = QInputDialog.getDouble(mw.win, "Ball Radius", "Radius:", 10.0)
        if not ok:
            return
        shape = make_ball(center, radius)
        DOCUMENT.append(Feature("Ball", dict(center=center, radius=radius), shape))
        rebuild_scene(mw.view._display)

class NewTorusCmd(BaseCmd):
    title = "Torus"
    def run(self, mw):
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.primitives import make_torus
        center_str, ok = QInputDialog.getText(mw.win, "Torus Center", "Center (x,y,z):", text="0,0,0")
        if not ok:
            return
        center = [float(x) for x in center_str.split(",")]
        maj, ok = QInputDialog.getDouble(mw.win, "Major Radius", "Major radius:", 30.0)
        if not ok:
            return
        minr, ok = QInputDialog.getDouble(mw.win, "Minor Radius", "Minor radius:", 7.0)
        if not ok:
            return
        shape = make_torus(center, maj, minr)
        DOCUMENT.append(Feature("Torus", dict(center=center, major_radius=maj, minor_radius=minr), shape))
        rebuild_scene(mw.view._display)
