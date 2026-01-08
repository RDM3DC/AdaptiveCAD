"""Vibration-to-heat conversion simulator.

Computes heat generation rate from amplified vibrations due to material damping.

Physics:
    - Damping converts mechanical vibration energy into heat
    - Power dissipated per cycle: P = π · η · f · k · |u|²
    - High-damping materials (TPU, rubber) generate more heat
    - Resonant amplification concentrates energy → localized heating

Applications:
    - Frequency-selective heating
    - Ultrasonic welding analysis
    - Vibration damper thermal design
    - Energy harvesting feasibility
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.sparse.linalg as spla

from .lattice import LatticeSystem
from .materials import IsotropicMaterial


@dataclass
class HeatGenerationResult:
    """Result of heat generation analysis at a single frequency."""
    frequency_hz: float
    total_power_watts: float           # Total heat generated (W)
    power_per_node: np.ndarray         # (n_nodes,) power at each node (W)
    displacement_rms: np.ndarray       # (n_nodes,) RMS displacement magnitude
    node_coords: np.ndarray            # (n_nodes, 3) for visualization
    input_power_watts: float           # Power input to system (W)
    efficiency: float                  # P_heat / P_input


@dataclass
class HeatSweepResult:
    """Result of heat generation frequency sweep."""
    frequencies_hz: np.ndarray         # (n_freq,)
    total_power_watts: np.ndarray      # (n_freq,) total heat at each freq
    input_power_watts: np.ndarray      # (n_freq,) input power at each freq
    efficiency: np.ndarray             # (n_freq,) conversion efficiency
    peak_frequency_hz: float           # Frequency with max heat generation
    peak_power_watts: float            # Max heat generation rate
    power_per_node: np.ndarray         # (n_freq, n_nodes) heat map over freq


@dataclass 
class HeatComparisonResult:
    """Compare heat generation between two structures."""
    frequencies_hz: np.ndarray
    baseline_power: np.ndarray         # (n_freq,) baseline heat generation
    candidate_power: np.ndarray        # (n_freq,) candidate heat generation
    power_ratio: np.ndarray            # candidate / baseline
    power_ratio_dB: np.ndarray         # 10*log10(ratio)
    best_amplification_dB: float       # Max heat increase
    best_amplification_hz: float
    baseline_peak_hz: float            # Where baseline generates most heat
    candidate_peak_hz: float           # Where candidate generates most heat


def compute_heat_at_frequency(
    system: LatticeSystem,
    *,
    frequency_hz: float,
    material: IsotropicMaterial,
    input_node_mask: np.ndarray,
    force_amplitude: float = 1.0,
    force_direction: np.ndarray = None,
) -> HeatGenerationResult:
    """Compute heat generation at a single frequency.

    Args:
        system: LatticeSystem with M, K matrices
        frequency_hz: Driving frequency
        material: Material with loss_factor for damping
        input_node_mask: (n_nodes,) boolean, where force is applied
        force_amplitude: Force magnitude (N)
        force_direction: (3,) unit direction, default [0,0,1]

    Returns:
        HeatGenerationResult with power distribution
    """
    if system.n_dof == 0:
        return HeatGenerationResult(
            frequency_hz=frequency_hz,
            total_power_watts=0.0,
            power_per_node=np.array([]),
            displacement_rms=np.array([]),
            node_coords=np.zeros((0, 3)),
            input_power_watts=0.0,
            efficiency=0.0,
        )

    if force_direction is None:
        force_direction = np.array([0.0, 0.0, 1.0])
    force_direction = np.asarray(force_direction, dtype=np.float64)
    force_direction = force_direction / (np.linalg.norm(force_direction) + 1e-12)

    M = system.M
    K = system.K
    eta = getattr(material, 'loss_factor', 0.05)

    omega = 2.0 * np.pi * frequency_hz
    omega2 = omega ** 2

    # Build force vector
    F = np.zeros(system.n_dof, dtype=np.complex128)
    input_nodes = np.where(input_node_mask)[0]
    for node_idx in input_nodes:
        for ax in range(3):
            F[3 * node_idx + ax] = force_amplitude * force_direction[ax]

    # Dynamic stiffness with complex damping
    K_complex = (1.0 + 1j * eta) * K
    D = K_complex - omega2 * M

    try:
        # Solve for displacement
        u = spla.spsolve(D.tocsc(), F)
    except Exception:
        return HeatGenerationResult(
            frequency_hz=frequency_hz,
            total_power_watts=0.0,
            power_per_node=np.zeros(system.n_nodes),
            displacement_rms=np.zeros(system.n_nodes),
            node_coords=system.node_coords,
            input_power_watts=0.0,
            efficiency=0.0,
        )

    # Compute displacement magnitude per node
    displacement_rms = np.zeros(system.n_nodes, dtype=np.float64)
    for i in range(system.n_nodes):
        ux = u[3*i]
        uy = u[3*i + 1]
        uz = u[3*i + 2]
        displacement_rms[i] = np.sqrt((np.abs(ux)**2 + np.abs(uy)**2 + np.abs(uz)**2) / 3)

    # Heat generation per node
    # P = π · η · f · k_eff · |u|²
    # k_eff approximated from diagonal of K
    K_diag = np.abs(K.diagonal())
    k_per_dof = np.maximum(K_diag, 1e-12)
    
    power_per_node = np.zeros(system.n_nodes, dtype=np.float64)
    for i in range(system.n_nodes):
        # Average stiffness for this node's DOFs
        k_node = (k_per_dof[3*i] + k_per_dof[3*i+1] + k_per_dof[3*i+2]) / 3
        u_mag_sq = displacement_rms[i] ** 2
        # P = π · η · f · k · |u|²
        power_per_node[i] = np.pi * eta * frequency_hz * k_node * u_mag_sq

    total_power = float(np.sum(power_per_node))

    # Input power = F · v = F · (iω·u) → real part = F · ω · Im(u)
    # For harmonic: P_in = 0.5 * Re(F* · iω·u) = 0.5 * ω * Im(F* · u)
    F_conj = np.conj(F)
    input_power = 0.5 * omega * np.abs(np.imag(np.dot(F_conj, u)))
    input_power = float(input_power) if input_power > 0 else 1e-12

    efficiency = total_power / input_power if input_power > 0 else 0.0

    return HeatGenerationResult(
        frequency_hz=frequency_hz,
        total_power_watts=total_power,
        power_per_node=power_per_node,
        displacement_rms=displacement_rms,
        node_coords=system.node_coords.copy(),
        input_power_watts=input_power,
        efficiency=efficiency,
    )


def compute_heat_sweep(
    system: LatticeSystem,
    *,
    freq_hz: np.ndarray,
    material: IsotropicMaterial,
    input_z_frac: float = 0.1,
    force_amplitude: float = 1.0,
) -> HeatSweepResult:
    """Sweep frequency range and compute heat generation.

    Args:
        system: LatticeSystem
        freq_hz: Array of frequencies to evaluate
        material: Material with loss_factor
        input_z_frac: Fraction along z-axis for input force location
        force_amplitude: Force magnitude (N)

    Returns:
        HeatSweepResult with power vs frequency
    """
    if system.n_nodes == 0:
        n = len(freq_hz)
        return HeatSweepResult(
            frequencies_hz=freq_hz,
            total_power_watts=np.zeros(n),
            input_power_watts=np.zeros(n),
            efficiency=np.zeros(n),
            peak_frequency_hz=0.0,
            peak_power_watts=0.0,
            power_per_node=np.zeros((n, 0)),
        )

    # Determine input nodes (near z_min + input_z_frac * z_range)
    coords = system.node_coords
    z = coords[:, 2]
    z_min, z_max = z.min(), z.max()
    z_range = z_max - z_min + 1e-12
    
    input_z = z_min + input_z_frac * z_range
    band = 0.1 * z_range
    input_mask = np.abs(z - input_z) < band
    
    if not np.any(input_mask):
        input_mask[np.argmin(np.abs(z - input_z))] = True

    freq_hz = np.asarray(freq_hz, dtype=np.float64)
    n_freq = len(freq_hz)

    total_power = np.zeros(n_freq, dtype=np.float64)
    input_power = np.zeros(n_freq, dtype=np.float64)
    efficiency = np.zeros(n_freq, dtype=np.float64)
    power_per_node = np.zeros((n_freq, system.n_nodes), dtype=np.float64)

    for i, f in enumerate(freq_hz):
        result = compute_heat_at_frequency(
            system,
            frequency_hz=f,
            material=material,
            input_node_mask=input_mask,
            force_amplitude=force_amplitude,
        )
        total_power[i] = result.total_power_watts
        input_power[i] = result.input_power_watts
        efficiency[i] = result.efficiency
        power_per_node[i, :] = result.power_per_node

    # Find peak
    peak_idx = int(np.argmax(total_power))
    peak_freq = float(freq_hz[peak_idx])
    peak_power = float(total_power[peak_idx])

    return HeatSweepResult(
        frequencies_hz=freq_hz,
        total_power_watts=total_power,
        input_power_watts=input_power,
        efficiency=efficiency,
        peak_frequency_hz=peak_freq,
        peak_power_watts=peak_power,
        power_per_node=power_per_node,
    )


def compare_heat_generation(
    baseline: HeatSweepResult,
    candidate: HeatSweepResult,
) -> HeatComparisonResult:
    """Compare heat generation between two structures.

    Args:
        baseline: HeatSweepResult for baseline structure
        candidate: HeatSweepResult for candidate structure

    Returns:
        HeatComparisonResult with power ratios
    """
    if not np.allclose(baseline.frequencies_hz, candidate.frequencies_hz):
        raise ValueError("Frequency arrays must match")

    freq = baseline.frequencies_hz
    P_base = baseline.total_power_watts
    P_cand = candidate.total_power_watts

    # Power ratio
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = P_cand / (P_base + 1e-30)
        ratio[~np.isfinite(ratio)] = 1.0
        ratio_dB = 10.0 * np.log10(ratio + 1e-30)
        ratio_dB[~np.isfinite(ratio_dB)] = 0.0

    # Best amplification (candidate generates more heat)
    best_idx = int(np.argmax(ratio_dB))
    best_amp_dB = float(ratio_dB[best_idx])
    best_amp_hz = float(freq[best_idx])

    return HeatComparisonResult(
        frequencies_hz=freq,
        baseline_power=P_base,
        candidate_power=P_cand,
        power_ratio=ratio,
        power_ratio_dB=ratio_dB,
        best_amplification_dB=best_amp_dB,
        best_amplification_hz=best_amp_hz,
        baseline_peak_hz=baseline.peak_frequency_hz,
        candidate_peak_hz=candidate.peak_frequency_hz,
    )


__all__ = [
    "HeatGenerationResult",
    "HeatSweepResult",
    "HeatComparisonResult",
    "compute_heat_at_frequency",
    "compute_heat_sweep",
    "compare_heat_generation",
]
