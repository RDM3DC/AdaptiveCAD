import os, importlib, pytest

# Force an offscreen platform if available to allow import in CI without display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401
    HAS_QT = True
except Exception:
    HAS_QT = False

@pytest.mark.skipif(not HAS_QT, reason="PySide6 not available")
def test_playground_import_offscreen():
    mod = importlib.import_module("adaptivecad.gui.playground")
    # Module should define HAS_GUI (True if OCC + PySide6 loaded)
    assert hasattr(mod, "HAS_GUI")
    # We only assert that it *defines* the GUI flag; actual GUI may be False if OCC missing.
