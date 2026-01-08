"""Modal analysis (eigenfrequency solver) for lattice systems."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse.linalg as spla

from .lattice import LatticeSystem


@dataclass
class ModalResult:
    """Result of modal analysis."""
    frequencies_hz: np.ndarray   # (n_modes,) natural frequencies in Hz
    mode_shapes: np.ndarray      # (n_dof, n_modes) eigenvectors
    n_rigid: int                 # Number of near-zero (rigid body) modes detected


def solve_modes(
    system: LatticeSystem,
    *,
    num_modes: int = 12,
    rigid_threshold_hz: float = 1.0,
) -> ModalResult:
    """Solve for natural frequencies and mode shapes.

    Solves: K φ = ω² M φ

    Args:
        system: LatticeSystem with M and K matrices
        num_modes: Number of modes to compute
        rigid_threshold_hz: Modes below this frequency are considered "rigid body"

    Returns:
        ModalResult with frequencies and mode shapes
    """
    if system.n_dof == 0:
        return ModalResult(
            frequencies_hz=np.array([], dtype=np.float64),
            mode_shapes=np.zeros((0, 0), dtype=np.float64),
            n_rigid=0,
        )

    M = system.M
    K = system.K

    # Request a few extra modes to handle rigid body modes
    k = min(num_modes + 6, system.n_dof - 1)
    if k < 1:
        k = 1

    try:
        # Shift-invert around sigma=0 to find smallest eigenvalues
        eigenvalues, eigenvectors = spla.eigsh(
            K, k=k, M=M, sigma=0.0, which="LM", tol=1e-6
        )
    except Exception:
        # Fallback: try standard eigenproblem on M^{-1} K
        try:
            M_inv_diag = 1.0 / (M.diagonal() + 1e-12)
            eigenvalues, eigenvectors = spla.eigsh(
                spla.LinearOperator(
                    shape=K.shape,
                    matvec=lambda x: M_inv_diag * (K @ x),
                ),
                k=k,
                which="SM",
                tol=1e-6,
            )
        except Exception:
            return ModalResult(
                frequencies_hz=np.array([], dtype=np.float64),
                mode_shapes=np.zeros((system.n_dof, 0), dtype=np.float64),
                n_rigid=0,
            )

    # Convert eigenvalues to frequencies
    eigenvalues = np.maximum(eigenvalues.real, 0.0)
    omega = np.sqrt(eigenvalues)
    freq_hz = omega / (2.0 * np.pi)

    # Sort by frequency
    order = np.argsort(freq_hz)
    freq_hz = freq_hz[order]
    eigenvectors = eigenvectors[:, order]

    # Count rigid body modes
    n_rigid = int(np.sum(freq_hz < rigid_threshold_hz))

    # Return requested number of non-rigid modes
    non_rigid_mask = freq_hz >= rigid_threshold_hz
    freq_hz_out = freq_hz[non_rigid_mask][:num_modes]
    modes_out = eigenvectors[:, non_rigid_mask][:, :num_modes]

    return ModalResult(
        frequencies_hz=freq_hz_out,
        mode_shapes=modes_out,
        n_rigid=n_rigid,
    )


__all__ = ["ModalResult", "solve_modes"]
