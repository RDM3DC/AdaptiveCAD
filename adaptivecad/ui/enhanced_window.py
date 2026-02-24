"""
AdaptiveCAD Enhanced Main Window

Provides improved UI layout, organization, and user experience
while maintaining compatibility with existing features.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

# Qt6 enum compatibility
try:
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _Horizontal = Qt.Orientation.Horizontal
    _TopToolBarArea = Qt.ToolBarArea.TopToolBarArea
    _LeftDockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
    _RightDockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
except AttributeError:
    _AlignCenter = Qt.AlignCenter
    _Horizontal = Qt.Horizontal
    _TopToolBarArea = Qt.TopToolBarArea
    _LeftDockWidgetArea = Qt.LeftDockWidgetArea
    _RightDockWidgetArea = Qt.RightDockWidgetArea

try:
    _VLine = QFrame.Shape.VLine
    _HLine = QFrame.Shape.HLine
    _Expanding = QSizePolicy.Policy.Expanding
    _Preferred = QSizePolicy.Policy.Preferred
except AttributeError:
    _VLine = QFrame.VLine
    _HLine = QFrame.HLine
    _Expanding = QSizePolicy.Expanding
    _Preferred = QSizePolicy.Preferred

from .theme import list_themes

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class ViewModeWidget(QWidget):
    """Widget for switching between viewport modes (OCC/Analytic)."""
    
    modeChanged = Signal(str)  # 'occ' or 'analytic'
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Mode label
        self.label = QLabel("Mode:")
        self.label.setProperty("muted", True)
        layout.addWidget(self.label)
        
        # Mode buttons
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        self.btn_occ = QPushButton("Mesh")
        self.btn_occ.setCheckable(True)
        self.btn_occ.setChecked(True)
        self.btn_occ.setToolTip("OpenCASCADE mesh-based rendering")
        self.btn_occ.setFixedWidth(60)
        
        self.btn_analytic = QPushButton("SDF")
        self.btn_analytic.setCheckable(True)
        self.btn_analytic.setToolTip("Analytic SDF rendering (no triangles)")
        self.btn_analytic.setFixedWidth(60)
        
        self.btn_group.addButton(self.btn_occ, 0)
        self.btn_group.addButton(self.btn_analytic, 1)
        
        layout.addWidget(self.btn_occ)
        layout.addWidget(self.btn_analytic)
        
        # Connect signals
        self.btn_group.idClicked.connect(self._on_mode_clicked)
    
    def _on_mode_clicked(self, id: int):
        mode = 'occ' if id == 0 else 'analytic'
        self.modeChanged.emit(mode)
    
    def setMode(self, mode: str):
        """Set the current mode programmatically."""
        if mode == 'occ':
            self.btn_occ.setChecked(True)
        else:
            self.btn_analytic.setChecked(True)


class ViewPresetsWidget(QWidget):
    """Widget for quick view presets."""
    
    viewChanged = Signal(str)  # 'top', 'front', 'right', 'iso', etc.
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        
        presets = [
            ("Top", "top", "View from top (XY plane)"),
            ("Front", "front", "View from front (XZ plane)"),
            ("Right", "right", "View from right (YZ plane)"),
            ("ISO", "iso", "Isometric view"),
        ]
        
        for name, code, tooltip in presets:
            btn = QPushButton(name)
            btn.setToolTip(tooltip)
            btn.setFixedWidth(45)
            btn.clicked.connect(lambda checked, c=code: self.viewChanged.emit(c))
            layout.addWidget(btn)


class CoordinateDisplay(QWidget):
    """Widget showing current cursor coordinates."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        
        self.labels = {}
        for axis, color in [("X", "#ef4444"), ("Y", "#22c55e"), ("Z", "#3b82f6")]:
            lbl = QLabel(f"{axis}: 0.000")
            lbl.setStyleSheet(f"color: {color}; font-family: monospace;")
            lbl.setFixedWidth(80)
            layout.addWidget(lbl)
            self.labels[axis] = lbl
    
    def setCoordinates(self, x: float, y: float, z: float):
        """Update the displayed coordinates."""
        self.labels["X"].setText(f"X: {x:>7.3f}")
        self.labels["Y"].setText(f"Y: {y:>7.3f}")
        self.labels["Z"].setText(f"Z: {z:>7.3f}")


