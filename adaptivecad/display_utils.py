from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from adaptivecad.settings import MESH_DEFLECTION, MESH_ANGLE

def smoother_display(display, shape, deflection=None, angle=None, color=None):
    # Use settings if not overridden
    if deflection is None:
        deflection = MESH_DEFLECTION
    if angle is None:
        angle = MESH_ANGLE
    BRepMesh_IncrementalMesh(shape, deflection, False, angle, True)
    display.DisplayShape(shape, color=color)

def display_with_high_res(display, shape, color=None):
    # For backward compatibility, just call smoother_display
    smoother_display(display, shape, color=color)
