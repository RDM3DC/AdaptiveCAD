"""2D Sketch Tools

Create 2D profiles that can be extruded into 3D shapes.
"""

import numpy as np

from ..aacore.sdf import KIND_BOX, KIND_CAPSULE, KIND_SPHERE, Prim


def sketch_rectangle(width: float, height: float, position: np.ndarray = None) -> Prim:
    """Create a 2D rectangle sketch (thin box in XY plane).
    
    Args:
        width: Rectangle width (X dimension)
        height: Rectangle height (Y dimension)
        position: Center position [x, y, z], defaults to origin
    
    Returns:
        Thin box primitive representing the rectangle
    """
    if position is None:
        position = [0, 0, 0]
    
    transform = np.eye(4, dtype=np.float32)
    transform[:3, 3] = position
    
    # Very thin in Z direction to represent 2D
    size = np.array([width, height, 0.01], dtype=np.float32)
    
    return Prim(
        kind=KIND_BOX,
        transform=transform,
        size=size,
        op='solid',
        color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.6
    )


def sketch_circle(radius: float, position: np.ndarray = None) -> Prim:
    """Create a 2D circle sketch (thin cylinder in XY plane).
    
    Args:
        radius: Circle radius
        position: Center position [x, y, z], defaults to origin
    
    Returns:
        Thin cylinder primitive representing the circle
    """
    if position is None:
        position = [0, 0, 0]
    
    transform = np.eye(4, dtype=np.float32)
    transform[:3, 3] = position
    
    # Very thin in Z direction
    size = np.array([radius, radius, 0.01], dtype=np.float32)
    
    return Prim(
        kind=KIND_CAPSULE,  # Flat capsule acts like circle
        transform=transform,
        size=size,
        op='solid',
        color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.6
    )


def sketch_polygon(radius: float, sides: int = 6, position: np.ndarray = None) -> Prim:
    """Create a 2D polygon sketch.
    
    For now, approximated with a cylinder (exact polygon SDF can be added later).
    
    Args:
        radius: Circumradius of polygon
        sides: Number of sides (3=triangle, 4=square, 5=pentagon, etc.)
        position: Center position
    
    Returns:
        Primitive representing the polygon
    """
    # For now, use cylinder as approximation
    # TODO: Add proper polygon SDF
    return sketch_circle(radius, position)


def sketch_ellipse(radius_x: float, radius_y: float, 
                   position: np.ndarray = None) -> Prim:
    """Create a 2D ellipse sketch (thin ellipsoid in XY plane).
    
    Args:
        radius_x: Radius in X direction
        radius_y: Radius in Y direction
        position: Center position
    
    Returns:
        Thin ellipsoid primitive
    """
    if position is None:
        position = [0, 0, 0]
    
    transform = np.eye(4, dtype=np.float32)
    transform[:3, 3] = position
    
    # Ellipsoid with different X and Y radii
    size = np.array([radius_x, radius_y, 0.01], dtype=np.float32)
    
    return Prim(
        kind=KIND_SPHERE,  # Sphere scaled non-uniformly becomes ellipsoid
        transform=transform,
        size=size,
        op='solid',
        color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.6
    )


def sketch_rounded_rectangle(width: float, height: float, 
                             corner_radius: float,
                             position: np.ndarray = None) -> list[Prim]:
    """Create a rounded rectangle sketch using CSG.
    
    Args:
        width: Rectangle width
        height: Rectangle height
        corner_radius: Radius of corner rounds
        position: Center position
    
    Returns:
        List of primitives forming rounded rectangle
    """
    if position is None:
        position = [0, 0, 0]
    
    prims = []
    
    # Center rectangle
    center_width = width - 2 * corner_radius
    center_height = height - 2 * corner_radius
    
    if center_width > 0 and center_height > 0:
        # Main body
        main_rect = sketch_rectangle(center_width, center_height, position)
        prims.append(main_rect)
        
        # Horizontal extensions
        h_ext_width = corner_radius * 2
        h_ext_height = center_height
        
        left_pos = [position[0] - center_width/2 - corner_radius, position[1], position[2]]
        right_pos = [position[0] + center_width/2 + corner_radius, position[1], position[2]]
        
        prims.append(sketch_rectangle(h_ext_width, h_ext_height, left_pos))
        prims.append(sketch_rectangle(h_ext_width, h_ext_height, right_pos))
        
        # Vertical extensions
        v_ext_width = center_width
        v_ext_height = corner_radius * 2
        
        top_pos = [position[0], position[1] + center_height/2 + corner_radius, position[2]]
        bottom_pos = [position[0], position[1] - center_height/2 - corner_radius, position[2]]
        
        prims.append(sketch_rectangle(v_ext_width, v_ext_height, top_pos))
        prims.append(sketch_rectangle(v_ext_width, v_ext_height, bottom_pos))
        
        # Corner circles
        corners = [
            [position[0] - center_width/2, position[1] - center_height/2, position[2]],
            [position[0] + center_width/2, position[1] - center_height/2, position[2]],
            [position[0] + center_width/2, position[1] + center_height/2, position[2]],
            [position[0] - center_width/2, position[1] + center_height/2, position[2]],
        ]
        
        for corner in corners:
            prims.append(sketch_circle(corner_radius, corner))
    
    return prims


