"""PR-Root Vibration Simulation Package

A from-scratch structural vibration simulator for analytic SDF geometry.
No OCC dependency. Uses mass-spring lattice approximation.

Workflow:
1. Load analytic .ama (SDF scene list)
2. Voxelize geometry
3. Build mass-spring lattice
4. Run modal analysis (eigenfrequencies)
5. Run forced response (frequency sweep)
6. Compare baseline vs candidate

Example:
    from adaptivecad.sim import run_vibration_comparison, VibrationTestConfig
    
    config = VibrationTestConfig(resolution=24, f_min_hz=50, f_max_hz=2500)
    baseline, candidate = run_vibration_comparison(
        "plain_tube.ama", "gyroid_tube.ama", config
    )
    print(f"Best attenuation: {candidate.comparison.best_attenuation_dB:.1f} dB")
"""

from .forced_response import (
    ComparisonResult,
    FrequencyResponseResult,
    compare_transmissibility,
    compute_frequency_response,
    compute_transmissibility,
)
from .heat_generation import (
    HeatComparisonResult,
    HeatGenerationResult,
    HeatSweepResult,
    compare_heat_generation,
    compute_heat_at_frequency,
    compute_heat_sweep,
)
from .lattice import LatticeSystem, build_lattice_system
from .materials import (
    ABS,
    ALUMINUM,
    MATERIALS,
    NYLON,
    PETG,
    PLA,
    STEEL,
    TITANIUM,
    TPU,
    IsotropicMaterial,
)
from .modal import ModalResult, solve_modes
from .pipeline import (
    VibrationTestConfig,
    VibrationTestResult,
    run_modal_analysis,
    run_vibration_comparison,
)
from .voxelizer import load_and_voxelize_ama, voxelize_sdf_scene

__all__ = [
    # Materials
    "IsotropicMaterial",
    "PLA", "ABS", "PETG", "TPU", "NYLON",
    "STEEL", "ALUMINUM", "TITANIUM",
    "MATERIALS",
    # Voxelization
    "voxelize_sdf_scene",
    "load_and_voxelize_ama",
    # Lattice
    "build_lattice_system",
    "LatticeSystem",
    # Modal
    "solve_modes",
    "ModalResult",
    # Forced response
    "compute_frequency_response",
    "compute_transmissibility",
    "compare_transmissibility",
    "FrequencyResponseResult",
    "ComparisonResult",
    # Pipeline
    "run_modal_analysis",
    "run_vibration_comparison",
    "VibrationTestConfig",
    "VibrationTestResult",
    # Heat generation
    "compute_heat_at_frequency",
    "compute_heat_sweep",
    "compare_heat_generation",
    "HeatGenerationResult",
    "HeatSweepResult",
    "HeatComparisonResult",
]
