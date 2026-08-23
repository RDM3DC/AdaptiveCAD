"""Curve-native, triangle-free manufacturing tools for AdaptiveCAD."""

from .contract import (
    CONTRACT_VERSION,
    ContractError,
    audit_job,
    scale_invariance_gate,
    validate_shared_source,
    verification_suite,
)
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
from .engineering_bracket import (
    BracketAdditiveSettings,
    BracketSubtractiveSettings,
    CircleSpec,
    EngineeringBracketSource,
    RoundedRectangleSpec,
    plan_engineering_bracket_additive,
    plan_engineering_bracket_subtractive,
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
    "CONTRACT_VERSION",
    "ContractError",
    "audit_job",
    "scale_invariance_gate",
    "validate_shared_source",
    "verification_suite",
    "RoundedRectangleSpec",
    "CircleSpec",
    "EngineeringBracketSource",
    "BracketAdditiveSettings",
    "BracketSubtractiveSettings",
    "plan_engineering_bracket_additive",
    "plan_engineering_bracket_subtractive",
]
