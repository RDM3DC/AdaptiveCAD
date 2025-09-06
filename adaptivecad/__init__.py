"""Top-level helpers for AdaptiveCAD.

This module previously imported *all* submodules eagerly, including those that
depend on optional heavy/scientific libraries like SciPy. That made a simple
`import adaptivecad` fail if SciPy wasn't present (e.g. for users who only want
the core CAD + GUI features). We now make those imports **lazy / optional** so
missing SciPy does not block the GUI startup.

If an optional domain (cosmic curves or quantum visualization) fails to import,
we record the exception in a private variable so tooling / diagnostics can
inspect it if needed, while keeping the public API available for everything
else.
"""

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
]

from .params import ParamEnv  # lightweight
from .spacetime import (
    Event,
    minkowski_interval,
    lorentz_boost_x,
    apply_boost,
    light_cone,
)

# --- Optional: Cosmic Curve Tools ---
_COSMIC_IMPORT_ERROR = None
try:  # pragma: no cover - optional dependency path
    from .cosmic_curve_tools import (
        BizarreCurveFeature,
        CosmicSplineFeature,
        NDFieldExplorerFeature,
    )
except Exception as _e:  # Broad except: we intentionally insulate core import
    _COSMIC_IMPORT_ERROR = _e
else:  # Only extend API if import succeeded
    __all__ += [
        "BizarreCurveFeature",
        "CosmicSplineFeature",
        "NDFieldExplorerFeature",
    ]

# --- Optional: Quantum Visualization (SciPy heavy) ---
_QUANTUM_IMPORT_ERROR = None
try:  # pragma: no cover - optional dependency path
    from .quantum_visualization import (
        QuantumState,
        WavefunctionVisualizer,
        EntanglementVisualizer,
        QuantumFieldVisualizer,
    )
except Exception as _e:  # noqa: BLE001
    _QUANTUM_IMPORT_ERROR = _e
else:
    __all__ += [
        "QuantumState",
        "WavefunctionVisualizer",
        "EntanglementVisualizer",
        "QuantumFieldVisualizer",
    ]


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


# Diagnostic helper (not exported) to introspect optional import status.
def _optional_import_status():  # pragma: no cover - debug utility
    return {
        "cosmic_ok": _COSMIC_IMPORT_ERROR is None,
        "quantum_ok": _QUANTUM_IMPORT_ERROR is None,
        "cosmic_error": repr(_COSMIC_IMPORT_ERROR) if _COSMIC_IMPORT_ERROR else None,
        "quantum_error": repr(_QUANTUM_IMPORT_ERROR) if _QUANTUM_IMPORT_ERROR else None,
    }