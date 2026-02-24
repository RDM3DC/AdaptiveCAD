"""AdaptiveCAD Scene Tree - Hierarchical scene object management.

Provides a tree view for managing scene objects with:
- Object selection and multi-selection
- Visibility toggling
- Object grouping
- Property editing integration
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _CustomContextMenu = Qt.ContextMenuPolicy.CustomContextMenu
    _ItemIsSelectable = Qt.ItemFlag.ItemIsSelectable
    _ItemIsEnabled = Qt.ItemFlag.ItemIsEnabled
    _ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable
    _Checked = Qt.CheckState.Checked
    _Unchecked = Qt.CheckState.Unchecked
    _ExtendedSelection = QTreeWidget.SelectionMode.ExtendedSelection
except AttributeError:
    _AlignCenter = Qt.AlignCenter
    _CustomContextMenu = Qt.CustomContextMenu
    _ItemIsSelectable = Qt.ItemIsSelectable
    _ItemIsEnabled = Qt.ItemIsEnabled
    _ItemIsUserCheckable = Qt.ItemIsUserCheckable
    _Checked = Qt.Checked
    _Unchecked = Qt.Unchecked
    _ExtendedSelection = QTreeWidget.ExtendedSelection


# Shape type icons (emoji-based for simplicity)
SHAPE_ICONS = {
    "sphere": "🔵",
    "box": "⬜",
    "capsule": "💊",
    "torus": "🍩",
    "mobius": "♾️",
    "superellipsoid": "🥚",
    "quasicrystal": "💎",
    "torus4d": "🔮",
    "mandelbulb": "🌸",
    "klein": "🧬",
    "menger": "🧊",
    "hyperbolic": "🌀",
    "gyroid": "🧽",
    "trefoil": "🎀",
    "helicoid": "🌪️",
    "group": "📁",
    "unknown": "❓",
}


class SceneItem:
    """Represents an item in the scene tree."""
    
    def __init__(
        self,
        name: str,
        item_type: str,
        prim_index: int = -1,
        visible: bool = True,
        locked: bool = False,
    ):
        self.name = name
        self.item_type = item_type
        self.prim_index = prim_index  # Index in scene.prims list
        self.visible = visible
        self.locked = locked
        self.children: List[SceneItem] = []
        self.parent: Optional[SceneItem] = None
    
    def add_child(self, child: SceneItem):
        child.parent = self
        self.children.append(child)
    
    def remove_child(self, child: SceneItem):
        if child in self.children:
            child.parent = None
            self.children.remove(child)
    
    @property
    def icon(self) -> str:
        return SHAPE_ICONS.get(self.item_type, SHAPE_ICONS["unknown"])


class SceneTreeWidget(QTreeWidget):
    """Custom tree widget for scene management."""
    
    itemSelected = Signal(int)  # Emits prim index (single selection, for backwards compatibility)
    itemsSelected = Signal(list)  # Emits list of prim indices (multi-selection)
    itemVisibilityChanged = Signal(int, bool)  # prim index, visible
    itemDeleted = Signal(int)  # prim index
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scene = None
        self._items: Dict[int, QTreeWidgetItem] = {}
        
        self.setHeaderLabels(["Object", "Type"])
        self.setSelectionMode(_ExtendedSelection)
        self.setContextMenuPolicy(_CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemChanged.connect(self._on_item_changed)
        
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                color: #e6edf3;
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #21262d;
                border: 1px solid #58a6ff;
            }
            QTreeWidget::item:hover {
                background-color: #161b22;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #30363d;
            }
        """)
    
    def set_scene(self, scene):
        """Set the scene to display."""
        self.scene = scene
        self.refresh()
        
        # Listen for scene changes
        if hasattr(scene, 'on_changed'):
            scene.on_changed(self.refresh)
    
    def refresh(self):
        """Refresh the tree from the scene."""
        self.blockSignals(True)
        self.clear()
        self._items.clear()
        
        if not self.scene:
            self.blockSignals(False)
            return
        
        for i, prim in enumerate(self.scene.prims):
            kind = self._get_kind_name(prim.kind)
            icon = SHAPE_ICONS.get(kind, "❓")
            
            item = QTreeWidgetItem()
            item.setText(0, f"{icon} {kind.capitalize()}_{i}")
            item.setText(1, kind)
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            item.setFlags(_ItemIsSelectable | _ItemIsEnabled | _ItemIsUserCheckable)
            item.setCheckState(0, _Checked)
            
            self.addTopLevelItem(item)
            self._items[i] = item
        
        self.blockSignals(False)
    
    def _get_kind_name(self, kind) -> str:
        """Get the name of a primitive kind."""
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
            KIND_QUASICRYSTAL,
            KIND_SPHERE,
            KIND_SUPERELLIPSOID,
            KIND_TORUS,
            KIND_TORUS4D,
            KIND_TREFOIL,
        )
        
        kind_map = {
            KIND_SPHERE: "sphere",
            KIND_BOX: "box",
            KIND_CAPSULE: "capsule",
            KIND_TORUS: "torus",
            KIND_MOBIUS: "mobius",
            KIND_SUPERELLIPSOID: "superellipsoid",
            KIND_QUASICRYSTAL: "quasicrystal",
            KIND_TORUS4D: "torus4d",
            KIND_MANDELBULB: "mandelbulb",
            KIND_KLEIN: "klein",
            KIND_MENGER: "menger",
            KIND_HYPERBOLIC: "hyperbolic",
            KIND_GYROID: "gyroid",
            KIND_TREFOIL: "trefoil",
            KIND_HELICOID: "helicoid",
        }
        
        if isinstance(kind, str):
            return kind
        return kind_map.get(kind, "unknown")
    
    def _on_selection_changed(self):
        """Handle selection changes."""
        items = self.selectedItems()
        indices = []
        for item in items:
            prim_index = item.data(0, Qt.ItemDataRole.UserRole)
            if prim_index is not None:
                indices.append(prim_index)
        
        # Emit multi-selection signal
        self.itemsSelected.emit(indices)
        
        # Also emit single selection for backwards compatibility
        if indices:
            self.itemSelected.emit(indices[0])
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle item changes (visibility checkbox)."""
        if column == 0:
            prim_index = item.data(0, Qt.ItemDataRole.UserRole)
            if prim_index is not None:
                visible = item.checkState(0) == _Checked
                self.itemVisibilityChanged.emit(prim_index, visible)
    
    def _show_context_menu(self, pos):
        """Show context menu for tree items."""
        item = self.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #21262d;
            }
        """)
        
        if item:
            prim_index = item.data(0, Qt.ItemDataRole.UserRole)
            
            rename_action = menu.addAction("✏️ Rename")
            rename_action.triggered.connect(lambda: self._rename_item(item))
            
            menu.addSeparator()
            
            duplicate_action = menu.addAction("📋 Duplicate")
            duplicate_action.triggered.connect(lambda: self._duplicate_item(prim_index))
            
            delete_action = menu.addAction("🗑️ Delete")
            delete_action.triggered.connect(lambda: self._delete_item(prim_index))
            
            menu.addSeparator()
            
            hide_action = menu.addAction("👁️ Toggle Visibility")
            hide_action.triggered.connect(lambda: self._toggle_visibility(item))
        
        menu.addSeparator()
        select_all = menu.addAction("☑️ Select All")
        select_all.triggered.connect(self.selectAll)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _rename_item(self, item: QTreeWidgetItem):
        """Rename an item."""
        self.editItem(item, 0)
    
    def _duplicate_item(self, prim_index: int):
        """Duplicate a primitive."""
        if self.scene and 0 <= prim_index < len(self.scene.prims):
            import copy
            prim = self.scene.prims[prim_index]
            new_prim = copy.deepcopy(prim)
            new_prim.xform.M[:3, 3] += 0.5  # Offset slightly
            self.scene.add(new_prim)
    
    def _delete_item(self, prim_index: int):
        """Delete a primitive."""
        self.itemDeleted.emit(prim_index)
    
    def _toggle_visibility(self, item: QTreeWidgetItem):
        """Toggle item visibility."""
        current = item.checkState(0)
        item.setCheckState(0, _Unchecked if current == _Checked else _Checked)


