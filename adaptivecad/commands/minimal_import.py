"""
Minimal import command that skips mesh processing to avoid hangs.
"""
import os
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TopoDS import TopoDS_Shape
from ..command_defs import Feature, DOCUMENT, rebuild_scene
from ..commands import BaseCmd
from ..gui.import_progress_dialog import ImportProgressDialog
import time


class MinimalImportThread(QThread):
    """Minimal import thread that skips complex processing."""
    
    progress_update = Signal(str)
    error_occurred = Signal(str)
    import_complete = Signal(object, int)
    shape_loaded = Signal(object)
    
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        
    def run(self):
        """Execute the import in the background."""
        try:
            print(f"[MinimalImportThread] Starting import of: {self.filename}")
            self.progress_update.emit(f"Starting import of {os.path.basename(self.filename)}...")
            time.sleep(0.3)
            
            # Import the shape
            self.progress_update.emit("Loading file...")
            print(f"[MinimalImportThread] About to call _import_shape")
            shape = self._import_shape(self.filename)
            print(f"[MinimalImportThread] _import_shape returned: {shape}")
            
            if shape is None:
                print("[MinimalImportThread] Shape is None, emitting error")
                self.error_occurred.emit("Failed to load the file")
                return
                
            print("[MinimalImportThread] Shape loaded successfully")
            self.shape_loaded.emit(shape)
            self.progress_update.emit("Shape loaded successfully")
            time.sleep(0.3)
            
            # Check for interruption
            if self.isInterruptionRequested():
                print("[MinimalImportThread] Interruption requested")
                return
            
            # Skip mesh processing - go straight to completion
            self.progress_update.emit("Import processing completed (skipped mesh)")
            time.sleep(0.3)
            
            # Check for interruption before completion
            if self.isInterruptionRequested():
                print("[MinimalImportThread] Interruption requested before completion")
                return
            
            # Complete
            print("[MinimalImportThread] Completing import...")
            self.progress_update.emit("Import completed successfully!")
            print("[MinimalImportThread] About to emit import_complete signal")
            self.import_complete.emit(shape, 1)
            print("[MinimalImportThread] Import complete signal emitted")
            
        except Exception as e:
            print(f"[MinimalImportThread] Error: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"Import failed: {str(e)}")
    
    def _import_shape(self, file_path):
        """Import STL or STEP file."""
        ext = os.path.splitext(file_path)[1].lower()
        print(f"[MinimalImportThread] Importing {ext} file: {file_path}")
        
        try:
            if ext == '.stl':
                print("[MinimalImportThread] Creating STL reader")
                reader = StlAPI_Reader()
                shape = TopoDS_Shape()
                print("[MinimalImportThread] Calling reader.Read...")
                success = reader.Read(shape, file_path)
                print(f"[MinimalImportThread] reader.Read returned: {success}")
                
                if shape.IsNull():
                    print("[MinimalImportThread] STL import resulted in null shape")
                    return None
                print("[MinimalImportThread] STL import successful")
                return shape
                
            elif ext in ['.step', '.stp']:
                print("[MinimalImportThread] Creating STEP reader")
                reader = STEPCAFControl_Reader()
                status = reader.ReadFile(file_path)
                print(f"[MinimalImportThread] STEP ReadFile status: {status}")
                if status == 1:  # Success
                    reader.TransferRoots()
                    shape = reader.OneShape()
                    print("[MinimalImportThread] STEP import successful")
                    return shape
                else:
                    print(f"[MinimalImportThread] STEP import failed with status: {status}")
                    return None
            else:
                print(f"[MinimalImportThread] Unsupported file format: {ext}")
                return None
                
        except Exception as e:
            print(f"[MinimalImportThread] Import error: {e}")
            import traceback
            traceback.print_exc()
            return None


class MinimalImportCmd(BaseCmd):
    """Minimal import command that avoids hangs."""
    
    @staticmethod
    def name():
        return "Minimal Import"
    
    def __init__(self):
        super().__init__()
        self.import_thread = None
        self.progress_dialog = None
        self.original_shape = None
        
    def run(self, mw):
        """Run the import command."""
        try:
            # Clean up any existing thread
            self._cleanup_thread()
            
            # Get file to import
            path, _ = QFileDialog.getOpenFileName(
                mw.win, "Import STL or STEP (Minimal)", filter="CAD files (*.stl *.step *.stp)"
            )
            if not path:
                return
                
            # Check if file exists
            if not os.path.exists(path):
                QMessageBox.critical(mw.win, "Error", f"File not found: {path}")
                return
            
            # Store references
            self.mw = mw
            self.file_path = path
            
            print(f"[MinimalImportCmd] Starting import of: {path}")
            
            # Create progress dialog
            self.progress_dialog = ImportProgressDialog(mw.win)
              # Create import thread
            self.import_thread = MinimalImportThread(path)            # Connect signals - import command handles actual completion
            print("[MinimalImportCmd] Connecting signals...")
            self.import_thread.progress_update.connect(self._on_progress_update, Qt.QueuedConnection)
            self.import_thread.error_occurred.connect(self._on_error, Qt.QueuedConnection)
            self.import_thread.import_complete.connect(self._on_import_complete, Qt.QueuedConnection)
            self.import_thread.shape_loaded.connect(self._store_original_shape, Qt.QueuedConnection)
              # Test connection by also connecting to a simple debug handler
            def test_completion_handler(shape, face_count):
                print(f"[MinimalImportCmd] TEST COMPLETION HANDLER CALLED with shape: {shape}, face_count: {face_count}")
                # Since the test handler works, let's use it to do the actual completion work
                self._handle_completion_directly(shape, face_count)
            self.import_thread.import_complete.connect(test_completion_handler, Qt.QueuedConnection)
            
            print("[MinimalImportCmd] Signal connections completed")
            
            # Set up progress dialog - it only handles UI updates
            self.progress_dialog.set_import_thread_for_ui_only(self.import_thread)
            self.progress_dialog.show()
            
            # Show status
            mw.win.statusBar().showMessage(f"Starting minimal import of {os.path.basename(path)}...")
            
        except Exception as e:
            print(f"[MinimalImportCmd] Error in run: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(mw.win, "Error", f"Import command failed: {str(e)}")
            self._cleanup_thread()
    
    def _store_original_shape(self, shape):
        """Store the loaded shape."""
        self.original_shape = shape
        print("[MinimalImportCmd] Shape stored")
    
    def _on_progress_update(self, message):
        """Handle progress updates."""
        print(f"[MinimalImportCmd] Progress: {message}")
        if hasattr(self, 'mw') and self.mw:
            self.mw.win.statusBar().showMessage(message)
    
    def _on_error(self, error_message):
        """Handle errors."""
        print(f"[MinimalImportCmd] Error: {error_message}")
        if hasattr(self, 'mw') and self.mw:
            QMessageBox.critical(self.mw.win, "Import Error", error_message)
            self.mw.win.statusBar().showMessage(f"Import failed: {error_message}", 4000)
        self._cleanup_thread()
    
    def _on_import_complete(self, shape, face_count):
        """Handle successful import completion."""
        print(f"\n[MinimalImportCmd] *** _on_import_complete CALLED ***")
        print(f"[MinimalImportCmd] Signal received with shape: {shape}, face_count: {face_count}")
        try:
            print("\n" + "="*50)
            print("[MinimalImportCmd] IMPORT COMPLETION HANDLER CALLED")
            print("="*50)
            print(f"[MinimalImportCmd] Shape parameter: {shape}")
            print(f"[MinimalImportCmd] Face count: {face_count}")
            
            if not (hasattr(self, 'mw') and self.mw):
                print("[MinimalImportCmd] No main window available")
                return
                
            # Use the stored shape
            if hasattr(self, 'original_shape') and self.original_shape:
                imported_shape = self.original_shape
                print("[MinimalImportCmd] Using stored original shape")
            else:
                imported_shape = shape
                print("[MinimalImportCmd] Using shape from completion signal")
                
            if imported_shape is None:
                print("[MinimalImportCmd] Shape is None")
                self._on_error("Import returned a null shape")
                return
                
            if hasattr(imported_shape, 'IsNull') and imported_shape.IsNull():
                print("[MinimalImportCmd] Shape is null (OCC check)")
                self._on_error("Import returned a null shape")
                return
                
            print(f"[MinimalImportCmd] Shape is valid, type: {type(imported_shape)}")
            
            # Create feature and add to document
            file_basename = os.path.basename(self.file_path) if hasattr(self, 'file_path') else "Unknown"
            feature = Feature(
                f"Imported: {file_basename}",
                {"file": getattr(self, 'file_path', 'N/A')},
                imported_shape
            )
            DOCUMENT.append(feature)
            print(f"[MinimalImportCmd] Added feature to document: {feature.name}")
              # Clear display first
            print("[MinimalImportCmd] Clearing display...")
            self.mw.view._display.EraseAll()
            
            # Display the shape directly first
            print("[MinimalImportCmd] Displaying shape directly...")
            try:
                ais_shape = self.mw.view._display.DisplayShape(imported_shape, update=False)
                print(f"[MinimalImportCmd] Direct shape display successful, AIS: {ais_shape}")
            except Exception as display_error:
                print(f"[MinimalImportCmd] Direct display error: {display_error}")
            
            # Update display with scene rebuild
            print("[MinimalImportCmd] Rebuilding scene...")
            try:
                rebuild_scene(self.mw.view._display)
                print("[MinimalImportCmd] Scene rebuild successful")
            except Exception as rebuild_error:
                print(f"[MinimalImportCmd] Scene rebuild error: {rebuild_error}")
            
            # Force display update and fit
            print("[MinimalImportCmd] Fitting view...")
            try:
                self.mw.view._display.FitAll()
                self.mw.view._display.Repaint()
                # Also try to set a reasonable view direction
                self.mw.view._display.View_Iso()
                self.mw.view._display.FitAll()
                print("[MinimalImportCmd] View fit and repaint successful")
            except Exception as fit_error:
                print(f"[MinimalImportCmd] View fit error: {fit_error}")
            
            # Show success message
            self.mw.win.statusBar().showMessage(f"Import completed: {file_basename}", 4000)
            print(f"[MinimalImportCmd] Import process completed for: {file_basename}")
            
            # Manually notify progress dialog of completion
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.manual_completion_update(face_count)
            
        except Exception as e:
            import traceback
            print(f"[MinimalImportCmd] Error in completion: {e}")
            traceback.print_exc()
            self._on_error(f"Error completing import: {str(e)}")
        finally:
            self._cleanup_thread()
    
    def _handle_completion_directly(self, shape, face_count):
        """Direct completion handler that bypasses any potential issues with the original handler."""
        print(f"\n[MinimalImportCmd] *** DIRECT COMPLETION HANDLER CALLED ***")
        print(f"[MinimalImportCmd] Shape: {shape}, Face count: {face_count}")
        
        try:
            if not (hasattr(self, 'mw') and self.mw):
                print("[MinimalImportCmd] No main window available")
                return
                
            # Use the stored shape
            if hasattr(self, 'original_shape') and self.original_shape:
                imported_shape = self.original_shape
                print("[MinimalImportCmd] Using stored original shape")
            else:
                imported_shape = shape
                print("[MinimalImportCmd] Using shape from completion signal")
                
            if imported_shape is None:
                print("[MinimalImportCmd] Shape is None")
                return
                
            if hasattr(imported_shape, 'IsNull') and imported_shape.IsNull():
                print("[MinimalImportCmd] Shape is null (OCC check)")
                return
                
            print(f"[MinimalImportCmd] Shape is valid, type: {type(imported_shape)}")
            
            # Create feature and add to document
            from ..command_defs import Feature, DOCUMENT, rebuild_scene
            file_basename = os.path.basename(self.file_path) if hasattr(self, 'file_path') else "Unknown"
            feature = Feature(
                f"Imported: {file_basename}",
                {"file": getattr(self, 'file_path', 'N/A')},
                imported_shape
            )
            DOCUMENT.append(feature)
            print(f"[MinimalImportCmd] Added feature to document: {feature.name}")
            
            # Clear display first
            print("[MinimalImportCmd] Clearing display...")
            self.mw.view._display.EraseAll()
            
            # Display the shape directly
            print("[MinimalImportCmd] Displaying shape directly...")
            try:
                ais_shape = self.mw.view._display.DisplayShape(imported_shape, update=False)
                print(f"[MinimalImportCmd] Direct shape display successful, AIS: {ais_shape}")
            except Exception as display_error:
                print(f"[MinimalImportCmd] Direct display error: {display_error}")
            
            # Update display with scene rebuild
            print("[MinimalImportCmd] Rebuilding scene...")
            try:
                rebuild_scene(self.mw.view._display)
                print("[MinimalImportCmd] Scene rebuild successful")
            except Exception as rebuild_error:
                print(f"[MinimalImportCmd] Scene rebuild error: {rebuild_error}")
            
            # Force display update and fit
            print("[MinimalImportCmd] Fitting view...")
            try:
                self.mw.view._display.FitAll()
                self.mw.view._display.Repaint()
                # Also try to set a reasonable view direction
                self.mw.view._display.View_Iso()
                self.mw.view._display.FitAll()
                print("[MinimalImportCmd] View fit and repaint successful")
            except Exception as fit_error:
                print(f"[MinimalImportCmd] View fit error: {fit_error}")
            
            # Show success message
            self.mw.win.statusBar().showMessage(f"Import completed: {file_basename}", 4000)
            print(f"[MinimalImportCmd] Import process completed for: {file_basename}")
            
            # Manually notify progress dialog of completion
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.manual_completion_update(face_count)
                
        except Exception as e:
            import traceback
            print(f"[MinimalImportCmd] Error in direct completion: {e}")
            traceback.print_exc()

    def _cleanup_thread(self):
        """Clean up resources."""
        print("[MinimalImportCmd] Cleaning up...")
        # Don't auto-close progress dialog - let user close it manually
        # if hasattr(self, 'progress_dialog') and self.progress_dialog:
        #     try:
        #         self.progress_dialog.close()
        #     except:
        #         pass
        #     self.progress_dialog = None
            
        if hasattr(self, 'import_thread') and self.import_thread:
            try:
                if self.import_thread.isRunning():
                    print("[MinimalImportCmd] Requesting thread interruption...")
                    self.import_thread.requestInterruption()
                    self.import_thread.wait(3000)
                self.import_thread = None
            except:
                pass
        print("[MinimalImportCmd] Cleanup complete")
