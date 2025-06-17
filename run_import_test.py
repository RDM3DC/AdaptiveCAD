# Run this script to test the import functionality with a proper conda environment
# First, activate the conda environment:
#    For PowerShell: .\activate_conda.ps1
#    For cmd: call start_adaptivecad.bat

# Make sure NumPy, PySide6 and PythonOCC are installed
import sys
import importlib.util

def check_module(module_name):
    """Check if a module is installed and print its status"""
    is_available = importlib.util.find_spec(module_name) is not None
    status = "✓" if is_available else "✗"
    status_msg = "available" if is_available else "NOT INSTALLED"
    print(f"{status} {module_name} is {status_msg}")
    return is_available

# Check required modules
print("Checking required modules:")
numpy_ok = check_module("numpy")
pyside_ok = check_module("PySide6")
occ_ok = check_module("OCC")

if not all([numpy_ok, pyside_ok, occ_ok]):
    print("\n⚠️ Some modules are missing. Please run:")
    print("    conda install -c conda-forge numpy pyside6 pythonocc-core")
    print("\nOr use the debug_import.bat script instead.")
    sys.exit(1)

# Import adaptivecad modules
print("\nImporting AdaptiveCAD modules:")
import adaptivecad
from adaptivecad.gui import playground
from adaptivecad.commands.import_conformal import ImportConformalCmd

# Create a test instance of the import command
print("\nTesting ImportConformalCmd:")
cmd = ImportConformalCmd()
print(f"Command title: {cmd.title}")

# Run the playground
print("\nStarting the playground:")
window = playground.MainWindow()
window._build_demo()
window.win.show()
window.app.exec()
