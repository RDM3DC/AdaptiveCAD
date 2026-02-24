"""Mesh-based SDF Primitive

Special primitive type that evaluates SDF from an imported triangle mesh.
Uses spatial acceleration for fast queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from adaptivecad.app.mesh_import import MeshSDFConverter


class MeshSDF:
    """SDF primitive backed by a triangle mesh."""
    
    def __init__(self, converter: 'MeshSDFConverter', cache_resolution: int = 64):
        """Initialize mesh SDF.
        
        Args:
            converter: Mesh to SDF converter
            cache_resolution: Resolution for distance field cache (per axis)
        """
        self.converter = converter
        self.cache_resolution = cache_resolution
        self.cache: Optional[np.ndarray] = None
        self.cache_bounds_min: Optional[np.ndarray] = None
        self.cache_bounds_max: Optional[np.ndarray] = None
        
        # Build cache for faster queries
        self._build_cache()
    
    def _build_cache(self):
        """Pre-compute distance field on a grid for faster queries."""
        res = self.cache_resolution
        
        # Add padding to bounds
        padding = 0.1
        bounds_min = self.converter.bounds_min - padding
        bounds_max = self.converter.bounds_max + padding
        
        self.cache_bounds_min = bounds_min
        self.cache_bounds_max = bounds_max
        
        # Create grid
        x = np.linspace(bounds_min[0], bounds_max[0], res)
        y = np.linspace(bounds_min[1], bounds_max[1], res)
        z = np.linspace(bounds_min[2], bounds_max[2], res)
        
        # Sample distances
        self.cache = np.zeros((res, res, res), dtype=np.float32)
        
        for i, xi in enumerate(x):
            for j, yj in enumerate(y):
                for k, zk in enumerate(z):
                    p = np.array([xi, yj, zk])
                    self.cache[i, j, k] = self.converter.signed_distance(p, ray_count=3)
    
    def evaluate(self, point: np.ndarray) -> float:
        """Evaluate signed distance at a point.
        
        Args:
            point: 3D point to query
        
        Returns:
            Signed distance (negative inside, positive outside)
        """
        # Check if we can use cache
        if self.cache is not None:
            # Try trilinear interpolation from cache
            dist = self._interpolate_cache(point)
            if dist is not None:
                return dist
        
        # Fall back to direct computation
        return self.converter.signed_distance(point, ray_count=3)
    
    def _interpolate_cache(self, point: np.ndarray) -> Optional[float]:
        """Interpolate distance from cache grid."""
        if self.cache is None or self.cache_bounds_min is None or self.cache_bounds_max is None:
            return None
        
        # Check if point is in cache bounds
        if np.any(point < self.cache_bounds_min) or np.any(point > self.cache_bounds_max):
            return None
        
        # Normalize to [0, 1]
        norm = (point - self.cache_bounds_min) / (self.cache_bounds_max - self.cache_bounds_min)
        
        # Scale to grid indices
        res = self.cache_resolution
        indices = norm * (res - 1)
        
        # Clamp
        indices = np.clip(indices, 0, res - 1)
        
        # Trilinear interpolation
        i0 = int(np.floor(indices[0]))
        j0 = int(np.floor(indices[1]))
        k0 = int(np.floor(indices[2]))
        i1 = min(i0 + 1, res - 1)
        j1 = min(j0 + 1, res - 1)
        k1 = min(k0 + 1, res - 1)
        
        # Interpolation weights
        fx = indices[0] - i0
        fy = indices[1] - j0
        fz = indices[2] - k0
        
        # Sample 8 corners
        c000 = self.cache[i0, j0, k0]
        c001 = self.cache[i0, j0, k1]
        c010 = self.cache[i0, j1, k0]
        c011 = self.cache[i0, j1, k1]
        c100 = self.cache[i1, j0, k0]
        c101 = self.cache[i1, j0, k1]
        c110 = self.cache[i1, j1, k0]
        c111 = self.cache[i1, j1, k1]
        
        # Trilinear interpolation
        c00 = c000 * (1 - fx) + c100 * fx
        c01 = c001 * (1 - fx) + c101 * fx
        c10 = c010 * (1 - fx) + c110 * fx
        c11 = c011 * (1 - fx) + c111 * fx
        
        c0 = c00 * (1 - fy) + c10 * fy
        c1 = c01 * (1 - fy) + c11 * fy
        
        result = c0 * (1 - fz) + c1 * fz
        
        return float(result)
