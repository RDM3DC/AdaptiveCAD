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
    ExportGCodeDirectCmd,
    DOCUMENT, # Added DOCUMENT import
    rebuild_scene # Added rebuild_scene import
)
from adaptivecad.snapping import SnapManager, GridStrategy
from adaptivecad.push_pull import PushPullFeatureCmd # Added PushPull

# Qt and OCC imports are optional and loaded lazily

# Try to import anti-aliasing enum if available
AA_AVAILABLE = False
try:
    from OCC.Core.V3d import V3d_TypeOfAntialiasing as AA
    AA_AVAILABLE = True
except ImportError:
    pass

try:
    from OCC.Core.TopoDS import TopoDS_Face  # For type checking selected face
    from OCC.Core.AIS import AIS_Shape  # For checking selected object type
except Exception:  # pragma: no cover - OCC optional
    TopoDS_Face = AIS_Shape = object  # type: ignore


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
    def run_cmd(self, cmd: BaseCmd) -> None:
        """Run a command on the main window."""
        cmd.run(self)
    """Main Playground window."""

    def __init__(self) -> None:
        # Initialize attributes
        self.app = None
        self.win = None
        self.view = None
        self.current_mode = "Navigate" # Navigate, Pick, PushPull, Sketch
        self.push_pull_cmd: PushPullFeatureCmd | None = None
        self.initial_drag_pos = None # For PushPull dragging
        self.Qt = Qt # Store Qt for use in _keyPressEvent

        # Get the required GUI modules
        result = _require_gui_modules()
        (
            QApplication,
            QMainWindow,
            qtViewer3d,
            QAction,
            QIcon,
            QToolBar,
            q_message_box, # Renamed to avoid conflict if self.QMessageBox is used elsewhere
        ) = result
        self.QMessageBox = q_message_box # Store as instance attribute

        # Check if GUI modules are available
        if qtViewer3d is None:
            print("GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6")
            return

        # Set up the application
        self.app = QApplication(sys.argv)
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)        # Initialize SnapManager
        self.snap_manager = SnapManager(self.view._display)
        self.snap_manager.add_strategy(GridStrategy(self.view._display))
        
        # Override mouse events instead of connecting to signals that don't exist
        # Override the qtViewer3d's mouse event handlers
        original_mouseMoveEvent = self.view.mouseMoveEvent
        original_mousePressEvent = self.view.mousePressEvent
        original_mouseReleaseEvent = self.view.mouseReleaseEvent
        
        def mouseMoveEvent_override(event):
            # Call the original handler first
            original_mouseMoveEvent(event)
            # Then call our custom handler
            self._on_mouse_move(event.pos().x(), event.pos().y())
            
        def mousePressEvent_override(event):
            # Call the original handler first
            original_mousePressEvent(event)
            # Then call our custom handler
            self._on_mouse_press(event.pos().x(), event.pos().y(), event.buttons(), event.modifiers())
            
        def mouseReleaseEvent_override(event):
            # Call the original handler first
            original_mouseReleaseEvent(event)
            # Then call our custom handler
            self._on_mouse_release(event.pos().x(), event.pos().y(), event.buttons(), event.modifiers())
            
        # Apply the overrides
        self.view.mouseMoveEvent = mouseMoveEvent_override
        self.view.mousePressEvent = mousePressEvent_override
        self.view.mouseReleaseEvent = mouseReleaseEvent_override


        # Viewport polish - try each enhancement feature
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

        # Add Grid Snap toggle action
        grid_snap_action = QAction("Toggle Grid Snap (G)", self.win)
        grid_snap_action.setShortcut("G")
        grid_snap_action.triggered.connect(self.toggle_grid_snap)
        self.win.addAction(grid_snap_action) # Add to window to catch shortcut

        # Add Push-Pull mode toggle action
        push_pull_action = QAction("Push-Pull (P)", self.win)
        push_pull_action.setShortcut("P")
        push_pull_action.triggered.connect(self.toggle_push_pull_mode)
        self.win.addAction(push_pull_action)

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
        # Add Bezier and B-spline curve actions
        from adaptivecad.commands import NewBezierCmd, NewBSplineCmd
        _add_action("Bezier Curve", "draw-bezier-curves", NewBezierCmd)
        _add_action("B-spline Curve", "curve-b-spline", NewBSplineCmd)
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

    def _on_mouse_press(self, x, y, buttons, modifiers):
        if self.current_mode == "PushPull" and self.push_pull_cmd:
            if not self.push_pull_cmd.selected_face: # If no face is selected yet for PP
                # Try to pick a face
                selected_objects = self.view._display.GetSelectedObjects()
                if selected_objects:
                    # We need to get the TopoDS_Face from the selected AIS_InteractiveObject
                    # This requires that selection mode is set to faces, or we iterate subshapes.
                    # For now, assume the first selected object is an AIS_Shape and try to get a face.
                    # This part needs robust face picking from AIS_InteractiveContext selection.
                    # Let's assume selection callback `on_select` has stored the last selected AIS_Shape
                    # and we can check if it's a face or get sub-faces.
                    # For MVP, we might need to adjust selection mode or how faces are picked.
                    
                    # A simpler way for now: use the context to detect what's under the mouse
                    self.view._display.Select(x,y) # Perform selection at click point
                    picked_ais = self.view._display.Context.DetectedCurrentShape()
                    
                    if picked_ais and isinstance(picked_ais, AIS_Shape):
                        shape = picked_ais.Shape() # This is the TopoDS_Shape
                        # We need to find which *face* of this shape was clicked.
                        # This is non-trivial. AIS_InteractiveContext.DetectedSubShape() or similar is needed.
                        # For now, let's assume the *first* face of the detected shape if it's a simple solid.
                        # This is a MAJOR simplification for MVP.
                        from OCC.Core.TopExp import TopExp_Explorer
                        from OCC.Core.TopAbs import TopAbs_FACE
                        
                        explorer = TopExp_Explorer(shape, TopAbs_FACE)
                        if explorer.More():
                            face = explorer.Current() # Take the first face
                            if isinstance(face, TopoDS_Face):
                                # Find the parent shape in DOCUMENT that this face belongs to
                                original_doc_shape = None
                                for feat in DOCUMENT:
                                    # Check if `shape` is part of `feat.shape` or is `feat.shape`
                                    # This check might need to be more robust (e.g. IsSame, or checking subshapes)
                                    if feat.shape.IsSame(shape) or TopExp_Explorer(feat.shape, TopAbs_FACE).More(): # Basic check
                                        # This logic is flawed if shape is a subshape. 
                                        # We need to find the actual TopoDS_Shape from DOCUMENT that `picked_ais` represents.
                                        # Let's assume picked_ais.Shape() IS the one from DOCUMENT for now.
                                        original_doc_shape = feat.shape
                                        break
                                if original_doc_shape:
                                    self.push_pull_cmd.pick_face(self, original_doc_shape, face)
                                    self.initial_drag_pos = (x, y) # Store initial mouse position for dragging
                                    self.win.statusBar().showMessage("Push-Pull: Face selected. Drag to offset.")
                                else:
                                    self.win.statusBar().showMessage("Push-Pull: Could not map selected face to document shape.") 
                            else:
                                self.win.statusBar().showMessage("Push-Pull: Selected geometry is not a face.")
                        else:
                             self.win.statusBar().showMessage("Push-Pull: No faces found on selected shape.")
                    else:
                        self.win.statusBar().showMessage("Push-Pull: No shape selected. Click on a face.")
                else:
                    self.win.statusBar().showMessage("Push-Pull: Click on a face to begin.")
            elif self.push_pull_cmd.selected_face: # Face already selected, this click starts the drag
                self.initial_drag_pos = (x, y)
                # print(f"Push-Pull: Drag started from {self.initial_drag_pos}")

    def _on_mouse_move(self, x, y):
        if self.current_mode == "PushPull" and self.push_pull_cmd and self.push_pull_cmd.selected_face and self.initial_drag_pos:
            # Calculate drag distance
            # This needs to be projected onto the face normal in screen space, or use 3D points.
            # For a simple MVP, let's use vertical mouse movement as a proxy for distance.
            dy = self.initial_drag_pos[1] - y # Positive dy for upward mouse movement
            # Scale dy to a reasonable offset distance (e.g., 1 pixel = 0.1 mm)
            offset_distance = dy * 0.1 
            self.push_pull_cmd.update_preview(self, offset_distance)
        elif self.current_mode == "Navigate" or self.current_mode == "Pick": # Only do snapping if not in PP drag
            self.snap_manager.on_mouse_move(x,y)

    def _on_mouse_release(self, x, y, buttons, modifiers):
        if self.current_mode == "PushPull" and self.push_pull_cmd and self.push_pull_cmd.selected_face and self.initial_drag_pos:
            # Drag finished, preview is already updated by mouse_move.
            # User needs to press Enter to commit or Esc to cancel.
            # print(f"Push-Pull: Drag ended. Current offset: {self.push_pull_cmd.current_offset_distance}")
            self.initial_drag_pos = None # Reset drag start position
            # Status bar already shows instructions from pick_face

    def _on_zoom_changed(self):
        # This is a placeholder. qtViewer3d doesn't have a direct sig_zoom_changed.
        # We might need to infer zoom changes from wheel events or view parameters.
        # For now, let's try to get a magnification factor if available.
        try:
            magnification = self.view._display.View().Scale() # This might be it
            self.snap_manager.update_grid_parameters_from_zoom(magnification)
        except AttributeError:
            pass 

    def toggle_grid_snap(self):
        is_active = self.snap_manager.toggle_grid_snap()
        status_message = f"Grid Snap: {'ON' if is_active else 'OFF'}"
        self.win.statusBar().showMessage(status_message, 2000) # Show for 2 seconds

    def enter_push_pull_mode(self):
        if self.current_mode == "PushPull":
            return
        self.current_mode = "PushPull"
        self.push_pull_cmd = PushPullFeatureCmd()
        # Change cursor, update status bar, etc.
        self.win.statusBar().showMessage("Push-Pull Mode: Click a face to select, then drag. Press P to exit.")
        # Set selection mode to faces if possible/needed
        self.view._display.SetSelectionMode(2) # 2 for AIS_Shape::SelectionMode(SM_Face)
        # print("Entered Push-Pull mode. SelectionMode set to Face.")

    def exit_push_pull_mode(self):
        if self.current_mode != "PushPull":
            return
        
        if self.push_pull_cmd and self.push_pull_cmd.preview_shape and self.view._display.Context.IsDisplayed(self.push_pull_cmd.preview_shape):
            self.view._display.Context.Remove(self.push_pull_cmd.preview_shape, True)

        self.current_mode = "Navigate" # Or "Pick"
        self.push_pull_cmd = None
        self.initial_drag_pos = None
        self.win.statusBar().showMessage("Exited Push-Pull mode. Back to Navigate.", 2000)
        self.view._display.SetSelectionMode(1) # 1 for AIS_Shape::SelectionMode(SM_Object) or default
        # print("Exited Push-Pull mode. SelectionMode set to Object.")
        rebuild_scene(self.view._display) # Ensure scene is correct

    def toggle_push_pull_mode(self):
        if self.current_mode == "PushPull":
            if self.push_pull_cmd: # If a command is active, cancel it before exiting mode
                self.push_pull_cmd.cancel(self)
            else:
                self.exit_push_pull_mode()
        else:
            self.enter_push_pull_mode()

    def _keyPressEvent(self, event):
        # Handle global key presses or mode-specific ones
        if self.current_mode == "PushPull" and self.push_pull_cmd:
            if event.key() == self.Qt.Key_Return or event.key() == self.Qt.Key_Enter:
                self.push_pull_cmd.commit(self)
                return # Event handled
            elif event.key() == self.Qt.Key_Escape:
                self.push_pull_cmd.cancel(self)
                return # Event handled
        
        # Allow event to propagate for other shortcuts (R, G, P etc.)
        # Call the base class's keyPressEvent if not handled
        # super(QMainWindow, self.win).keyPressEvent(event) # This is one way if self.win is QMainWindow
        # Or rely on event propagation if this handler doesn't consume it.
        # For now, simply not consuming it should allow other shortcuts to work.
        pass

    def run(self):
        """Run the main window application."""
        if not self.app or not self.win:
            print("Error: Application not properly initialized")
            return
        
        # Install event filter to catch key events in main window
        from PySide6.QtCore import QObject, QEvent
        class KeyPressFilter(QObject):
            def __init__(self, main_window):
                super().__init__()
                self.main_window = main_window
            def eventFilter(self, obj, event):
                if event.type() == QEvent.KeyPress:
                    self.main_window._keyPressEvent(event)
                return super().eventFilter(obj, event)

        # Install the filter
        self.event_filter = KeyPressFilter(self)
        self.win.installEventFilter(self.event_filter)
        
        # Show the window and run the application
        self.win.show()
        self.win.setGeometry(100, 100, 1024, 768)  # Set a reasonable default size
        
        # Execute the application
        return self.app.exec()
        




def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
