"""Command definition for slicing models to G-code."""
from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
        QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
        QLineEdit, QPushButton, QLabel, QFileDialog,
        QProgressBar, QTabWidget, QWidget, QMessageBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
except ImportError:
    # For type hints only
    class QDialog: pass
    QVBoxLayout = QHBoxLayout = QFormLayout = QComboBox = QDoubleSpinBox = None
    QSpinBox = QCheckBox = QLineEdit = QPushButton = QLabel = QFileDialog = None
    QProgressBar = QTabWidget = QWidget = QMessageBox = Qt = QTimer = None
    
    class QObject:
        class Signal:
            def __init__(self, *args): pass
            def emit(self, *args): pass


class SlicerProgressSignals(QObject):
    """Signals for slicer progress updates."""
    update = Signal(int, int, str)  # current, total, message
    finished = Signal()
    error = Signal(str)


class SliceToGCodeDialog(QDialog):
    """Dialog for slicing and G-code options."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Slice to G-code")
        self.resize(500, 600)
        
        self.main_layout = QVBoxLayout(self)
        
        # Create tabs
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.print_settings_tab = QWidget()
        self.printer_settings_tab = QWidget()
        self.advanced_tab = QWidget()
        
        self.tab_widget.addTab(self.print_settings_tab, "Print Settings")
        self.tab_widget.addTab(self.printer_settings_tab, "Printer Settings")
        self.tab_widget.addTab(self.advanced_tab, "Advanced")
        
        # Create print settings UI
        self._create_print_settings_ui()
        
        # Create printer settings UI
        self._create_printer_settings_ui()
        
        # Create advanced settings UI
        self._create_advanced_settings_ui()
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)
        
        # Add status label
        self.status_label = QLabel("Ready")
        self.main_layout.addWidget(self.status_label)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        self.slice_button = QPushButton("Slice && Export G-code")
        self.slice_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.slice_button)
        
        self.main_layout.addLayout(button_layout)
        
        # Create signals for progress updates
        self.progress_signals = SlicerProgressSignals()
        self.progress_signals.update.connect(self._update_progress)
        self.progress_signals.finished.connect(self._slicing_finished)
        self.progress_signals.error.connect(self._slicing_error)
    
    def _create_print_settings_ui(self):
        """Create UI for print settings tab."""
        layout = QFormLayout(self.print_settings_tab)
        
        # Layer height settings
        self.layer_height = QDoubleSpinBox()
        self.layer_height.setRange(0.05, 0.5)
        self.layer_height.setValue(0.2)
        self.layer_height.setSingleStep(0.05)
        self.layer_height.setSuffix(" mm")
        layout.addRow("Layer Height:", self.layer_height)
        
        self.first_layer_height = QDoubleSpinBox()
        self.first_layer_height.setRange(0.1, 0.5)
        self.first_layer_height.setValue(0.3)
        self.first_layer_height.setSingleStep(0.05)
        self.first_layer_height.setSuffix(" mm")
        layout.addRow("First Layer Height:", self.first_layer_height)
        
        # Wall settings
        self.wall_count = QSpinBox()
        self.wall_count.setRange(1, 10)
        self.wall_count.setValue(3)
        layout.addRow("Wall Count:", self.wall_count)
        
        # Top/bottom layers
        self.top_layers = QSpinBox()
        self.top_layers.setRange(1, 10)
        self.top_layers.setValue(3)
        layout.addRow("Top Layers:", self.top_layers)
        
        self.bottom_layers = QSpinBox()
        self.bottom_layers.setRange(1, 10)
        self.bottom_layers.setValue(3)
        layout.addRow("Bottom Layers:", self.bottom_layers)
        
        # Infill settings
        self.infill_percentage = QDoubleSpinBox()
        self.infill_percentage.setRange(0, 100)
        self.infill_percentage.setValue(20)
        self.infill_percentage.setSingleStep(5)
        self.infill_percentage.setSuffix(" %")
        layout.addRow("Infill Percentage:", self.infill_percentage)
        
        self.infill_pattern = QComboBox()
        self.infill_pattern.addItems(["Grid", "Lines", "Triangles", "Honeycomb"])
        layout.addRow("Infill Pattern:", self.infill_pattern)
        
        # Print speed settings
        self.print_speed = QDoubleSpinBox()
        self.print_speed.setRange(10, 200)
        self.print_speed.setValue(60)
        self.print_speed.setSingleStep(5)
        self.print_speed.setSuffix(" mm/s")
        layout.addRow("Print Speed:", self.print_speed)
        
        self.first_layer_speed = QDoubleSpinBox()
        self.first_layer_speed.setRange(10, 100)
        self.first_layer_speed.setValue(30)
        self.first_layer_speed.setSingleStep(5)
        self.first_layer_speed.setSuffix(" mm/s")
        layout.addRow("First Layer Speed:", self.first_layer_speed)
        
        self.travel_speed = QDoubleSpinBox()
        self.travel_speed.setRange(50, 300)
        self.travel_speed.setValue(120)
        self.travel_speed.setSingleStep(10)
        self.travel_speed.setSuffix(" mm/s")
        layout.addRow("Travel Speed:", self.travel_speed)
        
    def _create_printer_settings_ui(self):
        """Create UI for printer settings tab."""
        layout = QFormLayout(self.printer_settings_tab)
        
        # Printer type
        self.printer_type = QComboBox()
        self.printer_type.addItems([
            "Generic", "Prusa i3 MK3S", "Creality Ender 3", "Anycubic i3 Mega", "Other..."
        ])
        layout.addRow("Printer Type:", self.printer_type)
        
        # Nozzle diameter
        self.nozzle_diameter = QDoubleSpinBox()
        self.nozzle_diameter.setRange(0.1, 1.5)
        self.nozzle_diameter.setValue(0.4)
        self.nozzle_diameter.setSingleStep(0.05)
        self.nozzle_diameter.setSuffix(" mm")
        layout.addRow("Nozzle Diameter:", self.nozzle_diameter)
        
        # Filament settings
        self.filament_diameter = QDoubleSpinBox()
        self.filament_diameter.setRange(1.0, 3.0)
        self.filament_diameter.setValue(1.75)
        self.filament_diameter.setSingleStep(0.05)
        self.filament_diameter.setSuffix(" mm")
        layout.addRow("Filament Diameter:", self.filament_diameter)
        
        # Temperature settings
        self.extruder_temperature = QDoubleSpinBox()
        self.extruder_temperature.setRange(150, 300)
        self.extruder_temperature.setValue(200)
        self.extruder_temperature.setSingleStep(5)
        self.extruder_temperature.setSuffix(" °C")
        layout.addRow("Extruder Temperature:", self.extruder_temperature)
        
        self.bed_temperature = QDoubleSpinBox()
        self.bed_temperature.setRange(0, 120)
        self.bed_temperature.setValue(60)
        self.bed_temperature.setSingleStep(5)
        self.bed_temperature.setSuffix(" °C")
        layout.addRow("Bed Temperature:", self.bed_temperature)
        
        # Fan settings
        self.fan_speed = QSpinBox()
        self.fan_speed.setRange(0, 255)
        self.fan_speed.setValue(255)
        layout.addRow("Fan Speed (0-255):", self.fan_speed)
        
        # Retraction settings
        self.retraction_amount = QDoubleSpinBox()
        self.retraction_amount.setRange(0, 10)
        self.retraction_amount.setValue(0.5)
        self.retraction_amount.setSingleStep(0.1)
        self.retraction_amount.setSuffix(" mm")
        layout.addRow("Retraction Distance:", self.retraction_amount)
        
        self.retraction_speed = QDoubleSpinBox()
        self.retraction_speed.setRange(10, 100)
        self.retraction_speed.setValue(40)
        self.retraction_speed.setSingleStep(5)
        self.retraction_speed.setSuffix(" mm/s")
        layout.addRow("Retraction Speed:", self.retraction_speed)
        
        # Bed size
        bed_size_layout = QHBoxLayout()
        self.bed_size_x = QDoubleSpinBox()
        self.bed_size_x.setRange(50, 500)
        self.bed_size_x.setValue(220)
        self.bed_size_x.setSingleStep(10)
        self.bed_size_x.setSuffix(" mm")
        
        self.bed_size_y = QDoubleSpinBox()
        self.bed_size_y.setRange(50, 500)
        self.bed_size_y.setValue(220)
        self.bed_size_y.setSingleStep(10)
        self.bed_size_y.setSuffix(" mm")
        
        bed_size_layout.addWidget(self.bed_size_x)
        bed_size_layout.addWidget(QLabel("×"))
        bed_size_layout.addWidget(self.bed_size_y)
        
        layout.addRow("Bed Size:", bed_size_layout)
        
    def _create_advanced_settings_ui(self):
        """Create UI for advanced settings tab."""
        layout = QFormLayout(self.advanced_tab)
        
        # Output file selection
        file_layout = QHBoxLayout()
        self.output_file = QLineEdit()
        self.output_file.setText(str(Path.home() / "output.gcode"))
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output)
        
        file_layout.addWidget(self.output_file)
        file_layout.addWidget(browse_button)
        
        layout.addRow("Output File:", file_layout)
        
        # Additional options
        self.include_comments = QCheckBox("Include Comments")
        self.include_comments.setChecked(True)
        layout.addRow("", self.include_comments)
        
        self.minimize_file_size = QCheckBox("Minimize File Size")
        self.minimize_file_size.setChecked(False)
        layout.addRow("", self.minimize_file_size)
        
        self.use_gpu = QCheckBox("Use GPU Acceleration (if available)")
        self.use_gpu.setChecked(True)
        layout.addRow("", self.use_gpu)
        
        # Advanced settings
        self.extrusion_multiplier = QDoubleSpinBox()
        self.extrusion_multiplier.setRange(0.5, 2.0)
        self.extrusion_multiplier.setValue(1.0)
        self.extrusion_multiplier.setSingleStep(0.05)
        layout.addRow("Extrusion Multiplier:", self.extrusion_multiplier)
        
    def _browse_output(self):
        """Open file dialog to select output file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save G-code As", self.output_file.text(), "G-code Files (*.gcode)"
        )
        if file_path:
            self.output_file.setText(file_path)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return {
            # Print settings
            "layer_height": self.layer_height.value(),
            "first_layer_height": self.first_layer_height.value(),
            "wall_count": self.wall_count.value(),
            "top_layers": self.top_layers.value(),
            "bottom_layers": self.bottom_layers.value(),
            "infill_percentage": self.infill_percentage.value(),
            "infill_pattern": self.infill_pattern.currentText(),
            "print_speed": self.print_speed.value(),
            "first_layer_speed": self.first_layer_speed.value(),
            "travel_speed": self.travel_speed.value(),
            
            # Printer settings
            "printer_type": self.printer_type.currentText(),
            "nozzle_diameter": self.nozzle_diameter.value(),
            "filament_diameter": self.filament_diameter.value(),
            "extruder_temperature": self.extruder_temperature.value(),
            "bed_temperature": self.bed_temperature.value(),
            "fan_speed": self.fan_speed.value(),
            "retraction_amount": self.retraction_amount.value(),
            "retraction_speed": self.retraction_speed.value(),
            "bed_size_x": self.bed_size_x.value(),
            "bed_size_y": self.bed_size_y.value(),
            
            # Advanced settings
            "output_file": self.output_file.text(),
            "include_comments": self.include_comments.isChecked(),
            "minimize_file_size": self.minimize_file_size.isChecked(),
            "use_gpu": self.use_gpu.isChecked(),
            "extrusion_multiplier": self.extrusion_multiplier.value(),
        }
    
    def _update_progress(self, current: int, total: int, message: str):
        """Update progress bar and status message."""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
        
        self.status_label.setText(message)
        self.progress_bar.setVisible(True)
        
    def _slicing_finished(self):
        """Called when slicing is complete."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Slicing complete!")
        QMessageBox.information(self, "Slicing Complete", 
                               f"G-code has been successfully exported to:\n{self.output_file.text()}")
        self.accept()
        
    def _slicing_error(self, error_message: str):
        """Called when slicing fails."""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Slicing Error", f"An error occurred during slicing:\n{error_message}")


class SliceToGCodeCmd:
    """Command to slice a model and generate G-code."""
    
    def __init__(self):
        self.name = "Slice to G-code"
        self.description = "Slice a model and generate G-code for 3D printing."
    
    def run(self, app):
        """Run the command in the given application context."""
        # Import here to avoid circular imports
        from adaptivecad.command_defs import DOCUMENT
        from adaptivecad.slicer3d import Slicer3D, PathPlanner, GCodeExporter, PrinterSettings
        
        try:
            # Check if there are shapes to slice
            if not DOCUMENT:
                app.win.statusBar().showMessage("No shapes to slice", 3000)
                QMessageBox.warning(
                    app.win, 
                    "No Models", 
                    "There are no models to slice. Please create or import a model first."
                )
                return
            
            # Get the selected shape or use all shapes
            shape_to_slice = app.selected_feature.shape if app.selected_feature else None
            
            if not shape_to_slice:
                # No selection, create a compound of all shapes
                try:
                    from OCC.Core.BRep import BRep_Builder
                    from OCC.Core.TopoDS import TopoDS_Compound
                    
                    compound = TopoDS_Compound()
                    builder = BRep_Builder()
                    builder.MakeCompound(compound)
                    
                    # Add all shapes to compound
                    for feature in DOCUMENT:
                        if hasattr(feature, 'shape'):
                            builder.Add(compound, feature.shape)
                    
                    shape_to_slice = compound
                    
                except Exception as e:
                    app.win.statusBar().showMessage(f"Error creating compound: {e}", 5000)
                    traceback.print_exc()
                    return
            
            # Show the slicer settings dialog
            dialog = SliceToGCodeDialog(app.win)
            result = dialog.exec()
            
            if result != QDialog.Accepted:
                return
                
            # Get settings
            settings_dict = dialog.get_settings()
            
            # Create printer settings
            printer_settings = PrinterSettings(
                nozzle_diameter=settings_dict["nozzle_diameter"],
                layer_height=settings_dict["layer_height"],
                filament_diameter=settings_dict["filament_diameter"],
                extrusion_multiplier=settings_dict["extrusion_multiplier"],
                retraction_amount=settings_dict["retraction_amount"],
                retraction_speed=settings_dict["retraction_speed"],
                print_speed=settings_dict["print_speed"],
                travel_speed=settings_dict["travel_speed"],
                first_layer_speed=settings_dict["first_layer_speed"],
                first_layer_height=settings_dict["first_layer_height"],
                bed_temperature=settings_dict["bed_temperature"],
                extruder_temperature=settings_dict["extruder_temperature"],
                fan_speed=settings_dict["fan_speed"],
                infill_percentage=settings_dict["infill_percentage"],
                wall_count=settings_dict["wall_count"],
                top_layers=settings_dict["top_layers"],
                bottom_layers=settings_dict["bottom_layers"],
            )
            
            # Prepare for slicing
            output_file = settings_dict["output_file"]
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_file)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Run slicing in a separate thread
            import threading
            
            def slice_thread():
                try:
                    # Update UI to show we're starting
                    dialog.progress_signals.update.emit(0, 100, "Creating slicer...")
                    
                    # Create slicer
                    slicer = Slicer3D(shape_to_slice, printer_settings)
                    
                    # Progress callback
                    def progress_callback(current, total):
                        dialog.progress_signals.update.emit(
                            current, total, f"Slicing layer {current}/{total}"
                        )
                    
                    # Slice model
                    dialog.progress_signals.update.emit(0, 100, "Slicing model...")
                    slice_contours = slicer.slice_model(callback=progress_callback)
                    
                    # Plan tool paths
                    dialog.progress_signals.update.emit(0, 100, "Planning tool paths...")
                    path_planner = PathPlanner(slice_contours, printer_settings)
                    paths = path_planner.plan_paths(callback=progress_callback)
                    
                    # Generate G-code
                    dialog.progress_signals.update.emit(90, 100, "Generating G-code...")
                    gcode_exporter = GCodeExporter(paths, printer_settings)
                    gcode = gcode_exporter.generate_gcode(
                        include_comments=settings_dict["include_comments"],
                        minimize_file_size=settings_dict["minimize_file_size"],
                        printer_type=settings_dict["printer_type"]
                    )
                    
                    # Save to file
                    dialog.progress_signals.update.emit(95, 100, "Saving G-code file...")
                    with open(output_file, 'w') as f:
                        f.write(gcode)
                    
                    # Finished
                    dialog.progress_signals.finished.emit()
                    
                except Exception as e:
                    traceback.print_exc()
                    dialog.progress_signals.error.emit(str(e))
            
            # Start the thread
            thread = threading.Thread(target=slice_thread)
            thread.daemon = True
            thread.start()
            
            # Keep the dialog open until the thread finishes
            dialog.exec()
            
        except Exception as e:
            app.win.statusBar().showMessage(f"Error slicing model: {e}", 5000)
            traceback.print_exc()
            
            QMessageBox.critical(
                app.win, 
                "Error", 
                f"An error occurred during slicing:\n{str(e)}\n\nSee console for details."
            )
