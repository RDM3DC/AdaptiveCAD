"""
Minimal PySide6 test script to check if Qt functionality works correctly.
"""
import sys

def test_simple_qt_window():
    try:
        print("Importing PySide6...")
        from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
        from PySide6.QtCore import Qt
        
        print("Creating QApplication...")
        app = QApplication(sys.argv)
        
        print("Creating main window...")
        window = QMainWindow()
        window.setWindowTitle("PySide6 Test")
        window.setMinimumSize(400, 300)
        
        label = QLabel("If you can see this, Qt is working correctly!", window)
        label.setAlignment(Qt.AlignCenter)
        window.setCentralWidget(label)
        
        print("Showing window...")
        window.show()
        
        print("Starting Qt event loop...")
        return app.exec()
    
    except Exception as e:
        print(f"Error in Qt test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_simple_qt_window())
