#!/usr/bin/env python3
"""
Simple test to check module imports.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Testing module imports...")

try:
    print("Importing OCC...")
    from OCC.Core.StlAPI import StlAPI_Reader
    from OCC.Core.TopoDS import TopoDS_Shape
    print("OCC import successful")
    
    print("Testing STL reader...")
    reader = StlAPI_Reader()
    shape = TopoDS_Shape()
    print("STL reader created successfully")
    
    print("Testing file existence...")
    test_file = "test_cube.stl"
    if os.path.exists(test_file):
        print(f"File {test_file} exists")
        
        print("Attempting to read STL...")
        success = reader.Read(shape, test_file)
        print(f"Read result: {success}")
        print(f"Shape is null: {shape.IsNull()}")
        
        if not shape.IsNull():
            print("SUCCESS: STL loaded successfully!")
        else:
            print("ERROR: Shape is null after loading")
    else:
        print(f"File {test_file} not found")
        
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()

print("Test completed")
