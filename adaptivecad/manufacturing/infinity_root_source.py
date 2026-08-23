"""Curve-native Infinity Root loft source for direct manufacturing.

This source never creates a polygon mesh.  Declared canonical and gauge pages
are converted to periodic cubic Bézier loops.  Physical cross-sections between
those declared pages use an explicitly labelled fabrication loft interpolation;
they are not presented as new fractional Infinity-Root iterates.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from adaptivecad.geometry.infinity_root import (
    CanonicalRootTower,
    FractionalGaugeSpec,
    make_infinity_root_profile,
)

from .curve_ir import CubicBezier2D, CurvePath, Point2D


def _periodic_bezier_segments(points: Sequence[Sequence[float]]) -> tuple[CubicBezier2D, ...]:
    vertices = np.asarray(points, dtype=float)
    if vertices.ndim != 2 or vertices.shape[0] < 8 or vertices.shape[1] != 2:
        raise ValueError("periodic Bézier construction needs at least eight 2D points")
    if not np.all(np.isfinite(vertices)):
        raise ValueError("periodic Bézier points must be finite")

    segments: list[CubicBezier2D] = []
    count = vertices.shape[0]
    for index in range(count):
        previous = vertices[(index - 1) % count]
        start = vertices[index]
        end = vertices[(index + 1) % count]
        following = vertices[(index + 2) % count]
        control_one = start + (end - previous) / 6.0
        control_two = end - (following - start) / 6.0
        segments.append(
            CubicBezier2D(
                tuple(float(value) for value in start),
                tuple(float(value) for value in control_one),
                tuple(float(value) for value in control_two),
                tuple(float(value) for value in end),
            )
        )
    return tuple(segments)


def _normal_offset_point(
    segment: CubicBezier2D,
    parameter: float,
    distance_mm: float,
) -> Point2D:
    point = segment.evaluate(parameter)
    derivative = segment.derivative(parameter)
    speed = math.hypot(*derivative)
    if speed <= 1e-12:
        raise ValueError("normal offset requires a regular curve with nonzero tangent")
    left_normal = (-derivative[1] / speed, derivative[0] / speed)
    return (
        point[0] + distance_mm * left_normal[0],
        point[1] + distance_mm * left_normal[1],
    )


def _fit_periodic_normal_offset(
    path: CurvePath,
    *,
    distance_mm: float,
    tolerance_mm: float,
    max_subdivisions_per_span: int = 64,
) -> CurvePath:
    """Fit a periodic cubic path to a local-normal offset of a smooth path.

    The fitter doubles samples per input span until validation samples on every
    output span lie within ``tolerance_mm`` of the evaluated normal offset. It
    creates curve entities only; no polygon or surface mesh is constructed.
    """

    distance = float(distance_mm)
    tolerance = float(tolerance_mm)
    if not math.isfinite(distance):
        raise ValueError("normal offset distance must be finite")
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("normal offset tolerance must be finite and positive")
    if not path.closed:
        raise ValueError("the periodic normal-offset fitter requires a closed path")
    if any(not isinstance(segment, CubicBezier2D) for segment in path.segments):
        raise TypeError("the Infinity Root normal-offset fitter requires cubic spans")
    maximum = int(max_subdivisions_per_span)
    if maximum < 1 or maximum & (maximum - 1):
        raise ValueError("max_subdivisions_per_span must be a positive power of two")

    subdivisions = 1
    while subdivisions <= maximum:
        samples = [
            _normal_offset_point(segment, sample_index / subdivisions, distance)
            for segment in path.segments
            for sample_index in range(subdivisions)
        ]
        fitted_segments = _periodic_bezier_segments(samples)
        maximum_error = 0.0
        for fitted_index, fitted in enumerate(fitted_segments):
            source_index, interval_index = divmod(fitted_index, subdivisions)
            source = path.segments[source_index]
            for fraction in (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875):
                source_parameter = (interval_index + fraction) / subdivisions
                target = _normal_offset_point(source, source_parameter, distance)
                actual = fitted.evaluate(fraction)
                maximum_error = max(
                    maximum_error,
                    math.hypot(actual[0] - target[0], actual[1] - target[1]),
                )

        if maximum_error <= tolerance:
            fitted_path = CurvePath(
                segments=fitted_segments,
                closed=True,
                role=path.role,
                channel=path.channel,
                feed_mm_min=path.feed_mm_min,
                metadata={
                    **dict(path.metadata),
                    "normal_offset_method": (
                        "adaptive_periodic_cubic_fit_to_evaluated_local_normal"
                    ),
                    "normal_offset_distance_mm": distance,
                    "normal_offset_fit_tolerance_mm": tolerance,
                    "normal_offset_max_validation_error_mm": maximum_error,
                    "normal_offset_subdivisions_per_input_span": subdivisions,
                    "normal_offset_validation_fractions": 7,
                },
            )
            if fitted_path.orientation != path.orientation:
                raise ValueError("normal offset collapsed or reversed the source path")
            return fitted_path
        subdivisions *= 2

    raise RuntimeError(
        "normal offset did not reach the requested tolerance before the subdivision limit"
    )


@dataclass(frozen=True)
class InfinityRootLoftSource:
    """A radial periodic-Bézier loft through declared Infinity Root pages."""

    angles: tuple[float, ...]
    page_z: tuple[float, ...]
    page_radii: tuple[tuple[float, ...], ...]
    page_records: tuple[Mapping[str, Any], ...]
    band_width_mm: float
    root_jet: Mapping[str, Any]
    source_id: str

    def __post_init__(self) -> None:
        angles = tuple(float(value) for value in self.angles)
        page_z = tuple(float(value) for value in self.page_z)
        radii = tuple(tuple(float(value) for value in row) for row in self.page_radii)
        records = tuple(dict(record) for record in self.page_records)
        band_width = float(self.band_width_mm)
        if len(angles) < 8 or not all(math.isfinite(value) for value in angles):
            raise ValueError("source angles must contain at least eight finite values")
        if any(value < 0.0 or value >= 2.0 * math.pi for value in angles) or any(
            right <= left for left, right in zip(angles, angles[1:])
        ):
            raise ValueError("source angles must be ordered once around [0, 2*pi)")
        if len(page_z) < 2 or any(right <= left for left, right in zip(page_z, page_z[1:])):
            raise ValueError("source page Z coordinates must be strictly increasing")
        if len(radii) != len(page_z) or len(records) != len(page_z):
            raise ValueError("page radii and records must match page Z coordinates")
        if any(len(row) != len(angles) for row in radii):
            raise ValueError("every radial page must match the angular sample count")
        if any(value <= 0.0 or not math.isfinite(value) for row in radii for value in row):
            raise ValueError("page radii must be finite and positive")
        if not math.isfinite(band_width) or band_width <= 0.0:
            raise ValueError("band width must be finite and positive")
        if min(value for row in radii for value in row) <= 0.5 * band_width:
            raise ValueError("band width would collapse the inner loft boundary")
        if not self.source_id:
            raise ValueError("source_id must not be empty")
        object.__setattr__(self, "angles", angles)
        object.__setattr__(self, "page_z", page_z)
        object.__setattr__(self, "page_radii", radii)
        object.__setattr__(self, "page_records", records)
        object.__setattr__(self, "band_width_mm", band_width)
        object.__setattr__(self, "root_jet", dict(self.root_jet))

    @classmethod
    def from_tower(
        cls,
        tower: CanonicalRootTower,
        *,
        fractional_pages: Sequence[tuple[float, FractionalGaugeSpec]] = (),
        radius_mm: float = 38.0,
        page_gap_mm: float = 8.0,
        radial_gain: float = 0.30,
        band_width_mm: float = 8.0,
    ) -> "InfinityRootLoftSource":
        page_gap = float(page_gap_mm)
        if not math.isfinite(page_gap) or page_gap <= 0.0:
            raise ValueError("page_gap_mm must be finite and positive")
        requested: list[tuple[float, FractionalGaugeSpec | None]] = [
            (float(index), None) for index in range(tower.depth + 1)
        ]
        seen = {height for height, _ in requested}
        for height, gauge in fractional_pages:
            height = float(height)
            if abs(height - round(height)) <= 1e-12:
                raise ValueError("fractional manufacturing pages must have non-integer heights")
            if height in seen:
                raise ValueError(f"duplicate manufacturing page height: {height}")
            requested.append((height, gauge))
            seen.add(height)
        requested.sort(key=lambda item: item[0])

        page_z: list[float] = []
        page_radii: list[tuple[float, ...]] = []
        page_records: list[dict[str, Any]] = []
        angles: tuple[float, ...] | None = None
        for height, gauge in requested:
            profile = make_infinity_root_profile(
                tower,
                height=height,
                gauge=gauge,
                radius=radius_mm,
                radial_gain=radial_gain,
            )
            points = np.asarray(profile["points"], dtype=float)
            current_angles = tuple(float(math.atan2(y, x) % (2.0 * math.pi)) for x, y in points)
            current_radii = tuple(float(math.hypot(x, y)) for x, y in points)
            if angles is None:
                angles = current_angles
            elif len(current_angles) != len(angles) or not np.allclose(
                current_angles,
                angles,
                rtol=0.0,
                atol=1e-12,
            ):
                raise ValueError("Infinity Root pages do not share angular samples")
            level = profile["infinity_root"]["level"]
            physical_z = page_gap * height
            page_z.append(physical_z)
            page_radii.append(current_radii)
            page_records.append(
                {
                    "root_height": height,
                    "physical_z_mm": physical_z,
                    "status": level["status"],
                    "canonical": bool(level["canonical"]),
                    "gauge": level["gauge"],
                }
            )

        assert angles is not None
        fingerprint_payload = {
            "kind": "infinity_root_periodic_bezier_loft",
            "page_z": page_z,
            "page_records": page_records,
            "band_width_mm": float(band_width_mm),
            "radius_mm": float(radius_mm),
            "radial_gain": float(radial_gain),
            "root_jet": tower.to_root_jet().to_dict(),
        }
        digest = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return cls(
            angles=angles,
            page_z=tuple(page_z),
            page_radii=tuple(page_radii),
            page_records=tuple(page_records),
            band_width_mm=band_width_mm,
            root_jet=tower.to_root_jet().to_dict(),
            source_id=f"infinity-root-loft-{digest}",
        )

    @property
    def z_min(self) -> float:
        return self.page_z[0]

    @property
    def z_max(self) -> float:
        return self.page_z[-1]

    @property
    def half_band_width(self) -> float:
        return 0.5 * self.band_width_mm

    def _section_state(self, z: float) -> tuple[np.ndarray, dict[str, Any]]:
        z = float(z)
        if not math.isfinite(z) or z < self.z_min - 1e-9 or z > self.z_max + 1e-9:
            raise ValueError("section Z lies outside the Infinity Root loft")
        z = min(self.z_max, max(self.z_min, z))
        exact_index = next(
            (index for index, page_value in enumerate(self.page_z) if abs(z - page_value) <= 1e-10),
            None,
        )
        if exact_index is not None:
            return np.asarray(self.page_radii[exact_index], dtype=float), {
                "section_status": "declared_root_page",
                "page": dict(self.page_records[exact_index]),
            }

        upper = int(np.searchsorted(np.asarray(self.page_z), z, side="right"))
        lower = upper - 1
        fraction = (z - self.page_z[lower]) / (self.page_z[upper] - self.page_z[lower])
        lower_radii = np.asarray(self.page_radii[lower], dtype=float)
        upper_radii = np.asarray(self.page_radii[upper], dtype=float)
        radii = (1.0 - fraction) * lower_radii + fraction * upper_radii
        return radii, {
            "section_status": "fabrication_loft_interpolation",
            "interpolation": "linear_in_physical_z_between_declared_pages",
            "fraction": float(fraction),
            "lower_page": dict(self.page_records[lower]),
            "upper_page": dict(self.page_records[upper]),
            "claim_boundary": (
                "This is physical loft interpolation, not an additional fractional "
                "Infinity-Root iterate."
            ),
        }

    def path_at(
        self,
        z: float,
        *,
        radial_offset_mm: float,
        role: str,
        clockwise: bool = False,
        channel: str = "default",
        feed_mm_min: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CurvePath:
        """Return one exact IR loop at a radial offset from the loft centerline."""

        offset = float(radial_offset_mm)
        if not math.isfinite(offset):
            raise ValueError("radial manufacturing offset must be finite")
        radii, section_metadata = self._section_state(z)
        shifted = radii + offset
        if np.any(shifted <= 0.0):
            raise ValueError("radial manufacturing offset collapses the curve")
        points: list[Point2D] = [
            (
                float(radius * math.cos(angle)),
                float(radius * math.sin(angle)),
            )
            for radius, angle in zip(shifted, self.angles)
        ]
        combined_metadata = {
            "source_id": self.source_id,
            "model_z_mm": float(z),
            "radial_offset_mm": offset,
            **section_metadata,
            **({} if metadata is None else dict(metadata)),
        }
        path = CurvePath(
            segments=_periodic_bezier_segments(points),
            closed=True,
            role=role,
            channel=channel,
            feed_mm_min=feed_mm_min,
            metadata=combined_metadata,
        )
        if clockwise and path.orientation != "clockwise":
            return path.reversed()
        if not clockwise and path.orientation != "counterclockwise":
            return path.reversed()
        return path

    def normal_offset_path_at(
        self,
        z: float,
        *,
        boundary_radial_offset_mm: float,
        normal_offset_mm: float,
        fit_tolerance_mm: float,
        role: str,
        clockwise: bool,
        channel: str = "default",
        feed_mm_min: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CurvePath:
        """Fit a curve-native local-normal offset from a loft boundary loop."""

        boundary = self.path_at(
            z,
            radial_offset_mm=boundary_radial_offset_mm,
            role=role,
            clockwise=clockwise,
            channel=channel,
            feed_mm_min=feed_mm_min,
            metadata={
                "boundary_radial_offset_mm": float(boundary_radial_offset_mm),
                **({} if metadata is None else dict(metadata)),
            },
        )
        return _fit_periodic_normal_offset(
            boundary,
            distance_mm=normal_offset_mm,
            tolerance_mm=fit_tolerance_mm,
        )

    def provenance(self) -> dict[str, Any]:
        return {
            "source_kind": "infinity_root_periodic_bezier_loft",
            "source_id": self.source_id,
            "root_jet": dict(self.root_jet),
            "declared_pages": [dict(record) for record in self.page_records],
            "surface_between_pages": "linear_physical_loft_not_new_root_level",
            "native_representation": "periodic_cubic_bezier_cross_sections",
            "mesh_created": False,
        }


__all__ = ["InfinityRootLoftSource"]
