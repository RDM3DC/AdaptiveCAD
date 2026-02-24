"""Shell and Offset Tools

Hollowing and surface offset operations for SDF primitives.
"""

from ..aacore.sdf import Prim, Scene


def shell_primitive(prim: Prim, thickness: float = 1.0, inward: bool = True) -> Prim:
    """Create a hollow shell from a solid primitive.
    
    This creates a thin-walled version of the primitive by offsetting the SDF.
    
    Args:
        prim: The primitive to shell
        thickness: Wall thickness
        inward: If True, shell inward (subtract). If False, add outward shell.
    
    Returns:
        Modified primitive representing the shell
    """
    shelled = Prim(
        kind=prim.kind,
        transform=prim.transform.copy(),
        size=prim.size.copy(),
        op=prim.op,
        color=prim.color.copy(),
        metallic=prim.metallic,
        roughness=prim.roughness
    )
    
    # Store shell parameters
    shelled._shell_thickness = thickness
    shelled._shell_inward = inward
    
    return shelled


def offset_surface(prim: Prim, distance: float = 0.5) -> Prim:
    """Offset the surface of a primitive by a distance.
    
    Positive distance expands the shape, negative shrinks it.
    
    Args:
        prim: The primitive to offset
        distance: Offset distance (positive = expand, negative = shrink)
    
    Returns:
        Modified primitive with offset applied
    """
    offset = Prim(
        kind=prim.kind,
        transform=prim.transform.copy(),
        size=prim.size.copy(),
        op=prim.op,
        color=prim.color.copy(),
        metallic=prim.metallic,
        roughness=prim.roughness
    )
    
    # Offset is implemented as SDF subtraction: d' = d - offset
    if not hasattr(offset, '_surface_offset'):
        offset._surface_offset = 0.0
    offset._surface_offset += distance
    
    return offset


def thicken_surface(prim: Prim, thickness: float = 1.0) -> Prim:
    """Thicken a thin surface into a solid.
    
    This creates a solid region around the zero-level set of the SDF.
    
    Args:
        prim: The primitive (can be thin/sheet-like)
        thickness: Total thickness (half on each side of surface)
    
    Returns:
        Thickened primitive
    """
    thickened = Prim(
        kind=prim.kind,
        transform=prim.transform.copy(),
        size=prim.size.copy(),
        op=prim.op,
        color=prim.color.copy(),
        metallic=prim.metallic,
        roughness=prim.roughness
    )
    
    # Store thickening parameters
    thickened._surface_thickness = thickness
    
    return thickened


def hollow_out(scene: Scene, primitives: list[Prim], thickness: float = 1.0) -> Scene:
    """Hollow out selected primitives in a scene.
    
    Args:
        scene: The scene containing primitives
        primitives: List of primitives to hollow
        thickness: Wall thickness
    
    Returns:
        Modified scene with hollowed primitives
    """
    new_prims = []
    prim_ids = {id(p) for p in primitives}
    
    for prim in scene.prims:
        if id(prim) in prim_ids:
            new_prims.append(shell_primitive(prim, thickness))
        else:
            new_prims.append(prim)
    
    new_scene = Scene()
    new_scene.prims = new_prims
    return new_scene


def evaluate_shell_sdf(base_sdf: float, thickness: float, inward: bool = True) -> float:
    """Evaluate the SDF for a shell operation.
    
    Args:
        base_sdf: Original SDF value
        thickness: Shell thickness
        inward: Shell direction
    
    Returns:
        Modified SDF value representing the shell
    """
    if inward:
        # Shell is the region between surface and inward offset
        inner_sdf = base_sdf + thickness
        # Shell is where: base_sdf < 0 AND inner_sdf > 0
        # SDF of shell = max(-base_sdf, inner_sdf)
        return max(-base_sdf, inner_sdf)
    else:
        # Outward shell
        outer_sdf = base_sdf - thickness
        return max(base_sdf, -outer_sdf)


def evaluate_offset_sdf(base_sdf: float, offset: float) -> float:
    """Evaluate the SDF for an offset operation.
    
    Args:
        base_sdf: Original SDF value
        offset: Offset distance
    
    Returns:
        Offset SDF value
    """
    return base_sdf - offset


def evaluate_thickness_sdf(base_sdf: float, thickness: float) -> float:
    """Evaluate the SDF for a thickening operation.
    
    Args:
        base_sdf: Original SDF value (can represent a thin surface)
        thickness: Thickness to add
    
    Returns:
        Thickened SDF value
    """
    # Solid region is where |sdf| < thickness/2
    return abs(base_sdf) - thickness / 2.0
