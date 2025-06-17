"""
Simple import command that shows progress dialog.
"""
import os
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from PySide6.QtCore import QThread, Signal
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from ..command_defs import Feature, DOCUMENT, rebuild_scene
from ..commands import BaseCmd
from ..gui.import_progress_dialog import ImportProgressDialog
import time


class SimpleImportThread(QThread):
    """Simple import thread that shows progress."""
    
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
            print(f"[SimpleImportThread] Starting import of: {self.filename}")
            self.progress_update.emit(f"Starting import of {os.path.basename(self.filename)}...")
            time.sleep(0.5)
              # Import the shape
            self.progress_update.emit("Loading file...")
            shape = self._import_shape(self.filename)
            
            if shape is None:
                self.error_occurred.emit("Failed to load the file")
                return
                
            print("[SimpleImportThread] Shape loaded successfully")
            self.shape_loaded.emit(shape)
            self.progress_update.emit("Shape loaded successfully")
            time.sleep(0.5)
            
            # Check for interruption before mesh processing
            if self.isInterruptionRequested():
                return
            
            # Try to mesh the shape (with timeout protection)
            self.progress_update.emit("Processing geometry...")
            print("[SimpleImportThread] Starting mesh processing...")
            try:
                # Use a much coarser mesh for faster processing
                mesh = BRepMesh_IncrementalMesh(shape, 1.0)  # Increased from 0.1 to 1.0 for speed
                print("[SimpleImportThread] Mesh object created, performing...")
                mesh.Perform()
                print(f"[SimpleImportThread] Mesh.Perform() completed, IsDone: {mesh.IsDone()}")
                
                if mesh.IsDone():
                    self.progress_update.emit("Mesh processing completed")
                    print("[SimpleImportThread] Mesh processing successful")
                    time.sleep(0.5)
                else:
                    self.progress_update.emit("Warning: Mesh processing failed, but continuing...")
                    print("[SimpleImportThread] Mesh processing failed but continuing")
            except Exception as e:
                print(f"[SimpleImportThread] Mesh processing error: {e}")
                import traceback
                traceback.print_exc()
                self.progress_update.emit(f"Mesh processing failed: {str(e)}")
            
            # Check for interruption before completion
            if self.isInterruptionRequested():
                return
            
            # Complete
            print("[SimpleImportThread] Completing import...")
            self.progress_update.emit("Import completed successfully!")
            self.import_complete.emit(shape, 1)
            print("[SimpleImportThread] Import complete signal emitted")
            
        except Exception as e:
            print(f"[SimpleImportThread] Error: {e}")
            self.error_occurred.emit(f"Import failed: {str(e)}")
    
    def _import_shape(self, file_path):
        """Import STL or STEP file."""
        ext = os.path.splitext(file_path)[1].lower()
        print(f"[SimpleImportThread] Importing {ext} file")
        
        try:
            if ext == '.stl':
                reader = StlAPI_Reader()
                shape = TopoDS_Shape()
                success = reader.Read(shape, file_path)
                if shape.IsNull():
                    print("[SimpleImportThread] STL import resulted in null shape")
                    return None
                print("[SimpleImportThread] STL import successful")
                return shape
                
            elif ext in ['.step', '.stp']:
                reader = STEPCAFControl_Reader()
                status = reader.ReadFile(file_path)
                if status == 1:  # Success
                    reader.TransferRoots()
                    shape = reader.OneShape()
                    print("[SimpleImportThread] STEP import successful")
                    return shape
                else:
                    print(f"[SimpleImportThread] STEP import failed with status: {status}")
                    return None
            else:
                print(f"[SimpleImportThread] Unsupported file format: {ext}")
                return None
                
        except Exception as e:
            print(f"[SimpleImportThread] Import error: {e}")
            return None


