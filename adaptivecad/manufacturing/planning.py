"""Triangle-free additive and subtractive planners.

Both planners consume the same curve-native cross-section source.  Additive
planning emits concentric extrusion paths.  Subtractive planning emits outside
and inside waterline finishing paths with tool-center compensation.  Neither
planner accepts or constructs a polygon mesh.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .curve_ir import ManufacturingJob, ManufacturingLayer
from .infinity_root_source import InfinityRootLoftSource


@dataclass(frozen=True)
class AdditivePlanSettings:
    layer_height_mm: float = 0.4
    extrusion_width_mm: float = 0.45
    filament_diameter_mm: float = 1.75
    perimeter_count: int = 2
    infill_density: float = 0.30
    perimeter_feed_mm_min: float = 2400.0
    infill_feed_mm_min: float = 3000.0
    travel_feed_mm_min: float = 7200.0
    nozzle_temperature_c: float = 205.0
    bed_temperature_c: float = 60.0
    tolerance_mm: float = 0.04

    def __post_init__(self) -> None:
        positive = (
            "layer_height_mm",
            "extrusion_width_mm",
            "filament_diameter_mm",
            "perimeter_feed_mm_min",
            "infill_feed_mm_min",
            "travel_feed_mm_min",
            "nozzle_temperature_c",
            "tolerance_mm",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        bed = float(self.bed_temperature_c)
        if not math.isfinite(bed) or bed < 0.0:
            raise ValueError("bed_temperature_c must be finite and nonnegative")
        object.__setattr__(self, "bed_temperature_c", bed)
        count = int(self.perimeter_count)
        if count < 1:
            raise ValueError("perimeter_count must be at least one")
        object.__setattr__(self, "perimeter_count", count)
        density = float(self.infill_density)
        if not 0.0 <= density <= 1.0:
            raise ValueError("infill_density must lie between zero and one")
        object.__setattr__(self, "infill_density", density)


@dataclass(frozen=True)
class SubtractivePlanSettings:
    step_down_mm: float = 2.0
    tool_diameter_mm: float = 3.0
    finish_feed_mm_min: float = 600.0
    plunge_feed_mm_min: float = 180.0
    rapid_feed_mm_min: float = 3000.0
    safe_height_mm: float = 5.0
    spindle_rpm: float = 12000.0
    tolerance_mm: float = 0.02
    climb_milling: bool = True

    def __post_init__(self) -> None:
        for name in (
            "step_down_mm",
            "tool_diameter_mm",
            "finish_feed_mm_min",
            "plunge_feed_mm_min",
            "rapid_feed_mm_min",
            "safe_height_mm",
            "spindle_rpm",
            "tolerance_mm",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)


def plan_additive_loft(
    source: InfinityRootLoftSource,
    settings: AdditivePlanSettings | None = None,
) -> ManufacturingJob:
    """Create concentric curve-native FDM layers from an Infinity Root loft."""

    settings = AdditivePlanSettings() if settings is None else settings
    occupied_perimeter_width = 2.0 * settings.perimeter_count * settings.extrusion_width_mm
    if occupied_perimeter_width >= source.band_width_mm:
        raise ValueError("perimeters consume the entire Infinity Root loft band")
    height = source.z_max - source.z_min
    layer_count = max(1, int(math.ceil(height / settings.layer_height_mm)))
    effective_layer_height = height / layer_count
    layers: list[ManufacturingLayer] = []

    for layer_index in range(layer_count):
        model_z = source.z_min + (layer_index + 0.5) * effective_layer_height
        paths = []
        for perimeter_index in range(settings.perimeter_count):
            inset = (perimeter_index + 0.5) * settings.extrusion_width_mm
            paths.append(
                source.normal_offset_path_at(
                    model_z,
                    boundary_radial_offset_mm=source.half_band_width,
                    normal_offset_mm=inset,
                    fit_tolerance_mm=settings.tolerance_mm,
                    role="additive_outer_perimeter",
                    clockwise=False,
                    channel="model",
                    feed_mm_min=settings.perimeter_feed_mm_min,
                    metadata={
                        "perimeter_index": perimeter_index,
                        "extrusion_width_mm": settings.extrusion_width_mm,
                        "layer_height_mm": effective_layer_height,
                    },
                )
            )
            paths.append(
                source.normal_offset_path_at(
                    model_z,
                    boundary_radial_offset_mm=-source.half_band_width,
                    normal_offset_mm=inset,
                    fit_tolerance_mm=settings.tolerance_mm,
                    role="additive_inner_perimeter",
                    clockwise=True,
                    channel="model",
                    feed_mm_min=settings.perimeter_feed_mm_min,
                    metadata={
                        "perimeter_index": perimeter_index,
                        "extrusion_width_mm": settings.extrusion_width_mm,
                        "layer_height_mm": effective_layer_height,
                    },
                )
            )

        if settings.infill_density > 0.0:
            low = (
                -source.half_band_width
                + settings.perimeter_count * settings.extrusion_width_mm
                + 0.5 * settings.extrusion_width_mm
            )
            high = (
                source.half_band_width
                - settings.perimeter_count * settings.extrusion_width_mm
                - 0.5 * settings.extrusion_width_mm
            )
            spacing = settings.extrusion_width_mm / settings.infill_density
            offset = low
            infill_index = 0
            while offset <= high + 1e-10:
                clockwise = (layer_index + infill_index) % 2 == 1
                paths.append(
                    source.path_at(
                        model_z,
                        radial_offset_mm=offset,
                        role="additive_concentric_infill",
                        clockwise=clockwise,
                        channel="model",
                        feed_mm_min=settings.infill_feed_mm_min,
                        metadata={
                            "infill_index": infill_index,
                            "infill_density": settings.infill_density,
                            "extrusion_width_mm": settings.extrusion_width_mm,
                            "layer_height_mm": effective_layer_height,
                        },
                    )
                )
                offset += spacing
                infill_index += 1

        layers.append(
            ManufacturingLayer(
                z=model_z,
                paths=tuple(paths),
                metadata={
                    "layer_index": layer_index,
                    "effective_layer_height_mm": effective_layer_height,
                    "model_z_mm": model_z,
                },
            )
        )

    serialized_settings = asdict(settings)
    serialized_settings["effective_layer_height_mm"] = effective_layer_height
    serialized_settings["planner"] = "direct_concentric_curve_layers"
    return ManufacturingJob(
        job_id=f"{source.source_id}-additive",
        process="additive",
        source_id=source.source_id,
        layers=tuple(layers),
        tolerance_mm=settings.tolerance_mm,
        settings=serialized_settings,
        source_provenance=source.provenance(),
    )


def plan_subtractive_waterlines(
    source: InfinityRootLoftSource,
    settings: SubtractivePlanSettings | None = None,
) -> ManufacturingJob:
    """Create tool-compensated outside/inside finishing waterlines."""

    settings = SubtractivePlanSettings() if settings is None else settings
    tool_radius = 0.5 * settings.tool_diameter_mm
    smallest_center_radius = min(value for row in source.page_radii for value in row)
    if smallest_center_radius - source.half_band_width - tool_radius <= 0.0:
        raise ValueError("selected tool does not fit inside the loft opening")

    height = source.z_max - source.z_min
    pass_count = max(1, int(math.ceil(height / settings.step_down_mm)))
    effective_step_down = height / pass_count
    layers: list[ManufacturingLayer] = []
    for pass_index in range(pass_count):
        depth = (pass_index + 1) * effective_step_down
        model_z = source.z_max - depth
        outer = source.normal_offset_path_at(
            model_z,
            boundary_radial_offset_mm=source.half_band_width,
            normal_offset_mm=-tool_radius,
            fit_tolerance_mm=settings.tolerance_mm,
            role="subtractive_outer_finish_waterline",
            clockwise=False,
            channel="cutting_tool",
            feed_mm_min=settings.finish_feed_mm_min,
            metadata={
                "tool_center_compensation": "outside_along_local_normal",
                "tool_radius_mm": tool_radius,
                "pass_index": pass_index,
            },
        )
        inner = source.normal_offset_path_at(
            model_z,
            boundary_radial_offset_mm=-source.half_band_width,
            normal_offset_mm=-tool_radius,
            fit_tolerance_mm=settings.tolerance_mm,
            role="subtractive_inner_finish_waterline",
            clockwise=True,
            channel="cutting_tool",
            feed_mm_min=settings.finish_feed_mm_min,
            metadata={
                "tool_center_compensation": "inside_hole_along_local_normal",
                "tool_radius_mm": tool_radius,
                "pass_index": pass_index,
            },
        )
        if settings.climb_milling:
            outer = outer.reversed()
            inner = inner.reversed()
        paths = (outer, inner)
        layers.append(
            ManufacturingLayer(
                z=-depth,
                paths=paths,
                metadata={
                    "pass_index": pass_index,
                    "model_z_mm": model_z,
                    "machine_depth_mm": depth,
                    "effective_step_down_mm": effective_step_down,
                },
            )
        )

    serialized_settings = asdict(settings)
    serialized_settings["effective_step_down_mm"] = effective_step_down
    serialized_settings["planner"] = "direct_curve_finish_waterlines"
    serialized_settings["scope"] = (
        "Finish waterlines only; stock definition, roughing, fixturing, and collision "
        "approval remain required before machining."
    )
    return ManufacturingJob(
        job_id=f"{source.source_id}-subtractive",
        process="subtractive",
        source_id=source.source_id,
        layers=tuple(layers),
        tolerance_mm=settings.tolerance_mm,
        settings=serialized_settings,
        source_provenance=source.provenance(),
    )


__all__ = [
    "AdditivePlanSettings",
    "SubtractivePlanSettings",
    "plan_additive_loft",
    "plan_subtractive_waterlines",
]
