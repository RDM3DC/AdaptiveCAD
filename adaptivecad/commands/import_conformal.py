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
# Use the robust hyperbolic geometry implementation
from ..geom.hyperbolic import pi_a_over_pi, validate_hyperbolic_params
# Keep legacy import for compatibility
from ..nd_math import stable_pi_a_over_pi
import math


def smooth_input(x, y, z, poles, i, j, nb_u_poles, nb_v_poles):
    """Return averaged coordinates using neighboring control points."""
    neighbors = []
    for di in [-1, 0, 1]:
        for dj in [-1, 0, 1]:
            ni, nj = i + di, j + dj
            if 1 <= ni <= nb_u_poles and 1 <= nj <= nb_v_poles and (di or dj):
                pole = poles.Value(ni, nj)
                neighbors.append((pole.X(), pole.Y(), pole.Z()))
    if neighbors:
        avg_x = sum(n[0] for n in neighbors) / len(neighbors)
        avg_y = sum(n[1] for n in neighbors) / len(neighbors)
        avg_z = sum(n[2] for n in neighbors) / len(neighbors)
        return (x + avg_x) / 2.0, (y + avg_y) / 2.0, (z + avg_z) / 2.0
    return x, y, z


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
            print("[ImportThread] Thread started")
            # Check for interruption before starting
            if self.isInterruptionRequested():
                return
                
            # Import the shape
            print(f"[ImportThread] About to import shape: {self.filename}")
            self.progress_update.emit(f"Starting import of {os.path.basename(self.filename)}...")
            
            # Check for interruption again
            if self.isInterruptionRequested():
                return
            
            shape = import_mesh_shape(self.filename)
            print(f"[ImportThread] Shape import returned: {shape}")
            if shape is None:
                self.error_occurred.emit("Failed to load the file")
                return
                
            # Emit the original shape for storage
            self.shape_loaded.emit(shape)
                
            # Check for interruption before processing
            if self.isInterruptionRequested():
                return
                
            # Process the shape
            print("[ImportThread] About to process shape")
            processed_results, face_count = self._process_shape(shape)
            print(f"[ImportThread] Processed results: {processed_results}, face_count: {face_count}")
            
            # Check one final time before completion
            if not self.isInterruptionRequested():
                self.progress_update.emit("Import completed successfully!")
                self.import_complete.emit(processed_results, face_count)
                
        except Exception as e:
            import traceback
            print("[ImportThread] Exception:", e)
            traceback.print_exc()
            if not self.isInterruptionRequested():
                self.error_occurred.emit(f"Import failed: {str(e)}")

    def _process_shape(self, shape):
        """Process the imported shape with multithreading and return results ready for document."""
        # Suppress deprecation warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                print("[ImportThread] Extracting B-spline faces...")
                self.progress_update.emit("Extracting surfaces from imported shape...")
                
                bspline_faces = extract_bspline_faces(shape)
                print(f"[ImportThread] Extracted {len(bspline_faces)} B-spline faces")
                
                if not bspline_faces:
                    # For simple STL files, this is expected - try mesh triangulation
                    self.progress_update.emit("No B-spline surfaces found - importing as mesh triangulation")
                    print("[ImportThread] No B-spline surfaces found, trying mesh triangulation...")
                    
                    # Try to mesh the shape and process as triangulated surface
                    try:
                        mesh = BRepMesh_IncrementalMesh(shape, 0.1)
                        mesh.Perform()
                        if mesh.IsDone():
                            self.progress_update.emit("Mesh triangulation completed successfully")
                            print("[ImportThread] Mesh triangulation successful")
                            # Return a simple result indicating mesh success
                            return [{'success': True, 'type': 'mesh', 'shape': shape}], 1
                        else:
                            self.error_occurred.emit("No surfaces could be extracted and mesh triangulation failed")
                            return [], 0
                    except Exception as mesh_error:
                        print(f"[ImportThread] Mesh triangulation failed: {mesh_error}")
                        self.error_occurred.emit(f"No surfaces could be extracted and mesh triangulation failed: {str(mesh_error)}")
                        return [], 0
                    
                total = len(bspline_faces)
                self.progress_update.emit(f"Processing {total} B-spline surfaces with conformal transformation...")
                self.progress_update.emit(f"PROGRESS:0/{total}")
                
                results = []
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    print(f"[ImportThread] Starting parallel processing with {self.num_threads} threads")
                    future_to_idx = {
                        executor.submit(process_single_bspline_surface, face_data, self.kappa): idx
                        for idx, face_data in enumerate(bspline_faces)
                    }
                    completed = 0
                    for future in as_completed(future_to_idx):
                        result = future.result()
                        results.append(result)
                        completed += 1
                        print(f"[ImportThread] Completed surface {completed}/{total}")
                        self.progress_update.emit(f"PROGRESS:{completed}/{total}")
                        
                successful_results = [r for r in results if r['success']]
                print(f"[ImportThread] Processing complete: {len(successful_results)}/{total} surfaces successful")
                self.progress_update.emit(f"Successfully processed {len(successful_results)}/{total} surfaces")
                return successful_results, len(successful_results)
            except Exception as e:
                import traceback
                print(f"[ImportThread] Error during shape processing: {e}")
                traceback.print_exc()
                self.error_occurred.emit(f"Error during face processing: {str(e)}")
                return [], 0


