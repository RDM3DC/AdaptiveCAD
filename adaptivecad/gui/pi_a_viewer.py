"""Minimal read-only viewer demonstrating the πₐ metric."""

from __future__ import annotations

try:
    from PySide6.QtWidgets import QApplication
    from .playground import MainWindow, HAS_GUI
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False


def main() -> None:  # pragma: no cover - GUI integration
    """Launch the read-only viewer if GUI libraries are available."""
    if not HAS_GUI:
        raise RuntimeError("PySide6 not available")

    app = QApplication([])
    mw = MainWindow()
    if hasattr(mw, "main_toolbar"):
        mw.main_toolbar.setDisabled(True)
    mw.win.setWindowTitle("πₐ Viewer")
    mw.win.show()
    app.exec()


if __name__ == "__main__":  # pragma: no cover - script mode
    main()
