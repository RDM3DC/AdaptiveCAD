#!/usr/bin/env python3
"""Test script to verify shape creation and display."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_shape_creation():
    """Test if shapes can be created and displayed properly."""
    try:
        print("Testing shape creation and display...")
        
        # Import required modules
        from adaptivecad.command_defs import NewBoxCmd, DOCUMENT
        from adaptivecad.gui.playground import MainWindow
        from PySide6.QtCore import QTimer
        
        # Create the main window
        mw = MainWindow()
        
        print("✓ MainWindow created")
        
        # Test creating a box
        print("Creating a test box...")
        box_cmd = NewBoxCmd()
        
        # Mock the dialog response for testing
        class MockMainWindow:
            def __init__(self, real_mw):
                self.win = real_mw.win
                self.view = real_mw.view
                
        mock_mw = MockMainWindow(mw)
        
        # Try to create a box programmatically
        from adaptivecad.command_defs import Feature
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        
        # Create a simple box shape
        box_shape = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
        box_feature = Feature("Test Box", {"width": 20, "height": 20, "depth": 20}, box_shape)
        
        # Add to document
        DOCUMENT.clear()  # Clear any existing objects
        DOCUMENT.append(box_feature)
        
        print(f"✓ Box created and added to document (doc length: {len(DOCUMENT)})")
        
        # Try to display it
        print("Attempting to display the box...")
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(box_shape, update=True)
        mw.view._display.FitAll()
        
        print("✓ Shape displayed successfully")
        
        # Auto-close after 3 seconds to verify it worked
        QTimer.singleShot(3000, mw.app.quit)
        
        print("Starting GUI to show the box for 3 seconds...")
        result = mw.run()
        
        print(f"✓ GUI test completed (exit code: {result})")
        return True
        
    except Exception as e:
        print(f"✗ Shape creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== AdaptiveCAD Shape Creation Test ===")
    
    success = test_shape_creation()
    
    if success:
        print("\n🎉 Shape creation test passed! Objects should appear in the GUI.")
    else:
        print("\n💥 Shape creation test failed.")
        sys.exit(1)
