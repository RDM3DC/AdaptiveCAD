from __future__ import annotations

from typing import Dict, Iterable

import numpy as np


def _laplacian_periodic_2d(arr: np.ndarray) -> np.ndarray:
    return (
        np.roll(arr, 1, axis=0)
        + np.roll(arr, -1, axis=0)
        + np.roll(arr, 1, axis=1)
        + np.roll(arr, -1, axis=1)
        - 4.0 * arr
    )


def _smooth_box_periodic_2d(arr: np.ndarray, *, iters: int = 4) -> np.ndarray:
    out = np.asarray(arr, dtype=np.float32)
    for _ in range(max(0, int(iters))):
        out = 0.5 * out + 0.5 * (
            np.roll(out, 1, axis=0)
            + np.roll(out, -1, axis=0)
            + np.roll(out, 1, axis=1)
            + np.roll(out, -1, axis=1)
        ) / 4.0
    return out.astype(np.float32)


def _mean_curvature_heightmap(f: np.ndarray) -> np.ndarray:
    """Approximate mean curvature of z=f(x,y) on a unit grid.

    Uses the standard Monge patch formula:
    H = ((1+f_y^2) f_xx - 2 f_x f_y f_xy + (1+f_x^2) f_yy) / (2 (1+f_x^2+f_y^2)^(3/2))

    Note: This is a geometric proxy (not a GR curvature invariant).
    """

    f = np.asarray(f, dtype=np.float32)
    fy, fx = np.gradient(f)
    fyy, fyx = np.gradient(fy)
    fxy, fxx = np.gradient(fx)

    denom = 2.0 * np.power(1.0 + fx * fx + fy * fy, 1.5)
    denom = np.where(denom == 0.0, 1e-9, denom)
    numer = (1.0 + fy * fy) * fxx - 2.0 * fx * fy * fxy + (1.0 + fx * fx) * fyy
    return (numer / denom).astype(np.float32)


def compute_derived_fields(
    field_2d: np.ndarray,
    *,
    include: Iterable[str] = ("gradmag", "laplacian", "curvature", "smooth"),
    smooth_iters: int = 4,
) -> Dict[str, np.ndarray]:
    """Compute additional PR-friendly diagnostic layers from a 2D scalar field.

    Returns a dict keyed by layer id.
    """

    f = np.asarray(field_2d, dtype=np.float32)
    if f.ndim != 2:
        raise ValueError("field_2d must be 2D")

    want = {str(x).strip().lower() for x in include}
    out: Dict[str, np.ndarray] = {}

    if "gradmag" in want:
        fy, fx = np.gradient(f)
        out["gradmag"] = np.sqrt(fx * fx + fy * fy).astype(np.float32)

    if "laplacian" in want:
        out["laplacian"] = _laplacian_periodic_2d(f).astype(np.float32)

    if "curvature" in want:
        out["curvature"] = _mean_curvature_heightmap(f)

    if "smooth" in want:
        out["smooth"] = _smooth_box_periodic_2d(f, iters=smooth_iters)

    return out


__all__ = ["compute_derived_fields"]
