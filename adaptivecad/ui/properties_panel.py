"""
AdaptiveCAD Properties Panel

Enhanced properties panel with live editing, undo/redo support,
and categorized property display.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Qt6 enum compatibility
try:
    _AlignRight = Qt.AlignmentFlag.AlignRight
    _AlignVCenter = Qt.AlignmentFlag.AlignVCenter
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _Horizontal = Qt.Orientation.Horizontal
    _HLine = QFrame.Shape.HLine
    _NoFrame = QFrame.Shape.NoFrame
except AttributeError:
    _AlignRight = Qt.AlignRight
    _AlignVCenter = Qt.AlignVCenter
    _AlignCenter = Qt.AlignCenter
    _Horizontal = Qt.Horizontal
    _HLine = QFrame.HLine
    _NoFrame = QFrame.NoFrame

log = logging.getLogger(__name__)


@dataclass
class PropertyChange:
    """Record of a property change for undo/redo."""
    object_id: str
    property_name: str
    old_value: Any
    new_value: Any
    timestamp: float = 0.0


class UndoStack:
    """Simple undo/redo stack for property changes."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._undo_stack: List[PropertyChange] = []
        self._redo_stack: List[PropertyChange] = []
    
    def push(self, change: PropertyChange):
        """Push a change onto the undo stack."""
        self._undo_stack.append(change)
        self._redo_stack.clear()  # Clear redo on new action
        
        # Trim if too large
        if len(self._undo_stack) > self.max_size:
            self._undo_stack.pop(0)
    
    def undo(self) -> Optional[PropertyChange]:
        """Pop and return the last change for undo."""
        if self._undo_stack:
            change = self._undo_stack.pop()
            self._redo_stack.append(change)
            return change
        return None
    
    def redo(self) -> Optional[PropertyChange]:
        """Pop and return the last undone change for redo."""
        if self._redo_stack:
            change = self._redo_stack.pop()
            self._undo_stack.append(change)
            return change
        return None
    
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0
    
    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()


class PropertyEditor(QWidget):
    """Base class for property editors."""
    
    valueChanged = Signal(str, object)  # property name, new value
    
    def __init__(self, name: str, value: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.property_name = name
        self._value = value
        self._setup_ui()
    
    def _setup_ui(self):
        raise NotImplementedError
    
    def getValue(self) -> Any:
        return self._value
    
    def setValue(self, value: Any):
        self._value = value
        self._update_ui()
    
    def _update_ui(self):
        raise NotImplementedError
    
    def _emit_change(self, new_value: Any):
        self._value = new_value
        self.valueChanged.emit(self.property_name, new_value)


class FloatPropertyEditor(PropertyEditor):
    """Editor for float properties."""
    
    def __init__(
        self,
        name: str,
        value: float,
        min_val: float = -1e6,
        max_val: float = 1e6,
        step: float = 0.1,
        decimals: int = 3,
        unit: str = "",
        parent: Optional[QWidget] = None
    ):
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.decimals = decimals
        self.unit = unit
        super().__init__(name, value, parent)
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.spin = QDoubleSpinBox()
        self.spin.setRange(self.min_val, self.max_val)
        self.spin.setSingleStep(self.step)
        self.spin.setDecimals(self.decimals)
        self.spin.setValue(self._value)
        self.spin.setMinimumWidth(80)
        
        layout.addWidget(self.spin, 1)
        
        if self.unit:
            unit_label = QLabel(self.unit)
            unit_label.setProperty("muted", True)
            layout.addWidget(unit_label)
        
        self.spin.valueChanged.connect(self._on_value_changed)
    
    def _on_value_changed(self, value: float):
        self._emit_change(value)
    
    def _update_ui(self):
        self.spin.blockSignals(True)
        self.spin.setValue(self._value)
        self.spin.blockSignals(False)


class IntPropertyEditor(PropertyEditor):
    """Editor for integer properties."""
    
    def __init__(
        self,
        name: str,
        value: int,
        min_val: int = -1000000,
        max_val: int = 1000000,
        step: int = 1,
        unit: str = "",
        parent: Optional[QWidget] = None
    ):
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.unit = unit
        super().__init__(name, value, parent)
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.spin = QSpinBox()
        self.spin.setRange(self.min_val, self.max_val)
        self.spin.setSingleStep(self.step)
        self.spin.setValue(self._value)
        self.spin.setMinimumWidth(80)
        
        layout.addWidget(self.spin, 1)
        
        if self.unit:
            unit_label = QLabel(self.unit)
            unit_label.setProperty("muted", True)
            layout.addWidget(unit_label)
        
        self.spin.valueChanged.connect(self._on_value_changed)
    
    def _on_value_changed(self, value: int):
        self._emit_change(value)
    
    def _update_ui(self):
        self.spin.blockSignals(True)
        self.spin.setValue(self._value)
        self.spin.blockSignals(False)


class StringPropertyEditor(PropertyEditor):
    """Editor for string properties."""
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.line_edit = QLineEdit()
        self.line_edit.setText(str(self._value))
        layout.addWidget(self.line_edit)
        
        self.line_edit.editingFinished.connect(self._on_editing_finished)
    
    def _on_editing_finished(self):
        self._emit_change(self.line_edit.text())
    
    def _update_ui(self):
        self.line_edit.blockSignals(True)
        self.line_edit.setText(str(self._value))
        self.line_edit.blockSignals(False)


class BoolPropertyEditor(PropertyEditor):
    """Editor for boolean properties."""
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(self._value))
        layout.addWidget(self.checkbox)
        layout.addStretch()
        
        self.checkbox.toggled.connect(self._emit_change)
    
    def _update_ui(self):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(bool(self._value))
        self.checkbox.blockSignals(False)


