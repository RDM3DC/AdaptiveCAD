"""Array and Pattern Tools

Provides linear, circular, and grid array operations for primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from adaptivecad.aacore.math import Xform, rot_x, rot_y, rot_z
from adaptivecad.aacore.sdf import Prim


@dataclass
class ArrayParams:
    """Parameters for array operations."""
    count: int = 3
    offset_x: float = 1.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    rotate_x: float = 0.0
    rotate_y: float = 0.0
    rotate_z: float = 0.0
    scale_factor: float = 1.0


def linear_array(prim: Prim, count: int, offset: np.ndarray) -> List[Prim]:
    """Create a linear array of primitives.
    
    Args:
        prim: Source primitive to array
        count: Number of copies (including original)
        offset: XYZ offset per step
        
    Returns:
        List of primitives (original + copies)
    """
    result = [prim]
    
    for i in range(1, count):
        new_prim = Prim(
            kind=prim.kind,
            params=prim.params.copy(),
            beta=prim.beta,
            pid=0,  # Will be reassigned
            op=prim.op,
            color=prim.color.copy()
        )
        
        # Apply cumulative offset
        new_xform = Xform()
        new_xform.M = prim.xform.M.copy()
        new_xform.M[:3, 3] += offset * i
        new_prim.xform = new_xform
        new_prim.euler = prim.euler.copy()
        new_prim.scale = prim.scale.copy()
        
        result.append(new_prim)
    
    return result


def circular_array(prim: Prim, count: int, radius: float, axis: str = 'z', full_circle: bool = True) -> List[Prim]:
    """Create a circular array of primitives.
    
    Args:
        prim: Source primitive to array
        count: Number of copies (including original)
        radius: Radius of the circle
        axis: Rotation axis ('x', 'y', or 'z')
        full_circle: If True, distribute over 360°, else over 360°-step
        
    Returns:
        List of primitives arranged in a circle
    """
    result = []
    
    # Calculate angular step
    if full_circle:
        angle_step = 360.0 / count
    else:
        angle_step = 360.0 / (count - 1) if count > 1 else 0.0
    
    for i in range(count):
        angle_deg = i * angle_step
        angle_rad = np.deg2rad(angle_deg)
        
        new_prim = Prim(
            kind=prim.kind,
            params=prim.params.copy(),
            beta=prim.beta,
            pid=0,
            op=prim.op,
            color=prim.color.copy()
        )
        
        # Calculate position on circle
        if axis == 'z':
            offset = np.array([radius * np.cos(angle_rad), radius * np.sin(angle_rad), 0.0])
            rot_matrix = rot_z(angle_deg)
        elif axis == 'y':
            offset = np.array([radius * np.cos(angle_rad), 0.0, radius * np.sin(angle_rad)])
            rot_matrix = rot_y(angle_deg)
        else:  # 'x'
            offset = np.array([0.0, radius * np.cos(angle_rad), radius * np.sin(angle_rad)])
            rot_matrix = rot_x(angle_deg)
        
        # Apply transform
        new_xform = Xform()
        new_xform.M = prim.xform.M.copy()
        
        # Add rotation and translation
        base_pos = prim.xform.M[:3, 3].copy()
        new_xform.M[:3, :3] = rot_matrix[:3, :3] @ prim.xform.M[:3, :3]
        new_xform.M[:3, 3] = base_pos + offset
        
        new_prim.xform = new_xform
        new_prim.euler = prim.euler.copy()
        new_prim.scale = prim.scale.copy()
        
        result.append(new_prim)
    
    return result


def grid_array(prim: Prim, count_x: int, count_y: int, count_z: int,
               spacing_x: float, spacing_y: float, spacing_z: float) -> List[Prim]:
    """Create a 3D grid array of primitives.
    
    Args:
        prim: Source primitive
        count_x, count_y, count_z: Number of copies in each axis
        spacing_x, spacing_y, spacing_z: Spacing between copies
        
    Returns:
        List of primitives arranged in a grid
    """
    result = []
    
    for ix in range(count_x):
        for iy in range(count_y):
            for iz in range(count_z):
                new_prim = Prim(
                    kind=prim.kind,
                    params=prim.params.copy(),
                    beta=prim.beta,
                    pid=0,
                    op=prim.op,
                    color=prim.color.copy()
                )
                
                # Calculate offset
                offset = np.array([
                    ix * spacing_x,
                    iy * spacing_y,
                    iz * spacing_z
                ], dtype=np.float32)
                
                # Apply transform
                new_xform = Xform()
                new_xform.M = prim.xform.M.copy()
                new_xform.M[:3, 3] += offset
                new_prim.xform = new_xform
                new_prim.euler = prim.euler.copy()
                new_prim.scale = prim.scale.copy()
                
                result.append(new_prim)
    
    return result


def mirror_primitive(prim: Prim, axis: str, offset: float = 0.0) -> Prim:
    """Mirror a primitive across an axis.
    
    Args:
        prim: Source primitive
        axis: Mirror axis ('x', 'y', or 'z')
        offset: Offset of the mirror plane along the axis
        
    Returns:
        Mirrored primitive
    """
    new_prim = Prim(
        kind=prim.kind,
        params=prim.params.copy(),
        beta=prim.beta,
        pid=0,
        op=prim.op,
        color=prim.color.copy()
    )
    
    # Create mirror transform
    mirror_scale = np.eye(4, dtype=np.float32)
    axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    mirror_scale[axis_idx, axis_idx] = -1.0
    
    # Get original position
    pos = prim.xform.M[:3, 3].copy()
    
    # Mirror position relative to offset
    pos[axis_idx] = 2.0 * offset - pos[axis_idx]
    
    # Apply mirrored transform
    new_xform = Xform()
    new_xform.M = mirror_scale @ prim.xform.M
    new_xform.M[:3, 3] = pos
    new_prim.xform = new_xform
    
    # Mirror scale
    new_scale = prim.scale.copy()
    new_scale[axis_idx] *= -1.0
    new_prim.scale = new_scale
    new_prim.euler = prim.euler.copy()
    
    return new_prim
