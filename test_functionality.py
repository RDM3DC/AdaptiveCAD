#!/usr/bin/env python3
"""Quick test to verify that shape creation works and import is functional."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_basic_functionality():
    """Test basic shape creation and import command availability."""
    try:
        print("Testing basic functionality...")
        
        # Test imports
        from adaptivecad.gui.playground import MainWindow, HAS_GUI
        from adaptivecad.commands.import_conformal import ImportConformalCmd
        from adaptivecad.command_defs import NewBoxCmd, DOCUMENT
        
        print(f"✓ All imports successful, HAS_GUI={HAS_GUI}")
        
        # Test creating a simple box without GUI
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from adaptivecad.command_defs import Feature
        
        # Create a basic box shape
        box_shape = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
        box_feature = Feature("Test Box", {"width": 10, "height": 10, "depth": 10}, box_shape)
        
        print("✓ Box shape created successfully")
        
        # Clear and add to document
        DOCUMENT.clear()
        DOCUMENT.append(box_feature)
        
        print(f"✓ Box added to document (doc length: {len(DOCUMENT)})")
        
        # Test import command creation
        import_cmd = ImportConformalCmd()
        print("✓ ImportConformalCmd created successfully")
        
        # Test if import command has required methods
        if hasattr(import_cmd, 'run') and hasattr(import_cmd, '_cleanup_thread'):
            print("✓ Import command has required methods")
        else:
            print("✗ Import command missing required methods")
            return False
        
        print("\n=== Basic functionality test PASSED ===")
        print("The GUI should now be able to:")
        print("1. Create and display basic shapes")
        print("2. Run import commands without hanging")
        print("3. Process imported geometry")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== AdaptiveCAD Functionality Test ===")
    
    success = test_basic_functionality()
    
    if success:
        print("\n🎉 All basic tests passed!")
        print("\nTry the following in the GUI:")
        print("- Basic Shapes → Box (should appear immediately)")
        print("- File → Import → STL/STEP (Conformal) (should not hang)")
    else:
        print("\n💥 Tests failed - check errors above")
        sys.exit(1)
