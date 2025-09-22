#!/usr/bin/env python3
"""Enhanced launcher for AdaptiveCAD playground with improved error handling and environment detection."""

import sys
import os
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

def check_display_available():
    """Check if we have a display available."""
    if os.environ.get('DISPLAY'):
        return True
    if os.name == 'nt':  # Windows
        return True
    return False

def check_dependencies():
    """Check if required dependencies are available."""
    missing_deps = []
    
    try:
        import numpy
        log.info("✓ numpy available")
    except ImportError:
        missing_deps.append("numpy")
    
    try:
        import PySide6
        log.info("✓ PySide6 available")
    except ImportError:
        missing_deps.append("pyside6")
    
    try:
        from OCC.Display import backend
        log.info("✓ OCC.Display available")
    except ImportError:
        log.info("! OCC.Display not available (optional)")
    
    return missing_deps

def run_playground_with_environment():
    """Run the playground with appropriate environment settings."""
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        log.error(f"Missing dependencies: {', '.join(missing_deps)}")
        log.info("Install with: pip install " + " ".join(missing_deps))
        return 1
    
    # Determine Qt platform
    display_available = check_display_available()
    qt_platform = os.environ.get('QT_QPA_PLATFORM')
    
    if not display_available and not qt_platform:
        log.info("No display detected, using offscreen platform")
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    elif display_available:
        log.info("Display available, using default platform")
    
    try:
        log.info("Starting AdaptiveCAD Playground...")
        
        # Import and run the playground
        from adaptivecad.gui.playground import MainWindow
        
        # Create main window
        mw = MainWindow()
        log.info("MainWindow created successfully")
        
        if not display_available:
            log.info("Running in headless mode - GUI will not be visible")
            # In headless mode, just demonstrate that it works
            log.info("Playground initialized successfully!")
            log.info("GUI features available:")
            log.info(f"  - Main window: {hasattr(mw, 'win')}")
            log.info(f"  - 3D viewer: {hasattr(mw, 'view')}")  
            log.info(f"  - App instance: {hasattr(mw, 'app')}")
            log.info("To see the actual GUI, run on a system with a display.")
            return 0
        else:
            # Run the actual GUI
            return mw.run()
            
    except Exception as e:
        log.error(f"Failed to start playground: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main entry point."""
    print("=" * 60)
    print("AdaptiveCAD Playground Enhanced Launcher")
    print("=" * 60)
    
    try:
        return run_playground_with_environment()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        return 1
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())