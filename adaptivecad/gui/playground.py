"""Minimal PySide6 + pythonOCC viewer prototype.

This module provides the ``AdaptiveCAD Playground`` application described in
``README.md``.  It launches a basic 3-D viewer using ``pythonocc-core`` and
``PySide6``.  The viewer displays a demo scene constructed from the geometric
primitives available in the package.  It is intentionally lightweight so that
contributors can quickly run ``python -m adaptivecad.gui.playground`` after
installing the optional GUI dependencies.

The GUI dependencies are not required for the rest of the package; therefore,
imports are done lazily with user-friendly error messages if the packages are
missing.

Dependencies:
    - pythonocc-core
    - PySide6 or PyQt5

Install with:
    conda install -c conda-forge pythonocc-core pyside6

Navigation:
    - Left mouse drag: Rotate
    - Middle mouse/wheel: Zoom
    - Shift + Right mouse: Dynamic zoom
    - Press 'R': Reload the demo scene
"""
from __future__ import annotations

import sys
import math
import numpy as np
from math import cos, sin, pi
from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire,
)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.gp import gp_Pnt
from OCC.Core.V3d import V3d_TypeOfAntialiasing as AA


def _require_gui_modules():
    """Import optional GUI modules, raising RuntimeError if unavailable."""
    try:
        # Initialize the Qt backend before importing the OCC Display modules
        from OCC.Display import backend
        backend.load_backend("qt-pyqt5")  # Use PyQt5 backend instead
        
        # Import required UI modules
        from PyQt5.QtWidgets import QApplication, QMainWindow
        from OCC.Display.qtDisplay import qtViewer3d  # type: ignore
        from OCC.Core.V3d import V3d_TypeOfAntialiasing  # For anti-aliasing
    except ImportError:
        # Show a helpful error message for users
        print("GUI extras not installed. Run:\n   conda install pyside6 pythonocc-core")
        qtViewer3d = None
        QMainWindow = object
        QApplication = lambda x: None
        V3d_TypeOfAntialiasing = None
        return QApplication, QMainWindow, qtViewer3d
    except Exception as exc:  # pragma: no cover - import error path
        raise RuntimeError(
            "PyQt5 and pythonocc-core are required to run the playground. Error: " + str(exc)
        ) from exc
    return QApplication, QMainWindow, qtViewer3d, V3d_TypeOfAntialiasing


def helix_wire(radius=20, pitch=5, height=40, n=250):
    """Create a helix wire shape."""
    try:
        ts = np.linspace(0, 2 * pi * height / pitch, n)
        pts = [gp_Pnt(radius * cos(t), radius * sin(t), pitch * t / (2 * pi)) for t in ts]
        wire = BRepBuilderAPI_MakeWire()
        for a, b in zip(pts[:-1], pts[1:]):
            wire.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
        return wire.Wire()
    except Exception as exc:
        print(f"Error creating helix: {exc}")
        return None


def on_select(shape, *k):
    """Selection callback for interactive shape selection."""
    try:
        t = shape.ShapeType()
        print("Selected", t, "-", shape)
    except Exception as exc:
        print(f"Selection error: {exc}")


def _demo_primitives(display):
    """Create a demo scene using simple primitives."""
    if display is None:
        return
        
    try:
        from adaptivecad import geom, linalg
    except ImportError as exc:
        print(f"Error loading modules: {exc}")
        print("Make sure pythonocc-core and PySide6 are installed:")
        print("    conda install -c conda-forge pythonocc-core pyside6")
        return
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return

    try:
        # Clear previous demo if any
        display.EraseAll()
        
        # Create a box and a helix
        box = BRepPrimAPI_MakeBox(50, 50, 10).Shape()
        helx = helix_wire()
        
        # Display the shapes
        display.DisplayShape(box, update=False, transparency=0.2)
        if helx:  # Only display helix if created successfully
            display.DisplayShape(helx, color="YELLOW")
        
        # Enable visualization features
        display.show_triedron()          # XYZ axes in lower left
        display.enable_grid()            # dotted construction grid
        display.register_select_callback(on_select)
        display.SetSelectionModeEdge()   # edges selectable
        
        # Apply shading for better visualization
        display.SetShadingMode(3)  # Phong shading
        
        # Apply anti-aliasing if available
        try:
            display.View.SetAntialiasingMode(AA.V3d_MSAA_8X)
        except Exception as exc:
            print(f"Could not enable anti-aliasing: {exc}")
        
        display.FitAll()
    except Exception as exc:
        print(f"Error creating demo scene: {exc}")
        # Fall back to simpler demo if full scene fails
        try:
            simple_shape = BRepPrimAPI_MakeBox(100, 100, 100).Shape()
            display.DisplayShape(simple_shape)
            display.FitAll()
        except Exception as e:
            print(f"Failed to create even a simple demo shape: {e}")


class MainWindow:
    """Main Playground window."""

    def __init__(self) -> None:
        # Initialize attributes
        self.app = None
        self.win = None
        self.view = None
        
        # Get the required GUI modules
        result = _require_gui_modules()
        QApplication, QMainWindow, qtViewer3d = result[:3]
        
        # Check if GUI modules are available
        if qtViewer3d is None:
            print("GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6")
            return

        # Set up the application
        self.app = QApplication(sys.argv)
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)
        
        # Create menu bar with reload action
        reload_action = self.win.menuBar().addAction("Reload  (R)")
        reload_action.setShortcut("R")
        reload_action.triggered.connect(self._build_demo)
        
        # Set status bar message with navigation help
        self.win.statusBar().showMessage(
            "LMB‑drag = rotate | MMB = pan | Wheel = zoom | Shift+MMB = fit"
        )
        
        self._build_demo()

    def _build_demo(self) -> None:
        """Build or rebuild the demo scene."""
        if hasattr(self, 'view') and self.view is not None and hasattr(self.view, '_display'):
            _demo_primitives(self.view._display)
    
    def run(self) -> None:
        """Run the application main loop."""
        if self.win is None or self.app is None:
            print("Cannot run the application: GUI dependencies not available")
            print("Please install required packages:")
            print("    conda install -c conda-forge pythonocc-core pyside6")
            return
            
        self.win.show()
        self.app.exec()


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
