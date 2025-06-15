"""Simplified GUI playground with optional dependencies."""

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True


if not HAS_GUI:

    class MainWindow:
        """Placeholder when GUI deps are unavailable."""

    def _require_gui_modules():
        raise RuntimeError("PySide6 and pythonocc-core are required to run the playground")

else:
    # Real implementation would go here in a full installation. We keep it minimal
    # for testing without GUI dependencies.
    from PySide6.QtWidgets import QApplication, QMainWindow  # type: ignore

    class MainWindow:
        def __init__(self) -> None:
            self.app = QApplication([])
            self.win = QMainWindow()

<<<<<<< HEAD

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


class SettingsDialog:
    @staticmethod
    def show(parent):
        defl = settings.MESH_DEFLECTION
        angle = settings.MESH_ANGLE
        defl, ok = QInputDialog.getDouble(parent, "Mesh Deflection", "Deflection (mm, lower=smoother):", defl, 0.001, 1.0, 3)
        if not ok:
            return
        angle, ok = QInputDialog.getDouble(parent, "Mesh Angle", "Angle (radians, lower=smoother):", angle, 0.001, 1.0, 3)
        if not ok:
            return
        settings.MESH_DEFLECTION = defl
        settings.MESH_ANGLE = angle




        # ...existing code...
