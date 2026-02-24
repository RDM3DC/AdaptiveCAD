"""Construction Geometry Tools

Datum planes, axes, and reference points for precise modeling.
"""

import numpy as np

from ..aacore.sdf import KIND_BOX, Prim


class DatumPlane:
    """Reference plane for construction."""
    
    def __init__(self, origin: np.ndarray, normal: np.ndarray, 
                 size: float = 10.0, name: str = ""):
        self.origin = np.array(origin, dtype=np.float32)
        self.normal = np.array(normal, dtype=np.float32)
        self.normal = self.normal / np.linalg.norm(self.normal)
        self.size = size
        self.name = name
    
    def as_primitive(self, thickness: float = 0.01) -> Prim:
        """Convert to a thin box primitive for visualization."""
        # Create a thin box aligned with the plane
        transform = np.eye(4, dtype=np.float32)
        transform[:3, 3] = self.origin
        
        # Align Z-axis with normal
        z = self.normal
        # Find perpendicular vectors
        if abs(z[0]) < 0.9:
            x = np.cross([1, 0, 0], z)
        else:
            x = np.cross([0, 1, 0], z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        
        # Build rotation matrix
        transform[:3, 0] = x
        transform[:3, 1] = y
        transform[:3, 2] = z
        
        return Prim(
            kind=KIND_BOX,
            transform=transform,
            size=np.array([self.size, self.size, thickness], dtype=np.float32),
            op='solid',
            color=np.array([0.5, 0.5, 0.5, 0.3], dtype=np.float32),  # Semi-transparent gray
            metallic=0.0,
            roughness=0.8
        )
    
    @staticmethod
    def XY(z: float = 0.0, size: float = 10.0) -> 'DatumPlane':
        """Create XY plane at given Z."""
        return DatumPlane([0, 0, z], [0, 0, 1], size, f"XY @ Z={z}")
    
    @staticmethod
    def XZ(y: float = 0.0, size: float = 10.0) -> 'DatumPlane':
        """Create XZ plane at given Y."""
        return DatumPlane([0, y, 0], [0, 1, 0], size, f"XZ @ Y={y}")
    
    @staticmethod
    def YZ(x: float = 0.0, size: float = 10.0) -> 'DatumPlane':
        """Create YZ plane at given X."""
        return DatumPlane([x, 0, 0], [1, 0, 0], size, f"YZ @ X={x}")


class DatumAxis:
    """Reference axis for construction."""
    
    def __init__(self, origin: np.ndarray, direction: np.ndarray,
                 length: float = 20.0, name: str = ""):
        self.origin = np.array(origin, dtype=np.float32)
        self.direction = np.array(direction, dtype=np.float32)
        self.direction = self.direction / np.linalg.norm(self.direction)
        self.length = length
        self.name = name
    
    def as_primitive(self, radius: float = 0.05) -> Prim:
        """Convert to a thin cylinder primitive for visualization."""
        from ..aacore.sdf import KIND_CAPSULE
        
        # Create cylinder along direction
        transform = np.eye(4, dtype=np.float32)
        transform[:3, 3] = self.origin
        
        # Align Z-axis with direction
        z = self.direction
        if abs(z[0]) < 0.9:
            x = np.cross([1, 0, 0], z)
        else:
            x = np.cross([0, 1, 0], z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        
        transform[:3, 0] = x
        transform[:3, 1] = y
        transform[:3, 2] = z
        
        return Prim(
            kind=KIND_CAPSULE,
            transform=transform,
            size=np.array([radius, radius, self.length], dtype=np.float32),
            op='solid',
            color=np.array([1.0, 0.5, 0.0, 0.7], dtype=np.float32),  # Orange
            metallic=0.0,
            roughness=0.6
        )
    
    @staticmethod
    def X(origin: np.ndarray = None, length: float = 20.0) -> 'DatumAxis':
        """Create X-axis."""
        if origin is None:
            origin = [0, 0, 0]
        return DatumAxis(origin, [1, 0, 0], length, "X-Axis")
    
    @staticmethod
    def Y(origin: np.ndarray = None, length: float = 20.0) -> 'DatumAxis':
        """Create Y-axis."""
        if origin is None:
            origin = [0, 0, 0]
        return DatumAxis(origin, [0, 1, 0], length, "Y-Axis")
    
    @staticmethod
    def Z(origin: np.ndarray = None, length: float = 20.0) -> 'DatumAxis':
        """Create Z-axis."""
        if origin is None:
            origin = [0, 0, 0]
        return DatumAxis(origin, [0, 0, 1], length, "Z-Axis")


class ReferencePoint:
    """Reference point for construction."""
    
    def __init__(self, position: np.ndarray, name: str = ""):
        self.position = np.array(position, dtype=np.float32)
        self.name = name
    
    def as_primitive(self, size: float = 0.2) -> Prim:
        """Convert to a small sphere primitive for visualization."""
        from ..aacore.sdf import KIND_SPHERE
        
        transform = np.eye(4, dtype=np.float32)
        transform[:3, 3] = self.position
        
        return Prim(
            kind=KIND_SPHERE,
            transform=transform,
            size=np.array([size, size, size], dtype=np.float32),
            op='solid',
            color=np.array([1.0, 0.0, 0.0, 0.8], dtype=np.float32),  # Red
            metallic=0.2,
            roughness=0.4
        )


def create_work_plane(position: np.ndarray = None, 
                     orientation: str = 'XY') -> DatumPlane:
    """Create a work plane for sketching.
    
    Args:
        position: Position of plane origin
        orientation: 'XY', 'XZ', or 'YZ'
    
    Returns:
        DatumPlane instance
    """
    if position is None:
        position = [0, 0, 0]
    
    if orientation == 'XY':
        return DatumPlane(position, [0, 0, 1], 10.0, "Work Plane XY")
    elif orientation == 'XZ':
        return DatumPlane(position, [0, 1, 0], 10.0, "Work Plane XZ")
    elif orientation == 'YZ':
        return DatumPlane(position, [1, 0, 0], 10.0, "Work Plane YZ")
    else:
        return DatumPlane(position, [0, 0, 1], 10.0, "Work Plane")


def create_construction_box(center: np.ndarray, size: np.ndarray) -> tuple:
    """Create a construction box with corner reference points.
    
    Args:
        center: Center position
        size: Box size [x, y, z]
    
    Returns:
        Tuple of (box_prim, corner_points)
    """
    transform = np.eye(4, dtype=np.float32)
    transform[:3, 3] = center
    
    box = Prim(
        kind=KIND_BOX,
        transform=transform,
        size=np.array(size, dtype=np.float32),
        op='solid',
        color=np.array([0.6, 0.6, 0.6, 0.2], dtype=np.float32),
        metallic=0.0,
        roughness=0.9
    )
    
    # Create corner points
    corners = []
    sx, sy, sz = size[0]/2, size[1]/2, size[2]/2
    cx, cy, cz = center
    
    for dx in [-sx, sx]:
        for dy in [-sy, sy]:
            for dz in [-sz, sz]:
                corners.append(ReferencePoint([cx+dx, cy+dy, cz+dz]))
    
    return box, corners


def snap_to_plane(point: np.ndarray, plane: DatumPlane) -> np.ndarray:
    """Snap a point to a datum plane.
    
    Args:
        point: 3D point to snap
        plane: Datum plane
    
    Returns:
        Snapped point on the plane
    """
    # Project point onto plane
    vec_to_point = point - plane.origin
    distance = np.dot(vec_to_point, plane.normal)
    return point - distance * plane.normal


def snap_to_axis(point: np.ndarray, axis: DatumAxis) -> np.ndarray:
    """Snap a point to a datum axis.
    
    Args:
        point: 3D point to snap
        axis: Datum axis
    
    Returns:
        Closest point on the axis
    """
    vec_to_point = point - axis.origin
    distance = np.dot(vec_to_point, axis.direction)
    return axis.origin + distance * axis.direction
