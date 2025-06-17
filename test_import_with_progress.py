"""
Test script to run the playground GUI and test the progress dialog.
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, r'd:\SuperCAD\AdaptiveCAD')

# First, let's test if our progress dialog can be imported
try:
    from adaptivecad.gui.import_progress_dialog import ImportProgressDialog
    print("✓ Progress dialog imported successfully")
except Exception as e:
    print(f"✗ Error importing progress dialog: {e}")
    import traceback
    traceback.print_exc()

# Test basic GUI dependencies
try:
    from PySide6.QtWidgets import QApplication
    from adaptivecad.gui.playground import MainWindow, HAS_GUI
    print(f"✓ GUI dependencies available: HAS_GUI = {HAS_GUI}")
except Exception as e:
    print(f"✗ Error importing GUI components: {e}")
    import traceback
    traceback.print_exc()

# Test import command
try:
    from adaptivecad.commands.import_conformal import ImportConformalCmd
    print("✓ Import command imported successfully")
    cmd = ImportConformalCmd()
    print("✓ Import command instantiated")
except Exception as e:
    print(f"✗ Error with import command: {e}")
    import traceback
    traceback.print_exc()

if HAS_GUI:
    print("\n🚀 Starting playground GUI...")
    try:
        app = QApplication.instance() or QApplication([])
        mw = MainWindow()
        mw.win.show()
        
        print("📋 Instructions:")
        print("1. Use File -> Import -> STL/STEP (Conformal) to test import")
        print("2. Try importing a STL file (e.g., test_cube.stl)")
        print("3. Watch the progress dialog for detailed debug output")
        print("4. Check the console for debug messages")
        
        print("\n🔍 Console will show debug output during import...")
        
        app.exec()
    except Exception as e:
        print(f"✗ Error running GUI: {e}")
        import traceback
        traceback.print_exc()
else:
    print("✗ GUI not available")
