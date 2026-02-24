"""
AdaptiveCAD Shape Creation Dialog

A unified dialog for creating shapes with live preview,
parameter controls, and categorized shape selection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Qt6 enum compatibility
try:
    _Horizontal = Qt.Orientation.Horizontal
    _UserRole = Qt.ItemDataRole.UserRole
    _NoFrame = QFrame.Shape.NoFrame
    _RejectRole = QDialogButtonBox.ButtonRole.RejectRole
    _ApplyRole = QDialogButtonBox.ButtonRole.ApplyRole
    _AcceptRole = QDialogButtonBox.ButtonRole.AcceptRole
    _Accepted = QDialog.DialogCode.Accepted
    _Antialiasing = QPainter.RenderHint.Antialiasing
except AttributeError:
    _Horizontal = Qt.Horizontal
    _UserRole = Qt.UserRole
    _NoFrame = QFrame.NoFrame
    _RejectRole = QDialogButtonBox.RejectRole
    _ApplyRole = QDialogButtonBox.ApplyRole
    _AcceptRole = QDialogButtonBox.AcceptRole
    _Accepted = QDialog.Accepted
    _Antialiasing = QPainter.Antialiasing

log = logging.getLogger(__name__)


class ShapeCategory(Enum):
    BASIC = "Basic Shapes"
    ADVANCED = "Advanced Shapes"
    MATHEMATICAL = "Mathematical"
    CURVES = "Curves & Surfaces"


@dataclass
class ShapeParameter:
    """Definition of a shape parameter."""
    name: str
    label: str
    param_type: str  # 'float', 'int', 'angle', 'percent'
    default: float
    min_val: float = 0.0
    max_val: float = 100.0
    step: float = 1.0
    unit: str = "mm"
    tooltip: str = ""


@dataclass
class ShapeDefinition:
    """Definition of a shape type."""
    id: str
    name: str
    category: ShapeCategory
    description: str
    icon: str = ""  # Unicode icon or path
    parameters: List[ShapeParameter] = field(default_factory=list)
    preview_fn: Optional[Callable] = None
    create_fn: Optional[Callable] = None


# Shape definitions
SHAPE_DEFINITIONS: Dict[str, ShapeDefinition] = {}


def register_shape(shape_def: ShapeDefinition):
    """Register a shape definition."""
    SHAPE_DEFINITIONS[shape_def.id] = shape_def


# Basic shapes
register_shape(ShapeDefinition(
    id="box",
    name="Box",
    category=ShapeCategory.BASIC,
    description="A rectangular box/cube with configurable dimensions",
    icon="⬜",
    parameters=[
        ShapeParameter("width", "Width", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Box width"),
        ShapeParameter("height", "Height", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Box height"),
        ShapeParameter("depth", "Depth", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Box depth"),
    ]
))

register_shape(ShapeDefinition(
    id="cylinder",
    name="Cylinder",
    category=ShapeCategory.BASIC,
    description="A cylinder with configurable radius and height",
    icon="⬤",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 25.0, 1.0, 250.0, 1.0, "mm", "Cylinder radius"),
        ShapeParameter("height", "Height", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Cylinder height"),
    ]
))

register_shape(ShapeDefinition(
    id="sphere",
    name="Sphere",
    category=ShapeCategory.BASIC,
    description="A sphere with configurable radius",
    icon="●",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 25.0, 1.0, 250.0, 1.0, "mm", "Sphere radius"),
    ]
))

register_shape(ShapeDefinition(
    id="cone",
    name="Cone",
    category=ShapeCategory.BASIC,
    description="A cone with configurable base radius and height",
    icon="▲",
    parameters=[
        ShapeParameter("radius", "Base Radius", "float", 25.0, 1.0, 250.0, 1.0, "mm", "Cone base radius"),
        ShapeParameter("height", "Height", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Cone height"),
    ]
))

register_shape(ShapeDefinition(
    id="torus",
    name="Torus",
    category=ShapeCategory.BASIC,
    description="A torus (donut shape) with configurable radii",
    icon="◯",
    parameters=[
        ShapeParameter("major_radius", "Major Radius", "float", 40.0, 5.0, 200.0, 1.0, "mm", "Distance from center to tube center"),
        ShapeParameter("minor_radius", "Minor Radius", "float", 10.0, 1.0, 100.0, 1.0, "mm", "Tube radius"),
    ]
))

register_shape(ShapeDefinition(
    id="capsule",
    name="Capsule",
    category=ShapeCategory.BASIC,
    description="A capsule (cylinder with hemispherical caps)",
    icon="⬭",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 15.0, 1.0, 150.0, 1.0, "mm", "Capsule radius"),
        ShapeParameter("height", "Height", "float", 50.0, 1.0, 500.0, 1.0, "mm", "Total height including caps"),
    ]
))

# Advanced shapes
register_shape(ShapeDefinition(
    id="superellipse",
    name="Superellipse",
    category=ShapeCategory.ADVANCED,
    description="A superellipse with configurable exponents for smooth corners",
    icon="◇",
    parameters=[
        ShapeParameter("a", "Width (a)", "float", 40.0, 1.0, 200.0, 1.0, "mm", "Semi-major axis"),
        ShapeParameter("b", "Height (b)", "float", 30.0, 1.0, 200.0, 1.0, "mm", "Semi-minor axis"),
        ShapeParameter("n", "Exponent (n)", "float", 2.5, 0.1, 10.0, 0.1, "", "Controls corner roundness (2=ellipse)"),
        ShapeParameter("extrude", "Extrusion", "float", 20.0, 1.0, 200.0, 1.0, "mm", "Extrusion depth"),
    ]
))

register_shape(ShapeDefinition(
    id="superquad",
    name="Superquadric",
    category=ShapeCategory.ADVANCED,
    description="A 3D superquadric with two shape exponents",
    icon="◆",
    parameters=[
        ShapeParameter("a1", "Size X", "float", 30.0, 1.0, 200.0, 1.0, "mm", "Size along X"),
        ShapeParameter("a2", "Size Y", "float", 30.0, 1.0, 200.0, 1.0, "mm", "Size along Y"),
        ShapeParameter("a3", "Size Z", "float", 30.0, 1.0, 200.0, 1.0, "mm", "Size along Z"),
        ShapeParameter("e1", "Exponent 1", "float", 1.0, 0.1, 4.0, 0.1, "", "East-west squareness"),
        ShapeParameter("e2", "Exponent 2", "float", 1.0, 0.1, 4.0, 0.1, "", "North-south squareness"),
    ]
))

register_shape(ShapeDefinition(
    id="pi_shell",
    name="Pi Curve Shell",
    category=ShapeCategory.ADVANCED,
    description="A shell based on the Adaptive Pi curve geometry",
    icon="π",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 30.0, 5.0, 200.0, 1.0, "mm", "Shell radius"),
        ShapeParameter("thickness", "Thickness", "float", 2.0, 0.5, 20.0, 0.5, "mm", "Shell wall thickness"),
        ShapeParameter("beta", "Beta (β)", "float", 0.3, 0.0, 1.0, 0.05, "", "Pi curve parameter"),
        ShapeParameter("segments", "Segments", "int", 64, 8, 256, 8, "", "Number of segments"),
    ]
))

register_shape(ShapeDefinition(
    id="helix",
    name="Helix",
    category=ShapeCategory.ADVANCED,
    description="A helical coil shape",
    icon="🌀",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 20.0, 5.0, 200.0, 1.0, "mm", "Helix radius"),
        ShapeParameter("pitch", "Pitch", "float", 10.0, 1.0, 100.0, 1.0, "mm", "Distance per turn"),
        ShapeParameter("turns", "Turns", "float", 3.0, 0.5, 20.0, 0.5, "", "Number of turns"),
        ShapeParameter("wire_radius", "Wire Radius", "float", 2.0, 0.5, 20.0, 0.5, "mm", "Thickness of the helix wire"),
    ]
))

register_shape(ShapeDefinition(
    id="ellipsoid",
    name="Ellipsoid",
    category=ShapeCategory.ADVANCED,
    description="An ellipsoid with three independent radii",
    icon="⬮",
    parameters=[
        ShapeParameter("rx", "Radius X", "float", 30.0, 1.0, 200.0, 1.0, "mm", "Radius along X axis"),
        ShapeParameter("ry", "Radius Y", "float", 20.0, 1.0, 200.0, 1.0, "mm", "Radius along Y axis"),
        ShapeParameter("rz", "Radius Z", "float", 15.0, 1.0, 200.0, 1.0, "mm", "Radius along Z axis"),
    ]
))

# Mathematical shapes
register_shape(ShapeDefinition(
    id="mobius",
    name="Möbius Strip",
    category=ShapeCategory.MATHEMATICAL,
    description="A Möbius strip with a half-twist",
    icon="∞",
    parameters=[
        ShapeParameter("radius", "Radius", "float", 30.0, 10.0, 200.0, 1.0, "mm", "Strip radius"),
        ShapeParameter("width", "Width", "float", 10.0, 1.0, 50.0, 1.0, "mm", "Strip width"),
        ShapeParameter("thickness", "Thickness", "float", 1.0, 0.5, 10.0, 0.5, "mm", "Strip thickness"),
        ShapeParameter("twists", "Half-Twists", "int", 1, 1, 5, 1, "", "Number of half-twists"),
    ]
))

register_shape(ShapeDefinition(
    id="klein",
    name="Klein Bottle",
    category=ShapeCategory.MATHEMATICAL,
    description="A Klein bottle (non-orientable surface)",
    icon="🧪",
    parameters=[
        ShapeParameter("scale", "Scale", "float", 20.0, 5.0, 100.0, 1.0, "mm", "Overall scale"),
        ShapeParameter("thickness", "Thickness", "float", 1.5, 0.5, 10.0, 0.5, "mm", "Wall thickness"),
    ]
))

register_shape(ShapeDefinition(
    id="gyroid",
    name="Gyroid",
    category=ShapeCategory.MATHEMATICAL,
    description="A gyroid minimal surface (common in metamaterials)",
    icon="🔷",
    parameters=[
        ShapeParameter("size", "Size", "float", 50.0, 10.0, 200.0, 1.0, "mm", "Bounding box size"),
        ShapeParameter("thickness", "Thickness", "float", 2.0, 0.5, 10.0, 0.5, "mm", "Surface thickness"),
        ShapeParameter("scale", "Cell Scale", "float", 10.0, 2.0, 50.0, 1.0, "mm", "Gyroid cell size"),
    ]
))

register_shape(ShapeDefinition(
    id="mandelbulb",
    name="Mandelbulb",
    category=ShapeCategory.MATHEMATICAL,
    description="A 3D Mandelbulb fractal",
    icon="🔮",
    parameters=[
        ShapeParameter("power", "Power", "float", 8.0, 2.0, 16.0, 1.0, "", "Mandelbulb power"),
        ShapeParameter("scale", "Scale", "float", 30.0, 10.0, 100.0, 1.0, "mm", "Overall scale"),
        ShapeParameter("iterations", "Iterations", "int", 10, 3, 20, 1, "", "Fractal iterations"),
    ]
))

register_shape(ShapeDefinition(
    id="menger",
    name="Menger Sponge",
    category=ShapeCategory.MATHEMATICAL,
    description="A Menger sponge fractal",
    icon="🧊",
    parameters=[
        ShapeParameter("size", "Size", "float", 50.0, 20.0, 200.0, 1.0, "mm", "Sponge size"),
        ShapeParameter("iterations", "Iterations", "int", 3, 1, 5, 1, "", "Fractal depth"),
    ]
))


class ParameterWidget(QWidget):
    """Widget for editing a single parameter."""
    
    valueChanged = Signal(str, object)  # parameter name, new value
    
    def __init__(self, param: ShapeParameter, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.param = param
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        
        # Label
        self.label = QLabel(f"{self.param.label}:")
        self.label.setMinimumWidth(100)
        self.label.setToolTip(self.param.tooltip)
        layout.addWidget(self.label)
        
        # Slider
        self.slider = QSlider(_Horizontal)
        self.slider.setMinimumWidth(120)
        
        # Value input
        if self.param.param_type == 'int':
            self.spin = QSpinBox()
            self.spin.setRange(int(self.param.min_val), int(self.param.max_val))
            self.spin.setValue(int(self.param.default))
            self.spin.setSingleStep(int(self.param.step))
            
            self.slider.setRange(int(self.param.min_val), int(self.param.max_val))
            self.slider.setValue(int(self.param.default))
        else:
            self.spin = QDoubleSpinBox()
            self.spin.setRange(self.param.min_val, self.param.max_val)
            self.spin.setValue(self.param.default)
            self.spin.setSingleStep(self.param.step)
            self.spin.setDecimals(2 if self.param.step >= 0.01 else 3)
            
            # Map float to int for slider
            scale = 100.0 / max(self.param.step, 0.01)
            self.slider.setRange(int(self.param.min_val * scale), int(self.param.max_val * scale))
            self.slider.setValue(int(self.param.default * scale))
            self._slider_scale = scale
        
        self.spin.setFixedWidth(80)
        self.spin.setToolTip(self.param.tooltip)
        
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        
        # Unit label
        if self.param.unit:
            unit_label = QLabel(self.param.unit)
            unit_label.setFixedWidth(30)
            unit_label.setProperty("muted", True)
            layout.addWidget(unit_label)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin.valueChanged.connect(self._on_spin_changed)
    
    def _on_slider_changed(self, value: int):
        if self.param.param_type == 'int':
            self.spin.blockSignals(True)
            self.spin.setValue(value)
            self.spin.blockSignals(False)
            self.valueChanged.emit(self.param.name, value)
        else:
            float_val = value / self._slider_scale
            self.spin.blockSignals(True)
            if hasattr(self.spin, 'setValue'):
                self.spin.setValue(float_val)  # QDoubleSpinBox accepts float
            self.spin.blockSignals(False)
            self.valueChanged.emit(self.param.name, float_val)
    
    def _on_spin_changed(self, value):
        if self.param.param_type == 'int':
            self.slider.blockSignals(True)
            self.slider.setValue(int(value))
            self.slider.blockSignals(False)
            self.valueChanged.emit(self.param.name, int(value))
        else:
            self.slider.blockSignals(True)
            self.slider.setValue(int(value * self._slider_scale))
            self.slider.blockSignals(False)
            self.valueChanged.emit(self.param.name, float(value))
    
    def getValue(self) -> Any:
        """Get the current parameter value."""
        return self.spin.value()
    
    def setValue(self, value: Any):
        """Set the parameter value."""
        self.spin.setValue(value)


class ShapePreviewWidget(QWidget):
    """Widget for previewing a shape (2D wireframe representation)."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.shape_id: Optional[str] = None
        self.parameters: Dict[str, Any] = {}
        
        # Colors
        self.bg_color = QColor("#0d1117")
        self.grid_color = QColor("#21262d")
        self.shape_color = QColor("#58a6ff")
    
    def setShape(self, shape_id: str, parameters: Dict[str, Any]):
        """Set the shape to preview."""
        self.shape_id = shape_id
        self.parameters = parameters
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(_Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Grid
        pen = QPen(self.grid_color)
        pen.setWidth(1)
        painter.setPen(pen)
        
        cx, cy = self.width() // 2, self.height() // 2
        
        # Draw grid lines
        for i in range(-5, 6):
            x = cx + i * 20
            painter.drawLine(x, 0, x, self.height())
        for i in range(-5, 6):
            y = cy + i * 20
            painter.drawLine(0, y, self.width(), y)
        
        # Draw shape
        if self.shape_id:
            pen = QPen(self.shape_color)
            pen.setWidth(2)
            painter.setPen(pen)
            
            self._draw_shape_preview(painter, cx, cy)
    
    def _draw_shape_preview(self, painter: QPainter, cx: int, cy: int):
        """Draw a 2D preview of the shape."""
        import math
        
        scale = min(self.width(), self.height()) / 200.0 * 0.6
        
        if self.shape_id == "box":
            w = self.parameters.get("width", 50) * scale * 0.8
            h = self.parameters.get("height", 50) * scale * 0.8
            d = self.parameters.get("depth", 50) * scale * 0.3
            
            # Front face
            painter.drawRect(int(cx - w/2), int(cy - h/2), int(w), int(h))
            # Back face (offset)
            painter.drawRect(int(cx - w/2 + d), int(cy - h/2 - d), int(w), int(h))
            # Connect corners
            painter.drawLine(int(cx - w/2), int(cy - h/2), int(cx - w/2 + d), int(cy - h/2 - d))
            painter.drawLine(int(cx + w/2), int(cy - h/2), int(cx + w/2 + d), int(cy - h/2 - d))
            painter.drawLine(int(cx + w/2), int(cy + h/2), int(cx + w/2 + d), int(cy + h/2 - d))
            
        elif self.shape_id == "cylinder":
            r = self.parameters.get("radius", 25) * scale
            h = self.parameters.get("height", 50) * scale
            
            # Draw ellipse for top and bottom
            painter.drawEllipse(int(cx - r), int(cy - h/2 - r/3), int(2*r), int(r/1.5))
            painter.drawEllipse(int(cx - r), int(cy + h/2 - r/3), int(2*r), int(r/1.5))
            # Sides
            painter.drawLine(int(cx - r), int(cy - h/2), int(cx - r), int(cy + h/2))
            painter.drawLine(int(cx + r), int(cy - h/2), int(cx + r), int(cy + h/2))
            
        elif self.shape_id == "sphere":
            r = self.parameters.get("radius", 25) * scale
            painter.drawEllipse(int(cx - r), int(cy - r), int(2*r), int(2*r))
            # Cross-section lines
            painter.drawEllipse(int(cx - r), int(cy - r/3), int(2*r), int(r/1.5))
            
        elif self.shape_id == "torus":
            R = self.parameters.get("major_radius", 40) * scale
            r = self.parameters.get("minor_radius", 10) * scale
            
            # Outer and inner circles
            painter.drawEllipse(int(cx - R - r), int(cy - R - r), int(2*(R+r)), int(2*(R+r)))
            painter.drawEllipse(int(cx - R + r), int(cy - R + r), int(2*(R-r)), int(2*(R-r)))
            
        elif self.shape_id in ("superellipse", "superquad"):
            a = self.parameters.get("a", self.parameters.get("a1", 40)) * scale
            b = self.parameters.get("b", self.parameters.get("a2", 30)) * scale
            n = self.parameters.get("n", self.parameters.get("e1", 2.5))
            
            points = []
            for i in range(100):
                t = 2 * math.pi * i / 100
                cos_t = math.cos(t)
                sin_t = math.sin(t)
                x = a * (abs(cos_t) ** (2/n)) * (1 if cos_t >= 0 else -1)
                y = b * (abs(sin_t) ** (2/n)) * (1 if sin_t >= 0 else -1)
                points.append((int(cx + x), int(cy + y)))
            
            for i in range(len(points)):
                painter.drawLine(points[i][0], points[i][1], 
                               points[(i+1) % len(points)][0], points[(i+1) % len(points)][1])
        else:
            # Default circle
            painter.drawEllipse(cx - 40, cy - 40, 80, 80)


class ShapeListWidget(QListWidget):
    """Widget for selecting a shape from a category."""
    
    shapeSelected = Signal(str)  # shape id
    
    def __init__(self, category: ShapeCategory, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category = category
        self._populate()
        
        self.currentItemChanged.connect(self._on_item_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def _populate(self):
        for shape_def in SHAPE_DEFINITIONS.values():
            if shape_def.category == self.category:
                item = QListWidgetItem(f"{shape_def.icon}  {shape_def.name}")
                item.setData(_UserRole, shape_def.id)
                item.setToolTip(shape_def.description)
                self.addItem(item)
    
    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            self.shapeSelected.emit(current.data(_UserRole))
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        # Emit for potential quick-create
        pass


class ShapeCreationDialog(QDialog):
    """Main dialog for creating shapes."""
    
    shapeCreated = Signal(str, dict)  # shape id, parameters
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Create Shape")
        self.setMinimumSize(700, 500)
        self.resize(800, 550)
        
        self.current_shape_id: Optional[str] = None
        self.param_widgets: Dict[str, ParameterWidget] = {}
        
        self._setup_ui()
        self._connect_signals()
        
        # Select first shape by default
        self._select_first_shape()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Main splitter
        splitter = QSplitter(_Horizontal)
        
        # Left panel - shape selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Category tabs
        self.category_tabs = QTabWidget()
        
        for category in ShapeCategory:
            list_widget = ShapeListWidget(category)
            list_widget.shapeSelected.connect(self._on_shape_selected)
            self.category_tabs.addTab(list_widget, category.value)
        
        left_layout.addWidget(self.category_tabs)
        splitter.addWidget(left_panel)
        
        # Right panel - parameters and preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Shape info
        self.shape_info = QLabel()
        self.shape_info.setWordWrap(True)
        self.shape_info.setProperty("subheading", True)
        right_layout.addWidget(self.shape_info)
        
        # Preview
        self.preview = ShapePreviewWidget()
        self.preview.setMinimumHeight(180)
        right_layout.addWidget(self.preview)
        
        # Parameters group
        params_group = QGroupBox("Parameters")
        self.params_layout = QVBoxLayout(params_group)
        
        # Scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_NoFrame)
        
        self.params_container = QWidget()
        self.params_container_layout = QVBoxLayout(self.params_container)
        self.params_container_layout.setContentsMargins(0, 0, 0, 0)
        self.params_container_layout.addStretch()
        
        scroll.setWidget(self.params_container)
        self.params_layout.addWidget(scroll)
        
        right_layout.addWidget(params_group, 1)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 550])
        
        layout.addWidget(splitter, 1)
        
        # Button box
        self.button_box = QDialogButtonBox()
        
        self.create_btn = QPushButton("Create")
        self.create_btn.setObjectName("primaryButton")
        self.create_btn.setEnabled(False)
        
        self.create_close_btn = QPushButton("Create && Close")
        self.cancel_btn = QPushButton("Cancel")
        
        self.button_box.addButton(self.cancel_btn, _RejectRole)
        self.button_box.addButton(self.create_btn, _ApplyRole)
        self.button_box.addButton(self.create_close_btn, _AcceptRole)
        
        layout.addWidget(self.button_box)
    
    def _connect_signals(self):
        self.create_btn.clicked.connect(self._on_create)
        self.create_close_btn.clicked.connect(self._on_create_close)
        self.cancel_btn.clicked.connect(self.reject)
    
    def _select_first_shape(self):
        """Select the first shape in the first category."""
        first_list = self.category_tabs.widget(0)
        if first_list and isinstance(first_list, QListWidget) and first_list.count() > 0:
            first_list.setCurrentRow(0)
    
    def _on_shape_selected(self, shape_id: str):
        """Handle shape selection."""
        self.current_shape_id = shape_id
        shape_def = SHAPE_DEFINITIONS.get(shape_id)
        
        if not shape_def:
            return
        
        # Update info
        self.shape_info.setText(f"<b>{shape_def.icon} {shape_def.name}</b><br/>{shape_def.description}")
        
        # Clear old parameters
        for widget in self.param_widgets.values():
            widget.deleteLater()
        self.param_widgets.clear()
        
        # Clear layout (except stretch)
        while self.params_container_layout.count() > 1:
            item = self.params_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add new parameters
        for param in shape_def.parameters:
            widget = ParameterWidget(param)
            widget.valueChanged.connect(self._on_param_changed)
            self.params_container_layout.insertWidget(
                self.params_container_layout.count() - 1, widget
            )
            self.param_widgets[param.name] = widget
        
        # Update preview
        self._update_preview()
        
        # Enable create button
        self.create_btn.setEnabled(True)
    
    def _on_param_changed(self, name: str, value: Any):
        """Handle parameter value change."""
        self._update_preview()
    
    def _update_preview(self):
        """Update the shape preview."""
        if not self.current_shape_id:
            return
        
        params = {name: widget.getValue() for name, widget in self.param_widgets.items()}
        self.preview.setShape(self.current_shape_id, params)
    
    def _get_parameters(self) -> Dict[str, Any]:
        """Get all current parameter values."""
        return {name: widget.getValue() for name, widget in self.param_widgets.items()}
    
    def _on_create(self):
        """Create the shape without closing."""
        if self.current_shape_id:
            self.shapeCreated.emit(self.current_shape_id, self._get_parameters())
    
    def _on_create_close(self):
        """Create the shape and close dialog."""
        self._on_create()
        self.accept()
    
    @staticmethod
    def createShape(parent: Optional[QWidget] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Show the dialog and return the shape to create, or None if cancelled."""
        dialog = ShapeCreationDialog(parent)
        
        result = None
        
        def on_created(shape_id: str, params: Dict[str, Any]):
            nonlocal result
            result = (shape_id, params)
        
        dialog.shapeCreated.connect(on_created)
        
        if dialog.exec() == _Accepted:
            return result
        return None


def show_shape_dialog(parent: Optional[QWidget] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Convenience function to show the shape creation dialog."""
    return ShapeCreationDialog.createShape(parent)
