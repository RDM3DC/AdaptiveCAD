"""Phase‑Resolved (PR) modeling primitives.

This package provides a minimal, headless-safe substrate for evolving phase fields
and collecting metrics. It is designed to be callable from the MCP bridge.
"""

from .derived import compute_derived_fields
from .export import (
    export_phase_field_as_ama,
    export_phase_field_as_heightmap_stl,
    export_phase_field_as_obj,
)
from .ribbon import (
    PRRibbonConfig,
    export_ribbon_as_ama,
    generate_centerline,
    generate_ribbon_mesh,
    save_ribbon_ama,
)
from .solver import relax_phase_field
from .tools import augment_ama_with_derived_fields
from .types import PRFieldConfig, PRFieldState
from .volume import (
    PRVolumeConfig,
    PRVolumeState,
    export_volume_as_ama,
    extract_isosurface,
    relax_phase_volume,
    save_volume_ama,
)

__all__ = [
    "PRFieldConfig",
    "PRFieldState",
    "relax_phase_field",
    "compute_derived_fields",
    "augment_ama_with_derived_fields",
    "export_phase_field_as_heightmap_stl",
    "export_phase_field_as_obj",
    "export_phase_field_as_ama",
    # Ribbon
    "PRRibbonConfig",
    "generate_centerline",
    "generate_ribbon_mesh",
    "export_ribbon_as_ama",
    "save_ribbon_ama",
    # Volume (3D)
    "PRVolumeConfig",
    "PRVolumeState",
    "relax_phase_volume",
    "extract_isosurface",
    "export_volume_as_ama",
    "save_volume_ama",
]
