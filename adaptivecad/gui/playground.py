"""Simplified GUI playground with optional dependencies."""

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True


if not HAS_GUI:

    class MainWindow:
        """Placeholder when GUI deps are unavailable."""

    def _require_gui_modules():
        raise RuntimeError("PySide6 and pythonocc-core are required to run the playground")

else:
    # Real implementation would go here in a full installation. We keep it minimal
    # for testing without GUI dependencies.
    from PySide6.QtWidgets import QApplication, QMainWindow  # type: ignore

    class MainWindow:
        def __init__(self) -> None:
            self.app = QApplication([])
            self.win = QMainWindow()

    def _require_gui_modules():
        return QApplication, QMainWindow
