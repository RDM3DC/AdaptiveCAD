"""AdaptiveCAD triangle-free manufacturing contract and scale gate.

The authoritative manufacturing representation is a graph of analytic curve
segments.  A display mesh or a controller-specific polyline may be derived from
that graph, but neither is allowed to become an input to the authoritative IR.

This module intentionally depends only on the Python standard library so the
gate can run beside AdaptiveCAD, in CI, or on a shop computer.
"""

from __future__ import annotations

import copy
import gc
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


CONTRACT_VERSION = "adaptivecad.triangle_free_contract/1.0"
CURVE_IR_VERSION = "adaptivecad.manufacturing.curves/1.0"
ALLOWED_SEGMENT_KINDS = frozenset({"line", "circular_arc", "cubic_bezier"})
FORBIDDEN_KIND_VALUES = frozenset(
    {
        "facet",
        "faceted_surface",
        "indexed_triangle_set",
        "mesh",
        "obj_mesh",
        "stl_mesh",
        "surface_facet",
        "triangle",
        "triangle_mesh",
        "triangulated_surface",
    }
)
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "facets",
        "mesh_faces",
        "mesh_vertices",
        "surface_facets",
        "triangle_entities",
        "triangle_indices",
        "triangles",
    }
)
FALSE_ASSERTION_KEYS = frozenset(
    {"mesh_created", "surface_mesh_generated", "triangle_mesh_input"}
)
TRUE_ASSERTION_KEYS = frozenset({"authoritative_ir_triangle_free"})
POINT_KEYS = frozenset(
    {"p0", "p1", "p2", "p3", "center", "start", "end", "control_points"}
)
ROUNDTRIP_RELATIVE_LIMIT = 5.0e-13
ABSOLUTE_FLOOR = 1.0e-12


class ContractError(ValueError):
    """Raised when a job cannot be interpreted as curve manufacturing IR."""


def load_job(path: str | Path) -> dict[str, Any]:
    """Load one JSON curve-manufacturing job."""

    with Path(path).open("r", encoding="utf-8") as stream:
        job = json.load(stream)
    if not isinstance(job, dict):
        raise ContractError(f"{path}: the top-level JSON value must be an object")
    return job


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return _is_number(value) and math.isfinite(float(value))


def _has_payload(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (list, tuple, dict, str)):
        return len(value) > 0
    return True


def _scan_forbidden_entities(node: Any, location: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        kind = node.get("kind")
        if isinstance(kind, str) and kind.lower() in FORBIDDEN_KIND_VALUES:
            errors.append(f"{location}.kind declares forbidden geometry {kind!r}")

        for key, value in node.items():
            child = f"{location}.{key}"
            lowered = key.lower()
            if lowered in FORBIDDEN_PAYLOAD_KEYS and _has_payload(value):
                errors.append(f"{child} contains a forbidden mesh/facet payload")
            if lowered in FALSE_ASSERTION_KEYS and value is not False:
                errors.append(f"{child} must be exactly false")
            if lowered in TRUE_ASSERTION_KEYS and value is not True:
                errors.append(f"{child} must be exactly true")
            _scan_forbidden_entities(value, child, errors)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _scan_forbidden_entities(value, f"{location}[{index}]", errors)


def _read_point(value: Any, location: str, errors: list[str]) -> tuple[float, ...] | None:
    if not isinstance(value, list) or len(value) not in (2, 3):
        errors.append(f"{location} must be a 2D or 3D numeric point")
        return None
    if not all(_is_finite_number(component) for component in value):
        errors.append(f"{location} contains a non-finite coordinate")
        return None
    return tuple(float(component) for component in value)


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return math.inf
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _control_polygon_length(points: Sequence[Sequence[float]]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))


