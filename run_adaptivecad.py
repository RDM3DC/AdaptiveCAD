#!/usr/bin/env python
"""Launch AdaptiveCAD - The Triangle-Free CAD System.

Usage:
    python run_adaptivecad.py
    
Or from command line:
    cd AdaptiveCAD
    python -m adaptivecad.app
"""

import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s]: %(message)s"
)

def main():
    """Main entry point."""
    try:
        from adaptivecad.app import launch_app
        return launch_app()
    except ImportError as e:
        print(f"Import error: {e}")
        print("\nTrying alternative launch method...")
        
        # Fallback to direct import
        try:
            from adaptivecad.app.main_window import launch_app
            return launch_app()
        except ImportError as e2:
            print(f"Failed to import: {e2}")
            print("\nMake sure you're in the AdaptiveCAD directory and have installed dependencies.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
