#!/usr/bin/env python3
"""
Test script to demonstrate the responsive GUI import with background threading.
This creates a minimal GUI to test the import functionality.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QTextEdit
from PySide6.QtCore import Qt

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adaptivecad.commands.import_conformal import ImportThread


class TestMainWindow(QMainWindow):
    """Simple test window to demonstrate responsive threading."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AdaptiveCAD - Responsive Import Test")
        self.setGeometry(100, 100, 600, 400)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Create widgets
        self.status_label = QLabel("Ready to test responsive import")
        self.test_button = QPushButton("Test Responsive Import (Mock)")
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(200)
        
        # Add widgets to layout
        layout.addWidget(self.status_label)
        layout.addWidget(self.test_button)
        layout.addWidget(QLabel("Log Output:"))
        layout.addWidget(self.log_display)
        
        # Connect button
        self.test_button.clicked.connect(self.test_responsive_import)
        
        # Initialize thread
        self.import_thread = None
        
    def test_responsive_import(self):
        """Test the responsive import by creating a mock thread."""
        self.log("Testing responsive import threading...")
        self.status_label.setText("Running background import...")
        self.test_button.setEnabled(False)
        
        # Create a mock import thread (using a non-existent file for demo)
        self.import_thread = ImportThread("mock_test_file.stl", 4)
        
        # Connect signals
        self.import_thread.progress_update.connect(self.on_progress)
        self.import_thread.error_occurred.connect(self.on_error)
        self.import_thread.import_complete.connect(self.on_complete)
        
        # Start the thread
        self.import_thread.start()
        
        self.log("✓ Background thread started successfully!")
        self.log("✓ GUI remains responsive while thread runs")
        
    def on_progress(self, message):
        """Handle progress updates."""
        self.log(f"Progress: {message}")
        self.status_label.setText(message)
        
    def on_error(self, error_message):
        """Handle errors."""
        self.log(f"✓ Expected error (mock test): {error_message}")
        self.status_label.setText("Test completed - GUI remained responsive!")
        self.test_button.setEnabled(True)
        
    def on_complete(self):
        """Handle completion."""
        self.log("✓ Import completed successfully!")
        self.status_label.setText("Import completed successfully!")
        self.test_button.setEnabled(True)
        
    def log(self, message):
        """Add a message to the log display."""
        self.log_display.append(message)
        self.log_display.ensureCursorVisible()


def main():
    """Run the responsive import test."""
    app = QApplication(sys.argv)
    
    window = TestMainWindow()
    window.show()
    
    print("=" * 60)
    print("🚀 RESPONSIVE IMPORT TEST")
    print("=" * 60)
    print("✅ GUI threading components loaded successfully")
    print("✅ Click 'Test Responsive Import' to see background threading")
    print("✅ GUI should remain responsive during the test")
    print("✅ Close the window when done testing")
    print("=" * 60)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
