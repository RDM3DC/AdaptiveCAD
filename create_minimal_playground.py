"""Create a basic version of playground.py that properly defines MainWindow at module level."""

import os

# Create a minimal playground.py file that will run
playground_path = r"d:\SuperCAD\AdaptiveCAD\adaptivecad\gui\playground.py"
backup_path = playground_path + '.minimal_backup'

print(f"Creating backup at {backup_path}...")
if os.path.exists(playground_path):
    with open(playground_path, 'r', encoding='utf-8') as f:
        original = f.read()
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original)

minimal_playground = '''"""Simplified GUI playground with optional dependencies."""

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True  # Ensure HAS_GUI is set to True here
    import numpy as np
    import traceback
    from adaptivecad import settings
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox
    )

# Make sure MainWindow is defined regardless of HAS_GUI
class MainWindow:
    def __init__(self):
        if not HAS_GUI:
            print("GUI dependencies not available. Cannot create MainWindow.")
            return
        
        self.app = QApplication.instance() or QApplication([])
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD - Minimal Playground (GUI Fixed)")
        self.win.resize(800, 600)
    
    def run(self):
        if not HAS_GUI:
            print("Error: Cannot run GUI without PySide6 and OCC.Display dependencies.")
            return 1
        
        self.win.show()
        return self.app.exec()

def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
'''

with open(playground_path, 'w', encoding='utf-8') as f:
    f.write(minimal_playground)

print(f"Created minimal playground.py at {playground_path}")
print("Try running 'python -m adaptivecad.gui.playground' now")
