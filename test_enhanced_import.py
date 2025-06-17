"""
Test the enhanced import with detailed debugging.
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
        print("\n🚀 Starting AdaptiveCAD playground with enhanced debugging...")
        
        app = QApplication.instance() or QApplication([])
        mw = MainWindow()
        mw.win.show()
        
        print("📋 Enhanced Import Instructions:")
        print("1. Use File -> Import -> STL/STEP (with Progress)")
        print("2. Import your STL file (benchy or test_cube.stl)")
        print("3. Watch the progress dialog AND the console output")
        print("4. Look for detailed debug messages about:")
        print("   - Shape loading status")
        print("   - Shape validation")
        print("   - Display operations")
        print("   - Scene rebuilding")
        print("   - View fitting")
        
        print("\n🔍 Console will show detailed debugging now...")
        print("🎯 This version should show exactly where the display issue occurs!")
        print("💡 If the model still doesn't appear, check the console for specific errors.")
        
        app.exec()
    else:
        print("✗ GUI not available")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
