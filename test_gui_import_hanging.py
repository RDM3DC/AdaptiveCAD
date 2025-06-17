#!/usr/bin/env python3
"""Test script to reproduce the GUI import hanging issue."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_gui_import():
    """Test the GUI import functionality to see if it hangs."""
    try:
        print("Testing GUI import functionality...")
        
        # Test if we can import the GUI modules
        print("1. Testing GUI module imports...")
        try:
            import PySide6
            from OCC.Display import backend
            backend.load_backend('pyside6')
            print("   ✓ PySide6 and OCC backend loaded")
        except Exception as e:
            print(f"   ✗ GUI dependencies failed: {e}")
            return False
        
        # Test importing the playground module
        print("2. Testing playground module import...")
        try:
            from adaptivecad.gui.playground import MainWindow, HAS_GUI
            print(f"   ✓ Playground module imported, HAS_GUI={HAS_GUI}")
        except Exception as e:
            print(f"   ✗ Playground import failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test importing the ImportConformalCmd
        print("3. Testing ImportConformalCmd import...")
        try:
            from adaptivecad.commands.import_conformal import ImportConformalCmd
            print("   ✓ ImportConformalCmd imported")
        except Exception as e:
            print(f"   ✗ ImportConformalCmd import failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        # Test creating the command object
        print("4. Testing command object creation...")
        try:
            cmd = ImportConformalCmd()
            print("   ✓ ImportConformalCmd instance created")
        except Exception as e:
            print(f"   ✗ Command creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        print("✓ All GUI import tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_thread_safety():
    """Test for potential threading issues."""
    try:
        print("\nTesting threading safety...")
        
        from adaptivecad.commands.import_conformal import ImportThread
        from PySide6.QtCore import QCoreApplication
        
        # Create a minimal QApplication for the thread
        app = QCoreApplication.instance() or QCoreApplication([])
        
        print("1. Testing ImportThread creation...")
        thread = ImportThread("test_file.stl", 1.0, 1)
        print("   ✓ ImportThread created")
        
        print("2. Testing thread cleanup...")
        if hasattr(thread, 'deleteLater'):
            thread.deleteLater()
        print("   ✓ Thread cleanup complete")
        
        return True
        
    except Exception as e:
        print(f"✗ Threading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== AdaptiveCAD GUI Import Test ===")
    
    success = True
    success &= test_gui_import()
    success &= test_thread_safety()
    
    if success:
        print("\n🎉 All GUI tests passed! The issue may be in the interaction between components.")
    else:
        print("\n💥 Some tests failed. Check the errors above.")
        sys.exit(1)
