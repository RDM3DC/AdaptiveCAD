import pytest
from PySide6.QtWidgets import QApplication

def test_simple_qt_window():
    """Test creating a simple Qt window."""
    import sys
    # Check if QApplication already exists
    app = QApplication.instance() or QApplication(sys.argv)

    try:
        # Your test logic here
        assert app is not None, "QApplication instance should exist."
    finally:
        # Cleanup QApplication
        if not QApplication.instance():
            app.quit()