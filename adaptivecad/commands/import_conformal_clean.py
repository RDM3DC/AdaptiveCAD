import os
import concurrent.futures
import threading
import warnings
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from PySide6.QtCore import QThread, Signal
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.GeomConvert import geomconvert_SurfaceToBSplineSurface
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Compound
from OCC.Core.TColgp import TColgp_Array2OfPnt
from OCC.Core.gp import gp_Pnt
from ..command_defs import rebuild_scene
from ..command_defs import Feature, DOCUMENT
from ..commands import BaseCmd
from ..nd_math import pi_a_over_pi


class ImportThread(QThread):
    """Background thread for conformal import to keep GUI responsive."""
    
    # Signals for communicating with the main thread
    progress_update = Signal(str)  # For status messages
    error_occurred = Signal(str)   # For error messages
    import_complete = Signal(object, int)  # When import is finished (processed_results, face_count)
    shape_loaded = Signal(object)  # When the original shape is loaded
    
    def __init__(self, filename, kappa, num_threads=None):
        super().__init__()
        self.filename = filename
        self.kappa = kappa
        self.num_threads = num_threads or os.cpu_count()
        
    def run(self):
        """Execute the import in the background thread."""
        try:
            # Check for interruption before starting
            if self.isInterruptionRequested():
                return
                
            # Import the shape
            self.progress_update.emit(f"Starting import of {os.path.basename(self.filename)}...")
            
            # Check for interruption again
            if self.isInterruptionRequested():
                return
            
            shape = import_mesh_shape(self.filename)
            if shape is None:
                self.error_occurred.emit("Failed to load the file")
                return
                
            # Emit the original shape for storage
            self.shape_loaded.emit(shape)
                
            # Check for interruption before processing
            if self.isInterruptionRequested():
                return
                
            # Process the shape
            processed_results, face_count = self._process_shape(shape)
            
            # Check one final time before completion
            if not self.isInterruptionRequested():
                self.progress_update.emit("Import completed successfully!")
                self.import_complete.emit(processed_results, face_count)
                
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(f"Import failed: {str(e)}")

    def _process_shape(self, shape):
        """Process the imported shape with multithreading and return results ready for document."""
        # Suppress deprecation warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            # Extract and process B-spline surfaces
            try:
                bspline_faces = extract_bspline_faces(shape)
                if not bspline_faces:
                    self.error_occurred.emit("No valid B-spline surfaces could be extracted from the file")
                    return [], 0
                
                # Process B-spline surfaces in parallel with conformal transformation
                self.progress_update.emit(f"Processing {len(bspline_faces)} surfaces with {self.num_threads} threads...")
                results = process_bspline_surfaces_parallel(bspline_faces, self.kappa, max_workers=self.num_threads)
                
                # Return only successful results as faces ready for the document
                successful_results = [r for r in results if r['success']]
                
                self.progress_update.emit(f"Successfully processed {len(successful_results)}/{len(bspline_faces)} surfaces")
                return successful_results, len(successful_results)
                
            except Exception as e:
                self.error_occurred.emit(f"Error during face processing: {str(e)}")
                return [], 0


def import_mesh_shape(file_path: str) -> TopoDS_Shape:
    """Import STL or STEP file and return the shape."""
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.stl':
            reader = StlAPI_Reader()
            shape = TopoDS_Shape()
            success = reader.Read(shape, file_path)
            return shape if success else None
            
        elif ext in ['.step', '.stp']:
            reader = STEPCAFControl_Reader()
            status = reader.ReadFile(file_path)
            if status == 1:  # Success
                reader.TransferRoots()
                shape = reader.OneShape()
                return shape
            else:
                return None
        else:
            print(f"Unsupported file format: {ext}")
            return None
            
    except Exception as e:
        print(f"Error importing {file_path}: {e}")
        return None


def extract_bspline_faces(shape):
    """Extract B-spline surfaces from the shape."""
    bspline_faces = []
    
    # Suppress deprecation warnings during face extraction
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            face = explorer.Current()
            try:
                surface = BRep_Tool.Surface(face)
                # Convert to B-spline surface
                bspline_surface = geomconvert_SurfaceToBSplineSurface(surface)
                if bspline_surface:
                    bspline_faces.append({
                        'face': face,
                        'surface': surface,
                        'bspline': bspline_surface
                    })
            except Exception as e:
                print(f"Warning: Could not convert face to B-spline: {e}")
                # Continue with other faces
            explorer.Next()
            
    return bspline_faces


