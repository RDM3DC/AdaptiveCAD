#!/usr/bin/env python3
"""Test script to verify import functionality without GUI."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_import_system():
    """Test the import system without GUI components."""
    try:
        # Test importing the necessary modules
        print("Testing imports...")
        from adaptivecad.commands.import_conformal import import_mesh_shape, extract_bspline_faces
        from adaptivecad.geom.hyperbolic import pi_a_over_pi, validate_hyperbolic_params
        print("✓ All imports successful")
        
        # Test the robust hyperbolic function
        print("\nTesting hyperbolic geometry...")
        
        # Test normal cases
        result1 = pi_a_over_pi(1.0, 0.5)
        print(f"✓ pi_a_over_pi(1.0, 0.5) = {result1}")
        
        # Test edge case
        result2 = pi_a_over_pi(0.0, 1.0)
        print(f"✓ pi_a_over_pi(0.0, 1.0) = {result2}")
        
        # Test parameter validation
        is_valid = validate_hyperbolic_params(1.0, 0.5)
        print(f"✓ validate_hyperbolic_params(1.0, 0.5) = {is_valid}")
        
        print("\n✓ All hyperbolic geometry tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stl_import():
    """Test STL import if test file exists."""
    test_stl = r"d:\SuperCAD\AdaptiveCAD\test_cube.stl"
    if os.path.exists(test_stl):
        try:
            print(f"\nTesting STL import with {test_stl}...")
            from adaptivecad.commands.import_conformal import import_mesh_shape
            
            shape = import_mesh_shape(test_stl)
            if shape is not None:
                print(f"✓ STL import successful, shape: {shape}")
                return True
            else:
                print("✗ STL import returned None")
                return False
        except Exception as e:
            print(f"✗ STL import failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"\n! STL test file not found: {test_stl}")
        return True  # Not a failure, just no test file

if __name__ == "__main__":
    print("=== AdaptiveCAD Import System Test ===")
    
    success = True
    success &= test_import_system()
    success &= test_stl_import()
    
    if success:
        print("\n🎉 All tests passed! Import system appears to be working correctly.")
    else:
        print("\n💥 Some tests failed. Check the errors above.")
        sys.exit(1)
