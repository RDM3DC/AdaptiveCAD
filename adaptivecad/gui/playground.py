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

# Fix Qt plugin paths
import os
import sys
import site
import pathlib

# Try to locate PySide6 plugins
potential_plugin_dirs = []
for site_dir in site.getsitepackages():
    pyside_plugins = pathlib.Path(site_dir) / "PySide6" / "plugins"
    if pyside_plugins.exists():
        potential_plugin_dirs.append(str(pyside_plugins))
        os.environ["QT_PLUGIN_PATH"] = str(pyside_plugins)
        platform_path = pyside_plugins / "platforms"
        if platform_path.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_path)
            if sys.platform == "win32":
                os.add_dll_directory(str(platform_path))
                os.add_dll_directory(str(pyside_plugins))
                os.environ["PATH"] = f"{platform_path};{pyside_plugins};{os.environ.get('PATH', '')}"

import math
import numpy as np
from math import cos, sin, pi
from adaptivecad.commands import (
    BaseCmd,
    NewBoxCmd,
    NewCylCmd,
    ExportStlCmd,
    ExportAmaCmd,
    ExportGCodeCmd,
    ExportGCodeDirectCmd,  # Added this line
)

# Try to import anti-aliasing enum if available
# Try to import anti-aliasing enum if available
AA_AVAILABLE = False
try:
    from OCC.Core.V3d import V3d_TypeOfAntialiasing as AA
    AA_AVAILABLE = True
except ImportError:
    pass


# Property helper for volume
class Props:
    def Volume(self, shp):
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties

        gp = GProp_GProps()
        brepgprop_VolumeProperties(shp, gp)
        return gp.Mass()


def _require_gui_modules():
    """Import optional GUI modules, raising RuntimeError if unavailable."""
    try:
        # Initialize the Qt backend before importing the OCC Display modules
        from OCC.Display import backend
        backend.load_backend("pyside6")  # Use PySide6 backend
        
        # Import required UI modules
        from PySide6.QtWidgets import (
            QApplication,
            QMainWindow,
            QToolBar,
            QMessageBox,
        )
        from PySide6.QtGui import QAction, QIcon
        from OCC.Display.qtDisplay import qtViewer3d  # type: ignore
    except ImportError:
        # Show a helpful error message for users
        print("GUI extras not installed. Run:\\n   conda install pyside6 pythonocc-core")
        raise RuntimeError(
            "PySide6 and pythonocc-core are required to run the playground"
        )
    except Exception as exc:  # pragma: no cover - import error path
        raise RuntimeError(
            "PySide6 and pythonocc-core are required to run the playground. Error: " + str(exc)
        ) from exc
    return QApplication, QMainWindow, qtViewer3d, QAction, QIcon, QToolBar, QMessageBox


