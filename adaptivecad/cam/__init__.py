"""CAM module stubs for AdaptiveCAD."""

from ..linalg import Vec3


def linear_toolpath(points):
    """Generate a simple linear toolpath from a list of points."""
    return [Vec3(p.x, p.y, p.z) for p in points]
