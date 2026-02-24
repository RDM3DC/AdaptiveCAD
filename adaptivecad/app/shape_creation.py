"""AdaptiveCAD Shape Creation Panel

Provides a comprehensive shape creation interface with:
- All SDF primitives accessible
- Live parameter editing
- Visual preview
- Template presets
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _Horizontal = Qt.Orientation.Horizontal
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _NoFrame = QFrame.Shape.NoFrame
except AttributeError:
    _Horizontal = Qt.Horizontal
    _AlignCenter = Qt.AlignCenter
    _NoFrame = QFrame.NoFrame


class ShapeCategory(Enum):
    """Categories for organizing shapes."""
    BASIC = "Basic"
    ADVANCED = "Advanced"
    MATHEMATICAL = "Mathematical"
    FRACTALS = "Fractals"
    TPMS = "TPMS (Triply Periodic)"


@dataclass
class ShapeParam:
    """Definition of a shape parameter."""
    name: str
    label: str
    default: float
    min_val: float
    max_val: float
    step: float = 0.1
    is_int: bool = False
    tooltip: str = ""


@dataclass
class ShapeDefinition:
    """Complete definition of a shape type."""
    kind: Any  # SDF kind constant
    name: str
    category: ShapeCategory
    icon: str
    description: str
    params: List[ShapeParam]
    color: Tuple[float, float, float] = (0.8, 0.7, 0.6)


# Import SDF kinds
from adaptivecad.aacore.sdf import (
    KIND_BOX,
    KIND_CAPSULE,
    KIND_GYROID,
    KIND_HELICOID,
    KIND_HYPERBOLIC,
    KIND_KLEIN,
    KIND_MANDELBULB,
    KIND_MENGER,
    KIND_MOBIUS,
    KIND_ORBITAL,
    KIND_QUASICRYSTAL,
    KIND_SPHERE,
    KIND_SUPERELLIPSOID,
    KIND_TORUS,
    KIND_TORUS4D,
    KIND_TREFOIL,
)

# Define all available shapes
SHAPE_DEFINITIONS: Dict[str, ShapeDefinition] = {
    # Basic Shapes
    "sphere": ShapeDefinition(
        kind=KIND_SPHERE,
        name="Sphere",
        category=ShapeCategory.BASIC,
        icon="🔵",
        description="A simple sphere defined by radius.",
        params=[
            ShapeParam("radius", "Radius", 0.5, 0.01, 10.0, 0.05, tooltip="Sphere radius"),
        ],
        color=(0.2, 0.5, 0.9),
    ),
    "box": ShapeDefinition(
        kind=KIND_BOX,
        name="Box",
        category=ShapeCategory.BASIC,
        icon="⬜",
        description="A rectangular box with adjustable dimensions.",
        params=[
            ShapeParam("size_x", "Width (X)", 0.5, 0.01, 10.0, 0.05),
            ShapeParam("size_y", "Height (Y)", 0.5, 0.01, 10.0, 0.05),
            ShapeParam("size_z", "Depth (Z)", 0.5, 0.01, 10.0, 0.05),
        ],
        color=(0.8, 0.6, 0.3),
    ),
    "capsule": ShapeDefinition(
        kind=KIND_CAPSULE,
        name="Capsule",
        category=ShapeCategory.BASIC,
        icon="💊",
        description="A cylinder with hemispherical caps.",
        params=[
            ShapeParam("radius", "Radius", 0.2, 0.01, 5.0, 0.05),
            ShapeParam("height", "Height", 0.8, 0.1, 10.0, 0.1),
        ],
        color=(0.7, 0.3, 0.5),
    ),
    "torus": ShapeDefinition(
        kind=KIND_TORUS,
        name="Torus",
        category=ShapeCategory.BASIC,
        icon="🍩",
        description="A donut-shaped ring.",
        params=[
            ShapeParam("major_radius", "Major Radius", 0.5, 0.1, 5.0, 0.05),
            ShapeParam("minor_radius", "Minor Radius", 0.15, 0.01, 2.0, 0.02),
        ],
        color=(0.9, 0.6, 0.2),
    ),
    
    # Advanced Shapes
    "superellipsoid": ShapeDefinition(
        kind=KIND_SUPERELLIPSOID,
        name="Superellipsoid",
        category=ShapeCategory.ADVANCED,
        icon="🥚",
        description="A parametric surface generalizing ellipsoids with variable roundness.",
        params=[
            ShapeParam("radius", "Radius", 0.5, 0.1, 5.0, 0.1),
            ShapeParam("power", "Power (n)", 2.0, 0.5, 8.0, 0.1, tooltip="Higher = boxier, lower = pinched"),
        ],
        color=(0.6, 0.8, 0.5),
    ),
    "mobius": ShapeDefinition(
        kind=KIND_MOBIUS,
        name="Möbius Strip",
        category=ShapeCategory.ADVANCED,
        icon="♾️",
        description="A non-orientable surface with a single side.",
        params=[
            ShapeParam("major_radius", "Major Radius", 0.5, 0.1, 3.0, 0.1),
            ShapeParam("width", "Strip Width", 0.3, 0.05, 1.0, 0.05),
        ],
        color=(0.5, 0.7, 0.9),
    ),
    "helicoid": ShapeDefinition(
        kind=KIND_HELICOID,
        name="Helicoid",
        category=ShapeCategory.ADVANCED,
        icon="🌪️",
        description="A ruled surface like a spiral ramp.",
        params=[
            ShapeParam("r_inner", "Inner Radius", 0.15, 0.01, 2.0, 0.05),
            ShapeParam("r_outer", "Outer Radius", 0.55, 0.1, 3.0, 0.05),
            ShapeParam("pitch", "Pitch", 0.35, 0.1, 2.0, 0.05),
            ShapeParam("turns", "Turns", 2.0, 0.5, 10.0, 0.5),
        ],
        color=(0.4, 0.6, 0.8),
    ),
    
    # Mathematical Shapes
    "trefoil": ShapeDefinition(
        kind=KIND_TREFOIL,
        name="Trefoil Knot",
        category=ShapeCategory.MATHEMATICAL,
        icon="🎀",
        description="A mathematical knot with three crossings.",
        params=[
            ShapeParam("scale", "Scale", 0.3, 0.1, 2.0, 0.1),
            ShapeParam("tube", "Tube Radius", 0.05, 0.01, 0.3, 0.01),
        ],
        color=(0.9, 0.4, 0.6),
    ),
    "klein": ShapeDefinition(
        kind=KIND_KLEIN,
        name="Klein Bottle",
        category=ShapeCategory.MATHEMATICAL,
        icon="🧬",
        description="A non-orientable surface that has no inside or outside.",
        params=[
            ShapeParam("scale", "Scale", 0.5, 0.1, 2.0, 0.1),
            ShapeParam("n", "Figure-8 Param", 2.0, 1.0, 5.0, 0.5),
            ShapeParam("t_offset", "4D Phase", 0.0, -3.14, 3.14, 0.1),
        ],
        color=(0.3, 0.8, 0.7),
    ),
    "torus4d": ShapeDefinition(
        kind=KIND_TORUS4D,
        name="4D Torus (Duocylinder)",
        category=ShapeCategory.MATHEMATICAL,
        icon="🔮",
        description="A 4-dimensional torus projected into 3D space.",
        params=[
            ShapeParam("R1", "Major Radius 1", 0.5, 0.1, 2.0, 0.1),
            ShapeParam("R2", "Major Radius 2", 0.3, 0.1, 2.0, 0.1),
            ShapeParam("r", "Minor Radius", 0.1, 0.02, 0.5, 0.02),
            ShapeParam("w_slice", "4D Slice", 0.0, -1.0, 1.0, 0.1),
        ],
        color=(0.7, 0.4, 0.9),
    ),
    "hyperbolic": ShapeDefinition(
        kind=KIND_HYPERBOLIC,
        name="Hyperbolic Tiling",
        category=ShapeCategory.MATHEMATICAL,
        icon="🌀",
        description="Hyperbolic geometry tiling in Poincaré disk model.",
        params=[
            ShapeParam("scale", "Scale", 1.0, 0.1, 5.0, 0.1),
            ShapeParam("order", "Polygon Sides", 7, 3, 12, 1, is_int=True),
            ShapeParam("symmetry", "Vertices Meet", 3, 3, 8, 1, is_int=True),
        ],
        color=(0.5, 0.5, 0.8),
    ),
    "quasicrystal": ShapeDefinition(
        kind=KIND_QUASICRYSTAL,
        name="Quasicrystal",
        category=ShapeCategory.MATHEMATICAL,
        icon="💎",
        description="Aperiodic structure with 7-fold symmetry.",
        params=[
            ShapeParam("scale", "Scale", 5.0, 1.0, 20.0, 0.5),
            ShapeParam("iso", "Iso-level", 3.0, 0.0, 7.0, 0.1),
            ShapeParam("thickness", "Thickness", 0.1, 0.01, 0.5, 0.02),
        ],
        color=(0.8, 0.8, 0.9),
    ),

    "orbital": ShapeDefinition(
        kind=KIND_ORBITAL,
        name="Hydrogenic Orbital",
        category=ShapeCategory.MATHEMATICAL,
        icon="🧿",
        description="Analytic hydrogen-like orbital isosurface of |ψ|².",
        params=[
            ShapeParam("n", "n (principal)", 2, 1, 6, 1, is_int=True),
            ShapeParam("l", "l (angular)", 1, 0, 3, 1, is_int=True),
            ShapeParam("m", "m (magnetic)", 0, -3, 3, 1, is_int=True),
            ShapeParam("iso", "Iso-level", 0.02, 0.0001, 0.2, 0.002, tooltip="Surface where |ψ|² = iso"),
            ShapeParam("thickness", "Thickness", 0.02, 0.0005, 0.1, 0.002, tooltip="Shell thickness around the isosurface"),
        ],
        color=(0.6, 0.7, 0.95),
    ),
    
    # Fractals
    "mandelbulb": ShapeDefinition(
        kind=KIND_MANDELBULB,
        name="Mandelbulb",
        category=ShapeCategory.FRACTALS,
        icon="🌸",
        description="3D fractal extension of the Mandelbrot set.",
        params=[
            ShapeParam("power", "Power", 8.0, 2.0, 16.0, 1.0),
            ShapeParam("bailout", "Bailout", 2.0, 1.0, 4.0, 0.1),
            ShapeParam("max_iter", "Iterations", 12, 4, 32, 1, is_int=True),
            ShapeParam("scale", "Scale", 1.0, 0.1, 3.0, 0.1),
        ],
        color=(0.9, 0.3, 0.5),
    ),
    "menger": ShapeDefinition(
        kind=KIND_MENGER,
        name="Menger Sponge",
        category=ShapeCategory.FRACTALS,
        icon="🧊",
        description="Fractal cube with infinite surface area and zero volume.",
        params=[
            ShapeParam("iterations", "Iterations", 3, 1, 5, 1, is_int=True),
            ShapeParam("size", "Size", 0.5, 0.1, 2.0, 0.1),
        ],
        color=(0.7, 0.7, 0.7),
    ),
    
    # TPMS (Triply Periodic Minimal Surfaces)
    "gyroid": ShapeDefinition(
        kind=KIND_GYROID,
        name="Gyroid",
        category=ShapeCategory.TPMS,
        icon="🧽",
        description="Triply periodic minimal surface used in 3D printing lattices.",
        params=[
            ShapeParam("scale", "Scale/Frequency", 6.0, 1.0, 20.0, 0.5),
            ShapeParam("tau", "Iso-level", 0.0, -1.0, 1.0, 0.05),
            ShapeParam("thickness", "Thickness", 0.05, 0.01, 0.3, 0.01),
        ],
        color=(0.4, 0.7, 0.4),
    ),
}


class ShapeButton(QPushButton):
    """A button for selecting a shape type."""
    
    def __init__(self, shape_def: ShapeDefinition, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.shape_def = shape_def
        
        self.setText(f"{shape_def.icon}\n{shape_def.name}")
        self.setToolTip(shape_def.description)
        self.setCheckable(True)
        self.setFixedSize(80, 70)
        
        self.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 8px;
                color: #e6edf3;
                font-size: 11px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
            }
            QPushButton:checked {
                background-color: #1f6feb;
                border-color: #58a6ff;
            }
        """)


