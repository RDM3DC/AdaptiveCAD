"""
Test the playground with the working simple import and progress dialog.
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, r'd:\SuperCAD\AdaptiveCAD')

try:
    from adaptivecad.gui.playground import MainWindow, HAS_GUI
    from PySide6.QtWidgets import QApplication
    
    print(f"✓ GUI components imported successfully: HAS_GUI = {HAS_GUI}")
    
    if HAS_GUI:
        print("\n🚀 Starting AdaptiveCAD playground with progress dialog...")
        
        app = QApplication.instance() or QApplication([])
        mw = MainWindow()
        mw.win.show()
        
        print("📋 Instructions:")
        print("1. Use File -> Import -> STL/STEP (with Progress) to test import")
        print("2. Try importing a STL file (e.g., test_cube.stl)")
        print("3. Watch the progress dialog for detailed output")
        print("4. The model should appear in the 3D viewer after import")
        print("5. Check the console for debug messages")
        
        print("\n🔍 Progress dialog will show detailed import steps...")
        print("🎯 This version should successfully show the imported model!")
        
        app.exec()
    else:
        print("✗ GUI not available")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