class SimpleImportCmd(BaseCmd):
    """Simple import command with progress dialog."""
    
    @staticmethod
    def name():
        return "Simple Import"
    
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
                mw.win, "Import STL or STEP", filter="CAD files (*.stl *.step *.stp)"
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
            
            # Create progress dialog
            self.progress_dialog = ImportProgressDialog(mw.win)
              # Create import thread
            self.import_thread = SimpleImportThread(path)
            
            # Connect signals - import command handles actual completion
            self.import_thread.progress_update.connect(self._on_progress_update)
            self.import_thread.error_occurred.connect(self._on_error)
            self.import_thread.import_complete.connect(self._on_import_complete)
            self.import_thread.shape_loaded.connect(self._store_original_shape)
            
            # Set up progress dialog - it only handles UI updates, not the actual import logic
            self.progress_dialog.set_import_thread_for_ui_only(self.import_thread)
            self.progress_dialog.show()
            
            # Show status
            mw.win.statusBar().showMessage(f"Starting import of {os.path.basename(path)}...")
            
        except Exception as e:
            QMessageBox.critical(mw.win, "Error", f"Import command failed: {str(e)}")
            self._cleanup_thread()
    
    def _store_original_shape(self, shape):
        """Store the loaded shape."""
        self.original_shape = shape
        print("[SimpleImportCmd] Shape stored")
    
    def _on_progress_update(self, message):
        """Handle progress updates."""
        if hasattr(self, 'mw') and self.mw:
            self.mw.win.statusBar().showMessage(message)
    
    def _on_error(self, error_message):
        """Handle errors."""
        print(f"[SimpleImportCmd] Error: {error_message}")
        if hasattr(self, 'mw') and self.mw:
            QMessageBox.critical(self.mw.win, "Import Error", error_message)
            self.mw.win.statusBar().showMessage(f"Import failed: {error_message}", 4000)
        self._cleanup_thread()
    
    def _on_import_complete(self, shape, face_count):
        """Handle successful import completion."""
        try:
            print("\n" + "="*50)
            print("[SimpleImportCmd] IMPORT COMPLETION HANDLER CALLED")
            print("="*50)
            print(f"[SimpleImportCmd] Shape parameter: {shape}")
            print(f"[SimpleImportCmd] Face count: {face_count}")
            
            if not (hasattr(self, 'mw') and self.mw):
                print("[SimpleImportCmd] No main window available")
                return
                
            # Use the stored shape
            if hasattr(self, 'original_shape') and self.original_shape:
                imported_shape = self.original_shape
                print("[SimpleImportCmd] Using stored original shape")
            else:
                imported_shape = shape
                print("[SimpleImportCmd] Using shape from completion signal")
                
            if imported_shape is None:
                print("[SimpleImportCmd] Shape is None")
                self._on_error("Import returned a null shape")
                return
                
            if hasattr(imported_shape, 'IsNull') and imported_shape.IsNull():
                print("[SimpleImportCmd] Shape is null (OCC check)")
                self._on_error("Import returned a null shape")
                return
                
            print(f"[SimpleImportCmd] Shape is valid, type: {type(imported_shape)}")
            
            # Create feature and add to document
            file_basename = os.path.basename(self.file_path) if hasattr(self, 'file_path') else "Unknown"
            feature = Feature(
                f"Imported: {file_basename}",
                {"file": getattr(self, 'file_path', 'N/A')},
                imported_shape
            )
            DOCUMENT.append(feature)
            print(f"[SimpleImportCmd] Added feature to document: {feature.name}")
            
            # Clear display first
            print("[SimpleImportCmd] Clearing display...")
            self.mw.view._display.EraseAll()
            
            # Display the shape directly first
            print("[SimpleImportCmd] Displaying shape directly...")
            try:
                self.mw.view._display.DisplayShape(imported_shape, update=False)
                print("[SimpleImportCmd] Direct shape display successful")
            except Exception as display_error:
                print(f"[SimpleImportCmd] Direct display error: {display_error}")
            
            # Update display with scene rebuild
            print("[SimpleImportCmd] Rebuilding scene...")
            try:
                rebuild_scene(self.mw.view._display)
                print("[SimpleImportCmd] Scene rebuild successful")
            except Exception as rebuild_error:
                print(f"[SimpleImportCmd] Scene rebuild error: {rebuild_error}")
            
            # Force display update and fit
            print("[SimpleImportCmd] Fitting view...")
            try:
                self.mw.view._display.FitAll()
                self.mw.view._display.Repaint()
                print("[SimpleImportCmd] View fit and repaint successful")
            except Exception as fit_error:
                print(f"[SimpleImportCmd] View fit error: {fit_error}")            # Show success message
            self.mw.win.statusBar().showMessage(f"Import completed: {file_basename}", 4000)
            print(f"[SimpleImportCmd] Import process completed for: {file_basename}")
            
            # Manually notify progress dialog of completion
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.manual_completion_update(face_count)
            
        except Exception as e:
            import traceback
            print(f"[SimpleImportCmd] Error in completion: {e}")
            traceback.print_exc()
            self._on_error(f"Error completing import: {str(e)}")
            
        except Exception as e:
            print(f"[SimpleImportCmd] Error in completion: {e}")
            self._on_error(f"Error completing import: {str(e)}")
        finally:
            self._cleanup_thread()
    
    def _cleanup_thread(self):
        """Clean up resources."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            try:
                self.progress_dialog.close()
            except:
                pass
            self.progress_dialog = None
            
        if hasattr(self, 'import_thread') and self.import_thread:
            try:
                if self.import_thread.isRunning():
                    self.import_thread.requestInterruption()
                    self.import_thread.wait(3000)
                self.import_thread = None
            except:
                pass
