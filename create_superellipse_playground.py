"""Create a proper version of playground.py with MainWindow and SuperellipseFeature."""

import os

# Load the backup to start from
playground_path = r"d:\SuperCAD\AdaptiveCAD\adaptivecad\gui\playground.py"
backup_path = r"d:\SuperCAD\AdaptiveCAD\adaptivecad\gui\playground.py.original"

if not os.path.exists(backup_path):
    print(f"ERROR: Backup file {backup_path} not found.")
    exit(1)

# Read the backup file to get the full content
with open(backup_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make a backup of our current minimal version
minimal_backup = playground_path + '.minimal'
with open(playground_path, 'r', encoding='utf-8') as f:
    minimal_content = f.read()

with open(minimal_backup, 'w', encoding='utf-8') as f:
    f.write(minimal_content)

# Extract feature definitions and create proper playground.py
import re
from adaptivecad.command_defs import Feature

# Create a new version with both MainWindow properly defined and SuperellipseFeature included
new_playground = '''"""Simplified GUI playground with optional dependencies."""

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
        QPushButton, QDockWidget, QLineEdit, QToolBar, QToolButton, QMenu,
        QAction, QDialogButtonBox, QFormLayout, QDoubleSpinBox, QSpinBox
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
        MoveCmd,
        UnionCmd,
        CutCmd,
        NewBallCmd,
        NewTorusCmd,
        NewConeCmd
    )

# Define SuperellipseFeature at module level regardless of GUI availability
from adaptivecad.command_defs import Feature

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

class MainWindow:
    def __init__(self):
        if not HAS_GUI:
            print("GUI dependencies not available. Cannot create MainWindow.")
            return
            
        # Initialize the application
        self.app = QApplication.instance() or QApplication([])
        
        # Create the main window
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD - Superellipse Demo")
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
        
        # Create a toolbar with shapes
        self.toolbar = self.win.addToolBar("Shapes")
        
        # Add Superellipse tool
        action = QAction("Superellipse", self.win)
        action.triggered.connect(lambda: self._run_command(NewSuperellipseCmd()))
        self.toolbar.addAction(action)
        
        # Add Box tool for comparison
        box_action = QAction("Box", self.win)
        box_action.triggered.connect(lambda: self._run_command(NewBoxCmd()))
        self.toolbar.addAction(box_action)
        
        # Add Cylinder tool
        cyl_action = QAction("Cylinder", self.win)
        cyl_action.triggered.connect(lambda: self._run_command(NewCylCmd()))
        self.toolbar.addAction(cyl_action)
        
        # Create status bar
        self.win.statusBar().showMessage("AdaptiveCAD Superellipse Demo Ready")
        
    def _run_command(self, cmd):
        try:
            cmd.run(self)
        except Exception as e:
            QMessageBox.critical(self.win, "Error", f"Error running command: {str(e)}")
            print(f"Command error: {str(e)}")
            print(traceback.format_exc())
    
    def run(self):
        if not HAS_GUI:
            print("Error: Cannot run GUI without PySide6 and OCC.Display dependencies.")
            return 1
            
        # Show the window and run the application
        self.win.show()
        return self.app.exec()

def main() -> None:
    MainWindow().run()

if __name__ == "__main__":
    main()
'''

# Write the new playground file
with open(playground_path, 'w', encoding='utf-8') as f:
    f.write(new_playground)

print(f"Created proper playground.py with Superellipse feature at {playground_path}")
print("Try running 'python -m adaptivecad.gui.playground' now")
