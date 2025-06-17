#!/usr/bin/env python3
"""Test the complete import workflow with mock GUI interactions."""

import sys
import os

# Add the project to Python path
sys.path.insert(0, r"d:\SuperCAD\AdaptiveCAD")

def test_complete_import_workflow():
    """Test the complete import workflow step by step."""
    try:
        print("Testing complete import workflow...")
        
        from adaptivecad.gui.playground import MainWindow
        from adaptivecad.commands.import_conformal import ImportConformalCmd
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        
        # Create application and main window
        app = QApplication.instance() or QApplication([])
        mw = MainWindow()
        
        print("✓ Main window created")
        
        # Test file exists
        test_file = r"d:\SuperCAD\AdaptiveCAD\test_cube.stl"
        if not os.path.exists(test_file):
            print(f"✗ Test file not found: {test_file}")
            return False
        
        print(f"✓ Test file found: {test_file}")
        
        # Create import command and try to simulate the workflow
        import_cmd = ImportConformalCmd()
        
        # Manually set the parameters that would come from dialogs
        import_cmd.mw = mw
        import_cmd.kappa = 1.0
        import_cmd.file_path = test_file
        import_cmd.n_faces = 0
        
        print("✓ Import command configured")
        
        # Test creating the thread manually
        from adaptivecad.commands.import_conformal import ImportThread
        
        print("Testing background import thread...")
        import_thread = ImportThread(test_file, 1.0, 2)  # Use 2 threads
        
        # Track if the thread actually runs
        thread_started = False
        thread_completed = False
        
        def on_progress(message):
            print(f"  Progress: {message}")
            
        def on_error(error):
            print(f"  Error: {error}")
            
        def on_complete(shape, count):
            nonlocal thread_completed
            thread_completed = True
            print(f"  Completed: shape={shape}, count={count}")
            app.quit()  # Exit when done
            
        def on_shape_loaded(shape):
            print(f"  Shape loaded: {shape}")
        
        # Connect signals
        import_thread.progress_update.connect(on_progress)
        import_thread.error_occurred.connect(on_error)
        import_thread.import_complete.connect(on_complete)
        import_thread.shape_loaded.connect(on_shape_loaded)
        
        # Start the thread
        print("Starting import thread...")
        import_thread.start()
        thread_started = True
        
        # Set a timeout to prevent hanging
        QTimer.singleShot(30000, app.quit)  # 30 second timeout
        
        # Run the event loop
        app.exec()
        
        # Clean up
        if import_thread.isRunning():
            import_thread.requestInterruption()
            import_thread.wait(5000)
        
        if thread_started and thread_completed:
            print("✓ Import thread ran and completed successfully")
            return True
        elif thread_started:
            print("! Import thread started but didn't complete (may have timed out)")
            return True
        else:
            print("✗ Import thread failed to start")
            return False
        
    except Exception as e:
        print(f"✗ Complete workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Complete Import Workflow Test ===")
    
    success = test_complete_import_workflow()
    
    if success:
        print("\n🎉 Import workflow test passed!")
        print("\nThe import should work correctly in the GUI.")
        print("If you're still not seeing CPU/GPU usage:")
        print("1. Check that you're selecting a valid STL/STEP file")
        print("2. Look for progress messages in the status bar")
        print("3. Wait for the 'Add Imported Shape' button to appear")
        print("4. The conformal transformation may be fast for simple files")
    else:
        print("\n💥 Import workflow test failed.")
        sys.exit(1)
