#!/usr/bin/env python
# Simple launcher for AdaptiveCAD playground

import sys
import os

# Add the project directory to the path if needed
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import and run the playground module
from adaptivecad.gui.playground import MainWindow

if __name__ == "__main__":
    app = MainWindow(None)
    app.run()
