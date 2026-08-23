"""Triangle-free curve intermediate representation for manufacturing.

The objects in this module are the contract between AdaptiveCAD geometry,
additive planning, subtractive planning, and machine postprocessors.  The
contract intentionally has no mesh, face, facet, or triangle entity.  Curves
may be evaluated numerically for verification or controller compatibility, but
the authoritative manufacturing job remains curve-native.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

MANUFACTURING_SCHEMA_VERSION = "adaptivecad.manufacturing.curves/1.0"
Point2D = tuple[float, float]


def _point2(value: Sequence[float], *, name: str) -> Point2D:
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two coordinates")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(coordinate) for coordinate in point):
        raise ValueError(f"{name} must contain finite coordinates")
    return point


def _distance(left: Point2D, right: Point2D) -> float:
    return math.hypot(right[0] - left[0], right[1] - left[1])


def _lerp(left: Point2D, right: Point2D, fraction: float) -> Point2D:
    return (
        left[0] + fraction * (right[0] - left[0]),
        left[1] + fraction * (right[1] - left[1]),
    )


@dataclass(frozen=True)
class Line2D:
    """An exact straight manufacturing segment."""

    start: Point2D
    end: Point2D

    def __post_init__(self) -> None:
        start = _point2(self.start, name="line start")
        end = _point2(self.end, name="line end")
        if _distance(start, end) <= 1e-12:
            raise ValueError("line segment must have nonzero length")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    @property
    def kind(self) -> str:
        return "line"

    def evaluate(self, parameter: float) -> Point2D:
        parameter = float(parameter)
        return _lerp(self.start, self.end, parameter)

    def derivative(self, _parameter: float) -> Point2D:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

    def length(self) -> float:
        return _distance(self.start, self.end)

    def reversed(self) -> "Line2D":
        return Line2D(self.end, self.start)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "start": list(self.start), "end": list(self.end)}


@dataclass(frozen=True)
class CircularArc2D:
    """A circular arc with signed angular sweep in radians."""

    center: Point2D
    radius: float
    start_angle: float
    sweep_angle: float

    def __post_init__(self) -> None:
        center = _point2(self.center, name="arc center")
        radius = float(self.radius)
        start_angle = float(self.start_angle)
        sweep_angle = float(self.sweep_angle)
        if not math.isfinite(radius) or radius <= 0.0:
            raise ValueError("arc radius must be finite and positive")
        if not math.isfinite(start_angle) or not math.isfinite(sweep_angle):
            raise ValueError("arc angles must be finite")
        if abs(sweep_angle) <= 1e-12 or abs(sweep_angle) > 2.0 * math.pi + 1e-12:
            raise ValueError("arc sweep must be nonzero and no greater than one turn")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_angle", start_angle)
        object.__setattr__(self, "sweep_angle", sweep_angle)

    @property
    def kind(self) -> str:
        return "circular_arc"

    @property
    def start(self) -> Point2D:
        return self.evaluate(0.0)

    @property
    def end(self) -> Point2D:
        return self.evaluate(1.0)

    @property
    def clockwise(self) -> bool:
        return self.sweep_angle < 0.0

    def evaluate(self, parameter: float) -> Point2D:
        angle = self.start_angle + float(parameter) * self.sweep_angle
        return (
            self.center[0] + self.radius * math.cos(angle),
            self.center[1] + self.radius * math.sin(angle),
        )

    def derivative(self, parameter: float) -> Point2D:
        angle = self.start_angle + float(parameter) * self.sweep_angle
        scale = self.radius * self.sweep_angle
        return (-scale * math.sin(angle), scale * math.cos(angle))

    def length(self) -> float:
        return self.radius * abs(self.sweep_angle)

    def reversed(self) -> "CircularArc2D":
        return CircularArc2D(
            center=self.center,
            radius=self.radius,
            start_angle=self.start_angle + self.sweep_angle,
            sweep_angle=-self.sweep_angle,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "center": list(self.center),
            "radius": self.radius,
            "start_angle": self.start_angle,
            "sweep_angle": self.sweep_angle,
        }


@dataclass(frozen=True)
class CubicBezier2D:
    """A cubic Bézier manufacturing segment."""

    p0: Point2D
    p1: Point2D
    p2: Point2D
    p3: Point2D

    def __post_init__(self) -> None:
        points = tuple(
            _point2(point, name=f"Bezier p{index}")
            for index, point in enumerate((self.p0, self.p1, self.p2, self.p3))
        )
        if max(_distance(points[0], point) for point in points[1:]) <= 1e-12:
            raise ValueError("Bezier segment must have nonzero extent")
        for name, point in zip(("p0", "p1", "p2", "p3"), points):
            object.__setattr__(self, name, point)

    @property
    def kind(self) -> str:
        return "cubic_bezier"

    @property
    def start(self) -> Point2D:
        return self.p0

    @property
    def end(self) -> Point2D:
        return self.p3

    def evaluate(self, parameter: float) -> Point2D:
        t = float(parameter)
        u = 1.0 - t
        weights = (u**3, 3.0 * u * u * t, 3.0 * u * t * t, t**3)
        points = (self.p0, self.p1, self.p2, self.p3)
        return (
            sum(weight * point[0] for weight, point in zip(weights, points)),
            sum(weight * point[1] for weight, point in zip(weights, points)),
        )

    def derivative(self, parameter: float) -> Point2D:
        t = float(parameter)
        u = 1.0 - t
        return (
            3.0
            * (
                u * u * (self.p1[0] - self.p0[0])
                + 2.0 * u * t * (self.p2[0] - self.p1[0])
                + t * t * (self.p3[0] - self.p2[0])
            ),
            3.0
            * (
                u * u * (self.p1[1] - self.p0[1])
                + 2.0 * u * t * (self.p2[1] - self.p1[1])
                + t * t * (self.p3[1] - self.p2[1])
            ),
        )

    def length(self, *, quadrature_order: int = 16) -> float:
        nodes, weights = np.polynomial.legendre.leggauss(int(quadrature_order))
        total = 0.0
        for node, weight in zip(nodes, weights):
            parameter = 0.5 * (float(node) + 1.0)
            derivative = self.derivative(parameter)
            total += float(weight) * math.hypot(*derivative)
        return 0.5 * total

    def split(self, parameter: float = 0.5) -> tuple["CubicBezier2D", "CubicBezier2D"]:
        t = float(parameter)
        if not 0.0 < t < 1.0:
            raise ValueError("Bezier split parameter must lie strictly between zero and one")
        p01 = _lerp(self.p0, self.p1, t)
        p12 = _lerp(self.p1, self.p2, t)
        p23 = _lerp(self.p2, self.p3, t)
        p012 = _lerp(p01, p12, t)
        p123 = _lerp(p12, p23, t)
        midpoint = _lerp(p012, p123, t)
        return (
            CubicBezier2D(self.p0, p01, p012, midpoint),
            CubicBezier2D(midpoint, p123, p23, self.p3),
        )

    def reversed(self) -> "CubicBezier2D":
        return CubicBezier2D(self.p3, self.p2, self.p1, self.p0)

    def _control_distance_to_chord(self) -> float:
        chord_x = self.p3[0] - self.p0[0]
        chord_y = self.p3[1] - self.p0[1]
        chord_length = math.hypot(chord_x, chord_y)
        if chord_length <= 1e-14:
            return max(_distance(self.p0, self.p1), _distance(self.p0, self.p2))

        def distance(point: Point2D) -> float:
            cross = abs(
                chord_x * (self.p0[1] - point[1])
                - (self.p0[0] - point[0]) * chord_y
            )
            return cross / chord_length

        return max(distance(self.p1), distance(self.p2))

    def flatten(self, tolerance: float, *, max_depth: int = 24) -> tuple[Point2D, ...]:
        """Return a tolerance-controlled line chain for a limited controller.

        This is a postprocessor compatibility operation.  It creates line
        motion, never surface facets or triangle geometry.
        """

        tolerance = float(tolerance)
        if not math.isfinite(tolerance) or tolerance <= 0.0:
            raise ValueError("flatten tolerance must be finite and positive")
        output: list[Point2D] = [self.p0]

        def visit(curve: CubicBezier2D, depth: int) -> None:
            if curve._control_distance_to_chord() <= tolerance:
                output.append(curve.p3)
                return
            if depth >= max_depth:
                raise RuntimeError("Bezier flattening exceeded the recursion limit")
            left, right = curve.split()
            visit(left, depth + 1)
            visit(right, depth + 1)

        visit(self, 0)
        return tuple(output)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "p0": list(self.p0),
            "p1": list(self.p1),
            "p2": list(self.p2),
            "p3": list(self.p3),
        }


CurveSegment2D = Line2D | CircularArc2D | CubicBezier2D
SUPPORTED_CURVE_KINDS = frozenset({"line", "circular_arc", "cubic_bezier"})


def _segment_from_dict(data: Mapping[str, Any]) -> CurveSegment2D:
    kind = str(data.get("kind", ""))
    if kind == "line":
        return Line2D(tuple(data["start"]), tuple(data["end"]))
    if kind == "circular_arc":
        return CircularArc2D(
            center=tuple(data["center"]),
            radius=float(data["radius"]),
            start_angle=float(data["start_angle"]),
            sweep_angle=float(data["sweep_angle"]),
        )
    if kind == "cubic_bezier":
        return CubicBezier2D(
            tuple(data["p0"]),
            tuple(data["p1"]),
            tuple(data["p2"]),
            tuple(data["p3"]),
        )
    raise ValueError(f"unsupported manufacturing curve kind: {kind!r}")


def _integrate_curve_area(segment: CurveSegment2D, order: int = 16) -> float:
    nodes, weights = np.polynomial.legendre.leggauss(order)
    total = 0.0
    for node, weight in zip(nodes, weights):
        parameter = 0.5 * (float(node) + 1.0)
        point = segment.evaluate(parameter)
        derivative = segment.derivative(parameter)
        total += float(weight) * (point[0] * derivative[1] - point[1] * derivative[0])
    return 0.25 * total


@dataclass(frozen=True)
class CurvePath:
    """An ordered open or closed manufacturing curve path."""

    segments: tuple[CurveSegment2D, ...]
    closed: bool
    role: str
    channel: str = "default"
    feed_mm_min: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    connectivity_tolerance: float = 1e-7

    def __post_init__(self) -> None:
        segments = tuple(self.segments)
        if not segments:
            raise ValueError("curve path must contain at least one segment")
        if any(segment.kind not in SUPPORTED_CURVE_KINDS for segment in segments):
            raise ValueError("curve path contains an unsupported segment kind")
        tolerance = float(self.connectivity_tolerance)
        if not math.isfinite(tolerance) or tolerance <= 0.0:
            raise ValueError("connectivity tolerance must be finite and positive")
        for left, right in zip(segments, segments[1:]):
            if _distance(left.end, right.start) > tolerance:
                raise ValueError("curve path segments are not endpoint-connected")
        if self.closed and _distance(segments[-1].end, segments[0].start) > tolerance:
            raise ValueError("closed curve path does not return to its start")
        if not self.role:
            raise ValueError("curve path role must not be empty")
        if not self.channel:
            raise ValueError("curve path channel must not be empty")
        feed = None if self.feed_mm_min is None else float(self.feed_mm_min)
        if feed is not None and (not math.isfinite(feed) or feed <= 0.0):
            raise ValueError("path feed must be finite and positive")
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "feed_mm_min", feed)
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "connectivity_tolerance", tolerance)

    @property
    def start(self) -> Point2D:
        return self.segments[0].start

    @property
    def end(self) -> Point2D:
        return self.segments[-1].end

    def length(self) -> float:
        return sum(segment.length() for segment in self.segments)

    def signed_area(self) -> float:
        if not self.closed:
            raise ValueError("signed area is defined only for a closed curve path")
        return sum(_integrate_curve_area(segment) for segment in self.segments)

    @property
    def orientation(self) -> str:
        if not self.closed:
            return "open"
        area = self.signed_area()
        if abs(area) <= 1e-12:
            return "degenerate"
        return "counterclockwise" if area > 0.0 else "clockwise"

    def reversed(self) -> "CurvePath":
        return CurvePath(
            segments=tuple(segment.reversed() for segment in reversed(self.segments)),
            closed=self.closed,
            role=self.role,
            channel=self.channel,
            feed_mm_min=self.feed_mm_min,
            metadata=self.metadata,
            connectivity_tolerance=self.connectivity_tolerance,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "curve_path",
            "closed": self.closed,
            "role": self.role,
            "channel": self.channel,
            "feed_mm_min": self.feed_mm_min,
            "metadata": dict(self.metadata),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CurvePath":
        if data.get("kind") != "curve_path":
            raise ValueError("dictionary does not contain a curve path")
        return cls(
            segments=tuple(_segment_from_dict(segment) for segment in data["segments"]),
            closed=bool(data["closed"]),
            role=str(data["role"]),
            channel=str(data.get("channel", "default")),
            feed_mm_min=data.get("feed_mm_min"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ManufacturingLayer:
    """One additive layer or subtractive waterline level."""

    z: float
    paths: tuple[CurvePath, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        z = float(self.z)
        paths = tuple(self.paths)
        if not math.isfinite(z):
            raise ValueError("manufacturing layer Z must be finite")
        if not paths:
            raise ValueError("manufacturing layer must contain at least one path")
        object.__setattr__(self, "z", z)
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "manufacturing_layer",
            "z": self.z,
            "metadata": dict(self.metadata),
            "paths": [path.to_dict() for path in self.paths],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ManufacturingLayer":
        if data.get("kind") != "manufacturing_layer":
            raise ValueError("dictionary does not contain a manufacturing layer")
        return cls(
            z=float(data["z"]),
            paths=tuple(CurvePath.from_dict(path) for path in data["paths"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ManufacturingJob:
    """Machine-neutral curve job for additive or subtractive manufacture."""

    job_id: str
    process: str
    source_id: str
    layers: tuple[ManufacturingLayer, ...]
    tolerance_mm: float
    settings: Mapping[str, Any] = field(default_factory=dict)
    source_provenance: Mapping[str, Any] = field(default_factory=dict)
    units: str = "mm"

    def __post_init__(self) -> None:
        if not self.job_id or not self.source_id:
            raise ValueError("job_id and source_id must not be empty")
        if self.process not in {"additive", "subtractive"}:
            raise ValueError("process must be 'additive' or 'subtractive'")
        if self.units != "mm":
            raise ValueError("the v1 manufacturing IR supports millimetres only")
        layers = tuple(self.layers)
        if not layers:
            raise ValueError("manufacturing job must contain at least one layer")
        tolerance = float(self.tolerance_mm)
        if not math.isfinite(tolerance) or tolerance <= 0.0:
            raise ValueError("job tolerance must be finite and positive")
        object.__setattr__(self, "layers", layers)
        object.__setattr__(self, "tolerance_mm", tolerance)
        object.__setattr__(self, "settings", dict(self.settings))
        object.__setattr__(self, "source_provenance", dict(self.source_provenance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MANUFACTURING_SCHEMA_VERSION,
            "kind": "curve_manufacturing_job",
            "triangle_mesh_input": False,
            "job_id": self.job_id,
            "process": self.process,
            "source_id": self.source_id,
            "units": self.units,
            "tolerance_mm": self.tolerance_mm,
            "settings": dict(self.settings),
            "source_provenance": dict(self.source_provenance),
            "layers": [layer.to_dict() for layer in self.layers],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ManufacturingJob":
        if data.get("schema_version") != MANUFACTURING_SCHEMA_VERSION:
            raise ValueError("unsupported manufacturing schema version")
        if data.get("kind") != "curve_manufacturing_job":
            raise ValueError("dictionary does not contain a curve manufacturing job")
        if data.get("triangle_mesh_input") is not False:
            raise ValueError("manufacturing job does not assert a triangle-free source")
        return cls(
            job_id=str(data["job_id"]),
            process=str(data["process"]),
            source_id=str(data["source_id"]),
            units=str(data["units"]),
            tolerance_mm=float(data["tolerance_mm"]),
            settings=dict(data.get("settings", {})),
            source_provenance=dict(data.get("source_provenance", {})),
            layers=tuple(ManufacturingLayer.from_dict(layer) for layer in data["layers"]),
        )


def audit_triangle_free_job(job: ManufacturingJob) -> dict[str, Any]:
    """Audit the authoritative IR for topology, continuity, and entity kinds."""

    kind_counts = {kind: 0 for kind in sorted(SUPPORTED_CURVE_KINDS)}
    path_count = 0
    closed_path_count = 0
    minimum_segment_length = math.inf
    invalid_orientation = 0
    for layer in job.layers:
        for path in layer.paths:
            path_count += 1
            if path.closed:
                closed_path_count += 1
                if path.orientation == "degenerate":
                    invalid_orientation += 1
            for segment in path.segments:
                if segment.kind not in SUPPORTED_CURVE_KINDS:
                    raise ValueError(f"unsupported entity kind in job: {segment.kind}")
                kind_counts[segment.kind] += 1
                minimum_segment_length = min(minimum_segment_length, segment.length())

    serialized = job.to_dict()

    def inspect(value: Any) -> None:
        if isinstance(value, Mapping):
            entity_kind = value.get("kind")
            if entity_kind in {"mesh", "triangle", "triangle_mesh", "facet"}:
                raise ValueError(f"forbidden manufacturing entity: {entity_kind}")
            for child in value.values():
                inspect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                inspect(child)

    inspect(serialized)
    return {
        "schema_version": MANUFACTURING_SCHEMA_VERSION,
        "authoritative_ir_triangle_free": True,
        "triangle_mesh_input": False,
        "layer_count": len(job.layers),
        "path_count": path_count,
        "closed_path_count": closed_path_count,
        "curve_kind_counts": kind_counts,
        "minimum_segment_length_mm": minimum_segment_length,
        "degenerate_closed_path_count": invalid_orientation,
        "connectivity_check": "passed_by_construction",
        "controller_linearization_scope": (
            "Optional postprocessor line motion is tolerance-controlled and does not "
            "alter the authoritative curve IR."
        ),
    }


__all__ = [
    "MANUFACTURING_SCHEMA_VERSION",
    "Point2D",
    "Line2D",
    "CircularArc2D",
    "CubicBezier2D",
    "CurveSegment2D",
    "CurvePath",
    "ManufacturingLayer",
    "ManufacturingJob",
    "SUPPORTED_CURVE_KINDS",
    "audit_triangle_free_job",
]
