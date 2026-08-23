"""Curve-native, triangle-free manufacturing tools for AdaptiveCAD."""

from .curve_ir import (
    MANUFACTURING_SCHEMA_VERSION,
    CircularArc2D,
    CubicBezier2D,
    CurvePath,
    Line2D,
    ManufacturingJob,
    ManufacturingLayer,
    audit_triangle_free_job,
)
from .gcode import (
    AdditivePostSettings,
    SubtractivePostSettings,
    postprocess_additive_gcode,
    postprocess_subtractive_gcode,
)
from .infinity_root_source import InfinityRootLoftSource
from .planning import (
    AdditivePlanSettings,
    SubtractivePlanSettings,
    plan_additive_loft,
    plan_subtractive_waterlines,
)

__all__ = [
    "MANUFACTURING_SCHEMA_VERSION",
    "Line2D",
    "CircularArc2D",
    "CubicBezier2D",
    "CurvePath",
    "ManufacturingLayer",
    "ManufacturingJob",
    "audit_triangle_free_job",
    "InfinityRootLoftSource",
    "AdditivePlanSettings",
    "SubtractivePlanSettings",
    "plan_additive_loft",
    "plan_subtractive_waterlines",
    "AdditivePostSettings",
    "SubtractivePostSettings",
    "postprocess_additive_gcode",
    "postprocess_subtractive_gcode",
]
