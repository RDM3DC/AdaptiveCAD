\
from adaptivecad.command_defs import BaseCmd, DOCUMENT, Feature, rebuild_scene
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCC.Core.TColgp import TColgp_Array2OfPnt
from OCC.Core.GeomAbs import GeomAbs_C2 # For BSpline surface continuity
from PySide6.QtWidgets import QInputDialog, QMessageBox
import math

class DrapedSheetCmd(BaseCmd):
    def run(self, mainwin):
        # Sheet parameters
        sheet_length, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sheet Length (X):", 100.0, 1.0, 2000.0, 2)
        if not ok: return
        sheet_width, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sheet Width (Y):", 100.0, 1.0, 2000.0, 2)
        if not ok: return

        # Sphere parameters
        sphere_radius, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sphere Radius:", 30.0, 1.0, 1000.0, 2)
        if not ok: return
        sphere_cx, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sphere Center X:", 0.0, -1000.0, 1000.0, 2)
        if not ok: return
        sphere_cy, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sphere Center Y:", 0.0, -1000.0, 1000.0, 2)
        if not ok: return
        sphere_cz, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sphere Center Z:", 0.0, -1000.0, 1000.0, 2)
        if not ok: return
        
        # Draping and resolution parameters
        drape_offset_z, ok = QInputDialog.getDouble(mainwin.win, "Draped Sheet", "Sheet Initial Z Offset (from sphere center):", sphere_radius, -2*sphere_radius, 2*sphere_radius, 2)
        if not ok: return
        num_points_u, ok = QInputDialog.getInt(mainwin.win, "Draped Sheet", "Number of points along Length (U):", 20, 2, 100, 1)
        if not ok: return
        num_points_v, ok = QInputDialog.getInt(mainwin.win, "Draped Sheet", "Number of points along Width (V):", 20, 2, 100, 1)
        if not ok: return

        sphere_center = gp_Pnt(sphere_cx, sphere_cy, sphere_cz)
        
        # Create a 2D array for OCC (1-indexed)
        projected_points_array = TColgp_Array2OfPnt(1, num_points_u, 1, num_points_v)

        for i in range(num_points_u): # Corresponds to U direction (sheet_length)
            u_ratio = i / (num_points_u - 1) # 0.0 to 1.0
            # X-coordinate on the flat sheet, centered at 0
            flat_x = (u_ratio - 0.5) * sheet_length
            
            for j in range(num_points_v): # Corresponds to V direction (sheet_width)
                v_ratio = j / (num_points_v - 1) # 0.0 to 1.0
                # Y-coordinate on the flat sheet, centered at 0
                flat_y = (v_ratio - 0.5) * sheet_width
                
                # Initial 3D point of the flat sheet, positioned relative to sphere center + offset
                initial_sheet_point = gp_Pnt(
                    sphere_center.X() + flat_x,
                    sphere_center.Y() + flat_y,
                    sphere_center.Z() + drape_offset_z 
                )
                
                # Vector from sphere center to the initial sheet point
                vec_to_point = gp_Vec(sphere_center, initial_sheet_point)
                
                projected_point_on_sphere = sphere_center
                if vec_to_point.Magnitude() > 1e-9: # Avoid division by zero if point is at sphere center
                    direction = vec_to_point.Normalized()
                    projected_point_on_sphere = sphere_center.Translated(direction.Scaled(sphere_radius))
                
                projected_points_array.SetValue(i + 1, j + 1, projected_point_on_sphere)

        try:
            # Create BSpline surface from the array of points
            # Constructor: GeomAPI_PointsToBSplineSurface(Points, DegMin, DegMax, Continuity, Tol)
            # Using default degrees by not specifying DegMin/DegMax initially.
            # surface_builder = GeomAPI_PointsToBSplineSurface(projected_points_array, 3, 8, GeomAbs_C2, 1e-3)
            surface_builder = GeomAPI_PointsToBSplineSurface(projected_points_array) # Simpler constructor
            if not surface_builder.IsDone():
                 # Try with more parameters if the simple one fails
                surface_builder = GeomAPI_PointsToBSplineSurface(projected_points_array, 3, 5, GeomAbs_C2, 1e-3)


            if surface_builder.IsDone() and surface_builder.Surface().NbUKnots() > 0 : # Check if surface is valid
                bspline_surface_handle = surface_builder.Surface()
                
                # Convert the BSpline surface to a TopoDS_Face
                # Tolerance for face creation might need adjustment
                face_maker = BRepBuilderAPI_MakeFace(bspline_surface_handle, 1e-3) 
                if face_maker.IsDone():
                    draped_shape = face_maker.Face()
                    params = {
                        "sheet_length": sheet_length, "sheet_width": sheet_width,
                        "sphere_radius": sphere_radius, "sphere_cx": sphere_cx, 
                        "sphere_cy": sphere_cy, "sphere_cz": sphere_cz,
                        "drape_offset_z": drape_offset_z,
                        "num_points_u": num_points_u, "num_points_v": num_points_v
                    }
                    feat = Feature("DrapedSheet", params, draped_shape)
                    DOCUMENT.append(feat)
                    rebuild_scene(mainwin.view._display)
                else:
                    QMessageBox.warning(mainwin.win, "Error", "Failed to create face from BSpline surface.")
            else:
                QMessageBox.warning(mainwin.win, "Error", "Failed to create BSpline surface from points. Check parameters or point grid.")
        except Exception as e:
            QMessageBox.critical(mainwin.win, "Critical Error", f"An exception occurred during surface creation: {e}")