def _segment_geometry(
    segment: Any,
    location: str,
    errors: list[str],
    tolerance_mm: float,
) -> tuple[str, tuple[float, ...], tuple[float, ...], list[tuple[float, ...]], float] | None:
    if not isinstance(segment, dict):
        errors.append(f"{location} must be an object")
        return None

    kind = segment.get("kind")
    if kind not in ALLOWED_SEGMENT_KINDS:
        errors.append(
            f"{location}.kind={kind!r} is not an allowed analytic manufacturing curve"
        )
        return None

    if kind == "line":
        # Curve IR 1.0 serializes lines as start/end.  Accept p0/p1 as a
        # compatibility spelling for early standalone benchmark bundles.
        names = (
            ("start", "end")
            if "start" in segment or "end" in segment
            else ("p0", "p1")
        )
    elif kind == "cubic_bezier":
        names = ("p0", "p1", "p2", "p3")
    elif "start_angle" in segment or "sweep_angle" in segment:
        center = _read_point(segment.get("center"), f"{location}.center", errors)
        radius = segment.get("radius")
        start_angle = segment.get("start_angle")
        sweep_angle = segment.get("sweep_angle")
        if center is None:
            return None
        if not _is_finite_number(radius) or float(radius) <= 0.0:
            errors.append(f"{location}.radius must be finite and positive")
            return None
        if not _is_finite_number(start_angle) or not _is_finite_number(sweep_angle):
            errors.append(f"{location} arc angles must be finite")
            return None
        radius_value = float(radius)
        start_value = float(start_angle)
        sweep_value = float(sweep_angle)
        if abs(sweep_value) <= ABSOLUTE_FLOOR:
            errors.append(f"{location}.sweep_angle must be nonzero")
        if abs(sweep_value) > 2.0 * math.pi + 1.0e-12:
            errors.append(f"{location}.sweep_angle must not exceed one turn")
        start = (
            center[0] + radius_value * math.cos(start_value),
            center[1] + radius_value * math.sin(start_value),
        )
        end_angle = start_value + sweep_value
        end = (
            center[0] + radius_value * math.cos(end_angle),
            center[1] + radius_value * math.sin(end_angle),
        )
        return (
            kind,
            start,
            end,
            [start, center, end],
            radius_value * abs(sweep_value),
        )
    else:
        names = ("p0", "center", "p1")

    points: list[tuple[float, ...]] = []
    for name in names:
        point = _read_point(segment.get(name), f"{location}.{name}", errors)
        if point is None:
            return None
        points.append(point)

    dimension = len(points[0])
    if any(len(point) != dimension for point in points):
        errors.append(f"{location} mixes 2D and 3D control points")
        return None

    if kind == "circular_arc":
        start, center, end = points
        start_radius = _distance(start, center)
        end_radius = _distance(end, center)
        if start_radius <= ABSOLUTE_FLOOR:
            errors.append(f"{location} has a zero-radius circular arc")
        radius_limit = max(tolerance_mm, start_radius * 1.0e-10)
        if abs(start_radius - end_radius) > radius_limit:
            errors.append(
                f"{location} arc radii disagree by {abs(start_radius - end_radius):.9g} mm"
            )
        recorded_radius = segment.get("radius_mm")
        if recorded_radius is not None:
            if not _is_finite_number(recorded_radius) or float(recorded_radius) <= 0.0:
                errors.append(f"{location}.radius_mm must be finite and positive")
            elif abs(float(recorded_radius) - start_radius) > radius_limit:
                errors.append(f"{location}.radius_mm disagrees with its center and start")
        polygon_length = _distance(start, center) + _distance(center, end)
        return kind, start, end, points, polygon_length

    polygon_length = _control_polygon_length(points)
    if not math.isfinite(polygon_length) or polygon_length <= ABSOLUTE_FLOOR:
        errors.append(f"{location} is a degenerate zero-length curve")
    return kind, points[0], points[-1], points, polygon_length


def _update_bounds(
    minimum: list[float],
    maximum: list[float],
    point: Sequence[float],
    layer_z: float,
) -> None:
    xyz = (point[0], point[1], point[2] if len(point) == 3 else layer_z)
    for axis, value in enumerate(xyz):
        minimum[axis] = min(minimum[axis], value)
        maximum[axis] = max(maximum[axis], value)


