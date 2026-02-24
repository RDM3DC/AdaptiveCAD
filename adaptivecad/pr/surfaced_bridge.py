"""Surfaced Bridge (Riemann surface visualization)

This module generates a *surfaced* version of a branch cut bridge: a continuous
helicoid-like ramp that connects sheets smoothly (instead of a discrete "jump").

Primary output target is an .ama archive containing a pre-built STL mesh so the
Analytic Viewport can display it directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SurfacedBridgeConfig:
    # Geometry (world units are arbitrary; viewer will auto-fit)
    r_inner: float = 0.15
    r_outer: float = 0.55

    # How many full turns around the branch point.
    # For a 2-sheet sqrt-like surface, `turns=2` (theta spans 0..4π).
    turns: float = 2.0

    # Height per full turn (2π). Total height = pitch * turns.
    pitch: float = 0.35

    # Sampling resolution
    n_theta: int = 480
    n_r: int = 64

    # Rendering robustness
    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedHandleConfig:
    """A simple genus-1 style handle: two sheets + a connecting tube."""

    # Sheet geometry (annulus in XY plane)
    sheet_r_outer: float = 0.70
    hole_r: float = 0.20

    # Separation between sheets (total distance is 2*sheet_z)
    sheet_z: float = 0.25

    # Sampling
    n_theta: int = 256
    n_r: int = 48
    n_z: int = 96

    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedMobiusConfig:
    """Parametric Möbius strip mesh."""

    R: float = 0.55
    width: float = 0.18
    twists: int = 1  # number of half-twists (1 => classic Möbius)

    n_u: int = 320
    n_v: int = 80

    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedKleinConfig:
    """Parametric Klein bottle immersion mesh (figure-8 style)."""

    a: float = 0.35  # controls the overall radius
    scale: float = 0.95

    n_u: int = 280
    n_v: int = 160

    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedBranchCutConfig:
    """Two flat sheets with a slit, glued by helical ramps (a surfaced branch cut)."""

    r_inner: float = 0.10
    r_outer: float = 0.80
    cut_angle: float = 0.20  # radians wedge removed around +X axis
    sheet_z: float = 0.20

    # ramps wind `ramp_turns` full revolutions as they rise from bottom to top
    ramp_turns: float = 1.0

    n_theta: int = 260
    n_r: int = 64
    n_s: int = 220

    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedTorusKnotRibbonConfig:
    """Ribbon swept along a torus knot with configurable twist (holonomy visible)."""

    R: float = 0.55
    r: float = 0.22
    p: int = 2
    q: int = 3

    width: float = 0.14
    twist_turns: float = 1.0  # additional twist along the loop

    n_u: int = 800
    n_v: int = 40

    two_sided: bool = True


@dataclass(frozen=True)
class SurfacedEnneperConfig:
    """Enneper minimal surface (order-1) patch."""

    extent: float = 1.65  # parameter domain half-width (u,v in [-extent, extent])
    scale: float = 0.35

    n_u: int = 220
    n_v: int = 220

    two_sided: bool = True


def _triangulate_polar_annulus(r_inner: float, r_outer: float, z: float, n_theta: int, n_r: int) -> tuple[np.ndarray, np.ndarray]:
    theta = np.linspace(0.0, 2.0 * np.pi, int(n_theta) + 1, dtype=np.float32)
    rr = np.linspace(float(r_inner), float(r_outer), int(n_r) + 1, dtype=np.float32)
    TT, RR = np.meshgrid(theta, rr, indexing="ij")
    X = RR * np.cos(TT)
    Y = RR * np.sin(TT)
    Z = np.full_like(X, float(z), dtype=np.float32)
    v = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)

    nT = int(n_theta) + 1
    nR = int(n_r) + 1

    def idx(i: int, j: int) -> int:
        return i * nR + j

    faces: list[list[int]] = []
    for i in range(nT - 1):
        for j in range(nR - 1):
            v00 = idx(i, j)
            v10 = idx(i + 1, j)
            v11 = idx(i + 1, j + 1)
            v01 = idx(i, j + 1)
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])

    return v, np.asarray(faces, dtype=np.int32)


def _triangulate_cylinder(r: float, z0: float, z1: float, n_theta: int, n_z: int) -> tuple[np.ndarray, np.ndarray]:
    theta = np.linspace(0.0, 2.0 * np.pi, int(n_theta) + 1, dtype=np.float32)
    zz = np.linspace(float(z0), float(z1), int(n_z) + 1, dtype=np.float32)
    TT, ZZ = np.meshgrid(theta, zz, indexing="ij")
    X = float(r) * np.cos(TT)
    Y = float(r) * np.sin(TT)
    v = np.stack([X, Y, ZZ], axis=-1).reshape(-1, 3).astype(np.float32)

    nT = int(n_theta) + 1
    nZ = int(n_z) + 1

    def idx(i: int, j: int) -> int:
        return i * nZ + j

    faces: list[list[int]] = []
    for i in range(nT - 1):
        for j in range(nZ - 1):
            v00 = idx(i, j)
            v10 = idx(i + 1, j)
            v11 = idx(i + 1, j + 1)
            v01 = idx(i, j + 1)
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])

    return v, np.asarray(faces, dtype=np.int32)


def build_handle_bridge_mesh(cfg: SurfacedHandleConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build a visible handle: two annular sheets at z=±sheet_z plus a tube at radius hole_r."""
    if cfg.n_theta < 8 or cfg.n_r < 2 or cfg.n_z < 2:
        raise ValueError("n_theta must be >= 8, n_r >= 2, n_z >= 2")
    if cfg.sheet_r_outer <= cfg.hole_r:
        raise ValueError("sheet_r_outer must be > hole_r")
    if cfg.hole_r <= 0 or cfg.sheet_r_outer <= 0:
        raise ValueError("radii must be > 0")
    if cfg.sheet_z <= 0:
        raise ValueError("sheet_z must be > 0")

    # Two annular sheets
    v0, f0 = _triangulate_polar_annulus(cfg.hole_r, cfg.sheet_r_outer, -cfg.sheet_z, cfg.n_theta, cfg.n_r)
    v1, f1 = _triangulate_polar_annulus(cfg.hole_r, cfg.sheet_r_outer, +cfg.sheet_z, cfg.n_theta, cfg.n_r)
    f1 = f1 + v0.shape[0]

    # Connecting tube (cylinder)
    v2, f2 = _triangulate_cylinder(cfg.hole_r, -cfg.sheet_z, +cfg.sheet_z, cfg.n_theta, cfg.n_z)
    f2 = f2 + (v0.shape[0] + v1.shape[0])

    vertices = np.concatenate([v0, v1, v2], axis=0).astype(np.float32)
    faces = np.concatenate([f0, f1, f2], axis=0).astype(np.int32)

    # Center mesh around origin
    if vertices.shape[0] > 0:
        vmin = vertices.min(axis=0)
        vmax = vertices.max(axis=0)
        center = (vmin + vmax) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def _triangulate_param_grid(n_u: int, n_v: int) -> np.ndarray:
    """Return faces for a (n_u+1) x (n_v+1) vertex grid."""
    nu = int(n_u) + 1
    nv = int(n_v) + 1

    def idx(i: int, j: int) -> int:
        return i * nv + j

    faces: list[list[int]] = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            v00 = idx(i, j)
            v10 = idx(i + 1, j)
            v11 = idx(i + 1, j + 1)
            v01 = idx(i, j + 1)
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])
    return np.asarray(faces, dtype=np.int32)


