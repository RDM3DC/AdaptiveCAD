"""Minimal PySide6 + pythonOCC viewer prototype.

This module provides the ``AdaptiveCAD Playground`` application described in
``README.md``.  It launches a basic 3-D viewer using ``pythonocc-core`` and
``PySide6``.  The viewer displays a demo scene constructed from the geometric
primitives available in the package.  It is intentionally lightweight so that
contributors can quickly run ``python -m adaptivecad.gui.playground`` after
installing the optional GUI dependencies.

The GUI dependencies are not required for the rest of the package; therefore,
imports are done lazily with user-friendly error messages if the packages are
missing.
"""
from __future__ import annotations

import sys


def _require_gui_modules():
    """Import optional GUI modules, raising RuntimeError if unavailable."""
    try:
        from PySide6.QtWidgets import QApplication, QMainWindow  # type: ignore
        from OCC.Display.qtDisplay import qtViewer3d  # type: ignore
    except Exception as exc:  # pragma: no cover - import error path
        raise RuntimeError(
            "PySide6 and pythonocc-core are required to run the playground"
        ) from exc
    return QApplication, QMainWindow, qtViewer3d


def _demo_primitives(display):
    """Create a demo scene using simple primitives."""
    try:
        from adaptivecad import geom, linalg
    except Exception:  # pragma: no cover - should not happen
        return

    # Simple demo primitive: a Bezier curve extruded as points
    curve = geom.BezierCurve([
        linalg.Vec3(0.0, 0.0, 0.0),
        linalg.Vec3(25.0, 40.0, 0.0),
        linalg.Vec3(50.0, 0.0, 0.0),
    ])
    pts = [curve.evaluate(u / 20.0) for u in range(21)]
    for p in pts:
        display.DisplayShape((p.x, p.y, p.z))
    display.FitAll()


class MainWindow:
    """Main Playground window."""

    def __init__(self) -> None:
        QApplication, QMainWindow, qtViewer3d = _require_gui_modules()

        self.app = QApplication(sys.argv)
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)
        self._setup_demo()

    def _setup_demo(self) -> None:
        _demo_primitives(self.view._display)

    def run(self) -> None:
        self.win.show()
        self.app.exec()


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
