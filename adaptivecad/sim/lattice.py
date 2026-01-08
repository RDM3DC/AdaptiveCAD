"""Build mass-spring lattice system for voxelized geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.sparse as sp

from .materials import IsotropicMaterial


@dataclass
class LatticeSystem:
    """Assembled mass-spring lattice system."""
    M: sp.csr_matrix          # Mass matrix (diagonal, lumped)
    K: sp.csr_matrix          # Stiffness matrix
    n_nodes: int              # Number of free nodes
    n_dof: int                # Number of DOFs (3 * n_nodes after clamping)
    voxel_size: float         # Voxel edge length
    node_coords: np.ndarray   # (n_nodes, 3) world coordinates of free nodes
    node_indices: np.ndarray  # (nx, ny, nz) int array: -1 if not free, else node index
    free_mask: np.ndarray     # Boolean mask of which solid voxels are free (not clamped)


def build_lattice_system(
    solid: np.ndarray,
    *,
    voxel_size: float,
    material: IsotropicMaterial,
    clamp_mask: Optional[np.ndarray] = None,
    neighbor_mode: str = "26",  # "6", "18", or "26"
) -> LatticeSystem:
    """Build M and K matrices for a 3D mass-spring lattice on solid voxels.

    Each solid voxel becomes a node with 3 DOFs (ux, uy, uz).
    Springs connect neighbors with axial stiffness derived from material properties.

    Args:
        solid: (nx, ny, nz) boolean array
        voxel_size: Edge length in meters (for proper units)
        material: Material properties
        clamp_mask: Optional (nx, ny, nz) boolean, True = fixed (Dirichlet BC)
        neighbor_mode: "6" (faces), "18" (faces+edges), "26" (faces+edges+corners)

    Returns:
        LatticeSystem with assembled M, K, and metadata
    """
    solid = np.asarray(solid, dtype=bool)
    if solid.ndim != 3:
        raise ValueError("solid must be 3D")

    nx, ny, nz = solid.shape
    h = float(voxel_size)

    # Determine free nodes (solid and not clamped)
    if clamp_mask is not None:
        clamp_mask = np.asarray(clamp_mask, dtype=bool)
        if clamp_mask.shape != solid.shape:
            raise ValueError("clamp_mask shape must match solid shape")
        free_mask = solid & ~clamp_mask
    else:
        free_mask = solid.copy()

    # Index map: -1 for non-free, else sequential node index
    node_indices = -np.ones((nx, ny, nz), dtype=np.int32)
    free_coords = np.argwhere(free_mask)
    n_nodes = len(free_coords)

    if n_nodes == 0:
        # Return empty system
        return LatticeSystem(
            M=sp.csr_matrix((0, 0), dtype=np.float64),
            K=sp.csr_matrix((0, 0), dtype=np.float64),
            n_nodes=0,
            n_dof=0,
            voxel_size=h,
            node_coords=np.zeros((0, 3), dtype=np.float32),
            node_indices=node_indices,
            free_mask=free_mask,
        )

    node_indices[free_mask] = np.arange(n_nodes, dtype=np.int32)
    n_dof = 3 * n_nodes

    # Node world coordinates (voxel centers)
    node_coords = (free_coords.astype(np.float32) + 0.5) * h
    # Center around origin
    node_coords -= node_coords.mean(axis=0)

    # Lumped mass per node
    m = material.density * (h ** 3)
    M = sp.diags(np.full(n_dof, m, dtype=np.float64), format="csr")

    # Spring stiffness (simplified: k = E * A / L where A ~ h², L ~ neighbor distance)
    E = material.youngs_modulus
    k_base = E * h  # Effective spring constant (E * h² / h = E * h)

    # Neighbor offsets by mode
    if neighbor_mode == "6":
        offsets = [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]
    elif neighbor_mode == "18":
        offsets = [
            (1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1),
            (1,1,0), (1,-1,0), (-1,1,0), (-1,-1,0),
            (1,0,1), (1,0,-1), (-1,0,1), (-1,0,-1),
            (0,1,1), (0,1,-1), (0,-1,1), (0,-1,-1),
        ]
    else:  # "26"
        offsets = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx != 0 or dy != 0 or dz != 0:
                        offsets.append((dx, dy, dz))

    # Build K using COO format for efficiency
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []

    def add_spring(a: int, b: int, direction: np.ndarray, k: float):
        """Add an axial spring between nodes a and b along direction n.

        Stiffness contribution: k * n ⊗ n (outer product)
        """
        n = direction / (np.linalg.norm(direction) + 1e-12)
        knn = k * np.outer(n, n)  # 3x3

        for i in range(3):
            for j in range(3):
                kij = knn[i, j]
                if abs(kij) < 1e-15:
                    continue

                # (a,a) block: +kij
                rows.append(3 * a + i)
                cols.append(3 * a + j)
                vals.append(+kij)

                # (b,b) block: +kij
                rows.append(3 * b + i)
                cols.append(3 * b + j)
                vals.append(+kij)

                # (a,b) block: -kij
                rows.append(3 * a + i)
                cols.append(3 * b + j)
                vals.append(-kij)

                # (b,a) block: -kij
                rows.append(3 * b + i)
                cols.append(3 * a + j)
                vals.append(-kij)

    # Process each free node
    for ix, iy, iz in free_coords:
        a = int(node_indices[ix, iy, iz])

        for dx, dy, dz in offsets:
            jx, jy, jz = ix + dx, iy + dy, iz + dz

            # Check bounds
            if not (0 <= jx < nx and 0 <= jy < ny and 0 <= jz < nz):
                continue

            # Check if neighbor is also free
            b = int(node_indices[jx, jy, jz])
            if b < 0 or b <= a:  # Skip non-free or already processed pairs
                continue

            # Direction vector and distance
            d = np.array([dx, dy, dz], dtype=np.float64) * h
            dist = np.linalg.norm(d)

            # Spring stiffness scales inversely with distance
            k = k_base * h / dist

            add_spring(a, b, d, k)

    K = sp.coo_matrix((vals, (rows, cols)), shape=(n_dof, n_dof), dtype=np.float64).tocsr()

    return LatticeSystem(
        M=M,
        K=K,
        n_nodes=n_nodes,
        n_dof=n_dof,
        voxel_size=h,
        node_coords=node_coords.astype(np.float32),
        node_indices=node_indices,
        free_mask=free_mask,
    )


__all__ = ["LatticeSystem", "build_lattice_system"]