class SceneTreeDock(QDockWidget):
    """Dock widget containing the scene tree."""
    
    objectSelected = Signal(int)  # Single selection (backwards compatibility)
    objectsSelected = Signal(list)  # Multi-selection
    objectDeleted = Signal(int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Scene", parent)
        self.setObjectName("SceneTreeDock")
        
        self._setup_ui()
    
    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter objects...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border-color: #58a6ff;
            }
        """)
        self.search_input.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Tree widget
        self.tree = SceneTreeWidget()
        self.tree.itemSelected.connect(self.objectSelected.emit)
        self.tree.itemsSelected.connect(self.objectsSelected.emit)
        self.tree.itemDeleted.connect(self.objectDeleted.emit)
        layout.addWidget(self.tree)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("➕")
        add_btn.setToolTip("Add Object")
        add_btn.setFixedSize(28, 28)
        
        group_btn = QPushButton("📁")
        group_btn.setToolTip("Group Selected")
        group_btn.setFixedSize(28, 28)
        
        delete_btn = QPushButton("🗑️")
        delete_btn.setToolTip("Delete Selected")
        delete_btn.setFixedSize(28, 28)
        delete_btn.clicked.connect(self._delete_selected)
        
        for btn in [add_btn, group_btn, delete_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    color: #e6edf3;
                }
                QPushButton:hover {
                    background-color: #30363d;
                }
            """)
            toolbar.addWidget(btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.setWidget(container)
        
        # Dock styling
        self.setStyleSheet("""
            QDockWidget {
                color: #e6edf3;
                font-weight: bold;
            }
            QDockWidget::title {
                background-color: #161b22;
                padding: 8px;
                border-bottom: 1px solid #30363d;
            }
        """)
    
    def set_scene(self, scene):
        """Set the scene to display."""
        self.tree.set_scene(scene)
    
    def refresh(self):
        """Refresh the tree."""
        self.tree.refresh()
    
    def _filter_tree(self, text: str):
        """Filter tree items by text."""
        text = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if text:
                item.setHidden(text not in item.text(0).lower())
            else:
                item.setHidden(False)
    
    def _delete_selected(self):
        """Delete selected items."""
        for item in self.tree.selectedItems():
            prim_index = item.data(0, Qt.ItemDataRole.UserRole)
            if prim_index is not None:
                self.objectDeleted.emit(prim_index)
    
    def select_indices(self, indices: list):
        """Select objects by their indices (for syncing with selection manager)."""
        self.tree.blockSignals(True)
        self.tree.clearSelection()
        for idx in indices:
            if idx in self.tree._items:
                self.tree._items[idx].setSelected(True)
        self.tree.blockSignals(False)
    
    def get_selected_indices(self) -> list:
        """Get the currently selected indices."""
        indices = []
        for item in self.tree.selectedItems():
            prim_index = item.data(0, Qt.ItemDataRole.UserRole)
            if prim_index is not None:
                indices.append(prim_index)
        return indices