class SelectionInfo(QWidget):
    """Widget showing current selection information."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        
        self.icon_label = QLabel("●")
        self.icon_label.setStyleSheet("color: #6b7280;")
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("No selection")
        self.text_label.setProperty("muted", True)
        layout.addWidget(self.text_label)
    
    def setSelection(self, count: int, type_name: str = "object"):
        """Update selection display."""
        if count == 0:
            self.icon_label.setStyleSheet("color: #6b7280;")
            self.text_label.setText("No selection")
        elif count == 1:
            self.icon_label.setStyleSheet("color: #22c55e;")
            self.text_label.setText(f"1 {type_name} selected")
        else:
            self.icon_label.setStyleSheet("color: #3b82f6;")
            self.text_label.setText(f"{count} {type_name}s selected")


class EnhancedStatusBar(QStatusBar):
    """Enhanced status bar with mode indicator, coordinates, and selection info."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Mode indicator (left)
        self.mode_label = QLabel("Ready")
        self.mode_label.setMinimumWidth(100)
        self.addWidget(self.mode_label)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(_VLine)
        sep1.setStyleSheet("color: #30363d;")
        self.addWidget(sep1)
        
        # Selection info
        self.selection_info = SelectionInfo()
        self.addWidget(self.selection_info)
        
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(_Expanding, _Preferred)
        self.addWidget(spacer)
        
        # Coordinate display (right)
        self.coord_display = CoordinateDisplay()
        self.addPermanentWidget(self.coord_display)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(_VLine)
        sep2.setStyleSheet("color: #30363d;")
        self.addPermanentWidget(sep2)
        
        # Viewport mode
        self.viewport_mode = QLabel("OCC")
        self.viewport_mode.setFixedWidth(60)
        self.viewport_mode.setAlignment(_AlignCenter)
        self.addPermanentWidget(self.viewport_mode)
    
    def setMode(self, mode: str):
        """Set the current operation mode."""
        self.mode_label.setText(mode)
    
    def setViewportMode(self, mode: str):
        """Set the viewport mode indicator."""
        self.viewport_mode.setText(mode.upper())
    
    def updateCoordinates(self, x: float, y: float, z: float):
        """Update cursor coordinates."""
        self.coord_display.setCoordinates(x, y, z)
    
    def updateSelection(self, count: int, type_name: str = "object"):
        """Update selection information."""
        self.selection_info.setSelection(count, type_name)


class MenuBuilder:
    """Helper class for building organized menus."""
    
    def __init__(self, menubar: QMenuBar, main_window: QMainWindow):
        self.menubar = menubar
        self.main_window = main_window
        self.actions: Dict[str, QAction] = {}
        self.menus: Dict[str, QMenu] = {}
    
    def add_menu(self, name: str) -> QMenu:
        """Add a top-level menu."""
        menu = self.menubar.addMenu(name)
        self.menus[name.lower().replace("&", "")] = menu
        return menu
    
    def add_action(
        self,
        menu: QMenu,
        name: str,
        callback: Optional[Callable] = None,
        shortcut: Optional[str] = None,
        icon: Optional[QIcon] = None,
        tooltip: Optional[str] = None,
        checkable: bool = False,
        checked: bool = False,
        separator_after: bool = False,
    ) -> QAction:
        """Add an action to a menu."""
        action = QAction(name, self.main_window)
        
        if callback:
            action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon:
            action.setIcon(icon)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        
        menu.addAction(action)
        
        if separator_after:
            menu.addSeparator()
        
        # Store action by cleaned name
        key = name.lower().replace("&", "").replace(" ", "_").replace("...", "")
        self.actions[key] = action
        
        return action
    
    def add_submenu(self, parent_menu: QMenu, name: str) -> QMenu:
        """Add a submenu."""
        submenu = parent_menu.addMenu(name)
        key = name.lower().replace("&", "").replace(" ", "_")
        self.menus[key] = submenu
        return submenu
    
    def add_separator(self, menu: QMenu):
        """Add a separator to a menu."""
        menu.addSeparator()
    
    def get_action(self, name: str) -> Optional[QAction]:
        """Get an action by name."""
        key = name.lower().replace("&", "").replace(" ", "_").replace("...", "")
        return self.actions.get(key)
    
    def get_menu(self, name: str) -> Optional[QMenu]:
        """Get a menu by name."""
        key = name.lower().replace("&", "").replace(" ", "_")
        return self.menus.get(key)


