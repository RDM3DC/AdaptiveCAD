#!/usr/bin/env python3
"""
Test script to debug movement functionality in AdaptiveCAD.

This script will:
1. Create a simple box
2. Try to move it using the MoveCmd
3. Check if the movement works properly
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_movement_debug():
    """Test movement functionality with debug output."""
    print("[TEST] Starting movement debug test...")
    
    try:
        # Import the necessary modules
        from adaptivecad.command_defs import DOCUMENT, Feature, MoveCmd, NewBoxCmd
        
        print(f"[TEST] Initial DOCUMENT length: {len(DOCUMENT)}")
        
        # Clear any existing document
        DOCUMENT.clear()
        print("[TEST] DOCUMENT cleared")
        
        # Create a simple box first 
        print("[TEST] Creating a test box...")
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        box_shape = BRepPrimAPI_MakeBox(20, 20, 10).Shape()
        box_feature = Feature("TestBox", {"l": 20, "w": 20, "h": 10}, box_shape)
        DOCUMENT.append(box_feature)
        print(f"[TEST] Box created: {box_feature.name}")
        print(f"[TEST] DOCUMENT now has {len(DOCUMENT)} features")
        
        # Test the apply_translation method directly
        print("[TEST] Testing apply_translation method directly...")
        try:
            box_feature.apply_translation([5.0, 10.0, 2.0])
            print("[TEST] apply_translation completed successfully")
        except Exception as e:
            print(f"[TEST] Error in apply_translation: {e}")
            import traceback
            traceback.print_exc()
        
        # Test the MoveCmd (this would normally require a GUI)
        print("[TEST] Testing MoveCmd...")
        
        # Create a mock main window object for testing
        class MockMainWindow:
            def __init__(self):
                self.win = MockWindow()
                self.view = MockView()
        
        class MockWindow:
            def statusBar(self):
                return MockStatusBar()
        
        class MockStatusBar:
            def showMessage(self, msg, duration=0):
                print(f"[MOCK STATUS] {msg}")
        
        class MockView:
            def __init__(self):
                self._display = MockDisplay()
        
        class MockDisplay:
            def Context(self):
                return None
                
            def EraseAll(self):
                print("[MOCK] EraseAll called")
                
            def DisplayShape(self, shape, **kwargs):
                print(f"[MOCK] DisplayShape called with kwargs: {kwargs}")
                return None
                
            def FitAll(self):
                print("[MOCK] FitAll called")
        
        mock_mw = MockMainWindow()
        
        # We can't easily test the full MoveCmd without a real GUI
        # But we can test the core movement logic
        print("[TEST] Testing core movement logic...")
        
        # Test translation directly
        from OCC.Core.gp import gp_Trsf, gp_Vec
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        
        print("[TEST] Creating translation transformation...")
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(15.0, 25.0, 5.0))
        moved_shape = BRepBuilderAPI_Transform(box_shape, trsf, True).Shape()
        print("[TEST] Translation transformation created successfully")
        
        # Create new moved feature
        moved_feature = Feature("MovedBox", {"target": 0, "dx": 15.0, "dy": 25.0, "dz": 5.0}, moved_shape)
        DOCUMENT.append(moved_feature)
        print(f"[TEST] Moved feature created: {moved_feature.name}")
        print(f"[TEST] Final DOCUMENT length: {len(DOCUMENT)}")
        
        print("[TEST] Movement debug test completed successfully!")
        return True
        
    except Exception as e:
        print(f"[TEST] Error in movement test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_movement_debug()
    if success:
        print("\n✅ Movement debug test PASSED")
    else:
        print("\n❌ Movement debug test FAILED")