def _topology_signature(job: dict[str, Any]) -> str:
    layers_signature: list[Any] = []
    for layer in job.get("layers", []):
        path_signatures: list[Any] = []
        if not isinstance(layer, dict):
            path_signatures.append(["invalid-layer"])
        else:
            for path in layer.get("paths", []):
                if not isinstance(path, dict):
                    path_signatures.append(["invalid-path"])
                    continue
                kinds = [
                    segment.get("kind") if isinstance(segment, dict) else "invalid"
                    for segment in path.get("segments", [])
                ]
                sequence_hash = hashlib.sha256(
                    json.dumps(kinds, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                path_signatures.append(
                    [
                        path.get("kind"),
                        path.get("role"),
                        path.get("channel"),
                        path.get("closed"),
                        len(kinds),
                        sorted(Counter(kinds).items()),
                        sequence_hash,
                    ]
                )
        layers_signature.append(path_signatures)

    payload = {
        "schema_version": job.get("schema_version"),
        "kind": job.get("kind"),
        "process": job.get("process"),
        "layer_count": len(job.get("layers", [])),
        "layers": layers_signature,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_provenance_signature(job: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            job.get("source_provenance"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def audit_job(job: dict[str, Any], *, name: str = "job") -> dict[str, Any]:
    """Audit one curve-manufacturing job against the normative contract."""

    errors: list[str] = []
    warnings: list[str] = []

    if job.get("schema_version") != CURVE_IR_VERSION:
        errors.append(
            f"$.schema_version must be {CURVE_IR_VERSION!r}, got {job.get('schema_version')!r}"
        )
    if job.get("kind") != "curve_manufacturing_job":
        errors.append("$.kind must be 'curve_manufacturing_job'")
    if job.get("process") not in {"additive", "subtractive"}:
        errors.append("$.process must be 'additive' or 'subtractive'")
    if job.get("units") != "mm":
        errors.append("$.units must be explicit canonical millimetres ('mm') in contract v1")
    if job.get("triangle_mesh_input") is not False:
        errors.append("$.triangle_mesh_input must be exactly false")

    source_id = job.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        errors.append("$.source_id must be a non-empty stable identifier")

    tolerance = job.get("tolerance_mm")
    if not _is_finite_number(tolerance) or float(tolerance) <= 0.0:
        errors.append("$.tolerance_mm must be finite and positive")
        tolerance_mm = ABSOLUTE_FLOOR
    else:
        tolerance_mm = float(tolerance)

    settings = job.get("settings")
    if not isinstance(settings, dict):
        errors.append("$.settings must be an object")
    else:
        settings_tolerance = settings.get("tolerance_mm")
        if settings_tolerance is not None:
            if not _is_finite_number(settings_tolerance):
                errors.append("$.settings.tolerance_mm must be finite")
            elif not math.isclose(
                float(settings_tolerance), tolerance_mm, rel_tol=1.0e-12, abs_tol=1.0e-15
            ):
                errors.append("$.settings.tolerance_mm must equal $.tolerance_mm")

    provenance = job.get("source_provenance")
    if not isinstance(provenance, dict):
        errors.append("$.source_provenance must be an object")
    else:
        if provenance.get("source_id") != source_id:
            errors.append("$.source_provenance.source_id must equal $.source_id")
        if provenance.get("mesh_created") is not False:
            errors.append("$.source_provenance.mesh_created must be exactly false")
        if not isinstance(provenance.get("native_representation"), str):
            errors.append("$.source_provenance.native_representation must be declared")

    _scan_forbidden_entities(job, "$", errors)

    layers = job.get("layers")
    if not isinstance(layers, list) or not layers:
        errors.append("$.layers must be a non-empty array")
        layers = []

    layer_count = len(layers)
    path_count = 0
    closed_path_count = 0
    segment_count = 0
    segment_kind_counts: Counter[str] = Counter()
    minimum_curve_control_polygon_mm = math.inf
    maximum_continuity_gap_mm = 0.0
    maximum_closure_gap_mm = 0.0
    bounds_min = [math.inf, math.inf, math.inf]
    bounds_max = [-math.inf, -math.inf, -math.inf]
    seen_layer_z: set[float] = set()

    for layer_index, layer in enumerate(layers):
        layer_location = f"$.layers[{layer_index}]"
        if not isinstance(layer, dict):
            errors.append(f"{layer_location} must be an object")
            continue
        layer_z_value = layer.get("z")
        if not _is_finite_number(layer_z_value):
            errors.append(f"{layer_location}.z must be finite")
            layer_z = 0.0
        else:
            layer_z = float(layer_z_value)
            if layer_z in seen_layer_z:
                warnings.append(f"{layer_location}.z duplicates another layer coordinate")
            seen_layer_z.add(layer_z)

        paths = layer.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{layer_location}.paths must be a non-empty array")
            continue

        for path_index, path in enumerate(paths):
            path_location = f"{layer_location}.paths[{path_index}]"
            path_count += 1
            if not isinstance(path, dict):
                errors.append(f"{path_location} must be an object")
                continue
            if path.get("kind") != "curve_path":
                errors.append(f"{path_location}.kind must be 'curve_path'")
            closed = path.get("closed")
            if not isinstance(closed, bool):
                errors.append(f"{path_location}.closed must be boolean")
                closed = False
            if closed:
                closed_path_count += 1
            feed = path.get("feed_mm_min")
            if not _is_finite_number(feed) or float(feed) <= 0.0:
                errors.append(f"{path_location}.feed_mm_min must be finite and positive")

            metadata = path.get("metadata")
            if isinstance(metadata, dict):
                metadata_source = metadata.get("source_id")
                if metadata_source is not None and metadata_source != source_id:
                    errors.append(f"{path_location}.metadata.source_id differs from $.source_id")
                offset_error = metadata.get("normal_offset_max_validation_error_mm")
                offset_tolerance = metadata.get("normal_offset_fit_tolerance_mm")
                if offset_error is not None:
                    if not _is_finite_number(offset_error) or float(offset_error) < 0.0:
                        errors.append(
                            f"{path_location}.metadata.normal_offset_max_validation_error_mm "
                            "must be finite and non-negative"
                        )
                    else:
                        recorded_limit = (
                            float(offset_tolerance)
                            if _is_finite_number(offset_tolerance)
                            else tolerance_mm
                        )
                        if float(offset_error) > recorded_limit + max(1.0e-12, recorded_limit * 1.0e-12):
                            errors.append(
                                f"{path_location} normal-offset error {float(offset_error):.9g} mm "
                                f"exceeds {recorded_limit:.9g} mm"
                            )

            segments = path.get("segments")
            if not isinstance(segments, list) or not segments:
                errors.append(f"{path_location}.segments must be a non-empty array")
                continue

            parsed: list[
                tuple[str, tuple[float, ...], tuple[float, ...], list[tuple[float, ...]], float]
            ] = []
            for segment_index, segment in enumerate(segments):
                segment_location = f"{path_location}.segments[{segment_index}]"
                geometry = _segment_geometry(segment, segment_location, errors, tolerance_mm)
                segment_count += 1
                if isinstance(segment, dict) and isinstance(segment.get("kind"), str):
                    segment_kind_counts[segment["kind"]] += 1
                if geometry is not None:
                    parsed.append(geometry)
                    minimum_curve_control_polygon_mm = min(
                        minimum_curve_control_polygon_mm, geometry[4]
                    )
                    for point in geometry[3]:
                        _update_bounds(bounds_min, bounds_max, point, layer_z)

            continuity_limit = max(tolerance_mm, ABSOLUTE_FLOOR)
            for left, right in zip(parsed, parsed[1:]):
                gap = _distance(left[2], right[1])
                maximum_continuity_gap_mm = max(maximum_continuity_gap_mm, gap)
                if gap > continuity_limit:
                    errors.append(
                        f"{path_location} has adjacent-curve gap {gap:.9g} mm, "
                        f"above tolerance {continuity_limit:.9g} mm"
                    )
            if closed and parsed:
                gap = _distance(parsed[-1][2], parsed[0][1])
                maximum_closure_gap_mm = max(maximum_closure_gap_mm, gap)
                if gap > continuity_limit:
                    errors.append(
                        f"{path_location} closure gap {gap:.9g} mm exceeds "
                        f"tolerance {continuity_limit:.9g} mm"
                    )

    if segment_count == 0:
        errors.append("The job contains no manufacturing curve segments")

    if not math.isfinite(minimum_curve_control_polygon_mm):
        minimum_curve_control_polygon_mm = 0.0
    if any(not math.isfinite(value) for value in bounds_min + bounds_max):
        bounds: dict[str, list[float]] | None = None
    else:
        bounds = {"min_mm": bounds_min, "max_mm": bounds_max}

    report = {
        "contract_version": CONTRACT_VERSION,
        "curve_ir_version": CURVE_IR_VERSION,
        "name": name,
        "job_id": job.get("job_id"),
        "source_id": source_id,
        "process": job.get("process"),
        "passed": not errors,
        "authoritative_ir_triangle_free": not any(
            "forbidden" in error or "must be exactly false" in error
            for error in errors
        ),
        "errors": errors,
        "warnings": warnings,
        "topology_signature_sha256": _topology_signature(job),
        "source_provenance_sha256": _source_provenance_signature(job),
        "statistics": {
            "layer_count": layer_count,
            "path_count": path_count,
            "closed_path_count": closed_path_count,
            "segment_count": segment_count,
            "segment_kind_counts": dict(sorted(segment_kind_counts.items())),
            "minimum_curve_control_polygon_mm": minimum_curve_control_polygon_mm,
            "maximum_continuity_gap_mm": maximum_continuity_gap_mm,
            "maximum_closure_gap_mm": maximum_closure_gap_mm,
            "bounds": bounds,
            "tolerance_mm": tolerance_mm,
        },
    }
    return report


def _scale_numeric_tree(value: Any, factor: float) -> Any:
    if _is_number(value):
        return float(value) * factor
    if isinstance(value, list):
        return [_scale_numeric_tree(item, factor) for item in value]
    return copy.deepcopy(value)


def _scaled_copy(node: Any, factor: float, parent_key: str | None = None) -> Any:
    if isinstance(node, dict):
        scaled: dict[str, Any] = {}
        for key, value in node.items():
            if key in POINT_KEYS:
                scaled[key] = _scale_numeric_tree(value, factor)
            elif key == "z" and _is_number(value):
                scaled[key] = float(value) * factor
            elif (
                key == "radius"
                and node.get("kind") == "circular_arc"
                and _is_number(value)
            ):
                scaled[key] = float(value) * factor
            elif key.endswith("_mm") and _is_number(value):
                scaled[key] = float(value) * factor
            else:
                scaled[key] = _scaled_copy(value, factor, key)
        return scaled
    if isinstance(node, list):
        return [_scaled_copy(value, factor, parent_key) for value in node]
    return copy.deepcopy(node)


def scale_job(job: dict[str, Any], factor: float) -> dict[str, Any]:
    """Return a geometrically similar job with every length scaled by factor."""

    if not _is_finite_number(factor) or float(factor) <= 0.0:
        raise ContractError("scale factor must be finite and positive")
    scaled = _scaled_copy(job, float(factor))
    assert isinstance(scaled, dict)
    return scaled


def _iter_coordinate_values(job: dict[str, Any]) -> Iterator[float]:
    for layer in job.get("layers", []):
        if not isinstance(layer, dict):
            continue
        for path in layer.get("paths", []):
            if not isinstance(path, dict):
                continue
            for segment in path.get("segments", []):
                if not isinstance(segment, dict):
                    continue
                for key in ("p0", "p1", "p2", "p3", "center", "start", "end"):
                    value = segment.get(key)
                    if isinstance(value, list):
                        for component in value:
                            if _is_number(component):
                                yield float(component)
                if (
                    segment.get("kind") == "circular_arc"
                    and _is_number(segment.get("radius"))
                ):
                    yield float(segment["radius"])


def scale_invariance_gate(
    job: dict[str, Any],
    *,
    factors: Iterable[float] = (0.001, 0.01, 1.0, 100.0, 1000.0),
    name: str = "job",
) -> dict[str, Any]:
    """Scale, re-audit, and normalize a job to detect resolution dependence."""

    base_audit = audit_job(job, name=name)
    base_coordinates = list(_iter_coordinate_values(job))
    base_signature = base_audit["topology_signature_sha256"]
    base_source = job.get("source_id")
    cases: list[dict[str, Any]] = []

    for raw_factor in factors:
        factor = float(raw_factor)
        case_errors: list[str] = []
        if not math.isfinite(factor) or factor <= 0.0:
            cases.append(
                {
                    "scale_factor": raw_factor,
                    "passed": False,
                    "errors": ["scale factor must be finite and positive"],
                }
            )
            continue

        scaled = scale_job(job, factor)
        scaled_audit = audit_job(scaled, name=f"{name}@{factor:g}x")
        scaled_coordinates = list(_iter_coordinate_values(scaled))
        if len(base_coordinates) != len(scaled_coordinates):
            case_errors.append("coordinate cardinality changed under scaling")

        maximum_absolute_roundtrip_error_mm = 0.0
        maximum_relative_roundtrip_error = 0.0
        for original, transformed in zip(base_coordinates, scaled_coordinates):
            normalized = transformed / factor
            absolute_error = abs(normalized - original)
            relative_error = absolute_error / max(1.0, abs(original))
            maximum_absolute_roundtrip_error_mm = max(
                maximum_absolute_roundtrip_error_mm, absolute_error
            )
            maximum_relative_roundtrip_error = max(
                maximum_relative_roundtrip_error, relative_error
            )

        if maximum_relative_roundtrip_error > ROUNDTRIP_RELATIVE_LIMIT:
            case_errors.append(
                "normalized coordinate round-trip error "
                f"{maximum_relative_roundtrip_error:.9g} exceeds "
                f"{ROUNDTRIP_RELATIVE_LIMIT:.9g}"
            )
        if scaled_audit["topology_signature_sha256"] != base_signature:
            case_errors.append("topology signature changed under scaling")
        if scaled.get("source_id") != base_source:
            case_errors.append("stable source_id changed under scaling")
        if not scaled_audit["passed"]:
            case_errors.append("scaled job failed the triangle-free semantic audit")

        base_tolerance = float(job.get("tolerance_mm", 0.0))
        scaled_tolerance = float(scaled.get("tolerance_mm", 0.0))
        normalized_tolerance_error = abs(scaled_tolerance / factor - base_tolerance)
        if normalized_tolerance_error > max(
            ABSOLUTE_FLOOR, abs(base_tolerance) * ROUNDTRIP_RELATIVE_LIMIT
        ):
            case_errors.append("tolerance did not scale linearly")

        cases.append(
            {
                "scale_factor": factor,
                "passed": not case_errors,
                "errors": case_errors,
                "semantic_audit_passed": scaled_audit["passed"],
                "triangle_free_after_scale": scaled_audit[
                    "authoritative_ir_triangle_free"
                ],
                "topology_signature_preserved": (
                    scaled_audit["topology_signature_sha256"] == base_signature
                ),
                "source_id_preserved": scaled.get("source_id") == base_source,
                "maximum_absolute_coordinate_roundtrip_error_mm": (
                    maximum_absolute_roundtrip_error_mm
                ),
                "maximum_relative_coordinate_roundtrip_error": (
                    maximum_relative_roundtrip_error
                ),
                "normalized_tolerance_error_mm": normalized_tolerance_error,
                "scaled_statistics": scaled_audit["statistics"],
            }
        )
        del scaled
        gc.collect()

    return {
        "contract_version": CONTRACT_VERSION,
        "name": name,
        "job_id": job.get("job_id"),
        "source_id": base_source,
        "passed": base_audit["passed"] and all(case["passed"] for case in cases),
        "base_audit_passed": base_audit["passed"],
        "roundtrip_relative_limit": ROUNDTRIP_RELATIVE_LIMIT,
        "cases": cases,
    }


def validate_shared_source(jobs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Verify that multiple process jobs descend from exactly one source object."""

    source_ids = [job.get("source_id") for job in jobs]
    provenance_signatures = [_source_provenance_signature(job) for job in jobs]
    errors: list[str] = []
    if not jobs:
        errors.append("no jobs were supplied")
    if len(set(source_ids)) > 1:
        errors.append("jobs do not share one stable source_id")
    if len(set(provenance_signatures)) > 1:
        errors.append("jobs do not carry identical source provenance")
    return {
        "passed": not errors,
        "errors": errors,
        "source_ids": source_ids,
        "one_source_id": source_ids[0] if source_ids and len(set(source_ids)) == 1 else None,
        "source_provenance_sha256": (
            provenance_signatures[0]
            if provenance_signatures and len(set(provenance_signatures)) == 1
            else None
        ),
    }


def verification_suite(
    named_jobs: Sequence[tuple[str, dict[str, Any]]],
    *,
    factors: Iterable[float] = (0.001, 0.01, 1.0, 100.0, 1000.0),
) -> dict[str, Any]:
    """Run the complete contract, source-identity, and scaling suite."""

    factor_list = [float(value) for value in factors]
    audits = [audit_job(job, name=name) for name, job in named_jobs]
    scale_gates = [
        scale_invariance_gate(job, factors=factor_list, name=name)
        for name, job in named_jobs
    ]
    shared_source = validate_shared_source([job for _, job in named_jobs])
    passed = (
        bool(named_jobs)
        and all(audit["passed"] for audit in audits)
        and all(gate["passed"] for gate in scale_gates)
        and shared_source["passed"]
    )
    return {
        "kind": "adaptivecad_triangle_free_contract_verification",
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "claim_boundary": (
            "The authoritative jobs contain analytic manufacturing curves and no "
            "triangle/facet payload. Scaling is resolution-independent within the "
            "recorded floating-point gate. Derived display meshes and controller "
            "linearization are outside the authoritative geometry."
        ),
        "scale_factors": factor_list,
        "shared_source": shared_source,
        "job_audits": audits,
        "scale_invariance_gates": scale_gates,
    }


def save_report(report: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
