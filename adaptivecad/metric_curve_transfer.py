"""Explicit coefficient-preserving model-to-chart copies, never face attachment.

Planar polynomial Beziers (including lines and trim/reverse) only. The mapping
is a user-declared placement into an intrinsic chart, not an isometry to a
curved surface. All validation precedes the receiving history's single commit.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

from .geom.directional_metric import _finite
from .geom.meshfree_tools import Curve, cross, dot, point, sub, unit
from .geom.metric_tools import unit_factor
from .geom.tool_document import ToolDocument, entity_record
from .metric_project import MetricCurve, MetricHistory, MetricProject


def _hash(value) -> str:
    return hashlib.sha256(value.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PlaneChartMapping:
    """Origin in source units; perpendicular axes are normalized and recorded.

    q = unit_factor * (dot(p-origin, x_axis), dot(p-origin, y_axis)).
    plane_tolerance is in SOURCE units. Accepted off-plane residual is removed
    explicitly; it is reported, not represented as exact 3D preservation.
    """
    origin: tuple = (0.0, 0.0, 0.0)
    x_axis: tuple = (1.0, 0.0, 0.0)
    y_axis: tuple = (0.0, 1.0, 0.0)
    plane_tolerance: float = 1e-9

    def __post_init__(self):
        origin = point(self.origin)
        u, v = unit(self.x_axis), unit(self.y_axis)
        if abs(dot(u, v)) > 1e-12:
            raise ValueError("Chart axes must be perpendicular; skew mappings are unsupported")
        # Remove only normalization roundoff, not a genuinely skew user frame.
        v = cross(unit(cross(u, v)), u)
        tolerance = _finite(self.plane_tolerance, "plane tolerance")
        if tolerance < 0:
            raise ValueError("Plane tolerance must be nonnegative in source units")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", u)
        object.__setattr__(self, "y_axis", v)
        object.__setattr__(self, "plane_tolerance", tolerance)


def _split_controls(controls, t):
    levels = [tuple(controls)]
    while len(levels[-1]) > 1:
        row = levels[-1]
        levels.append(tuple(point(tuple((1-t)*a[k] + t*b[k] for k in range(3)))
                            for a, b in zip(row, row[1:])))
    return tuple(row[0] for row in levels), tuple(row[-1] for row in reversed(levels))


def restricted_controls(curve: Curve) -> tuple:
    """de Casteljau restriction to the stored interval, preserving orientation.

    No fitting or display sampling. Floating-point roundoff still applies.
    """
    if not isinstance(curve, Curve) or curve.kind != "bezier":
        raise ValueError("Transfer supports polynomial Beziers and lines, not arcs or surfaces")
    if len(curve.points) > 32:
        raise ValueError("The receiving metric format supports at most 32 controls (degree 31)")
    a, b = curve.interval
    lo, hi = min(a, b), max(a, b)
    controls = curve.points
    if hi < 1:
        controls, _ = _split_controls(controls, hi)
    if lo > 0:
        _, controls = _split_controls(controls, lo / hi)
    return tuple(reversed(controls)) if a > b else tuple(controls)


@dataclass(frozen=True)
class TransferPreview:
    source: ToolDocument
    target: MetricProject
    source_name: str
    mapping: PlaneChartMapping
    curve: MetricCurve
    candidate: MetricProject
    factor: float
    max_plane_residual: float
    max_control_radius: float

    def receipt(self) -> dict:
        """Audit record for this copy, not a live association or experiment."""
        return {
            "schema": "adaptivecad.metric_curve_transfer", "version": 1,
            "operation": "explicit_planar_bezier_copy",
            "source_document_sha256": _hash(self.source),
            "target_before_sha256": _hash(self.target),
            "target_after_sha256": _hash(self.candidate),
            "source_name": self.source_name,
            "source_geometry": entity_record(self.source.get(self.source_name)),
            "source_unit": self.source.unit, "target_unit": self.target.patch.unit,
            "mapping": asdict(self.mapping), "unit_factor": self.factor,
            "max_control_plane_residual_source_units": self.max_plane_residual,
            "max_control_radius_target_units": self.max_control_radius,
            "target_curve": {"name": self.curve.name, "controls": self.curve.controls},
            "note": "One-time copy; no live link, face binding or curved-metric isometry. "
                    "Control-hull tests are conservative floating-point checks, not interval certification.",
        }


def preview_transfer(source: ToolDocument, target: MetricProject, source_name: str,
                     target_name: str, mapping: PlaneChartMapping) -> TransferPreview:
    """Validate the entire candidate; neither document nor history is mutated."""
    if not isinstance(source, ToolDocument) or not isinstance(target, MetricProject):
        raise ValueError("Expected model ToolDocument and receiving MetricProject")
    if not isinstance(mapping, PlaneChartMapping):
        raise ValueError("An explicit PlaneChartMapping is required")
    if target_name in {c.name for c in target.curves}:
        raise ValueError("Target name already exists; choose a new name (no implicit overwrite)")
    controls = restricted_controls(source.get(source_name))
    factor = _finite(unit_factor(source.unit, target.patch.unit), "unit factor")
    if factor <= 0:
        raise ValueError("Unit conversion must be positive")
    normal = unit(cross(mapping.x_axis, mapping.y_axis))
    mapped, residuals = [], []
    for p in controls:
        offset = point(sub(p, mapping.origin))
        residuals.append(abs(_finite(dot(offset, normal), "plane residual")))
        xy = tuple(_finite(factor * dot(offset, axis), "mapped coordinate")
                   for axis in (mapping.x_axis, mapping.y_axis))
        mapped.append(xy)
    error = max(residuals)
    if error > mapping.plane_tolerance:
        raise ValueError(f"Curve is outside the declared plane: control residual {error:.9g} "
                         f"> {mapping.plane_tolerance:.9g} {source.unit}; no copy made")
    radius = max(math.hypot(*p) for p in mapped)
    if radius > target.patch.radius:
        raise ValueError(f"Mapped control hull exceeds the chart disk ({radius:.9g} > "
                         f"{target.patch.radius:.9g} {target.patch.unit}); no automatic resize or clipping")
    curve = MetricCurve(target_name, tuple(mapped))
    candidate = target.put_curve(curve)  # also validates domain, name, count and metric
    return TransferPreview(source, target, source_name, mapping, curve, candidate, factor, error, radius)


def commit_transfer(preview: TransferPreview, current_source: ToolDocument,
                    target_history: MetricHistory) -> dict:
    """Commit one receiving-side undo step; reject a stale preview atomically."""
    if not isinstance(preview, TransferPreview) or not isinstance(target_history, MetricHistory):
        raise ValueError("Expected a validated preview and receiving MetricHistory")
    if current_source != preview.source or target_history.current != preview.target:
        raise ValueError("Source or target changed since preview; preview the transfer again")
    # Regenerate so even an API caller cannot substitute a forged candidate.
    checked = preview_transfer(current_source, target_history.current, preview.source_name,
                               preview.curve.name, preview.mapping)
    if checked != preview:
        raise ValueError("Transfer preview was modified; preview again")
    receipt = checked.receipt()
    json.dumps(receipt, allow_nan=False)  # ensure report generation cannot fail after commit
    target_history.commit(checked.candidate)
    return receipt