class MainWindow:
    def resizeEvent(self, event):
        if hasattr(self, "_position_viewcube"):
            self._position_viewcube()
        super(type(self.win), self.win).resizeEvent(event)
    def add_view_toolbar(self):
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QToolBar
        tb = QToolBar("Views", self.win)
        self.win.addToolBar(tb)
        occ_display = self.view._display
        view_map = {
            "Home": occ_display.View_Iso,
            "Top": occ_display.View_Top,
            "Bottom": occ_display.View_Bottom,
            "Front": occ_display.View_Front,
            "Back": occ_display.View_Rear,
            "Left": occ_display.View_Left,
            "Right": occ_display.View_Right,
        }
        for name, fn in view_map.items():
            act = QAction(name, self.win)
            def make_slot(f):
                return lambda checked=False: [f(), occ_display.FitAll()]
            act.triggered.connect(make_slot(fn))
            tb.addAction(act)
        self.views_toolbar = tb
    def clear_property_panel(self):
        # Clear all widgets from the property panel
        for i in reversed(range(self.property_layout.count())):
            widget = self.property_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.property_layout.addWidget(QLabel("No selection."))

    def _init_property_panel(self):
        from PySide6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel
        self.property_dock = QDockWidget("Properties", self.win)
        self.property_widget = QWidget()
        self.property_layout = QVBoxLayout()
        self.property_widget.setLayout(self.property_layout)
        self.property_dock.setWidget(self.property_widget)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.property_dock)
        self.property_dock.setVisible(True)

    def _build_snap_menu(self):
        snap_menu = self.win.menuBar().addMenu("Snaps")
        self.snap_actions = {}
        for _, strat in self.snap_manager.strategies:
            name = strat.__name__
            act = QAction(name.replace('_', ' ').title(), self.win, checkable=True)
            act.setChecked(self.snap_manager.is_enabled(name))
            act.toggled.connect(lambda checked, n=name: self.snap_manager.enable_strategy(n, checked))
            snap_menu.addAction(act)
            self.snap_actions[name] = act

    def _show_properties(self, obj):
        from PySide6.QtWidgets import QLabel, QLineEdit, QHBoxLayout
        # Clear previous
        for i in reversed(range(self.property_layout.count())):
            widget = self.property_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.property_layout.addWidget(QLabel(f"Type: {type(obj).__name__}"))
        # Show editable attributes (simple, non-callable, non-private)
        def is_editable(val):
            return isinstance(val, (int, float, str, bool))
        # If this is a Feature with params, show params as editable fields
        is_feature = hasattr(obj, 'params') and isinstance(getattr(obj, 'params', None), dict)
        params = obj.params if is_feature else None
        shown_attrs = set()
        if params:
            for key, val in params.items():
                row = QHBoxLayout()
                row.addWidget(QLabel(f"{key}: "))
                if is_editable(val):
                    editor = QLineEdit(str(val))
                    def make_param_setter(param_key, typ):
                        def setter():
                            text = editor.text()
                            try:
                                if typ is bool:
                                    new_val = text.lower() in ("1", "true", "yes", "on")
                                else:
                                    new_val = typ(text)
                                obj.params[param_key] = new_val
                                # If the feature has a rebuild/update method, call it
                                if hasattr(obj, 'rebuild') and callable(obj.rebuild):
                                    obj.rebuild()
                                # Always update the viewer
                                if hasattr(self, 'view') and hasattr(self.view, '_display'):
                                    try:
                                        rebuild_scene(self.view._display)
                                    except Exception:
                                        pass
                            except Exception as e:
                                editor.setText(str(obj.params[param_key]))  # revert
                        return setter
                    editor.editingFinished.connect(make_param_setter(key, type(val)))
                    row.addWidget(editor)
                else:
                    row.addWidget(QLabel(str(val)))
                self.property_layout.addLayout(row)
                shown_attrs.add(key)
        # Show other attributes as before
        for attr in dir(obj):
            if attr.startswith('_') or callable(getattr(obj, attr)) or attr in shown_attrs:
                continue
            val = getattr(obj, attr)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{attr}: "))
            if is_editable(val):
                editor = QLineEdit(str(val))
                def make_setter(attr_name, typ):
                    def setter():
                        text = editor.text()
                        try:
                            if typ is bool:
                                new_val = text.lower() in ("1", "true", "yes", "on")
                            else:
                                new_val = typ(text)
                            setattr(obj, attr_name, new_val)
                            if hasattr(self, 'view') and hasattr(self.view, '_display'):
                                try:
                                    rebuild_scene(self.view._display)
                                except Exception:
                                    pass
                        except Exception as e:
                            editor.setText(str(getattr(obj, attr_name)))  # revert
                    return setter
                editor.editingFinished.connect(make_setter(attr, type(val)))
                row.addWidget(editor)
            else:
                row.addWidget(QLabel(str(val)))
            self.property_layout.addLayout(row)


    def show_ndfield_slicer(self, ndfield):
        """Show the NDField slicer dock for a given NDField object."""
        def on_slice_update(slice_indices):
            data = ndfield.get_slice(slice_indices)
            plot_nd_slice(data)
        self.ndfield_slicer = NDSliceWidget(ndfield, on_slice_update)
        self.win.addDockWidget(Qt.RightDockWidgetArea, self.ndfield_slicer)

        # Add NDField Slicer demo action to menu
        ndfield_action = self.win.menuBar().addAction("NDField Slicer Demo")
        def launch_ndfield_demo():
            import numpy as np
            from adaptivecad.ndfield import NDField
            # Example: 4D field, shape (8,8,8,8)
            grid_shape = [8,8,8,8]
            values = np.random.rand(*grid_shape)
            ndfield = NDField(grid_shape, values)
            self.show_ndfield_slicer(ndfield)
        ndfield_action.triggered.connect(launch_ndfield_demo)
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
        self.Qt = Qt # Store Qt for use in _keyPressEvent        # Get the required GUI modules
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
        self.win.setCentralWidget(self.view)
        self.view.show() # Explicitly show the view

        # --- Add View Cube overlay ---
        self.viewcube = ViewCubeWidget(self.view._display, self.view)
        self._position_viewcube()
        self.viewcube.show()

        # Reposition cube on view resize
        original_resize = self.view.resizeEvent
        def resizeEvent(evt):
            if original_resize:
                original_resize(evt)
            self._position_viewcube()
        self.view.resizeEvent = resizeEvent

        # Add menu toggle for View Cube
        viewcube_action = QAction("Show View Cube", self.win, checkable=True)
        viewcube_action.setChecked(True)
        def toggle_cube(checked):
            self.viewcube.setVisible(checked)
        viewcube_action.triggered.connect(toggle_cube)
        self.win.menuBar().addAction(viewcube_action)

        self._init_property_panel()        # Initialize SnapManager
        from adaptivecad.snap import SnapManager
        from adaptivecad.snap_strategies import grid_snap, endpoint_snap
        self.snap_manager = SnapManager()
        self.snap_manager.register(endpoint_snap, priority=20)
        self.snap_manager.register(grid_snap, priority=10)
        self.current_snap_point = None

        # Override mouse events instead of connecting to signals that don't exist
        # Override the qtViewer3d's mouse event handlers
        original_mouseMoveEvent = self.view.mouseMoveEvent
        original_mousePressEvent = self.view.mousePressEvent
        original_mouseReleaseEvent = self.view.mouseReleaseEvent
        def mouseMoveEvent_override(event):
            # Call the original handler first
            original_mouseMoveEvent(event)
            # Fix: Use a valid method to convert screen to world coordinates
            try:
                if hasattr(self.view._display, 'View') and hasattr(self.view._display.View, 'ConvertToGrid'):
                    world_pt = self.view._display.View.ConvertToGrid(event.pos().x(), event.pos().y())
                elif hasattr(self.view._display, 'ConvertToPoint'):
                    world_pt = self.view._display.ConvertToPoint(event.pos().x(), event.pos().y())
                elif hasattr(self.view._display, 'convertToPoint'):
                    world_pt = self.view._display.convertToPoint(event.pos().x(), event.pos().y())
                else:
                    # Fallback: just use zeros or the event position as a placeholder
                    world_pt = [0.0, 0.0, 0.0]
            except:                # Fallback if any conversion fails
                world_pt = [0.0, 0.0, 0.0]
            self._on_mouse_move(world_pt)
            
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
                # If selection is a list, unwrap it
                if isinstance(shape, list) and shape:
                    shape = shape[0]
                try:
                    t = shape.ShapeType() if hasattr(shape, 'ShapeType') else type(shape).__name__
                    try:
                        mass = round(self.props_tool.Volume(shape), 3)
                    except Exception:
                        mass = "n/a"
                    self.win.statusBar().showMessage(f"Selected {t} | volume ≈ {mass} mm³")
                except Exception as e:
                    print(f"Selection callback error: {e}")

                # --- Show properties in side panel if shape is a Feature or NDField ---
                from adaptivecad.commands import DOCUMENT
                found = None
                for feat in DOCUMENT:
                    if hasattr(feat, 'shape') and hasattr(shape, 'IsEqual'):
                        try:
                            if shape.IsEqual(feat.shape):
                                found = feat
                                break
                        except Exception:
                            continue
                if found is not None:
                    self._show_properties(found)
                else:
                    # Try NDField: look for .shape or .values attribute
                    from adaptivecad.ndfield import NDField
                    for obj in DOCUMENT:
                        if isinstance(obj, NDField):
                            self._show_properties(obj)
                            break
                    else:
                        # Fallback: show the shape itself
                        self._show_properties(shape)

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

        # Add Settings action to menu
        settings_action = self.win.menuBar().addAction("Settings")
        settings_action.triggered.connect(lambda: (SettingsDialog.show(self.win), self._build_demo()))        # Set status bar message with navigation help
        self.win.statusBar().showMessage(
            "LMB‑drag = rotate | MMB = pan | Wheel = zoom | Shift+MMB = fit"
        )
        
        # Add toolbar with primitive commands
        self.tb = QToolBar("Primitives", self.win)
        self.tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)  # Always show text under icon
        self.win.addToolBar(Qt.TopToolBarArea, self.tb)  # Force toolbar to top
        self.tb.setVisible(True)

        # Add Views toolbar
        self.add_view_toolbar()

        def _add_action(text, icon_name, cmd_cls):
            act = QAction(QIcon.fromTheme(icon_name), text, self.win)
            act.setToolTip(text)
            act.setIconText(text)
            self.tb.addAction(act)
            act.triggered.connect(lambda: self.run_cmd(cmd_cls()))

        # Add Clear Selection button
        clear_sel_action = QAction("Clear Selection", self.win)
        clear_sel_action.setToolTip("Clear property panel selection")
        clear_sel_action.triggered.connect(self.clear_property_panel)
        self.tb.addAction(clear_sel_action)
        
        _add_action("Box", "view-cube", NewBoxCmd)
        _add_action("Cylinder", "media-optical", NewCylCmd)
        self.tb.addSeparator()
        
        # Add Bezier and B-spline curve actions
        from adaptivecad.commands import NewBezierCmd, NewBSplineCmd
        _add_action("Bezier Curve", "draw-bezier-curves", NewBezierCmd)
        _add_action("B-spline Curve", "curve-b-spline", NewBSplineCmd)
        self.tb.addSeparator()
        _add_action("Export STL", "document-save", ExportStlCmd)
        _add_action("Export AMA", "document-save-as", ExportAmaCmd)
        _add_action("Export G-code", "media-record", ExportGCodeCmd)
        _add_action("Export G-code (CAD)", "text-x-generic", ExportGCodeDirectCmd)
        self.tb.addSeparator()
        from adaptivecad.commands import MoveCmd
        _add_action("Move", "transform-move", MoveCmd)
        self.tb.addSeparator()
        
        from adaptivecad.commands import UnionCmd, CutCmd
        _add_action("Union", "list-add", UnionCmd)
        _add_action("Cut", "edit-cut", CutCmd)
        self.tb.addSeparator()
        
        from adaptivecad.commands import NewNDBoxCmd, NewNDFieldCmd
        _add_action("ND Box", "view-list-details", NewNDBoxCmd)
        _add_action("ND Field", "view-list-tree", NewNDFieldCmd)
        self.tb.addSeparator()
        
        from adaptivecad.commands import NewBallCmd, NewTorusCmd
        _add_action("Ball", "media-playback-stop", NewBallCmd)
        _add_action("Torus", "format-rotate", NewTorusCmd)
        self.tb.addSeparator()

    def _build_demo(self) -> None:
        """Build or rebuild the demo scene."""
        if hasattr(self, 'view') and self.view is not None and hasattr(self.view, '_display'):
            _demo_primitives(self.view._display)

    def _position_viewcube(self):
        if hasattr(self, 'viewcube') and self.viewcube.parent() is self.view:
            self.viewcube.move(self.view.width() - self.viewcube.width() - 10, 10)

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

    def _on_mouse_move(self, world_pt):
        if self.current_mode == "PushPull" and self.push_pull_cmd and self.push_pull_cmd.selected_face and self.initial_drag_pos:
            pass # (PushPull logic unchanged for brevity)
        else:
            snapped, label = self.snap_manager.snap(world_pt, self.view)
            if snapped is not None:
                self.show_snap_marker(snapped, label)
                self.current_snap_point = snapped
            else:
                self.hide_snap_marker()
                self.current_snap_point = world_pt

    def show_snap_marker(self, point, label):
        if hasattr(self, "snap_marker"):
            self.view._display.Erase(self.snap_marker)
        self.snap_marker = self.view._display.DisplayShape(point, update=False, color="CYAN")

    def hide_snap_marker(self):
        if hasattr(self, "snap_marker"):
            self.view._display.Erase(self.snap_marker)
            del self.snap_marker

    def _on_mouse_press(self, world_pt, *args, **kwargs):
        pass # On mouse click: use self.current_snap_point for placement

    def toggle_grid_snap(self):
        is_on = self.snap_manager.toggle_strategy('grid_snap')
        if hasattr(self, 'snap_actions') and 'grid_snap' in self.snap_actions:
            self.snap_actions['grid_snap'].setChecked(is_on)
        status_message = f"Grid Snap {'ON' if is_on else 'OFF'}"
        self.win.statusBar().showMessage(status_message, 2000)

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
        vk = event.key()
        vmap = {
            self.Qt.Key_H: self.view._display.View_Iso,
            self.Qt.Key_T: self.view._display.View_Top,
            self.Qt.Key_B: self.view._display.View_Bottom,
            self.Qt.Key_F: self.view._display.View_Front,
            self.Qt.Key_R: self.view._display.View_Rear,
            self.Qt.Key_L: self.view._display.View_Left,
            self.Qt.Key_Y: self.view._display.View_Right,
        }
        if vk in vmap:
            vmap[vk]()
            self.view._display.FitAll()
            event.accept()
            return
        if self.current_mode == "PushPull" and self.push_pull_cmd:
            if vk == self.Qt.Key_Return or vk == self.Qt.Key_Enter:
                self.push_pull_cmd.commit(self)
                return # Event handled
            elif vk == self.Qt.Key_Escape:
                self.push_pull_cmd.cancel(self)
                return # Event handled
        # Allow event to propagate for other shortcuts (R, G, P etc.)
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
        self._build_demo() # Build demo scene AFTER window is shown
        
        # Execute the application
        return self.app.exec()
        




def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
=======
    def _require_gui_modules():
        return QApplication, QMainWindow
>>>>>>> 03eaca40f8f07a7d2af56067fe99d2fb95770f51
