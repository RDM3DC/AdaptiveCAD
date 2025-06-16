from PySide6.QtWidgets import QDockWidget, QCheckBox, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from adaptivecad.snap_points import SNAP_TYPES

class SnapMenu(QDockWidget):
    """Dock widget with check boxes to toggle snap types."""

    def __init__(self, mainwin):
        super().__init__("Snap Types")
        self.mainwin = mainwin
        widget = QWidget()
        layout = QVBoxLayout()
        self.checks = {}
        for name in SNAP_TYPES:
            cb = QCheckBox(name)
            cb.setChecked(SNAP_TYPES[name])
            cb.stateChanged.connect(self._make_toggler(name))
            layout.addWidget(cb)
            self.checks[name] = cb
        layout.addStretch(1)
        widget.setLayout(layout)
        self.setWidget(widget)
        self.setFloating(False)

    def _make_toggler(self, name):
        def f(state):
            SNAP_TYPES[name] = bool(state)
            if hasattr(self.mainwin, "update_snap_points_display"):
                self.mainwin.update_snap_points_display()
        return f
