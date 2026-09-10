"""Keep the metric dock readable in both existing, differently styled hosts."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDockWidget, QScrollArea


def prepare_metric_dock(host, dock):
    """Apply styling only to this dock and reuse a right-side tab location.

    A scroll container avoids forcing the host beyond the desktop height. No
    scene or other dock's contents are modified. Calling twice is a no-op.
    """
    if getattr(dock, "_metric_layout_ready", False):
        return dock
    dock._metric_layout_ready = True
    root = dock.widget()
    root.setParent(None)
    root.setObjectName("MetricWorkbenchRoot")
    scroll = QScrollArea(dock)
    scroll.setWidgetResizable(True)
    scroll.setMinimumHeight(180)
    scroll.setWidget(root)
    dock.setWidget(scroll)
    palette = QPalette(dock.palette())
    for role, color in (
        (QPalette.ColorRole.Window, "#202630"),
        (QPalette.ColorRole.Base, "#151b23"),
        (QPalette.ColorRole.Text, "#dce5ef"),
        (QPalette.ColorRole.WindowText, "#dce5ef"),
        (QPalette.ColorRole.ButtonText, "#dce5ef"),
        (QPalette.ColorRole.Highlight, "#66aaff"),
        (QPalette.ColorRole.Link, "#ffbe66"),
    ):
        palette.setColor(role, QColor(color))
    dock.setPalette(palette)
    dock.view.setBackgroundBrush(QColor("#151b23"))
    dock.setStyleSheet("""
        QDockWidget { color: #dce5ef; }
        QWidget#MetricWorkbenchRoot, QScrollArea { background: #202630; }
        QLabel, QCheckBox { color: #dce5ef; background: transparent; }
        QPlainTextEdit, QLineEdit, QComboBox, QAbstractItemView, QGraphicsView {
            background: #151b23; color: #dce5ef; border: 1px solid #455363;
            selection-background-color: #365a7e;
        }
        QPushButton, QToolButton {
            color: #dce5ef; background: #303c4c; border: 1px solid #455363;
            padding: 4px;
        }
        QPushButton:hover, QToolButton:hover { background: #40556c; }
        QPushButton:disabled, QToolButton:disabled { color: #7f8c99; }
        QToolBar { background: #202630; border: none; }
        QTabWidget::pane { background: #202630; border: 1px solid #455363; }
        QTabBar::tab { color: #dce5ef; background: #303c4c; padding: 5px; }
        QTabBar::tab:selected { background: #40556c; }
    """)
    peers = [p for p in host.findChildren(QDockWidget)
             if p is not dock and host.dockWidgetArea(p) == Qt.DockWidgetArea.RightDockWidgetArea]
    if peers:
        peer = max(peers, key=lambda p: p.height())
        host.tabifyDockWidget(peer, dock)
        peer.raise_()
    dock.toggleViewAction().triggered.connect(lambda visible: dock.raise_() if visible else None)
    dock.redraw()
    dock.hide()
    return dock
