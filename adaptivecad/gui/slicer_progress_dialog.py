from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PySide6.QtCore import Qt

class SlicerProgressDialog(QDialog):
    def __init__(self, total_layers=100, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Slicing Progress")
        self.setModal(True)
        self.resize(400, 120)
        layout = QVBoxLayout(self)
        self.label = QLabel("Slicing model...", self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, total_layers)
        self.progress.setValue(0)
        self.cancel_button = QPushButton("Cancel", self)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        layout.addWidget(self.cancel_button)
        self.cancelled = False
        self.cancel_button.clicked.connect(self._on_cancel)

    def _on_cancel(self):
        self.cancelled = True
        self.label.setText("Cancelling...")
        self.cancel_button.setEnabled(False)

    def update_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.label.setText(f"Slicing: {current}/{total} layers ({current/total*100:.1f}%)")
        if current >= total:
            self.label.setText("Slicing complete!")
