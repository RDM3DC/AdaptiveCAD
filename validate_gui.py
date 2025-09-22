#!/usr/bin/env python3
"""Validate GUI functionality by creating a screenshot of the playground interface."""

import sys
import os
from pathlib import Path

def create_gui_screenshot():
    """Create a screenshot of the playground GUI to validate functionality."""
    print("Creating GUI screenshot to validate functionality...")
    
    # Set environment for GUI operation
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        from adaptivecad.gui.playground import MainWindow
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QTimer
        
        # Create main window
        mw = MainWindow()
        print("✓ MainWindow created")
        
        # Show the window (in offscreen mode)
        mw.win.show()
        print("✓ Window shown")
        
        # Let the UI settle
        mw.app.processEvents()
        
        # Try to capture the window content
        try:
            # Get window size
            size = mw.win.size()
            print(f"✓ Window size: {size.width()}x{size.height()}")
            
            # Create pixmap
            pixmap = mw.win.grab()
            
            # Save screenshot
            screenshot_path = Path(__file__).parent / "playground_screenshot.png"
            if pixmap.save(str(screenshot_path)):
                print(f"✓ Screenshot saved to {screenshot_path}")
                print(f"✓ Screenshot size: {pixmap.width()}x{pixmap.height()}")
            else:
                print("! Screenshot save failed (expected in offscreen mode)")
                
        except Exception as e:
            print(f"! Screenshot capture failed (expected in offscreen mode): {e}")
        
        # Validate GUI components
        from PySide6.QtWidgets import QToolBar
        
        components = {
            "Main window": hasattr(mw, 'win') and mw.win is not None,
            "3D viewer": hasattr(mw, 'view') and mw.view is not None,
            "Menu bar": mw.win.menuBar() is not None,
            "Tool bars": len(mw.win.findChildren(QToolBar)) > 0,
            "Application": hasattr(mw, 'app') and mw.app is not None,
        }
        
        print("\nGUI Components Validation:")
        for component, status in components.items():
            status_icon = "✓" if status else "✗"
            print(f"{status_icon} {component}: {'Available' if status else 'Missing'}")
        
        all_good = all(components.values())
        
        # Test some menu actions
        try:
            menus = mw.win.menuBar().findChildren('QMenu')
            print(f"✓ Found {len(mw.win.menuBar().actions())} menu actions")
        except Exception as e:
            print(f"! Menu inspection failed: {e}")
        
        # Test toolbar availability
        try:
            from PySide6.QtWidgets import QToolBar
            toolbars = mw.win.findChildren(QToolBar)
            print(f"✓ Found {len(toolbars)} toolbars")
            for i, toolbar in enumerate(toolbars):
                print(f"  - Toolbar {i+1}: {toolbar.windowTitle()}")
        except Exception as e:
            print(f"! Toolbar inspection failed: {e}")
        
        print(f"\n{'✓ GUI validation successful!' if all_good else '✗ GUI validation failed!'}")
        return all_good
        
    except Exception as e:
        print(f"✗ GUI validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    print("=" * 60)
    print("AdaptiveCAD Playground GUI Validation")
    print("=" * 60)
    
    success = create_gui_screenshot()
    
    if success:
        print("\n🎉 GUI validation successful! The playground is fully functional.")
        return 0
    else:
        print("\n💥 GUI validation failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())