"""Phase / πₐ demo tools for AdaptiveCAD.

These helpers build *solid* geometry in the AACore SDF scene to make
phase/πₐ concepts visible and printable.

Key constraint: the analytic renderer has a primitive budget (MAX_PRIMS).
We therefore resample paths to fit available primitives.
"""

from __future__ import annotations

import math

import numpy as np

from adaptivecad.aacore.math import Xform
from adaptivecad.aacore.sdf import KIND_CAPSULE, MAX_PRIMS, Prim
from adaptivecad.pi.kernel import PiAParams, make_adaptive_circle
from adaptivecad.torus_phase import TorusPath, wrap_to_pi


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return v
    return v / n


def _capsule_xform_between(p0: np.ndarray, p1: np.ndarray) -> tuple[np.ndarray, float]:
    """Return (M, h) for a capsule aligned to segment p0->p1.

    The capsule primitive is a Y-axis capsule of height h in *local* space.
    We build a local->world transform where local Y maps to the segment.
    """

    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    v = p1 - p0
    h = float(np.linalg.norm(v))
    if h < 1e-9:
        M = np.eye(4, dtype=np.float64)
        M[:3, 3] = p0
        return M, 0.0

    y_hat = v / h

    # Choose a reference axis not parallel to y_hat.
    ref = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(float(np.dot(ref, y_hat))) > 0.95:
        ref = np.array([1.0, 0.0, 0.0], dtype=float)

    x_hat = _normalize(np.cross(ref, y_hat))
    z_hat = _normalize(np.cross(y_hat, x_hat))

    R = np.column_stack([x_hat, y_hat, z_hat])
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R
    M[:3, 3] = 0.5 * (p0 + p1)
    return M, h


def _resample_polyline(points: np.ndarray, target_points: int) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must have shape (N,3)")
    n = points.shape[0]
    if n <= target_points:
        return points

    # Arc-length parameterize for better uniformity.
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total < 1e-9:
        idx = np.linspace(0, n - 1, target_points).round().astype(int)
        return points[idx]

    t_new = np.linspace(0.0, total, target_points)
    out = np.zeros((target_points, 3), dtype=float)
    for k in range(3):
        out[:, k] = np.interp(t_new, s, points[:, k])
    return out


def add_polyline_tube(
    scene,
    points_xyz: np.ndarray,
    *,
    tube_radius: float = 0.05,
    color: tuple[float, float, float] = (0.9, 0.6, 0.2),
    closed: bool = True,
) -> int:
    """Add a tube following a polyline by unioning capsules.

    Returns number of primitives added.
    """

    points = np.asarray(points_xyz, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points_xyz must have shape (N,3)")

    if points.shape[0] < 2:
        return 0

    available = max(0, int(MAX_PRIMS) - int(len(getattr(scene, "prims", []))))
    if available <= 0:
        return 0

    segments = points.shape[0] if closed else (points.shape[0] - 1)
    # Need one capsule per segment.
    target_segments = min(available, segments)
    target_points = target_segments + (0 if closed else 1)
    if closed:
        target_points = target_segments

    pts = points
    if closed:
        # Resample the open polyline, then close by connecting last->first.
        pts_open = _resample_polyline(points, max(2, target_segments))
        pts = pts_open
    else:
        pts = _resample_polyline(points, max(2, target_points))

    added = 0
    if closed:
        n = pts.shape[0]
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            M, h = _capsule_xform_between(p0, p1)
            if h <= 1e-8:
                continue
            pr = Prim(KIND_CAPSULE, [float(tube_radius), float(h), 0.0, 0.0], xform=Xform())
            pr.color = np.asarray(color, dtype=np.float64)
            pr.xform.M = M
            scene.add(pr)
            added += 1
            if added >= available:
                break
    else:
        for i in range(pts.shape[0] - 1):
            p0 = pts[i]
            p1 = pts[i + 1]
            M, h = _capsule_xform_between(p0, p1)
            if h <= 1e-8:
                continue
            pr = Prim(KIND_CAPSULE, [float(tube_radius), float(h), 0.0, 0.0], xform=Xform())
            pr.color = np.asarray(color, dtype=np.float64)
            pr.xform.M = M
            scene.add(pr)
            added += 1
            if added >= available:
                break

    return added


def add_pi_a_adaptive_circle_demo(
    scene,
    *,
    radius: float = 1.0,
    tube_radius: float = 0.05,
    kappa: float = 1.0,
    scale: float = 1.0,
    params: PiAParams | None = None,
    n: int = 42,
    z: float = 0.0,
) -> int:
    """Create a πₐ-scaled circle tube (visualizes conformal scaling)."""

    params = params or PiAParams(beta=0.25, s0=1.0, clamp=0.35)
    pts2 = make_adaptive_circle(radius=radius, n=int(n), kappa=float(kappa), scale=float(scale), params=params)
    pts3 = np.column_stack([pts2[:, 0], pts2[:, 1], np.full((pts2.shape[0],), float(z))])
    return add_polyline_tube(scene, pts3, tube_radius=tube_radius, color=(0.2, 0.8, 0.6), closed=True)


def add_torus_phase_path_demo(
    scene,
    *,
    R: float = 1.2,
    r: float = 0.45,
    tube_radius: float = 0.05,
    samples: int = 60,
    theta_turns: float = 1.0,
    phi_turns: float = 0.25,
) -> int:
    """Create a solid tube along a path on T^2, embedded in 3D."""

    t = np.linspace(0.0, 1.0, int(samples))
    theta = (2.0 * math.pi * float(theta_turns)) * t
    phi = (2.0 * math.pi * float(phi_turns)) * t
    wrapped = np.column_stack([wrap_to_pi(theta), wrap_to_pi(phi)])
    path = TorusPath(wrapped, phase_space="wrapped").interpolate(min(80, int(samples)))
    xyz = path.to_xyz(R=float(R), r=float(r), center=(0.0, 0.0, 0.0))
    # Not closed by default (it’s a trajectory); set closed=False.
    return add_polyline_tube(scene, xyz, tube_radius=tube_radius, color=(0.9, 0.55, 0.2), closed=False)