def helix_wire(radius=20, pitch=5, height=40, n=250):
    """Create a helix wire shape."""
    try:
        from OCC.Core.BRepBuilderAPI import (
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeWire,
        )
        from OCC.Core.gp import gp_Pnt
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
        # Clear previous demo if any
        display.EraseAll()
        
        # Create a box and a helix
        box = BRepPrimAPI_MakeBox(50, 50, 10).Shape()
        helx = helix_wire()
        
        # Display the shapes
        display.DisplayShape(box, update=False, transparency=0.2)
        if helx:  # Only display helix if created successfully
            display.DisplayShape(helx, color="YELLOW")
        
        # Apply shading for better visualization
        try:
            if hasattr(display, 'SetShadingMode'):
                display.SetShadingMode(3)  # Phong shading
        except Exception as exc:
            print(f"Could not set shading mode: {exc}")
        
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
        (
            QApplication,
            QMainWindow,
            qtViewer3d,
            QAction,
            QIcon,
            QToolBar,
            QMessageBox,
        ) = result

        # Check if GUI modules are available
        if qtViewer3d is None:
            print("GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6")
            return

        # Set up the application
        self.app = QApplication(sys.argv)
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)        # Viewport polish - try each enhancement feature
        try:
            # Try displaying trihedron (axes)
            if hasattr(self.view._display, 'DisplayTrihedron'):
                self.view._display.DisplayTrihedron()
            elif hasattr(self.view._display, 'display_trihedron'):
                self.view._display.display_trihedron()
            else:
                print("Warning: Trihedron display method not found. Skipping axes display.")
        except Exception as e:
            print(f"Warning: Could not display trihedron: {e}")
            
        try:
            # Try enabling grid
            if hasattr(self.view._display, 'enable_grid'):
                self.view._display.enable_grid()
            elif hasattr(self.view._display, 'display_grid'):
                self.view._display.display_grid()
            else:
                print("Warning: Grid enable method not found. Skipping grid display.")
        except Exception as e:
            print(f"Warning: Could not enable grid: {e}")
            
        # Try setting anti-aliasing
        if AA_AVAILABLE:
            try:
                self.view._display.View.SetAntialiasingMode(AA.V3d_MSAA_8X)
            except Exception as exc:
                print(f"Warning: Could not enable anti-aliasing: {exc}")
                
        # Try setting background gradient colors
        try:
            self.view._display.SetBgGradientColor(0.12, 0.12, 0.12, 0.18, 0.18, 0.18)
        except Exception as e:
            print(f"Warning: Could not set background color: {e}")
            try:
                # Fallback to any available background color method
                if hasattr(self.view._display, 'set_bg_gradient_color'):
                    self.view._display.set_bg_gradient_color(0.12, 0.12, 0.12, 0.18, 0.18, 0.18)
            except:
                print("Could not set background color using any known method.")        # Property tool and selection callback
        try:
            self.props_tool = Props()
            
            def on_select(shape, *k):
                try:
                    t = shape.ShapeType()
                    try:
                        mass = round(self.props_tool.Volume(shape), 3)
                    except Exception:
                        mass = "n/a"
                    self.win.statusBar().showMessage(f"Selected {t} | volume ≈ {mass} mm³")
                except Exception as e:
                    print(f"Selection callback error: {e}")
            
            # Try to register selection callback
            if hasattr(self.view._display, 'register_select_callback'):
                self.view._display.register_select_callback(on_select)
            elif hasattr(self.view._display, 'SetSelectionCallBack'):
                self.view._display.SetSelectionCallBack(on_select)
            else:
                print("Warning: Could not register selection callback - method not found")
                
            # Try to set selection mode for edges
            try:
                if hasattr(self.view._display, 'SetSelectionModeEdge'):
                    self.view._display.SetSelectionModeEdge()
                elif hasattr(self.view._display, 'set_selection_mode_edge'):
                    self.view._display.set_selection_mode_edge()
                else:
                    print("Warning: Could not enable edge selection - method not found")
            except Exception as e:
                print(f"Warning: Could not set selection mode: {e}")
        except Exception as e:
            print(f"Warning: Could not set up selection callback: {e}")

        # Create menu bar with reload action
        reload_action = self.win.menuBar().addAction("Reload  (R)")
        reload_action.setShortcut("R")
        reload_action.triggered.connect(self._build_demo)

        # Set status bar message with navigation help
        self.win.statusBar().showMessage(
            "LMB‑drag = rotate | MMB = pan | Wheel = zoom | Shift+MMB = fit"
        )        # Add toolbar with primitive commands
        tb = QToolBar("Primitives", self.win)
        self.win.addToolBar(tb)
        
        def _add_action(text, icon_name, cmd_cls):
            act = QAction(QIcon.fromTheme(icon_name), text, self.win)
            tb.addAction(act)
            act.triggered.connect(lambda: self.run_cmd(cmd_cls()))
            
        _add_action("Box", "view-cube", NewBoxCmd)
        _add_action("Cylinder", "media-optical", NewCylCmd)
        tb.addSeparator()
        _add_action("Export STL", "document-save", ExportStlCmd)
        _add_action("Export AMA", "document-save-as", ExportAmaCmd)
        _add_action("Export G-code", "media-record", ExportGCodeCmd)
        _add_action("Export G-code (CAD)", "text-x-generic", ExportGCodeDirectCmd)

        self._build_demo()

    def _build_demo(self) -> None:
        """Build or rebuild the demo scene."""
        if hasattr(self, 'view') and self.view is not None and hasattr(self.view, '_display'):
            _demo_primitives(self.view._display)

    def run_cmd(self, cmd) -> None:
        """Execute a command instance and report errors."""
        try:
            cmd.run(self)
        except Exception as exc:  # pragma: no cover - runtime GUI path
            QMessageBox.critical(self.win, "Command failed", str(exc))
    
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
