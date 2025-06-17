"""Fix the playground.py file to properly define the MainWindow class at the module level."""

import os

# Path definitions
playground_path = r"d:\SuperCAD\AdaptiveCAD\adaptivecad\gui\playground.py"
backup_path = playground_path + '.original'

# First, make a backup of the current file
print(f"Creating backup of current file at {backup_path}")
with open(playground_path, 'r', encoding='utf-8') as f:
    current_content = f.read()
    
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(current_content)

# Replace the problematic structure with this fix
fixed_content = """\"\"\"Simplified GUI playground with optional dependencies.\"\"\"

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True  # Ensure HAS_GUI is set to True here
    from math import pi, cos, sin
    import os
    import sys
    import numpy as np
    import traceback
    from adaptivecad import settings
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QInputDialog, QMessageBox, QCheckBox, 
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, 
        QPushButton, QDockWidget, QLineEdit, QToolBar, QToolButton, QMenu
    )
    from PySide6.QtGui import QAction, QIcon, QCursor, QPixmap  # Added QPixmap for custom icon loading
    from PySide6.QtCore import Qt, QObject, QEvent  # Original import
    from OCC.Core.AIS import AIS_Shape
    from OCC.Core.TopoDS import TopoDS_Face
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from adaptivecad.push_pull import PushPullFeatureCmd
    from adaptivecad.gui.viewcube_widget import ViewCubeWidget
    # Ensure this block is indented
    from adaptivecad.command_defs import (
        NewBoxCmd,
        NewCylCmd,
        ExportStlCmd,
        ExportAmaCmd,
        ExportGCodeCmd,
        ExportGCodeDirectCmd,
        MoveCmd,
        UnionCmd,
        CutCmd,
        NewNDBoxCmd,
        NewNDFieldCmd,
        NewBezierCmd,
        NewBSplineCmd,
        NewBallCmd,
        NewTorusCmd,
        NewConeCmd,
        LoftCmd,
        SweepAlongPathCmd,
        ShellCmd,
        IntersectCmd,
        Feature
    )

# Define feature classes at module level so they're always available
from adaptivecad.command_defs import Feature

# --- HELIX / SPIRAL SHAPE TOOL (Selectable, parametric) ---
class HelixFeature(Feature):
    def __init__(self, radius, pitch, height, n_points=250):
        params = {
            "radius": radius,
            "pitch": pitch,
            "height": height,
            "n_points": n_points,
        }
        super().__init__(params)

    def _make_shape(self, params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCC.Core.TColgp import TColgp_Array1OfPnt
        from OCC.Core.gp import gp_Pnt
        # Create a helix curve
        points = TColgp_Array1OfPnt(1, params["n_points"])
        radius = params["radius"]
        pitch = params["pitch"]
        height = params["height"]
        n_points = params["n_points"]
        for i in range(1, n_points + 1):
            t = (i - 1) / (n_points - 1)
            angle = t * height / pitch * 2.0 * np.pi
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            z = t * height
            points.SetValue(i, gp_Pnt(x, y, z))
        # Convert points to an edge
        edge_builder = BRepBuilderAPI_MakeEdge(points)
        return edge_builder.Edge()

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewHelixCmd:
    def __init__(self):
        pass
    def run(self, mw):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Helix / Spiral Parameters")
                layout = QFormLayout(self)
                self.radius = QDoubleSpinBox()
                self.radius.setRange(0.1, 1000)
                self.radius.setValue(20.0)
                self.pitch = QDoubleSpinBox()
                self.pitch.setRange(0.1, 1000)
                self.pitch.setValue(5.0)
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(40.0)
                self.n_points = QSpinBox()
                self.n_points.setRange(10, 1000)
                self.n_points.setValue(250)
                layout.addRow("Radius:", self.radius)
                layout.addRow("Pitch:", self.pitch)
                layout.addRow("Height:", self.height)
                layout.addRow("Resolution:", self.n_points)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)

        dialog = ParamDialog(mw)
        if dialog.exec():
            radius = dialog.radius.value()
            pitch = dialog.pitch.value()
            height = dialog.height.value()
            n_points = dialog.n_points.value()
            feat = HelixFeature(radius, pitch, height, n_points)
            mw.add_shape(feat)

# --- PI CURVE SHELL SHAPE TOOL (Parametric πₐ-based surface) ---
class PiCurveShellFeature(Feature):
    def __init__(self, base_radius, height, frequency, amplitude, phase, n_u=20, n_v=20):
        params = {
            "base_radius": base_radius,
            "height": height,
            "frequency": frequency,
            "amplitude": amplitude,
            "phase": phase,
            "n_u": n_u,
            "n_v": n_v,
        }
        super().__init__(params)

    def _make_shape(self, params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineSurface
        from OCC.Core.TColgp import TColgp_Array2OfPnt
        from OCC.Core.gp import gp_Pnt

        base_radius = params["base_radius"]
        height = params["height"]
        frequency = params["frequency"]
        amplitude = params["amplitude"]
        phase = params["phase"]
        n_u = params["n_u"]
        n_v = params["n_v"]

        # Generate parametric surface points
        points = TColgp_Array2OfPnt(1, n_u, 1, n_v)
        
        for i in range(1, n_u + 1):
            u_param = (i - 1) / (n_u - 1)  # 0 to 1
            height_at_u = u_param * height
            
            for j in range(1, n_v + 1):
                v_param = 2.0 * np.pi * (j - 1) / (n_v - 1)  # 0 to 2π
                
                # Apply Pi Adaptive calculation to radius
                # πₐ(x) formula with phase shift
                pi_a_factor = amplitude * np.sin(frequency * v_param + phase) + 1.0
                radius_at_point = base_radius * pi_a_factor
                
                x = radius_at_point * np.cos(v_param)
                y = radius_at_point * np.sin(v_param)
                z = height_at_u
                
                points.SetValue(i, j, gp_Pnt(x, y, z))
        
        # Create B-spline surface
        surface_builder = GeomAPI_PointsToBSplineSurface(
            points, 3, 8, 3, 8, True, False  # Surface order parameters
        )
        surface = surface_builder.Surface()
        
        # Create a face from the surface
        face = BRepBuilderAPI_MakeFace(surface, 1e-6).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewPiCurveShellCmd:
    def __init__(self):
        pass
    def run(self, mw):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Adaptive Pi Curve Surface")
                layout = QFormLayout(self)

                self.base_radius = QDoubleSpinBox()
                self.base_radius.setRange(0.1, 1000)
                self.base_radius.setValue(20.0)
                
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(50.0)
                
                self.frequency = QDoubleSpinBox()
                self.frequency.setRange(0.1, 20)
                self.frequency.setValue(3.0)
                self.frequency.setSingleStep(0.1)
                
                self.amplitude = QDoubleSpinBox()
                self.amplitude.setRange(0.01, 10)
                self.amplitude.setValue(0.25)
                self.amplitude.setSingleStep(0.05)
                
                self.phase = QDoubleSpinBox()
                self.phase.setRange(0, 2.0 * 3.14159)
                self.phase.setValue(0.0)
                self.phase.setSingleStep(0.1)
                
                self.n_u = QSpinBox()
                self.n_u.setRange(5, 100)
                self.n_u.setValue(20)
                
                self.n_v = QSpinBox()
                self.n_v.setRange(5, 100)
                self.n_v.setValue(20)
                
                layout.addRow("Base Radius:", self.base_radius)
                layout.addRow("Height:", self.height)
                layout.addRow("Frequency:", self.frequency)
                layout.addRow("Amplitude:", self.amplitude)
                layout.addRow("Phase:", self.phase)
                layout.addRow("U Resolution:", self.n_u)
                layout.addRow("V Resolution:", self.n_v)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)

        dialog = ParamDialog(mw)
        if dialog.exec():
            base_radius = dialog.base_radius.value()
            height = dialog.height.value()
            freq = dialog.frequency.value()
            amp = dialog.amplitude.value()
            phase = dialog.phase.value()
            n_u = dialog.n_u.value()
            n_v = dialog.n_v.value()
            feat = PiCurveShellFeature(base_radius, height, freq, amp, phase, n_u, n_v)
            mw.add_shape(feat)

# --- SUPERELLIPSE SHAPE TOOL (Parametric generalized ellipse) ---
class SuperellipseFeature(Feature):
    def __init__(self, rx, ry, n, segments=100):
        params = {
            "rx": rx,
            "ry": ry,
            "n": n,
            "segments": segments
        }
        super().__init__(params)

    def _make_shape(self, params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace
        from OCC.Core.gp import gp_Pnt, gp_Dir
        from OCC.Core.TColgp import TColgp_Array1OfPnt
        from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineCurve

        rx = params["rx"]
        ry = params["ry"]
        n = params["n"]
        segments = params["segments"]

        # Generate superellipse points
        points = TColgp_Array1OfPnt(1, segments + 1)
        for i in range(1, segments + 2):
            t = 2.0 * np.pi * (i - 1) / segments
            # Superellipse equation: |cos(t)|^(2/n) * rx * sgn(cos(t)), |sin(t)|^(2/n) * ry * sgn(sin(t))
            ct = np.cos(t)
            st = np.sin(t)
            x = rx * np.sign(ct) * np.abs(ct) ** (2/n)
            y = ry * np.sign(st) * np.abs(st) ** (2/n)
            points.SetValue(i if i <= segments else 1, gp_Pnt(x, y, 0))

        # Create a spline from the points
        spline_builder = GeomAPI_PointsToBSplineCurve(points, 3, 8, False, 1.0e-6)
        spline = spline_builder.Curve()
        
        # Create wire from the spline
        edge = BRepBuilderAPI_MakeEdge(spline).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        
        # Create a face from the wire
        face = BRepBuilderAPI_MakeFace(wire).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewSuperellipseCmd:
    def __init__(self):
        pass
    def run(self, mw):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Superellipse Parameters")
                layout = QFormLayout(self)
                
                self.rx = QDoubleSpinBox()
                self.rx.setRange(0.1, 1000)
                self.rx.setValue(25.0)
                
                self.ry = QDoubleSpinBox()
                self.ry.setRange(0.1, 1000)
                self.ry.setValue(15.0)
                
                self.n = QDoubleSpinBox()
                self.n.setRange(0.01, 10)
                self.n.setValue(2.0)
                self.n.setSingleStep(0.1)
                
                self.segments = QSpinBox()
                self.segments.setRange(10, 500)
                self.segments.setValue(100)
                
                layout.addRow("X Radius:", self.rx)
                layout.addRow("Y Radius:", self.ry)
                layout.addRow("Power (n):", self.n)
                layout.addRow("Segments:", self.segments)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
                
        dialog = ParamDialog(mw)
        if dialog.exec():
            rx = dialog.rx.value()
            ry = dialog.ry.value()
            n = dialog.n.value()
            segments = dialog.segments.value()
            feat = SuperellipseFeature(rx, ry, n, segments)
            mw.add_shape(feat)

# --- TAPERED CYLINDER SHAPE TOOL ---
class TaperedCylinderFeature(Feature):
    def __init__(self, height, radius1, radius2):
        params = {
            "height": height,
            "radius1": radius1,
            "radius2": radius2
        }
        super().__init__(params)

    def _make_shape(self, params):
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
        from OCC.Core.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Vec
        
        height = params["height"]
        radius1 = params["radius1"]
        radius2 = params["radius2"]
        
        ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        cone = BRepPrimAPI_MakeCone(ax, radius1, radius2, height).Shape()
        return cone

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewTaperedCylinderCmd:
    def __init__(self):
        pass
    def run(self, mw):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Tapered Cylinder Parameters")
                layout = QFormLayout(self)
                
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(30.0)
                
                self.radius1 = QDoubleSpinBox()
                self.radius1.setRange(0.1, 1000)
                self.radius1.setValue(15.0)
                
                self.radius2 = QDoubleSpinBox()
                self.radius2.setRange(0.1, 1000)
                self.radius2.setValue(5.0)
                
                layout.addRow("Height:", self.height)
                layout.addRow("Base Radius:", self.radius1)
                layout.addRow("Top Radius:", self.radius2)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
                
        dialog = ParamDialog(mw)
        if dialog.exec():
            height = dialog.height.value()
            radius1 = dialog.radius1.value()
            radius2 = dialog.radius2.value()
            feat = TaperedCylinderFeature(height, radius1, radius2)
            mw.add_shape(feat)
            
# Define MainWindow class properly at module level
if not HAS_GUI:
    # Define a fallback MainWindow when GUI is not available
    class MainWindow:
        def __init__(self):
            print("GUI dependencies not available. Can't create MainWindow.")
        
        def run(self):
            print("Error: Cannot run GUI without PySide6 and OCC.Display dependencies.")
            return 1
else:
    # Original MainWindow implementation when GUI is available
"""

# Find where the actual MainWindow class starts in the original file after the feature class definitions
import re
main_window_content_match = re.search(r'else:\s+class MainWindow:', current_content)
if main_window_content_match:
    # Extract everything after the MainWindow class definition
    main_window_index = main_window_content_match.end()
    main_window_content = current_content[main_window_index:]
    
    # Complete the fixed content with the MainWindow class implementation
    fixed_content += main_window_content
    
    # Write the fixed content to the file
    with open(playground_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    print(f"Successfully fixed {playground_path}")
else:
    print("Could not find the MainWindow class definition in the file. No changes were made.")
