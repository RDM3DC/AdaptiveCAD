"""Forced frequency response analysis for vibration testing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse.linalg as spla

from .lattice import LatticeSystem


@dataclass
class FrequencyResponseResult:
    """Result of frequency response analysis."""
    frequencies_hz: np.ndarray      # (n_freq,) sweep frequencies
    input_rms: np.ndarray           # (n_freq,) RMS displacement at input region
    output_rms: np.ndarray          # (n_freq,) RMS displacement at output region
    transmissibility: np.ndarray    # (n_freq,) T = output_rms / input_rms


@dataclass
class ComparisonResult:
    """Result of comparing two structures' vibration response."""
    frequencies_hz: np.ndarray      # (n_freq,)
    baseline_T: np.ndarray          # (n_freq,) baseline transmissibility
    candidate_T: np.ndarray         # (n_freq,) candidate transmissibility
    delta_dB: np.ndarray            # (n_freq,) 20*log10(candidate_T / baseline_T)
    best_attenuation_dB: float      # Most negative delta_dB
    best_attenuation_hz: float      # Frequency of best attenuation
    worst_amplification_dB: float   # Most positive delta_dB
    worst_amplification_hz: float   # Frequency of worst amplification


def compute_frequency_response(
    system: LatticeSystem,
    *,
    freq_hz: np.ndarray,
    input_node_mask: np.ndarray,
    output_node_mask: np.ndarray,
    force_direction: np.ndarray = None,
    loss_factor: float = 0.05,
) -> FrequencyResponseResult:
    """Compute frequency response by solving forced harmonic problem.

    At each frequency f, solve:
        [(1 + iη)K - ω²M] u = F

    Args:
        system: LatticeSystem
        freq_hz: Array of frequencies to evaluate
        input_node_mask: (n_nodes,) boolean, True for input (force) nodes
        output_node_mask: (n_nodes,) boolean, True for output (measurement) nodes
        force_direction: (3,) unit force direction, default [0,0,1]
        loss_factor: η for structural damping

    Returns:
        FrequencyResponseResult
    """
    if system.n_dof == 0:
        n = len(freq_hz)
        return FrequencyResponseResult(
            frequencies_hz=freq_hz,
            input_rms=np.zeros(n),
            output_rms=np.zeros(n),
            transmissibility=np.zeros(n),
        )

    if force_direction is None:
        force_direction = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    force_direction = np.asarray(force_direction, dtype=np.float64)
    force_direction = force_direction / (np.linalg.norm(force_direction) + 1e-12)

    M = system.M
    K = system.K
    eta = float(loss_factor)

    # Build force vector (unit force at input nodes in force_direction)
    F = np.zeros(system.n_dof, dtype=np.complex128)
    input_nodes = np.where(input_node_mask)[0]
    for node_idx in input_nodes:
        for ax in range(3):
            F[3 * node_idx + ax] = force_direction[ax]

    # Output DOF indices
    output_nodes = np.where(output_node_mask)[0]
    output_dofs = []
    for node_idx in output_nodes:
        output_dofs.extend([3 * node_idx, 3 * node_idx + 1, 3 * node_idx + 2])
    output_dofs = np.array(output_dofs, dtype=np.int32)

    input_dofs = []
    for node_idx in input_nodes:
        input_dofs.extend([3 * node_idx, 3 * node_idx + 1, 3 * node_idx + 2])
    input_dofs = np.array(input_dofs, dtype=np.int32)

    # Complex stiffness with loss factor
    K_complex = (1.0 + 1j * eta) * K

    freq_hz = np.asarray(freq_hz, dtype=np.float64)
    n_freq = len(freq_hz)

    input_rms = np.zeros(n_freq, dtype=np.float64)
    output_rms = np.zeros(n_freq, dtype=np.float64)

    for i, f in enumerate(freq_hz):
        omega = 2.0 * np.pi * f
        omega2 = omega ** 2

        # Dynamic stiffness matrix
        D = K_complex - omega2 * M

        try:
            # Solve D u = F
            u = spla.spsolve(D.tocsc(), F)

            # RMS at input and output
            if len(input_dofs) > 0:
                u_in = u[input_dofs]
                input_rms[i] = np.sqrt(np.mean(np.abs(u_in) ** 2))

            if len(output_dofs) > 0:
                u_out = u[output_dofs]
                output_rms[i] = np.sqrt(np.mean(np.abs(u_out) ** 2))

        except Exception:
            input_rms[i] = np.nan
            output_rms[i] = np.nan

    # Transmissibility
    with np.errstate(divide="ignore", invalid="ignore"):
        T = output_rms / (input_rms + 1e-30)
        T[~np.isfinite(T)] = 0.0

    return FrequencyResponseResult(
        frequencies_hz=freq_hz,
        input_rms=input_rms,
        output_rms=output_rms,
        transmissibility=T,
    )


