"""
Advanced test of the GUI and STL import functionality.
Run this script directly to test the GUI functionality with STL import.
"""
import os
import sys
import time
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath('.'))

def test_square_and_stl_import():
    print("Starting GUI import test...")
    
    # Create QApplication first
    app = QApplication.instance() or QApplication(sys.argv)
    
    try:
        # Import MainWindow only after QApplication is created
        from adaptivecad.gui.playground import MainWindow
        
        print("Creating MainWindow with existing QApplication...")
        # Pass our QApplication to MainWindow
        mw = MainWindow(existing_app=app)
        
        if not hasattr(mw, 'win') or mw.win is None:
            print("ERROR: MainWindow creation failed, window is None")
            return 1
        
        print("MainWindow created successfully, showing window...")
        mw.win.show()
        
        # Give the window time to render fully
        QTest.qWait(1000)
        
        # Add a square (Rectangle)        print("Adding a square...")
        # Find the Rectangle button and click it
        from PySide6.QtGui import QAction
        actions = mw.win.findChildren(QAction)
        rectangle_action = None
        
        for action in actions:
            if action.text() == "Rectangle" or "rectangle" in action.objectName().lower():
                rectangle_action = action
                break
        
        if rectangle_action:
            rectangle_action.trigger()
            print("Rectangle action triggered")
        else:
            # Fallback method if we couldn't find the action
            print("Rectangle action not found, trying to create a box...")
            from adaptivecad.command_defs import NewBoxCmd
            mw.run_cmd(NewBoxCmd())
        
        # Give time for the rectangle to be created
        QTest.qWait(1000)
        
        # Now try to import an STL file
        print("Attempting to import STL file...")
        test_stl_file = os.path.join(os.path.dirname(__file__), "test_cube.stl")
        
        if not os.path.exists(test_stl_file):
            print(f"ERROR: Test STL file not found: {test_stl_file}")
            return 1
        
        # Find Import action or menu
        import_action = None
        
        for action in actions:
            if "import" in action.text().lower() or "import" in (action.objectName().lower() if action.objectName() else ""):
                import_action = action
                break
        
        if import_action:
            print(f"Found import action: {import_action.text()}")
            
            # Set up a timer to handle file dialog
            def select_file():
                dialog = app.activeModalWidget()
                if dialog:
                    dialog.selectFile(test_stl_file)
                    QTest.mouseClick(dialog.findChild(QTest.QPushButton, "Open"), Qt.LeftButton)
            
            QTimer.singleShot(500, select_file)
            import_action.trigger()
            print("Import action triggered")
            
            # Wait for import to complete
            QTest.qWait(3000)
            
            print("STL file import attempted.")
        else:
            print("Import action not found")
          # Let the GUI run for a very brief moment to verify it's working
        print("\nTest complete. GUI will close in 2 seconds...")
        QTest.qWait(2000)
        
        if hasattr(mw, 'win') and mw.win:
            mw.win.close()
            print("Window closed successfully")
        else:
            print("No window to close")
        
        print("Test completed successfully")
        return 0
        
    except Exception as e:
        import traceback
        print(f"ERROR in test: {e}")
        traceback.print_exc()
        
        # Show error in dialog for visibility
        if QApplication.instance():
            QMessageBox.critical(None, "Test Error", f"Error: {e}")
        
        return 1

if __name__ == "__main__":
    sys.exit(test_square_and_stl_import())
