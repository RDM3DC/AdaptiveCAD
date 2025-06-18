# Check OCC status in AdaptiveCAD
try:
    from adaptivecad.cosmic.curve_tools import HAS_OCC
    print(f"HAS_OCC = {HAS_OCC}")
    
    # If HAS_OCC is False, try to identify why
    if not HAS_OCC:
        print("Debugging why HAS_OCC is False:")
        try:
            from OCC.Core.gp import gp_Pnt
            print("  - OCC.Core.gp can be imported")
        except ImportError as e:
            print(f"  - OCC.Core.gp import error: {e}")
        
        try:
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            print("  - OCC.Core.BRepBuilderAPI can be imported")
        except ImportError as e:
            print(f"  - OCC.Core.BRepBuilderAPI import error: {e}")
            
        try:
            from OCC.Core.AIS import AIS_Shape
            print("  - OCC.Core.AIS can be imported")
        except ImportError as e:
            print(f"  - OCC.Core.AIS import error: {e}")
    else:
        print("OpenCascade (pythonocc-core) detected successfully!")
except Exception as e:
    print(f"Error accessing curve_tools module: {e}")
    
# Check Python path
import sys
print("\nPython Path:")
for path in sys.path:
    print(f"  - {path}")

# Check conda environment
import os
print("\nConda Environment:")
print(f"  - CONDA_PREFIX: {os.environ.get('CONDA_PREFIX', 'Not set')}")
print(f"  - CONDA_DEFAULT_ENV: {os.environ.get('CONDA_DEFAULT_ENV', 'Not set')}")
