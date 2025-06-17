"""Test script for the import functionality."""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Try to import the required modules
try:
    import numpy as np
    print("✓ NumPy is available")
except ImportError:
    print("✗ NumPy is not installed!")

try:
    from PySide6 import QtWidgets
    print("✓ PySide6 is available")
except ImportError:
    print("✗ PySide6 is not installed!")

try:
    from OCC.Core.TopoDS import TopoDS_Shape
    print("✓ PythonOCC is available")
except ImportError:
    print("✗ PythonOCC is not installed!")

print("\nTrying to import AdaptiveCAD modules...")

try:
    from adaptivecad import settings
    print("✓ adaptivecad.settings imported")
except ImportError as e:
    print(f"✗ Failed to import adaptivecad.settings: {e}")

try:
    from adaptivecad.geom import pi_a_over_pi
    print("✓ adaptivecad.geom.pi_a_over_pi function imported")
except ImportError as e:
    print(f"✗ Failed to import pi_a_over_pi: {e}")

try:
    from adaptivecad.command_defs import BaseCmd, DOCUMENT, Feature, rebuild_scene
    print("✓ adaptivecad.command_defs imported")
except ImportError as e:
    print(f"✗ Failed to import from command_defs: {e}")

print("\nChecking import_conformal module...")
try:
    from adaptivecad.commands.import_conformal import ImportConformalCmd
    print("✓ ImportConformalCmd imported successfully")
    
    # Test creating an instance
    cmd = ImportConformalCmd()
    print("✓ ImportConformalCmd instance created")
    print(f"Title: {cmd.title}")
    
except ImportError as e:
    print(f"✗ Failed to import ImportConformalCmd: {e}")
except Exception as e:
    print(f"✗ Error when working with ImportConformalCmd: {e}")

print("\nTest complete")
