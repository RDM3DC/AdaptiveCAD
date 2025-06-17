"""
Simple test to verify that the GUI can be started and basic operations work.
"""
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath('.'))

def main():
    print("Starting simple GUI test...")
    
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
        
        # Try to add a box
        print("Adding a box...")
        from adaptivecad.command_defs import NewBoxCmd
        mw.run_cmd(NewBoxCmd())
        print("Box command initiated")
        
        # Let the window stay visible briefly
        print("Window will close in 3 seconds...")
        QTest.qWait(3000)
        
        # Close the window
        mw.win.close()
        print("Window closed successfully")
        
        print("Test completed successfully!")
        return 0
        
    except Exception as e:
        import traceback
        print(f"ERROR in test: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
