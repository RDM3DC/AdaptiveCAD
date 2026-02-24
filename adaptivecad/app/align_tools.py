"""Alignment and Snapping Tools

Provides alignment operations for primitives relative to each other or to a grid.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from adaptivecad.aacore.sdf import Prim


def get_prim_bounds(prim: Prim) -> tuple[np.ndarray, np.ndarray]:
    """Get approximate axis-aligned bounding box for a primitive.
    
    Returns (min_point, max_point) in world space.
    Note: This is a simple approximation based on transform position.
    """
    pos = prim.xform.M[:3, 3]
    # Rough estimate: use scale as radius
    scale_max = np.max(np.abs(prim.scale))
    extent = np.ones(3) * scale_max * 2.0
    
    return pos - extent, pos + extent


def get_selection_bounds(prims: List[Prim]) -> tuple[np.ndarray, np.ndarray]:
    """Get combined bounding box for multiple primitives."""
    if not prims:
        return np.zeros(3), np.zeros(3)
    
    mins = []
    maxs = []
    for prim in prims:
        min_pt, max_pt = get_prim_bounds(prim)
        mins.append(min_pt)
        maxs.append(max_pt)
    
    return np.min(mins, axis=0), np.max(maxs, axis=0)


def align_primitives(prims: List[Prim], mode: str, axis: str) -> None:
    """Align primitives to each other.
    
    Args:
        prims: List of primitives to align
        mode: 'min', 'center', or 'max'
        axis: 'x', 'y', or 'z'
    """
    if len(prims) < 2:
        return
    
    axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    
    # Get reference value from first primitive
    bounds = [get_prim_bounds(p) for p in prims]
    
    if mode == 'min':
        # Align to minimum
        target_val = min(b[0][axis_idx] for b in bounds)
        for prim, (min_pt, _) in zip(prims, bounds):
            offset = target_val - min_pt[axis_idx]
            prim.xform.M[axis_idx, 3] += offset
    elif mode == 'max':
        # Align to maximum
        target_val = max(b[1][axis_idx] for b in bounds)
        for prim, (_, max_pt) in zip(prims, bounds):
            offset = target_val - max_pt[axis_idx]
            prim.xform.M[axis_idx, 3] += offset
    else:  # 'center'
        # Align to center
        centers = [(b[0][axis_idx] + b[1][axis_idx]) / 2.0 for b in bounds]
        target_val = sum(centers) / len(centers)
        for prim, center in zip(prims, centers):
            offset = target_val - center
            prim.xform.M[axis_idx, 3] += offset


def distribute_primitives(prims: List[Prim], axis: str, spacing: Optional[float] = None) -> None:
    """Distribute primitives evenly along an axis.
    
    Args:
        prims: List of primitives to distribute
        axis: 'x', 'y', or 'z'
        spacing: If provided, use fixed spacing; otherwise distribute evenly
    """
    if len(prims) < 2:
        return
    
    axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    
    # Sort by current position
    positions = [p.xform.M[axis_idx, 3] for p in prims]
    sorted_indices = np.argsort(positions)
    sorted_prims = [prims[i] for i in sorted_indices]
    
    if spacing is not None:
        # Fixed spacing
        start_pos = sorted_prims[0].xform.M[axis_idx, 3]
        for i, prim in enumerate(sorted_prims):
            prim.xform.M[axis_idx, 3] = start_pos + i * spacing
    else:
        # Even distribution between first and last
        first_pos = sorted_prims[0].xform.M[axis_idx, 3]
        last_pos = sorted_prims[-1].xform.M[axis_idx, 3]
        
        if len(sorted_prims) > 2:
            step = (last_pos - first_pos) / (len(sorted_prims) - 1)
            for i, prim in enumerate(sorted_prims[1:-1], start=1):
                prim.xform.M[axis_idx, 3] = first_pos + i * step


def snap_to_grid(prim: Prim, grid_size: float, axes: str = 'xyz') -> None:
    """Snap primitive position to grid.
    
    Args:
        prim: Primitive to snap
        grid_size: Grid cell size
        axes: Which axes to snap (combination of 'x', 'y', 'z')
    """
    pos = prim.xform.M[:3, 3]
    
    for axis in axes:
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
        pos[axis_idx] = np.round(pos[axis_idx] / grid_size) * grid_size
    
    prim.xform.M[:3, 3] = pos


def center_selection_at_origin(prims: List[Prim]) -> None:
    """Move selection so its center is at the origin."""
    if not prims:
        return
    
    min_pt, max_pt = get_selection_bounds(prims)
    center = (min_pt + max_pt) / 2.0
    
    # Move all primitives
    for prim in prims:
        prim.xform.M[:3, 3] -= center
