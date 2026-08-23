"""Analytic engineering-bracket source and triangle-free process planners.

The benchmark is intentionally ordinary: a rounded rectangular frame with a
rounded central cutout, four mounting holes, and an exact linear extrusion.
Its bounded purpose is to prove that one analytic source can drive additive
and subtractive manufacturing without promoting a mesh to authoritative
geometry.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from .curve_ir import (
    CircularArc2D,
    CurvePath,
    CurveSegment2D,
    Line2D,
    ManufacturingJob,
    ManufacturingLayer,
)


SOURCE_SCHEMA_VERSION = "adaptivecad.analytic_extrusion/1.0"
CLAIM_BOUNDARY = (
    "This benchmark validates analytic regularized difference for rounded "
    "rectangles and circles. It is not yet a general arbitrary-surface B-rep "
    "Boolean proof."
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _positive_float(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _point2(value: Sequence[float], name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two coordinates")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(component) for component in point):
        raise ValueError(f"{name} must contain finite coordinates")
    return point


@dataclass(frozen=True)
class RoundedRectangleSpec:
    center: tuple[float, float]
    width_mm: float
    height_mm: float
    radius_mm: float

    def __post_init__(self) -> None:
        center = _point2(self.center, "rounded rectangle center")
        width = _positive_float(self.width_mm, "rounded rectangle width_mm")
        height = _positive_float(self.height_mm, "rounded rectangle height_mm")
        radius = _positive_float(self.radius_mm, "rounded rectangle radius_mm")
        if radius > min(width, height) / 2.0:
            raise ValueError("rounded rectangle radius exceeds half its smaller dimension")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "width_mm", width)
        object.__setattr__(self, "height_mm", height)
        object.__setattr__(self, "radius_mm", radius)

    @property
    def area_mm2(self) -> float:
        return (
            self.width_mm * self.height_mm
            - (4.0 - math.pi) * self.radius_mm * self.radius_mm
        )

    def offset(self, distance_mm: float) -> "RoundedRectangleSpec":
        distance = float(distance_mm)
        if not math.isfinite(distance):
            raise ValueError("rounded rectangle offset must be finite")
        return RoundedRectangleSpec(
            center=self.center,
            width_mm=self.width_mm + 2.0 * distance,
            height_mm=self.height_mm + 2.0 * distance,
            radius_mm=self.radius_mm + distance,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "center": list(self.center),
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "radius_mm": self.radius_mm,
        }


@dataclass(frozen=True)
class CircleSpec:
    center: tuple[float, float]
    radius_mm: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "center", _point2(self.center, "circle center"))
        object.__setattr__(
            self,
            "radius_mm",
            _positive_float(self.radius_mm, "circle radius_mm"),
        )

    @property
    def area_mm2(self) -> float:
        return math.pi * self.radius_mm * self.radius_mm

    def offset(self, distance_mm: float) -> "CircleSpec":
        distance = float(distance_mm)
        if not math.isfinite(distance):
            raise ValueError("circle offset must be finite")
        return CircleSpec(self.center, self.radius_mm + distance)

    def to_dict(self) -> dict[str, Any]:
        return {"center": list(self.center), "radius_mm": self.radius_mm}


@dataclass(frozen=True)
class EngineeringBracketSource:
    outer: RoundedRectangleSpec
    cutout: RoundedRectangleSpec
    holes: tuple[CircleSpec, ...]
    thickness_mm: float

    def __post_init__(self) -> None:
        holes = tuple(self.holes)
        if not holes:
            raise ValueError("engineering bracket requires at least one mounting hole")
        thickness = _positive_float(self.thickness_mm, "bracket thickness_mm")
        object.__setattr__(self, "holes", holes)
        object.__setattr__(self, "thickness_mm", thickness)

        outer_left = self.outer.center[0] - self.outer.width_mm / 2.0
        outer_right = self.outer.center[0] + self.outer.width_mm / 2.0
        outer_bottom = self.outer.center[1] - self.outer.height_mm / 2.0
        outer_top = self.outer.center[1] + self.outer.height_mm / 2.0
        cut_left = self.cutout.center[0] - self.cutout.width_mm / 2.0
        cut_right = self.cutout.center[0] + self.cutout.width_mm / 2.0
        cut_bottom = self.cutout.center[1] - self.cutout.height_mm / 2.0
        cut_top = self.cutout.center[1] + self.cutout.height_mm / 2.0
        if not (
            outer_left < cut_left < cut_right < outer_right
            and outer_bottom < cut_bottom < cut_top < outer_top
        ):
            raise ValueError("rounded cutout must lie strictly inside the outer body")
        for hole in holes:
            x, y = hole.center
            if not (
                outer_left < x - hole.radius_mm
                and x + hole.radius_mm < outer_right
                and outer_bottom < y - hole.radius_mm
                and y + hole.radius_mm < outer_top
            ):
                raise ValueError("mounting hole must lie strictly inside the outer body")
            if (
                cut_left < x + hole.radius_mm
                and x - hole.radius_mm < cut_right
                and cut_bottom < y + hole.radius_mm
                and y - hole.radius_mm < cut_top
            ):
                raise ValueError("mounting holes must not overlap the central cutout")
        for index, left in enumerate(holes):
            for right in holes[index + 1 :]:
                if math.dist(left.center, right.center) <= left.radius_mm + right.radius_mm:
                    raise ValueError("mounting holes must not overlap")

    @classmethod
    def default(cls) -> "EngineeringBracketSource":
        return cls(
            outer=RoundedRectangleSpec((0.0, 0.0), 100.0, 60.0, 8.0),
            cutout=RoundedRectangleSpec((0.0, 0.0), 58.0, 24.0, 4.5),
            holes=(
                CircleSpec((-40.0, -20.0), 3.25),
                CircleSpec((40.0, -20.0), 3.25),
                CircleSpec((40.0, 20.0), 3.25),
                CircleSpec((-40.0, 20.0), 3.25),
            ),
            thickness_mm=8.0,
        )

    def _without_id(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_SCHEMA_VERSION,
            "kind": "analytic_extrusion",
            "name": "AdaptiveCAD Triangle-Free Engineering Frame Bracket",
            "units": "mm",
            "native_representation": (
                "analytic_planar_regularized_difference_plus_linear_extrusion"
            ),
            "mesh_created": False,
            "height_mm": self.thickness_mm,
            "construction": {
                "kind": "regularized_difference",
                "base": {"kind": "rounded_rectangle", **self.outer.to_dict()},
                "subtract": [
                    {
                        "feature_id": "center_cutout",
                        "kind": "rounded_rectangle",
                        **self.cutout.to_dict(),
                    },
                    *[
                        {
                            "feature_id": f"mounting_hole_{index + 1}",
                            "kind": "circle",
                            **hole.to_dict(),
                        }
                        for index, hole in enumerate(self.holes)
                    ],
                ],
            },
            "topology": {
                "solid_count": 1,
                "outer_boundary_loop_count": 1,
                "inner_boundary_loop_count": 1 + len(self.holes),
                "through_cut_count": 1 + len(self.holes),
                "filleted_corner_count": 8,
            },
            "claim_boundary": CLAIM_BOUNDARY,
        }

    @property
    def source_id(self) -> str:
        digest = hashlib.sha256(
            _canonical_json(self._without_id()).encode("utf-8")
        ).hexdigest()[:20]
        return f"engineering-bracket-{digest}"

    def to_dict(self) -> dict[str, Any]:
        result = self._without_id()
        result["source_id"] = self.source_id
        removed_area = self.cutout.area_mm2 + sum(hole.area_mm2 for hole in self.holes)
        net_area = self.outer.area_mm2 - removed_area
        result["analytic_properties"] = {
            "outer_area_mm2": self.outer.area_mm2,
            "removed_area_mm2": removed_area,
            "net_area_mm2": net_area,
            "net_volume_mm3": net_area * self.thickness_mm,
        }
        return result

    def provenance(self) -> dict[str, Any]:
        source = self.to_dict()
        return {
            "source_id": self.source_id,
            "source_kind": source["kind"],
            "native_representation": source["native_representation"],
            "mesh_created": False,
            "height_mm": source["height_mm"],
            "construction": source["construction"],
            "topology": source["topology"],
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _reverse_segments(
    segments: Sequence[CurveSegment2D],
) -> tuple[CurveSegment2D, ...]:
    return tuple(segment.reversed() for segment in reversed(segments))


def rounded_rectangle_segments(
    shape: RoundedRectangleSpec, *, clockwise: bool = False
) -> tuple[CurveSegment2D, ...]:
    cx, cy = shape.center
    half_width = shape.width_mm / 2.0
    half_height = shape.height_mm / 2.0
    radius = shape.radius_mm
    left, right = cx - half_width, cx + half_width
    bottom, top = cy - half_height, cy + half_height
    segments: tuple[CurveSegment2D, ...] = (
        Line2D((left + radius, bottom), (right - radius, bottom)),
        CircularArc2D(
            (right - radius, bottom + radius), radius, -math.pi / 2.0, math.pi / 2.0
        ),
        Line2D((right, bottom + radius), (right, top - radius)),
        CircularArc2D(
            (right - radius, top - radius), radius, 0.0, math.pi / 2.0
        ),
        Line2D((right - radius, top), (left + radius, top)),
        CircularArc2D(
            (left + radius, top - radius), radius, math.pi / 2.0, math.pi / 2.0
        ),
        Line2D((left, top - radius), (left, bottom + radius)),
        CircularArc2D(
            (left + radius, bottom + radius), radius, math.pi, math.pi / 2.0
        ),
    )
    return _reverse_segments(segments) if clockwise else segments


def circle_segments(
    shape: CircleSpec, *, clockwise: bool = False
) -> tuple[CurveSegment2D, ...]:
    segments: tuple[CurveSegment2D, ...] = tuple(
        CircularArc2D(
            shape.center,
            shape.radius_mm,
            index * math.pi / 2.0,
            math.pi / 2.0,
        )
        for index in range(4)
    )
    return _reverse_segments(segments) if clockwise else segments


def _path(
    segments: Sequence[CurveSegment2D],
    *,
    role: str,
    channel: str,
    closed: bool,
    feed_mm_min: float,
    source_id: str,
    metadata: dict[str, Any] | None = None,
) -> CurvePath:
    path_metadata = {"source_id": source_id}
    if metadata:
        path_metadata.update(metadata)
    return CurvePath(
        segments=tuple(segments),
        closed=closed,
        role=role,
        channel=channel,
        feed_mm_min=feed_mm_min,
        metadata=path_metadata,
    )


def _rounded_rectangle_cross_interval(
    shape: RoundedRectangleSpec,
    scan_coordinate: float,
    *,
    horizontal: bool,
) -> tuple[float, float] | None:
    cx, cy = shape.center
    if horizontal:
        orthogonal_delta = abs(float(scan_coordinate) - cy)
        orthogonal_half = shape.height_mm / 2.0
        along_half = shape.width_mm / 2.0
        along_center = cx
    else:
        orthogonal_delta = abs(float(scan_coordinate) - cx)
        orthogonal_half = shape.width_mm / 2.0
        along_half = shape.height_mm / 2.0
        along_center = cy
    if orthogonal_delta > orthogonal_half:
        return None
    straight_half_extent = orthogonal_half - shape.radius_mm
    if orthogonal_delta <= straight_half_extent:
        extent = along_half
    else:
        corner_delta = orthogonal_delta - straight_half_extent
        extent = (
            along_half
            - shape.radius_mm
            + math.sqrt(
                max(
                    0.0,
                    shape.radius_mm * shape.radius_mm
                    - corner_delta * corner_delta,
                )
            )
        )
    return along_center - extent, along_center + extent


def _circle_cross_interval(
    shape: CircleSpec,
    scan_coordinate: float,
    *,
    horizontal: bool,
) -> tuple[float, float] | None:
    cx, cy = shape.center
    delta = float(scan_coordinate) - (cy if horizontal else cx)
    if abs(delta) > shape.radius_mm:
        return None
    extent = math.sqrt(max(0.0, shape.radius_mm**2 - delta**2))
    along_center = cx if horizontal else cy
    return along_center - extent, along_center + extent


def _subtract_interval(
    intervals: Sequence[tuple[float, float]],
    cutter: tuple[float, float] | None,
) -> list[tuple[float, float]]:
    if cutter is None:
        return list(intervals)
    cut_low, cut_high = cutter
    result: list[tuple[float, float]] = []
    for low, high in intervals:
        if cut_high <= low or cut_low >= high:
            result.append((low, high))
            continue
        if cut_low > low:
            result.append((low, min(cut_low, high)))
        if cut_high < high:
            result.append((max(cut_high, low), high))
    return result


def _scan_coordinates(lower: float, upper: float, spacing: float) -> Iterable[float]:
    index = math.ceil(lower / spacing)
    coordinate = index * spacing
    while coordinate <= upper + 1.0e-12:
        yield float(coordinate)
        index += 1
        coordinate = index * spacing


def _analytic_infill_paths(
    *,
    source_id: str,
    outer: RoundedRectangleSpec,
    cutout: RoundedRectangleSpec,
    holes: Sequence[CircleSpec],
    horizontal: bool,
    spacing_mm: float,
    extrusion_width_mm: float,
    feed_mm_min: float,
    role: str,
) -> list[CurvePath]:
    cx, cy = outer.center
    lower = (
        cy - outer.height_mm / 2.0
        if horizontal
        else cx - outer.width_mm / 2.0
    )
    upper = (
        cy + outer.height_mm / 2.0
        if horizontal
        else cx + outer.width_mm / 2.0
    )
    paths: list[CurvePath] = []
    reverse = False
    for scan in _scan_coordinates(lower, upper, spacing_mm):
        outer_interval = _rounded_rectangle_cross_interval(
            outer, scan, horizontal=horizontal
        )
        if outer_interval is None:
            continue
        intervals = _subtract_interval(
            [outer_interval],
            _rounded_rectangle_cross_interval(cutout, scan, horizontal=horizontal),
        )
        for hole in holes:
            intervals = _subtract_interval(
                intervals,
                _circle_cross_interval(hole, scan, horizontal=horizontal),
            )
        for along_start, along_end in intervals:
            if along_end - along_start < extrusion_width_mm * 0.75:
                continue
            if reverse:
                along_start, along_end = along_end, along_start
            if horizontal:
                start, end = (along_start, scan), (along_end, scan)
            else:
                start, end = (scan, along_start), (scan, along_end)
            paths.append(
                _path(
                    (Line2D(start, end),),
                    role=role,
                    channel="model",
                    closed=False,
                    feed_mm_min=feed_mm_min,
                    source_id=source_id,
                    metadata={
                        "planner": "analytic_scanline_regularized_difference",
                        "scan_orientation": "horizontal" if horizontal else "vertical",
                        "spacing_mm": spacing_mm,
                        "triangle_mesh_used": False,
                    },
                )
            )
            reverse = not reverse
    return paths


@dataclass(frozen=True)
class BracketAdditiveSettings:
    layer_height_mm: float = 0.2
    extrusion_width_mm: float = 0.45
    filament_diameter_mm: float = 1.75
    perimeter_count: int = 2
    infill_density: float = 0.30
    solid_layer_count: int = 4
    perimeter_feed_mm_min: float = 2400.0
    infill_feed_mm_min: float = 3000.0
    travel_feed_mm_min: float = 7200.0
    nozzle_temperature_c: float = 205.0
    bed_temperature_c: float = 60.0
    tolerance_mm: float = 0.025

    def __post_init__(self) -> None:
        for name in (
            "layer_height_mm",
            "extrusion_width_mm",
            "filament_diameter_mm",
            "perimeter_feed_mm_min",
            "infill_feed_mm_min",
            "travel_feed_mm_min",
            "nozzle_temperature_c",
            "tolerance_mm",
        ):
            object.__setattr__(self, name, _positive_float(getattr(self, name), name))
        bed = float(self.bed_temperature_c)
        if not math.isfinite(bed) or bed < 0.0:
            raise ValueError("bed_temperature_c must be finite and nonnegative")
        object.__setattr__(self, "bed_temperature_c", bed)
        if int(self.perimeter_count) < 1:
            raise ValueError("perimeter_count must be at least one")
        if int(self.solid_layer_count) < 0:
            raise ValueError("solid_layer_count must be nonnegative")
        if not 0.0 < float(self.infill_density) <= 1.0:
            raise ValueError("infill_density must lie in (0, 1]")
        object.__setattr__(self, "perimeter_count", int(self.perimeter_count))
        object.__setattr__(self, "solid_layer_count", int(self.solid_layer_count))
        object.__setattr__(self, "infill_density", float(self.infill_density))


@dataclass(frozen=True)
class BracketSubtractiveSettings:
    step_down_mm: float = 2.0
    tool_diameter_mm: float = 3.0
    finish_feed_mm_min: float = 600.0
    plunge_feed_mm_min: float = 180.0
    rapid_feed_mm_min: float = 3000.0
    safe_height_mm: float = 5.0
    spindle_rpm: float = 12000.0
    tolerance_mm: float = 0.015
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
            object.__setattr__(self, name, _positive_float(getattr(self, name), name))


def plan_engineering_bracket_additive(
    source: EngineeringBracketSource | None = None,
    settings: BracketAdditiveSettings | None = None,
) -> ManufacturingJob:
    source = EngineeringBracketSource.default() if source is None else source
    settings = BracketAdditiveSettings() if settings is None else settings
    layer_count = max(1, int(math.ceil(source.thickness_mm / settings.layer_height_mm)))
    layer_height = source.thickness_mm / layer_count
    layers: list[ManufacturingLayer] = []

    for layer_index in range(layer_count):
        z = (layer_index + 0.5) * layer_height
        paths: list[CurvePath] = []
        for perimeter_index in range(settings.perimeter_count):
            centerline_distance = settings.extrusion_width_mm * (0.5 + perimeter_index)
            outer = source.outer.offset(-centerline_distance)
            cutout = source.cutout.offset(centerline_distance)
            holes = tuple(hole.offset(centerline_distance) for hole in source.holes)
            common_metadata = {
                "derivation": "analytic_normal_offset",
                "perimeter_index": perimeter_index,
                "normal_offset_fit_tolerance_mm": settings.tolerance_mm,
                "normal_offset_max_validation_error_mm": 0.0,
                "surface_mesh_generated": False,
            }
            paths.append(
                _path(
                    rounded_rectangle_segments(outer),
                    role="additive_outer_perimeter",
                    channel="model",
                    closed=True,
                    feed_mm_min=settings.perimeter_feed_mm_min,
                    source_id=source.source_id,
                    metadata={**common_metadata, "feature_id": "outer_boundary"},
                )
            )
            paths.append(
                _path(
                    rounded_rectangle_segments(cutout, clockwise=True),
                    role="additive_cutout_perimeter",
                    channel="model",
                    closed=True,
                    feed_mm_min=settings.perimeter_feed_mm_min,
                    source_id=source.source_id,
                    metadata={**common_metadata, "feature_id": "center_cutout"},
                )
            )
            for hole_index, hole in enumerate(holes):
                paths.append(
                    _path(
                        circle_segments(hole, clockwise=True),
                        role="additive_hole_perimeter",
                        channel="model",
                        closed=True,
                        feed_mm_min=settings.perimeter_feed_mm_min,
                        source_id=source.source_id,
                        metadata={
                            **common_metadata,
                            "feature_id": f"mounting_hole_{hole_index + 1}",
                        },
                    )
                )

        fill_margin = settings.extrusion_width_mm * (settings.perimeter_count + 0.5)
        fill_outer = source.outer.offset(-fill_margin)
        fill_cutout = source.cutout.offset(fill_margin)
        fill_holes = tuple(hole.offset(fill_margin) for hole in source.holes)
        solid = (
            layer_index < settings.solid_layer_count
            or layer_index >= layer_count - settings.solid_layer_count
        )
        spacing = (
            settings.extrusion_width_mm
            if solid
            else settings.extrusion_width_mm / settings.infill_density
        )
        paths.extend(
            _analytic_infill_paths(
                source_id=source.source_id,
                outer=fill_outer,
                cutout=fill_cutout,
                holes=fill_holes,
                horizontal=layer_index % 2 == 0,
                spacing_mm=spacing,
                extrusion_width_mm=settings.extrusion_width_mm,
                feed_mm_min=(
                    0.9 * settings.infill_feed_mm_min
                    if solid
                    else settings.infill_feed_mm_min
                ),
                role="additive_solid_infill" if solid else "additive_sparse_infill",
            )
        )
        layers.append(
            ManufacturingLayer(
                z=z,
                paths=tuple(paths),
                metadata={
                    "layer_index": layer_index,
                    "model_z_mm": z,
                    "layer_height_mm": layer_height,
                    "analytic_boolean_clipping": True,
                    "triangle_mesh_used": False,
                },
            )
        )

    serialized_settings = asdict(settings)
    serialized_settings.update(
        {
            "effective_layer_height_mm": layer_height,
            "planner": (
                "analytic_boundary_offsets_plus_analytic_boolean_scanline_infill"
            ),
        }
    )
    return ManufacturingJob(
        job_id=f"{source.source_id}-additive",
        process="additive",
        source_id=source.source_id,
        layers=tuple(layers),
        tolerance_mm=settings.tolerance_mm,
        settings=serialized_settings,
        source_provenance=source.provenance(),
    )


def plan_engineering_bracket_subtractive(
    source: EngineeringBracketSource | None = None,
    settings: BracketSubtractiveSettings | None = None,
) -> ManufacturingJob:
    source = EngineeringBracketSource.default() if source is None else source
    settings = BracketSubtractiveSettings() if settings is None else settings
    tool_radius = settings.tool_diameter_mm / 2.0
    outer_tool_center = source.outer.offset(tool_radius)
    cutout_tool_center = source.cutout.offset(-tool_radius)
    hole_tool_centers = tuple(hole.offset(-tool_radius) for hole in source.holes)
    pass_count = max(1, int(math.ceil(source.thickness_mm / settings.step_down_mm)))
    step_down = source.thickness_mm / pass_count
    layers: list[ManufacturingLayer] = []

    for pass_index in range(pass_count):
        depth = min((pass_index + 1) * step_down, source.thickness_mm)
        common_metadata = {
            "derivation": "analytic_cutter_center_offset",
            "tool_radius_mm": tool_radius,
            "normal_offset_fit_tolerance_mm": settings.tolerance_mm,
            "normal_offset_max_validation_error_mm": 0.0,
            "surface_mesh_generated": False,
            "pass_index": pass_index,
        }
        paths = [
            _path(
                rounded_rectangle_segments(outer_tool_center, clockwise=True),
                role="subtractive_outer_finish_contour",
                channel="cutting_tool",
                closed=True,
                feed_mm_min=settings.finish_feed_mm_min,
                source_id=source.source_id,
                metadata={
                    **common_metadata,
                    "feature_id": "outer_boundary",
                    "compensation_side": "outside_part",
                },
            ),
            _path(
                rounded_rectangle_segments(cutout_tool_center),
                role="subtractive_cutout_finish_contour",
                channel="cutting_tool",
                closed=True,
                feed_mm_min=0.87 * settings.finish_feed_mm_min,
                source_id=source.source_id,
                metadata={
                    **common_metadata,
                    "feature_id": "center_cutout",
                    "compensation_side": "inside_void",
                },
            ),
        ]
        for hole_index, hole in enumerate(hole_tool_centers):
            paths.append(
                _path(
                    circle_segments(hole),
                    role="subtractive_hole_finish_contour",
                    channel="cutting_tool",
                    closed=True,
                    feed_mm_min=0.70 * settings.finish_feed_mm_min,
                    source_id=source.source_id,
                    metadata={
                        **common_metadata,
                        "feature_id": f"mounting_hole_{hole_index + 1}",
                        "compensation_side": "inside_void",
                    },
                )
            )
        layers.append(
            ManufacturingLayer(
                z=-depth,
                paths=tuple(paths),
                metadata={
                    "pass_index": pass_index,
                    "machine_depth_mm": depth,
                    "model_z_mm": source.thickness_mm - depth,
                    "effective_step_down_mm": step_down,
                },
            )
        )

    serialized_settings = asdict(settings)
    serialized_settings.update(
        {
            "effective_step_down_mm": step_down,
            "planner": "analytic_finish_contours_with_exact_tool_center_offsets",
            "scope": (
                "Finish contours only; stock, roughing, drilling strategy, tabs, "
                "fixturing, work offset, tool length, and collision approval remain "
                "required."
            ),
        }
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
    "SOURCE_SCHEMA_VERSION",
    "CLAIM_BOUNDARY",
    "RoundedRectangleSpec",
    "CircleSpec",
    "EngineeringBracketSource",
    "BracketAdditiveSettings",
    "BracketSubtractiveSettings",
    "rounded_rectangle_segments",
    "circle_segments",
    "plan_engineering_bracket_additive",
    "plan_engineering_bracket_subtractive",
]
