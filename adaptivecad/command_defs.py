from __future__ import annotations


"""Simple command framework for the AdaptiveCAD GUI.

This module defines primitives for creating and manipulating geometry in the
GUI playground.  All GUI dependencies are imported lazily so the rest of the
package can be used without installing ``pythonocc-core`` or ``PyQt``.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from adaptivecad.params import ParamEnv

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

    def rebuild(self):
        """Regenerate the OCC shape from current parameters for basic primitives."""
        try:
            # Box
            if self.name == "Box":
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
                l = float(self.params.get("l", 50))
                w = float(self.params.get("w", 50))
                h = float(self.params.get("h", 20))
                self.shape = BRepPrimAPI_MakeBox(l, w, h).Shape()
            # Cylinder
            elif self.name == "Cyl":
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
                r = float(self.params.get("r", 10))
                h = float(self.params.get("h", 40))
                self.shape = BRepPrimAPI_MakeCylinder(r, h).Shape()
            # Cone
            elif self.name == "Cone":
                from adaptivecad.primitives import make_cone
                center = self.params.get("center", [0, 0, 0])
                r1 = float(self.params.get("base_radius", 10))
                r2 = float(self.params.get("top_radius", 0))
                height = float(self.params.get("height", 20))
                self.shape = make_cone(center, r1, r2, height)
            # Sphere (Ball)
            elif self.name == "Ball":
                from adaptivecad.primitives import make_ball
                center = self.params.get("center", [0, 0, 0])
                radius = float(self.params.get("radius", 10))
                self.shape = make_ball(center, radius)
            # Torus
            elif self.name == "Torus":
                from adaptivecad.primitives import make_torus
                center = self.params.get("center", [0, 0, 0])
                major = float(self.params.get("major_radius", 30))
                minor = float(self.params.get("minor_radius", 7))
                self.shape = make_torus(center, major, minor)
            # Add more primitives as needed
        except Exception as e:
            print(f"[Feature.rebuild] Error rebuilding {self.name}: {e}")
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

    def eval_param(self, key, env: 'ParamEnv'):
        """Evaluate a parameter as a possible expression using ``env``."""
        val = self.params.get(key)
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            try:
                return env.eval(val)
            except Exception:
                print(f"Error evaluating param {key}: {val}")
                return 0
        return val

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

    def get_reference_point(self):
        # Try OCC shape center of mass
        if hasattr(self, 'shape') and hasattr(self.shape, 'CenterOfMass'):
            return self.shape.CenterOfMass()
        # Try stored param
        if hasattr(self, 'params') and "center" in self.params:
            return self.params["center"]
        # Fallback: first vertex or origin
        if hasattr(self, 'vertices') and self.vertices:
            return self.vertices[0]
        return [0.0] * self.dim

    def all_snap_points(self):
        # For a box: corners; for a sphere: center; for curve: endpoints
        points = []
        # Example: collect vertices if present
        if hasattr(self, 'vertices') and self.vertices:
            points.extend(self.vertices)
        # Example: add center if present
        if hasattr(self, 'center'):
            points.append(self.center)
        # Add more as needed for your shape types
        # Fallback: reference point
        if not points:
            points.append(self.get_reference_point())
        return points

    def snap_points_2d(self):
        """Return common 2‑D snap points based on feature parameters."""
        from adaptivecad.snap_points import snap_points_2d as util

        try:
            return util(self)
        except Exception:
            return []

    def apply_translation(self, delta):
        from adaptivecad.nd_math import translationN
        import numpy as np
        if hasattr(self, 'local_transform') and self.local_transform is not None:
            self.local_transform = np.dot(translationN(delta), self.local_transform)
        # For OCC shapes, you may need to rebuild the shape at the new position
        # ...add OCC-specific logic if needed...

    def apply_scale(self, factor):
        """Uniform or per-axis scaling of the feature."""
        from adaptivecad.nd_math import scalingN
        import numpy as np
        if hasattr(self, 'local_transform') and self.local_transform is not None:
            self.local_transform = np.dot(scalingN(factor, self.dim), self.local_transform)


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
    # Explicitly remove consumed features from OCC display if possible
    for i, feat in enumerate(DOCUMENT):
        if getattr(feat, 'params', {}).get('consumed', False):
            print(f"[rebuild_scene] Feature '{feat.name}' (index {i}) is consumed. Attempting to remove from display.") # DEBUG
            try:
                if hasattr(display, 'Context') and hasattr(feat, 'shape') and feat.shape is not None:
                    if display.Context.IsDisplayed(feat.shape):
                        display.Context.Remove(feat.shape, True)
            except Exception:
                pass
    # Only display features not consumed by a later feature and not marked as consumed
    from OCC.Core.gp import gp_Trsf
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    import numpy as np
    for i, feat in enumerate(DOCUMENT):
        if i not in consumed and not getattr(feat, 'params', {}).get('consumed', False):
            shape = feat.shape
            try:
                T = np.array(feat.world_transform(), dtype=float)
                trsf = gp_Trsf()
                trsf.SetValues(
                    T[0, 0], T[0, 1], T[0, 2],
                    T[1, 0], T[1, 1], T[1, 2],
                    T[2, 0], T[2, 1], T[2, 2],
                    T[0, 3], T[1, 3], T[2, 3]
                )
                shape = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
            except Exception:
                pass
            smoother_display(display, shape)
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
            QInputDialog,
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

        unit, ok = QInputDialog.getItem(
            mw.win,
            "Units",
            "Select export units:",
            ["mm", "inch"],
            0,
            False,
        )
        if not ok:
            return

        scale = 1.0 if unit == "mm" else 1.0 / 25.4
        shape = DOCUMENT[-1].shape
        if scale != 1.0:
            from OCC.Core.gp import gp_Trsf, gp_Pnt
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
            trsf = gp_Trsf()
            trsf.SetScale(gp_Pnt(0, 0, 0), scale)
            shape = BRepBuilderAPI_Transform(shape, trsf, True).Shape()

        writer = StlAPI_Writer()
        err = writer.Write(shape, path)
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

        unit, ok = QInputDialog.getItem(
            mw.win,
            "Units",
            "Select export units:",
            ["mm", "inch"],
            0,
            False,
        )
        if not ok:
            return

        from adaptivecad.io.ama_writer import write_ama
        write_ama(DOCUMENT, path, units=unit)
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

        unit, oku = QInputDialog.getItem(
            mw.win,
            "Units",
            "Select export units:",
            ["mm", "inch"],
            0,
            False,
        )
        if not oku:
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
                tool_diameter=tool_diameter,
                use_mm=(unit == "mm"),
            )

            # Generate G-code
            ama_to_gcode(tmp_ama_path, path, strategy, use_mm=(unit == "mm"))
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

        unit, oku = QInputDialog.getItem(
            mw.win,
            "Units",
            "Select export units:",
            ["mm", "inch"],
            0,
            False,
        )
        if not oku:
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
            gcode = generate_gcode_from_shape(
                shape, shape_name, tool_diameter, use_mm=(unit == "mm")
            )
            
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
            return        # Apply translation
        from OCC.Core.gp import gp_Trsf, gp_Vec
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        trsf = gp_Trsf(); trsf.SetTranslation(gp_Vec(dx, dy, dz))
        moved_shape = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
        # Mark the source shape as consumed (hidden)
        if hasattr(DOCUMENT[shape_idx], 'params'):
            DOCUMENT[shape_idx].params['consumed'] = True
            print(f"[MoveCmd] Feature '{DOCUMENT[shape_idx].name}' (index {shape_idx}) marked as consumed: {DOCUMENT[shape_idx].params}") # DEBUG
        DOCUMENT.append(Feature("Move", {"target": shape_idx, "dx": dx, "dy": dy, "dz": dz}, moved_shape))
        rebuild_scene(mw.view._display)


class ScaleCmd(BaseCmd):
    title = "Scale"

    def run(self, mw) -> None:
        if mw.selected_feature is None:
            mw.win.statusBar().showMessage("Select object to scale!")
            return
        from PySide6.QtWidgets import QInputDialog
        factor, ok = QInputDialog.getDouble(mw.win, "Scale", "Scale factor:", 1.5, 0.1, 10.0, 2)
        if not ok:
            return
        mw.selected_feature.apply_scale(factor)
        rebuild_scene(mw.view._display)


class MirrorCmd(BaseCmd):
    title = "Mirror"

    def run(self, mw) -> None:
        if mw.selected_feature is None:
            mw.win.statusBar().showMessage("Select object to mirror!")
            return

        from PySide6.QtWidgets import QInputDialog
        from OCC.Core.gp import gp_Trsf, gp_Ax2, gp_Pnt, gp_Dir
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

        plane, ok = QInputDialog.getItem(
            mw.win,
            "Mirror",
            "Mirror plane:",
            ["XY", "YZ", "XZ"],
            0,
            False,
        )
        if not ok:
            return

        axes = {
            "XY": gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)),
            "YZ": gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)),
            "XZ": gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)),
        }

        trsf = gp_Trsf()
        trsf.SetMirror(axes[plane])

        mirrored_shape = BRepBuilderAPI_Transform(
            mw.selected_feature.shape, trsf, True
        ).Shape()

        idx = DOCUMENT.index(mw.selected_feature)
        if hasattr(mw.selected_feature, "params"):
            mw.selected_feature.params["consumed"] = True

        DOCUMENT.append(Feature("Mirror", {"target": idx, "plane": plane}, mirrored_shape))
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
        # Mark the target and tool as consumed (hidden)
        if hasattr(DOCUMENT[i1], 'params'):
            DOCUMENT[i1].params['consumed'] = True
        if hasattr(DOCUMENT[i2], 'params'):
            DOCUMENT[i2].params['consumed'] = True
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
        # Mark the target as consumed (hidden)
        if hasattr(DOCUMENT[i1], 'params'):
            DOCUMENT[i1].params['consumed'] = True
            print(f"[CutCmd] Feature '{DOCUMENT[i1].name}' (index {i1}) marked as consumed: {DOCUMENT[i1].params}") # DEBUG
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

class NewConeCmd(BaseCmd):
    title = "Cone"

    def run(self, mw):
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.primitives import make_cone
        center_str, ok = QInputDialog.getText(mw.win, "Cone Center", "Center (x,y,z):", text="0,0,0")
        if not ok:
            return
        center = [float(x) for x in center_str.split(",")]
        r1, ok = QInputDialog.getDouble(mw.win, "Base Radius", "Base radius:", 10.0)
        if not ok:
            return
        r2, ok = QInputDialog.getDouble(mw.win, "Top Radius", "Top radius:", 0.0)
        if not ok:
            return
        height, ok = QInputDialog.getDouble(mw.win, "Height", "Height:", 20.0)
        if not ok:
            return
        shape = make_cone(center, r1, r2, height)
        DOCUMENT.append(Feature("Cone", dict(center=center, base_radius=r1, top_radius=r2, height=height), shape))
        rebuild_scene(mw.view._display)

class RevolveCmd(BaseCmd):
    title = "Revolve"

    def run(self, mw):
        from PySide6.QtWidgets import QInputDialog
        from adaptivecad.primitives import make_revolve

        curve_items = [
            f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT) if hasattr(feat, "shape")
        ]
        if not curve_items:
            mw.win.statusBar().showMessage("No profile curves found!")
            return

        idx, ok = QInputDialog.getItem(mw.win, "Revolve", "Select profile curve:", curve_items, 0, False)
        if not ok:
            return
        curve_idx = int(idx.split(":")[0])
        profile = DOCUMENT[curve_idx].shape

        axis_origin_str, ok = QInputDialog.getText(mw.win, "Axis Origin", "Axis origin (x,y,z):", text="0,0,0")
        if not ok:
            return
        axis_origin = [float(x) for x in axis_origin_str.split(",")]

        axis_dir_str, ok = QInputDialog.getText(mw.win, "Axis Direction", "Axis direction (dx,dy,dz):", text="0,0,1")
        if not ok:
            return
        axis_dir = [float(x) for x in axis_dir_str.split(",")]

        angle_deg, ok = QInputDialog.getDouble(mw.win, "Angle", "Degrees:", 360.0, 1.0, 360.0)
        if not ok:
            return

        shape = make_revolve(profile, axis_origin, axis_dir, angle_deg)
        DOCUMENT.append(
            Feature(
                "Revolve",
                dict(profile=curve_idx, axis_origin=axis_origin, axis_dir=axis_dir, angle=angle_deg),
                shape,
            )
        )
        rebuild_scene(mw.view._display)


class LoftCmd(BaseCmd):
    title = "Loft"

    def run(self, mw) -> None:
        from PySide6.QtWidgets import QInputDialog
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Circ
        from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections

        r1, ok = QInputDialog.getDouble(mw.win, "Loft", "Bottom radius:", 10.0, 0.1)
        if not ok:
            return
        r2, ok = QInputDialog.getDouble(mw.win, "Loft", "Top radius:", 20.0, 0.1)
        if not ok:
            return
        height, ok = QInputDialog.getDouble(mw.win, "Loft", "Height:", 40.0, 0.1)
        if not ok:
            return

        circ1 = gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r1)
        circ2 = gp_Circ(gp_Ax2(gp_Pnt(0, 0, height), gp_Dir(0, 0, 1)), r2)
        wire1 = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ1).Edge()).Wire()
        wire2 = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ2).Edge()).Wire()

        loft = BRepOffsetAPI_ThruSections(True)
        loft.AddWire(wire1)
        loft.AddWire(wire2)
        loft.Build()
        shape = loft.Shape()

        DOCUMENT.append(Feature("Loft", {"r1": r1, "r2": r2, "height": height}, shape))
        rebuild_scene(mw.view._display)


class SweepAlongPathCmd(BaseCmd):
    title = "Sweep"

    def run(self, mw) -> None:
        from PySide6.QtWidgets import QInputDialog
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Circ
        from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipe

        radius, ok = QInputDialog.getDouble(mw.win, "Sweep", "Profile radius:", 5.0, 0.1)
        if not ok:
            return
        length, ok = QInputDialog.getDouble(mw.win, "Sweep", "Path length:", 50.0, 0.1)
        if not ok:
            return

        path_edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(0, 0, length)).Edge()
        circ = gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), radius)
        profile_wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()

        pipe = BRepOffsetAPI_MakePipe(path_edge, profile_wire)
        shape = pipe.Shape()

        DOCUMENT.append(Feature("Sweep", {"radius": radius, "length": length}, shape))
        rebuild_scene(mw.view._display)


class ShellCmd(BaseCmd):
    title = "Shell"

    def run(self, mw) -> None:
        if not DOCUMENT:
            mw.win.statusBar().showMessage("No shapes to shell!")
            return
        from PySide6.QtWidgets import QInputDialog
        from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
        from OCC.Core.TopTools import TopTools_ListOfShape

        items = [f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT)]
        idx_str, ok = QInputDialog.getItem(mw.win, "Shell", "Select shape:", items, 0, False)
        if not ok:
            return
        idx = int(idx_str.split(":" )[0])
        thickness, ok = QInputDialog.getDouble(mw.win, "Shell", "Thickness:", 1.0, 0.01)
        if not ok:
            return

        maker = BRepOffsetAPI_MakeThickSolid()
        maker.MakeThickSolidByJoin(DOCUMENT[idx].shape, TopTools_ListOfShape(), -abs(thickness), 1e-3)
        maker.Build()
        shape = maker.Shape()
        DOCUMENT.append(Feature("Shell", {"source": idx, "thickness": thickness}, shape))
        rebuild_scene(mw.view._display)


class IntersectCmd(BaseCmd):
    title = "Intersect"

    def run(self, mw) -> None:
        if len(DOCUMENT) < 2:
            mw.win.statusBar().showMessage("Need at least two shapes for Intersect!")
            return
        from PySide6.QtWidgets import QInputDialog
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common

        items = [f"{i}: {feat.name}" for i, feat in enumerate(DOCUMENT)]
        idx1, ok = QInputDialog.getItem(mw.win, "Select A", "Target:", items, 0, False)
        if not ok:
            return
        idx2, ok = QInputDialog.getItem(mw.win, "Select B", "Tool:", items, 1, False)
        if not ok:
            return
        i1 = int(idx1.split(":" )[0])
        i2 = int(idx2.split(":" )[0])
        a = DOCUMENT[i1].shape
        b = DOCUMENT[i2].shape
        common = BRepAlgoAPI_Common(a, b).Shape()
        # Mark the target and tool as consumed (hidden)
        if hasattr(DOCUMENT[i1], 'params'):
            DOCUMENT[i1].params['consumed'] = True
        if hasattr(DOCUMENT[i2], 'params'):
            DOCUMENT[i2].params['consumed'] = True
        DOCUMENT.append(Feature("Intersect", {"target": i1, "tool": i2}, common))
        rebuild_scene(mw.view._display)
