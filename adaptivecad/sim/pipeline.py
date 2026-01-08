"""High-level vibration testing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

import numpy as np

from .materials import IsotropicMaterial, PLA
from .voxelizer import load_and_voxelize_ama
from .lattice import build_lattice_system, LatticeSystem
from .modal import solve_modes, ModalResult
from .forced_response import (
    compute_transmissibility,
    compare_transmissibility,
    FrequencyResponseResult,
    ComparisonResult,
)


@dataclass
class VibrationTestConfig:
    """Configuration for vibration testing."""
    # Geometry sampling
    extent: float = 1.5
    resolution: int = 24
    iso: float = 0.0

    # Material
    material: IsotropicMaterial = field(default_factory=lambda: PLA)

    # Boundary conditions
    clamp_z_min: bool = True
    clamp_z_min_frac: float = 0.05  # Clamp bottom 5% of z-range

    # Modal analysis
    num_modes: int = 12

    # Frequency response
    f_min_hz: float = 50.0
    f_max_hz: float = 2500.0
    n_freq: int = 100
    loss_factor: float = 0.05
    input_z_frac: float = 0.1
    output_z_frac: float = 0.9


@dataclass
class VibrationTestResult:
    """Complete result of vibration testing."""
    # Input
    config: VibrationTestConfig
    ama_path: str

    # Geometry stats
    n_solid_voxels: int
    n_free_nodes: int
    voxel_size: float

    # Modal analysis
    modal: ModalResult

    # Frequency response
    response: FrequencyResponseResult

    # Optional comparison
    comparison: Optional[ComparisonResult] = None
    baseline_path: Optional[str] = None

    def to_dict(self) -> dict:
        """Export as JSON-serializable dict."""
        return {
            "ama_path": self.ama_path,
            "config": {
                "extent": self.config.extent,
                "resolution": self.config.resolution,
                "material": self.config.material.name,
                "f_min_hz": self.config.f_min_hz,
                "f_max_hz": self.config.f_max_hz,
                "n_freq": self.config.n_freq,
                "loss_factor": self.config.loss_factor,
            },
            "geometry": {
                "n_solid_voxels": self.n_solid_voxels,
                "n_free_nodes": self.n_free_nodes,
                "voxel_size": self.voxel_size,
            },
            "modal": {
                "frequencies_hz": self.modal.frequencies_hz.tolist(),
                "n_rigid": self.modal.n_rigid,
            },
            "response": {
                "frequencies_hz": self.response.frequencies_hz.tolist(),
                "transmissibility": self.response.transmissibility.tolist(),
            },
            "comparison": None if self.comparison is None else {
                "baseline_path": self.baseline_path,
                "delta_dB": self.comparison.delta_dB.tolist(),
                "best_attenuation_dB": self.comparison.best_attenuation_dB,
                "best_attenuation_hz": self.comparison.best_attenuation_hz,
                "worst_amplification_dB": self.comparison.worst_amplification_dB,
                "worst_amplification_hz": self.comparison.worst_amplification_hz,
            },
        }

    def save_json(self, path: str | Path):
        """Save results to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def _build_clamp_mask(solid: np.ndarray, config: VibrationTestConfig) -> np.ndarray:
    """Build a clamp mask based on config."""
    clamp = np.zeros_like(solid, dtype=bool)

    if config.clamp_z_min:
        # Find z-extent of solid voxels
        z_indices = np.where(solid)[2]
        if len(z_indices) > 0:
            z_min = z_indices.min()
            z_max = z_indices.max()
            z_range = z_max - z_min + 1
            clamp_height = int(config.clamp_z_min_frac * z_range) + 1
            clamp[:, :, z_min:z_min + clamp_height] = True

    return clamp


def run_modal_analysis(
    ama_path: str | Path,
    config: Optional[VibrationTestConfig] = None,
) -> VibrationTestResult:
    """Run modal analysis on an analytic .ama file.

    Args:
        ama_path: Path to .ama with analytic/scene.json (list format)
        config: Test configuration (defaults to PLA, clamped z-min)

    Returns:
        VibrationTestResult with modal frequencies
    """
    if config is None:
        config = VibrationTestConfig()

    ama_path = Path(ama_path)

    # Load and voxelize
    solid, dist, voxel_size, scene = load_and_voxelize_ama(
        ama_path,
        extent=config.extent,
        resolution=config.resolution,
        iso=config.iso,
    )

    n_solid = int(solid.sum())

    # Build clamp mask
    clamp = _build_clamp_mask(solid, config)

    # Build lattice system
    system = build_lattice_system(
        solid,
        voxel_size=voxel_size,
        material=config.material,
        clamp_mask=clamp,
        neighbor_mode="26",
    )

    # Modal analysis
    modal = solve_modes(system, num_modes=config.num_modes)

    # Frequency response
    freq_hz = np.linspace(config.f_min_hz, config.f_max_hz, config.n_freq)
    response = compute_transmissibility(
        system,
        freq_hz=freq_hz,
        input_z_frac=config.input_z_frac,
        output_z_frac=config.output_z_frac,
        loss_factor=config.loss_factor,
    )

    return VibrationTestResult(
        config=config,
        ama_path=str(ama_path),
        n_solid_voxels=n_solid,
        n_free_nodes=system.n_nodes,
        voxel_size=voxel_size,
        modal=modal,
        response=response,
    )


def run_vibration_comparison(
    baseline_ama: str | Path,
    candidate_ama: str | Path,
    config: Optional[VibrationTestConfig] = None,
) -> tuple[VibrationTestResult, VibrationTestResult]:
    """Compare vibration response of two structures.

    Args:
        baseline_ama: Path to baseline structure .ama
        candidate_ama: Path to candidate structure .ama
        config: Test configuration (same for both)

    Returns:
        (baseline_result, candidate_result) where candidate has .comparison populated
    """
    if config is None:
        config = VibrationTestConfig()

    baseline_result = run_modal_analysis(baseline_ama, config)
    candidate_result = run_modal_analysis(candidate_ama, config)

    # Compute comparison
    comparison = compare_transmissibility(
        baseline_result.response,
        candidate_result.response,
    )

    candidate_result.comparison = comparison
    candidate_result.baseline_path = str(baseline_ama)

    return baseline_result, candidate_result


__all__ = [
    "VibrationTestConfig",
    "VibrationTestResult",
    "run_modal_analysis",
    "run_vibration_comparison",
]
