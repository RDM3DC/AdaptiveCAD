"""Printer and CNC postprocessors for the triangle-free curve IR."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .curve_ir import (
    CircularArc2D,
    CubicBezier2D,
    CurvePath,
    CurveSegment2D,
    Line2D,
    ManufacturingJob,
    Point2D,
)


@dataclass(frozen=True)
class AdditivePostSettings:
    curve_mode: str = "native"
    work_offset_x_mm: float = 110.0
    work_offset_y_mm: float = 110.0
    chord_tolerance_mm: float | None = None
    retraction_distance_mm: float = 0.8
    retraction_feed_mm_min: float = 2400.0

    def __post_init__(self) -> None:
        if self.curve_mode not in {"native", "linearized"}:
            raise ValueError("curve_mode must be 'native' or 'linearized'")
        for name in (
            "work_offset_x_mm",
            "work_offset_y_mm",
            "retraction_distance_mm",
            "retraction_feed_mm_min",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if name.startswith("retraction") and value < 0.0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)
        if self.chord_tolerance_mm is not None:
            tolerance = float(self.chord_tolerance_mm)
            if not math.isfinite(tolerance) or tolerance <= 0.0:
                raise ValueError("chord_tolerance_mm must be finite and positive")
            object.__setattr__(self, "chord_tolerance_mm", tolerance)


@dataclass(frozen=True)
class SubtractivePostSettings:
    curve_mode: str = "native"
    work_offset_x_mm: float = 0.0
    work_offset_y_mm: float = 0.0
    chord_tolerance_mm: float | None = None

    def __post_init__(self) -> None:
        if self.curve_mode not in {"native", "linearized"}:
            raise ValueError("curve_mode must be 'native' or 'linearized'")
        for name in ("work_offset_x_mm", "work_offset_y_mm"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        if self.chord_tolerance_mm is not None:
            tolerance = float(self.chord_tolerance_mm)
            if not math.isfinite(tolerance) or tolerance <= 0.0:
                raise ValueError("chord_tolerance_mm must be finite and positive")
            object.__setattr__(self, "chord_tolerance_mm", tolerance)


def _translated(point: Point2D, offset_x: float, offset_y: float) -> Point2D:
    return (point[0] + offset_x, point[1] + offset_y)


def _arc_linear_points(arc: CircularArc2D, tolerance: float) -> tuple[Point2D, ...]:
    if tolerance >= arc.radius:
        maximum_angle = math.pi / 2.0
    else:
        maximum_angle = 2.0 * math.acos(max(-1.0, min(1.0, 1.0 - tolerance / arc.radius)))
    maximum_angle = max(maximum_angle, 1e-5)
    count = max(1, int(math.ceil(abs(arc.sweep_angle) / maximum_angle)))
    return tuple(arc.evaluate(index / count) for index in range(1, count + 1))


def _linearized_endpoints(
    segment: CurveSegment2D, tolerance: float
) -> tuple[Point2D, ...]:
    if isinstance(segment, Line2D):
        return (segment.end,)
    if isinstance(segment, CircularArc2D):
        return _arc_linear_points(segment, tolerance)
    if isinstance(segment, CubicBezier2D):
        return segment.flatten(tolerance)[1:]
    raise TypeError(f"unsupported manufacturing segment: {type(segment)!r}")


def _native_motion(
    segment: CurveSegment2D,
    *,
    offset_x: float,
    offset_y: float,
    feed: float,
    extrusion_end: float | None,
) -> str:
    end = _translated(segment.end, offset_x, offset_y)
    extrusion = "" if extrusion_end is None else f" E{extrusion_end:.5f}"
    if isinstance(segment, Line2D):
        return f"G1 X{end[0]:.5f} Y{end[1]:.5f}{extrusion} F{feed:.1f}"
    if isinstance(segment, CircularArc2D):
        start = _translated(segment.start, offset_x, offset_y)
        center = _translated(segment.center, offset_x, offset_y)
        code = "G2" if segment.clockwise else "G3"
        return (
            f"{code} X{end[0]:.5f} Y{end[1]:.5f} "
            f"I{center[0] - start[0]:.5f} J{center[1] - start[1]:.5f}"
            f"{extrusion} F{feed:.1f}"
        )
    if isinstance(segment, CubicBezier2D):
        # Common XY cubic-Bézier G5 convention: I/J is control 1 relative
        # to the start; P/Q is control 2 relative to the endpoint.
        return (
            f"G5 X{end[0]:.5f} Y{end[1]:.5f} "
            f"I{segment.p1[0] - segment.p0[0]:.5f} "
            f"J{segment.p1[1] - segment.p0[1]:.5f} "
            f"P{segment.p2[0] - segment.p3[0]:.5f} "
            f"Q{segment.p2[1] - segment.p3[1]:.5f}"
            f"{extrusion} F{feed:.1f}"
        )
    raise TypeError(f"unsupported manufacturing segment: {type(segment)!r}")


def _linear_motion(
    endpoint: Point2D,
    *,
    offset_x: float,
    offset_y: float,
    feed: float,
    extrusion_end: float | None,
) -> str:
    end = _translated(endpoint, offset_x, offset_y)
    extrusion = "" if extrusion_end is None else f" E{extrusion_end:.5f}"
    return f"G1 X{end[0]:.5f} Y{end[1]:.5f}{extrusion} F{feed:.1f}"


def _motion_count(gcode: str) -> dict[str, int]:
    counts = {"G0": 0, "G1": 0, "G2": 0, "G3": 0, "G5": 0}
    for line in gcode.splitlines():
        code = line.split(maxsplit=1)[0] if line and not line.startswith(";") else ""
        if code in counts:
            counts[code] += 1
    return counts


def _postprocess_audit(
    job: ManufacturingJob,
    gcode: str,
    *,
    curve_mode: str,
    chord_tolerance_mm: float,
) -> dict[str, Any]:
    counts = _motion_count(gcode)
    return {
        "job_id": job.job_id,
        "process": job.process,
        "curve_mode": curve_mode,
        "authoritative_ir_triangle_free": True,
        "surface_mesh_generated": False,
        "motion_counts": counts,
        "native_bezier_motion_present": counts["G5"] > 0,
        "controller_linearization_used": curve_mode == "linearized",
        "controller_chord_tolerance_mm": chord_tolerance_mm,
        "claim_boundary": (
            "Linearized mode approximates curves with controller line motion only; "
            "it does not construct surface facets or a triangle mesh."
        ),
    }


def postprocess_additive_gcode(
    job: ManufacturingJob,
    settings: AdditivePostSettings | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generate printer G-code directly from curve paths."""

    if job.process != "additive":
        raise ValueError("additive postprocessor requires an additive job")
    settings = AdditivePostSettings() if settings is None else settings
    tolerance = settings.chord_tolerance_mm or job.tolerance_mm
    layer_height = float(job.settings["effective_layer_height_mm"])
    extrusion_width = float(job.settings["extrusion_width_mm"])
    filament_diameter = float(job.settings["filament_diameter_mm"])
    filament_area = math.pi * (0.5 * filament_diameter) ** 2
    extrusion_per_mm = layer_height * extrusion_width / filament_area
    travel_feed = float(job.settings["travel_feed_mm_min"])
    nozzle_temp = float(job.settings["nozzle_temperature_c"])
    bed_temp = float(job.settings["bed_temperature_c"])

    lines = [
        "; AdaptiveCAD Direct Manufacturing — additive",
        f"; Source: {job.source_id}",
        "; Authoritative input: curve IR; no surface mesh",
        f"; Curve mode: {settings.curve_mode}",
        (
            "; Native G5 convention: I/J from segment start, P/Q from segment end"
            if settings.curve_mode == "native"
            else f"; Controller line tolerance: {tolerance:.5f} mm"
        ),
        "G21 ; millimetres",
        "G90 ; absolute XYZ",
        "M82 ; absolute extrusion",
        f"M140 S{bed_temp:.0f}",
        f"M104 S{nozzle_temp:.0f}",
        f"M190 S{bed_temp:.0f}",
        f"M109 S{nozzle_temp:.0f}",
        "G28",
        "G92 E0",
    ]
    extrusion = 0.0
    retracted = False
    for layer_index, layer in enumerate(job.layers):
        lines.append(f"; LAYER {layer_index} MODEL_Z={layer.z:.5f}")
        lines.append(f"G0 Z{layer.z:.5f} F{travel_feed:.1f}")
        for path_index, path in enumerate(layer.paths):
            feed = path.feed_mm_min or float(job.settings["perimeter_feed_mm_min"])
            start = _translated(
                path.start,
                settings.work_offset_x_mm,
                settings.work_offset_y_mm,
            )
            if settings.retraction_distance_mm > 0.0:
                extrusion -= settings.retraction_distance_mm
                lines.append(
                    f"G1 E{extrusion:.5f} F{settings.retraction_feed_mm_min:.1f} ; retract"
                )
                retracted = True
            lines.append(f"G0 X{start[0]:.5f} Y{start[1]:.5f} F{travel_feed:.1f}")
            if retracted:
                extrusion += settings.retraction_distance_mm
                lines.append(
                    f"G1 E{extrusion:.5f} F{settings.retraction_feed_mm_min:.1f} ; restore"
                )
                retracted = False
            lines.append(f"; PATH {path_index} {path.role} {path.orientation}")
            for segment in path.segments:
                if settings.curve_mode == "native":
                    extrusion += segment.length() * extrusion_per_mm
                    lines.append(
                        _native_motion(
                            segment,
                            offset_x=settings.work_offset_x_mm,
                            offset_y=settings.work_offset_y_mm,
                            feed=feed,
                            extrusion_end=extrusion,
                        )
                    )
                else:
                    current = segment.start
                    for endpoint in _linearized_endpoints(segment, tolerance):
                        extrusion += math.hypot(
                            endpoint[0] - current[0], endpoint[1] - current[1]
                        ) * extrusion_per_mm
                        lines.append(
                            _linear_motion(
                                endpoint,
                                offset_x=settings.work_offset_x_mm,
                                offset_y=settings.work_offset_y_mm,
                                feed=feed,
                                extrusion_end=extrusion,
                            )
                        )
                        current = endpoint
    lines.extend(
        [
            "M104 S0",
            "M140 S0",
            "G91",
            "G0 Z10 F3000",
            "G90",
            "M84",
            "; End AdaptiveCAD direct curve job",
        ]
    )
    gcode = "\n".join(lines) + "\n"
    return gcode, _postprocess_audit(
        job,
        gcode,
        curve_mode=settings.curve_mode,
        chord_tolerance_mm=tolerance,
    )