class ToolbarBuilder:
    """Helper class for building organized toolbars."""
    
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
        self.toolbars: Dict[str, QToolBar] = {}
    
    def add_toolbar(
        self,
        name: str,
        area = None,
        movable: bool = True,
        icon_size: int = 24,
    ) -> QToolBar:
        if area is None:
            area = _TopToolBarArea
        """Create and add a toolbar."""
        toolbar = QToolBar(name, self.main_window)
        toolbar.setMovable(movable)
        toolbar.setIconSize(QSize(icon_size, icon_size))
        toolbar.setObjectName(f"toolbar_{name.lower().replace(' ', '_')}")
        
        self.main_window.addToolBar(area, toolbar)
        self.toolbars[name.lower()] = toolbar
        
        return toolbar
    
    def add_action(
        self,
        toolbar: QToolBar,
        name: str,
        callback: Optional[Callable] = None,
        icon: Optional[QIcon] = None,
        tooltip: Optional[str] = None,
        checkable: bool = False,
    ) -> QAction:
        """Add an action to a toolbar."""
        action = QAction(name, self.main_window)
        
        if callback:
            action.triggered.connect(callback)
        if icon:
            action.setIcon(icon)
        if tooltip:
            action.setToolTip(tooltip)
        if checkable:
            action.setCheckable(True)
        
        toolbar.addAction(action)
        return action
    
    def add_widget(self, toolbar: QToolBar, widget: QWidget):
        """Add a widget to a toolbar."""
        toolbar.addWidget(widget)
    
    def add_separator(self, toolbar: QToolBar):
        """Add a separator to a toolbar."""
        toolbar.addSeparator()
    
    def get_toolbar(self, name: str) -> Optional[QToolBar]:
        """Get a toolbar by name."""
        return self.toolbars.get(name.lower())


def create_file_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the File menu with standard actions."""
    menu = builder.add_menu("&File")
    
    builder.add_action(menu, "&New Project", callbacks.get("new"), "Ctrl+N",
                      tooltip="Create a new project")
    builder.add_action(menu, "&Open Project...", callbacks.get("open"), "Ctrl+O",
                      tooltip="Open an existing project")
    builder.add_separator(menu)
    builder.add_action(menu, "&Save", callbacks.get("save"), "Ctrl+S",
                      tooltip="Save the current project")
    builder.add_action(menu, "Save &As...", callbacks.get("save_as"), "Ctrl+Shift+S",
                      tooltip="Save project with a new name")
    builder.add_separator(menu)
    
    # Import submenu
    import_menu = builder.add_submenu(menu, "&Import")
    builder.add_action(import_menu, "Import &STL...", callbacks.get("import_stl"),
                      tooltip="Import STL mesh file")
    builder.add_action(import_menu, "Import S&TEP...", callbacks.get("import_step"),
                      tooltip="Import STEP CAD file")
    builder.add_action(import_menu, "Import &OBJ...", callbacks.get("import_obj"),
                      tooltip="Import OBJ mesh file")
    
    # Export submenu
    export_menu = builder.add_submenu(menu, "&Export")
    builder.add_action(export_menu, "Export &STL...", callbacks.get("export_stl"), "Ctrl+E",
                      tooltip="Export as STL mesh")
    builder.add_action(export_menu, "Export STE&P...", callbacks.get("export_step"),
                      tooltip="Export as STEP CAD file")
    builder.add_action(export_menu, "Export &G-Code...", callbacks.get("export_gcode"),
                      tooltip="Export as G-Code for CNC/3D printing")
    
    builder.add_separator(menu)
    builder.add_action(menu, "E&xit", callbacks.get("exit"), "Ctrl+Q",
                      tooltip="Exit AdaptiveCAD")
    
    return menu


def create_edit_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Edit menu with standard actions."""
    menu = builder.add_menu("&Edit")
    
    builder.add_action(menu, "&Undo", callbacks.get("undo"), "Ctrl+Z",
                      tooltip="Undo the last action")
    builder.add_action(menu, "&Redo", callbacks.get("redo"), "Ctrl+Y",
                      tooltip="Redo the last undone action")
    builder.add_separator(menu)
    builder.add_action(menu, "Cu&t", callbacks.get("cut"), "Ctrl+X",
                      tooltip="Cut selection to clipboard")
    builder.add_action(menu, "&Copy", callbacks.get("copy"), "Ctrl+C",
                      tooltip="Copy selection to clipboard")
    builder.add_action(menu, "&Paste", callbacks.get("paste"), "Ctrl+V",
                      tooltip="Paste from clipboard")
    builder.add_action(menu, "&Delete", callbacks.get("delete"), "Del",
                      tooltip="Delete selected objects")
    builder.add_separator(menu)
    builder.add_action(menu, "Select &All", callbacks.get("select_all"), "Ctrl+A",
                      tooltip="Select all objects")
    builder.add_action(menu, "Deselect A&ll", callbacks.get("deselect_all"), "Escape",
                      tooltip="Clear selection")
    
    return menu


