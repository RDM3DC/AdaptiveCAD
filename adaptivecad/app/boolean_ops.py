"""Boolean Operations Manager

Provides UI and logic for managing boolean operations between primitives.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from adaptivecad.aacore.sdf import Prim, Scene

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    from PySide6.QtCore import Qt
    _AlignCenter = Qt.AlignmentFlag.AlignCenter  # type: ignore
except (AttributeError, ImportError):
    _AlignCenter = Qt.AlignCenter  # type: ignore


def apply_boolean_to_selection(scene: Scene, indices: List[int], operation: str) -> None:
    """Apply a boolean operation to selected primitives.
    
    Args:
        scene: Scene containing primitives
        indices: Indices of selected primitives
        operation: 'union' (solid), 'subtract', or 'intersect'
    """
    if not indices:
        return
    
    # Map operation to primitive op field
    op_map = {
        'union': 'solid',
        'subtract': 'subtract',
        'intersect': 'intersect',
    }
    
    target_op = op_map.get(operation, 'solid')
    
    # Apply operation to all selected primitives
    for idx in indices:
        if 0 <= idx < len(scene.prims):
            scene.prims[idx].op = target_op
    
    scene._notify()
    log.info(f"Applied {operation} to {len(indices)} primitive(s)")


def set_primitive_operation(prim: Prim, operation: str) -> None:
    """Set the boolean operation for a primitive.
    
    Args:
        prim: Primitive to modify
        operation: 'solid', 'subtract', or 'intersect'
    """
    if operation in ('solid', 'subtract', 'intersect'):
        prim.op = operation


class BooleanOperationsDialog(QDialog):
    """Dialog for applying boolean operations."""
    
    operationApplied = Signal(str)  # operation name
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("Boolean Operations")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info = QLabel("Apply boolean operation to selected objects:")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Operation selector
        form = QFormLayout()
        
        self.operation_combo = QComboBox()
        self.operation_combo.addItem("🔗 Union (Solid)", "union")
        self.operation_combo.addItem("➖ Subtract", "subtract")
        self.operation_combo.addItem("✖ Intersect", "intersect")
        
        form.addRow("Operation:", self.operation_combo)
        layout.addLayout(form)
        
        # Explanation
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.explanation)
        
        self._update_explanation()
        self.operation_combo.currentIndexChanged.connect(self._update_explanation)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self._apply_theme()
    
    def _update_explanation(self):
        """Update the explanation text based on selected operation."""
        explanations = {
            "union": "Combines objects additively. Default operation for most primitives.",
            "subtract": "Removes this object's volume from previous objects in the scene.",
            "intersect": "Keeps only the overlapping volume with previous objects.",
        }
        
        op = self.operation_combo.currentData()
        self.explanation.setText(explanations.get(op, ""))
    
    def get_operation(self) -> str:
        """Get the selected operation."""
        return self.operation_combo.currentData()
    
    def _apply_theme(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QLabel {
                color: #e6edf3;
            }
            QComboBox {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 24px;
            }
            QComboBox:hover {
                border-color: #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #161b22;
                color: #e6edf3;
                selection-background-color: #1f6feb;
                border: 1px solid #30363d;
            }
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 16px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
            }
            QPushButton:pressed {
                background-color: #1f6feb;
            }
        """)
