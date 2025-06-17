
from adaptivecad.command_defs import BaseCmd, DOCUMENT, Feature, rebuild_scene
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.GC import GC_MakeArcOfCircle
from PySide6.QtWidgets import QInputDialog, QMessageBox
import math

# Robust, bounded pi_a_over_pi implementation
def pi_a_over_pi(u):
    amplitude = 0.5
    sensitivity = 0.1
    scaling = 1.0 + amplitude * math.tanh(sensitivity * u)
    if not math.isfinite(scaling):
        return 1.0
    return max(0.5, min(1.5, scaling))

class PiSquareCmd(BaseCmd):
    def run(self, mainwin):
        # Prompt for Length (X)
        length, ok = QInputDialog.getDouble(
            mainwin.win, "Parametric Rectangle", "Length (X) (mm):", 50.0, 1.0, 1000.0, 2
        )
        if not ok: return

        # Prompt for Width (Y)
        width, ok = QInputDialog.getDouble(
            mainwin.win, "Parametric Rectangle", "Width (Y) (mm):", 30.0, 1.0, 1000.0, 2
        )
        if not ok: return
        
        min_side_for_bulge_limit = min(length, width)

        # Prompt for bulge amount
        bulge, ok = QInputDialog.getDouble(
            mainwin.win, "Parametric Rectangle", "Bulge Amount (mm):", 0.0, 
            -min_side_for_bulge_limit / 2 + 1e-3, min_side_for_bulge_limit / 2 - 1e-3, 2
        )
        if not ok: return

        # Prompt for Height (Z)
        height, ok = QInputDialog.getDouble(
            mainwin.win, "Parametric Rectangle", "Height (Z) (mm):", 0.0, 0.0, 1000.0, 2
        )
        if not ok: return

        # Prompt for Kappa (conformal factor)
        kappa, ok = QInputDialog.getDouble(
            mainwin.win, "Conformal Transformation", "Kappa:", 1.0, 0.0, 100.0, 2
        )
        if not ok: return

        # Create and transform 4 corner points
        corners_raw = [
            (0, 0, 0),
            (length, 0, 0),
            (length, width, 0),
            (0, width, 0)
        ]
        corners = []
        for x, y, z in corners_raw:
            px = pi_a_over_pi(kappa * abs(x))
            py = pi_a_over_pi(kappa * abs(y))
            pz = pi_a_over_pi(kappa * abs(z))
            if not all(math.isfinite(val) for val in [px, py, pz]):
                print(f"[WARN] Non-finite pi_a_over_pi at ({x}, {y}, {z}), using 1.0")
                px, py, pz = 1.0, 1.0, 1.0
            transformed_x = x * px
            transformed_y = y * py
            transformed_z = z * pz
            if not all(math.isfinite(val) for val in [transformed_x, transformed_y, transformed_z]):
                print(f"[WARN] Non-finite transformed coords at ({x}, {y}, {z}), clamping to original")
                transformed_x, transformed_y, transformed_z = x, y, z
            corners.append(gp_Pnt(transformed_x, transformed_y, transformed_z))

        edges = []
        if abs(bulge) < 1e-6:
            # Straight edges
            for i in range(4):
                edges.append(BRepBuilderAPI_MakeEdge(corners[i], corners[(i+1)%4]).Edge())
        else:
            # Transform bulge points
            bulge_points_raw = [
                (length / 2, -bulge, 0),  # bp01
                (length + bulge, width / 2, 0),  # bp12
                (length / 2, width + bulge, 0),  # bp23
                (-bulge, width / 2, 0)  # bp30
            ]
            bulge_points = []
            for x, y, z in bulge_points_raw:
                px = pi_a_over_pi(kappa * abs(x))
                py = pi_a_over_pi(kappa * abs(y))
                pz = pi_a_over_pi(kappa * abs(z))
                if not all(math.isfinite(val) for val in [px, py, pz]):
                    print(f"[WARN] Non-finite pi_a_over_pi at ({x}, {y}, {z}), using 1.0")
                    px, py, pz = 1.0, 1.0, 1.0
                transformed_x = x * px
                transformed_y = y * py
                transformed_z = z * pz
                if not all(math.isfinite(val) for val in [transformed_x, transformed_y, transformed_z]):
                    print(f"[WARN] Non-finite transformed coords at ({x}, {y}, {z}), clamping to original")
                    transformed_x, transformed_y, transformed_z = x, y, z
                bulge_points.append(gp_Pnt(transformed_x, transformed_y, transformed_z))

            # Create arcs
            for i in range(4):
                arc = GC_MakeArcOfCircle(corners[i], bulge_points[i], corners[(i+1)%4]).Value()
                if arc:
                    edges.append(BRepBuilderAPI_MakeEdge(arc).Edge())
                else:
                    print(f"[WARN] Arc creation failed for edge {i}, using straight edge")
                    edges.append(BRepBuilderAPI_MakeEdge(corners[i], corners[(i+1)%4]).Edge())

        wire_builder = BRepBuilderAPI_MakeWire()
        for edge in edges:
            if edge:
                wire_builder.Add(edge)
            else:
                QMessageBox.critical(mainwin.win, "Error", "A null edge was encountered.")
                return

        final_shape = None
        if wire_builder.IsDone():
            wire = wire_builder.Wire()
            if height > 1e-6:
                face_builder = BRepBuilderAPI_MakeFace(wire)
                if face_builder.IsDone():
                    face = face_builder.Face()
                    # Transform height if needed
                    transformed_height = height * pi_a_over_pi(kappa * abs(height))
                    if not math.isfinite(transformed_height) or transformed_height > 1e6:
                        print(f"[WARN] Non-finite transformed height {transformed_height}, using original")
                        transformed_height = height
                    prism_vec = gp_Vec(0, 0, transformed_height)
                    prism_builder = BRepPrimAPI_MakePrism(face, prism_vec)
                    if prism_builder.IsDone():
                        final_shape = prism_builder.Shape()
                    else:
                        QMessageBox.warning(mainwin.win, "Error", "Failed to create 3D prism.")
                        final_shape = wire
                else:
                    QMessageBox.warning(mainwin.win, "Error", "Failed to create face from wire.")
                    final_shape = wire
            else:
                final_shape = wire
        else:
            QMessageBox.critical(mainwin.win, "Error", "Failed to build wire. Creating fallback rectangle.")
            sb_wire = BRepBuilderAPI_MakeWire()
            for i in range(4):
                sb_wire.Add(BRepBuilderAPI_MakeEdge(corners[i], corners[(i+1)%4]).Edge())
            if sb_wire.IsDone():
                final_shape = sb_wire.Wire()
            else:
                QMessageBox.critical(mainwin.win, "Fatal Error", "Could not create fallback shape.")
                return

        if final_shape:
            feat = Feature("ParametricRectShape", {
                "length": length, "width": width, "bulge": bulge, "height": height, "kappa": kappa
            }, final_shape)
            DOCUMENT.append(feat)
            rebuild_scene(mainwin.view._display)
        else:
            QMessageBox.information(mainwin.win, "Info", "No shape was created.")