def create_view_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the View menu."""
    menu = builder.add_menu("&View")
    
    # Viewport submenu
    viewport_menu = builder.add_submenu(menu, "&Viewport")
    builder.add_action(viewport_menu, "&Mesh Mode (OCC)", callbacks.get("view_occ"),
                      tooltip="Switch to mesh-based OCC viewport")
    builder.add_action(viewport_menu, "&SDF Mode (Analytic)", callbacks.get("view_analytic"),
                      tooltip="Switch to analytic SDF viewport")
    
    builder.add_separator(menu)
    
    # View presets
    builder.add_action(menu, "&Top View", callbacks.get("view_top"), "Numpad 7",
                      tooltip="View from top")
    builder.add_action(menu, "&Front View", callbacks.get("view_front"), "Numpad 1",
                      tooltip="View from front")
    builder.add_action(menu, "&Right View", callbacks.get("view_right"), "Numpad 3",
                      tooltip="View from right")
    builder.add_action(menu, "&Isometric View", callbacks.get("view_iso"), "Numpad 0",
                      tooltip="Isometric view")
    builder.add_separator(menu)
    builder.add_action(menu, "&Fit All", callbacks.get("fit_all"), "F",
                      tooltip="Fit all objects in view")
    builder.add_action(menu, "Zoom to &Selection", callbacks.get("zoom_selection"), ".",
                      tooltip="Zoom to selected object")
    builder.add_separator(menu)
    
    # Display options
    builder.add_action(menu, "Show &Grid", callbacks.get("toggle_grid"),
                      checkable=True, checked=True, tooltip="Toggle grid display")
    builder.add_action(menu, "Show &Axes", callbacks.get("toggle_axes"),
                      checkable=True, checked=True, tooltip="Toggle axes display")
    builder.add_action(menu, "Show &Wireframe", callbacks.get("toggle_wireframe"),
                      checkable=True, tooltip="Toggle wireframe overlay")
    
    builder.add_separator(menu)
    
    # Panels
    panels_menu = builder.add_submenu(menu, "&Panels")
    builder.add_action(panels_menu, "&Properties", callbacks.get("toggle_properties"),
                      checkable=True, checked=True, tooltip="Toggle properties panel")
    builder.add_action(panels_menu, "&Hierarchy", callbacks.get("toggle_hierarchy"),
                      checkable=True, tooltip="Toggle object hierarchy panel")
    builder.add_action(panels_menu, "&Console", callbacks.get("toggle_console"),
                      checkable=True, tooltip="Toggle console panel")
    builder.add_action(panels_menu, "&AI Copilot", callbacks.get("toggle_ai"),
                      checkable=True, tooltip="Toggle AI assistant panel")
    
    return menu


def create_create_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Create menu for shapes."""
    menu = builder.add_menu("&Create")
    
    # Basic shapes
    basic_menu = builder.add_submenu(menu, "&Basic Shapes")
    builder.add_action(basic_menu, "&Box", callbacks.get("create_box"), "B",
                      tooltip="Create a box/cube")
    builder.add_action(basic_menu, "&Cylinder", callbacks.get("create_cylinder"), "C",
                      tooltip="Create a cylinder")
    builder.add_action(basic_menu, "&Sphere", callbacks.get("create_sphere"), "S",
                      tooltip="Create a sphere")
    builder.add_action(basic_menu, "C&one", callbacks.get("create_cone"),
                      tooltip="Create a cone")
    builder.add_action(basic_menu, "&Torus", callbacks.get("create_torus"), "T",
                      tooltip="Create a torus")
    builder.add_action(basic_menu, "Ca&psule", callbacks.get("create_capsule"),
                      tooltip="Create a capsule")
    
    # Advanced shapes
    adv_menu = builder.add_submenu(menu, "&Advanced Shapes")
    builder.add_action(adv_menu, "&Superellipse", callbacks.get("create_superellipse"),
                      tooltip="Create a superellipse/superellipsoid")
    builder.add_action(adv_menu, "Super&quad", callbacks.get("create_superquad"),
                      tooltip="Create a superquadric")
    builder.add_action(adv_menu, "&Pi Curve Shell", callbacks.get("create_pi_shell"),
                      tooltip="Create a Pi curve shell")
    builder.add_action(adv_menu, "&Helix", callbacks.get("create_helix"),
                      tooltip="Create a helix")
    builder.add_action(adv_menu, "&Ellipsoid", callbacks.get("create_ellipsoid"),
                      tooltip="Create an ellipsoid")
    
    # Mathematical surfaces
    math_menu = builder.add_submenu(menu, "&Mathematical")
    builder.add_action(math_menu, "&Mobius Strip", callbacks.get("create_mobius"),
                      tooltip="Create a Möbius strip")
    builder.add_action(math_menu, "&Klein Bottle", callbacks.get("create_klein"),
                      tooltip="Create a Klein bottle")
    builder.add_action(math_menu, "&Gyroid", callbacks.get("create_gyroid"),
                      tooltip="Create a gyroid surface")
    builder.add_action(math_menu, "&Mandelbulb", callbacks.get("create_mandelbulb"),
                      tooltip="Create a 3D Mandelbulb fractal")
    builder.add_action(math_menu, "M&enger Sponge", callbacks.get("create_menger"),
                      tooltip="Create a Menger sponge fractal")
    
    # Sketch tools
    builder.add_separator(menu)
    sketch_menu = builder.add_submenu(menu, "&Sketch")
    builder.add_action(sketch_menu, "&New Sketch", callbacks.get("new_sketch"),
                      tooltip="Create a new 2D sketch")
    builder.add_action(sketch_menu, "&Line", callbacks.get("sketch_line"),
                      tooltip="Draw a line")
    builder.add_action(sketch_menu, "&Rectangle", callbacks.get("sketch_rect"),
                      tooltip="Draw a rectangle")
    builder.add_action(sketch_menu, "&Circle", callbacks.get("sketch_circle"),
                      tooltip="Draw a circle")
    builder.add_action(sketch_menu, "&Arc", callbacks.get("sketch_arc"),
                      tooltip="Draw an arc")
    
    return menu


