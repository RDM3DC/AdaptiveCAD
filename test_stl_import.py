"""Test script to verify the import functionality."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path if needed
project_root = Path(__file__).parent.absolute()
print(f"Project root: {project_root}")

try:
    print("Attempting to import adaptivecad...")
    import adaptivecad
    print("Successfully imported adaptivecad")
except ImportError as e:
    print(f"Error importing adaptivecad: {e}")
    print("Try running this script with the correct conda environment activated:")
    print("    conda activate adaptivecad")
    sys.exit(1)

# Test importing the required modules
try:
    from adaptivecad.gui import playground
    from adaptivecad.commands.import_conformal import ImportConformalCmd
    print("Successfully imported required modules")
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

# Create a simple STL file if needed for testing
def create_test_stl():
    try:
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.StlAPI import StlAPI_Writer
        
        test_stl_path = os.path.join(project_root, "test_cube.stl")
        box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
        writer = StlAPI_Writer()
        writer.Write(box, test_stl_path)
        print(f"Created test STL file at {test_stl_path}")
        return test_stl_path
    except Exception as e:
        print(f"Error creating test STL: {e}")
        return None

# Directly test the import functionality
def test_import():
    stl_path = create_test_stl()
    if not stl_path:
        print("Skipping import test as test STL couldn't be created")
        return
    
    try:
        print("\nTesting import functionality directly...")
        cmd = ImportConformalCmd()
        print("Created ImportConformalCmd instance successfully")
        
        # Load window to test the GUI interaction
        print("\nStarting playground window...")
        window = playground.MainWindow()
        print("Created MainWindow")
        window._build_demo()
        print("Built demo scene")
        window.win.show()
        print("Showing window - you can now click the Debug Import button")
        print("or use the Import πₐ button in the toolbar")
        window.app.exec()
        
    except Exception as e:
        import traceback
        print(f"Error testing import: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    test_import()
