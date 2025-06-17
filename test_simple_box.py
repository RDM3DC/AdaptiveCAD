#!/usr/bin/env python3
"""Simple GUI test - just show a box using the Basic Shapes menu."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def create_simple_box():
    """Create a simple box to test if object creation works."""
    try:
        print("Testing simple box creation...")
        
        # Import OpenCascade directly
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.gp import gp_Pnt
        
        # Create a simple 20x20x20 box
        box_maker = BRepPrimAPI_MakeBox(20.0, 20.0, 20.0)
        box_shape = box_maker.Shape()
        
        print(f"✓ Box shape created: {box_shape}")
        
        # Test if we can create a GUI display
        from adaptivecad.gui.playground import MainWindow
        from PySide6.QtCore import QTimer
        
        mw = MainWindow()
        
        print("✓ GUI MainWindow created")
        
        # Clear display and show the box
        print("Adding box to display...")
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(box_shape, update=True)
        mw.view._display.FitAll()
        
        print("✓ Box added to display")
        
        # Also add to document
        from adaptivecad.command_defs import Feature, DOCUMENT
        box_feature = Feature("Simple Box", {"width": 20, "height": 20, "depth": 20}, box_shape)
        DOCUMENT.clear()
        DOCUMENT.append(box_feature)
        
        print(f"✓ Box added to document (length: {len(DOCUMENT)})")
        
        # Show message in status bar
        mw.win.statusBar().showMessage("Simple Box Created - should be visible in 3D view", 5000)
        
        # Auto-close after 5 seconds
        QTimer.singleShot(5000, mw.app.quit)
        
        print("Starting GUI - the box should be visible...")
        result = mw.run()
        
        print(f"✓ GUI completed (exit code: {result})")
        return True
        
    except Exception as e:
        print(f"✗ Simple box test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Simple Box Creation Test ===")
    
    success = create_simple_box()
    
    if success:
        print("\n🎉 Simple box test completed!")
    else:
        print("\n💥 Simple box test failed.")
        sys.exit(1)
