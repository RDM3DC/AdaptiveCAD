#!/usr/bin/env python3
"""
Integration script to add unselect button to AdaptiveCAD toolbar.

Run this script or import it to add the unselect functionality to your main window.
"""

def integrate_unselect_button(main_window):
    """Add unselect button to the main AdaptiveCAD window.
    
    Args:
        main_window: The main AdaptiveCAD window object
        
    Returns:
        bool: True if integration was successful
    """
    try:
        # Import our unselect functions
        from adaptivecad.cosmic.spacetime_viz import (
            add_unselect_toolbar_button,
            register_unselect_toolbar_commands,
            ToolbarUnselectCmd,
            ErrorClearingUnselectCmd
        )
        
        print("Integrating unselect functionality...")
        
        # Register commands
        commands_registered = register_unselect_toolbar_commands()
        if commands_registered:
            print("✓ Unselect commands registered successfully")
        else:
            print("⚠ Warning: Command registration failed, using fallback")
        
        # Add toolbar button
        button_added = add_unselect_toolbar_button(main_window)
        if button_added:
            print("✓ Unselect button added to toolbar")
            print("  - Button location: Main toolbar")
            print("  - Keyboard shortcut: Ctrl+D")
            print("  - Menu location: Edit > Unselect All")
        else:
            print("✗ Failed to add toolbar button")
            return False
        
        # Test the functionality
        try:
            test_cmd = ToolbarUnselectCmd()
            print("✓ Unselect commands are ready to use")
            print("\nAvailable unselect commands:")
            print("  - ToolbarUnselectCmd: Main toolbar command")
            print("  - QuickUnselectCmd: Fast unselect without feedback")
            print("  - ErrorClearingUnselectCmd: Advanced error clearing")
            
        except Exception as e:
            print(f"⚠ Warning: Command test failed: {e}")
        
        print("\nIntegration complete! Use Ctrl+D or the toolbar button to unselect all objects.")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure spacetime_viz.py is in the correct location.")
        return False
    except Exception as e:
        print(f"✗ Integration error: {e}")
        return False


def create_unselect_menu_action(main_window):
    """Create a standalone menu action for unselect functionality.
    
    Args:
        main_window: The main window object
        
    Returns:
        QAction: The created action, or None if failed
    """
    try:
        from PySide6.QtWidgets import QAction
        from PySide6.QtGui import QKeySequence
        from adaptivecad.cosmic.spacetime_viz import ToolbarUnselectCmd
        
        # Create action
        action = QAction("Unselect All Objects", main_window)
        action.setShortcut(QKeySequence("Ctrl+D"))
        action.setStatusTip("Clear all object selections and remove selection errors")
        
        # Connect to command
        def execute_unselect():
            cmd = ToolbarUnselectCmd()
            cmd.run(main_window)
            
        action.triggered.connect(execute_unselect)
        
        return action
        
    except Exception as e:
        print(f"Error creating menu action: {e}")
        return None


def quick_integrate(main_window):
    """Quick integration - just add the essential unselect functionality.
    
    Args:
        main_window: The main window object
    """
    try:
        from adaptivecad.cosmic.spacetime_viz import clear_all_selection_errors
        
        def quick_unselect():
            """Quick unselect function."""
            try:
                if hasattr(main_window, 'view') and hasattr(main_window.view, '_display'):
                    clear_all_selection_errors(main_window.view._display)
                    print("All objects unselected")
                else:
                    print("No display available")
            except Exception as e:
                print(f"Unselect error: {e}")
        
        # Add as a method to the main window
        main_window.unselect_all = quick_unselect
        
        print("Quick unselect integration complete!")
        print("Usage: main_window.unselect_all()")
        
        return True
        
    except Exception as e:
        print(f"Quick integration failed: {e}")
        return False


if __name__ == "__main__":
    print("AdaptiveCAD Unselect Toolbar Integration")
    print("=" * 40)
    print()
    print("This script adds unselect functionality to AdaptiveCAD.")
    print()
    print("To use:")
    print("1. Import this module in your main application")
    print("2. Call integrate_unselect_button(your_main_window)")
    print()
    print("Example:")
    print("  from add_unselect_toolbar import integrate_unselect_button")
    print("  integrate_unselect_button(main_window)")
    print()
    print("Features added:")
    print("  • Toolbar button for unselecting all objects")
    print("  • Keyboard shortcut (Ctrl+D)")
    print("  • Menu item in Edit menu")
    print("  • Advanced error clearing for selection artifacts")
    print("  • Multiple unselect modes (quick, verbose, error-clearing)")