def sketch_line(start: np.ndarray, end: np.ndarray, thickness: float = 0.1) -> Prim:
    """Create a line segment sketch.
    
    Args:
        start: Start point [x, y, z]
        end: End point [x, y, z]
        thickness: Line thickness
    
    Returns:
        Thin cylinder connecting the points
    """
    start = np.array(start, dtype=np.float32)
    end = np.array(end, dtype=np.float32)
    
    # Calculate center and length
    center = (start + end) / 2
    direction = end - start
    length = np.linalg.norm(direction)
    
    if length < 1e-6:
        # Degenerate case: create a small sphere
        return Prim(
            kind=KIND_SPHERE,
            transform=np.eye(4, dtype=np.float32),
            size=np.array([thickness, thickness, thickness], dtype=np.float32),
            op='solid',
            color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32),
            metallic=0.0,
            roughness=0.6
        )
    
    direction = direction / length
    
    # Create transform that orients cylinder along the line
    transform = np.eye(4, dtype=np.float32)
    transform[:3, 3] = center
    
    # Align Z-axis with direction
    z = direction
    if abs(z[0]) < 0.9:
        x = np.cross([1, 0, 0], z)
    else:
        x = np.cross([0, 1, 0], z)
    
    if np.linalg.norm(x) > 1e-6:
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
    else:
        x = np.array([1, 0, 0], dtype=np.float32)
        y = np.array([0, 1, 0], dtype=np.float32)
    
    transform[:3, 0] = x
    transform[:3, 1] = y
    transform[:3, 2] = z
    
    return Prim(
        kind=KIND_CAPSULE,
        transform=transform,
        size=np.array([thickness/2, thickness/2, length], dtype=np.float32),
        op='solid',
        color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.6
    )


def sketch_arc(center: np.ndarray, radius: float, start_angle: float,
               end_angle: float, segments: int = 16) -> list[Prim]:
    """Create an arc sketch using line segments.
    
    Args:
        center: Arc center [x, y, z]
        radius: Arc radius
        start_angle: Start angle in degrees
        end_angle: End angle in degrees
        segments: Number of line segments
    
    Returns:
        List of line primitives forming the arc
    """
    center = np.array(center, dtype=np.float32)
    lines = []
    
    # Convert to radians
    start_rad = np.radians(start_angle)
    end_rad = np.radians(end_angle)
    angle_range = end_rad - start_rad
    
    for i in range(segments):
        t1 = start_rad + (i / segments) * angle_range
        t2 = start_rad + ((i + 1) / segments) * angle_range
        
        p1 = center + radius * np.array([np.cos(t1), np.sin(t1), 0], dtype=np.float32)
        p2 = center + radius * np.array([np.cos(t2), np.sin(t2), 0], dtype=np.float32)
        
        lines.append(sketch_line(p1, p2, thickness=0.05))
    
    return lines


def sketch_spline(points: list[np.ndarray], segments_per_span: int = 4) -> list[Prim]:
    """Create a smooth spline through points.
    
    Args:
        points: List of control points
        segments_per_span: Number of segments between each pair of points
    
    Returns:
        List of line primitives approximating the spline
    """
    if len(points) < 2:
        return []
    
    lines = []
    
    # Simple linear interpolation for now (can be upgraded to Catmull-Rom or Bezier)
    for i in range(len(points) - 1):
        p1 = np.array(points[i], dtype=np.float32)
        p2 = np.array(points[i + 1], dtype=np.float32)
        
        for j in range(segments_per_span):
            t1 = j / segments_per_span
            t2 = (j + 1) / segments_per_span
            
            point1 = (1 - t1) * p1 + t1 * p2
            point2 = (1 - t2) * p1 + t2 * p2
            
            lines.append(sketch_line(point1, point2, thickness=0.05))
    
    return lines
