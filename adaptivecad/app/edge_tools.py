"""Edge Modification Tools

Fillet, chamfer, and edge smoothing operations for SDF primitives.
"""

import numpy as np

from ..aacore.sdf import Prim


def apply_fillet(prim: Prim, radius: float = 0.5) -> Prim:
    """Apply fillet (rounded edges) to a primitive using SDF blending.
    
    Args:
        prim: The primitive to fillet
        radius: Fillet radius (positive = round outward, negative = round inward)
    
    Returns:
        Modified primitive with fillet applied
    """
    # Create a copy to avoid modifying original
    from ..aacore.sdf import Xform
    filleted = Prim(
        kind=prim.kind,
        params=list(prim.params),
        xform=Xform(),
        op=prim.op,
        color=tuple(prim.color[:3])
    )
    filleted.xform.M = prim.xform.M.copy()
    
    # Store fillet parameters for SDF evaluation
    # Fillet is implemented as SDF offset: d' = d - r
    if not hasattr(filleted, '_fillet_radius'):
        filleted._fillet_radius = 0.0
    filleted._fillet_radius += radius
    
    return filleted


def apply_chamfer(prim: Prim, distance: float = 0.5) -> Prim:
    """Apply chamfer (beveled edges) to a primitive.
    
    Args:
        prim: The primitive to chamfer
        distance: Chamfer distance from edge
    
    Returns:
        Modified primitive with chamfer applied
    """
    # Create a copy
    from ..aacore.sdf import Xform
    chamfered = Prim(
        kind=prim.kind,
        params=list(prim.params),
        xform=Xform(),
        op=prim.op,
        color=tuple(prim.color[:3])
    )
    chamfered.xform.M = prim.xform.M.copy()
    
    # Store chamfer parameters
    # Chamfer is similar to fillet but with linear transition
    if not hasattr(chamfered, '_chamfer_distance'):
        chamfered._chamfer_distance = 0.0
    chamfered._chamfer_distance += distance
    
    return chamfered


def round_edges_smooth(prims: list[Prim], blend_radius: float = 0.2) -> list[Prim]:
    """Smooth the edges between multiple primitives using SDF blending.
    
    This creates smooth unions between primitives instead of sharp intersections.
    
    Args:
        prims: List of primitives to blend
        blend_radius: Radius of the blending operation
    
    Returns:
        List of primitives with smooth blending applied
    """
    result = []
    for prim in prims:
        smoothed = Prim(
            kind=prim.kind,
            transform=prim.transform.copy(),
            size=prim.size.copy(),
            op=prim.op,
            color=prim.color.copy(),
            metallic=prim.metallic,
            roughness=prim.roughness
        )
        
        # Mark for smooth union operation
        if not hasattr(smoothed, '_smooth_blend_radius'):
            smoothed._smooth_blend_radius = 0.0
        smoothed._smooth_blend_radius = blend_radius
        
        result.append(smoothed)
    
    return result


def sharpen_edges(prim: Prim, amount: float = 0.1) -> Prim:
    """Sharpen edges by applying negative offset.
    
    Args:
        prim: The primitive to sharpen
        amount: Amount to sharpen (makes edges crisper)
    
    Returns:
        Modified primitive with sharpened edges
    """
    return apply_fillet(prim, -amount)


# SDF blending functions for smooth operations
def sdf_smooth_union(d1: float, d2: float, k: float = 0.2) -> float:
    """Smooth minimum (union) of two SDF values.
    
    Args:
        d1, d2: SDF distances
        k: Smoothing radius
    
    Returns:
        Smoothly blended minimum distance
    """
    h = np.clip(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0)
    return d2 * (1 - h) + d1 * h - k * h * (1 - h)


def sdf_smooth_subtract(d1: float, d2: float, k: float = 0.2) -> float:
    """Smooth subtraction of two SDF values.
    
    Args:
        d1: Base distance
        d2: Subtracting distance
        k: Smoothing radius
    
    Returns:
        Smoothly blended subtraction
    """
    h = np.clip(0.5 - 0.5 * (d2 + d1) / k, 0.0, 1.0)
    return d2 * h + d1 * (1 - h) + k * h * (1 - h)


def sdf_smooth_intersect(d1: float, d2: float, k: float = 0.2) -> float:
    """Smooth intersection of two SDF values.
    
    Args:
        d1, d2: SDF distances
        k: Smoothing radius
    
    Returns:
        Smoothly blended maximum distance
    """
    h = np.clip(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0)
    return d2 * (1 - h) + d1 * h + k * h * (1 - h)