class ParameterWidget(QWidget):
    """Widget for editing a shape parameter."""
    
    valueChanged = Signal(str, float)  # param name, value
    
    def __init__(self, param: ShapeParam, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.param = param
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        # Label
        label = QLabel(f"{param.label}:")
        label.setFixedWidth(100)
        label.setStyleSheet("color: #8b949e;")
        layout.addWidget(label)
        
        # Slider
        self.slider = QSlider(_Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self._set_slider_from_value(param.default)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, stretch=1)
        
        # Spinbox
        if param.is_int:
            self.spinbox = QSpinBox()
            self.spinbox.setRange(int(param.min_val), int(param.max_val))
            self.spinbox.setValue(int(param.default))
        else:
            self.spinbox = QDoubleSpinBox()
            self.spinbox.setRange(param.min_val, param.max_val)
            self.spinbox.setSingleStep(param.step)
            self.spinbox.setDecimals(3)
            self.spinbox.setValue(param.default)
        
        self.spinbox.setFixedWidth(70)
        self.spinbox.setStyleSheet("""
            QSpinBox, QDoubleSpinBox {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        layout.addWidget(self.spinbox)
        
        if param.tooltip:
            self.setToolTip(param.tooltip)
    
    def _set_slider_from_value(self, value: float):
        """Set slider position from parameter value."""
        param = self.param
        normalized = (value - param.min_val) / (param.max_val - param.min_val)
        self.slider.blockSignals(True)
        self.slider.setValue(int(normalized * 100))
        self.slider.blockSignals(False)
    
    def _on_slider_changed(self, slider_val: int):
        """Handle slider changes."""
        param = self.param
        value = param.min_val + (slider_val / 100.0) * (param.max_val - param.min_val)
        
        self.spinbox.blockSignals(True)
        if param.is_int:
            self.spinbox.setValue(int(value))
        else:
            self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        
        self.valueChanged.emit(param.name, value)
    
    def _on_spinbox_changed(self, value):
        """Handle spinbox changes."""
        self._set_slider_from_value(float(value))
        self.valueChanged.emit(self.param.name, float(value))
    
    def get_value(self) -> float:
        """Get the current parameter value."""
        return float(self.spinbox.value())
    
    def set_value(self, value: float):
        """Set the parameter value."""
        self.spinbox.setValue(value)


class ShapeCreationPanel(QWidget):
    """Panel for creating new shapes."""
    
    shapeCreated = Signal(str, dict)  # shape type, params dict
    shapePreviewRequested = Signal(str, dict)  # for live preview
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_shape: Optional[str] = None
        self._param_widgets: Dict[str, ParameterWidget] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Category tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0d1117;
            }
            QTabBar::tab {
                background-color: #161b22;
                color: #8b949e;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #e6edf3;
                border-bottom: 2px solid #58a6ff;
            }
            QTabBar::tab:hover {
                background-color: #21262d;
            }
        """)
        
        # Create tabs for each category
        self._shape_buttons: Dict[str, ShapeButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        for category in ShapeCategory:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(8, 8, 8, 8)
            
            # Grid of shape buttons
            grid = QGridLayout()
            grid.setSpacing(8)
            
            # Get shapes in this category
            shapes = [
                (key, defn) for key, defn in SHAPE_DEFINITIONS.items()
                if defn.category == category
            ]
            
            for i, (key, defn) in enumerate(shapes):
                btn = ShapeButton(defn)
                btn.clicked.connect(lambda checked, k=key: self._select_shape(k))
                self._button_group.addButton(btn)
                self._shape_buttons[key] = btn
                grid.addWidget(btn, i // 3, i % 3)
            
            tab_layout.addLayout(grid)
            tab_layout.addStretch()
            
            self.tabs.addTab(tab, category.value)
        
        layout.addWidget(self.tabs)
        
        # Parameters section
        params_frame = QFrame()
        params_frame.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border-top: 1px solid #30363d;
            }
        """)
        params_layout = QVBoxLayout(params_frame)
        params_layout.setContentsMargins(12, 12, 12, 12)
        
        # Shape info
        self.shape_info = QLabel("Select a shape to create")
        self.shape_info.setStyleSheet("color: #8b949e; font-size: 12px;")
        params_layout.addWidget(self.shape_info)
        
        # Parameter container (scroll area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        
        self.params_container = QWidget()
        self.params_layout = QVBoxLayout(self.params_container)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_layout.addStretch()
        
        scroll.setWidget(self.params_container)
        params_layout.addWidget(scroll)
        
        # Position controls
        pos_group = QGroupBox("Position")
        pos_group.setStyleSheet("""
            QGroupBox {
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
        """)
        pos_layout = QFormLayout(pos_group)
        
        self.pos_x = QDoubleSpinBox()
        self.pos_y = QDoubleSpinBox()
        self.pos_z = QDoubleSpinBox()
        
        for spin, label in [(self.pos_x, "X"), (self.pos_y, "Y"), (self.pos_z, "Z")]:
            spin.setRange(-100, 100)
            spin.setSingleStep(0.1)
            spin.setValue(0.0)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: #0d1117;
                    color: #e6edf3;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            pos_layout.addRow(label, spin)
        
        params_layout.addWidget(pos_group)
        
        # Create button
        self.create_btn = QPushButton("✨ Create Shape")
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #8b949e;
            }
        """)
        self.create_btn.clicked.connect(self._create_shape)
        params_layout.addWidget(self.create_btn)
        
        layout.addWidget(params_frame)
    
    def _select_shape(self, shape_key: str):
        """Handle shape selection."""
        self._current_shape = shape_key
        shape_def = SHAPE_DEFINITIONS[shape_key]
        
        # Update info
        self.shape_info.setText(f"{shape_def.icon} {shape_def.name}: {shape_def.description}")
        
        # Clear old parameters
        for widget in self._param_widgets.values():
            widget.deleteLater()
        self._param_widgets.clear()
        
        # Remove stretch
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add new parameter widgets
        for param in shape_def.params:
            widget = ParameterWidget(param)
            widget.valueChanged.connect(self._on_param_changed)
            self.params_layout.addWidget(widget)
            self._param_widgets[param.name] = widget
        
        self.params_layout.addStretch()
        
        # Enable create button
        self.create_btn.setEnabled(True)
        
        # Request preview
        self._request_preview()
    
    def _on_param_changed(self, name: str, value: float):
        """Handle parameter value changes."""
        self._request_preview()
    
    def _request_preview(self):
        """Request a preview update."""
        if self._current_shape:
            params = self._get_current_params()
            self.shapePreviewRequested.emit(self._current_shape, params)
    
    def _get_current_params(self) -> dict:
        """Get current parameter values."""
        params = {}
        for name, widget in self._param_widgets.items():
            params[name] = widget.get_value()
        params["pos_x"] = self.pos_x.value()
        params["pos_y"] = self.pos_y.value()
        params["pos_z"] = self.pos_z.value()
        return params
    
    def _create_shape(self):
        """Create the selected shape."""
        if self._current_shape:
            params = self._get_current_params()
            self.shapeCreated.emit(self._current_shape, params)


class ShapeCreationDock(QWidget):
    """Dock widget for shape creation."""
    
    shapeCreated = Signal(str, dict)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Create Shape")
        title.setStyleSheet("""
            QLabel {
                color: #e6edf3;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                background-color: #161b22;
                border-bottom: 1px solid #30363d;
            }
        """)
        layout.addWidget(title)
        
        # Panel
        self.panel = ShapeCreationPanel()
        self.panel.shapeCreated.connect(self.shapeCreated.emit)
        layout.addWidget(self.panel)


def get_shape_definition(shape_key: str) -> Optional[ShapeDefinition]:
    """Get a shape definition by key."""
    return SHAPE_DEFINITIONS.get(shape_key)


def create_prim_from_definition(shape_key: str, params: dict):
    """Create a Prim object from a shape definition and parameters."""
    from adaptivecad.aacore.sdf import Prim, Xform
    
    shape_def = SHAPE_DEFINITIONS.get(shape_key)
    if not shape_def:
        return None
    
    # Build params array based on shape type
    prim_params = []
    
    if shape_key == "sphere":
        prim_params = [params.get("radius", 0.5), 0, 0, 0]
    elif shape_key == "box":
        prim_params = [
            params.get("size_x", 0.5),
            params.get("size_y", 0.5),
            params.get("size_z", 0.5),
            0
        ]
    elif shape_key == "capsule":
        prim_params = [params.get("radius", 0.2), params.get("height", 0.8), 0, 0]
    elif shape_key == "torus":
        prim_params = [params.get("major_radius", 0.5), params.get("minor_radius", 0.15), 0, 0]
    elif shape_key == "superellipsoid":
        prim_params = [params.get("radius", 0.5), params.get("power", 2.0), 0, 0]
    elif shape_key == "mobius":
        prim_params = [params.get("major_radius", 0.5), params.get("width", 0.3), 0, 0]
    elif shape_key == "helicoid":
        prim_params = [
            params.get("r_inner", 0.15),
            params.get("r_outer", 0.55),
            params.get("pitch", 0.35),
            params.get("turns", 2.0)
        ]
    elif shape_key == "trefoil":
        prim_params = [params.get("scale", 0.3), params.get("tube", 0.05), 96, 0]
    elif shape_key == "klein":
        prim_params = [
            params.get("scale", 0.5),
            params.get("n", 2.0),
            params.get("t_offset", 0.0),
            0.1
        ]
    elif shape_key == "torus4d":
        prim_params = [
            params.get("R1", 0.5),
            params.get("R2", 0.3),
            params.get("r", 0.1),
            params.get("w_slice", 0.0)
        ]
    elif shape_key == "hyperbolic":
        prim_params = [
            params.get("scale", 1.0),
            params.get("order", 7),
            params.get("symmetry", 3),
            0
        ]
    elif shape_key == "quasicrystal":
        prim_params = [
            params.get("scale", 5.0),
            params.get("iso", 3.0),
            params.get("thickness", 0.1),
            0
        ]
    elif shape_key == "mandelbulb":
        prim_params = [
            params.get("power", 8.0),
            params.get("bailout", 2.0),
            params.get("max_iter", 12),
            params.get("scale", 1.0)
        ]
    elif shape_key == "menger":
        prim_params = [params.get("iterations", 3), params.get("size", 0.5), 0, 0]
    elif shape_key == "gyroid":
        prim_params = [
            params.get("scale", 6.0),
            params.get("tau", 0.0),
            params.get("thickness", 0.05),
            0
        ]
    elif shape_key == "orbital":
        prim_params = [
            params.get("n", 2),
            params.get("l", 1),
            params.get("m", 0),
            params.get("iso", 0.02),
        ]
    else:
        prim_params = [0.5, 0, 0, 0]
    
    # Create transform with position
    xform = Xform()
    pos = np.array([
        params.get("pos_x", 0.0),
        params.get("pos_y", 0.0),
        params.get("pos_z", 0.0),
        1.0
    ], dtype=np.float32)
    xform.M[:3, 3] = pos[:3]
    
    # Create prim
    beta = 0.0
    if shape_key == "orbital":
        beta = float(params.get("thickness", 0.02))

    prim = Prim(
        kind=shape_def.kind,
        params=prim_params,
        xform=xform,
        beta=beta,
        color=shape_def.color
    )
    
    return prim
