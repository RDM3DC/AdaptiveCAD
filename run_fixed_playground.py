#!/usr/bin/env python

"""
Run the fixed AdaptiveCAD GUI playground.
This script has been updated to use the new version with advanced shapes.
For the most complete experience, use run_advanced_playground.py instead.
"""

import sys
import os

# Add the repository root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

print("\n=== AdaptiveCAD Fixed Playground ===")
print("The playground now includes all advanced shapes.")
print("Check out ADVANCED_SHAPES.md for documentation.")
print("===========================\n")

# Import and run the playground
from adaptivecad.gui.playground import MainWindow

if __name__ == "__main__":
    print("Starting AdaptiveCAD GUI...")
    app = MainWindow()
    sys.exit(app.run())