def compute_transmissibility(
    system: LatticeSystem,
    *,
    freq_hz: np.ndarray,
    input_z_frac: float = 0.1,
    output_z_frac: float = 0.9,
    loss_factor: float = 0.05,
) -> FrequencyResponseResult:
    """Convenience wrapper: input near z_min, output near z_max.

    Args:
        input_z_frac: Fraction along z-range for input band (0=min, 1=max)
        output_z_frac: Fraction along z-range for output band
    """
    if system.n_nodes == 0:
        n = len(freq_hz)
        return FrequencyResponseResult(
            frequencies_hz=freq_hz,
            input_rms=np.zeros(n),
            output_rms=np.zeros(n),
            transmissibility=np.zeros(n),
        )

    coords = system.node_coords
    z = coords[:, 2]
    z_min, z_max = z.min(), z.max()
    z_range = z_max - z_min + 1e-12

    # Band width = 10% of z-range
    band = 0.1 * z_range

    input_z = z_min + input_z_frac * z_range
    output_z = z_min + output_z_frac * z_range

    input_mask = np.abs(z - input_z) < band
    output_mask = np.abs(z - output_z) < band

    # Ensure at least some nodes
    if not np.any(input_mask):
        input_mask[np.argmin(np.abs(z - input_z))] = True
    if not np.any(output_mask):
        output_mask[np.argmin(np.abs(z - output_z))] = True

    return compute_frequency_response(
        system,
        freq_hz=freq_hz,
        input_node_mask=input_mask,
        output_node_mask=output_mask,
        loss_factor=loss_factor,
    )


def compare_transmissibility(
    baseline: FrequencyResponseResult,
    candidate: FrequencyResponseResult,
) -> ComparisonResult:
    """Compare transmissibility of two structures.

    delta_dB = 20 * log10(T_candidate / T_baseline)
    Negative = candidate attenuates more (good)
    Positive = candidate amplifies more (bad)
    """
    if not np.allclose(baseline.frequencies_hz, candidate.frequencies_hz):
        raise ValueError("Frequency arrays must match")

    freq = baseline.frequencies_hz
    T_base = baseline.transmissibility
    T_cand = candidate.transmissibility

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = T_cand / (T_base + 1e-30)
        delta_dB = 20.0 * np.log10(ratio + 1e-30)
        delta_dB[~np.isfinite(delta_dB)] = 0.0

    # Find best attenuation (most negative)
    best_idx = int(np.argmin(delta_dB))
    best_atten_dB = float(delta_dB[best_idx])
    best_atten_hz = float(freq[best_idx])

    # Find worst amplification (most positive)
    worst_idx = int(np.argmax(delta_dB))
    worst_amp_dB = float(delta_dB[worst_idx])
    worst_amp_hz = float(freq[worst_idx])

    return ComparisonResult(
        frequencies_hz=freq,
        baseline_T=T_base,
        candidate_T=T_cand,
        delta_dB=delta_dB,
        best_attenuation_dB=best_atten_dB,
        best_attenuation_hz=best_atten_hz,
        worst_amplification_dB=worst_amp_dB,
        worst_amplification_hz=worst_amp_hz,
    )


__all__ = [
    "FrequencyResponseResult",
    "ComparisonResult",
    "compute_frequency_response",
    "compute_transmissibility",
    "compare_transmissibility",
]
