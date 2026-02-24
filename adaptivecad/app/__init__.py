"""AdaptiveCAD Main Application Package

This package provides the complete CAD application with:
- Full SDF-based rendering (no triangles)
- All mathematical surfaces accessible
- Integrated scene management
- Object selection and transform gizmos
- Array, align, and mirror tools
- Boolean operations
- Measurement and analysis tools
- Camera presets
- Direct G-code export
"""

from .gizmos import (
    GizmoAxis,
    GizmoColors,
    GizmoController,
    GizmoMode,
    GizmoRenderer,
    GizmoState,
    SelectionManager,
)
from .interactive_viewport import GizmoOverlayWidget, InteractiveViewport
from .main_window import AdaptiveCADApp, launch_app
from .sdf_slicer import PrintSettings, SDFSlicer, Slice, SliceContour
from .selection import ObjectPicker, PickResult, RayPicker, SelectionHighlighter

__all__ = [
    # Main app
    "AdaptiveCADApp", 
    "launch_app",
    # Slicer
    "SDFSlicer",
    "PrintSettings",
    "Slice",
    "SliceContour",
    # Gizmos
    "GizmoMode",
    "GizmoAxis",
    "GizmoState",
    "GizmoController",
    "SelectionManager",
    "GizmoRenderer",
    "GizmoColors",
    # Selection
    "RayPicker",
    "PickResult",
    "SelectionHighlighter",
    "ObjectPicker",
    # Viewport
    "InteractiveViewport",
    "GizmoOverlayWidget",
]
