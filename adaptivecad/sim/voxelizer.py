"""Voxelize analytic SDF scenes for vibration simulation."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np


def _build_scene(scene_list: list[dict]):
    """Build an SDF Scene from a list of primitive dicts."""
    from adaptivecad.aacore.sdf import Prim, Scene

    def op_from_json(v):
        if isinstance(v, str):
            t = v.strip().lower()
            if t in ("subtract", "sub"):
                return "subtract"
            if t in ("intersect", "and"):
                return "intersect"
            return "solid"
        try:
            i = int(v or 0)
        except Exception:
            i = 0
        return "subtract" if i == 1 else ("intersect" if i == 2 else "solid")

    scene = Scene()
    scene.prims.clear()

    for entry in scene_list:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", "")).strip().lower()
        if not kind:
            continue

        params = entry.get("params")
        if not isinstance(params, list):
            params = [0.5, 0.0, 0.0, 0.0]

        beta = float(entry.get("beta", 0.0) or 0.0)
        op = op_from_json(entry.get("op", 0))

        color = entry.get("color")
        if isinstance(color, list) and len(color) >= 3:
            col = (float(color[0]), float(color[1]), float(color[2]))
        else:
            col = (0.85, 0.75, 0.55)

        pr = Prim(kind, [float(x) for x in params], beta=beta, op=op, color=col)

        # Transforms
        pos = entry.get("pos")
        euler = entry.get("euler")
        scale = entry.get("scale")

        def f3(x):
            return [float(x[0]), float(x[1]), float(x[2])]

        try:
            pr.set_transform(
                pos=f3(pos) if isinstance(pos, list) and len(pos) >= 3 else None,
                euler=f3(euler) if isinstance(euler, list) and len(euler) >= 3 else None,
                scale=f3(scale) if isinstance(scale, list) and len(scale) >= 3 else None,
            )
        except Exception:
            pass

        scene.add(pr)

    return scene


def voxelize_sdf_scene(
    scene_list: list[dict],
    *,
    extent: float = 1.5,
    resolution: int = 24,
    iso: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Voxelize an analytic SDF scene into a boolean solid mask.

    Args:
        scene_list: List of SDF primitive dicts (kind, pos, params, op, ...)
        extent: Half-size of the sampling cube (centered at origin)
        resolution: Number of voxels per axis
        iso: Isosurface threshold (inside if sdf < iso)

    Returns:
        solid: (res, res, res) boolean array, True where solid
        dist: (res, res, res) float32 signed distance field
        voxel_size: Edge length of each voxel in world units
    """
    scene = _build_scene(scene_list)

    res = int(resolution)
    ext = float(extent)
    voxel_size = (2.0 * ext) / res

    # Voxel centers
    lin = np.linspace(-ext + voxel_size / 2, ext - voxel_size / 2, res, dtype=np.float32)
    X, Y, Z = np.meshgrid(lin, lin, lin, indexing="ij")

    # Evaluate SDF at all points
    dist = np.empty((res, res, res), dtype=np.float32)
    for i in range(res):
        for j in range(res):
            for k in range(res):
                d, _, _ = scene.sdf((float(X[i, j, k]), float(Y[i, j, k]), float(Z[i, j, k])))
                dist[i, j, k] = float(d)

    # Inside = sdf < iso
    solid = dist < float(iso)

    return solid, dist, voxel_size


def load_and_voxelize_ama(
    ama_path: str | Path,
    *,
    extent: float = 1.5,
    resolution: int = 24,
    iso: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, float, list[dict]]:
    """Load an .ama with analytic/scene.json (list format) and voxelize it.

    Returns:
        solid, dist, voxel_size, scene_list
    """
    ama_path = Path(ama_path)
    if not ama_path.exists():
        raise FileNotFoundError(f"AMA not found: {ama_path}")

    with zipfile.ZipFile(ama_path, "r") as zf:
        if "analytic/scene.json" not in zf.namelist():
            raise ValueError(f"No analytic/scene.json in {ama_path}")

        scene_data = json.loads(zf.read("analytic/scene.json").decode("utf-8"))

    # Must be a list (not a dict with "layers")
    if isinstance(scene_data, dict):
        raise ValueError(
            "scene.json is a dict (volume/field AMA), not a list (analytic SDF). "
            "This voxelizer only supports list-based analytic scenes."
        )

    if not isinstance(scene_data, list):
        raise ValueError("scene.json must be a list of SDF primitives")

    solid, dist, voxel_size = voxelize_sdf_scene(
        scene_data, extent=extent, resolution=resolution, iso=iso
    )

    return solid, dist, voxel_size, scene_data


__all__ = ["voxelize_sdf_scene", "load_and_voxelize_ama"]
