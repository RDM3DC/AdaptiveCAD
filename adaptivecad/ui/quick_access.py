"""
AdaptiveCAD Quick Access Toolbar

A floating, customizable quick-access toolbar for common operations
with support for shortcuts and drag-to-customize functionality.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _LeftButton = Qt.MouseButton.LeftButton
    _MoveAction = Qt.DropAction.MoveAction
    _Horizontal = Qt.Orientation.Horizontal
    _Tool = Qt.WindowType.Tool
    _FramelessWindowHint = Qt.WindowType.FramelessWindowHint
    _WA_TranslucentBackground = Qt.WidgetAttribute.WA_TranslucentBackground
    _SizeAllCursor = Qt.CursorShape.SizeAllCursor
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _VLine = QFrame.Shape.VLine
except AttributeError:
    _LeftButton = Qt.LeftButton
    _MoveAction = Qt.MoveAction
    _Horizontal = Qt.Horizontal
    _Tool = Qt.Tool
    _FramelessWindowHint = Qt.FramelessWindowHint
    _WA_TranslucentBackground = Qt.WA_TranslucentBackground
    _SizeAllCursor = Qt.SizeAllCursor
    _AlignCenter = Qt.AlignCenter
    _VLine = QFrame.VLine

# Default quick access configuration
DEFAULT_QUICK_ACCESS = [
    {"id": "new", "icon": "📄", "label": "New", "shortcut": "Ctrl+N", "tooltip": "New Project"},
    {"id": "open", "icon": "📂", "label": "Open", "shortcut": "Ctrl+O", "tooltip": "Open Project"},
    {"id": "save", "icon": "💾", "label": "Save", "shortcut": "Ctrl+S", "tooltip": "Save Project"},
    {"id": "separator", "type": "separator"},
    {"id": "undo", "icon": "↶", "label": "Undo", "shortcut": "Ctrl+Z", "tooltip": "Undo"},
    {"id": "redo", "icon": "↷", "label": "Redo", "shortcut": "Ctrl+Y", "tooltip": "Redo"},
    {"id": "separator2", "type": "separator"},
    {"id": "box", "icon": "⬜", "label": "Box", "shortcut": "B", "tooltip": "Create Box"},
    {"id": "cylinder", "icon": "⬤", "label": "Cylinder", "shortcut": "C", "tooltip": "Create Cylinder"},
    {"id": "sphere", "icon": "●", "label": "Sphere", "shortcut": "S", "tooltip": "Create Sphere"},
    {"id": "separator3", "type": "separator"},
    {"id": "move", "icon": "✥", "label": "Move", "shortcut": "G", "tooltip": "Move Selection"},
    {"id": "rotate", "icon": "⟳", "label": "Rotate", "shortcut": "R", "tooltip": "Rotate Selection"},
    {"id": "delete", "icon": "🗑", "label": "Delete", "shortcut": "Del", "tooltip": "Delete Selection"},
]


@dataclass
class QuickAction:
    """Definition of a quick access action."""
    id: str
    icon: str = ""
    label: str = ""
    shortcut: str = ""
    tooltip: str = ""
    action_type: str = "action"  # 'action', 'separator', 'toggle'
    checked: bool = False
    callback: Optional[Callable] = None


class QuickAccessButton(QToolButton):
    """A button in the quick access toolbar."""
    
    customizeRequested = Signal()
    dragStarted = Signal(str)  # action id
    
    def __init__(
        self,
        action: QuickAction,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.action = action
        self._drag_start_pos: Optional[QPoint] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFixedSize(36, 36)
        self.setText(self.action.icon or self.action.label[0])
        self.setToolTip(self._format_tooltip())
        
        if self.action.action_type == "toggle":
            self.setCheckable(True)
            self.setChecked(self.action.checked)
        
        self.setStyleSheet("""
            QToolButton {
                background-color: #1a1f26;
                border: 1px solid #30363d;
                border-radius: 6px;
                font-size: 16px;
                color: #e6edf3;
            }
            QToolButton:hover {
                background-color: #21262d;
                border-color: #58a6ff;
            }
            QToolButton:pressed {
                background-color: #0d1117;
            }
            QToolButton:checked {
                background-color: #1f3a5f;
                border-color: #58a6ff;
            }
        """)
        
        self.clicked.connect(self._on_clicked)
    
    def _format_tooltip(self) -> str:
        tooltip = self.action.tooltip or self.action.label
        if self.action.shortcut:
            tooltip += f" ({self.action.shortcut})"
        return tooltip
    
    def _on_clicked(self):
        if self.action.callback:
            self.action.callback()
    
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        menu.addAction("Remove from Quick Access")
        menu.addSeparator()
        customize_action = menu.addAction("Customize Toolbar...")
        
        result = menu.exec(event.globalPos())
        
        if result == customize_action:
            self.customizeRequested.emit()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == _LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_pos is not None:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._start_drag()
                self._drag_start_pos = None
                return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def _start_drag(self):
        """Start a drag operation for reordering."""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.action.id)
        drag.setMimeData(mime_data)
        
        # Create drag pixmap
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        self.dragStarted.emit(self.action.id)
        drag.exec(_MoveAction)


class QuickAccessSeparator(QFrame):
    """A separator in the quick access toolbar."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(_VLine)
        self.setFixedSize(8, 24)
        self.setStyleSheet("color: #30363d;")


