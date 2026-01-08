from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def build_lattice_mk(
    solid: np.ndarray,
    *,
    voxel_size_m: float,
    density: float,
    k_spring: float,
    clamp_mask: np.ndarray | None = None,
) -> tuple[sp.csr_matrix, sp.csr_matrix, np.ndarray, np.ndarray]:
    """Build sparse (M,K) for a 3D mass–spring lattice.

    - Voxels where solid==True get a lumped mass and 3 DOFs.
    - Springs connect 6-neighborhood (axis-aligned) and act on the corresponding component.

    Returns: (M, K, keep_dofs) where keep_dofs is a boolean mask of kept DOFs after clamping.
    """
    if solid.ndim != 3:
        raise ValueError("solid must be a 3D array")

    # Note: voxel grids in this project are indexed as [y, x, z]
    solid = solid.astype(bool)
    ny, nx, nz = solid.shape

    idx = -np.ones((ny, nx, nz), dtype=np.int32)
    pts = np.argwhere(solid)  # (y,x,z)
    idx[solid] = np.arange(len(pts), dtype=np.int32)

    n_vox = int(len(pts))
    if n_vox == 0:
        raise ValueError("No solid voxels in mask")

    dof = 3 * n_vox

    m_vox = float(density) * float(voxel_size_m) ** 3
    M = sp.diags(np.full(dof, m_vox, dtype=np.float64), format="csr")

    # Vector springs: for an edge with unit direction n, stiffness contributes
    # k * (n n^T) to each 3x3 block.
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []

    dx = float(voxel_size_m)
    k_base = float(k_spring)

    # Half-space of 26-neighborhood offsets to avoid double-count.
    # Include all (ox,oy,oz) where:
    #   oz > 0, OR oz==0 and oy > 0, OR oz==0 and oy==0 and ox > 0
    offs: list[tuple[int, int, int]] = []
    for oz in (-1, 0, 1):
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                if ox == 0 and oy == 0 and oz == 0:
                    continue
                if (oz > 0) or (oz == 0 and oy > 0) or (oz == 0 and oy == 0 and ox > 0):
                    offs.append((ox, oy, oz))

    def add_edge(a: int, b: int, n: np.ndarray, k_edge: float) -> None:
        nn = (n.reshape(3, 1) @ n.reshape(1, 3)).astype(np.float64)
        aa = 3 * a
        bb = 3 * b
        # Kaa += k*nn; Kbb += k*nn; Kab -= k*nn; Kba -= k*nn
        for r in range(3):
            for c in range(3):
                v = float(k_edge * nn[r, c])
                if v == 0.0:
                    continue
                rows.extend([aa + r, bb + r, aa + r, bb + r])
                cols.extend([aa + c, bb + c, bb + c, aa + c])
                vals.extend([+v, +v, -v, -v])

    for y, x, z in pts:
        a = int(idx[y, x, z])
        for ox, oy, oz in offs:
            x2, y2, z2 = x + ox, y + oy, z + oz
            if 0 <= x2 < nx and 0 <= y2 < ny and 0 <= z2 < nz and solid[y2, x2, z2]:
                b = int(idx[y2, x2, z2])
                L = dx * float(np.sqrt(ox * ox + oy * oy + oz * oz))
                if L <= 0:
                    continue
                n = np.array([ox, oy, oz], dtype=np.float64) / float(np.sqrt(ox * ox + oy * oy + oz * oz))
                # Scale stiffness with 1/L (axial spring: E*A/L). With A ~ dx^2:
                # k(L) ~= E*dx^2/L = (E*dx) * (dx/L) = k_base * (dx/L)
                k_edge = k_base * (dx / L)
                add_edge(a, b, n, k_edge)

    K = sp.coo_matrix((vals, (rows, cols)), shape=(dof, dof)).tocsr()

    keep = np.ones(dof, dtype=bool)
    if clamp_mask is not None:
        clamp_mask = clamp_mask.astype(bool)
        fixed_ids = idx[solid & clamp_mask]
        fixed_ids = fixed_ids[fixed_ids >= 0]
        if fixed_ids.size:
            fixed_dofs = np.concatenate([3 * fixed_ids, 3 * fixed_ids + 1, 3 * fixed_ids + 2]).astype(np.int32)
            keep[fixed_dofs] = False
            K = K[keep][:, keep]
            M = M[keep][:, keep]

    # Map from full DOF (3*n_vox) -> reduced DOF, or -1 if removed.
    keep_idx = np.flatnonzero(keep)
    inv = -np.ones(dof, dtype=np.int32)
    inv[keep_idx] = np.arange(keep_idx.size, dtype=np.int32)

    return M, K, inv, idx


def solve_modes(
    M: sp.csr_matrix,
    K: sp.csr_matrix,
    *,
    num_modes: int,
    regularize: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve generalized eigenproblem K x = w^2 M x.

    Returns:
      freq_hz: (k,) float64
      modes: (ndof, k) float64

    Notes:
      Free-free systems can have rigid-body modes -> singular K. For robustness,
      we apply a tiny diagonal regularization.
    """
    k = int(num_modes)
    if k <= 0:
        raise ValueError("num_modes must be > 0")

    # Regularize K slightly to avoid numerical issues.
    if regularize > 0:
        K = K + sp.eye(K.shape[0], format="csr") * float(regularize)

    # Ask for smallest magnitude eigenvalues.
    evals, evecs = spla.eigsh(K, k=k, M=M, which="SM")
    evals = np.maximum(evals, 0.0)
    w = np.sqrt(evals)
    f = w / (2.0 * np.pi)

    order = np.argsort(f)
    f = f[order]
    evecs = evecs[:, order]

    return f.astype(np.float64), evecs.astype(np.float64)