def build_mobius_mesh(cfg: SurfacedMobiusConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build a Möbius strip mesh as (V,F)."""
    if cfg.n_u < 8 or cfg.n_v < 2:
        raise ValueError("n_u must be >= 8 and n_v must be >= 2")
    if cfg.R <= 0 or cfg.width <= 0:
        raise ValueError("R and width must be > 0")

    u = np.linspace(0.0, 2.0 * np.pi, int(cfg.n_u) + 1, dtype=np.float32)
    v = np.linspace(-float(cfg.width), float(cfg.width), int(cfg.n_v) + 1, dtype=np.float32)
    UU, VV = np.meshgrid(u, v, indexing="ij")

    # Classic Möbius parameterization with configurable half-twists.
    # twist factor affects how the strip frame rotates over u.
    half_twist = float(cfg.twists) * 0.5
    c = np.cos(half_twist * UU)
    s = np.sin(half_twist * UU)

    X = (float(cfg.R) + VV * c) * np.cos(UU)
    Y = (float(cfg.R) + VV * c) * np.sin(UU)
    Z = VV * s

    vertices = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)
    faces = _triangulate_param_grid(int(cfg.n_u), int(cfg.n_v))

    # Center mesh around origin
    if vertices.shape[0] > 0:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def build_klein_bottle_mesh(cfg: SurfacedKleinConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build a Klein bottle immersion mesh as (V,F)."""
    if cfg.n_u < 8 or cfg.n_v < 8:
        raise ValueError("n_u and n_v must be >= 8")

    u = np.linspace(0.0, 2.0 * np.pi, int(cfg.n_u) + 1, dtype=np.float32)
    v = np.linspace(0.0, 2.0 * np.pi, int(cfg.n_v) + 1, dtype=np.float32)
    UU, VV = np.meshgrid(u, v, indexing="ij")

    # Figure-8 Klein bottle immersion (common visualization).
    a = float(cfg.a)
    x = (a + np.cos(UU / 2.0) * np.sin(VV) - np.sin(UU / 2.0) * np.sin(2.0 * VV)) * np.cos(UU)
    y = (a + np.cos(UU / 2.0) * np.sin(VV) - np.sin(UU / 2.0) * np.sin(2.0 * VV)) * np.sin(UU)
    z = np.sin(UU / 2.0) * np.sin(VV) + np.cos(UU / 2.0) * np.sin(2.0 * VV)

    vertices = (np.stack([x, y, z], axis=-1) * float(cfg.scale)).reshape(-1, 3).astype(np.float32)
    faces = _triangulate_param_grid(int(cfg.n_u), int(cfg.n_v))

    # Center mesh around origin
    if vertices.shape[0] > 0:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def build_branch_cut_ramp_mesh(cfg: SurfacedBranchCutConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build two annular sheets with a slit, plus ramps that glue the slit edges."""
    if cfg.n_theta < 16 or cfg.n_r < 2 or cfg.n_s < 8:
        raise ValueError("n_theta >= 16, n_r >= 2, n_s >= 8")
    if cfg.r_outer <= cfg.r_inner:
        raise ValueError("r_outer must be > r_inner")
    if cfg.sheet_z <= 0:
        raise ValueError("sheet_z must be > 0")
    if cfg.cut_angle <= 0 or cfg.cut_angle >= np.pi:
        raise ValueError("cut_angle must be in (0, π)")

    # --- two sheets (annulus with a removed wedge around +X axis) ---
    theta0 = float(cfg.cut_angle) * 0.5
    theta1 = float(2.0 * np.pi - cfg.cut_angle * 0.5)
    theta = np.linspace(theta0, theta1, int(cfg.n_theta) + 1, dtype=np.float32)
    rr = np.linspace(float(cfg.r_inner), float(cfg.r_outer), int(cfg.n_r) + 1, dtype=np.float32)
    TT, RR = np.meshgrid(theta, rr, indexing="ij")
    X = RR * np.cos(TT)
    Y = RR * np.sin(TT)

    def sheet(z: float) -> tuple[np.ndarray, np.ndarray]:
        Z = np.full_like(X, float(z), dtype=np.float32)
        v = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)
        faces = _triangulate_param_grid(int(cfg.n_theta), int(cfg.n_r))
        return v, faces

    v_bot, f_bot = sheet(-cfg.sheet_z)
    v_top, f_top = sheet(+cfg.sheet_z)
    f_top = f_top + v_bot.shape[0]

    # --- ramps that glue each slit edge bottom->top ---
    def ramp(edge_theta: float, sign: float) -> tuple[np.ndarray, np.ndarray]:
        # s runs bottom->top
        s = np.linspace(0.0, 1.0, int(cfg.n_s) + 1, dtype=np.float32)
        r = rr  # reuse same radial samples
        SS, RR2 = np.meshgrid(s, r, indexing="ij")

        # helical wrap around origin while rising
        theta_r = float(edge_theta) + sign * float(2.0 * np.pi * cfg.ramp_turns) * SS
        Xr = RR2 * np.cos(theta_r)
        Yr = RR2 * np.sin(theta_r)
        Zr = (-float(cfg.sheet_z) + 2.0 * float(cfg.sheet_z) * SS).astype(np.float32)

        v = np.stack([Xr, Yr, Zr], axis=-1).reshape(-1, 3).astype(np.float32)
        faces = _triangulate_param_grid(int(cfg.n_s), int(cfg.n_r))
        return v, faces

    # two edges of the wedge
    v_r0, f_r0 = ramp(theta0, +1.0)
    v_r1, f_r1 = ramp(theta1, -1.0)

    f_r0 = f_r0 + (v_bot.shape[0] + v_top.shape[0])
    f_r1 = f_r1 + (v_bot.shape[0] + v_top.shape[0] + v_r0.shape[0])

    vertices = np.concatenate([v_bot, v_top, v_r0, v_r1], axis=0).astype(np.float32)
    faces = np.concatenate([f_bot, f_top, f_r0, f_r1], axis=0).astype(np.int32)

    if vertices.shape[0] > 0:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def build_torus_knot_ribbon_mesh(cfg: SurfacedTorusKnotRibbonConfig) -> tuple[np.ndarray, np.ndarray]:
    """Sweep a ribbon along a (p,q) torus knot using a parallel-transport frame."""
    if cfg.n_u < 32 or cfg.n_v < 2:
        raise ValueError("n_u must be >= 32 and n_v >= 2")
    if cfg.width <= 0 or cfg.R <= 0 or cfg.r <= 0:
        raise ValueError("R, r, width must be > 0")

    u = np.linspace(0.0, 2.0 * np.pi, int(cfg.n_u) + 1, dtype=np.float32)
    v = np.linspace(-float(cfg.width), float(cfg.width), int(cfg.n_v) + 1, dtype=np.float32)

    # Torus knot centerline
    # (R + r cos(q u)) [cos(p u), sin(p u)] with z = r sin(q u)
    np.cos(u)
    np.sin(u)
    cpu = np.cos(float(cfg.p) * u)
    spu = np.sin(float(cfg.p) * u)
    cqu = np.cos(float(cfg.q) * u)
    squ = np.sin(float(cfg.q) * u)

    rad = float(cfg.R) + float(cfg.r) * cqu
    C = np.stack([rad * cpu, rad * spu, float(cfg.r) * squ], axis=1).astype(np.float32)

    # Tangents (finite difference) and normalize
    dC = np.roll(C, -1, axis=0) - np.roll(C, 1, axis=0)
    T = dC / (np.linalg.norm(dC, axis=1, keepdims=True) + 1e-9)

    # Build a stable initial normal not parallel to T[0]
    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(float(np.dot(T[0], up))) > 0.9:
        up = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    N = np.cross(T[0], up)
    N = N / (np.linalg.norm(N) + 1e-9)

    normals = np.zeros_like(T)
    normals[0] = N

    # Parallel transport along polyline
    for i in range(1, T.shape[0]):
        t0 = T[i - 1]
        t1 = T[i]
        axis = np.cross(t0, t1)
        axn = float(np.linalg.norm(axis))
        n_prev = normals[i - 1]
        if axn < 1e-8:
            normals[i] = n_prev
            continue
        axis = axis / axn
        angle = float(np.arctan2(axn, float(np.dot(t0, t1))))

        # Rodrigues rotation of n_prev about axis
        n_rot = (
            n_prev * np.cos(angle)
            + np.cross(axis, n_prev) * np.sin(angle)
            + axis * float(np.dot(axis, n_prev)) * (1.0 - np.cos(angle))
        )
        normals[i] = n_rot / (np.linalg.norm(n_rot) + 1e-9)

    binormals = np.cross(T, normals)
    binormals = binormals / (np.linalg.norm(binormals, axis=1, keepdims=True) + 1e-9)

    # Add controlled twist around the tangent (visible holonomy)
    twist = float(cfg.twist_turns) * 2.0 * np.pi * (u / (2.0 * np.pi))
    ct = np.cos(twist)[:, None]
    st = np.sin(twist)[:, None]
    Nw = normals * ct + binormals * st

    # Build vertex grid: C(u) + v * Nw(u)
    # shape (n_u+1, n_v+1, 3)
    VV = v[None, :, None]
    P = C[:, None, :] + VV * Nw[:, None, :]
    vertices = P.reshape(-1, 3).astype(np.float32)
    faces = _triangulate_param_grid(int(cfg.n_u), int(cfg.n_v))

    # Center
    if vertices.shape[0] > 0:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def build_enneper_mesh(cfg: SurfacedEnneperConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build an Enneper surface patch mesh."""
    if cfg.n_u < 16 or cfg.n_v < 16:
        raise ValueError("n_u and n_v must be >= 16")
    if cfg.extent <= 0 or cfg.scale <= 0:
        raise ValueError("extent and scale must be > 0")

    u = np.linspace(-float(cfg.extent), float(cfg.extent), int(cfg.n_u) + 1, dtype=np.float32)
    v = np.linspace(-float(cfg.extent), float(cfg.extent), int(cfg.n_v) + 1, dtype=np.float32)
    UU, VV = np.meshgrid(u, v, indexing="ij")

    # Enneper (order-1)
    X = UU - (UU**3) / 3.0 + UU * (VV**2)
    Y = VV - (VV**3) / 3.0 + VV * (UU**2)
    Z = (UU**2) - (VV**2)
    P = np.stack([X, Y, Z], axis=-1) * float(cfg.scale)

    vertices = P.reshape(-1, 3).astype(np.float32)
    faces = _triangulate_param_grid(int(cfg.n_u), int(cfg.n_v))

    if vertices.shape[0] > 0:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces.shape[0] > 0:
        faces = np.concatenate([faces, faces[:, ::-1].copy()], axis=0)

    return vertices, faces


def build_helicoid_bridge_mesh(cfg: SurfacedBridgeConfig):
    """Build a helicoid annulus mesh as (V,F).

    Parametrization:
      x = r cos(theta)
      y = r sin(theta)
      z = a * theta
    where a = pitch / (2π).

    We sample theta in [0, 2π * turns] and r in [r_inner, r_outer].

    Returns:
      vertices: (M,3) float32
      faces: (K,3) int32
    """
    if cfg.n_theta < 4 or cfg.n_r < 2:
        raise ValueError("n_theta must be >= 4 and n_r must be >= 2")
    if cfg.r_outer <= cfg.r_inner:
        raise ValueError("r_outer must be > r_inner")
    if cfg.turns <= 0:
        raise ValueError("turns must be > 0")

    theta_max = float(2.0 * np.pi * cfg.turns)
    theta = np.linspace(0.0, theta_max, int(cfg.n_theta) + 1, dtype=np.float32)
    r = np.linspace(float(cfg.r_inner), float(cfg.r_outer), int(cfg.n_r) + 1, dtype=np.float32)

    # Grid
    TT, RR = np.meshgrid(theta, r, indexing="ij")

    a = float(cfg.pitch) / float(2.0 * np.pi)
    X = RR * np.cos(TT)
    Y = RR * np.sin(TT)
    Z = a * TT

    vertices = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)

    # Faces (two triangles per quad)
    nT = int(cfg.n_theta) + 1
    nR = int(cfg.n_r) + 1

    def idx(i: int, j: int) -> int:
        return i * nR + j

    faces: list[list[int]] = []
    for i in range(nT - 1):
        for j in range(nR - 1):
            v00 = idx(i, j)
            v10 = idx(i + 1, j)
            v11 = idx(i + 1, j + 1)
            v01 = idx(i, j + 1)
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])

    faces_arr = np.asarray(faces, dtype=np.int32)

    # Center mesh around origin for viewer camera sanity.
    if vertices.shape[0] > 0:
        vmin = vertices.min(axis=0)
        vmax = vertices.max(axis=0)
        center = (vmin + vmax) * 0.5
        vertices = vertices - center

    if cfg.two_sided and faces_arr.shape[0] > 0:
        faces_rev = faces_arr[:, ::-1].copy()
        faces_arr = np.concatenate([faces_arr, faces_rev], axis=0)

    return vertices, faces_arr


