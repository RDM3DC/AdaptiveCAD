from adaptivecad.command_defs import BaseCmd, DOCUMENT, Feature, rebuild_scene
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.GC import GC_MakeArcOfCircle
from PySide6.QtWidgets import QInputDialog, QMessageBox
import math

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
            mainwin.win, "Parametric Rectangle", "Height (Z) (mm):", 0.0, 0.0, 1000.0, 2 # Min height 0 for 2D wire
        )
        if not ok: return

        # Create 4 corner points for the rectangle
        p0 = gp_Pnt(0, 0, 0)
        p1 = gp_Pnt(length, 0, 0)
        p2 = gp_Pnt(length, width, 0)
        p3 = gp_Pnt(0, width, 0)

        corners = [p0, p1, p2, p3]
        edges = []

        if abs(bulge) < 1e-6: # If bulge is very small, make straight edges
            edges.append(BRepBuilderAPI_MakeEdge(corners[0], corners[1]).Edge())
            edges.append(BRepBuilderAPI_MakeEdge(corners[1], corners[2]).Edge())
            edges.append(BRepBuilderAPI_MakeEdge(corners[2], corners[3]).Edge())
            edges.append(BRepBuilderAPI_MakeEdge(corners[3], corners[0]).Edge())
        else:
            # Calculate bulge points and create arcs for rectangle
            # Edge 0: p0 to p1 (along X axis, length 'length')
            bp01 = gp_Pnt(length / 2, -bulge, 0) 
            arc01 = GC_MakeArcOfCircle(corners[0], bp01, corners[1]).Value()
            if arc01: edges.append(BRepBuilderAPI_MakeEdge(arc01).Edge())
            else: edges.append(BRepBuilderAPI_MakeEdge(corners[0], corners[1]).Edge())

            # Edge 1: p1 to p2 (along Y axis, length 'width')
            bp12 = gp_Pnt(length + bulge, width / 2, 0)
            arc12 = GC_MakeArcOfCircle(corners[1], bp12, corners[2]).Value()
            if arc12: edges.append(BRepBuilderAPI_MakeEdge(arc12).Edge())
            else: edges.append(BRepBuilderAPI_MakeEdge(corners[1], corners[2]).Edge())

            # Edge 2: p2 to p3 (along X axis, length 'length')
            bp23 = gp_Pnt(length / 2, width + bulge, 0)
            arc23 = GC_MakeArcOfCircle(corners[2], bp23, corners[3]).Value()
            if arc23: edges.append(BRepBuilderAPI_MakeEdge(arc23).Edge())
            else: edges.append(BRepBuilderAPI_MakeEdge(corners[2], corners[3]).Edge())

            # Edge 3: p3 to p0 (along Y axis, length 'width')
            bp30 = gp_Pnt(-bulge, width / 2, 0)
            arc30 = GC_MakeArcOfCircle(corners[3], bp30, corners[0]).Value()
            if arc30: edges.append(BRepBuilderAPI_MakeEdge(arc30).Edge())
            else: edges.append(BRepBuilderAPI_MakeEdge(corners[3], corners[0]).Edge())
            
            if len(edges) != 4: # Fallback if any arc creation failed
                mainwin.QMessageBox.warning(mainwin.win, "Warning", "Arc creation failed for one or more edges. Using straight edges.")
                edges = [
                    BRepBuilderAPI_MakeEdge(corners[0], corners[1]).Edge(),
                    BRepBuilderAPI_MakeEdge(corners[1], corners[2]).Edge(),
                    BRepBuilderAPI_MakeEdge(corners[2], corners[3]).Edge(),
                    BRepBuilderAPI_MakeEdge(corners[3], corners[0]).Edge(),
                ]

        wire_builder = BRepBuilderAPI_MakeWire()
        for edge in edges:
            if edge: wire_builder.Add(edge)
            else: # Should not happen if fallback above works
                mainwin.QMessageBox.critical(mainwin.win, "Error", "A null edge was encountered.")
                return


        final_shape = None
        if wire_builder.IsDone():
            wire = wire_builder.Wire()
            if height > 1e-6: # If height is significant, extrude to 3D
                face_builder = BRepBuilderAPI_MakeFace(wire)
                if face_builder.IsDone():
                    face = face_builder.Face()
                    prism_vec = gp_Vec(0, 0, height)
                    prism_builder = BRepPrimAPI_MakePrism(face, prism_vec)
                    if prism_builder.IsDone():
                        final_shape = prism_builder.Shape()
                    else:
                        mainwin.QMessageBox.warning(mainwin.win, "Error", "Failed to create 3D prism. Check parameters.")
                        final_shape = wire # Fallback to 2D wire
                else:
                    mainwin.QMessageBox.warning(mainwin.win, "Error", "Failed to create face from wire for extrusion. Check wire self-intersections.")
                    final_shape = wire # Fallback to 2D wire
            else: # Otherwise, keep it as a 2D wire
                final_shape = wire
        else:
            mainwin.QMessageBox.critical(mainwin.win, "Error", "Failed to build wire. Creating a simple straight rectangle as fallback.")
            # Fallback to a simple straight rectangle wire
            sb_wire = BRepBuilderAPI_MakeWire()
            sb_wire.Add(BRepBuilderAPI_MakeEdge(corners[0], corners[1]).Edge())
            sb_wire.Add(BRepBuilderAPI_MakeEdge(corners[1], corners[2]).Edge())
            sb_wire.Add(BRepBuilderAPI_MakeEdge(corners[2], corners[3]).Edge())
            sb_wire.Add(BRepBuilderAPI_MakeEdge(corners[3], corners[0]).Edge())
            if sb_wire.IsDone(): final_shape = sb_wire.Wire()
            else: # Ultimate fallback: do nothing
                mainwin.QMessageBox.critical(mainwin.win, "Fatal Error", "Could not create even a simple fallback shape.")
                return


        if final_shape:
            feat = Feature("ParametricRectShape", {"length": length, "width": width, "bulge": bulge, "height": height}, final_shape)
            DOCUMENT.append(feat)
            rebuild_scene(mainwin.view._display)
        else:
            mainwin.QMessageBox.information(mainwin.win, "Info", "No shape was created.")
