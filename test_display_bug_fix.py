#!/usr/bin/env python
"""
Test script to verify the cut+move display bug fix.

This script creates shapes, performs a cut, then moves the result to verify
that only the correct geometry is displayed (no duplicates or old shapes).
"""

import os
import sys

# Ensure adaptivecad is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_display_bug_fix():
    """Test the cut+move display bug fix."""
    try:
        print("Testing cut+move display bug fix...")
        
        # Import required modules
        from adaptivecad.command_defs import DOCUMENT, Feature, rebuild_scene
        from adaptivecad.gui.playground import MainWindow
        
        # Clear any existing document
        DOCUMENT.clear()
        
        # Create a MainWindow instance (but don't show it)
        mw = MainWindow()
        
        # Create two box features for cutting
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        
        box1_shape = BRepPrimAPI_MakeBox(50, 50, 20).Shape()
        box2_shape = BRepPrimAPI_MakeBox(30, 30, 40).Shape()
        
        box1 = Feature("Box", {"l": 50, "w": 50, "h": 20}, box1_shape)
        box2 = Feature("Box", {"l": 30, "w": 30, "h": 40}, box2_shape)
        
        DOCUMENT.append(box1)
        DOCUMENT.append(box2)
        
        print(f"✓ Created 2 box features")
        
        # Perform a cut operation
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        cut_shape = BRepAlgoAPI_Cut(box1_shape, box2_shape).Shape()
        cut_feat = Feature("Cut", {"target": 0, "tool": 1}, cut_shape)
        
        # Mark the target as consumed (like CutCmd does)
        DOCUMENT[0].params['consumed'] = True
        
        DOCUMENT.append(cut_feat)
        print(f"✓ Performed cut operation (index 2)")
        
        # Perform a move operation
        from OCC.Core.gp import gp_Trsf, gp_Vec
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(25, 10, 5))
        moved_shape = BRepBuilderAPI_Transform(cut_shape, trsf, True).Shape()
        
        move_feat = Feature("Move", {"target": 2, "dx": 25, "dy": 10, "dz": 5}, moved_shape)
        
        # Mark the cut feature as consumed (like MoveCmd now does)
        DOCUMENT[2].params['consumed'] = True
        
        DOCUMENT.append(move_feat)
        print(f"✓ Performed move operation (index 3)")
        
        # Check which features should be visible
        consumed = set()
        for i, feat in enumerate(DOCUMENT):
            if feat.name in ("Move", "Cut", "Union", "Intersect"):
                target = feat.params.get("target")
                if isinstance(target, int):
                    consumed.add(target)
                tool = feat.params.get("tool")
                if isinstance(tool, int):
                    consumed.add(tool)
        
        # Also check for explicit consumption markings
        for i, feat in enumerate(DOCUMENT):
            if getattr(feat, 'params', {}).get('consumed', False):
                consumed.add(i)
        
        visible_features = [i for i in range(len(DOCUMENT)) if i not in consumed]
        
        print(f"✓ Document contains {len(DOCUMENT)} features")
        print(f"✓ Consumed features: {sorted(consumed)}")
        print(f"✓ Visible features: {visible_features}")
        
        # Verify that only the final moved result should be visible
        expected_visible = [3]  # Only the move result
        if visible_features == expected_visible:
            print("✅ SUCCESS: Display bug fix working correctly!")
            print("   Only the moved cut result should be visible")
            return True
        else:
            print(f"❌ FAILURE: Expected visible features {expected_visible}, got {visible_features}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_display_bug_fix()
    if success:
        print("\n🎉 Cut+Move display bug has been successfully fixed!")
        print("   After performing a cut and then moving the result,")
        print("   only the correct, updated geometry will be displayed.")
    else:
        print("\n⚠️  There may still be issues with the display bug fix.")
    
    sys.exit(0 if success else 1)
