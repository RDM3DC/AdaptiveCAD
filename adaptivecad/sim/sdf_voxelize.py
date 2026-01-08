from __future__ import annotations

import numpy as np


def voxel_grid(extent: float, res: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return X,Y,Z grids of voxel centers over [-extent, extent]^3."""
    r = int(res)
    e = float(extent)
    lin = np.linspace(-e, e, r, dtype=np.float32)
    X, Y, Z = np.meshgrid(lin, lin, lin, indexing="xy")
    return X, Y, Z


def voxelize_scene(scene, *, extent: float, res: int) -> tuple[np.ndarray, np.ndarray]:
    """Sample SDF on a 3D grid.

    Returns:
      dist: (res,res,res) float32 signed distance
      solid: (res,res,res) bool where dist<=0

    Notes:
      CPU SDF evaluation is scalar; this is intentionally simple (MVP).
    """
    X, Y, Z = voxel_grid(extent, res)
    dist = np.empty((res, res, res), dtype=np.float32)

    # Loop in a cache-friendly order.
    for k in range(res):
        for j in range(res):
            for i in range(res):
                d, _, _ = scene.sdf((float(X[j, i, k]), float(Y[j, i, k]), float(Z[j, i, k])))
                dist[j, i, k] = float(d)

    solid = dist <= 0.0
    return dist, solid
