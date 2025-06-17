"""
Progress dialog for long-running operations like import/export.
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QProgressBar, QTextEdit, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class ImportProgressDialog(QDialog):
    """Progress dialog that shows real-time import progress and details."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Progress")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        # Set up the UI
        self._setup_ui()
        
        # Variables for tracking
        self.import_thread = None
        self.completed = False
        
    def _setup_ui(self):
        """Set up the progress dialog UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Importing STL/STEP File")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("Initializing import...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Detailed log
        log_label = QLabel("Detailed Progress:")
        log_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_import)
        button_layout.addWidget(self.cancel_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def set_import_thread(self, import_thread):
        """Connect to the import thread to receive progress updates."""
        self.import_thread = import_thread
        
        # Connect signals
        import_thread.progress_update.connect(self.update_progress)
        import_thread.error_occurred.connect(self.handle_error)
        import_thread.import_complete.connect(self.handle_completion)
        import_thread.shape_loaded.connect(self.handle_shape_loaded)
        
        # Start the import
        import_thread.start()
        
    def set_import_thread_for_ui_only(self, import_thread):
        """Connect to the import thread for UI updates only (no completion handling)."""
        self.import_thread = import_thread
        
        # Connect only UI-related signals, let the import command handle completion
        import_thread.progress_update.connect(self.update_progress)
        import_thread.error_occurred.connect(self.handle_error)
        import_thread.shape_loaded.connect(self.handle_shape_loaded)
        # NOTE: NOT connecting to import_complete to avoid duplication
        
        # Start the import
        import_thread.start()
        
    def update_progress(self, message):
        """Update progress based on message from import thread."""
        self.log_text.append(f"[{self._get_timestamp()}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
        # Parse progress messages
        if message.startswith("PROGRESS:"):
            # Format: "PROGRESS:current/total"
            try:
                progress_part = message.split("PROGRESS:")[1]
                current, total = map(int, progress_part.split("/"))
                if total > 0:
                    percentage = int((current / total) * 100)
                    self.progress_bar.setValue(percentage)
                    self.status_label.setText(f"Processing surface {current} of {total} ({percentage}%)")
            except (IndexError, ValueError):
                # If we can't parse, just show the message
                self.status_label.setText(message)
        elif "Starting import" in message:
            self.status_label.setText("Loading file...")
            self.progress_bar.setValue(10)
        elif "Successfully processed" in message:
            self.status_label.setText(message)
            self.progress_bar.setValue(95)
        elif "Import completed" in message:
            self.status_label.setText("Import completed successfully!")
            self.progress_bar.setValue(100)
        else:
            self.status_label.setText(message)
            
    def handle_shape_loaded(self, shape):
        """Handle when the original shape is loaded."""
        self.log_text.append(f"[{self._get_timestamp()}] Shape loaded successfully")
        self.status_label.setText("Shape loaded, extracting surfaces...")
        self.progress_bar.setValue(20)
        
    def handle_error(self, error_message):
        """Handle import errors."""
        self.log_text.append(f"[{self._get_timestamp()}] ERROR: {error_message}")
        self.status_label.setText(f"Error: {error_message}")
        self.progress_bar.setValue(0)
        self._finish_import(success=False)
        
    def handle_completion(self, processed_results, face_count):
        """Handle successful import completion."""
        self.log_text.append(f"[{self._get_timestamp()}] Import completed! {face_count} surfaces processed.")
        self.log_text.append(f"[{self._get_timestamp()}] Adding shape to 3D viewer...")
        self.status_label.setText(f"Import completed successfully! {face_count} surfaces added.")
        self.progress_bar.setValue(100)
        
        # Add a slight delay to allow viewing the completion message
        QTimer.singleShot(2000, lambda: self._finish_import(success=True))
        
    def manual_completion_update(self, face_count):
        """Manually update the dialog when import completes (called by import command)."""
        self.log_text.append(f"[{self._get_timestamp()}] Import completed! {face_count} surfaces processed.")
        self.log_text.append(f"[{self._get_timestamp()}] Adding shape to 3D viewer...")
        self.status_label.setText(f"Import completed successfully! {face_count} surfaces added.")
        self.progress_bar.setValue(100)
        
        # Add a slight delay to allow viewing the completion message
        QTimer.singleShot(2000, lambda: self._finish_import(success=True))
        
    def _finish_import(self, success=True):
        """Finish the import process."""
        self.completed = True
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        
        if success:
            self.cancel_button.setText("Done")
        else:
            self.cancel_button.setText("Failed")
            
    def _cancel_import(self):
        """Cancel the ongoing import."""
        if self.import_thread and self.import_thread.isRunning() and not self.completed:
            self.log_text.append(f"[{self._get_timestamp()}] Cancelling import...")
            self.status_label.setText("Cancelling import...")
            self.import_thread.requestInterruption()
            self.import_thread.wait(3000)  # Wait up to 3 seconds
            self.reject()
        else:
            self.reject()
            
    def _get_timestamp(self):
        """Get a formatted timestamp for log entries."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
        
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.import_thread and self.import_thread.isRunning() and not self.completed:
            self._cancel_import()
        event.accept()