class ColorPropertyEditor(PropertyEditor):
    """Editor for color properties."""
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self._update_button_color()
        
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaximumWidth(80)
        self.hex_edit.setText(self._get_hex())
        
        layout.addWidget(self.color_btn)
        layout.addWidget(self.hex_edit, 1)
        
        self.color_btn.clicked.connect(self._open_color_dialog)
        self.hex_edit.editingFinished.connect(self._on_hex_changed)
    
    def _get_hex(self) -> str:
        if isinstance(self._value, QColor):
            return self._value.name()
        elif isinstance(self._value, str):
            return self._value
        elif isinstance(self._value, (tuple, list)) and len(self._value) >= 3:
            return f"#{self._value[0]:02x}{self._value[1]:02x}{self._value[2]:02x}"
        return "#ffffff"
    
    def _update_button_color(self):
        hex_color = self._get_hex()
        self.color_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #30363d;")
    
    def _open_color_dialog(self):
        color = QColorDialog.getColor(QColor(self._get_hex()), self)
        if color.isValid():
            self._emit_change(color.name())
            self._update_button_color()
            self.hex_edit.setText(color.name())
    
    def _on_hex_changed(self):
        text = self.hex_edit.text()
        if not text.startswith("#"):
            text = "#" + text
        if QColor(text).isValid():
            self._emit_change(text)
            self._update_button_color()
    
    def _update_ui(self):
        self._update_button_color()
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(self._get_hex())
        self.hex_edit.blockSignals(False)


class Vec3PropertyEditor(PropertyEditor):
    """Editor for 3D vector properties (x, y, z)."""
    
    def __init__(
        self,
        name: str,
        value: tuple,
        min_val: float = -1e6,
        max_val: float = 1e6,
        step: float = 0.1,
        decimals: int = 3,
        parent: Optional[QWidget] = None
    ):
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.decimals = decimals
        super().__init__(name, value, parent)
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.spins = {}
        colors = {"X": "#ef4444", "Y": "#22c55e", "Z": "#3b82f6"}
        
        for i, (axis, color) in enumerate(colors.items()):
            label = QLabel(axis)
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            label.setFixedWidth(12)
            
            spin = QDoubleSpinBox()
            spin.setRange(self.min_val, self.max_val)
            spin.setSingleStep(self.step)
            spin.setDecimals(self.decimals)
            spin.setValue(self._value[i] if i < len(self._value) else 0.0)
            spin.setMinimumWidth(60)
            
            layout.addWidget(label)
            layout.addWidget(spin)
            
            self.spins[axis] = spin
            spin.valueChanged.connect(self._on_value_changed)
    
    def _on_value_changed(self):
        new_value = (
            self.spins["X"].value(),
            self.spins["Y"].value(),
            self.spins["Z"].value()
        )
        self._emit_change(new_value)
    
    def _update_ui(self):
        for i, axis in enumerate(["X", "Y", "Z"]):
            self.spins[axis].blockSignals(True)
            self.spins[axis].setValue(self._value[i] if i < len(self._value) else 0.0)
            self.spins[axis].blockSignals(False)


