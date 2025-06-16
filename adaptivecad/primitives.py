from OCC.Core.gp import gp_Pnt, gp_Ax2, gp_Dir
from OCC.Core.BRepPrimAPI import (
    BRepPrimAPI_MakeSphere,
    BRepPrimAPI_MakeTorus,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeRevol,
)
import math

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

def make_revolve(profile, axis_point, axis_dir=(0,0,1), angle_deg=360):
    """Revolve a profile edge/wire about an axis to create a solid."""
    ax = gp_Ax2(gp_Pnt(*axis_point), gp_Dir(*axis_dir))
    angle_rad = math.radians(angle_deg)
    return BRepPrimAPI_MakeRevol(profile, ax, angle_rad).Shape()
