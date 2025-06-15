from OCC.Core.gp import gp_Pnt, gp_Ax2, gp_Dir
from OCC.Core.BRepPrimAPI import (
    BRepPrimAPI_MakeSphere,
    BRepPrimAPI_MakeTorus,
    BRepPrimAPI_MakeCone,
)

def make_ball(center, radius):
    c = gp_Pnt(*center)
    return BRepPrimAPI_MakeSphere(c, radius).Shape()

def make_torus(center, major_radius, minor_radius, axis=(0,0,1)):
    c = gp_Pnt(*center)
    ax = gp_Ax2(c, gp_Dir(*axis))
    return BRepPrimAPI_MakeTorus(ax, major_radius, minor_radius).Shape()

def make_cone(center, radius1, radius2, height, axis=(0,0,1)):
    """Create a truncated cone shape."""
    c = gp_Pnt(*center)
    ax = gp_Ax2(c, gp_Dir(*axis))
    return BRepPrimAPI_MakeCone(ax, radius1, radius2, height).Shape()
