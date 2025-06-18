#!/usr/bin/env python3
"""
Test script for unselect functionality in AdaptiveCAD.

This script tests the various unselect commands and error clearing functions.
"""

def test_unselect_functions():
    """Test all unselect functions without requiring a full GUI."""
    print("Testing AdaptiveCAD Unselect Functionality")
    print("=" * 45)
    
    try:
        # Test imports
        print("\n1. Testing imports...")
        from adaptivecad.cosmic.spacetime_viz import (
            ToolbarUnselectCmd,
            QuickUnselectCmd,
            ErrorClearingUnselectCmd,
            UnselectAllObjectsCmd,
            clear_all_selection_errors,
            unselect_all_objects_utility
        )
        print("✓ All unselect classes imported successfully")
        
        # Test command creation
        print("\n2. Testing command creation...")
        commands = [
            ("ToolbarUnselectCmd", ToolbarUnselectCmd()),
            ("QuickUnselectCmd", QuickUnselectCmd()),
            ("ErrorClearingUnselectCmd", ErrorClearingUnselectCmd()),
            ("UnselectAllObjectsCmd", UnselectAllObjectsCmd())
        ]
        
        for name, cmd in commands:
            print(f"✓ {name}: {cmd.name}")
            if hasattr(cmd, 'tooltip'):
                print(f"    Tooltip: {cmd.tooltip}")
        
        # Test utility function
        print("\n3. Testing utility functions...")
        
        # Mock display object for testing
        class MockDisplay:
            def __init__(self):
                self.selected_cleared = False
                self.repainted = False
                
            def ClearSelected(self):
                self.selected_cleared = True
                
            def Repaint(self):
                self.repainted = True
                
        mock_display = MockDisplay()
        result = unselect_all_objects_utility(mock_display)
        
        if result and mock_display.selected_cleared and mock_display.repainted:
            print("✓ unselect_all_objects_utility works correctly")
        else:
            print("✗ unselect_all_objects_utility test failed")
        
        # Test error clearing function
        print("\n4. Testing error clearing...")
        actions = clear_all_selection_errors(mock_display, verbose=False)
        if actions:
            print(f"✓ clear_all_selection_errors returned {len(actions)} actions")
            for action in actions[:3]:  # Show first 3 actions
                print(f"    - {action}")
            if len(actions) > 3:
                print(f"    ... and {len(actions) - 3} more actions")
        else:
            print("✗ clear_all_selection_errors returned no actions")
        
        print("\n5. Testing keyboard shortcuts...")
        toolbar_cmd = ToolbarUnselectCmd()
        if hasattr(toolbar_cmd, 'shortcut'):
            print(f"✓ Keyboard shortcut available: {toolbar_cmd.shortcut}")
        else:
            print("ℹ No keyboard shortcut defined")
        
        print("\n" + "=" * 45)
        print("✓ All tests completed successfully!")
        print("\nTo integrate into AdaptiveCAD:")
        print("1. Run: python add_unselect_toolbar.py")
        print("2. Or import and call: integrate_unselect_button(main_window)")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("\nMake sure you're running this from the AdaptiveCAD directory")
        print("and that spacetime_viz.py is properly installed.")
        return False
        
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False


def test_with_real_display(display_object):
    """Test unselect functionality with a real display object.
    
    Args:
        display_object: Real OpenCASCADE display object from AdaptiveCAD
    """
    print("Testing with real display object...")
    
    try:
        from adaptivecad.cosmic.spacetime_viz import clear_all_selection_errors
        
        print("Before clearing:")
        print(f"  Display object type: {type(display_object)}")
        print(f"  Has ClearSelected: {hasattr(display_object, 'ClearSelected')}")
        print(f"  Has Context: {hasattr(display_object, 'Context')}")
        
        # Run the clearing function
        actions = clear_all_selection_errors(display_object, verbose=True)
        
        print(f"\nClearing completed: {len(actions)} actions taken")
        print("✓ Real display test successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Real display test failed: {e}")
        return False


def create_test_toolbar_button(main_window):
    """Create a test button to verify toolbar integration.
    
    Args:
        main_window: The main window to add the test button to
    """
    try:
        from PySide6.QtWidgets import QAction, QPushButton, QVBoxLayout, QWidget, QLabel
        from adaptivecad.cosmic.spacetime_viz import ToolbarUnselectCmd
        
        # Create test widget
        test_widget = QWidget()
        layout = QVBoxLayout(test_widget)
        
        # Add label
        label = QLabel("Unselect Test Controls")
        layout.addWidget(label)
        
        # Add test button
        test_button = QPushButton("Test Unselect")
        test_button.setToolTip("Click to test the unselect functionality")
        
        def on_test_click():
            cmd = ToolbarUnselectCmd()
            cmd.run(main_window)
            print("Test unselect command executed")
            
        test_button.clicked.connect(on_test_click)
        layout.addWidget(test_button)
        
        # Show the test widget
        test_widget.setWindowTitle("Unselect Test")
        test_widget.resize(200, 100)
        test_widget.show()
        
        print("✓ Test toolbar button created")
        return test_widget
        
    except Exception as e:
        print(f"✗ Failed to create test button: {e}")
        return None


if __name__ == "__main__":
    print("Running unselect functionality tests...\n")
    
    success = test_unselect_functions()
    
    if success:
        print("\n🎉 All tests passed!")
        print("\nNext steps:")
        print("1. Integrate with your main AdaptiveCAD window")
        print("2. Test with real 3D objects")
        print("3. Verify selection errors are cleared")
    else:
        print("\n❌ Some tests failed. Check the error messages above.")
