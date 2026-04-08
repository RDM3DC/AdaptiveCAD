"""AdaptiveCAD Main Window

The complete CAD application with:
- SDF-based viewport (no triangles)
- All mathematical surfaces
- Scene management
- Transform tools
- Direct export pipeline
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from adaptivecad.aacore.sdf import KIND_SPHERE, Prim
from adaptivecad.aacore.sdf import Scene as SDFScene
from adaptivecad.app.gizmos import GizmoController, GizmoMode, SelectionManager

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _LeftDockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
    _RightDockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
    _TopToolBarArea = Qt.ToolBarArea.TopToolBarArea
except AttributeError:
    _LeftDockWidgetArea = Qt.LeftDockWidgetArea
    _RightDockWidgetArea = Qt.RightDockWidgetArea
    _TopToolBarArea = Qt.TopToolBarArea


class AdaptiveCADApp(QMainWindow):
    """Main application window for AdaptiveCAD."""
    
    sceneChanged = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("AdaptiveCAD - Triangle-Free CAD")
        self.setMinimumSize(1400, 900)
        
        # Core scene
        self.scene = SDFScene()
        self._selected_prim_index: int = -1
        self._selected_indices: list = []  # Multi-selection support
        self._project_path: Optional[Path] = None
        
        # Selection and transform system
        self.selection_manager = SelectionManager(self.scene)
        self.gizmo_controller = GizmoController(self.selection_manager, self.scene)
        self._current_tool_mode = GizmoMode.NONE
        
        # Connect selection signals
        self.selection_manager.selectionChanged.connect(self._on_selection_changed_multi)
        self.gizmo_controller.transformUpdated.connect(self._on_gizmo_transform)
        
        # Setup UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_docks()
        self._setup_shortcuts()
        
        # Apply dark theme
        self._apply_theme()
        
        # Add a default shape
        self._add_default_shape()
    
    def _setup_ui(self):
        """Setup the main UI layout."""
        # Central widget with viewport
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Import viewport
        try:
            from adaptivecad.gui.analytic_viewport import AnalyticViewport
            self.viewport = AnalyticViewport(central, aacore_scene=self.scene)
            layout.addWidget(self.viewport)
            
            # Connect viewport selection to our selection manager
            self._connect_viewport_selection()
            
        except Exception as e:
            log.error(f"Failed to create viewport: {e}")
            # Fallback placeholder
            placeholder = QLabel("Viewport failed to load. Check OpenGL drivers.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #ff6b6b; font-size: 18px;")
            layout.addWidget(placeholder)
            self.viewport = None
        
        # Add gizmo overlay widget (2D handles on top of 3D view)
        try:
            from adaptivecad.app.interactive_viewport import GizmoOverlayWidget
            self.gizmo_overlay = GizmoOverlayWidget(central)
            self.gizmo_overlay.setGeometry(central.rect())
            self.gizmo_overlay.raise_()
        except Exception as e:
            log.debug(f"Gizmo overlay not available: {e}")
            self.gizmo_overlay = None
        
        self.setCentralWidget(central)
    
    def _connect_viewport_selection(self):
        """Connect viewport picking to selection manager."""
        if not self.viewport:
            return
        
        # Store original mouse handler
        original_mouse_press = self.viewport.mousePressEvent
        
        def enhanced_mouse_press(event):
            # Call original for camera control
            original_mouse_press(event)
            
            # Get picked index from viewport
            try:
                picked_idx = self.viewport.selected_index
                if picked_idx >= 0:
                    mods = event.modifiers()
                    try:
                        shift = Qt.KeyboardModifier.ShiftModifier
                        ctrl = Qt.KeyboardModifier.ControlModifier
                    except AttributeError:
                        shift = Qt.ShiftModifier
                        ctrl = Qt.ControlModifier
                    
                    if mods & shift:
                        self.selection_manager.select(picked_idx, add_to_selection=True)
                    elif mods & ctrl:
                        self.selection_manager.toggle_selection(picked_idx)
                    else:
                        self.selection_manager.select(picked_idx)
                elif event.button() == Qt.MouseButton.LeftButton:
                    # Clicked on empty space - clear selection
                    self.selection_manager.clear_selection()
            except Exception as e:
                log.debug(f"Selection handling: {e}")
        
        self.viewport.mousePressEvent = enhanced_mouse_press
    
    def _on_selection_changed_multi(self, indices: list):
        """Handle multi-selection changes."""
        self._selected_indices = indices
        self._selected_prim_index = indices[0] if indices else -1
        
        # Update UI
        if indices:
            if len(indices) == 1:
                self.selection_label.setText(f"Selection: Object {indices[0]}")
            else:
                self.selection_label.setText(f"Selection: {len(indices)} objects")
            
            # Update transform dock with primary selection
            if 0 <= self._selected_prim_index < len(self.scene.prims):
                prim = self.scene.prims[self._selected_prim_index]
                self.transform_dock.set_prim(prim)
        else:
            self.selection_label.setText("Selection: None")
            self.transform_dock.set_prim(None)
        
        # Sync scene tree selection (if different)
        if hasattr(self, 'scene_dock') and self.scene_dock:
            tree_indices = self.scene_dock.get_selected_indices()
            if set(tree_indices) != set(indices):
                self.scene_dock.select_indices(indices)
        
        # Update gizmo position
        self._update_gizmo_position()
    
    def _on_gizmo_transform(self, transform: dict):
        """Handle transform changes from gizmo."""
        self._update_scene_display()
    
    def _update_gizmo_position(self):
        """Update gizmo overlay position based on selection."""
        # Update viewport selection highlight
        if self.viewport and self._selected_indices:
            self.viewport.selected_index = self._selected_indices[0]
        elif self.viewport:
            self.viewport.selected_index = -1
        
        if not self.gizmo_overlay or not self._selected_indices:
            if self.gizmo_overlay:
                self.gizmo_overlay.set_visible(False)
            return
        
        # Get selection center in world space
        self.selection_manager.get_selection_center()
        
        # Project to screen space (simplified - would need proper matrix math)
        # For now, just position at center of viewport
        if self.viewport:
            self.gizmo_overlay.set_position(
                self.viewport.width() // 2,
                self.viewport.height() // 2
            )
            self.gizmo_overlay.set_visible(self._current_tool_mode != GizmoMode.NONE)
            self.gizmo_overlay.set_mode(self._current_tool_mode)
            
            # Update viewport
            self.viewport.update()
    
    def _setup_menus(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        # Import submenu
        import_menu = file_menu.addMenu("&Import")
        
        import_stl = QAction("Import STL/OBJ as SDF...", self)
        import_stl.setShortcut(QKeySequence("Ctrl+I"))
        import_stl.triggered.connect(self._import_mesh)
        import_menu.addAction(import_stl)
        
        file_menu.addSeparator()
        
        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu("&Export")
        
        export_gcode = QAction("Export G-Code (Direct SDF)...", self)
        export_gcode.triggered.connect(self._export_gcode)
        export_menu.addAction(export_gcode)
        
        export_ama = QAction("Export AMA (Analytic)...", self)
        export_ama.triggered.connect(self._export_ama)
        export_menu.addAction(export_ama)
        
        export_slices = QAction("Export Slice Images...", self)
        export_slices.triggered.connect(self._export_slices)
        export_menu.addAction(export_slices)
        
        file_menu.addSeparator()
        
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        delete_action = QAction("&Delete", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(delete_action)
        
        duplicate_action = QAction("D&uplicate", self)
        duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        duplicate_action.triggered.connect(self._duplicate_selected)
        edit_menu.addAction(duplicate_action)
        
        edit_menu.addSeparator()
        
        # Array submenu
        array_menu = edit_menu.addMenu("🔢 Array")
        
        linear_array_action = QAction("Linear Array...", self)
        linear_array_action.triggered.connect(self._show_linear_array_dialog)
        array_menu.addAction(linear_array_action)
        
        circular_array_action = QAction("Circular Array...", self)
        circular_array_action.triggered.connect(self._show_circular_array_dialog)
        array_menu.addAction(circular_array_action)
        
        grid_array_action = QAction("Grid Array...", self)
        grid_array_action.triggered.connect(self._show_grid_array_dialog)
        array_menu.addAction(grid_array_action)
        
        edit_menu.addSeparator()
        
        # Align submenu
        align_menu = edit_menu.addMenu("📐 Align")
        
        align_left_action = QAction("Align Left (X-)", self)
        align_left_action.triggered.connect(lambda: self._align_selection('min', 'x'))
        align_menu.addAction(align_left_action)
        
        align_center_x_action = QAction("Align Center X", self)
        align_center_x_action.triggered.connect(lambda: self._align_selection('center', 'x'))
        align_menu.addAction(align_center_x_action)
        
        align_right_action = QAction("Align Right (X+)", self)
        align_right_action.triggered.connect(lambda: self._align_selection('max', 'x'))
        align_menu.addAction(align_right_action)
        
        align_menu.addSeparator()
        
        distribute_x_action = QAction("Distribute X", self)
        distribute_x_action.triggered.connect(lambda: self._distribute_selection('x'))
        align_menu.addAction(distribute_x_action)
        
        edit_menu.addSeparator()
        
        # Transform submenu
        transform_menu = edit_menu.addMenu("🔄 Transform")
        
        mirror_x_action = QAction("Mirror X", self)
        mirror_x_action.triggered.connect(lambda: self._mirror_selection('x'))
        transform_menu.addAction(mirror_x_action)
        
        mirror_y_action = QAction("Mirror Y", self)
        mirror_y_action.triggered.connect(lambda: self._mirror_selection('y'))
        transform_menu.addAction(mirror_y_action)
        
        mirror_z_action = QAction("Mirror Z", self)
        mirror_z_action.triggered.connect(lambda: self._mirror_selection('z'))
        transform_menu.addAction(mirror_z_action)
        
        transform_menu.addSeparator()
        
        snap_grid_action = QAction("Snap to Grid", self)
        snap_grid_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        snap_grid_action.triggered.connect(self._snap_selection_to_grid)
        transform_menu.addAction(snap_grid_action)
        
        edit_menu.addSeparator()
        
        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        edit_menu.addAction(select_all_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        fit_all_action = QAction("&Fit All", self)
        fit_all_action.setShortcut(QKeySequence("F"))
        fit_all_action.triggered.connect(self._fit_all)
        view_menu.addAction(fit_all_action)
        
        fit_selected_action = QAction("Fit Selected", self)
        fit_selected_action.setShortcut(QKeySequence("Shift+F"))
        fit_selected_action.triggered.connect(self._fit_selected)
        view_menu.addAction(fit_selected_action)
        
        view_menu.addSeparator()
        
        # View presets
        front_action = QAction("Front", self)
        front_action.setShortcut(QKeySequence("Numpad 1"))
        front_action.triggered.connect(lambda: self._set_camera_preset('front'))
        view_menu.addAction(front_action)
        
        right_action = QAction("Right", self)
        right_action.setShortcut(QKeySequence("Numpad 3"))
        right_action.triggered.connect(lambda: self._set_camera_preset('right'))
        view_menu.addAction(right_action)
        
        top_action = QAction("Top", self)
        top_action.setShortcut(QKeySequence("Numpad 7"))
        top_action.triggered.connect(lambda: self._set_camera_preset('top'))
        view_menu.addAction(top_action)
        
        iso_action = QAction("Isometric", self)
        iso_action.setShortcut(QKeySequence("Numpad 0"))
        iso_action.triggered.connect(lambda: self._set_camera_preset('isometric'))
        view_menu.addAction(iso_action)
        
        view_menu.addSeparator()
        
        # Toggle docks
        self._dock_actions = {}
        
        # Create menu
        create_menu = menubar.addMenu("&Create")
        
        # Add shape categories
        from adaptivecad.app.shape_creation import SHAPE_DEFINITIONS, ShapeCategory
        
        for category in ShapeCategory:
            cat_menu = create_menu.addMenu(category.value)
            
            shapes = [
                (key, defn) for key, defn in SHAPE_DEFINITIONS.items()
                if defn.category == category
            ]
            
            for key, defn in shapes:
                action = QAction(f"{defn.icon} {defn.name}", self)
                action.triggered.connect(lambda checked, k=key: self._quick_create_shape(k))
                cat_menu.addAction(action)
        
        # Operations menu
        ops_menu = menubar.addMenu("&Operations")
        
        union_action = QAction("🔗 Union", self)
        union_action.setShortcut(QKeySequence("Ctrl+U"))
        union_action.triggered.connect(lambda: self._apply_boolean('union'))
        ops_menu.addAction(union_action)
        
        subtract_action = QAction("➖ Subtract", self)
        subtract_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        subtract_action.triggered.connect(lambda: self._apply_boolean('subtract'))
        ops_menu.addAction(subtract_action)
        
        intersect_action = QAction("✖ Intersect", self)
        intersect_action.setShortcut(QKeySequence("Ctrl+I"))
        intersect_action.triggered.connect(lambda: self._apply_boolean('intersect'))
        ops_menu.addAction(intersect_action)
        
        ops_menu.addSeparator()
        
        boolean_dialog_action = QAction("Boolean Operations...", self)
        boolean_dialog_action.triggered.connect(self._show_boolean_dialog)
        ops_menu.addAction(boolean_dialog_action)
        
        # Modify menu (edge operations, offsets, etc.)
        modify_menu = menubar.addMenu("&Modify")
        
        fillet_action = QAction("🔘 Fillet (Round Edges)", self)
        fillet_action.triggered.connect(self._apply_fillet)
        modify_menu.addAction(fillet_action)
        
        chamfer_action = QAction("▽ Chamfer (Bevel Edges)", self)
        chamfer_action.triggered.connect(self._apply_chamfer)
        modify_menu.addAction(chamfer_action)
        
        modify_menu.addSeparator()
        
        shell_action = QAction("⊙ Shell (Hollow Out)", self)
        shell_action.triggered.connect(self._apply_shell)
        modify_menu.addAction(shell_action)
        
        offset_action = QAction("⇄ Offset Surface", self)
        offset_action.triggered.connect(self._apply_offset)
        modify_menu.addAction(offset_action)
        
        thicken_action = QAction("⇆ Thicken Surface", self)
        thicken_action.triggered.connect(self._apply_thicken)
        modify_menu.addAction(thicken_action)
        
        # Sketch menu (2D tools)
        sketch_menu = menubar.addMenu("&Sketch")
        
        rect_action = QAction("▢ Rectangle", self)
        rect_action.setShortcut(QKeySequence("R"))
        rect_action.triggered.connect(self._create_sketch_rectangle)
        sketch_menu.addAction(rect_action)
        
        circle_action = QAction("○ Circle", self)
        circle_action.setShortcut(QKeySequence("C"))
        circle_action.triggered.connect(self._create_sketch_circle)
        sketch_menu.addAction(circle_action)
        
        ellipse_action = QAction("◯ Ellipse", self)
        ellipse_action.triggered.connect(self._create_sketch_ellipse)
        sketch_menu.addAction(ellipse_action)
        
        polygon_action = QAction("⬡ Polygon", self)
        polygon_action.triggered.connect(self._create_sketch_polygon)
        sketch_menu.addAction(polygon_action)
        
        sketch_menu.addSeparator()
        
        line_action = QAction("— Line", self)
        line_action.setShortcut(QKeySequence("L"))
        line_action.triggered.connect(self._create_sketch_line)
        sketch_menu.addAction(line_action)
        
        arc_action = QAction("⌒ Arc", self)
        arc_action.triggered.connect(self._create_sketch_arc)
        sketch_menu.addAction(arc_action)
        
        # Model menu (extrude, revolve, loft)
        model_menu = menubar.addMenu("Mo&del")
        
        extrude_action = QAction("↕ Extrude", self)
        extrude_action.setShortcut(QKeySequence("E"))
        extrude_action.triggered.connect(self._extrude_selection)
        model_menu.addAction(extrude_action)
        
        revolve_action = QAction("↻ Revolve", self)
        revolve_action.triggered.connect(self._revolve_selection)
        model_menu.addAction(revolve_action)
        
        loft_action = QAction("⇋ Loft", self)
        loft_action.triggered.connect(self._loft_selection)
        model_menu.addAction(loft_action)
        
        sweep_action = QAction("⤷ Sweep", self)
        sweep_action.triggered.connect(self._sweep_selection)
        model_menu.addAction(sweep_action)
        
        model_menu.addSeparator()
        
        datum_plane_action = QAction("▭ Work Plane", self)
        datum_plane_action.triggered.connect(self._create_datum_plane)
        model_menu.addAction(datum_plane_action)
        
        datum_axis_action = QAction("│ Axis", self)
        datum_axis_action.triggered.connect(self._create_datum_axis)
        model_menu.addAction(datum_axis_action)
        
        ref_point_action = QAction("• Reference Point", self)
        ref_point_action.triggered.connect(self._create_reference_point)
        model_menu.addAction(ref_point_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        measure_distance_action = QAction("📏 Measure Distance", self)
        measure_distance_action.setShortcut(QKeySequence("M"))
        measure_distance_action.triggered.connect(self._measure_distance)
        tools_menu.addAction(measure_distance_action)
        
        analyze_volume_action = QAction("📊 Analyze Volume", self)
        analyze_volume_action.triggered.connect(self._analyze_volume)
        tools_menu.addAction(analyze_volume_action)

        tools_menu.addSeparator()

        phase_menu = tools_menu.addMenu("🌀 Phase / πₐ")

        pia_circle_action = QAction("Add πₐ Adaptive Circle (Tube)", self)
        pia_circle_action.triggered.connect(self._add_pia_adaptive_circle_demo)
        phase_menu.addAction(pia_circle_action)

        polar_pia_circle_action = QAction("Add Polar πₐ Shape (Tube)", self)
        polar_pia_circle_action.triggered.connect(self._add_polar_pia_adaptive_circle_demo)
        phase_menu.addAction(polar_pia_circle_action)

        torus_path_action = QAction("Add Torus Phase Path (Tube)", self)
        torus_path_action.triggered.connect(self._add_torus_phase_path_demo)
        phase_menu.addAction(torus_path_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About AdaptiveCAD", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        shortcuts_action = QAction("Keyboard &Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)
    
    def _setup_toolbar(self):
        """Setup the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(_TopToolBarArea, toolbar)
        
        # File actions
        new_btn = toolbar.addAction("📄 New")
        new_btn.triggered.connect(self._new_project)
        open_btn = toolbar.addAction("📂 Open")
        open_btn.triggered.connect(self._open_project)
        save_btn = toolbar.addAction("💾 Save")
        save_btn.triggered.connect(self._save_project)
        
        toolbar.addSeparator()
        
        # Transform mode tools (Select/Move/Rotate/Scale)
        self._setup_transform_mode_buttons(toolbar)
        
        toolbar.addSeparator()
        
        # Transform tools dock
        from adaptivecad.app.transform_tools import TransformToolbar
        self.transform_toolbar = TransformToolbar()
        toolbar.addWidget(self.transform_toolbar)
        
        toolbar.addSeparator()
        
        # Quick shape buttons
        quick_shapes = [
            ("🔵", "Sphere", "sphere"),
            ("⬜", "Box", "box"),
            ("🍩", "Torus", "torus"),
            ("🧽", "Gyroid", "gyroid"),
        ]
        
        for icon, tooltip, shape_key in quick_shapes:
            btn = toolbar.addAction(icon)
            btn.setToolTip(f"Create {tooltip}")
            btn.triggered.connect(lambda checked, k=shape_key: self._quick_create_shape(k))
    
    def _setup_transform_mode_buttons(self, toolbar):
        """Setup transform mode buttons (Select/Move/Rotate/Scale)."""
        from PySide6.QtGui import QShortcut
        from PySide6.QtWidgets import QButtonGroup, QToolButton
        
        self._mode_buttons = QButtonGroup(self)
        self._mode_buttons.setExclusive(True)
        
        modes = [
            ("🖱️", "Select (Q)", GizmoMode.NONE, "Q"),
            ("↔️", "Move (G)", GizmoMode.MOVE, "G"),
            ("🔄", "Rotate (R)", GizmoMode.ROTATE, "R"),
            ("📏", "Scale (S)", GizmoMode.SCALE, "S"),
        ]
        
        for icon, tooltip, mode, shortcut_key in modes:
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QToolButton {
                    font-size: 16px;
                    padding: 4px 8px;
                    border-radius: 4px;
                    min-width: 30px;
                }
                QToolButton:checked {
                    background-color: #1f6feb;
                    border: 1px solid #58a6ff;
                }
            """)
            
            btn.clicked.connect(lambda checked, m=mode: self._set_tool_mode(m))
            toolbar.addWidget(btn)
            self._mode_buttons.addButton(btn)
            
            # Add keyboard shortcut
            shortcut = QShortcut(shortcut_key, self)
            shortcut.activated.connect(lambda m=mode: self._set_tool_mode(m))
        
        # Set default mode (Select)
        if self._mode_buttons.buttons():
            self._mode_buttons.buttons()[0].setChecked(True)
    
    def _set_tool_mode(self, mode: GizmoMode):
        """Set the current tool mode."""
        self._current_tool_mode = mode
        self.gizmo_controller.set_mode(mode)
        
        # Update button states
        mode_index = [GizmoMode.NONE, GizmoMode.MOVE, GizmoMode.ROTATE, GizmoMode.SCALE].index(mode)
        buttons = self._mode_buttons.buttons()
        if 0 <= mode_index < len(buttons):
            buttons[mode_index].setChecked(True)
        
        # Update gizmo overlay
        self._update_gizmo_position()
        
        # Status bar feedback
        mode_names = {
            GizmoMode.NONE: "Select",
            GizmoMode.MOVE: "Move",
            GizmoMode.ROTATE: "Rotate",
            GizmoMode.SCALE: "Scale",
        }
        self.statusBar().showMessage(f"Tool: {mode_names.get(mode, 'Unknown')}", 2000)
    
    def _setup_status_bar(self):
        """Setup the status bar."""
        status = QStatusBar()
        self.setStatusBar(status)
        
        # Object count
        self.object_count_label = QLabel("Objects: 0")
        self.object_count_label.setStyleSheet("color: #8b949e; margin-right: 20px;")
        status.addWidget(self.object_count_label)
        
        # Selected object
        self.selection_label = QLabel("Selection: None")
        self.selection_label.setStyleSheet("color: #8b949e; margin-right: 20px;")
        status.addWidget(self.selection_label)
        
        # Render mode
        self.render_mode_label = QLabel("SDF Raymarching")
        self.render_mode_label.setStyleSheet("color: #58a6ff;")
        status.addPermanentWidget(self.render_mode_label)
    
    def _setup_docks(self):
        """Setup dock widgets."""
        # Scene tree dock
        from adaptivecad.app.scene_tree import SceneTreeDock
        self.scene_dock = SceneTreeDock()
        self.scene_dock.set_scene(self.scene)
        self.scene_dock.objectSelected.connect(self._on_object_selected)
        self.scene_dock.objectsSelected.connect(self._on_objects_selected)
        self.scene_dock.objectDeleted.connect(self._on_object_deleted)
        
        scene_dock_widget = QDockWidget("Scene", self)
        scene_dock_widget.setWidget(self.scene_dock)
        scene_dock_widget.setObjectName("SceneDock")
        self.addDockWidget(_LeftDockWidgetArea, scene_dock_widget)
        
        # Shape creation dock
        from adaptivecad.app.shape_creation import ShapeCreationDock
        self.shape_dock = ShapeCreationDock()
        self.shape_dock.shapeCreated.connect(self._create_shape)
        
        shape_dock_widget = QDockWidget("Create", self)
        shape_dock_widget.setWidget(self.shape_dock)
        shape_dock_widget.setObjectName("ShapeDock")
        self.addDockWidget(_RightDockWidgetArea, shape_dock_widget)
        
        # Transform dock
        from adaptivecad.app.transform_tools import TransformDock
        self.transform_dock = TransformDock()
        self.transform_dock.transformChanged.connect(self._on_transform_changed)
        
        transform_dock_widget = QDockWidget("Transform", self)
        transform_dock_widget.setWidget(self.transform_dock)
        transform_dock_widget.setObjectName("TransformDock")
        self.addDockWidget(_RightDockWidgetArea, transform_dock_widget)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        from PySide6.QtGui import QKeySequence, QShortcut
        
        # Selection shortcuts
        select_all = QShortcut(QKeySequence.StandardKey.SelectAll, self)
        select_all.activated.connect(self._select_all)
        
        deselect = QShortcut(QKeySequence("Escape"), self)
        deselect.activated.connect(self._deselect_all)
        
        # Delete shortcut (additional binding)
        delete_key = QShortcut(QKeySequence("Delete"), self)
        delete_key.activated.connect(self._delete_selected)
        
        # Duplicate shortcut
        dup_key = QShortcut(QKeySequence("Ctrl+D"), self)
        dup_key.activated.connect(self._duplicate_selected)
        
        # Focus/fit view
        fit_key = QShortcut(QKeySequence("F"), self)
        fit_key.activated.connect(self._fit_all)
        
        # Frame selected
        frame_key = QShortcut(QKeySequence("."), self)
        frame_key.activated.connect(self._frame_selected)
    
    def _select_all(self):
        """Select all objects."""
        self.selection_manager.select_all()
    
    def _deselect_all(self):
        """Deselect all objects."""
        self.selection_manager.clear_selection()
        self._set_tool_mode(GizmoMode.NONE)
    
    def _frame_selected(self):
        """Frame the selected objects in view."""
        if self._selected_indices and self.viewport:
            # Get center of selection
            self.selection_manager.get_selection_center()
            # TODO: Implement proper camera framing
            self.statusBar().showMessage("Frame selected (not fully implemented)", 2000)
    
    def _apply_theme(self):
        """Apply the dark theme."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
            }
            QMenuBar {
                background-color: #161b22;
                color: #e6edf3;
                border-bottom: 1px solid #30363d;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #21262d;
            }
            QMenu {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #21262d;
            }
            QMenu::separator {
                height: 1px;
                background-color: #30363d;
                margin: 4px 8px;
            }
            QToolBar {
                background-color: #161b22;
                border-bottom: 1px solid #30363d;
                padding: 4px;
                spacing: 4px;
            }
            QToolBar::separator {
                width: 1px;
                background-color: #30363d;
                margin: 4px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 6px;
                color: #e6edf3;
            }
            QToolButton:hover {
                background-color: #21262d;
                border-color: #30363d;
            }
            QToolButton:pressed, QToolButton:checked {
                background-color: #1f6feb;
            }
            QStatusBar {
                background-color: #161b22;
                color: #8b949e;
                border-top: 1px solid #30363d;
            }
            QDockWidget {
                color: #e6edf3;
                font-weight: bold;
            }
            QDockWidget::title {
                background-color: #161b22;
                padding: 8px;
                border-bottom: 1px solid #30363d;
            }
            QScrollBar:vertical {
                background-color: #0d1117;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
    
    def _add_default_shape(self):
        """Add a default shape to the scene.

        Keep startup deterministic and lightweight: do not auto-load external
        demo scenes (e.g. benchy) unless the user explicitly opens a file.
        """
        
        prim = Prim(
            kind=KIND_SPHERE,
            params=[0.5, 0, 0, 0],
            color=(0.2, 0.5, 0.9)
        )
        self.scene.add(prim)
        self._update_scene_display()
    
    def _update_scene_display(self):
        """Update the display after scene changes."""
        self.scene_dock.refresh()
        self.object_count_label.setText(f"Objects: {len(self.scene.prims)}")
        
        if self.viewport:
            self.viewport.update()
    
    def _on_object_selected(self, index: int):
        """Handle object selection from scene tree."""
        self._selected_prim_index = index
        
        if 0 <= index < len(self.scene.prims):
            prim = self.scene.prims[index]
            self.selection_label.setText(f"Selection: Object {index}")
            self.transform_dock.set_prim(prim)
        else:
            self.selection_label.setText("Selection: None")
            self.transform_dock.set_prim(None)
    
    def _on_objects_selected(self, indices: list):
        """Handle multi-selection from scene tree."""
        # Sync with selection manager (without triggering a loop)
        if set(indices) != set(self.selection_manager.selected_indices):
            self.selection_manager._selected_indices = indices
            # Don't emit signal to avoid loop, just update UI directly
            self._on_selection_changed_multi(indices)
    
    def _on_object_deleted(self, index: int):
        """Handle object deletion from scene tree."""
        if 0 <= index < len(self.scene.prims):
            self.scene.remove_index(index)
            self._update_scene_display()
    
    def _on_transform_changed(self, transform: dict):
        """Handle transform changes."""
        self._update_scene_display()
    
    def _create_shape(self, shape_key: str, params: dict):
        """Create a shape from the shape creation panel."""
        from adaptivecad.app.shape_creation import create_prim_from_definition
        
        prim = create_prim_from_definition(shape_key, params)
        if prim:
            prim.pid = len(self.scene.prims)
            self.scene.add(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created {shape_key}", 3000)
    
    def _quick_create_shape(self, shape_key: str):
        """Quick create a shape with default parameters."""
        from adaptivecad.app.shape_creation import SHAPE_DEFINITIONS, create_prim_from_definition
        
        shape_def = SHAPE_DEFINITIONS.get(shape_key)
        if not shape_def:
            return
        
        # Build default params
        params = {p.name: p.default for p in shape_def.params}
        params["pos_x"] = 0.0
        params["pos_y"] = 0.0
        params["pos_z"] = 0.0
        
        prim = create_prim_from_definition(shape_key, params)
        if prim:
            prim.pid = len(self.scene.prims)
            self.scene.add(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created {shape_def.name}", 3000)
    
    def _delete_selected(self):
        """Delete the selected object."""
        if self._selected_prim_index >= 0:
            self._on_object_deleted(self._selected_prim_index)
            self._selected_prim_index = -1
    
    def _duplicate_selected(self):
        """Duplicate the selected object."""
        if 0 <= self._selected_prim_index < len(self.scene.prims):
            import copy
            prim = self.scene.prims[self._selected_prim_index]
            new_prim = copy.deepcopy(prim)
            new_prim.xform.M[:3, 3] += 0.5
            new_prim.pid = len(self.scene.prims)
            self.scene.add(new_prim)
            self._update_scene_display()
    
    def _fit_all(self):
        """Fit all objects in view."""
        if self.viewport and hasattr(self.viewport, 'fit_all'):
            self.viewport.fit_all()
    
    def _new_project(self):
        """Create a new project."""
        self.scene.clear()
        self._project_path = None
        self._add_default_shape()
        self.setWindowTitle("AdaptiveCAD - New Project")
    
    def _open_project(self):
        """Open an existing project."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "AdaptiveCAD Files (*.ama *.json);;All Files (*)"
        )
        
        if path:
            self._load_project(Path(path))
    
    def _load_project(self, path: Path):
        """Load a project from file."""
        try:
            import json
            
            with open(path, 'r') as f:
                json.load(f)
            
            # TODO: Implement proper loading
            self._project_path = path
            self.setWindowTitle(f"AdaptiveCAD - {path.name}")
            self.statusBar().showMessage(f"Loaded {path.name}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project: {e}")
    
    def _save_project(self):
        """Save the current project."""
        if self._project_path:
            self._save_to_path(self._project_path)
        else:
            self._save_project_as()
    
    def _save_project_as(self):
        """Save the project with a new name."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(Path.home()),
            "AdaptiveCAD Files (*.ama);;JSON Files (*.json)"
        )
        
        if path:
            self._save_to_path(Path(path))
    
    def _save_to_path(self, path: Path):
        """Save project to the specified path."""
        try:
            import json
            
            # Serialize scene
            data = {
                "version": "1.0",
                "prims": []
            }
            
            for prim in self.scene.prims:
                prim_data = {
                    "kind": int(prim.kind) if isinstance(prim.kind, int) else prim.kind,
                    "params": prim.params.tolist() if hasattr(prim.params, 'tolist') else list(prim.params),
                    "color": prim.color.tolist() if hasattr(prim.color, 'tolist') else list(prim.color),
                    "transform": prim.xform.M.tolist() if hasattr(prim.xform.M, 'tolist') else list(prim.xform.M),
                    "op": prim.op,
                    "beta": float(prim.beta),
                }
                data["prims"].append(prim_data)
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self._project_path = path
            self.setWindowTitle(f"AdaptiveCAD - {path.name}")
            self.statusBar().showMessage(f"Saved to {path.name}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")
    
    def _export_gcode(self):
        """Export directly to G-code using SDF slicing."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export G-Code",
            str(Path.home()),
            "G-Code Files (*.gcode *.nc)"
        )
        
        if path:
            try:
                # Use direct SDF slicer (no triangles!)
                from adaptivecad.app.sdf_slicer import PrintSettings, SDFSlicer
                
                # Configure print settings
                settings = PrintSettings(
                    layer_height=0.2,
                    nozzle_diameter=0.4,
                    infill_density=0.2,
                    print_speed=60.0,
                )
                
                slicer = SDFSlicer(self.scene, settings)
                
                progress = QProgressDialog("Generating G-Code from SDF...", "Cancel", 0, 100, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
                
                # Compute bounds
                min_b, max_b = slicer.compute_bounds()
                
                # Generate slices directly from SDF (no triangles!)
                slicer.slice_scene(
                    z_start=min_b[2],
                    z_end=max_b[2],
                    layer_height=settings.layer_height,
                    progress_callback=lambda p: progress.setValue(int(p * 100))
                )
                
                # Export G-code
                slicer.export_gcode(path)
                
                progress.close()
                
                num_slices = len(slicer.slices)
                self.statusBar().showMessage(
                    f"Exported G-Code ({num_slices} layers) to {Path(path).name} - NO TRIANGLES!", 
                    5000
                )
                
            except Exception as e:
                log.exception("G-code export failed")
                QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def _export_ama(self):
        """Export to AMA (Analytic Model Archive) format."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AMA",
            str(Path.home()),
            "AMA Files (*.ama)"
        )
        
        if path:
            self._save_to_path(Path(path))
    
    def _export_slices(self):
        """Export slice images for visualization."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Export Slice Images",
            str(Path.home())
        )
        
        if directory:
            try:
                # TODO: Implement slice image export
                self.statusBar().showMessage("Slice export not yet implemented", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def _show_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About AdaptiveCAD",
            """<h2>AdaptiveCAD</h2>
            <p>Triangle-Free CAD System</p>
            <p>Version 0.1.0</p>
            <hr>
            <p>A modern CAD system based on Signed Distance Functions (SDF)
            with direct G-code generation - no triangle mesh conversion needed.</p>
            <p>Features:</p>
            <ul>
            <li>16+ mathematical surfaces</li>
            <li>Real-time SDF raymarching</li>
            <li>Direct SDF to G-code export</li>
            <li>Adaptive Pi Geometry (πₐ) principles</li>
            </ul>
            <p>© 2024-2026 AdaptiveCAD Team</p>
            """
        )
    
    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """
        <h3>General</h3>
        <table>
        <tr><td><b>Ctrl+N</b></td><td>New Project</td></tr>
        <tr><td><b>Ctrl+O</b></td><td>Open Project</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Save Project</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
        </table>
        
        <h3>View</h3>
        <table>
        <tr><td><b>F</b></td><td>Fit All</td></tr>
        <tr><td><b>Middle Mouse</b></td><td>Orbit</td></tr>
        <tr><td><b>Shift+Middle</b></td><td>Pan</td></tr>
        <tr><td><b>Scroll</b></td><td>Zoom</td></tr>
        </table>
        
        <h3>Transform</h3>
        <table>
        <tr><td><b>Q</b></td><td>Select Mode</td></tr>
        <tr><td><b>G</b></td><td>Move Mode</td></tr>
        <tr><td><b>R</b></td><td>Rotate Mode</td></tr>
        <tr><td><b>S</b></td><td>Scale Mode</td></tr>
        </table>
        
        <h3>Edit</h3>
        <table>
        <tr><td><b>Delete</b></td><td>Delete Selection</td></tr>
        <tr><td><b>Ctrl+D</b></td><td>Duplicate</td></tr>
        <tr><td><b>Ctrl+Z</b></td><td>Undo</td></tr>
        <tr><td><b>Ctrl+Y</b></td><td>Redo</td></tr>
        </table>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts)
        msg.exec()
    
    # ===== Array Tools =====
    
    def _show_linear_array_dialog(self):
        """Show linear array dialog."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QSpinBox,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Linear Array")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)
        
        count_spin = QSpinBox()
        count_spin.setRange(2, 100)
        count_spin.setValue(3)
        layout.addRow("Count:", count_spin)
        
        offset_x = QDoubleSpinBox()
        offset_x.setRange(-100, 100)
        offset_x.setValue(1.0)
        offset_x.setSingleStep(0.1)
        layout.addRow("Offset X:", offset_x)
        
        offset_y = QDoubleSpinBox()
        offset_y.setRange(-100, 100)
        offset_y.setValue(0.0)
        offset_y.setSingleStep(0.1)
        layout.addRow("Offset Y:", offset_y)
        
        offset_z = QDoubleSpinBox()
        offset_z.setRange(-100, 100)
        offset_z.setValue(0.0)
        offset_z.setSingleStep(0.1)
        layout.addRow("Offset Z:", offset_z)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            from adaptivecad.app.array_tools import linear_array
            offset = np.array([offset_x.value(), offset_y.value(), offset_z.value()])
            
            for idx in self._selected_indices:
                if 0 <= idx < len(self.scene.prims):
                    new_prims = linear_array(self.scene.prims[idx], count_spin.value(), offset)
                    for prim in new_prims[1:]:  # Skip original
                        self.scene.add(prim)
            
            self._update_scene_display()
            self.statusBar().showMessage("Created linear array", 2000)
    
    def _show_circular_array_dialog(self):
        """Show circular array dialog."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QSpinBox,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Circular Array")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)
        
        count_spin = QSpinBox()
        count_spin.setRange(2, 100)
        count_spin.setValue(6)
        layout.addRow("Count:", count_spin)
        
        radius_spin = QDoubleSpinBox()
        radius_spin.setRange(0.1, 100)
        radius_spin.setValue(2.0)
        radius_spin.setSingleStep(0.1)
        layout.addRow("Radius:", radius_spin)
        
        axis_combo = QComboBox()
        axis_combo.addItems(["Z", "Y", "X"])
        layout.addRow("Axis:", axis_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            from adaptivecad.app.array_tools import circular_array
            axis = axis_combo.currentText().lower()
            
            for idx in self._selected_indices:
                if 0 <= idx < len(self.scene.prims):
                    new_prims = circular_array(self.scene.prims[idx], count_spin.value(), 
                                              radius_spin.value(), axis)
                    for prim in new_prims[1:]:  # Skip original
                        self.scene.add(prim)
            
            self._update_scene_display()
            self.statusBar().showMessage("Created circular array", 2000)
    
    def _show_grid_array_dialog(self):
        """Show grid array dialog."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QSpinBox,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Grid Array")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)
        
        count_x = QSpinBox()
        count_x.setRange(1, 50)
        count_x.setValue(3)
        layout.addRow("Count X:", count_x)
        
        count_y = QSpinBox()
        count_y.setRange(1, 50)
        count_y.setValue(3)
        layout.addRow("Count Y:", count_y)
        
        count_z = QSpinBox()
        count_z.setRange(1, 50)
        count_z.setValue(1)
        layout.addRow("Count Z:", count_z)
        
        spacing_x = QDoubleSpinBox()
        spacing_x.setRange(0.1, 100)
        spacing_x.setValue(1.0)
        layout.addRow("Spacing X:", spacing_x)
        
        spacing_y = QDoubleSpinBox()
        spacing_y.setRange(0.1, 100)
        spacing_y.setValue(1.0)
        layout.addRow("Spacing Y:", spacing_y)
        
        spacing_z = QDoubleSpinBox()
        spacing_z.setRange(0.1, 100)
        spacing_z.setValue(1.0)
        layout.addRow("Spacing Z:", spacing_z)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            from adaptivecad.app.array_tools import grid_array
            
            for idx in self._selected_indices:
                if 0 <= idx < len(self.scene.prims):
                    new_prims = grid_array(self.scene.prims[idx],
                                          count_x.value(), count_y.value(), count_z.value(),
                                          spacing_x.value(), spacing_y.value(), spacing_z.value())
                    for prim in new_prims[1:]:  # Skip original
                        self.scene.add(prim)
            
            self._update_scene_display()
            self.statusBar().showMessage("Created grid array", 2000)
    
    # ===== Alignment Tools =====
    
    def _align_selection(self, mode: str, axis: str):
        """Align selected primitives."""
        if len(self._selected_indices) < 2:
            self.statusBar().showMessage("Select at least 2 objects to align", 2000)
            return
        
        from adaptivecad.app.align_tools import align_primitives
        
        prims = [self.scene.prims[i] for i in self._selected_indices if 0 <= i < len(self.scene.prims)]
        align_primitives(prims, mode, axis)
        self._update_scene_display()
        self.statusBar().showMessage(f"Aligned to {mode} {axis.upper()}", 2000)
    
    def _distribute_selection(self, axis: str):
        """Distribute selected primitives evenly."""
        if len(self._selected_indices) < 3:
            self.statusBar().showMessage("Select at least 3 objects to distribute", 2000)
            return
        
        from adaptivecad.app.align_tools import distribute_primitives
        
        prims = [self.scene.prims[i] for i in self._selected_indices if 0 <= i < len(self.scene.prims)]
        distribute_primitives(prims, axis)
        self._update_scene_display()
        self.statusBar().showMessage(f"Distributed along {axis.upper()}", 2000)
    
    def _mirror_selection(self, axis: str):
        """Mirror selected primitives."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from adaptivecad.app.array_tools import mirror_primitive
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                mirrored = mirror_primitive(self.scene.prims[idx], axis)
                self.scene.add(mirrored)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Mirrored across {axis.upper()}", 2000)
    
    def _snap_selection_to_grid(self):
        """Snap selected primitives to grid."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from adaptivecad.app.align_tools import snap_to_grid
        
        grid_size = 0.5  # Default grid size
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                snap_to_grid(self.scene.prims[idx], grid_size)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Snapped to grid ({grid_size})", 2000)
    
    # ===== Boolean Operations =====
    
    def _apply_boolean(self, operation: str):
        """Apply boolean operation to selection."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from adaptivecad.app.boolean_ops import apply_boolean_to_selection
        apply_boolean_to_selection(self.scene, self._selected_indices, operation)
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied {operation} operation", 2000)
    
    def _show_boolean_dialog(self):
        """Show boolean operations dialog."""
        if not self._selected_indices:
            self.statusBar().showMessage("No objects selected", 2000)
            return
        
        from adaptivecad.app.boolean_ops import BooleanOperationsDialog
        dialog = BooleanOperationsDialog(self)
        
        if dialog.exec():
            operation = dialog.get_operation()
            self._apply_boolean(operation)
    
    # ===== Camera Tools =====
    
    def _set_camera_preset(self, preset_name: str):
        """Set camera to a preset view."""
        if not self.viewport or not hasattr(self.viewport, 'cam_pos'):
            return
        
        from adaptivecad.app.camera_tools import CameraPresets
        
        presets = {
            'front': CameraPresets.front,
            'back': CameraPresets.back,
            'right': CameraPresets.right,
            'left': CameraPresets.left,
            'top': CameraPresets.top,
            'bottom': CameraPresets.bottom,
            'isometric': CameraPresets.isometric,
        }
        
        if preset_name in presets:
            pos, rot = presets[preset_name]()
            self.viewport.cam_pos = pos
            self.viewport.cam_rot = rot
            self.viewport.update()
            self.statusBar().showMessage(f"Camera: {preset_name.capitalize()}", 2000)
    
    def _fit_selected(self):
        """Fit selected objects in view."""
        if not self._selected_indices or not self.viewport:
            return
        
        from adaptivecad.app.align_tools import get_selection_bounds
        from adaptivecad.app.camera_tools import frame_bounds
        
        prims = [self.scene.prims[i] for i in self._selected_indices if 0 <= i < len(self.scene.prims)]
        if not prims:
            return
        
        min_pt, max_pt = get_selection_bounds(prims)
        
        if hasattr(self.viewport, 'cam_pos') and hasattr(self.viewport, 'cam_rot'):
            new_pos, distance = frame_bounds(min_pt, max_pt, self.viewport.cam_rot)
            self.viewport.cam_pos = new_pos
            self.viewport.update()
            self.statusBar().showMessage(f"Framed {len(prims)} object(s)", 2000)
    
    # ===== Measurement Tools =====
    
    def _measure_distance(self):
        """Start distance measurement mode."""
        if len(self._selected_indices) >= 2:
            from adaptivecad.app.measurement_tools import measure_distance_between_prims
            idx1, idx2 = self._selected_indices[:2]
            if 0 <= idx1 < len(self.scene.prims) and 0 <= idx2 < len(self.scene.prims):
                dist = measure_distance_between_prims(self.scene.prims[idx1], self.scene.prims[idx2])
                QMessageBox.information(self, "Distance Measurement", 
                                      f"Distance between centers: {dist:.4f} units")
        else:
            self.statusBar().showMessage("Select 2 objects to measure distance", 3000)
    
    def _analyze_volume(self):
        """Analyze volume of selected object."""
        if not self._selected_indices:
            self.statusBar().showMessage("No object selected", 2000)
            return
        
        from adaptivecad.app.measurement_tools import estimate_surface_area_sdf, estimate_volume_sdf
        
        idx = self._selected_indices[0]
        if 0 <= idx < len(self.scene.prims):
            progress = QProgressDialog("Analyzing volume...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            try:
                volume = estimate_volume_sdf(self.scene, idx, resolution=30)
                progress.setValue(50)
                area = estimate_surface_area_sdf(self.scene, idx, resolution=30)
                progress.setValue(100)
                progress.close()
                
                QMessageBox.information(
                    self, "Volume Analysis",
                    f"<b>Primitive {idx}</b><br>"
                    f"Estimated Volume: {volume:.4f} cubic units<br>"
                    f"Estimated Surface Area: {area:.4f} square units<br>"
                    f"<i>(Approximation based on SDF sampling)</i>"
                )
            except Exception as e:
                progress.close()
                QMessageBox.warning(self, "Analysis Failed", f"Could not analyze: {e}")

    # ===== Phase / πₐ Demo Tools =====

    def _add_pia_adaptive_circle_demo(self):
        """Add a πₐ-scaled circle tube to the scene (visualizes conformal scaling)."""

        try:
            from adaptivecad.app.phase_tools import add_pi_a_adaptive_circle_demo

            added = add_pi_a_adaptive_circle_demo(self.scene)
            self._update_scene_display()
            self._fit_all()
            if added <= 0:
                QMessageBox.information(
                    self,
                    "πₐ Demo",
                    "Could not add the πₐ demo (primitive budget may be full).",
                )
            else:
                self.statusBar().showMessage(f"Added πₐ adaptive circle ({added} prims)", 3000)
        except Exception as e:
            QMessageBox.warning(self, "πₐ Demo Failed", f"Could not add πₐ demo: {e}")

    def _add_torus_phase_path_demo(self):
        """Add a torus-parameter path tube to the scene."""

    def _add_polar_pia_adaptive_circle_demo(self):
        """Add a polar adaptive-π tube where the boundary changes with angle."""

        try:
            from adaptivecad.app.phase_tools import add_polar_pi_adaptive_circle_demo

            added = add_polar_pi_adaptive_circle_demo(self.scene)
            self._update_scene_display()
            self._fit_all()
            if added <= 0:
                QMessageBox.information(
                    self,
                    "Polar πₐ Shape",
                    "Could not add the polar πₐ shape (primitive budget may be full).",
                )
            else:
                self.statusBar().showMessage(f"Added polar πₐ shape ({added} prims)", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Polar πₐ Shape Failed", f"Could not add polar πₐ shape: {e}")

    def _add_torus_phase_path_demo(self):
        """Add a torus-parameter path tube to the scene."""

        try:
            from adaptivecad.app.phase_tools import add_torus_phase_path_demo

            added = add_torus_phase_path_demo(self.scene)
            self._update_scene_display()
            self._fit_all()
            if added <= 0:
                QMessageBox.information(
                    self,
                    "Torus Phase Demo",
                    "Could not add the torus phase path (primitive budget may be full).",
                )
            else:
                self.statusBar().showMessage(f"Added torus phase path ({added} prims)", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Torus Phase Demo Failed", f"Could not add torus demo: {e}")
    
    # ===== Edge Modification Tools =====
    
    def _apply_fillet(self):
        """Apply fillet (round edges) to selected objects."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.edge_tools import apply_fillet
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select an object to fillet", 2000)
            return
        
        radius, ok = QInputDialog.getDouble(
            self, "Fillet", "Fillet Radius:", 0.5, 0.01, 100.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = apply_fillet(self.scene.prims[idx], radius)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied fillet (r={radius})", 2000)
    
    def _apply_chamfer(self):
        """Apply chamfer (bevel edges) to selected objects."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.edge_tools import apply_chamfer
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select an object to chamfer", 2000)
            return
        
        distance, ok = QInputDialog.getDouble(
            self, "Chamfer", "Chamfer Distance:", 0.5, 0.01, 100.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = apply_chamfer(self.scene.prims[idx], distance)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied chamfer (d={distance})", 2000)
    
    # ===== Surface Modification Tools =====
    
    def _apply_shell(self):
        """Hollow out selected objects."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.shell_tools import shell_primitive
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select an object to shell", 2000)
            return
        
        thickness, ok = QInputDialog.getDouble(
            self, "Shell", "Wall Thickness:", 1.0, 0.01, 100.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = shell_primitive(self.scene.prims[idx], thickness)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied shell (thickness={thickness})", 2000)
    
    def _apply_offset(self):
        """Offset surface of selected objects."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.shell_tools import offset_surface
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select an object to offset", 2000)
            return
        
        distance, ok = QInputDialog.getDouble(
            self, "Offset Surface", "Offset Distance (+ expand, - shrink):", 
            0.5, -100.0, 100.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = offset_surface(self.scene.prims[idx], distance)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied offset (d={distance})", 2000)
    
    def _apply_thicken(self):
        """Thicken surface of selected objects."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.shell_tools import thicken_surface
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select an object to thicken", 2000)
            return
        
        thickness, ok = QInputDialog.getDouble(
            self, "Thicken Surface", "Thickness:", 1.0, 0.01, 100.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = thicken_surface(self.scene.prims[idx], thickness)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Applied thicken (t={thickness})", 2000)
    
    # ===== Sketch Tools =====
    
    def _create_sketch_rectangle(self):
        """Create a 2D rectangle sketch."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

        from adaptivecad.app.sketch_tools import sketch_rectangle
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Rectangle Sketch")
        layout = QFormLayout(dialog)
        
        width_spin = QDoubleSpinBox()
        width_spin.setRange(0.1, 1000.0)
        width_spin.setValue(10.0)
        layout.addRow("Width:", width_spin)
        
        height_spin = QDoubleSpinBox()
        height_spin.setRange(0.1, 1000.0)
        height_spin.setValue(10.0)
        layout.addRow("Height:", height_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            prim = sketch_rectangle(width_spin.value(), height_spin.value())
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created rectangle sketch {width_spin.value()}×{height_spin.value()}", 2000)
    
    def _create_sketch_circle(self):
        """Create a 2D circle sketch."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.sketch_tools import sketch_circle
        
        radius, ok = QInputDialog.getDouble(
            self, "Circle Sketch", "Radius:", 5.0, 0.1, 1000.0, 2
        )
        if ok:
            prim = sketch_circle(radius)
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created circle sketch (r={radius})", 2000)
    
    def _create_sketch_ellipse(self):
        """Create a 2D ellipse sketch."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

        from adaptivecad.app.sketch_tools import sketch_ellipse
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Ellipse Sketch")
        layout = QFormLayout(dialog)
        
        rx_spin = QDoubleSpinBox()
        rx_spin.setRange(0.1, 1000.0)
        rx_spin.setValue(5.0)
        layout.addRow("X Radius:", rx_spin)
        
        ry_spin = QDoubleSpinBox()
        ry_spin.setRange(0.1, 1000.0)
        ry_spin.setValue(3.0)
        layout.addRow("Y Radius:", ry_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            prim = sketch_ellipse(rx_spin.value(), ry_spin.value())
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage("Created ellipse sketch", 2000)
    
    def _create_sketch_polygon(self):
        """Create a 2D polygon sketch."""
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QSpinBox,
        )

        from adaptivecad.app.sketch_tools import sketch_polygon
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Polygon Sketch")
        layout = QFormLayout(dialog)
        
        radius_spin = QDoubleSpinBox()
        radius_spin.setRange(0.1, 1000.0)
        radius_spin.setValue(5.0)
        layout.addRow("Radius:", radius_spin)
        
        sides_spin = QSpinBox()
        sides_spin.setRange(3, 20)
        sides_spin.setValue(6)
        layout.addRow("Sides:", sides_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            prim = sketch_polygon(radius_spin.value(), sides_spin.value())
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created {sides_spin.value()}-sided polygon", 2000)
    
    def _create_sketch_line(self):
        """Create a line segment."""
        self.statusBar().showMessage("Line tool not yet implemented - use sketch primitives", 3000)
    
    def _create_sketch_arc(self):
        """Create an arc."""
        self.statusBar().showMessage("Arc tool not yet implemented - use sketch primitives", 3000)
    
    # ===== 3D Modeling Tools =====
    
    def _extrude_selection(self):
        """Extrude selected 2D sketch to 3D."""
        from PySide6.QtWidgets import QInputDialog

        from adaptivecad.app.extrude_tools import extrude_profile
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select a sketch to extrude", 2000)
            return
        
        depth, ok = QInputDialog.getDouble(
            self, "Extrude", "Extrusion Depth:", 10.0, 0.1, 1000.0, 2
        )
        if not ok:
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = extrude_profile(self.scene.prims[idx], depth, centered=True)
        
        self._update_scene_display()
        self.statusBar().showMessage(f"Extruded {len(self._selected_indices)} sketch(es)", 2000)
    
    def _revolve_selection(self):
        """Revolve selected profile around axis."""
        from adaptivecad.app.extrude_tools import revolve_profile
        
        if not self._selected_indices:
            self.statusBar().showMessage("Select a profile to revolve", 2000)
            return
        
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                self.scene.prims[idx] = revolve_profile(self.scene.prims[idx], axis='Z', angle=360.0)
        
        self._update_scene_display()
        self.statusBar().showMessage("Revolved profile(s)", 2000)
    
    def _loft_selection(self):
        """Loft between selected profiles."""
        from adaptivecad.app.extrude_tools import loft_between_profiles
        
        if len(self._selected_indices) < 2:
            self.statusBar().showMessage("Select 2 profiles to loft", 2000)
            return
        
        idx1, idx2 = self._selected_indices[:2]
        if 0 <= idx1 < len(self.scene.prims) and 0 <= idx2 < len(self.scene.prims):
            loft_prims = loft_between_profiles(
                self.scene.prims[idx1], 
                self.scene.prims[idx2], 
                steps=10
            )
            
            # Remove originals and add loft
            self.scene.prims = [p for i, p in enumerate(self.scene.prims) 
                               if i not in [idx1, idx2]]
            self.scene.prims.extend(loft_prims)
            
            self._update_scene_display()
            self.statusBar().showMessage(f"Created loft with {len(loft_prims)} steps", 2000)
    
    def _sweep_selection(self):
        """Sweep profile along path."""
        self.statusBar().showMessage("Sweep tool not yet implemented - use extrude/revolve", 3000)
    
    # ===== Construction Geometry Tools =====
    
    def _create_datum_plane(self):
        """Create a reference plane."""
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
        )

        from adaptivecad.app.construction_tools import DatumPlane
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Work Plane")
        layout = QFormLayout(dialog)
        
        orientation_combo = QComboBox()
        orientation_combo.addItems(["XY", "XZ", "YZ"])
        layout.addRow("Orientation:", orientation_combo)
        
        offset_spin = QDoubleSpinBox()
        offset_spin.setRange(-1000.0, 1000.0)
        offset_spin.setValue(0.0)
        layout.addRow("Offset:", offset_spin)
        
        size_spin = QDoubleSpinBox()
        size_spin.setRange(1.0, 1000.0)
        size_spin.setValue(20.0)
        layout.addRow("Size:", size_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            orientation = orientation_combo.currentText()
            offset = offset_spin.value()
            size = size_spin.value()
            
            if orientation == 'XY':
                plane = DatumPlane.XY(offset, size)
            elif orientation == 'XZ':
                plane = DatumPlane.XZ(offset, size)
            else:
                plane = DatumPlane.YZ(offset, size)
            
            # Add as primitive for visualization
            prim = plane.as_primitive()
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created work plane: {plane.name}", 2000)
    
    def _create_datum_axis(self):
        """Create a reference axis."""
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout

        from adaptivecad.app.construction_tools import DatumAxis
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Datum Axis")
        layout = QFormLayout(dialog)
        
        axis_combo = QComboBox()
        axis_combo.addItems(["X", "Y", "Z"])
        layout.addRow("Axis:", axis_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            axis_name = axis_combo.currentText()
            
            if axis_name == 'X':
                axis = DatumAxis.X()
            elif axis_name == 'Y':
                axis = DatumAxis.Y()
            else:
                axis = DatumAxis.Z()
            
            prim = axis.as_primitive()
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created {axis_name}-axis", 2000)
    
    def _create_reference_point(self):
        """Create a reference point."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

        from adaptivecad.app.construction_tools import ReferencePoint
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Reference Point")
        layout = QFormLayout(dialog)
        
        x_spin = QDoubleSpinBox()
        x_spin.setRange(-1000.0, 1000.0)
        x_spin.setValue(0.0)
        layout.addRow("X:", x_spin)
        
        y_spin = QDoubleSpinBox()
        y_spin.setRange(-1000.0, 1000.0)
        y_spin.setValue(0.0)
        layout.addRow("Y:", y_spin)
        
        z_spin = QDoubleSpinBox()
        z_spin.setRange(-1000.0, 1000.0)
        z_spin.setValue(0.0)
        layout.addRow("Z:", z_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            position = np.array([x_spin.value(), y_spin.value(), z_spin.value()])
            point = ReferencePoint(position)
            
            prim = point.as_primitive()
            self.scene.prims.append(prim)
            self._update_scene_display()
            self.statusBar().showMessage(f"Created reference point at ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})", 2000)
    
    # ===== Import Tools =====
    
    def _import_mesh(self):
        """Import STL/OBJ and convert to SDF primitive."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Mesh",
            str(Path.home()),
            "3D Models (*.stl *.STL *.obj *.OBJ);;STL Files (*.stl *.STL);;OBJ Files (*.obj *.OBJ);;All Files (*)"
        )
        
        if not path:
            return
        
        try:
            from adaptivecad.aacore.mesh_sdf import MeshSDF
            from adaptivecad.aacore.sdf import KIND_MESH_IMPORT, Prim, Xform
            from adaptivecad.app.mesh_import import import_mesh_as_sdf
            
            # Show progress
            progress = QProgressDialog("Importing mesh...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            progress.setValue(20)
            
            # Import and convert
            converter = import_mesh_as_sdf(Path(path), scale=1.0, center=True)
            
            if converter is None:
                progress.close()
                QMessageBox.critical(self, "Import Failed", "Could not load mesh file")
                return
            
            progress.setValue(50)
            
            # Create MeshSDF with cache
            mesh_sdf = MeshSDF(converter, cache_resolution=64)
            
            progress.setValue(80)
            
            # Create primitive
            prim = Prim(
                kind=KIND_MESH_IMPORT,
                params=[0, 0, 0, 0],  # No params needed
                xform=Xform(),
                color=(0.7, 0.7, 0.8)
            )
            prim.mesh_sdf = mesh_sdf
            
            # Add to scene
            self.scene.add(prim)
            self._update_scene_display()
            
            progress.setValue(100)
            progress.close()
            
            # Show info
            num_tris = len(converter.triangles)
            bounds = converter.bounds_max - converter.bounds_min
            QMessageBox.information(
                self, "Mesh Imported",
                f"<b>Successfully imported mesh!</b><br><br>"
                f"<b>Source:</b> {Path(path).name}<br>"
                f"<b>Triangles:</b> {num_tris}<br>"
                f"<b>Bounds:</b> {bounds[0]:.2f} × {bounds[1]:.2f} × {bounds[2]:.2f}<br>"
                f"<b>Cache:</b> 64³ distance field<br><br>"
                f"<i>Mesh converted to SDF - ready to slice!</i>"
            )
            
            self.statusBar().showMessage(f"Imported {Path(path).name} ({num_tris} triangles)", 5000)
            
        except Exception as e:
            log.exception("Mesh import failed")
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Import Error", f"Failed to import mesh:\\n{e}")


def launch_app():
    """Launch the AdaptiveCAD application."""
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Set application info
    app.setApplicationName("AdaptiveCAD")
    app.setOrganizationName("AdaptiveCAD")
    app.setOrganizationDomain("adaptivecad.io")
    
    # Create and show main window
    window = AdaptiveCADApp()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch_app())
