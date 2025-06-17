"""Simplified GUI playground with optional dependencies.

This playground implements advanced parametric shapes including Pi Curve Shell,
Superellipse, Helix, Tapered Cylinder, Capsule and Ellipsoid that demonstrate the
Adaptive Pi Geometry (πₐ) principles. 

For the formal mathematical foundation, see the ADAPTIVE_PI_AXIOMS.md document.
"""

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
    # Initialize the backend explicitly
    backend.load_backend('pyside6')  # Load PySide6 backend for OCC
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True  # Ensure HAS_GUI is set to True here
    from math import pi, cos, sin
    import os
    import sys
    import json  # Add json import at module level
    import numpy as np
    import traceback
    from adaptivecad import settings
    from adaptivecad.gui.viewcube_widget import ViewCubeWidget
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QInputDialog, QMessageBox, QCheckBox, 
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, 
        QPushButton, QDockWidget, QLineEdit, QToolBar, QToolButton, QMenu,
        QDialogButtonBox, QFormLayout, QDoubleSpinBox, QSpinBox, QDialog
    )
    from PySide6.QtGui import QAction, QIcon, QCursor, QPixmap
    from PySide6.QtCore import Qt, QObject, QEvent
    from OCC.Core.AIS import AIS_Shape
    from OCC.Core.TopoDS import TopoDS_Face
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from adaptivecad.command_defs import (
        Feature,
        NewBoxCmd,
        NewCylCmd,
        ExportStlCmd,
        ExportAmaCmd,
        ExportGCodeCmd,
        ExportGCodeDirectCmd,
        MoveCmd,
        UnionCmd,
        CutCmd,
        IntersectCmd,
        ScaleCmd,
        NewBallCmd,
        NewTorusCmd,
        NewConeCmd,
        ShellCmd
    )
    from adaptivecad.commands.minimal_import import MinimalImportCmd

# Define SuperellipseFeature at module level regardless of GUI availability
from adaptivecad.command_defs import Feature