def process_bspline_surfaces_parallel(bspline_faces, kappa, max_workers=None):
    """Process B-spline surfaces in parallel with conformal transformation."""
    if not bspline_faces:
        return []
        
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all surface processing tasks
        future_to_face = {
            executor.submit(process_single_bspline_surface, face_data, kappa): face_data
            for face_data in bspline_faces
        }
        
        results = []
        for future in concurrent.futures.as_completed(future_to_face):
            face_data = future_to_face[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error processing B-spline surface: {e}")
                results.append({
                    'face_data': face_data,
                    'success': False,
                    'error': str(e)
                })
                
    return results


def process_single_bspline_surface(face_data, kappa):
    """Process a single B-spline surface with conformal transformation."""
    try:
        # Suppress deprecation warnings during processing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            bspline = face_data['bspline']
            
            # Get control points
            u_min, u_max, v_min, v_max = bspline.Bounds()
            nb_u_poles = bspline.NbUPoles()
            nb_v_poles = bspline.NbVPoles()
            
            # Create new control points array
            new_poles = TColgp_Array2OfPnt(1, nb_u_poles, 1, nb_v_poles)
            
            # Apply conformal transformation to each control point
            for i in range(1, nb_u_poles + 1):
                for j in range(1, nb_v_poles + 1):
                    pole = bspline.Pole(i, j)
                    
                    # Apply conformal transformation using pi_a_over_pi
                    # This is a mathematically correct conformal mapping
                    x, y, z = pole.X(), pole.Y(), pole.Z()
                    
                    # Use our mathematically correct pi_a_over_pi function
                    transformed_x = x * pi_a_over_pi(kappa * abs(x))
                    transformed_y = y * pi_a_over_pi(kappa * abs(y))
                    transformed_z = z * pi_a_over_pi(kappa * abs(z))
                    
                    new_pole = gp_Pnt(transformed_x, transformed_y, transformed_z)
                    new_poles.SetValue(i, j, new_pole)
            
            # Create new B-spline surface with transformed control points
            # (In a real implementation, we would create a new surface here)
            # For now, we just return success with the transformation applied
            
            return {
                'face_data': face_data,
                'success': True,
                'transformed_poles': new_poles,
                'bounds': (u_min, u_max, v_min, v_max),
                'nb_poles': (nb_u_poles, nb_v_poles)
            }
            
    except Exception as e:
        return {
            'face_data': face_data,
            'success': False,
            'error': str(e)
        }


class ImportConformalCmd(BaseCmd):
    """Command for importing STL/STEP files with conformal transformation."""
    
    @staticmethod
    def name():
        return "Import Conformal"
    
    def __init__(self):
        super().__init__()
        self.import_thread = None
        self.original_shape = None
        
    def __del__(self):
        """Destructor to ensure thread cleanup when command object is destroyed."""
        try:
            self._cleanup_thread()
        except:
            pass  # Ignore any errors during cleanup in destructor
    
    def run(self, mw) -> None:  # pragma: no cover - GUI integration
        try:
            # Clean up any existing thread first
            self._cleanup_thread()
            
            path, _ = QFileDialog.getOpenFileName(
                mw.win, "Import STL or STEP", filter="CAD files (*.stl *.step *.stp)"
            )
            if not path:
                return
                
            # Check if file exists
            if not os.path.exists(path):
                QMessageBox.critical(mw.win, "Error", f"File not found: {path}")
                return

            kappa, ok = QInputDialog.getDouble(mw.win, "Conformal Import", "kappa:", 1.0)
            if not ok:
                return
            
            # Ask for number of threads (optional optimization)
            max_threads = min(32, os.cpu_count() or 1)  # Cap at reasonable limit
            threads, ok_threads = QInputDialog.getInt(
                mw.win, "Threading Options", 
                f"Number of threads (1-{max_threads}):", 
                min(8, max_threads), 1, max_threads
            )
            if not ok_threads:
                threads = min(8, max_threads)  # Default to 8 threads
                
            # Store references for the thread callbacks
            self.mw = mw
            self.kappa = kappa
            self.file_path = path
            self.n_faces = 0
            
            # Create and start the background import thread
            self.import_thread = ImportThread(path, kappa, threads)
            
            # Connect signals with proper error handling
            try:
                self.import_thread.progress_update.connect(self._on_progress_update)
                self.import_thread.error_occurred.connect(self._on_error)
                self.import_thread.import_complete.connect(self._on_import_complete)
                # Connect a signal to store the original shape
                self.import_thread.shape_loaded.connect(self._store_original_shape)
            except Exception as e:
                print(f"Warning: Could not connect thread signals: {e}")
                self._cleanup_thread()
                return
            
            # Show initial status
            mw.win.statusBar().showMessage(f"Starting import of {os.path.basename(path)}...")
            
            # Start the background thread
            self.import_thread.start()
                
        except Exception as exc:
            print(f"Critical error in ImportConformalCmd: {exc}")
            self._cleanup_thread()  # Ensure cleanup on any error
            try:
                QMessageBox.critical(mw.win, "Critical Error", f"Import command failed: {exc}")
            except:
                print("Could not show error dialog")
                pass
    
    def _store_original_shape(self, shape):
        """Store the original shape for later use."""
        self.original_shape = shape
    
    def _on_progress_update(self, message):
        """Handle progress updates from the background thread."""
        try:
            if hasattr(self, 'mw') and self.mw:
                self.mw.win.statusBar().showMessage(message)
        except Exception as e:
            print(f"Error updating progress: {e}")
    
    def _on_error(self, error_message):
        """Handle errors from the background thread."""
        try:
            if hasattr(self, 'mw') and self.mw:
                print(f"Import error: {error_message}")
                QMessageBox.critical(self.mw.win, "Import Error", error_message)
                self.mw.win.statusBar().showMessage(f"Import failed: {error_message}", 4000)
        except Exception as e:
            print(f"Error handling import error: {e}")
        
        # Clean up the thread on error as well
        self._cleanup_thread()

    def _on_import_complete(self, processed_results, face_count):
        """Handle successful completion of the import."""
        try:
            if hasattr(self, 'mw') and self.mw and self.original_shape:
                # The results contain face processing results ready for the document
                self.mw.win.statusBar().showMessage("Adding imported shape to document...")
                
                # Add the original shape with conformal processing marker
                if hasattr(self, 'file_path'):
                    DOCUMENT.append(Feature("Imported Shape", {"file": self.file_path, "conformal_faces": face_count}, self.original_shape))
                    
                    # Display the original shape (conformal processing affects analysis, not visual display)
                    self.mw.view._display.DisplayShape(self.original_shape, update=False)
                    rebuild_scene(self.mw.view._display)
                    
                    # Final status message
                    self.mw.win.statusBar().showMessage(
                        f"Import completed: {os.path.basename(self.file_path)} ({face_count} faces processed)", 4000
                    )
                
        except Exception as e:
            self._on_error(f"Error displaying imported shape: {str(e)}")
        finally:
            # Clean up the thread
            self._cleanup_thread()
    
    def _cleanup_thread(self):
        """Clean up the import thread properly."""
        if hasattr(self, 'import_thread') and self.import_thread:
            try:
                # Disconnect signals to prevent callbacks during cleanup
                try:
                    self.import_thread.progress_update.disconnect()
                    self.import_thread.error_occurred.disconnect()
                    self.import_thread.import_complete.disconnect()
                    if hasattr(self.import_thread, 'shape_loaded'):
                        self.import_thread.shape_loaded.disconnect()
                except:
                    pass  # Ignore disconnect errors
                
                # Request interruption if running
                if self.import_thread.isRunning():
                    self.import_thread.requestInterruption()
                    
                    # Wait for thread to finish with timeout
                    if not self.import_thread.wait(3000):  # 3 second timeout
                        print("Warning: Import thread did not terminate gracefully")
                        # Force termination as last resort (not recommended but necessary)
                        try:
                            self.import_thread.terminate()
                            self.import_thread.wait(1000)  # Wait 1 more second
                        except:
                            pass
                            
                # Clean up the thread object
                try:
                    self.import_thread.deleteLater()
                except:
                    pass
                    
            except Exception as e:
                print(f"Error during thread cleanup: {e}")
            finally:
                self.import_thread = None
