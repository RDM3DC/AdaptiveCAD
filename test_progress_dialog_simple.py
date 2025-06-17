"""
Simple test of the progress dialog alone.
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, r'd:\SuperCAD\AdaptiveCAD')

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    from PySide6.QtCore import QThread, Signal
    from adaptivecad.gui.import_progress_dialog import ImportProgressDialog
    import time
    
    print("✓ All imports successful")
    
    class DemoImportThread(QThread):
        """Demo thread that simulates an import process."""
        progress_update = Signal(str)
        error_occurred = Signal(str)
        import_complete = Signal(object, int)
        shape_loaded = Signal(object)
        
        def run(self):
            """Simulate import process with debug output."""
            try:
                print("[DemoThread] Starting demo import...")
                self.progress_update.emit("Starting demo import...")
                time.sleep(1)
                
                self.progress_update.emit("Loading file...")
                time.sleep(1)
                
                # Simulate shape loaded
                self.shape_loaded.emit("demo_shape")
                self.progress_update.emit("Shape loaded successfully")
                time.sleep(1)
                
                # Simulate surface extraction
                self.progress_update.emit("Extracting surfaces from imported shape...")
                time.sleep(1)
                
                # Simulate no B-spline surfaces found (typical for simple STL)
                self.progress_update.emit("No B-spline surfaces found - importing as mesh triangulation")
                time.sleep(1)
                
                self.progress_update.emit("Mesh triangulation completed successfully")
                time.sleep(1)
                
                # Complete the import
                self.progress_update.emit("Import completed successfully!")
                self.import_complete.emit([], 1)
                
            except Exception as e:
                self.error_occurred.emit(f"Demo error: {str(e)}")
    
    # Create demo app
    app = QApplication.instance() or QApplication([])
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("Progress Dialog Test")
    main_window.resize(300, 200)
    
    # Create central widget
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Create button to start demo import
    demo_button = QPushButton("Start Demo Import")
    layout.addWidget(demo_button)
    
    main_window.setCentralWidget(central)
    
    def start_demo():
        """Start the demo import process."""
        print("🚀 Starting demo import process...")
        
        # Create progress dialog
        progress_dialog = ImportProgressDialog(main_window)
        
        # Create demo thread
        demo_thread = DemoImportThread()
        
        # Set up progress dialog with thread
        progress_dialog.set_import_thread(demo_thread)
        
        # Show the dialog
        progress_dialog.show()
    
    demo_button.clicked.connect(start_demo)
    
    # Show main window
    main_window.show()
    
    print("📋 Click 'Start Demo Import' to test the progress dialog")
    print("🔍 Watch the progress dialog for detailed debug output...")
    
    app.exec()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