# --- PI CURVE SHELL SHAPE TOOL (Parametric πₐ-based surface) ---
class PiCurveShellFeature(Feature):
    def __init__(self, base_radius, height, freq, amp, phase, n_u=60, n_v=30):
        params = {
            "base_radius": base_radius,
            "height": height,
            "freq": freq,
            "amp": amp,
            "phase": phase,
            "n_u": n_u,
            "n_v": n_v,
        }
        shape = self._make_shape(params)
        super().__init__("PiCurveShell", params, shape)

    @staticmethod
    def _make_shape(params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCC.Core.gp import gp_Pnt
        base_radius = params["base_radius"]
        height = params["height"]
        freq = params["freq"]
        amp = params["amp"]
        phase = params["phase"]
        n_u = params["n_u"]
        n_v = params["n_v"]
        # Generate points for a deformed cylinder shell
        us = np.linspace(0, 2 * np.pi, n_u)
        vs = np.linspace(0, height, n_v)
        def pi_curve(u):
            # Example: πₐ curve as a sine deformation
            return amp * np.sin(freq * u + phase)
        pts = []
        for v in vs:
            row = []
            for u in us:
                r = base_radius + pi_curve(u)
                x = r * np.cos(u)
                y = r * np.sin(u)
                z = v
                row.append(gp_Pnt(x, y, z))
            pts.append(row)
        # Create faces between grid points
        from OCC.Core.TColgp import TColgp_Array2OfPnt
        arr = TColgp_Array2OfPnt(1, n_u, 1, n_v)
        for i in range(n_u):
            for j in range(n_v):
                arr.SetValue(i+1, j+1, pts[j][i])
        face = BRepBuilderAPI_MakeFace(arr, 1e-6).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewPiCurveShellCmd:
    def __init__(self):
        pass
    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Adaptive Pi Curve Shell Parameters")
                layout = QFormLayout(self)
                self.base_radius = QDoubleSpinBox()
                self.base_radius.setRange(0.1, 1000)
                self.base_radius.setValue(20.0)
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(40.0)
                self.freq = QDoubleSpinBox()
                self.freq.setRange(0.1, 20.0)
                self.freq.setValue(3.0)
                self.amp = QDoubleSpinBox()
                self.amp.setRange(0.0, 20.0)
                self.amp.setValue(5.0)
                self.phase = QDoubleSpinBox()
                self.phase.setRange(-10.0, 10.0)
                self.phase.setValue(0.0)
                self.n_u = QSpinBox()
                self.n_u.setRange(8, 200)
                self.n_u.setValue(60)
                self.n_v = QSpinBox()
                self.n_v.setRange(4, 100)
                self.n_v.setValue(30)
                layout.addRow("Base Radius", self.base_radius)
                layout.addRow("Height", self.height)
                layout.addRow("Frequency (πₐ)", self.freq)
                layout.addRow("Amplitude", self.amp)
                layout.addRow("Phase", self.phase)
                layout.addRow("Segments U", self.n_u)
                layout.addRow("Segments V", self.n_v)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        base_radius = dlg.base_radius.value()
        height = dlg.height.value()
        freq = dlg.freq.value()
        amp = dlg.amp.value()
        phase = dlg.phase.value()
        n_u = dlg.n_u.value()
        n_v = dlg.n_v.value()
        feat = PiCurveShellFeature(base_radius, height, freq, amp, phase, n_u, n_v)
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Pi Curve Shell created: r={base_radius}, h={height}, freq={freq}, amp={amp}", 3000)

# --- HELIX / SPIRAL SHAPE TOOL (Selectable, parametric) ---
class HelixFeature(Feature):
    def __init__(self, radius, pitch, height, n_points=250):
        params = {
            "radius": radius,
            "pitch": pitch,
            "height": height,
            "n_points": n_points,
        }
        shape = self._make_shape(params)
        super().__init__("Helix", params, shape)

    @staticmethod
    def _make_shape(params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCC.Core.gp import gp_Pnt
        radius = params["radius"]
        pitch = params["pitch"]
        height = params["height"]
        n = int(params.get("n_points", 250))
        ts = np.linspace(0, 2 * np.pi * height / pitch, n)
        pts = [gp_Pnt(radius * np.cos(t), radius * np.sin(t), pitch * t / (2 * np.pi)) for t in ts]
        wire = BRepBuilderAPI_MakeWire()
        for a, b in zip(pts[:-1], pts[1:]):
            wire.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
        return wire.Wire()

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewHelixCmd:
    def __init__(self):
        pass
    def run(self, mw):
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
                self.n_points.setRange(10, 2000)
                self.n_points.setValue(250)
                layout.addRow("Radius", self.radius)
                layout.addRow("Pitch", self.pitch)
                layout.addRow("Height", self.height)
                layout.addRow("Points", self.n_points)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        radius = dlg.radius.value()
        pitch = dlg.pitch.value()
        height = dlg.height.value()
        n_points = dlg.n_points.value()
        feat = HelixFeature(radius, pitch, height, n_points)
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Helix created: radius={radius}, pitch={pitch}, height={height}", 3000)

class SuperellipseFeature(Feature):
    def __init__(self, rx, ry, n, segments=100):
        params = {
            "rx": rx,
            "ry": ry,
            "n": n,
            "segments": segments
        }
        shape = self._make_shape(params)
        super().__init__("Superellipse", params, shape)
        
    @staticmethod
    def _make_shape(params):
        import numpy as np
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace
        from OCC.Core.gp import gp_Pnt
        
        rx = params["rx"]
        ry = params["ry"]
        n = params["n"]
        segments = params["segments"]
        
        # Generate points for superellipse: |x/rx|^n + |y/ry|^n = 1
        ts = np.linspace(0, 2 * np.pi, segments)
        # Convert parametric equations for superellipse
        pts = []
        for t in ts:
            # Parametric form with power of 2/n
            cos_t = np.cos(t)
            sin_t = np.sin(t)
            cos_t_abs = abs(cos_t)
            sin_t_abs = abs(sin_t)
            
            # Handle zero case to avoid division by zero
            if cos_t_abs < 1e-10:
                x = 0
            else:
                x = rx * np.sign(cos_t) * (cos_t_abs ** (2/n))
                
            if sin_t_abs < 1e-10:
                y = 0
            else:
                y = ry * np.sign(sin_t) * (sin_t_abs ** (2/n))
            
            pts.append(gp_Pnt(x, y, 0))
        
        # Create a wire from the points
        wire = BRepBuilderAPI_MakeWire()
        for i in range(segments):
            edge = BRepBuilderAPI_MakeEdge(pts[i], pts[(i + 1) % segments]).Edge()
            wire.Add(edge)
        
        # Create a face from the wire
        face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
        return face
        
    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewSuperellipseCmd:
    def __init__(self):
        pass
        
    def run(self, mw):
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
                self.n.setRange(0.1, 10.0)
                self.n.setValue(2.5)
                self.n.setSingleStep(0.1)
                
                self.segments = QSpinBox()
                self.segments.setRange(12, 200)
                self.segments.setValue(60)
                
                layout.addRow("X Radius:", self.rx)
                layout.addRow("Y Radius:", self.ry)
                layout.addRow("Exponent (n):", self.n)
                layout.addRow("Segments:", self.segments)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
        
        dlg = ParamDialog(mw.win)
        if dlg.exec():
            rx = dlg.rx.value()
            ry = dlg.ry.value()
            n = dlg.n.value()
            segments = dlg.segments.value()
            
            feat = SuperellipseFeature(rx, ry, n, segments)
            try:
                from adaptivecad.command_defs import DOCUMENT
                DOCUMENT.append(feat)
            except Exception:
                pass
                
            mw.view._display.EraseAll()
            mw.view._display.DisplayShape(feat.shape, update=True)
            mw.view._display.FitAll()
            mw.win.statusBar().showMessage(f"Superellipse created: rx={rx}, ry={ry}, n={n}", 3000)

# --- TAPERED CYLINDER / CONE SHAPE TOOL ---
class TaperedCylinderFeature(Feature):
    def __init__(self, height, radius1, radius2):
        params = {
            "height": height,
            "radius1": radius1,
            "radius2": radius2,
        }
        shape = self._make_shape(params)
        super().__init__("Tapered Cylinder", params, shape)

    @staticmethod
    def _make_shape(params):
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
        height = params["height"]
        radius1 = params["radius1"]
        radius2 = params["radius2"]
        # OCC expects bottom radius, top radius, height
        return BRepPrimAPI_MakeCone(radius1, radius2, height).Shape()

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewTaperedCylinderCmd:
    def __init__(self):
        pass
    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Tapered Cylinder / Cone Parameters")
                layout = QFormLayout(self)
                self.height = QDoubleSpinBox()
                self.height.setRange(1, 1000)
                self.height.setValue(40.0)
                self.radius1 = QDoubleSpinBox()
                self.radius1.setRange(0, 1000)
                self.radius1.setValue(10.0)
                self.radius2 = QDoubleSpinBox()
                self.radius2.setRange(0, 1000)
                self.radius2.setValue(5.0)
                layout.addRow("Height", self.height)
                layout.addRow("Bottom Radius", self.radius1)
                layout.addRow("Top Radius", self.radius2)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        height = dlg.height.value()
        radius1 = dlg.radius1.value()
        radius2 = dlg.radius2.value()
        feat = TaperedCylinderFeature(height, radius1, radius2)
        # Add to document if available
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Tapered Cylinder created: h={height}, r1={radius1}, r2={radius2}", 3000)

# --- CAPSULE / PILL SHAPE TOOL (Selectable, like other shapes) ---
class CapsuleFeature(Feature):
    def __init__(self, height, radius):
        params = {
            "height": height,
            "radius": radius,
        }
        shape = self._make_shape(params)
        super().__init__("Capsule", params, shape)

    @staticmethod
    def _make_shape(params):
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
        height = params["height"]
        radius = params["radius"]
        cyl_height = max(0.0, height - 2 * radius)
        cyl = BRepPrimAPI_MakeCylinder(radius, cyl_height).Shape()
        sph1 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), radius, 0, 0.5 * 3.141592653589793).Shape()
        sph2 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, cyl_height), radius, 0.5 * 3.141592653589793, 3.141592653589793).Shape()
        fuse1 = BRepAlgoAPI_Fuse(cyl, sph1).Shape()
        capsule = BRepAlgoAPI_Fuse(fuse1, sph2).Shape()
        return capsule

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewCapsuleCmd:
    def __init__(self):
        pass
    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Capsule / Pill Parameters")
                layout = QFormLayout(self)
                self.height = QDoubleSpinBox()
                self.height.setRange(1, 1000)
                self.height.setValue(40.0)
                self.radius = QDoubleSpinBox()
                self.radius.setRange(0.1, 1000)
                self.radius.setValue(10.0)
                layout.addRow("Height", self.height)
                layout.addRow("Radius", self.radius)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        height = dlg.height.value()
        radius = dlg.radius.value()
        feat = CapsuleFeature(height, radius)
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Capsule created: height={height}, radius={radius}", 3000)

