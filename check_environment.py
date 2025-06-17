# Check environment configuration for AdaptiveCAD
# This script helps diagnose conda environment issues

import sys
import platform
import os
import subprocess
from pathlib import Path

def green(text):
    """Print text in green color"""
    return f"\033[92m{text}\033[0m"

def red(text):
    """Print text in red color"""
    return f"\033[91m{text}\033[0m"

def yellow(text):
    """Print text in yellow color"""
    return f"\033[93m{text}\033[0m"

print(f"{'=' * 50}")
print(f"{green('AdaptiveCAD Environment Diagnostic Tool')}")
print(f"{'=' * 50}")
print()

# 1. Python Version
print(f"Python Version: {green(platform.python_version())}")
print(f"Python Executable: {green(sys.executable)}")
print(f"Python Path: {green(Path(sys.executable).parent)}")

# 2. Check if we're in the conda environment
conda_env = os.environ.get("CONDA_DEFAULT_ENV")
if conda_env:
    print(f"Conda Environment: {green(conda_env)}")
else:
    print(f"Conda Environment: {red('Not detected!')}")

# 3. Check if the adaptivecad package is installed
try:
    import adaptivecad
    print(f"AdaptiveCAD Package: {green('Installed')}")
    print(f"    Location: {green(Path(adaptivecad.__file__).parent)}")
except ImportError:
    print(f"AdaptiveCAD Package: {red('Not installed or not in Python path')}")

# 4. Check required dependencies
dependencies = [
    "numpy",
    "pyside6",
    "pythonocc-core"
]

print("\nChecking dependencies:")
for dep in dependencies:
    try:
        module = __import__(dep)
        if hasattr(module, "__version__"):
            version = module.__version__
        elif hasattr(module, "VERSION"):
            version = module.VERSION
        elif hasattr(module, "version"):
            version = module.version
        else:
            version = "Unknown version"
        
        module_file = getattr(module, "__file__", "Unknown location")
        print(f"  ✓ {dep}: {green(f'Installed - {version}')}")
        print(f"      Location: {Path(module_file).parent}")
    except ImportError:
        print(f"  ✗ {dep}: {red('Not installed')}")

# 5. Check if we can import the required modules
print("\nChecking critical modules:")
try:
    from adaptivecad.gui import playground
    print(f"  ✓ adaptivecad.gui.playground: {green('Available')}")
except ImportError as e:
    print(f"  ✗ adaptivecad.gui.playground: {red(f'Not available - {e}')}")

try:
    from adaptivecad.commands.import_conformal import ImportConformalCmd
    print(f"  ✓ adaptivecad.commands.import_conformal: {green('Available')}")
except ImportError as e:
    print(f"  ✗ adaptivecad.commands.import_conformal: {red(f'Not available - {e}')}")

# 6. Provide recommendations
print("\nRecommendations:")
if conda_env != "adaptivecad":
    print(f"{yellow('- You are not in the adaptivecad conda environment.')}")
    print(f"{yellow('  Activate it with: conda activate adaptivecad')}")

missing_deps = []
for dep in dependencies:
    try:
        __import__(dep)
    except ImportError:
        missing_deps.append(dep)

if missing_deps:
    deps_str = " ".join(missing_deps)
    print(f"{yellow(f'- Missing dependencies: {deps_str}')}")
    print(f"{yellow(f'  Install them with: conda install -y -c conda-forge {deps_str}')}")

print(f"\n{green('Diagnostic complete.')}")