class ComboPropertyEditor(PropertyEditor):
    """Editor for enum/choice properties."""
    
    def __init__(
        self,
        name: str,
        value: str,
        choices: List[str],
        parent: Optional[QWidget] = None
    ):
        self.choices = choices
        super().__init__(name, value, parent)
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.combo = QComboBox()
        self.combo.addItems(self.choices)
        if self._value in self.choices:
            self.combo.setCurrentText(self._value)
        
        layout.addWidget(self.combo, 1)
        
        self.combo.currentTextChanged.connect(self._emit_change)
    
    def _update_ui(self):
        self.combo.blockSignals(True)
        if self._value in self.choices:
            self.combo.setCurrentText(self._value)
        self.combo.blockSignals(False)


class PropertySection(QWidget):
    """A collapsible section of properties."""
    
    propertyChanged = Signal(str, object)  # property name, new value
    
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.editors: Dict[str, PropertyEditor] = {}
        self._collapsed = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header
        self.header = QPushButton(f"▼ {self.title}")
        self.header.setFlat(True)
        self.header.setStyleSheet("""
            QPushButton {
                text-align: left;
                font-weight: bold;
                padding: 8px 4px;
                background-color: transparent;
                border: none;
                border-bottom: 1px solid #30363d;
            }
            QPushButton:hover {
                background-color: #21262d;
            }
        """)
        self.header.clicked.connect(self._toggle_collapsed)
        self.main_layout.addWidget(self.header)
        
        # Content
        self.content = QWidget()
        self.content_layout = QGridLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)
        self.content_layout.setColumnStretch(1, 1)
        
        self.main_layout.addWidget(self.content)
    
    def _toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        arrow = "▶" if self._collapsed else "▼"
        self.header.setText(f"{arrow} {self.title}")
    
    def addProperty(
        self,
        name: str,
        label: str,
        editor: PropertyEditor,
        row: Optional[int] = None
    ):
        """Add a property editor to this section."""
        if row is None:
            row = self.content_layout.rowCount()
        
        # Label
        lbl = QLabel(f"{label}:")
        lbl.setProperty("muted", True)
        self.content_layout.addWidget(lbl, row, 0, _AlignRight | _AlignVCenter)
        
        # Editor
        self.content_layout.addWidget(editor, row, 1)
        
        self.editors[name] = editor
        editor.valueChanged.connect(lambda n, v: self.propertyChanged.emit(n, v))
    
    def getProperty(self, name: str) -> Optional[Any]:
        """Get a property value by name."""
        editor = self.editors.get(name)
        return editor.getValue() if editor else None
    
    def setProperty(self, name: str, value: Any):
        """Set a property value by name."""
        editor = self.editors.get(name)
        if editor:
            editor.setValue(value)


