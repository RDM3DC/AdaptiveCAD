"""
Test the fixed import without duplication.
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
        print("\n🚀 Starting AdaptiveCAD playground with FIXED import (no duplication)...")
        
        app = QApplication.instance() or QApplication([])
        mw = MainWindow()
        mw.win.show()
        
        print("📋 Fixed Import Instructions:")
        print("1. Use File -> Import -> STL/STEP (with Progress)")
        print("2. Import your STL file")
        print("3. Check console for:")
        print("   - Only ONE 'IMPORT COMPLETION HANDLER CALLED' message")
        print("   - Clear separation of display operations")
        print("   - No duplication of shape loading")
        
        print("\n🔧 FIXES APPLIED:")
        print("✓ Progress dialog no longer handles import_complete signal")
        print("✓ Only import command handles actual shape display")
        print("✓ Manual progress dialog updates to avoid duplication")
        print("✓ Clear debug boundaries to track operations")
        
        print("\n🎯 The model should now appear properly without duplication!")
        
        app.exec()
    else:
        print("✗ GUI not available")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
