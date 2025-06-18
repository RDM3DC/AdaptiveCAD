"""
Test script to verify OpenCascade (OCC) detection in AdaptiveCAD.
This script checks if OCC is properly detected in the cosmic/curve_tools module.
"""

# First, ensure we can import the curve_tools module
try:
    # This will attempt imports and set HAS_OCC
    from adaptivecad.cosmic import curve_tools
    print(f"Imported curve_tools module successfully")
    print(f"curve_tools.HAS_OCC = {curve_tools.HAS_OCC}")
    
    if curve_tools.HAS_OCC:
        print("OpenCascade detected successfully! You should be able to create shapes.")
    else:
        print("OpenCascade NOT detected. Checking why...")
        
        # Try direct OCC imports to verify
        try:
            from OCC.Core.gp import gp_Pnt
            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
            print("Interesting: Direct OCC imports work, but curve_tools.HAS_OCC is False!")
            print("This suggests an issue with the import detection in curve_tools.py")
        except ImportError as e:
            print(f"Confirmed: OCC imports fail with error: {e}")
            print("Please ensure pythonocc-core is installed in the active Python environment")
except Exception as e:
    print(f"Error importing curve_tools: {e}")
    
# Check Python environment
import sys
print(f"\nPython executable: {sys.executable}")
print(f"Python version: {sys.version}")

# Check for OCC in sys.modules
if any('OCC' in module for module in sys.modules):
    print("OCC modules found in sys.modules:")
    for module in sys.modules:
        if 'OCC' in module:
            print(f"  - {module}")
else:
    print("No OCC modules found in sys.modules")

# Try to create a BizarreCurve to test
try:
    from adaptivecad.cosmic.curve_tools import BizarreCurveFeature
    curve = BizarreCurveFeature(20.0, 50.0, 2.0, 1.0, 100)
    print(f"\nCreated BizarreCurveFeature with shape: {curve.shape}")
    if curve.shape is None:
        print("Shape is None - this indicates OCC is not properly detected or available")
    else:
        print("Shape successfully created!")
except Exception as e:
    print(f"Error creating BizarreCurve: {e}")
