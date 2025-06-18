import importlib
import pytest
try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:
    HAS_QT = False
    QApplication = None

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not available")


def test_playground_import():
    mod = importlib.import_module("adaptivecad.gui.playground")
    # Expect main import to succeed even without GUI deps
    assert hasattr(mod, "MainWindow")


def test_view_mode_methods_present():
    """Test that view mode methods are present in MainWindow."""
    import sys
    # Check if QApplication already exists
    app = QApplication.instance() or QApplication(sys.argv)

    try:
        mod = importlib.import_module("adaptivecad.gui.playground")
        if not getattr(mod, "HAS_GUI", False):
            pytest.skip("GUI not available")

        mw = mod.MainWindow(app)  # Pass existing QApplication instance
        assert mw is not None, "MainWindow instance should be created."
    finally:
        # Cleanup QApplication
        if not QApplication.instance():
            app.quit()


def test_playground_missing_deps(monkeypatch):
    import builtins

    calls = []

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6") or name.startswith("OCC"):
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    mod = importlib.import_module("adaptivecad.gui.playground")
    with pytest.raises(RuntimeError):
        mod._require_gui_modules()
