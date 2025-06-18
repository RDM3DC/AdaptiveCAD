#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
add_cosmic_commands.py - Adds the Cosmic Spacetime and Multiverse commands to AdaptiveCAD's toolbar.

This script integrates the spacetime visualization and multiverse exploration tools
into the main AdaptiveCAD interface for easy access.
"""

import os
import sys
import importlib
from pathlib import Path

# Add parent directory to path if needed
script_dir = Path(__file__).parent
parent_dir = script_dir.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


def add_cosmic_commands_to_toolbar(main_window):
    """Add cosmic commands to the AdaptiveCAD toolbar.
    
    Args:
        main_window: The AdaptiveCAD main window object
    
    Returns:
        bool: True if commands were added successfully, False otherwise
    """
    try:
        # First check if we can import the spacetime_viz module
        try:
            from adaptivecad.cosmic import spacetime_viz
            if not hasattr(spacetime_viz, 'SpacetimeVisualizationCmd'):
                print("Error: spacetime_viz module loaded but missing expected classes")
                return False
        except ImportError:
            print("Error: Could not import adaptivecad.cosmic.spacetime_viz")
            return False
        
        # Add spacetime visualization command
        try:
            spacetime_cmd = spacetime_viz.SpacetimeVisualizationCmd()
            if hasattr(main_window, 'add_command'):
                main_window.add_command(spacetime_cmd)
                print("✓ Added Spacetime Visualization command")
        except Exception as e:
            print(f"Error adding Spacetime Visualization: {e}")
        
        # Add light cone display box command
        try:
            lightcone_cmd = spacetime_viz.LightConeDisplayBoxCmd()
            if hasattr(main_window, 'add_command'):
                main_window.add_command(lightcone_cmd)
                print("✓ Added Light Cone Display Box command")
        except Exception as e:
            print(f"Error adding Light Cone Display Box: {e}")
        
        # Add unselect toolbar command
        try:
            unselect_cmd = spacetime_viz.ToolbarUnselectCmd()
            if hasattr(main_window, 'add_toolbar_command'):
                main_window.add_toolbar_command(unselect_cmd)
                print("✓ Added Unselect All toolbar command")
        except Exception as e:
            print(f"Error adding Unselect All command: {e}")
            
            # Fallback - try to add it as a regular command
            try:
                if hasattr(main_window, 'add_command'):
                    main_window.add_command(unselect_cmd)
                    print("  Added Unselect All as regular command (fallback)")
            except:
                pass
        
        # Add error-clearing unselect command
        try:
            error_clear_cmd = spacetime_viz.ErrorClearingUnselectCmd()
            if hasattr(main_window, 'add_command'):
                main_window.add_command(error_clear_cmd)
                print("✓ Added Clear Selection Errors command")
        except Exception as e:
            print(f"Error adding Clear Selection Errors command: {e}")
        
        # Add multiverse exploration command
        try:
            multiverse_cmd = spacetime_viz.MultiverseExplorationCmd()
            if hasattr(main_window, 'add_command'):
                main_window.add_command(multiverse_cmd)
                print("✓ Added Multiverse Exploration command")
        except Exception as e:
            print(f"Error adding Multiverse Exploration command: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error adding cosmic commands: {e}")
        return False


if __name__ == "__main__":
    print("This script is designed to be imported and used by AdaptiveCAD.")
    print("It adds cosmic exploration commands to the AdaptiveCAD toolbar.")
    print("\nTo add these commands manually, run:")
    print("   from adaptivecad.cosmic.add_cosmic_commands import add_cosmic_commands_to_toolbar")
    print("   add_cosmic_commands_to_toolbar(main_window)")