def create_transform_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Transform menu."""
    menu = builder.add_menu("&Transform")
    
    builder.add_action(menu, "&Move", callbacks.get("move"), "G",
                      tooltip="Move selected objects")
    builder.add_action(menu, "&Rotate", callbacks.get("rotate"), "R",
                      tooltip="Rotate selected objects")
    builder.add_action(menu, "&Scale", callbacks.get("scale"), "S",
                      tooltip="Scale selected objects")
    builder.add_separator(menu)
    builder.add_action(menu, "Mirror &X", callbacks.get("mirror_x"),
                      tooltip="Mirror across X axis")
    builder.add_action(menu, "Mirror &Y", callbacks.get("mirror_y"),
                      tooltip="Mirror across Y axis")
    builder.add_action(menu, "Mirror &Z", callbacks.get("mirror_z"),
                      tooltip="Mirror across Z axis")
    builder.add_separator(menu)
    
    # Boolean operations
    bool_menu = builder.add_submenu(menu, "&Boolean")
    builder.add_action(bool_menu, "&Union", callbacks.get("bool_union"),
                      tooltip="Combine selected objects (union)")
    builder.add_action(bool_menu, "&Difference", callbacks.get("bool_difference"),
                      tooltip="Subtract second object from first")
    builder.add_action(bool_menu, "&Intersection", callbacks.get("bool_intersection"),
                      tooltip="Keep only intersecting volume")
    
    return menu


def create_tools_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Tools menu."""
    menu = builder.add_menu("T&ools")
    
    builder.add_action(menu, "&Measure", callbacks.get("measure"),
                      tooltip="Measure distances and angles")
    builder.add_action(menu, "&Analyze", callbacks.get("analyze"),
                      tooltip="Analyze geometry properties")
    builder.add_separator(menu)
    
    # Simulation submenu
    sim_menu = builder.add_submenu(menu, "&Simulation")
    builder.add_action(sim_menu, "&Vibration Analysis", callbacks.get("sim_vibration"),
                      tooltip="Run vibration simulation")
    builder.add_action(sim_menu, "&Heat Generation", callbacks.get("sim_heat"),
                      tooltip="Run heat generation simulation")
    builder.add_action(sim_menu, "&Stress Analysis", callbacks.get("sim_stress"),
                      tooltip="Run stress analysis")
    
    # Conversion submenu
    conv_menu = builder.add_submenu(menu, "&Conversion")
    builder.add_action(conv_menu, "OCC → &Analytic", callbacks.get("occ_to_analytic"),
                      tooltip="Convert OCC mesh to analytic SDF")
    builder.add_action(conv_menu, "Analytic → &Mesh", callbacks.get("analytic_to_mesh"),
                      tooltip="Convert analytic SDF to mesh")
    
    builder.add_separator(menu)
    
    # Custom tools
    builder.add_action(menu, "Custom &Tools...", callbacks.get("custom_tools"),
                      tooltip="Manage custom tools and macros")
    builder.add_action(menu, "&Record Macro...", callbacks.get("record_macro"),
                      tooltip="Record a new macro")
    
    return menu


