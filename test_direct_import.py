#!/usr/bin/env python3
"""
Simple test of the minimal import thread functionality without Qt GUI.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

def test_direct_import():
    """Test the import function directly without threading."""
    
    try:
        from adaptivecad.commands.minimal_import import MinimalImportThread
        
        # Use test_cube.stl
        test_file = "test_cube.stl"
        if not os.path.exists(test_file):
            print(f"Test file {test_file} not found")
            return
            
        print(f"Testing direct import with: {test_file}")
        
        # Create the thread object but don't start it as a thread
        thread = MinimalImportThread(test_file)
        
        # Call the import function directly
        print("Calling _import_shape directly...")
        shape = thread._import_shape(test_file)
        
        print(f"Result: {shape}")
        if shape is not None:
            print(f"Shape type: {type(shape)}")
            if hasattr(shape, 'IsNull'):
                print(f"Shape is null: {shape.IsNull()}")
                if not shape.IsNull():
                    print("SUCCESS: Shape imported and is valid!")
                else:
                    print("ERROR: Shape is null")
            else:
                print("SUCCESS: Shape imported!")
        else:
            print("ERROR: Import returned None")
            
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_import()
