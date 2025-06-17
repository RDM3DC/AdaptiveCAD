#!/usr/bin/env python3
"""Quick test to verify GUI starts without hanging."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_gui_startup():
    """Test if the GUI can start without hanging."""
    try:
        print("Testing GUI startup...")
        
        from adaptivecad.gui.playground import MainWindow
        from PySide6.QtCore import QTimer
        
        # Create the main window
        mw = MainWindow()
        
        # Auto-close after 2 seconds
        QTimer.singleShot(2000, mw.app.quit)
        
        print("✓ MainWindow created successfully")
        print("Starting GUI for 2 seconds to test for hanging...")
        
        # Run the application briefly
        result = mw.run()
        
        print(f"✓ GUI ran and closed normally (exit code: {result})")
        return True
        
    except Exception as e:
        print(f"✗ GUI startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== AdaptiveCAD GUI Startup Test ===")
    
    success = test_gui_startup()
    
    if success:
        print("\n🎉 GUI startup test passed! No hanging detected.")
    else:
        print("\n💥 GUI startup test failed.")
        sys.exit(1)