def postprocess_subtractive_gcode(
    job: ManufacturingJob,
    settings: SubtractivePostSettings | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generate finish-waterline CNC code directly from curve paths."""

    if job.process != "subtractive":
        raise ValueError("subtractive postprocessor requires a subtractive job")
    settings = SubtractivePostSettings() if settings is None else settings
    tolerance = settings.chord_tolerance_mm or job.tolerance_mm
    safe_height = float(job.settings["safe_height_mm"])
    rapid_feed = float(job.settings["rapid_feed_mm_min"])
    plunge_feed = float(job.settings["plunge_feed_mm_min"])
    spindle_rpm = float(job.settings["spindle_rpm"])
    lines = [
        "; AdaptiveCAD Direct Manufacturing — subtractive finish waterlines",
        f"; Source: {job.source_id}",
        "; Authoritative input: curve IR; no surface mesh",
        "; VERIFY STOCK, WORK OFFSET, TOOL, FIXTURING, AND COLLISIONS BEFORE RUNNING",
        f"; Curve mode: {settings.curve_mode}",
        (
            "; Native G5 convention: I/J from segment start, P/Q from segment end"
            if settings.curve_mode == "native"
            else f"; Controller line tolerance: {tolerance:.5f} mm"
        ),
        "G21 ; millimetres",
        "G90 ; absolute",
        "G17 ; XY plane",
        "G94 ; feed per minute",
        f"S{spindle_rpm:.0f} M3",
        f"G0 Z{safe_height:.5f} F{rapid_feed:.1f}",
    ]
    for level_index, layer in enumerate(job.layers):
        lines.append(
            f"; WATERLINE {level_index} MACHINE_Z={layer.z:.5f} "
            f"MODEL_Z={float(layer.metadata['model_z_mm']):.5f}"
        )
        for path_index, path in enumerate(layer.paths):
            feed = path.feed_mm_min or float(job.settings["finish_feed_mm_min"])
            start = _translated(
                path.start,
                settings.work_offset_x_mm,
                settings.work_offset_y_mm,
            )
            lines.append(f"G0 Z{safe_height:.5f} F{rapid_feed:.1f}")
            lines.append(f"G0 X{start[0]:.5f} Y{start[1]:.5f} F{rapid_feed:.1f}")
            lines.append(f"G1 Z{layer.z:.5f} F{plunge_feed:.1f}")
            lines.append(f"; PATH {path_index} {path.role} {path.orientation}")
            for segment in path.segments:
                if settings.curve_mode == "native":
                    lines.append(
                        _native_motion(
                            segment,
                            offset_x=settings.work_offset_x_mm,
                            offset_y=settings.work_offset_y_mm,
                            feed=feed,
                            extrusion_end=None,
                        )
                    )
                else:
                    for endpoint in _linearized_endpoints(segment, tolerance):
                        lines.append(
                            _linear_motion(
                                endpoint,
                                offset_x=settings.work_offset_x_mm,
                                offset_y=settings.work_offset_y_mm,
                                feed=feed,
                                extrusion_end=None,
                            )
                        )
            lines.append(f"G0 Z{safe_height:.5f} F{rapid_feed:.1f}")
    lines.extend(["M5", f"G0 Z{safe_height:.5f}", "M30", "; End AdaptiveCAD direct curve job"])
    gcode = "\n".join(lines) + "\n"
    return gcode, _postprocess_audit(
        job,
        gcode,
        curve_mode=settings.curve_mode,
        chord_tolerance_mm=tolerance,
    )


__all__ = [
    "AdditivePostSettings",
    "SubtractivePostSettings",
    "postprocess_additive_gcode",
    "postprocess_subtractive_gcode",
]
