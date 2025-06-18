"""Top-level helpers for AdaptiveCAD."""

__all__ = [
    "generate_gcode_from_shape",
    "generate_gcode_from_ama_file",
    "generate_gcode_from_ama_data",
    "ParamEnv",
    "load_stl",
    "export_slices_from_ama",
    # Spacetime helpers
    "Event",
    "minkowski_interval",
    "lorentz_boost_x",
    "apply_boost",
    "light_cone",
    "QuantumConfig",
    "WavefunctionVisualizer",
    "EntanglementVisualizer",
    "QuantumState",
]

from .params import ParamEnv
from .spacetime import (
    Event,
    minkowski_interval,
    lorentz_boost_x,
    apply_boost,
    light_cone,
)
from .quantum import (
    QuantumConfig,
    WavefunctionVisualizer,
    EntanglementVisualizer,
    QuantumState,
)


def generate_gcode_from_shape(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_shape
    return generate_gcode_from_shape(*args, **kwargs)


def generate_gcode_from_ama_file(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_ama_file
    return generate_gcode_from_ama_file(*args, **kwargs)


def generate_gcode_from_ama_data(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_ama_data
    return generate_gcode_from_ama_data(*args, **kwargs)


def load_stl(*args, **kwargs):
    """Convenience wrapper for :func:`simple_stl.load_stl`."""
    from .simple_stl import load_stl as _load_stl
    return _load_stl(*args, **kwargs)


def export_slices_from_ama(*args, **kwargs):
    """Convenience wrapper for :func:`slice_export.export_slices_from_ama`."""
    from .slice_export import export_slices_from_ama as _export
    return _export(*args, **kwargs)