# --- ELLIPSOID SHAPE TOOL (Selectable, like other shapes) ---
class EllipsoidFeature(Feature):
    def __init__(self, rx, ry, rz):
        params = {
            "rx": rx,
            "ry": ry,
            "rz": rz,
        }
        shape = self._make_shape(params)
        super().__init__("Ellipsoid", params, shape)

    @staticmethod
    def _make_shape(params):
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.gp import gp_Trsf
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        rx = params["rx"]
        ry = params["ry"]
        rz = params["rz"]
        sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 1.0).Shape()
        trsf = gp_Trsf()
        trsf.SetValues(
            rx, 0, 0, 0,
            0, ry, 0, 0,
            0, 0, rz, 0
        )
        ellipsoid = BRepBuilderAPI_Transform(sphere, trsf, True).Shape()
        return ellipsoid

    def rebuild(self):
        self.shape = self._make_shape(self.params)

class NewEllipsoidCmd:
    def __init__(self):
        pass
    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Ellipsoid Parameters")
                layout = QFormLayout(self)
                self.rx = QDoubleSpinBox()
                self.rx.setRange(0.1, 1000)
                self.rx.setValue(20.0)
                self.ry = QDoubleSpinBox()
                self.ry.setRange(0.1, 1000)
                self.ry.setValue(10.0)
                self.rz = QDoubleSpinBox()
                self.rz.setRange(0.1, 1000)
                self.rz.setValue(5.0)
                layout.addRow("Radius X", self.rx)
                layout.addRow("Radius Y", self.ry)
                layout.addRow("Radius Z", self.rz)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        rx = dlg.rx.value()
        ry = dlg.ry.value()
        rz = dlg.rz.value()
        feat = EllipsoidFeature(rx, ry, rz)
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Ellipsoid created: rx={rx}, ry={ry}, rz={rz}", 3000)

# --- PROJECT MANAGEMENT COMMANDS ---
class SaveProjectCmd:
    def __init__(self):
        pass
    
    def run(self, mw):
        try:
            from PySide6.QtWidgets import QFileDialog
            from adaptivecad.command_defs import DOCUMENT
            import json
            import os
            
            if not DOCUMENT:
                mw.win.statusBar().showMessage("No shapes in document to save", 3000)
                return
            
            # Get save location
            path, _filter = QFileDialog.getSaveFileName(
                mw.win, "Save AdaptiveCAD Project", filter="AdaptiveCAD Project (*.acad);;JSON Files (*.json)"
            )
            if not path:
                return
            
            # Create project data structure
            project_data = {
                "version": "1.0",
                "type": "AdaptiveCAD Project",
                "features": []
            }
            
            # Save each feature's data
            for idx, feat in enumerate(DOCUMENT):
                feature_data = {
                    "id": idx,
                    "name": feat.name,
                    "params": feat.params,
                    "type": type(feat).__name__
                }
                project_data["features"].append(feature_data)
            
            # Write project file
            with open(path, 'w') as f:
                json.dump(project_data, f, indent=2)
            
            mw.win.statusBar().showMessage(f"Project saved: {os.path.basename(path)}", 3000)
            
        except Exception as e:
            mw.win.statusBar().showMessage(f"Error saving project: {str(e)}", 5000)
            print(f"Save project error: {str(e)}")

