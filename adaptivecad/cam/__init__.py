"""CAM module stubs for AdaptiveCAD."""

from ..linalg import Vec3


def linear_toolpath(points):
    """Generate a simple linear toolpath from a list of points."""
    return [Vec3(p.x, p.y, p.z) for p in points]


def adaptive_clearing_5axis(shape, tool_radius: float = 3.0):
    """Placeholder for aggressive 5-axis adaptive clearing.

    This stub exists so downstream modules can import the API, but the
    actual implementation is intentionally deferred until the numerical
    kernels (linalg and geometry) are thoroughly validated.

    Args:
        shape: CAD shape to machine. The type is intentionally loose
            because this function is not implemented yet.
        tool_radius (float): Radius of the milling tool in millimeters.

    Raises:
        NotImplementedError: Always, until the kernel stack is stable.
    """

    raise NotImplementedError(
        "Adaptive clearing for 5-axis machines is not implemented yet"
    )