class QuickAccessToolbar(QWidget):
    """A floating quick access toolbar with common operations."""
    
    actionTriggered = Signal(str)  # action id
    customizeRequested = Signal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        orientation = None  # Qt.Orientation
    ):
        super().__init__(parent)
        self.orientation = orientation if orientation is not None else _Horizontal
        self.actions: Dict[str, QuickAction] = {}
        self.buttons: Dict[str, QuickAccessButton] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._dragging = False
        
        self.setWindowFlags(_Tool | _FramelessWindowHint)
        self.setAttribute(_WA_TranslucentBackground)
        
        self._setup_ui()
        self._load_config()
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
    
    def _setup_ui(self):
        self.main_layout = QHBoxLayout(self) if self.orientation == _Horizontal else QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        
        # Container for styling
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background-color: #0f1419;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        
        self.container_layout = QHBoxLayout(self.container) if self.orientation == _Horizontal else QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(6, 6, 6, 6)
        self.container_layout.setSpacing(4)
        
        # Grip handle for moving
        self.grip = QLabel("⋮⋮")
        self.grip.setStyleSheet("color: #6e7681; font-size: 12px;")
        self.grip.setCursor(_SizeAllCursor)
        self.container_layout.addWidget(self.grip)
        
        # Separator after grip
        sep = QuickAccessSeparator()
        self.container_layout.addWidget(sep)
        
        self.main_layout.addWidget(self.container)
    
    def _load_config(self):
        """Load quick access configuration."""
        config_path = Path.home() / ".adaptivecad" / "quick_access.json"
        
        try:
            if config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                config = DEFAULT_QUICK_ACCESS
        except Exception:
            config = DEFAULT_QUICK_ACCESS
        
        self._build_from_config(config)
    
    def _save_config(self):
        """Save quick access configuration."""
        config_path = Path.home() / ".adaptivecad" / "quick_access.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = []
        for action in self.actions.values():
            if action.action_type == "separator":
                config.append({"id": action.id, "type": "separator"})
            else:
                config.append({
                    "id": action.id,
                    "icon": action.icon,
                    "label": action.label,
                    "shortcut": action.shortcut,
                    "tooltip": action.tooltip,
                })
        
        try:
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"Failed to save quick access config: {e}")
    
    def _build_from_config(self, config: List[dict]):
        """Build toolbar from configuration."""
        # Clear existing
        for button in self.buttons.values():
            button.deleteLater()
        self.buttons.clear()
        self.actions.clear()
        
        for item in config:
            if item.get("type") == "separator":
                action = QuickAction(
                    id=item["id"],
                    action_type="separator"
                )
                self.actions[action.id] = action
                
                sep = QuickAccessSeparator()
                self.container_layout.addWidget(sep)
            else:
                action = QuickAction(
                    id=item["id"],
                    icon=item.get("icon", ""),
                    label=item.get("label", item["id"]),
                    shortcut=item.get("shortcut", ""),
                    tooltip=item.get("tooltip", ""),
                    callback=self._callbacks.get(item["id"]),
                )
                self.actions[action.id] = action
                
                button = QuickAccessButton(action)
                button.clicked.connect(lambda checked, aid=action.id: self.actionTriggered.emit(aid))
                button.customizeRequested.connect(self.customizeRequested.emit)
                
                self.container_layout.addWidget(button)
                self.buttons[action.id] = button
    
    def setCallback(self, action_id: str, callback: Callable):
        """Set the callback for an action."""
        self._callbacks[action_id] = callback
        
        if action_id in self.actions:
            self.actions[action_id].callback = callback
        
        if action_id in self.buttons:
            self.buttons[action_id].action.callback = callback
    
    def addAction(
        self,
        action_id: str,
        icon: str = "",
        label: str = "",
        shortcut: str = "",
        tooltip: str = "",
        callback: Optional[Callable] = None,
    ):
        """Add an action to the toolbar."""
        if callback:
            self._callbacks[action_id] = callback
        
        action = QuickAction(
            id=action_id,
            icon=icon,
            label=label or action_id,
            shortcut=shortcut,
            tooltip=tooltip,
            callback=callback,
        )
        self.actions[action_id] = action
        
        button = QuickAccessButton(action)
        button.clicked.connect(lambda checked, aid=action_id: self.actionTriggered.emit(aid))
        button.customizeRequested.connect(self.customizeRequested.emit)
        
        self.container_layout.addWidget(button)
        self.buttons[action_id] = button
    
    def addSeparator(self, separator_id: str = ""):
        """Add a separator to the toolbar."""
        if not separator_id:
            separator_id = f"separator_{len(self.actions)}"
        
        action = QuickAction(id=separator_id, action_type="separator")
        self.actions[separator_id] = action
        
        sep = QuickAccessSeparator()
        self.container_layout.addWidget(sep)
    
    def removeAction(self, action_id: str):
        """Remove an action from the toolbar."""
        if action_id in self.buttons:
            self.buttons[action_id].deleteLater()
            del self.buttons[action_id]
        
        if action_id in self.actions:
            del self.actions[action_id]
        
        self._save_config()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == _LeftButton:
            # Check if clicking on grip
            grip_rect = self.grip.geometry()
            if grip_rect.contains(event.pos()):
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if hasattr(self, '_drag_pos') and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if hasattr(self, '_drag_pos'):
            self._drag_pos = None
        super().mouseReleaseEvent(event)