class PropertiesPanel(QWidget):
    """Main properties panel with sections and undo/redo support."""
    
    propertyChanged = Signal(str, str, object)  # object_id, property_name, new_value
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sections: Dict[str, PropertySection] = {}
        self.current_object_id: Optional[str] = None
        self.undo_stack = UndoStack()
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header with object info and undo/redo
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 8, 8)
        
        self.object_label = QLabel("No Selection")
        self.object_label.setProperty("heading", True)
        header_layout.addWidget(self.object_label, 1)
        
        # Undo/Redo buttons
        self.undo_btn = QPushButton("↶")
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.setFixedSize(28, 28)
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._on_undo)
        
        self.redo_btn = QPushButton("↷")
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        self.redo_btn.setFixedSize(28, 28)
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._on_redo)
        
        header_layout.addWidget(self.undo_btn)
        header_layout.addWidget(self.redo_btn)
        
        main_layout.addWidget(header)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(_HLine)
        sep.setStyleSheet("color: #30363d;")
        main_layout.addWidget(sep)
        
        # Scroll area for sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()
        
        scroll.setWidget(self.scroll_content)
        main_layout.addWidget(scroll, 1)
        
        # No selection placeholder
        self.placeholder = QLabel("Select an object to view and edit its properties.")
        self.placeholder.setAlignment(_AlignCenter)
        self.placeholder.setProperty("muted", True)
        self.placeholder.setWordWrap(True)
        self.placeholder.setContentsMargins(20, 40, 20, 40)
        self.scroll_layout.insertWidget(0, self.placeholder)
    
    def addSection(self, name: str, title: str) -> PropertySection:
        """Add a property section."""
        section = PropertySection(title)
        section.propertyChanged.connect(self._on_property_changed)
        
        # Insert before the stretch
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, section)
        self.sections[name] = section
        
        return section
    
    def clearSections(self):
        """Clear all property sections."""
        for section in self.sections.values():
            section.deleteLater()
        self.sections.clear()
    
    def setObject(self, object_id: str, object_name: str, properties: Dict[str, Any]):
        """Set the current object and its properties."""
        self.current_object_id = object_id
        self.object_label.setText(object_name)
        self.placeholder.hide()
        
        # Clear and recreate sections based on properties
        self.clearSections()
        self._create_sections_for_object(properties)
    
    def clearObject(self):
        """Clear the current object selection."""
        self.current_object_id = None
        self.object_label.setText("No Selection")
        self.clearSections()
        self.placeholder.show()
    
    def _create_sections_for_object(self, properties: Dict[str, Any]):
        """Create property sections based on the object's properties."""
        # Group properties by category
        transform_props = {}
        geometry_props = {}
        appearance_props = {}
        other_props = {}
        
        for name, value in properties.items():
            lower_name = name.lower()
            if any(k in lower_name for k in ['position', 'rotation', 'scale', 'translation']):
                transform_props[name] = value
            elif any(k in lower_name for k in ['radius', 'width', 'height', 'depth', 'size', 'length']):
                geometry_props[name] = value
            elif any(k in lower_name for k in ['color', 'material', 'opacity', 'visible']):
                appearance_props[name] = value
            else:
                other_props[name] = value
        
        # Create sections
        if transform_props:
            section = self.addSection("transform", "Transform")
            self._add_properties_to_section(section, transform_props)
        
        if geometry_props:
            section = self.addSection("geometry", "Geometry")
            self._add_properties_to_section(section, geometry_props)
        
        if appearance_props:
            section = self.addSection("appearance", "Appearance")
            self._add_properties_to_section(section, appearance_props)
        
        if other_props:
            section = self.addSection("other", "Other")
            self._add_properties_to_section(section, other_props)
    
    def _add_properties_to_section(self, section: PropertySection, properties: Dict[str, Any]):
        """Add properties to a section with appropriate editors."""
        for name, value in properties.items():
            label = name.replace("_", " ").title()
            editor = self._create_editor_for_value(name, value)
            if editor:
                section.addProperty(name, label, editor)
    
    def _create_editor_for_value(self, name: str, value: Any) -> Optional[PropertyEditor]:
        """Create an appropriate editor for a value."""
        if isinstance(value, bool):
            return BoolPropertyEditor(name, value)
        elif isinstance(value, int):
            return IntPropertyEditor(name, value)
        elif isinstance(value, float):
            return FloatPropertyEditor(name, value)
        elif isinstance(value, str):
            if value.startswith("#") or name.lower().endswith("color"):
                return ColorPropertyEditor(name, value)
            return StringPropertyEditor(name, value)
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            if all(isinstance(v, (int, float)) for v in value):
                return Vec3PropertyEditor(name, tuple(value))
        return None
    
    def _on_property_changed(self, name: str, value: Any):
        """Handle property change from an editor."""
        if self.current_object_id:
            # Record for undo
            import time
            change = PropertyChange(
                object_id=self.current_object_id,
                property_name=name,
                old_value=None,  # Would need to track this
                new_value=value,
                timestamp=time.time()
            )
            self.undo_stack.push(change)
            self._update_undo_buttons()
            
            # Emit signal
            self.propertyChanged.emit(self.current_object_id, name, value)
    
    def _on_undo(self):
        """Handle undo button click."""
        change = self.undo_stack.undo()
        if change:
            # Apply the old value
            section = self._find_section_for_property(change.property_name)
            if section:
                section.setProperty(change.property_name, change.old_value)
            self.propertyChanged.emit(change.object_id, change.property_name, change.old_value)
        self._update_undo_buttons()
    
    def _on_redo(self):
        """Handle redo button click."""
        change = self.undo_stack.redo()
        if change:
            # Apply the new value
            section = self._find_section_for_property(change.property_name)
            if section:
                section.setProperty(change.property_name, change.new_value)
            self.propertyChanged.emit(change.object_id, change.property_name, change.new_value)
        self._update_undo_buttons()
    
    def _find_section_for_property(self, property_name: str) -> Optional[PropertySection]:
        """Find the section containing a property."""
        for section in self.sections.values():
            if property_name in section.editors:
                return section
        return None
    
    def _update_undo_buttons(self):
        """Update undo/redo button states."""
        self.undo_btn.setEnabled(self.undo_stack.can_undo())
        self.redo_btn.setEnabled(self.undo_stack.can_redo())
