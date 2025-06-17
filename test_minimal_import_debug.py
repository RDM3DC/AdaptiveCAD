#!/usr/bin/env python3
"""
Test script to debug the minimal import thread in isolation.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from adaptivecad.commands.minimal_import import MinimalImportThread

def test_minimal_import_thread():
    """Test the minimal import thread with detailed logging."""
      # Use test_cube.stl if it exists
    test_file = "test_cube.stl"
    if not os.path.exists(test_file):
        print(f"Test file {test_file} not found, skipping test")
        return
        
    print(f"Testing minimal import with: {test_file}")
    
    # Create the thread
    thread = MinimalImportThread(test_file)
    
    # Connect signals to track progress
    def on_progress(msg):
        print(f"PROGRESS: {msg}")
        
    def on_error(msg):
        print(f"ERROR: {msg}")
        
    def on_complete(shape, face_count):
        print(f"COMPLETE: shape={shape}, faces={face_count}")
        print(f"Shape type: {type(shape)}")
        if hasattr(shape, 'IsNull'):
            print(f"Shape is null: {shape.IsNull()}")
        app.quit()
        
    def on_shape_loaded(shape):
        print(f"SHAPE_LOADED: {shape}")
        print(f"Shape type: {type(shape)}")
        if hasattr(shape, 'IsNull'):
            print(f"Shape is null: {shape.IsNull()}")
        
    thread.progress_update.connect(on_progress)
    thread.error_occurred.connect(on_error)
    thread.import_complete.connect(on_complete)
    thread.shape_loaded.connect(on_shape_loaded)
    
    # Start the thread
    print("Starting thread...")
    thread.start()
    
    # Set a timeout
    def timeout():
        print("TIMEOUT: Thread did not complete in 30 seconds")
        thread.requestInterruption()
        app.quit()
        
    QTimer.singleShot(30000, timeout)  # 30 second timeout

if __name__ == "__main__":
    app = QApplication(sys.argv)
    test_minimal_import_thread()
    app.exec()