def create_settings_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Settings menu."""
    menu = builder.add_menu("&Settings")
    
    # Theme submenu
    theme_menu = builder.add_submenu(menu, "&Theme")
    for theme_name in list_themes():
        builder.add_action(
            theme_menu, 
            theme_name.title(),
            lambda checked, t=theme_name: callbacks.get("set_theme", lambda x: None)(t),
            tooltip=f"Switch to {theme_name} theme"
        )
    
    builder.add_separator(menu)
    builder.add_action(menu, "&Preferences...", callbacks.get("preferences"),
                      tooltip="Open preferences dialog")
    builder.add_action(menu, "&Keyboard Shortcuts...", callbacks.get("shortcuts"),
                      tooltip="Customize keyboard shortcuts")
    
    return menu


def create_help_menu(builder: MenuBuilder, callbacks: Dict[str, Callable]) -> QMenu:
    """Create the Help menu."""
    menu = builder.add_menu("&Help")
    
    builder.add_action(menu, "&Getting Started", callbacks.get("getting_started"),
                      tooltip="View getting started guide")
    builder.add_action(menu, "&Documentation", callbacks.get("documentation"),
                      tooltip="Open documentation")
    builder.add_action(menu, "&Keyboard Shortcuts", callbacks.get("shortcut_help"), "?",
                      tooltip="View keyboard shortcuts")
    builder.add_separator(menu)
    builder.add_action(menu, "&Diagnostics...", callbacks.get("diagnostics"),
                      tooltip="View system diagnostics")
    builder.add_action(menu, "Enable &Debug Logs", callbacks.get("debug_logs"),
                      checkable=True, tooltip="Enable verbose logging")
    builder.add_separator(menu)
    builder.add_action(menu, "&About AdaptiveCAD", callbacks.get("about"),
                      tooltip="About this application")
    
    return menu


def setup_enhanced_menus(main_window: QMainWindow, callbacks: Dict[str, Callable]) -> MenuBuilder:
    """Set up all enhanced menus for the main window."""
    menubar = main_window.menuBar()
    builder = MenuBuilder(menubar, main_window)
    
    create_file_menu(builder, callbacks)
    create_edit_menu(builder, callbacks)
    create_view_menu(builder, callbacks)
    create_create_menu(builder, callbacks)
    create_transform_menu(builder, callbacks)
    create_tools_menu(builder, callbacks)
    create_settings_menu(builder, callbacks)
    create_help_menu(builder, callbacks)
    
    return builder


def setup_main_toolbar(main_window: QMainWindow, callbacks: Dict[str, Callable]) -> ToolbarBuilder:
    """Set up the main toolbar with essential actions."""
    builder = ToolbarBuilder(main_window)
    
    # Main toolbar
    main_tb = builder.add_toolbar("Main")
    
    # File operations
    builder.add_action(main_tb, "New", callbacks.get("new"), tooltip="New Project (Ctrl+N)")
    builder.add_action(main_tb, "Open", callbacks.get("open"), tooltip="Open Project (Ctrl+O)")
    builder.add_action(main_tb, "Save", callbacks.get("save"), tooltip="Save Project (Ctrl+S)")
    builder.add_separator(main_tb)
    
    # Undo/Redo
    builder.add_action(main_tb, "Undo", callbacks.get("undo"), tooltip="Undo (Ctrl+Z)")
    builder.add_action(main_tb, "Redo", callbacks.get("redo"), tooltip="Redo (Ctrl+Y)")
    builder.add_separator(main_tb)
    
    # View mode widget
    view_mode = ViewModeWidget()
    view_mode.modeChanged.connect(lambda m: callbacks.get("set_view_mode", lambda x: None)(m))
    builder.add_widget(main_tb, view_mode)
    builder.add_separator(main_tb)
    
    # View presets
    view_presets = ViewPresetsWidget()
    view_presets.viewChanged.connect(lambda v: callbacks.get("set_view_preset", lambda x: None)(v))
    builder.add_widget(main_tb, view_presets)
    
    # Create toolbar
    create_tb = builder.add_toolbar("Create")
    builder.add_action(create_tb, "Box", callbacks.get("create_box"), tooltip="Create Box (B)")
    builder.add_action(create_tb, "Cylinder", callbacks.get("create_cylinder"), tooltip="Create Cylinder (C)")
    builder.add_action(create_tb, "Sphere", callbacks.get("create_sphere"), tooltip="Create Sphere (S)")
    builder.add_action(create_tb, "Torus", callbacks.get("create_torus"), tooltip="Create Torus (T)")
    builder.add_separator(create_tb)
    builder.add_action(create_tb, "Superellipse", callbacks.get("create_superellipse"), tooltip="Create Superellipse")
    builder.add_action(create_tb, "Pi Shell", callbacks.get("create_pi_shell"), tooltip="Create Pi Curve Shell")
    
    # Transform toolbar
    transform_tb = builder.add_toolbar("Transform")
    builder.add_action(transform_tb, "Move", callbacks.get("move"), tooltip="Move (G)")
    builder.add_action(transform_tb, "Rotate", callbacks.get("rotate"), tooltip="Rotate (R)")
    builder.add_action(transform_tb, "Scale", callbacks.get("scale"), tooltip="Scale")
    builder.add_separator(transform_tb)
    builder.add_action(transform_tb, "Union", callbacks.get("bool_union"), tooltip="Boolean Union")
    builder.add_action(transform_tb, "Cut", callbacks.get("bool_difference"), tooltip="Boolean Difference")
    builder.add_separator(transform_tb)
    builder.add_action(transform_tb, "Delete", callbacks.get("delete"), tooltip="Delete (Del)")
    
    return builder
