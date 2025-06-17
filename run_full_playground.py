#!/usr/bin/env python
"""
Run the AdaptiveCAD Full Playground with all advanced shapes and modeling tools.
"""

import sys
import os

# Ensure adaptivecad is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from adaptivecad.gui.playground import main

    # Run the playground application
    print("Starting AdaptiveCAD Full Playground with advanced shapes and modeling tools...")
    main()
except ImportError as e:
    print(f"Error importing playground: {e}")
    print("Make sure you have all dependencies installed (run check_environment.py)")
    sys.exit(1)
except Exception as e:
    print(f"Error running playground: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
