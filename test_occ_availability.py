# Test OpenCascade availability in AdaptiveCAD
print("Testing OpenCascade (pythonocc-core) availability...")

# Test OCC imports
try:
    from OCC.Core.gp import gp_Pnt
    print("✅ OCC.Core.gp imported successfully")
except ImportError as e:
    print(f"❌ OCC.Core.gp import error: {e}")

try:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    print("✅ OCC.Core.BRepBuilderAPI imported successfully")
except ImportError as e:
    print(f"❌ OCC.Core.BRepBuilderAPI import error: {e}")
    
try:
    from OCC.Core.AIS import AIS_Shape
    print("✅ OCC.Core.AIS imported successfully")
except ImportError as e:
    print(f"❌ OCC.Core.AIS import error: {e}")
    
# Test AdaptiveCAD modules
print("\nTesting AdaptiveCAD modules...")

try:
    import adaptivecad
    print(f"✅ adaptivecad module imported successfully (version: {getattr(adaptivecad, '__version__', 'unknown')})")
except ImportError as e:
    print(f"❌ adaptivecad import error: {e}")
    
try:
    from adaptivecad.cosmic.curve_tools import HAS_OCC
    print(f"✅ adaptivecad.cosmic.curve_tools imported successfully")
    print(f"   HAS_OCC = {HAS_OCC}")
    
    # If HAS_OCC is False, check why
    if not HAS_OCC:
        # See how the module is detecting OCC
        import inspect
        import adaptivecad.cosmic.curve_tools as curve_tools
        try:
            print("\nRelevant code in curve_tools.py:")
            source_lines = inspect.getsourcelines(curve_tools)
            for i, line in enumerate(source_lines[0]):
                if "HAS_OCC" in line or "import OCC" in line or "from OCC" in line:
                    print(f"   Line {source_lines[1] + i}: {line.rstrip()}")
        except Exception as e:
            print(f"Could not inspect curve_tools.py: {e}")
        
except ImportError as e:
    print(f"❌ adaptivecad.cosmic.curve_tools import error: {e}")

# Print Python and environment info
import sys
import os

print("\nEnvironment Information:")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"CONDA_PREFIX: {os.environ.get('CONDA_PREFIX', 'Not set')}")
print(f"CONDA_DEFAULT_ENV: {os.environ.get('CONDA_DEFAULT_ENV', 'Not set')}")
