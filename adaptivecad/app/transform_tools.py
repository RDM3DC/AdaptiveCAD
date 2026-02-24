"""AdaptiveCAD Transform Tools

Provides interactive transform tools for manipulating objects:
- Move (translate)
- Rotate
- Scale
- With visual handles and gizmos
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _Horizontal = Qt.Orientation.Horizontal
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
except AttributeError:
    _Horizontal = Qt.Horizontal
    _AlignCenter = Qt.AlignCenter


class TransformMode(Enum):
    """Transform tool modes."""
    SELECT = "select"
    MOVE = "move"
    ROTATE = "rotate"
    SCALE = "scale"


class TransformAxis(Enum):
    """Transform constraint axes."""
    FREE = "free"
    X = "x"
    Y = "y"
    Z = "z"
    XY = "xy"
    XZ = "xz"
    YZ = "yz"


class TransformToolbar(QWidget):
    """Toolbar for transform mode selection."""
    
    modeChanged = Signal(str)  # TransformMode value
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_mode = TransformMode.SELECT
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        self._buttons = {}
        
        tools = [
            (TransformMode.SELECT, "🔘", "Select (Q)", "Q"),
            (TransformMode.MOVE, "✥", "Move (G)", "G"),
            (TransformMode.ROTATE, "⟳", "Rotate (R)", "R"),
            (TransformMode.SCALE, "⤢", "Scale (S)", "S"),
        ]
        
        for mode, icon, tooltip, shortcut in tools:
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)
            btn.setToolTip(f"{tooltip}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    color: #e6edf3;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #30363d;
                }
                QPushButton:checked {
                    background-color: #1f6feb;
                    border-color: #58a6ff;
                }
            """)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            
            self._button_group.addButton(btn)
            self._buttons[mode] = btn
            layout.addWidget(btn)
        
        # Set default
        self._buttons[TransformMode.SELECT].setChecked(True)
        
        layout.addStretch()
        
        # Axis constraint buttons
        layout.addWidget(self._create_separator())
        
        self._axis_group = QButtonGroup(self)
        self._axis_group.setExclusive(True)
        self._axis_buttons = {}
        
        axes = [
            (TransformAxis.FREE, "∞", "Free"),
            (TransformAxis.X, "X", "X Axis"),
            (TransformAxis.Y, "Y", "Y Axis"),
            (TransformAxis.Z, "Z", "Z Axis"),
        ]
        
        for axis, label, tooltip in axes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            
            # Color code axes
            if axis == TransformAxis.X:
                color = "#ff6b6b"
            elif axis == TransformAxis.Y:
                color = "#51cf66"
            elif axis == TransformAxis.Z:
                color = "#339af0"
            else:
                color = "#e6edf3"
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #21262d;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    color: {color};
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #30363d;
                }}
                QPushButton:checked {{
                    background-color: #30363d;
                    border-color: {color};
                }}
            """)
            
            self._axis_group.addButton(btn)
            self._axis_buttons[axis] = btn
            layout.addWidget(btn)
        
        self._axis_buttons[TransformAxis.FREE].setChecked(True)
    
    def _create_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #30363d;")
        return sep
    
    def _set_mode(self, mode: TransformMode):
        self._current_mode = mode
        self.modeChanged.emit(mode.value)
    
    def get_current_mode(self) -> TransformMode:
        return self._current_mode
    
    def get_current_axis(self) -> TransformAxis:
        for axis, btn in self._axis_buttons.items():
            if btn.isChecked():
                return axis
        return TransformAxis.FREE


class TransformPanel(QWidget):
    """Panel for precise transform value editing."""
    
    transformChanged = Signal(dict)  # {"position": [x,y,z], "rotation": [...], "scale": [...]}
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._prim = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Transform")
        title.setStyleSheet("""
            color: #e6edf3;
            font-size: 14px;
            font-weight: bold;
        """)
        layout.addWidget(title)
        
        # Position
        pos_group = self._create_group("Position", ["X", "Y", "Z"])
        self.pos_x, self.pos_y, self.pos_z = pos_group["spins"]
        layout.addWidget(pos_group["widget"])
        
        # Rotation
        rot_group = self._create_group("Rotation (°)", ["X", "Y", "Z"], range=(-360, 360))
        self.rot_x, self.rot_y, self.rot_z = rot_group["spins"]
        layout.addWidget(rot_group["widget"])
        
        # Scale
        scale_group = self._create_group("Scale", ["X", "Y", "Z"], default=1.0, range=(0.01, 100))
        self.scale_x, self.scale_y, self.scale_z = scale_group["spins"]
        layout.addWidget(scale_group["widget"])
        
        # Uniform scale checkbox
        self.uniform_scale = QPushButton("🔗 Uniform Scale")
        self.uniform_scale.setCheckable(True)
        self.uniform_scale.setChecked(True)
        self.uniform_scale.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #e6edf3;
                padding: 6px;
            }
            QPushButton:checked {
                background-color: #1f6feb;
            }
        """)
        layout.addWidget(self.uniform_scale)
        
        # Apply button
        apply_btn = QPushButton("Apply Transform")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        apply_btn.clicked.connect(self._apply_transform)
        layout.addWidget(apply_btn)
        
        # Reset button
        reset_btn = QPushButton("Reset Transform")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #e6edf3;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
        """)
        reset_btn.clicked.connect(self._reset_transform)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        
        # Connect uniform scale
        self.scale_x.valueChanged.connect(self._on_scale_changed)
    
    def _create_group(self, title: str, labels: list, default: float = 0.0, range: Tuple[float, float] = (-100, 100)) -> dict:
        """Create a labeled group of spinboxes."""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
        """)
        
        layout = QGridLayout(group)
        layout.setSpacing(4)
        
        spins = []
        colors = {"X": "#ff6b6b", "Y": "#51cf66", "Z": "#339af0"}
        
        for i, label in enumerate(labels):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {colors.get(label, '#e6edf3')}; font-weight: bold;")
            lbl.setFixedWidth(20)
            
            spin = QDoubleSpinBox()
            spin.setRange(range[0], range[1])
            spin.setSingleStep(0.1)
            spin.setDecimals(3)
            spin.setValue(default)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: #0d1117;
                    color: #e6edf3;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            
            layout.addWidget(lbl, i, 0)
            layout.addWidget(spin, i, 1)
            spins.append(spin)
        
        return {"widget": group, "spins": spins}
    
    def set_prim(self, prim):
        """Set the primitive to edit."""
        self._prim = prim
        if prim:
            self._load_from_prim()
    
    def _load_from_prim(self):
        """Load values from the current primitive."""
        if not self._prim:
            return
        
        # Position from transform matrix
        pos = self._prim.xform.M[:3, 3]
        self.pos_x.setValue(float(pos[0]))
        self.pos_y.setValue(float(pos[1]))
        self.pos_z.setValue(float(pos[2]))
        
        # Euler angles (if stored)
        if hasattr(self._prim, 'euler'):
            self.rot_x.setValue(float(self._prim.euler[0]))
            self.rot_y.setValue(float(self._prim.euler[1]))
            self.rot_z.setValue(float(self._prim.euler[2]))
        
        # Scale (if stored)
        if hasattr(self._prim, 'scale'):
            self.scale_x.setValue(float(self._prim.scale[0]))
            self.scale_y.setValue(float(self._prim.scale[1]))
            self.scale_z.setValue(float(self._prim.scale[2]))
    
    def _on_scale_changed(self, value):
        """Handle scale X change for uniform scaling."""
        if self.uniform_scale.isChecked():
            self.scale_y.blockSignals(True)
            self.scale_z.blockSignals(True)
            self.scale_y.setValue(value)
            self.scale_z.setValue(value)
            self.scale_y.blockSignals(False)
            self.scale_z.blockSignals(False)
    
    def _apply_transform(self):
        """Apply the transform to the primitive."""
        transform = {
            "position": [self.pos_x.value(), self.pos_y.value(), self.pos_z.value()],
            "rotation": [self.rot_x.value(), self.rot_y.value(), self.rot_z.value()],
            "scale": [self.scale_x.value(), self.scale_y.value(), self.scale_z.value()],
        }
        
        if self._prim and hasattr(self._prim, 'set_transform'):
            self._prim.set_transform(
                pos=transform["position"],
                euler=transform["rotation"],
                scale=transform["scale"]
            )
        
        self.transformChanged.emit(transform)
    
    def _reset_transform(self):
        """Reset transform to defaults."""
        self.pos_x.setValue(0.0)
        self.pos_y.setValue(0.0)
        self.pos_z.setValue(0.0)
        self.rot_x.setValue(0.0)
        self.rot_y.setValue(0.0)
        self.rot_z.setValue(0.0)
        self.scale_x.setValue(1.0)
        self.scale_y.setValue(1.0)
        self.scale_z.setValue(1.0)
        
        self._apply_transform()


class TransformDock(QWidget):
    """Dock widget containing transform tools."""
    
    transformChanged = Signal(dict)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        self.toolbar = TransformToolbar()
        layout.addWidget(self.toolbar)
        
        # Panel
        self.panel = TransformPanel()
        self.panel.transformChanged.connect(self.transformChanged.emit)
        layout.addWidget(self.panel)
    
    def set_prim(self, prim):
        """Set the primitive to edit."""
        self.panel.set_prim(prim)