class QuickAccessDock(QWidget):
    """A dockable version of the quick access toolbar."""
    
    actionTriggered = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._callbacks: Dict[str, Callable] = {}
        
        self._setup_ui()
        self._load_default_actions()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Title
        title = QLabel("Quick Access")
        title.setProperty("heading", True)
        title.setAlignment(_AlignCenter)
        layout.addWidget(title)
        
        # Button grid
        self.button_grid = QGridLayout()
        self.button_grid.setSpacing(4)
        layout.addLayout(self.button_grid)
        
        layout.addStretch()
        
        # Customize button
        customize_btn = QPushButton("Customize...")
        customize_btn.setProperty("muted", True)
        customize_btn.clicked.connect(self._show_customize_dialog)
        layout.addWidget(customize_btn)
    
    def _load_default_actions(self):
        """Load default quick access actions."""
        actions = [
            ("new", "📄", "New"),
            ("open", "📂", "Open"),
            ("save", "💾", "Save"),
            ("undo", "↶", "Undo"),
            ("redo", "↷", "Redo"),
            ("box", "⬜", "Box"),
            ("cylinder", "⬤", "Cylinder"),
            ("sphere", "●", "Sphere"),
            ("torus", "◯", "Torus"),
            ("move", "✥", "Move"),
            ("rotate", "⟳", "Rotate"),
            ("delete", "🗑", "Delete"),
        ]
        
        cols = 4
        for i, (action_id, icon, label) in enumerate(actions):
            row, col = divmod(i, cols)
            
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(label)
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QToolButton {
                    background-color: #1a1f26;
                    border: 1px solid #30363d;
                    border-radius: 6px;
                    font-size: 18px;
                }
                QToolButton:hover {
                    background-color: #21262d;
                    border-color: #58a6ff;
                }
                QToolButton:pressed {
                    background-color: #0d1117;
                }
            """)
            btn.clicked.connect(lambda checked, aid=action_id: self._on_action_clicked(aid))
            
            self.button_grid.addWidget(btn, row, col)
    
    def _on_action_clicked(self, action_id: str):
        """Handle action button click."""
        self.actionTriggered.emit(action_id)
        
        if action_id in self._callbacks:
            self._callbacks[action_id]()
    
    def setCallback(self, action_id: str, callback: Callable):
        """Set callback for an action."""
        self._callbacks[action_id] = callback
    
    def _show_customize_dialog(self):
        """Show the customization dialog."""
        # TODO: Implement customization dialog
        log.info("Customize dialog not implemented yet")