class OpenProjectCmd:
    def __init__(self):
        pass
    
    def run(self, mw):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            from adaptivecad.command_defs import DOCUMENT
            import json
            import os
            
            # Get file to open
            path, _filter = QFileDialog.getOpenFileName(
                mw.win, "Open AdaptiveCAD Project", filter="AdaptiveCAD Project (*.acad);;JSON Files (*.json);;All Files (*.*)"
            )
            if not path:
                return
            
            if not os.path.exists(path):
                QMessageBox.warning(mw.win, "File Not Found", f"Could not find file: {path}")
                return
            
            # Ask if user wants to clear current document
            if DOCUMENT:
                reply = QMessageBox.question(
                    mw.win, "Clear Current Project?", 
                    "Opening a project will replace the current shapes. Continue?",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # Load project file
            with open(path, 'r') as f:
                project_data = json.load(f)
            
            # Clear current document
            DOCUMENT.clear()
            mw.view._display.EraseAll()
            
            # Recreate features from project data
            features_loaded = 0
            for feat_data in project_data.get("features", []):
                try:
                    feat_type = feat_data.get("type", "")
                    feat_name = feat_data.get("name", "Unknown")
                    feat_params = feat_data.get("params", {})
                    
                    # Try to recreate the feature based on its type
                    feature = None
                    if feat_type == "SuperellipseFeature":
                        feature = SuperellipseFeature(
                            feat_params.get("rx", 25.0),
                            feat_params.get("ry", 15.0),
                            feat_params.get("n", 2.5),
                            feat_params.get("segments", 60)
                        )
                    elif feat_type == "PiCurveShellFeature":
                        feature = PiCurveShellFeature(
                            feat_params.get("base_radius", 20.0),
                            feat_params.get("height", 40.0),
                            feat_params.get("freq", 3.0),
                            feat_params.get("amp", 5.0),
                            feat_params.get("phase", 0.0),
                            feat_params.get("n_u", 60),
                            feat_params.get("n_v", 30)
                        )
                    elif feat_type == "HelixFeature":
                        feature = HelixFeature(
                            feat_params.get("radius", 20.0),
                            feat_params.get("pitch", 5.0),
                            feat_params.get("height", 40.0),
                            feat_params.get("n_points", 250)
                        )
                    elif feat_type == "TaperedCylinderFeature":
                        feature = TaperedCylinderFeature(
                            feat_params.get("height", 40.0),
                            feat_params.get("radius1", 10.0),
                            feat_params.get("radius2", 5.0)
                        )
                    elif feat_type == "CapsuleFeature":
                        feature = CapsuleFeature(
                            feat_params.get("height", 40.0),
                            feat_params.get("radius", 10.0)
                        )
                    elif feat_type == "EllipsoidFeature":
                        feature = EllipsoidFeature(
                            feat_params.get("rx", 20.0),
                            feat_params.get("ry", 10.0),
                            feat_params.get("rz", 5.0)
                        )
                    # For basic shapes, we'll need to import them from command_defs
                    else:
                        # Try to create basic shapes using the existing command system
                        from adaptivecad.command_defs import Feature
                        
                        # Create a generic feature - this won't have the actual shape
                        # but will preserve the parameter data
                        feature = Feature(feat_name, feat_params, None)
                    
                    if feature:
                        DOCUMENT.append(feature)
                        if hasattr(feature, 'shape') and feature.shape:
                            mw.view._display.DisplayShape(feature.shape, update=False)
                        features_loaded += 1
                        
                except Exception as e:
                    print(f"Error loading feature {feat_data.get('name', 'Unknown')}: {e}")
                    continue
            
            # Update display
            mw.view._display.FitAll()
            
            mw.win.statusBar().showMessage(
                f"Project loaded: {os.path.basename(path)} ({features_loaded} features)", 3000
            )
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(mw.win, "Invalid Project File", f"Could not parse project file: {str(e)}")
        except Exception as e:
            QMessageBox.critical(mw.win, "Error Loading Project", f"Error loading project: {str(e)}")
            print(f"Open project error: {str(e)}")

# --- MAIN WINDOW AND APPLICATION ---
class MainWindow:
    def __init__(self):
        if not HAS_GUI:
            print("GUI dependencies not available. Cannot create MainWindow.")
            return
            
        # Initialize the application
        self.app = QApplication.instance() or QApplication([])
        
        # Initialize state variables
        self.selected_feature = None
        self.property_panel = None
        self.dimension_panel = None
        
        # Create the main window
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD - Advanced Shapes & Modeling Tools")
        self.win.resize(1024, 768)
        
        # Create central widget with the OpenCascade viewer
        from OCC.Display.qtDisplay import qtViewer3d
        central = QWidget()
        layout = QVBoxLayout(central)
        self.view = qtViewer3d(central)
        layout.addWidget(self.view)
        self.win.setCentralWidget(central)
        
        # Initialize view
        self.view._display.set_bg_gradient_color([50, 50, 50], [10, 10, 10])
        self.view._display.display_triedron()
        self.view._display.View.SetProj(1, 1, 1)
        self.view._display.View.SetScale(300)
        
        # Initialize ViewCube
        self.viewcube = ViewCubeWidget(self.view._display, self.view)
        self._position_viewcube()
        self.viewcube.show()
        self.setup_view_events()
        
        # Setup selection handling
        self._setup_selection_handling()
        
        # Setup UI
        self._create_menus_and_toolbar()
        
        # Create status bar
        self.win.statusBar().showMessage("AdaptiveCAD Advanced Shapes & Modeling Tools Ready")
        
    def _setup_selection_handling(self):
        """Setup selection handling for objects in the 3D view."""
        try:
            # Connect selection changed signal
            def on_selection_changed():
                self._on_object_selected()
            
            # Set up mouse click handling for selection
            self.view._display.register_select_callback(on_selection_changed)
        except Exception as e:
            print(f"Warning: Could not setup selection handling: {e}")
    
    def _on_object_selected(self):
        """Handle object selection in the 3D view."""
        try:
            from adaptivecad.command_defs import DOCUMENT
            
            # Get selected objects from the display
            selected_shapes = self.view._display.GetSelectedShapes()
            
            if selected_shapes:
                # Find the feature that corresponds to the selected shape
                for i, feature in enumerate(DOCUMENT):
                    if hasattr(feature, 'shape') and feature.shape in selected_shapes:
                        self.selected_feature = feature
                        self._update_property_panel(feature)
                        self.win.statusBar().showMessage(f"Selected: {feature.name}", 3000)
                        return
                        
                # If no matching feature found, clear selection
                self.selected_feature = None
                self._clear_property_panel()
            else:
                self.selected_feature = None
                self._clear_property_panel()
                
        except Exception as e:
            print(f"Error handling selection: {e}")
    
    def _update_property_panel(self, feature):
        """Update the property panel with the selected feature's properties."""
        if self.property_panel is None or not hasattr(self, 'property_layout'):
            return
            
        # Clear existing property widgets
        self._clear_property_panel()
        
        # Add feature name
        name_label = QLabel(f"Selected: {feature.name}")
        name_label.setStyleSheet("font-weight: bold; color: blue; margin-bottom: 5px;")
        self.property_layout.insertWidget(2, name_label)
        
        # Add feature parameters
        if hasattr(feature, 'params') and feature.params:
            params_label = QLabel("Parameters:")
            params_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            self.property_layout.insertWidget(3, params_label)
            
            # Create editable parameter fields
            for key, value in feature.params.items():
                if key == 'consumed':  # Skip internal flags
                    continue
                    
                param_widget = QWidget()
                param_layout = QHBoxLayout(param_widget)
                param_layout.setContentsMargins(0, 2, 0, 2)
                
                # Parameter name
                param_label = QLabel(f"{key}:")
                param_label.setMinimumWidth(80)
                param_layout.addWidget(param_label)
                  # Parameter value (editable if numeric)
                if isinstance(value, (int, float)):
                    editor = QLineEdit(str(value))
                    editor.setMaximumWidth(100)
                    
                    def make_param_setter(param_key, param_type):
                        def setter():
                            try:
                                new_value = param_type(editor.text())
                                feature.params[param_key] = new_value
                                # Rebuild the feature if it has a rebuild method
                                if hasattr(feature, 'rebuild'):
                                    feature.rebuild()
                                # Update the display
                                if hasattr(self, 'view') and hasattr(self.view, '_display'):
                                    from adaptivecad.command_defs import rebuild_scene
                                    rebuild_scene(self.view._display)
                                self.win.statusBar().showMessage(f"Updated {param_key} to {new_value}", 2000)
                            except ValueError:
                                editor.setText(str(feature.params[param_key]))  # Revert on error
                                self.win.statusBar().showMessage(f"Invalid value for {param_key}", 2000)
                        return setter
                    
                    editor.editingFinished.connect(make_param_setter(key, type(value)))
                    param_layout.addWidget(editor)
                else:
                    # Non-editable display
                    value_label = QLabel(str(value))
                    value_label.setStyleSheet("color: gray;")
                    param_layout.addWidget(value_label)
                
                param_layout.addStretch()
                self.property_layout.insertWidget(self.property_layout.count() - 1, param_widget)
        
        # Add feature type info
        type_label = QLabel(f"Type: {type(feature).__name__}")
        type_label.setStyleSheet("color: gray; margin-top: 10px;")
        self.property_layout.insertWidget(self.property_layout.count() - 1, type_label)
        
    def _create_menus_and_toolbar(self):
        """Create all menus and toolbar in one method to avoid variable scope issues."""
        # Create menu bar
        menubar = self.win.menuBar()
        
        # Create File menu
        file_menu = menubar.addMenu("File")
        
        # Add Import submenu
        import_menu = file_menu.addMenu("Import")
          # Add STL/STEP import (Simple with Progress)
        import_simple_action = QAction("STL/STEP (with Progress)", self.win)
        import_simple_action.triggered.connect(lambda: self._run_command(MinimalImportCmd()))
        import_menu.addAction(import_simple_action)
        
        # Add separator
        file_menu.addSeparator()
        
        # Add Export submenu
        export_menu = file_menu.addMenu("Export")
        
        # Add STL export
        export_stl_action = QAction("Export STL", self.win)
        export_stl_action.triggered.connect(lambda: self._run_command(ExportStlCmd()))
        export_menu.addAction(export_stl_action)
        
        # Add AMA export
        export_ama_action = QAction("Export AMA", self.win)
        export_ama_action.triggered.connect(lambda: self._run_command(ExportAmaCmd()))
        export_menu.addAction(export_ama_action)
        
        # Add G-Code export
        export_gcode_action = QAction("Export G-Code", self.win)
        export_gcode_action.triggered.connect(lambda: self._run_command(ExportGCodeCmd()))
        export_menu.addAction(export_gcode_action)
        
        # Add G-Code Direct export
        export_gcode_direct_action = QAction("Export G-Code (Direct)", self.win)
        export_gcode_direct_action.triggered.connect(lambda: self._run_command(ExportGCodeDirectCmd()))
        export_menu.addAction(export_gcode_direct_action)
        
        # Add separator
        file_menu.addSeparator()
        
        # Add Save/Open project functionality
        save_action = QAction("Save Project...", self.win)
        save_action.triggered.connect(lambda: self._run_command(SaveProjectCmd()))
        file_menu.addAction(save_action)
        
        open_action = QAction("Open Project...", self.win)
        open_action.triggered.connect(lambda: self._run_command(OpenProjectCmd()))
        file_menu.addAction(open_action)
        
        # Add separator and Exit
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self.win)
        exit_action.triggered.connect(self.win.close)
        file_menu.addAction(exit_action)
        
        # Create Basic Shapes menu
        basic_menu = menubar.addMenu("Basic Shapes")
        
        # Add Box tool
        box_action = QAction("Box", self.win)
        box_action.triggered.connect(lambda: self._run_command(NewBoxCmd()))
        basic_menu.addAction(box_action)
        
        # Add Cylinder tool
        cyl_action = QAction("Cylinder", self.win)
        cyl_action.triggered.connect(lambda: self._run_command(NewCylCmd()))
        basic_menu.addAction(cyl_action)
        
        # Add Ball tool
        ball_action = QAction("Ball", self.win)
        ball_action.triggered.connect(lambda: self._run_command(NewBallCmd()))
        basic_menu.addAction(ball_action)
        
        # Add Torus tool
        torus_action = QAction("Torus", self.win)
        torus_action.triggered.connect(lambda: self._run_command(NewTorusCmd()))
        basic_menu.addAction(torus_action)
        
        # Add Cone tool
        cone_action = QAction("Cone", self.win)
        cone_action.triggered.connect(lambda: self._run_command(NewConeCmd()))
        basic_menu.addAction(cone_action)
        
        # Create Advanced Shapes menu
        adv_menu = menubar.addMenu("Advanced Shapes")
        
        # Add Superellipse tool
        super_action = QAction("Superellipse", self.win)
        super_action.triggered.connect(lambda: self._run_command(NewSuperellipseCmd()))
        adv_menu.addAction(super_action)
        
        # Add Pi Curve Shell tool
        pi_shell_action = QAction("Pi Curve Shell (πₐ)", self.win)
        pi_shell_action.triggered.connect(lambda: self._run_command(NewPiCurveShellCmd()))
        adv_menu.addAction(pi_shell_action)
        
        # Add Helix tool
        helix_action = QAction("Helix/Spiral", self.win)
        helix_action.triggered.connect(lambda: self._run_command(NewHelixCmd()))
        adv_menu.addAction(helix_action)
        
        # Add Tapered Cylinder tool
        tapered_action = QAction("Tapered Cylinder", self.win)
        tapered_action.triggered.connect(lambda: self._run_command(NewTaperedCylinderCmd()))
        adv_menu.addAction(tapered_action)
        
        # Add Capsule tool
        capsule_action = QAction("Capsule/Pill", self.win)
        capsule_action.triggered.connect(lambda: self._run_command(NewCapsuleCmd()))
        adv_menu.addAction(capsule_action)
        
        # Add Ellipsoid tool
        ellipsoid_action = QAction("Ellipsoid", self.win)
        ellipsoid_action.triggered.connect(lambda: self._run_command(NewEllipsoidCmd()))
        adv_menu.addAction(ellipsoid_action)
        
        # Create Modeling Tools menu
        modeling_menu = menubar.addMenu("Modeling Tools")
        
        # Add Move tool
        move_action = QAction("Move", self.win)
        move_action.triggered.connect(lambda: self._run_command(MoveCmd()))
        modeling_menu.addAction(move_action)
        
        # Add Scale tool
        scale_action = QAction("Scale", self.win)
        scale_action.triggered.connect(lambda: self._run_command(ScaleCmd()))
        modeling_menu.addAction(scale_action)
        
        # Add separator
        modeling_menu.addSeparator()
        
        # Add Union tool
        union_action = QAction("Union", self.win)
        union_action.triggered.connect(lambda: self._run_command(UnionCmd()))
        modeling_menu.addAction(union_action)
        
        # Add Cut tool
        cut_action = QAction("Cut", self.win)
        cut_action.triggered.connect(lambda: self._run_command(CutCmd()))
        modeling_menu.addAction(cut_action)
        
        # Add Intersect tool
        intersect_action = QAction("Intersect", self.win)
        intersect_action.triggered.connect(lambda: self._run_command(IntersectCmd()))
        modeling_menu.addAction(intersect_action)
        
        # Add Shell tool
        shell_action = QAction("Shell", self.win)
        shell_action.triggered.connect(lambda: self._run_command(ShellCmd()))
        modeling_menu.addAction(shell_action)
        
        # Add separator
        modeling_menu.addSeparator()
        
        # Add Delete tool
        delete_action = QAction("Delete", self.win)
        delete_action.triggered.connect(self._delete_selected)
        modeling_menu.addAction(delete_action)
        
        # Create Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Add View settings submenu
        view_menu = settings_menu.addMenu("View")
        
        # Add Properties Panel toggle
        properties_action = QAction("Show Properties Panel", self.win, checkable=True)
        properties_action.setChecked(False)
        properties_action.triggered.connect(self._toggle_properties_panel)
        view_menu.addAction(properties_action)
        
        # Add Dimension Selector toggle
        dimension_action = QAction("Show Dimension Selector", self.win, checkable=True)
        dimension_action.setChecked(False)
        dimension_action.triggered.connect(self._toggle_dimension_panel)
        view_menu.addAction(dimension_action)
        
        view_menu.addSeparator()
        
        # Add View Cube toggle
        viewcube_action = QAction("Show View Cube", self.win, checkable=True)
        viewcube_action.setChecked(True)
        def toggle_cube(checked):
            self.viewcube.setVisible(checked)
        viewcube_action.triggered.connect(toggle_cube)
        view_menu.addAction(viewcube_action)
        
        # Add View Background settings
        view_bg_menu = view_menu.addMenu("Background Color")
        bg_dark_action = QAction("Dark", self.win)
        bg_dark_action.triggered.connect(lambda: self.view._display.set_bg_gradient_color([50, 50, 50], [10, 10, 10]))
        view_bg_menu.addAction(bg_dark_action)
        
        bg_light_action = QAction("Light", self.win)
        bg_light_action.triggered.connect(lambda: self.view._display.set_bg_gradient_color([230, 230, 230], [200, 200, 200]))
        view_bg_menu.addAction(bg_light_action)
        
        bg_blue_action = QAction("Blue", self.win)
        bg_blue_action.triggered.connect(lambda: self.view._display.set_bg_gradient_color([5, 20, 76], [5, 39, 175]))
        view_bg_menu.addAction(bg_blue_action)
        
        # Add Tessellation quality submenu
        tessellation_menu = settings_menu.addMenu("Tessellation Quality")
        
        # Add different tessellation quality options
        def set_tessellation(deflection, angle):
            settings.MESH_DEFLECTION = deflection
            settings.MESH_ANGLE = angle
            # Update status bar to confirm the change
            self.win.statusBar().showMessage(f"Tessellation set to: deflection={deflection}, angle={angle}", 3000)
            
        high_quality = QAction("High Quality", self.win)
        high_quality.triggered.connect(lambda: set_tessellation(0.005, 0.01))
        tessellation_menu.addAction(high_quality)
        
        normal_quality = QAction("Normal Quality", self.win)
        normal_quality.triggered.connect(lambda: set_tessellation(0.01, 0.05))
        tessellation_menu.addAction(normal_quality)
        
        low_quality = QAction("Low Quality (Faster)", self.win)
        low_quality.triggered.connect(lambda: set_tessellation(0.05, 0.1))
        tessellation_menu.addAction(low_quality)
        
        # Add option to toggle triedron visibility
        triedron_action = QAction("Show Axes Indicator", self.win, checkable=True)
        triedron_action.setChecked(True)
        triedron_action.triggered.connect(lambda checked: self.view._display.display_triedron() if checked else self.view._display.hide_triedron())
        view_menu.addAction(triedron_action)
        
        # Create a main toolbar with commonly used shapes
        self.toolbar = self.win.addToolBar("Common Shapes")
        self.toolbar.addAction(box_action)
        self.toolbar.addAction(cyl_action)
        self.toolbar.addAction(super_action)
        self.toolbar.addAction(pi_shell_action)
        
        # Add separator
        self.toolbar.addSeparator()
        
        # Add common modeling tools to toolbar
        self.toolbar.addAction(move_action)
        self.toolbar.addAction(union_action)
        self.toolbar.addAction(cut_action)
        self.toolbar.addAction(delete_action)
          # Create Help menu
        help_menu = menubar.addMenu("Help")
        
        # Add About action
        about_action = QAction("About AdaptiveCAD", self.win)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        # Add Documentation links
        docs_menu = help_menu.addMenu("Documentation")
        
        adaptive_pi_action = QAction("Adaptive Pi Axioms", self.win)
        adaptive_pi_action.triggered.connect(lambda: self._show_doc_message("Adaptive Pi Axioms", 
            "Please see ADAPTIVE_PI_AXIOMS.md in the project root directory for the complete formal axiom set."))
        docs_menu.addAction(adaptive_pi_action)
        
        modeling_tools_action = QAction("Modeling Tools Reference", self.win)
        modeling_tools_action.triggered.connect(lambda: self._show_doc_message("Modeling Tools", 
            "Please see MODELING_TOOLS.md in the project root directory for details on all available modeling tools."))
        docs_menu.addAction(modeling_tools_action)
    
    def _run_command(self, cmd):
        try:
            # Store reference to command to prevent garbage collection during execution
            self._current_command = cmd
            cmd.run(self)
        except Exception as e:
            QMessageBox.critical(self.win, "Error", f"Error running command: {str(e)}")
            print(f"Command error: {str(e)}")
            print(traceback.format_exc())
        finally:
            # Clear the reference after some delay to allow signals to complete
            # Don't clear immediately as async operations might still be running
            if hasattr(self, '_current_command'):
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1000, lambda: setattr(self, '_current_command', None))
    
    def _delete_selected(self):
        """Delete the currently selected feature."""
        if self.selected_feature is None:
            QMessageBox.information(self.win, "Delete", "No object selected for deletion.")
            return
            
        try:
            from adaptivecad.command_defs import DOCUMENT, rebuild_scene
            
            if self.selected_feature in DOCUMENT:
                DOCUMENT.remove(self.selected_feature)
                self.selected_feature = None
                self._clear_property_panel()
                rebuild_scene(self.view._display)
                self.win.statusBar().showMessage("Object deleted.", 2000)
            else:
                self.win.statusBar().showMessage("Could not delete object.", 2000)
        except Exception as e:
            QMessageBox.critical(self.win, "Error", f"Error deleting object: {str(e)}")
    
    def _toggle_properties_panel(self, checked):
        """Toggle the properties panel visibility."""
        if checked:
            self._create_properties_panel()
        else:
            self._hide_properties_panel()
    
    def _create_properties_panel(self):
        """Create and show the properties panel."""
        if self.property_panel is not None:
            return  # Already created
            
        # Create a dock widget for properties
        self.property_panel = QDockWidget("Properties", self.win)
        self.property_panel.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create the properties widget
        properties_widget = QWidget()
        self.property_layout = QVBoxLayout(properties_widget)
        
        # Add a label
        label = QLabel("Object Properties")
        label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        self.property_layout.addWidget(label)
        
        # Add instructions
        instructions = QLabel("Select an object from the 3D view to see its properties here.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray; margin-bottom: 10px;")
        self.property_layout.addWidget(instructions)
        
        # Add stretch to push content to top
        self.property_layout.addStretch()
        
        self.property_panel.setWidget(properties_widget)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.property_panel)
        self.property_panel.show()
    
    def _hide_properties_panel(self):
        """Hide the properties panel."""
        if self.property_panel is not None:
            self.property_panel.hide()
            self.win.removeDockWidget(self.property_panel)
            self.property_panel = None
    
    def _clear_property_panel(self):
        """Clear the property panel contents."""
        if self.property_panel is not None and hasattr(self, 'property_layout'):
            # Clear all widgets except the first two (label and instructions)
            while self.property_layout.count() > 3:  # Keep label, instructions, and stretch
                child = self.property_layout.takeAt(2)  # Remove items after instructions
                if child.widget():
                    child.widget().deleteLater()
    
    def _toggle_dimension_panel(self, checked):
        """Toggle the dimension selector panel visibility."""
        if checked:
            self._create_dimension_panel()
        else:
            self._hide_dimension_panel()
    
    def _create_dimension_panel(self):
        """Create and show the dimension selector panel."""
        if self.dimension_panel is not None:
            return  # Already created
            
        # Create a dock widget for dimension selection
        self.dimension_panel = QDockWidget("Dimension Selector", self.win)
        self.dimension_panel.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create the dimension widget
        dimension_widget = QWidget()
        layout = QVBoxLayout(dimension_widget)
        
        # Add title
        title = QLabel("Multi-Dimensional View Control")
        title.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Add dimension selector
        dim_label = QLabel("Active Dimensions:")
        layout.addWidget(dim_label)
        
        # Create checkboxes for X, Y, Z, and additional dimensions
        self.dim_checkboxes = {}
        dimensions = ['X', 'Y', 'Z', 'W', 'U', 'V']
        
        for i, dim in enumerate(dimensions):
            checkbox = QCheckBox(f"Dimension {dim}")
            # Default to X, Y, Z enabled for 3D view
            if i < 3:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)
            self.dim_checkboxes[dim] = checkbox
            layout.addWidget(checkbox)
        
        # Add slice controls for higher dimensions
        layout.addWidget(QLabel("Slice Controls:"))
        
        # Create sliders for slicing through higher dimensions
        self.slice_controls = {}
        for dim in ['W', 'U', 'V']:
            group = QWidget()
            group_layout = QHBoxLayout(group)
            
            label = QLabel(f"{dim}:")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            value_label = QLabel("50")
            
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))
            
            group_layout.addWidget(label)
            group_layout.addWidget(slider)
            group_layout.addWidget(value_label)
            
            self.slice_controls[dim] = {'slider': slider, 'value_label': value_label}
            layout.addWidget(group)
        
        # Add projection controls
        layout.addWidget(QLabel("Projection:"))
        
        projection_combo = QComboBox()
        projection_combo.addItems(['Orthographic', 'Perspective', 'Isometric'])
        layout.addWidget(projection_combo)
        
        # Add view preset buttons
        layout.addWidget(QLabel("View Presets:"))
        
        preset_buttons = QHBoxLayout()
        
        xy_btn = QPushButton("X-Y")
        xz_btn = QPushButton("X-Z")
        yz_btn = QPushButton("Y-Z")
        iso_btn = QPushButton("ISO")
        
        xy_btn.clicked.connect(lambda: self._set_view_preset('XY'))
        xz_btn.clicked.connect(lambda: self._set_view_preset('XZ'))
        yz_btn.clicked.connect(lambda: self._set_view_preset('YZ'))
        iso_btn.clicked.connect(lambda: self._set_view_preset('ISO'))
        
        preset_buttons.addWidget(xy_btn)
        preset_buttons.addWidget(xz_btn)
        preset_buttons.addWidget(yz_btn)
        preset_buttons.addWidget(iso_btn)
        
        preset_widget = QWidget()
        preset_widget.setLayout(preset_buttons)
        layout.addWidget(preset_widget)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        self.dimension_panel.setWidget(dimension_widget)
        self.win.addDockWidget(Qt.RightDockWidgetArea, self.dimension_panel)
        self.dimension_panel.show()
    
    def _hide_dimension_panel(self):
        """Hide the dimension selector panel."""
        if self.dimension_panel is not None:
            self.dimension_panel.hide()
            self.win.removeDockWidget(self.dimension_panel)
            self.dimension_panel = None

    def _set_view_preset(self, preset):
        """Set a view preset for the 3D view."""
        try:
            if preset == 'XY':
                self.view._display.View.SetProj(0, 0, 1)  # Top view
            elif preset == 'XZ':
                self.view._display.View.SetProj(0, -1, 0)  # Front view
            elif preset == 'YZ':
                self.view._display.View.SetProj(1, 0, 0)  # Right view
            elif preset == 'ISO':
                self.view._display.View.SetProj(1, 1, 1)  # Isometric view
            
            self.view._display.FitAll()
            self.win.statusBar().showMessage(f"View set to {preset}", 2000)
        except Exception as e:
            print(f"Error setting view preset {preset}: {e}")
            self.win.statusBar().showMessage(f"Error setting view preset: {e}", 3000)
            print(f"Error setting view preset {preset}: {e}")
    
    def _show_not_implemented(self, feature_name):
        QMessageBox.information(self.win, "Not Implemented", 
                               f"{feature_name} functionality is not yet implemented.\n"
                               "This feature will be added in a future version.")
    
    def run(self):
        if not HAS_GUI:
            print("Error: Cannot run GUI without PySide6 and OCC.Display dependencies.")
            return 1
            
        # Show the window and run the application
        self.win.show()
        return self.app.exec()
        
    def _position_viewcube(self):
        if hasattr(self, 'viewcube') and self.viewcube.parent() is self.view:
            self.viewcube.move(self.view.width() - self.viewcube.width() - 10, 10)
            
    def setup_view_events(self):
        # Connect view resize event to reposition viewcube
        original_resize = self.view.resizeEvent
        def new_resize(event):
            original_resize(event)
            self._position_viewcube()
        self.view.resizeEvent = new_resize
            
    def _show_about(self):
        QMessageBox.about(self.win, "About AdaptiveCAD",
            """<h2>AdaptiveCAD</h2>
<p>A curvature-first CAD/CAM system based on the Adaptive Pi Geometry.</p>
<p>This application demonstrates parametric shapes and modeling tools
that implement the πₐ (Adaptive Pi) geometry principles.</p>
<p>For more information, see the documentation files in the project root.</p>
""")
            
    def _show_doc_message(self, title, message):
        QMessageBox.information(self.win, title, message)
    
def main() -> None:
    MainWindow().run()

if __name__ == "__main__":
    main()
