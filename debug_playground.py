#!/usr/bin/env python
# Debug launcher for AdaptiveCAD playground

import sys
import os
import traceback

# Configure logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='playground_debug.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

# Add the project directory to the path if needed
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    logger.debug("Starting import of MainWindow")
    # Import and run the playground module
    from adaptivecad.gui.playground import MainWindow
    logger.debug("Successfully imported MainWindow")

    if __name__ == "__main__":
        logger.debug("Creating MainWindow instance")
        app = MainWindow(None)
        logger.debug("Created MainWindow instance, running app")
        app.run()
except Exception as e:
    logger.error(f"Error: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"Error: {str(e)}")
    print(traceback.format_exc())