def export_surfaced_bridge_as_ama(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    mesh_name: str = "mesh/surface.stl",
    field_size: int = 32,
    units: str = "mm",
    scene_colormap: str = "plasma",
    generator: str = "adaptivecad.pr.surfaced_bridge",
) -> bytes:
    """Export a pre-built surfaced-bridge mesh as an .ama archive.

    Notes:
    - The Analytic Viewport launcher always tries to load *a field* first.
      So we include a small `fields/phi.npy` even though the mesh is the star.
    """
    import hashlib
    import io
    import json
    import zipfile
    from datetime import datetime, timezone

    v = np.asarray(vertices, dtype=np.float32)
    f = np.asarray(faces, dtype=np.int32)

    # STL bytes
    stl_bytes: bytes
    if v.shape[0] > 0 and f.shape[0] > 0:
        try:
            import trimesh  # type: ignore

            mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
            stl_io = io.BytesIO()
            mesh.export(stl_io, file_type="stl")
            stl_bytes = stl_io.getvalue()
        except Exception:
            # ASCII STL fallback
            lines = ["solid surfaced_bridge"]
            for tri in f:
                v0, v1, v2 = v[int(tri[0])], v[int(tri[1])], v[int(tri[2])]
                e1, e2 = v1 - v0, v2 - v0
                n = np.cross(e1, e2)
                n_len = float(np.linalg.norm(n))
                if n_len > 1e-9:
                    n = n / n_len
                else:
                    n = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                lines.append(f"  facet normal {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
                lines.append("    outer loop")
                lines.append(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}")
                lines.append(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}")
                lines.append(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}")
                lines.append("    endloop")
                lines.append("  endfacet")
            lines.append("endsolid surfaced_bridge")
            stl_bytes = "\n".join(lines).encode("utf-8")
    else:
        stl_bytes = b"solid empty\nendsolid empty"

    # Dummy field required by launcher (keeps it simple + square)
    n = int(field_size)
    phi = np.zeros((n, n), dtype=np.float32)

    scene = {
        "layers": [
            {
                "id": "phi",
                "name": "phi",
                "field": "fields/phi.npy",
                "field_ref": "fields/phi.npy",
                "colormap": str(scene_colormap),
                "enabled": True,
            }
        ],
        "mesh": str(mesh_name),
        "render": {"mode": "mesh", "wireframe": False, "shading": "smooth"},
    }

    manifest: dict[str, Any] = {
        "type": "surfaced_bridge",
        "mesh": {"path": str(mesh_name), "format": "stl"},
        "fields": {"phi": {"shape": list(phi.shape), "dtype": "float32", "path": "fields/phi.npy"}},
    }

    provenance = {
        "generator": str(generator),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units": str(units),
        "checksum_mesh": hashlib.sha256(stl_bytes).hexdigest()[:16],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(str(mesh_name), stl_bytes)

        arr_io = io.BytesIO()
        np.save(arr_io, phi)
        zf.writestr("fields/phi.npy", arr_io.getvalue())

        zf.writestr("analytic/scene.json", json.dumps(scene, indent=2))
        zf.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("meta/provenance.json", json.dumps(provenance, indent=2))

    return buf.getvalue()


def export_analytic_scene_as_ama(
    scene_list: list[dict[str, object]],
    *,
    units: str = "mm",
    generator: str = "adaptivecad.pr.surfaced_bridge",
) -> bytes:
    """Export a true-analytic SDF scene as an .ama archive.

    The `analytic/scene.json` is stored as a JSON list compatible with
    `analytic_viewport_launcher.py --scene-json ...`, and the launcher is also
    patched to load this list directly from an .ama when present.
    """
    import io
    import json
    import zipfile
    from datetime import datetime, timezone

    if not isinstance(scene_list, list):
        raise ValueError("scene_list must be a list")

    provenance = {
        "generator": str(generator),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units": str(units),
        "mode": "analytic_sdf",
    }

    manifest = {
        "type": "analytic_sdf_scene",
        "scene": {"path": "analytic/scene.json", "format": "list"},
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("analytic/scene.json", json.dumps(scene_list, indent=2))
        zf.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("meta/provenance.json", json.dumps(provenance, indent=2))

    return buf.getvalue()


def save_surfaced_bridge_ama(path: str, cfg: SurfacedBridgeConfig) -> str:
    vertices, faces = build_helicoid_bridge_mesh(cfg)
    data = export_surfaced_bridge_as_ama(vertices, faces)
    with open(path, "wb") as f:
        f.write(data)
    return path


__all__ = [
    "SurfacedBridgeConfig",
    "SurfacedHandleConfig",
    "SurfacedMobiusConfig",
    "SurfacedKleinConfig",
    "SurfacedBranchCutConfig",
    "SurfacedTorusKnotRibbonConfig",
    "SurfacedEnneperConfig",
    "build_helicoid_bridge_mesh",
    "build_handle_bridge_mesh",
    "build_mobius_mesh",
    "build_klein_bottle_mesh",
    "build_branch_cut_ramp_mesh",
    "build_torus_knot_ribbon_mesh",
    "build_enneper_mesh",
    "export_surfaced_bridge_as_ama",
    "export_analytic_scene_as_ama",
    "save_surfaced_bridge_ama",
]
