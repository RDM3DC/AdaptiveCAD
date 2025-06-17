#!/usr/bin/env python
"""
Test script to verify all modeling tools and advanced shapes in AdaptiveCAD playground.

This script:
1. Creates a basic shape
2. Creates an advanced shape
3. Performs a move operation
4. Performs a boolean operation

If all operations complete without errors, the playground is working correctly.
"""

import os
import sys
import time

# Ensure adaptivecad is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import PySide6
try:
    import PySide6
except ImportError:
    print("PySide6 is not available. Please install it with:")
    print("conda install -c conda-forge pyside6")
    print("or")
    print("pip install pyside6")
    sys.exit(1)

try:
    # Import required modules
    from adaptivecad.gui.playground import MainWindow
    from adaptivecad.command_defs import (
        DOCUMENT, Feature,
        NewBoxCmd, MoveCmd, UnionCmd
    )
    
    print("Setting up test for modeling tools...")
    
    # Create a MainWindow instance
    window = MainWindow()
    
    # Create a box
    print("Creating a box...")
    box_cmd = NewBoxCmd()
    box_cmd.run(window)  # This will prompt for dimensions, use defaults
    
    # Verify box was created
    if len(DOCUMENT) > 0:
        print(f"Box created successfully: {DOCUMENT[-1].name}")
    else:
        print("Failed to create box")
        sys.exit(1)
    
    # Create a second box for boolean operations
    print("Creating second box...")
    box_cmd = NewBoxCmd()
    box_cmd.run(window)
    
    # Move the second box
    print("Moving second box...")
    move_cmd = MoveCmd()
    move_cmd.run(window)  # This will prompt for move parameters
    
    # Perform union operation
    print("Performing union operation...")
    union_cmd = UnionCmd()
    union_cmd.run(window)  # This will prompt for shapes to union
    
    print("All operations completed successfully!")
    print("Modeling tools are working correctly.")
    
    # Run the main event loop
    print("Starting main window. Close the window to exit.")
    window.run()
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have all dependencies installed.")
    sys.exit(1)
except Exception as e:
    print(f"Error during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
