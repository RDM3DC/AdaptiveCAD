#!/usr/bin/env python

"""
Run the enhanced AdaptiveCAD GUI playground with all advanced shape features.
This script launches the fixed AdaptiveCAD GUI playground with the following:
- MainWindow properly defined at module level (fixes import errors)
- All advanced shape tools including:
  - Superellipse
  - Pi Curve Shell (πₐ)
  - Helix/Spiral
  - Tapered Cylinder
  - Capsule/Pill
  - Ellipsoid
"""

import sys
import os

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

print("\n=== AdaptiveCAD Advanced Shapes Playground ===")
print("Starting advanced shapes playground with:")
print("- Superellipse")
print("- Pi Curve Shell (πₐ)")
print("- Helix/Spiral")
print("- Tapered Cylinder")
print("- Capsule/Pill")
print("- Ellipsoid")
print("===========================\n")

# Now import and run the playground
from adaptivecad.gui.playground import MainWindow

if __name__ == "__main__":
    app = MainWindow()
    result = app.run()
    if result != 0:
        print(f"AdaptiveCAD GUI closed with error code: {result}")
    sys.exit(result)
