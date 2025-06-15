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


def helix_wire(radius=20, pitch=5, height=40, n=200):
    """Create a helix wire shape."""
    # Import needed modules inside the function to handle cases where OCC is not available
    try:
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge
    except ImportError:
        print("OCC modules not available - cannot create helix")
        return None
        
    pts = [gp_Pnt(radius * cos(t), radius * sin(t), pitch * t / (2*pi))
           for t in np.linspace(0, 2*pi*height/pitch, n)]
    edges = [BRepBuilderAPI_MakeEdge(pts[i], pts[i+1]).Edge()
             for i in range(len(pts)-1)]
    wire = BRepBuilderAPI_MakeWire()
    for e in edges:
        wire.Add(e)
    return wire.Wire()


def _demo_primitives(display):
    """Create a demo scene using simple primitives."""
    if display is None:
        return
        
    try:
        from adaptivecad import geom, linalg
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    except ImportError as exc:
        print(f"Error loading modules: {exc}")
        print("Make sure pythonocc-core and PySide6 are installed:")
        print("    conda install -c conda-forge pythonocc-core pyside6")
        return
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return

    try:
        # Create a box and a helix
        wire = helix_wire()
        box = BRepPrimAPI_MakeBox(50, 50, 10).Shape()
        
        # Display the shapes
        display.DisplayShape(box, update=False)
        if wire:  # Only display wire if created successfully
            display.DisplayShape(wire, color="YELLOW")
        
        # Enable visualization features
        display.show_triedron()          # XYZ axes in lower left
        display.enable_grid()            # dotted construction grid
        display.register_select_callback(lambda shp, ctx: print(shp))
        
        # Apply shading for better visualization
        display.SetShadingMode(3)  # Phong shading
        
        display.FitAll()
    except Exception as exc:
        print(f"Error creating demo scene: {exc}")
        # Fall back to simpler demo if full scene fails
        try:
            simple_shape = BRepPrimAPI_MakeBox(100, 100, 100).Shape()
            display.DisplayShape(simple_shape)
            display.FitAll()
        except:
            print("Failed to create even a simple demo shape.")


class MainWindow:
    """Main Playground window."""

    def __init__(self) -> None:
        # Get the required GUI modules
        result = _require_gui_modules()
        QApplication, QMainWindow, qtViewer3d = result[:3]
        V3d_TypeOfAntialiasing = result[3] if len(result) > 3 else None
        
        # Check if GUI modules are available
        if qtViewer3d is None:
            print("GUI extras not installed. Run:\n   conda install pyside6 pythonocc-core")
            return

        # Set up the application
        self.app = QApplication(sys.argv)
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)
        
        # Create menu bar with reload action
        reload_act = self.win.menuBar().addAction("Reload (R)")
        reload_act.setShortcut("R")
        reload_act.triggered.connect(self._rebuild_scene)
        
        # Set status bar message with navigation help
        self.win.statusBar().showMessage("LMB‑drag = rotate | MMB = pan | Wheel = zoom")
        
        # Enable anti-aliasing if available
        if V3d_TypeOfAntialiasing:
            self.view._display.View.SetAntialiasingMode(V3d_TypeOfAntialiasing.V3d_MSAA_8X)
        
        self._setup_demo()

    def _setup_demo(self) -> None:
        """Set up the initial demo scene."""
        _demo_primitives(self.view._display)
    
    def _rebuild_scene(self) -> None:
        """Rebuild the scene for hot-reloading."""
        self.view._display.EraseAll()
        self._setup_demo()

    def run(self) -> None:
        """Run the application main loop."""
        self.win.show()
        self.app.exec()


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