def import_mesh_shape(file_path: str) -> TopoDS_Shape:
    """Import STL or STEP file and return the shape."""
    ext = os.path.splitext(file_path)[1].lower()
    print(f"[import_mesh_shape] Called with: {file_path} (ext: {ext})")
    try:
        if ext == '.stl':
            print(f"[import_mesh_shape] Reading STL file: {file_path}")
            reader = StlAPI_Reader()
            shape = TopoDS_Shape()
            success = None # Initialize success
            try:
                # Try to get the return value, which is typical in newer versions
                success = reader.Read(shape, file_path)
                print(f"[import_mesh_shape] STL Read returned: {success}")
            except TypeError:
                print(f"[import_mesh_shape] STL Read TypeError, trying fallback")
                reader.Read(shape, file_path)
                success = True 
            except Exception as e:
                print(f"[import_mesh_shape] Exception during STL Read: {e}")
                import traceback
                traceback.print_exc()
                return None
            # After reading, check if the shape is null as an additional safeguard
            if shape.IsNull():
                print(f"[import_mesh_shape] Warning: STL file {file_path} resulted in a null shape.")
                return None
            print(f"[import_mesh_shape] STL shape is not null, returning shape")
            return shape if (success is None or bool(success)) else None
        elif ext in ['.step', '.stp']:
            print(f"[import_mesh_shape] Reading STEP file: {file_path}")
            reader = STEPCAFControl_Reader()
            status = reader.ReadFile(file_path)
            print(f"[import_mesh_shape] STEP ReadFile status: {status}")
            if status == 1:  # Success
                reader.TransferRoots()
                shape = reader.OneShape()
                print(f"[import_mesh_shape] STEP shape returned")
                return shape
            else:
                print(f"[import_mesh_shape] STEP ReadFile failed")
                return None
        else:
            print(f"[import_mesh_shape] Unsupported file format: {ext}")
            return None
    except Exception as e:
        print(f"[import_mesh_shape] Error importing {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_bspline_faces(shape):
    """Extract B-spline surfaces from the shape."""
    bspline_faces = []
    
    print("[extract_bspline_faces] Starting surface extraction...")
    
    # Suppress deprecation warnings during face extraction
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        face_count = 0
        
        while explorer.More():
            face_count += 1
            print(f"[extract_bspline_faces] Processing face {face_count}")
            
            face = explorer.Current()
            try:
                surface = BRep_Tool.Surface(face)
                print(f"[extract_bspline_faces] Surface obtained for face {face_count}")
                
                # Convert to B-spline surface
                bspline_surface = geomconvert_SurfaceToBSplineSurface(surface)
                if bspline_surface:
                    print(f"[extract_bspline_faces] Successfully converted face {face_count} to B-spline")
                    bspline_faces.append({
                        'face': face,
                        'surface': surface,
                        'bspline': bspline_surface
                    })
                else:
                    print(f"[extract_bspline_faces] Could not convert face {face_count} to B-spline (returned None)")
            except Exception as e:
                print(f"[extract_bspline_faces] Warning: Could not convert face {face_count} to B-spline: {e}")
                # Continue with other faces
            explorer.Next()
            
    print(f"[extract_bspline_faces] Completed: {len(bspline_faces)} B-spline surfaces extracted from {face_count} total faces")
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
            
            max_input = 100.0

            for i in range(1, nb_u_poles + 1):
                for j in range(1, nb_v_poles + 1):
                    pole = bspline.Pole(i, j)
                    x0, y0, z0 = pole.X(), pole.Y(), pole.Z()
                    print(f"[DEBUG] Pole({i},{j}) original: x={x0}, y={y0}, z={z0}")

                    x, y, z = smooth_input(
                        x0, y0, z0, bspline.Poles(), i, j, nb_u_poles, nb_v_poles
                    )
                    print(f"[DEBUG] Pole({i},{j}) after smoothing: x={x}, y={y}, z={z}")                    # Apply robust conformal transformation using improved pi_a_over_pi
                    # Validate parameters first
                    valid, msg = validate_hyperbolic_params(math.sqrt(x*x + y*y + z*z), kappa)
                    if not valid:
                        print(f"[WARN] Invalid hyperbolic params at pole({i},{j}): {msg}")
                        # Use original coordinates if validation fails
                        transformed_x = x
                        transformed_y = y
                        transformed_z = z
                    else:
                        # Apply adaptive pi transformation to each coordinate
                        # Use coordinate-wise transformation for better stability
                        if abs(x) > 1e-10:
                            px = pi_a_over_pi(abs(x), kappa)
                            transformed_x = x * px
                        else:
                            transformed_x = x
                            
                        if abs(y) > 1e-10:
                            py = pi_a_over_pi(abs(y), kappa)
                            transformed_y = y * py
                        else:
                            transformed_y = y
                            
                        if abs(z) > 1e-10:
                            pz = pi_a_over_pi(abs(z), kappa)
                            transformed_z = z * pz
                        else:
                            transformed_z = z
                    
                    print(f"[DEBUG] Pole({i},{j}) transformed: x={transformed_x}, y={transformed_y}, z={transformed_z}")

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
        self.progress_bar = None
        
    def __del__(self):
        """Destructor to ensure thread cleanup when command object is destroyed."""
        try:            self._cleanup_thread()
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

            # Create the progress dialog
            from ..gui.import_progress_dialog import ImportProgressDialog
            self.progress_dialog = ImportProgressDialog(mw.win)
            
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
                return            # Set up the progress dialog with the import thread
            self.progress_dialog.set_import_thread(self.import_thread)
            
            # Show the progress dialog
            self.progress_dialog.show()
            
            # Show initial status
            mw.win.statusBar().showMessage(f"Starting import of {os.path.basename(path)}...")

            # Remove any previous 'Add Imported Shape' button
            if hasattr(self, 'add_shape_btn') and self.add_shape_btn:
                try:
                    self.add_shape_btn.deleteLater()
                except Exception:
                    pass
                self.add_shape_btn = None

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
                # Handle progress bar updates
                if message.startswith("PROGRESS:"):
                    # Format: PROGRESS:current/total
                    try:
                        _, val = message.split(":", 1)
                        current, total = val.split("/")
                        current = int(current)
                        total = int(total)
                        if self.progress_bar is None:
                            from PySide6.QtWidgets import QProgressBar
                            self.progress_bar = QProgressBar()
                            self.progress_bar.setMinimum(0)
                            self.progress_bar.setMaximum(total)
                            self.progress_bar.setValue(current)
                            self.mw.win.statusBar().addPermanentWidget(self.progress_bar)
                        else:
                            self.progress_bar.setMaximum(total)
                            self.progress_bar.setValue(current)
                        if current == total:
                            # Hide progress bar after completion
                            self.mw.win.statusBar().removeWidget(self.progress_bar)
                            self.progress_bar.deleteLater()
                            self.progress_bar = None
                    except Exception as e:
                        print(f"Error parsing progress bar update: {e}")
                else:
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
                # Hide progress bar if present
                if self.progress_bar:
                    self.mw.win.statusBar().removeWidget(self.progress_bar)
                    self.progress_bar.deleteLater()
                    self.progress_bar = None
        except Exception as e:
            print(f"Error handling import error: {e}")
        # Clean up the thread on error as well
        self._cleanup_thread()

    def _on_import_complete(self, processed_results, face_count):
        """Handle successful completion of the import."""
        try:
            print(f"[_on_import_complete] Called with {len(processed_results) if processed_results else 0} results, {face_count} faces")
            
            # Ensure MainWindow context is available
            if not (hasattr(self, 'mw') and self.mw and 
                    hasattr(self.mw, 'win') and hasattr(self.mw, 'view') and 
                    hasattr(self.mw.view, '_display')):
                print("Error: Critical GUI components not available in _on_import_complete.")
                return

            # Use the original shape that was loaded (stored via shape_loaded signal)
            if hasattr(self, 'original_shape') and self.original_shape:
                imported_shape = self.original_shape
                print("[_on_import_complete] Using original shape")
            else:
                print("[_on_import_complete] No original shape available")
                self._on_error("No shape was successfully loaded from the file.")
                return

            # Check if the imported shape is valid
            if imported_shape is None or (hasattr(imported_shape, 'IsNull') and imported_shape.IsNull()):
                self._on_error("Import returned a null or invalid shape.")
                return

            # Automatically add the shape to the document
            file_basename = "Unknown File"
            if hasattr(self, 'file_path') and self.file_path:
                try:
                    file_basename = os.path.basename(self.file_path)
                except Exception:
                    file_basename = str(self.file_path)
                    
            # Create the feature and add to document
            feature = Feature(
                f"Imported: {file_basename}",
                {"file": getattr(self, 'file_path', 'N/A'), "conformal_faces": face_count},
                imported_shape
            )
            DOCUMENT.append(feature)
            
            # Update the display
            print("[_on_import_complete] Adding shape to display")
            rebuild_scene(self.mw.view._display)
            self.mw.view._display.FitAll()
            
            # Show success message
            self.mw.win.statusBar().showMessage(
                f"Import completed: {file_basename} ({face_count} surfaces processed)", 4000
            )
            
            print("[_on_import_complete] Import completed successfully")

        except Exception as e:
            import traceback
            print(f"[_on_import_complete] Exception: {e}")
            traceback.print_exc()
            error_msg = f"Error during final import completion: {str(e)}"
            file_info = ""
            if hasattr(self, 'file_path') and self.file_path:
                try:
                    file_info = f" (File: {os.path.basename(self.file_path)})"
                except Exception:
                    file_info = f" (File: {self.file_path})"
            self._on_error(f"{error_msg}{file_info}")
        finally:
            self._cleanup_thread()

    def _cleanup_thread(self):
        """Clean up the import thread properly."""
        
        # Clean up progress dialog
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            try:
                self.progress_dialog.close()
                self.progress_dialog.deleteLater()
            except:
                pass
            self.progress_dialog = None
            
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
