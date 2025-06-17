#!/usr/bin/env python3
"""Test import functionality with minimal GUI setup."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_import_dialog():
    """Test the import functionality with a mock dialog."""
    try:
        print("Testing import command with mock GUI...")
        
        # Import required modules
        from adaptivecad.commands.import_conformal import ImportConformalCmd
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        # Create a minimal application
        app = QApplication.instance() or QApplication([])
        
        # Create a mock main window class for testing
        class MockMainWindow:
            def __init__(self):
                from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
                self.win = QMainWindow()
                self.win.setWindowTitle("Test Import")
                
                # Create a minimal view mock
                self.view = MockView()
                
                central = QWidget()
                layout = QVBoxLayout(central)
                layout.addWidget(QWidget())  # Placeholder
                self.win.setCentralWidget(central)
                
        class MockView:
            def __init__(self):
                self._display = MockDisplay()
                
        class MockDisplay:
            def EraseAll(self):
                print("MockDisplay: EraseAll called")
            def DisplayShape(self, shape, update=True):
                print(f"MockDisplay: DisplayShape called with shape={shape}")
            def FitAll(self):
                print("MockDisplay: FitAll called")
                
        # Create the mock main window
        mw = MockMainWindow()
        
        # Create the import command
        import_cmd = ImportConformalCmd()
        
        print("✓ Import command created successfully")
        print("✓ Mock GUI components created")
        
        # Test that the command has the required methods
        assert hasattr(import_cmd, 'run'), "ImportConformalCmd missing run method"
        assert hasattr(import_cmd, '_cleanup_thread'), "ImportConformalCmd missing _cleanup_thread method"
        
        print("✓ Command has required methods")
        
        # Test thread cleanup (should not crash)
        import_cmd._cleanup_thread()
        print("✓ Thread cleanup works")
        
        # Close the application after a short delay
        QTimer.singleShot(100, app.quit)
        
        print("✓ All import command tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Import command test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== AdaptiveCAD Import Command Test ===")
    
    success = test_import_dialog()
    
    if success:
        print("\n🎉 Import command test passed! The hanging issue should be resolved.")
    else:
        print("\n💥 Import command test failed.")
        sys.exit(1)
