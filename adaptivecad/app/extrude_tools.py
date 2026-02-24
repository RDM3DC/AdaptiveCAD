"""Extrude and Revolve Tools

Convert 2D profiles to 3D shapes through extrusion and revolution.
"""

import numpy as np

from ..aacore.sdf import KIND_BOX, KIND_CAPSULE, Prim


def extrude_rectangle(width: float, height: float, depth: float, 
                     centered: bool = True) -> Prim:
    """Create a box by extruding a rectangle.
    
    Args:
        width: Rectangle width (X)
        height: Rectangle height (Y)
        depth: Extrusion depth (Z)
        centered: If True, center at origin. If False, start at origin.
    
    Returns:
        Extruded box primitive
    """
    size = np.array([width, height, depth], dtype=np.float32)
    transform = np.eye(4, dtype=np.float32)
    
    if not centered:
        # Shift so bottom-left-back corner is at origin
        transform[2, 3] = depth / 2
    
    return Prim(
        kind=KIND_BOX,
        transform=transform,
        size=size,
        op='solid',
        color=np.array([0.7, 0.7, 0.9, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.5
    )


def extrude_circle(radius: float, depth: float, centered: bool = True) -> Prim:
    """Create a cylinder by extruding a circle.
    
    Args:
        radius: Circle radius
        depth: Extrusion depth (Z)
        centered: If True, center at origin. If False, start at origin.
    
    Returns:
        Extruded cylinder primitive
    """
    size = np.array([radius, radius, depth], dtype=np.float32)
    transform = np.eye(4, dtype=np.float32)
    
    if not centered:
        transform[2, 3] = depth / 2
    
    return Prim(
        kind=KIND_CAPSULE,  # Capsule with height acts like cylinder
        transform=transform,
        size=size,
        op='solid',
        color=np.array([0.7, 0.9, 0.7, 1.0], dtype=np.float32),
        metallic=0.0,
        roughness=0.5
    )


def extrude_profile(prim_2d: Prim, depth: float, centered: bool = True) -> Prim:
    """Extrude a 2D primitive along the Z-axis.
    
    Args:
        prim_2d: 2D primitive to extrude (typically flat in XY plane)
        depth: Extrusion depth
        centered: If True, extrude equally in +Z and -Z
    
    Returns:
        3D extruded primitive
    """
    extruded = Prim(
        kind=prim_2d.kind,
        transform=prim_2d.transform.copy(),
        size=prim_2d.size.copy(),
        op=prim_2d.op,
        color=prim_2d.color.copy(),
        metallic=prim_2d.metallic,
        roughness=prim_2d.roughness
    )
    
    # Modify Z component of size to create depth
    extruded.size[2] = depth
    
    if not centered:
        # Shift to start at Z=0
        extruded.transform[2, 3] += depth / 2
    
    return extruded


def revolve_profile(prim_2d: Prim, axis: str = 'Z', angle: float = 360.0) -> Prim:
    """Revolve a 2D profile around an axis.
    
    For simple shapes like rectangles and circles, this creates cylinders,
    cones, spheres, and tori depending on the profile shape and position.
    
    Args:
        prim_2d: 2D primitive to revolve
        axis: Axis to revolve around ('X', 'Y', or 'Z')
        angle: Angle of revolution in degrees (360 = full revolution)
    
    Returns:
        Revolved 3D primitive
    """
    # For now, approximate revolution with appropriate 3D primitive
    # Full revolution of a circle -> sphere or torus
    # Full revolution of rectangle -> cylinder
    
    if prim_2d.kind == KIND_BOX:
        # Rectangle revolution -> Cylinder
        # Use the profile width as radius
        radius = prim_2d.size[0] / 2
        height = prim_2d.size[1]
        
        revolved = Prim(
            kind=KIND_CAPSULE,
            transform=prim_2d.transform.copy(),
            size=np.array([radius, radius, height], dtype=np.float32),
            op=prim_2d.op,
            color=prim_2d.color.copy(),
            metallic=prim_2d.metallic,
            roughness=prim_2d.roughness
        )
        
        return revolved
    
    else:
        # For other shapes, return a copy with note
        revolved = Prim(
            kind=prim_2d.kind,
            transform=prim_2d.transform.copy(),
            size=prim_2d.size.copy(),
            op=prim_2d.op,
            color=prim_2d.color.copy(),
            metallic=prim_2d.metallic,
            roughness=prim_2d.roughness
        )
        return revolved


def loft_between_profiles(profile1: Prim, profile2: Prim, steps: int = 10) -> list[Prim]:
    """Create a loft between two profiles.
    
    This interpolates between two shapes, creating a smooth transition.
    
    Args:
        profile1: First profile
        profile2: Second profile
        steps: Number of interpolation steps
    
    Returns:
        List of primitives forming the loft
    """
    loft_prims = []
    
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.5
        
        # Interpolate transform
        transform = (1 - t) * profile1.transform + t * profile2.transform
        
        # Interpolate size
        size = (1 - t) * profile1.size + t * profile2.size
        
        # Interpolate color
        color = (1 - t) * profile1.color + t * profile2.color
        
        prim = Prim(
            kind=profile1.kind,  # Use first profile's kind
            transform=transform,
            size=size,
            op='solid',
            color=color,
            metallic=(1 - t) * profile1.metallic + t * profile2.metallic,
            roughness=(1 - t) * profile1.roughness + t * profile2.roughness
        )
        
        loft_prims.append(prim)
    
    return loft_prims


def sweep_along_path(profile: Prim, path_points: np.ndarray, 
                     scale_along_path: bool = False) -> list[Prim]:
    """Sweep a profile along a path.
    
    Args:
        profile: 2D profile to sweep
        path_points: Nx3 array of path points
        scale_along_path: If True, scale profile along path
    
    Returns:
        List of primitives along the path
    """
    swept_prims = []
    n_points = len(path_points)
    
    for i, point in enumerate(path_points):
        # Create a copy of the profile
        prim = Prim(
            kind=profile.kind,
            transform=profile.transform.copy(),
            size=profile.size.copy(),
            op=profile.op,
            color=profile.color.copy(),
            metallic=profile.metallic,
            roughness=profile.roughness
        )
        
        # Translate to path point
        prim.transform[0, 3] = point[0]
        prim.transform[1, 3] = point[1]
        prim.transform[2, 3] = point[2]
        
        # Optional scaling
        if scale_along_path:
            t = i / (n_points - 1) if n_points > 1 else 0.5
            scale = 1.0 - 0.5 * t  # Taper from 1.0 to 0.5
            prim.size *= scale
        
        swept_prims.append(prim)
    
    return swept_prims
