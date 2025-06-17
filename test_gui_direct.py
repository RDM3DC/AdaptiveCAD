"""
Direct test of the GUI and STL import functionality.
Run this script directly to test the GUI functionality.

This version uses the updated MainWindow class that accepts an existing QApplication.
"""
import os
import sys
import time
from PySide6.QtWidgets import QApplication, QMessageBox

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath('.'))

def main():
    print("Setting up QApplication...")
    app = QApplication.instance() or QApplication(sys.argv)
    
    try:
        # Import MainWindow from playground 
        from adaptivecad.gui.playground import MainWindow, HAS_GUI
        
        # Check if GUI is available
        print(f"HAS_GUI: {HAS_GUI}")
        if not HAS_GUI:
            print("ERROR: GUI dependencies not available")
            return 1
        
        print("Creating MainWindow with existing QApplication...")
        mw = MainWindow(existing_app=app)
        
        if not hasattr(mw, 'win') or mw.win is None:
            print("ERROR: MainWindow creation failed, window is None")
            return 1
        
        print("MainWindow created successfully, showing window...")
        mw.win.show()
        
        print("GUI is now visible, let's test import functionality...")
        
        # Pause to allow the GUI to stabilize
        time.sleep(2)
        
        # Check that the window is displayed properly
        if hasattr(mw, 'win') and mw.win.isVisible():
            print("Window is visible, test PASS")
        else:
            print("Window is not visible, test FAIL")
            return 1
        
        # Try adding a box
        try:
            print("Attempting to add a box...")
            from adaptivecad.command_defs import NewBoxCmd
            mw.execute_command(NewBoxCmd())
            print("Box added successfully")
        except Exception as e:
            print(f"Failed to add box: {e}")
        
        # Try importing an STL file
        try:
            print("Attempting to import STL file...")
            test_stl_file = os.path.abspath("test_cube.stl")
            
            if not os.path.exists(test_stl_file):
                print(f"WARNING: Test STL file not found: {test_stl_file}")
                # Try to find it elsewhere
                test_stl_file = os.path.join(os.path.dirname(__file__), "test_cube.stl")
            
            if os.path.exists(test_stl_file):
                from adaptivecad.commands.import_conformal import ImportConformalCmd
                cmd = ImportConformalCmd()
                cmd.filename = test_stl_file
                mw.execute_command(cmd)
                print("STL import command executed successfully")
            else:
                print("ERROR: Could not find test_cube.stl file")
        except Exception as e:
            print(f"STL import error: {e}")
        
        # Let the application run until user closes it
        print("\nTest complete. You can now interact with the GUI.")
        print("Close the window to exit the test.")
        
        return app.exec()
        
    except Exception as e:
        import traceback
        print(f"Error in test: {e}")
        traceback.print_exc()
        
        # Show error in dialog for visibility
        if QApplication.instance():
            QMessageBox.critical(None, "Test Error", f"Error: {e}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
