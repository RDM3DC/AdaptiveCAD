"""Measurement and Analysis Tools

Provides measurement tools for distances, angles, volumes, and surface areas.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

from adaptivecad.aacore.sdf import Prim, Scene

log = logging.getLogger(__name__)


def measure_distance_between_prims(prim1: Prim, prim2: Prim) -> float:
    """Measure distance between centers of two primitives."""
    pos1 = prim1.xform.M[:3, 3]
    pos2 = prim2.xform.M[:3, 3]
    return float(np.linalg.norm(pos2 - pos1))


def measure_point_to_point(p1: np.ndarray, p2: np.ndarray) -> float:
    """Measure distance between two 3D points."""
    return float(np.linalg.norm(p2 - p1))


def measure_angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    """Measure angle between two vectors in degrees."""
    v1_norm = v1 / (np.linalg.norm(v1) + 1e-9)
    v2_norm = v2 / (np.linalg.norm(v2) + 1e-9)
    cos_angle = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def estimate_volume_sdf(scene: Scene, prim_index: int, resolution: int = 50) -> float:
    """Estimate volume of a primitive using SDF sampling.
    
    Args:
        scene: Scene containing the primitive
        prim_index: Index of primitive to measure
        resolution: Number of samples per axis
        
    Returns:
        Estimated volume in cubic units
    """
    if prim_index < 0 or prim_index >= len(scene.prims):
        return 0.0
    
    prim = scene.prims[prim_index]
    
    # Get approximate bounds
    pos = prim.xform.M[:3, 3]
    scale_max = np.max(np.abs(prim.scale))
    extent = scale_max * 3.0  # Sample a bit beyond expected size
    
    # Create sampling grid
    x = np.linspace(pos[0] - extent, pos[0] + extent, resolution)
    y = np.linspace(pos[1] - extent, pos[1] + extent, resolution)
    z = np.linspace(pos[2] - extent, pos[2] + extent, resolution)
    
    # Sample SDF
    inside_count = 0
    resolution ** 3
    
    for xi in x:
        for yi in y:
            for zi in z:
                p = np.array([xi, yi, zi], dtype=np.float64)
                d, _, _ = scene.sdf(p)
                if d < 0:  # Inside the surface
                    inside_count += 1
    
    # Calculate volume
    cell_volume = (2 * extent / resolution) ** 3
    return inside_count * cell_volume


def estimate_surface_area_sdf(scene: Scene, prim_index: int, resolution: int = 50) -> float:
    """Estimate surface area of a primitive using SDF sampling.
    
    Args:
        scene: Scene containing the primitive
        prim_index: Index of primitive to measure
        resolution: Number of samples per axis
        
    Returns:
        Estimated surface area in square units
    """
    if prim_index < 0 or prim_index >= len(scene.prims):
        return 0.0
    
    prim = scene.prims[prim_index]
    
    # Get approximate bounds
    pos = prim.xform.M[:3, 3]
    scale_max = np.max(np.abs(prim.scale))
    extent = scale_max * 3.0
    
    # Create sampling grid
    x = np.linspace(pos[0] - extent, pos[0] + extent, resolution)
    y = np.linspace(pos[1] - extent, pos[1] + extent, resolution)
    z = np.linspace(pos[2] - extent, pos[2] + extent, resolution)
    
    # Count cells near the surface (|SDF| < threshold)
    threshold = extent / resolution * 0.5
    surface_count = 0
    
    for xi in x:
        for yi in y:
            for zi in z:
                p = np.array([xi, yi, zi], dtype=np.float64)
                d, _, _ = scene.sdf(p)
                if abs(d) < threshold:
                    surface_count += 1
    
    # Calculate surface area
    cell_area = (2 * extent / resolution) ** 2
    return surface_count * cell_area


class MeasurementTool:
    """Interactive measurement tool for the viewport."""
    
    def __init__(self):
        self.points: list[np.ndarray] = []
        self.mode: str = 'distance'  # 'distance', 'angle', 'area'
        
    def add_point(self, point: np.ndarray):
        """Add a measurement point."""
        self.points.append(point.copy())
        
    def clear(self):
        """Clear all measurement points."""
        self.points.clear()
        
    def get_result(self) -> Optional[Tuple[str, float]]:
        """Get the current measurement result.
        
        Returns:
            (description, value) or None
        """
        if self.mode == 'distance':
            if len(self.points) >= 2:
                dist = measure_point_to_point(self.points[-2], self.points[-1])
                return (f"Distance: {dist:.4f}", dist)
        elif self.mode == 'angle':
            if len(self.points) >= 3:
                # Angle at the middle point
                v1 = self.points[-3] - self.points[-2]
                v2 = self.points[-1] - self.points[-2]
                angle = measure_angle_between_vectors(v1, v2)
                return (f"Angle: {angle:.2f}°", angle)
        
        return None
