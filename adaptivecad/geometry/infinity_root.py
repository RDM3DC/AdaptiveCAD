"""Infinity-Root descriptors and profile geometry for AdaptiveCAD.

The mathematical operator is

    R[f](x) = x f'(x) / f(x) = d(log f) / d(log x).

This module deliberately treats Infinity-Root data as a descriptor layer over
ordinary CAD geometry.  Integer applications of ``R`` (or its normalized lift)
form the canonical backbone.  A non-integer height is never silently inferred:
it requires an explicit :class:`FractionalGaugeSpec` and is serialized as a
gauge-dependent visualization view.

The sampled decoder implements the proved root-jet reconstruction formula with
trapezoidal integration in ``log(x)``.  It is exact for that declared discrete
integration model; estimating a tower from arbitrary samples remains a numerical
finite-difference operation and is labeled accordingly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np

SCHEMA_VERSION = "adaptivecad.infinity_root/1.0"
ROOT_OPERATOR = "R[f](x)=d(log(f))/d(log(x))=x*f'(x)/f(x)"


class LevelStatus(str, Enum):
    """Provenance class for a displayed Infinity-Root level."""

    CANONICAL_INTEGER = "canonical_integer"
    GAUGE_VIEW = "gauge_view"


def _as_float_tuple(values: Sequence[float], *, name: str) -> tuple[float, ...]:
    converted = tuple(float(value) for value in values)
    if not converted:
        raise ValueError(f"{name} must not be empty")
    if not all(math.isfinite(value) for value in converted):
        raise ValueError(f"{name} must contain only finite values")
    return converted


def _positive_tuple(values: Sequence[float], *, name: str) -> tuple[float, ...]:
    converted = _as_float_tuple(values, name=name)
    if any(value <= 0.0 for value in converted):
        raise ValueError(f"{name} must be strictly positive")
    return converted


def _validated_grid(x: Sequence[float]) -> tuple[float, ...]:
    grid = _positive_tuple(x, name="x")
    if len(grid) < 3:
        raise ValueError("x must contain at least three samples")
    if any(right <= left for left, right in zip(grid, grid[1:])):
        raise ValueError("x must be strictly increasing")
    return grid


def _check_basepoint(basepoint: float, x: Sequence[float]) -> float:
    basepoint = float(basepoint)
    if not math.isfinite(basepoint) or basepoint <= 0.0:
        raise ValueError("basepoint must be finite and positive")
    if basepoint < x[0] or basepoint > x[-1]:
        raise ValueError("basepoint must lie inside the sampled x interval")
    return basepoint


def _cumulative_trapezoid(y: np.ndarray, u: np.ndarray) -> np.ndarray:
    result = np.zeros_like(y, dtype=float)
    result[1:] = np.cumsum(0.5 * (y[:-1] + y[1:]) * np.diff(u))
    return result


def _log_interpolated_value(x: Sequence[float], values: Sequence[float], sample_x: float) -> float:
    """Evaluate a positive sampled profile by linear interpolation in log-log data."""

    sample_x = _check_basepoint(sample_x, x)
    return float(
        math.exp(
            np.interp(
                math.log(sample_x),
                np.log(np.asarray(x, dtype=float)),
                np.log(np.asarray(values, dtype=float)),
            )
        )
    )


@dataclass(frozen=True)
class FractionalGaugeSpec:
    """Serializable policy for a noncanonical, non-integer profile view.

    The built-in ``positive_power_mean`` family interpolates adjacent positive
    integer levels pointwise.  ``p=0`` is log-linear interpolation and ``p=1``
    is arithmetic interpolation.  Both preserve the integer endpoints, while
    generally producing different intermediate geometry.

    This local display family is *not* claimed to solve an Abel equation on the
    full function space.  That limitation is recorded in every serialized view.
    A future verified Abel coordinate should receive a different gauge name and
    implementation rather than changing this one's meaning.
    """

    name: str = "positive_power_mean"
    version: str = "1"
    parameters: Mapping[str, float] = field(default_factory=lambda: {"p": 0.0})

    def __post_init__(self) -> None:
        if self.name != "positive_power_mean":
            raise ValueError(f"unsupported fractional gauge: {self.name!r}")
        if not self.version:
            raise ValueError("gauge version must not be empty")
        p = float(self.parameters.get("p", 0.0))
        if not math.isfinite(p):
            raise ValueError("power-mean gauge parameter p must be finite")
        object.__setattr__(self, "parameters", {"p": p})

    @classmethod
    def power_mean(cls, p: float = 0.0) -> "FractionalGaugeSpec":
        return cls(parameters={"p": float(p)})

    @property
    def gauge_id(self) -> str:
        return f"{self.name}@{self.version}"

    def interpolate(
        self, lower: Sequence[float], upper: Sequence[float], fraction: float
    ) -> tuple[float, ...]:
        lower_values = np.asarray(_positive_tuple(lower, name="lower level"), dtype=float)
        upper_values = np.asarray(_positive_tuple(upper, name="upper level"), dtype=float)
        if lower_values.shape != upper_values.shape:
            raise ValueError("adjacent levels must have the same sample count")
        fraction = float(fraction)
        if not 0.0 < fraction < 1.0:
            raise ValueError("fraction must lie strictly between zero and one")

        p = float(self.parameters["p"])
        log_lower = np.log(lower_values)
        log_upper = np.log(upper_values)
        if abs(p) < 1e-12:
            result = np.exp((1.0 - fraction) * log_lower + fraction * log_upper)
        else:
            # Stable weighted log-sum-exp evaluation of the power mean.
            a = p * log_lower
            b = p * log_upper
            peak = np.maximum(a, b)
            mixed = (1.0 - fraction) * np.exp(a - peak) + fraction * np.exp(b - peak)
            result = np.exp((peak + np.log(mixed)) / p)
        return tuple(float(value) for value in result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gauge_id": self.gauge_id,
            "name": self.name,
            "version": self.version,
            "parameters": dict(self.parameters),
            "mathematical_status": "local_visualization_gauge",
            "abel_equation_verified": False,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FractionalGaugeSpec":
        return cls(
            name=str(data.get("name", "positive_power_mean")),
            version=str(data.get("version", "1")),
            parameters=dict(data.get("parameters", {"p": 0.0})),
        )


@dataclass(frozen=True)
class ProfileLevel:
    """One sampled integer level or one explicitly gauged fractional view."""

    height: float
    values: tuple[float, ...]
    status: LevelStatus
    gauge: FractionalGaugeSpec | None = None

    def __post_init__(self) -> None:
        values = _positive_tuple(self.values, name="level values")
        height = float(self.height)
        if not math.isfinite(height) or height < 0.0:
            raise ValueError("height must be finite and nonnegative")
        status = self.status if isinstance(self.status, LevelStatus) else LevelStatus(self.status)
        is_integer = abs(height - round(height)) <= 1e-12
        if status is LevelStatus.CANONICAL_INTEGER:
            if not is_integer:
                raise ValueError("a canonical level must have an integer height")
            if self.gauge is not None:
                raise ValueError("a canonical integer level must not carry gauge metadata")
            height = float(round(height))
        else:
            if is_integer:
                raise ValueError("a gauge view must have a non-integer height")
            if self.gauge is None:
                raise ValueError("a non-integer level requires explicit gauge metadata")
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "status", status)

    @property
    def is_canonical(self) -> bool:
        return self.status is LevelStatus.CANONICAL_INTEGER

    def to_dict(self, *, include_values: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "height": self.height,
            "status": self.status.value,
            "canonical": self.is_canonical,
            "gauge": None if self.gauge is None else self.gauge.to_dict(),
        }
        if include_values:
            result["values"] = list(self.values)
        return result


@dataclass(frozen=True)
class RootJetSamples:
    """Finite sampled form of ``J_(n,b)(f)``.

    ``constants`` stores ``h_0(b), ..., h_(n-1)(b)`` and ``terminal`` stores
    the sampled terminal function ``h_n``.  Decoding uses nested normalized
    lifts and therefore restores every constant erased by the root operator.
    """

    x: tuple[float, ...]
    basepoint: float
    constants: tuple[float, ...]
    terminal: tuple[float, ...]
    provenance: str = "user_supplied"

    def __post_init__(self) -> None:
        x = _validated_grid(self.x)
        basepoint = _check_basepoint(self.basepoint, x)
        constants = tuple(float(value) for value in self.constants)
        if any(not math.isfinite(value) or value <= 0.0 for value in constants):
            raise ValueError("root-jet constants must be finite and positive")
        terminal = _positive_tuple(self.terminal, name="terminal values")
        if len(terminal) != len(x):
            raise ValueError("terminal values must match the x sample count")
        if not self.provenance:
            raise ValueError("provenance must not be empty")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "basepoint", basepoint)
        object.__setattr__(self, "constants", constants)
        object.__setattr__(self, "terminal", terminal)

    @property
    def depth(self) -> int:
        return len(self.constants)

    def decode(self) -> "CanonicalRootTower":
        log_x = np.log(np.asarray(self.x, dtype=float))
        log_base = math.log(self.basepoint)
        child = np.asarray(self.terminal, dtype=float)
        reversed_levels: list[tuple[float, ...]] = [self.terminal]
        max_log = math.log(np.finfo(float).max)

        for constant in reversed(self.constants):
            integral = _cumulative_trapezoid(child, log_x)
            integral_at_base = float(np.interp(log_base, log_x, integral))
            log_parent = math.log(constant) + integral - integral_at_base
            if np.any(log_parent > max_log):
                raise OverflowError("decoded root-jet level exceeds float range")
            parent = np.exp(log_parent)
            if np.any(parent <= 0.0) or not np.all(np.isfinite(parent)):
                raise FloatingPointError("decoded root-jet level is not finite and positive")
            parent_tuple = tuple(float(value) for value in parent)
            reversed_levels.append(parent_tuple)
            child = parent

        return CanonicalRootTower(
            x=self.x,
            basepoint=self.basepoint,
            levels=tuple(reversed(reversed_levels)),
            source=f"root_jet_decode:{self.provenance}",
        )

    def transport(self, new_basepoint: float) -> "RootJetSamples":
        """Transport root-jet constants without changing the represented tower."""

        return self.decode().to_root_jet(
            basepoint=new_basepoint,
            provenance=f"basepoint_transport:{self.provenance}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "sampled_root_jet",
            "operator": ROOT_OPERATOR,
            "x": list(self.x),
            "basepoint": self.basepoint,
            "constants": list(self.constants),
            "terminal": list(self.terminal),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RootJetSamples":
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported Infinity-Root schema version")
        if data.get("kind") != "sampled_root_jet":
            raise ValueError("dictionary does not contain a sampled root jet")
        return cls(
            x=tuple(data["x"]),
            basepoint=float(data["basepoint"]),
            constants=tuple(data["constants"]),
            terminal=tuple(data["terminal"]),
            provenance=str(data.get("provenance", "deserialized")),
        )


@dataclass(frozen=True)
class CanonicalRootTower:
    """Sampled integer backbone ``h_0, ..., h_n`` of an Infinity-Root profile."""

    x: tuple[float, ...]
    basepoint: float
    levels: tuple[tuple[float, ...], ...]
    source: str = "unspecified"

    def __post_init__(self) -> None:
        x = _validated_grid(self.x)
        basepoint = _check_basepoint(self.basepoint, x)
        if not self.levels:
            raise ValueError("a root tower must contain at least one level")
        levels = tuple(
            _positive_tuple(level, name=f"level {index}") for index, level in enumerate(self.levels)
        )
        if any(len(level) != len(x) for level in levels):
            raise ValueError("every level must match the x sample count")
        if not self.source:
            raise ValueError("source must not be empty")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "basepoint", basepoint)
        object.__setattr__(self, "levels", levels)

    @property
    def depth(self) -> int:
        return len(self.levels) - 1

    def value_at(self, index: int, sample_x: float) -> float:
        if not 0 <= int(index) <= self.depth:
            raise IndexError("integer level index is outside the tower")
        return _log_interpolated_value(self.x, self.levels[int(index)], sample_x)

    def integer_level(self, index: int) -> ProfileLevel:
        index = int(index)
        if not 0 <= index <= self.depth:
            raise IndexError("integer level index is outside the tower")
        return ProfileLevel(
            height=float(index),
            values=self.levels[index],
            status=LevelStatus.CANONICAL_INTEGER,
        )

    def level_at(self, height: float, *, gauge: FractionalGaugeSpec | None = None) -> ProfileLevel:
        """Return an integer level or an explicitly gauged fractional view.

        The strict gauge requirement is intentional: AdaptiveCAD must never make
        a hidden choice for geometry between the canonical integer levels.
        """

        height = float(height)
        if not math.isfinite(height) or height < 0.0 or height > self.depth:
            raise ValueError(f"height must lie in [0, {self.depth}]")
        nearest = round(height)
        if abs(height - nearest) <= 1e-12:
            if gauge is not None:
                raise ValueError("omit gauge metadata for a canonical integer level")
            return self.integer_level(int(nearest))
        if gauge is None:
            raise ValueError("a non-integer height requires an explicit fractional gauge")

        lower_index = math.floor(height)
        upper_index = lower_index + 1
        fraction = height - lower_index
        values = gauge.interpolate(self.levels[lower_index], self.levels[upper_index], fraction)
        return ProfileLevel(
            height=height,
            values=values,
            status=LevelStatus.GAUGE_VIEW,
            gauge=gauge,
        )

    def to_root_jet(
        self,
        *,
        basepoint: float | None = None,
        provenance: str | None = None,
    ) -> RootJetSamples:
        resolved_base = self.basepoint if basepoint is None else _check_basepoint(basepoint, self.x)
        constants = tuple(self.value_at(index, resolved_base) for index in range(self.depth))
        return RootJetSamples(
            x=self.x,
            basepoint=resolved_base,
            constants=constants,
            terminal=self.levels[-1],
            provenance=provenance or f"encoded_from:{self.source}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "canonical_root_tower",
            "operator": ROOT_OPERATOR,
            "x": list(self.x),
            "basepoint": self.basepoint,
            "depth": self.depth,
            "levels": [list(level) for level in self.levels],
            "source": self.source,
            "canonical_integer_heights": list(range(self.depth + 1)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalRootTower":
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported Infinity-Root schema version")
        if data.get("kind") != "canonical_root_tower":
            raise ValueError("dictionary does not contain a canonical root tower")
        return cls(
            x=tuple(data["x"]),
            basepoint=float(data["basepoint"]),
            levels=tuple(tuple(level) for level in data["levels"]),
            source=str(data.get("source", "deserialized")),
        )


def root_operator_samples(x: Sequence[float], values: Sequence[float]) -> tuple[float, ...]:
    """Estimate ``R[f]`` from positive samples using the log-coordinate identity."""

    grid = _validated_grid(x)
    profile = _positive_tuple(values, name="profile values")
    if len(profile) != len(grid):
        raise ValueError("profile values must match the x sample count")
    log_x = np.log(np.asarray(grid, dtype=float))
    log_values = np.log(np.asarray(profile, dtype=float))
    derivative = np.gradient(log_values, log_x, edge_order=2)
    if not np.all(np.isfinite(derivative)):
        raise FloatingPointError("root operator produced non-finite samples")
    return tuple(float(value) for value in derivative)


def tower_from_profile_samples(
    x: Sequence[float],
    values: Sequence[float],
    *,
    depth: int,
    basepoint: float = 1.0,
    positivity_floor: float = 1e-12,
) -> CanonicalRootTower:
    """Estimate an integer tower from a positive sampled CAD scalar profile.

    Every requested intermediate root must remain positive.  Failure is reported
    rather than hidden with absolute values or clamping, because positivity is a
    hypothesis of the root-jet reconstruction theorem.
    """

    depth = int(depth)
    if depth < 0:
        raise ValueError("depth must be nonnegative")
    grid = _validated_grid(x)
    current = _positive_tuple(values, name="profile values")
    if len(current) != len(grid):
        raise ValueError("profile values must match the x sample count")
    levels = [current]
    for index in range(1, depth + 1):
        current = root_operator_samples(grid, current)
        minimum = min(current)
        if minimum <= positivity_floor:
            raise ValueError(
                f"profile is not positive {depth}-admissible: "
                f"estimated level {index} has minimum {minimum:.6g}"
            )
        levels.append(current)
    return CanonicalRootTower(
        x=grid,
        basepoint=basepoint,
        levels=tuple(levels),
        source="finite_difference_log_grid_estimate",
    )


def make_exact_lift_tower(
    x: Sequence[float],
    *,
    depth: int,
    residue: float,
    basepoint: float = 1.0,
) -> CanonicalRootTower:
    """Construct the normalized exact-tower representative of ``[depth; residue]``."""

    depth = int(depth)
    residue = float(residue)
    if depth < 0:
        raise ValueError("depth must be nonnegative")
    if not math.isfinite(residue) or residue <= 0.0:
        raise ValueError("residue must be finite and positive")
    grid = _validated_grid(x)
    terminal = tuple(residue for _ in grid)
    jet = RootJetSamples(
        x=grid,
        basepoint=basepoint,
        constants=tuple(1.0 for _ in range(depth)),
        terminal=terminal,
        provenance=f"normalized_exact_tower:[{depth};{residue:.17g}]",
    )
    return jet.decode()


def _display_radii(
    values: Sequence[float], *, radius: float, radial_gain: float
) -> tuple[tuple[float, ...], dict[str, float | str]]:
    radius = float(radius)
    radial_gain = float(radial_gain)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("radius must be finite and positive")
    if not math.isfinite(radial_gain) or radial_gain < 0.0:
        raise ValueError("radial_gain must be finite and nonnegative")
    log_values = np.log(np.asarray(_positive_tuple(values, name="profile values")))
    center = float(np.mean(log_values))
    centered = log_values - center
    span = float(np.max(np.abs(centered)))
    signal = np.zeros_like(centered) if span <= 1e-15 else centered / span
    radii = radius * np.exp(radial_gain * signal)
    return tuple(float(value) for value in radii), {
        "name": "bounded_centered_log_radial",
        "base_radius": radius,
        "radial_gain": radial_gain,
        "log_center": center,
        "log_half_span": span,
    }


def profile_curvature_metrics(
    points: Sequence[Sequence[float]],
) -> dict[str, Any]:
    """Return discrete curvature metrics for a regular closed planar profile.

    The signed turning angle is the polygonal form of ``integral(kappa ds)``.
    For a regular simple closed page it is ``2*pi`` times the turning number,
    even when pointwise curvature and perimeter change under a gauge view.
    """

    vertices = np.asarray(points, dtype=float)
    if vertices.ndim != 2 or vertices.shape[0] < 3 or vertices.shape[1] < 2:
        raise ValueError("a curvature profile needs at least three planar points")
    vertices = vertices[:, :2]
    if not np.all(np.isfinite(vertices)):
        raise ValueError("curvature profile points must be finite")

    incoming = vertices - np.roll(vertices, 1, axis=0)
    outgoing = np.roll(vertices, -1, axis=0) - vertices
    incoming_lengths = np.linalg.norm(incoming, axis=1)
    outgoing_lengths = np.linalg.norm(outgoing, axis=1)
    if np.any(incoming_lengths <= 1e-14) or np.any(outgoing_lengths <= 1e-14):
        raise ValueError("curvature profile must not contain zero-length edges")

    cross = incoming[:, 0] * outgoing[:, 1] - incoming[:, 1] * outgoing[:, 0]
    dot = np.einsum("ij,ij->i", incoming, outgoing)
    turning_angles = np.arctan2(cross, dot)
    dual_lengths = 0.5 * (incoming_lengths + outgoing_lengths)
    signed_curvature = turning_angles / dual_lengths
    perimeter = float(np.sum(outgoing_lengths))
    signed_total = float(np.sum(turning_angles))
    absolute_total = float(np.sum(np.abs(turning_angles)))
    rms_curvature = float(
        math.sqrt(np.sum(signed_curvature**2 * dual_lengths) / np.sum(dual_lengths))
    )

    return {
        "perimeter": perimeter,
        "signed_total_curvature": signed_total,
        "absolute_total_curvature": absolute_total,
        "turning_number": signed_total / (2.0 * math.pi),
        "rms_curvature": rms_curvature,
        "max_abs_curvature": float(np.max(np.abs(signed_curvature))),
        "min_signed_curvature": float(np.min(signed_curvature)),
        "max_signed_curvature": float(np.max(signed_curvature)),
        "sample_count": int(vertices.shape[0]),
        "regularity_check": "passed_nonzero_edges",
        "simplicity_assumption": "required_for_simple_closed_curve_interpretation",
    }


def make_infinity_root_profile(
    tower: CanonicalRootTower,
    *,
    height: float,
    gauge: FractionalGaugeSpec | None = None,
    radius: float = 10.0,
    center: tuple[float, float] = (0.0, 0.0),
    radial_gain: float = 0.35,
) -> dict[str, Any]:
    """Create a profile dictionary compatible with AdaptiveCAD profile consumers."""

    level = tower.level_at(height, gauge=gauge)
    source_radii, display_mapping = _display_radii(
        level.values, radius=radius, radial_gain=radial_gain
    )
    # A growth profile is not periodic. Reflect it before wrapping it around a
    # closed page so the first/last source values do not create an artificial
    # seam. Endpoints occur once; interior samples occur once on each half.
    radii = source_radii + tuple(reversed(source_radii[1:-1]))
    display_mapping.update(
        {
            "periodicization": "forward_then_reflected_without_duplicate_endpoints",
            "source_sample_count": len(source_radii),
            "profile_point_count": len(radii),
        }
    )
    cx, cy = (float(center[0]), float(center[1]))
    if not math.isfinite(cx) or not math.isfinite(cy):
        raise ValueError("profile center must be finite")
    angles = np.linspace(0.0, 2.0 * math.pi, len(radii), endpoint=False)
    points = [
        (cx + local_radius * math.cos(angle), cy + local_radius * math.sin(angle))
        for local_radius, angle in zip(radii, angles)
    ]
    curvature = profile_curvature_metrics(points)
    curvature["simplicity_status"] = "guaranteed_by_positive_single_radius_per_angle"
    curvature["orientation"] = "counterclockwise"
    descriptor = {
        "schema_version": SCHEMA_VERSION,
        "operator": ROOT_OPERATOR,
        "role": "geometry_descriptor_not_metric_kernel",
        "depth": tower.depth,
        "basepoint": tower.basepoint,
        "source": tower.source,
        "level": level.to_dict(include_values=True),
        "root_jet": tower.to_root_jet().to_dict(),
        "display_mapping": display_mapping,
        "curvature": curvature,
        "curvature_scope": "closed_planar_display_profile",
    }
    return {
        "type": "profile",
        "family": "infinity_root:profile",
        "descriptor": "infinity_root",
        "metric": "inherit",
        "closed": True,
        "points": points,
        "infinity_root": descriptor,
    }


def make_infinity_root_book(
    tower: CanonicalRootTower,
    *,
    fractional_pages: Sequence[tuple[float, FractionalGaugeSpec]] = (),
    radius: float = 10.0,
    page_gap: float = 2.0,
    radial_gain: float = 0.35,
) -> dict[str, Any]:
    """Build a quad-loftable stack of integer pages plus declared gauge views.

    The returned vertices and quads are a preview topology; the canonical data is
    the sampled root jet at the top level.  AdaptiveCAD can later replace the
    preview quads with OCC/NURBS lofts without changing the descriptor schema.
    """

    page_gap = float(page_gap)
    if not math.isfinite(page_gap) or page_gap <= 0.0:
        raise ValueError("page_gap must be finite and positive")

    requested: list[tuple[float, FractionalGaugeSpec | None]] = [
        (float(index), None) for index in range(tower.depth + 1)
    ]
    seen = {height for height, _ in requested}
    for height, gauge in fractional_pages:
        height = float(height)
        if abs(height - round(height)) <= 1e-12:
            raise ValueError("fractional_pages must not repeat an integer level")
        if height in seen:
            raise ValueError(f"duplicate book page height: {height}")
        requested.append((height, gauge))
        seen.add(height)
    requested.sort(key=lambda item: item[0])

    pages: list[dict[str, Any]] = []
    vertices: list[tuple[float, float, float]] = []
    for height, gauge in requested:
        profile = make_infinity_root_profile(
            tower,
            height=height,
            gauge=gauge,
            radius=radius,
            radial_gain=radial_gain,
        )
        z = page_gap * height
        page_points = [(float(x), float(y), z) for x, y in profile["points"]]
        level_meta = profile["infinity_root"]["level"]
        pages.append(
            {
                "height": height,
                "z": z,
                "status": level_meta["status"],
                "canonical": level_meta["canonical"],
                "gauge": level_meta["gauge"],
                "curvature": profile["infinity_root"]["curvature"],
                "points": page_points,
            }
        )
        vertices.extend(page_points)

    samples_per_page = len(pages[0]["points"])
    quads: list[tuple[int, int, int, int]] = []
    for page_index in range(len(pages) - 1):
        lower = page_index * samples_per_page
        upper = (page_index + 1) * samples_per_page
        for sample_index in range(samples_per_page):
            next_index = (sample_index + 1) % samples_per_page
            quads.append(
                (
                    lower + sample_index,
                    lower + next_index,
                    upper + next_index,
                    upper + sample_index,
                )
            )

    return {
        "type": "profile_stack",
        "family": "infinity_root:book",
        "descriptor": "infinity_root",
        "metric": "inherit",
        "schema_version": SCHEMA_VERSION,
        "root_jet": tower.to_root_jet().to_dict(),
        "canonical_integer_heights": list(range(tower.depth + 1)),
        "contains_gauge_views": any(not page["canonical"] for page in pages),
        "pages": pages,
        "vertices": vertices,
        "quads": quads,
        "preview_topology": "quad_loft_no_triangles",
        "curvature_audit": {
            "survives_regular_closed_page_morph": [
                "turning_number",
                "signed_total_curvature=2*pi*turning_number",
            ],
            "generally_gauge_dependent": [
                "pointwise_curvature",
                "rms_curvature",
                "perimeter",
                "absolute_total_curvature_for_nonconvex_profiles",
            ],
            "scope": (
                "Planar page curves only. This is the turning-tangent theorem, "
                "not a claim that the 3D loft has gauge-invariant Gaussian curvature."
            ),
        },
        "claim_boundary": (
            "Integer pages are operator levels; fractional pages are editable "
            "gauge views and are not coordinate-free fractional iterates."
        ),
    }


def compare_fractional_gauge_curvature(
    tower: CanonicalRootTower,
    *,
    height: float,
    gauges: Sequence[FractionalGaugeSpec],
    radius: float = 10.0,
    radial_gain: float = 0.35,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    """Compare curvature metrics for several gauges at one fractional height."""

    height = float(height)
    if abs(height - round(height)) <= 1e-12:
        raise ValueError("gauge comparison requires a non-integer height")
    if len(gauges) < 2:
        raise ValueError("gauge comparison requires at least two gauges")
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be finite and positive")

    rows = []
    for gauge in gauges:
        profile = make_infinity_root_profile(
            tower,
            height=height,
            gauge=gauge,
            radius=radius,
            radial_gain=radial_gain,
        )
        rows.append(
            {
                "gauge": gauge.to_dict(),
                "curvature": profile["infinity_root"]["curvature"],
            }
        )

    def spread(metric: str) -> float:
        values = [float(row["curvature"][metric]) for row in rows]
        return max(values) - min(values)

    signed_spread = spread("signed_total_curvature")
    turning_spread = spread("turning_number")
    invariant = []
    if signed_spread <= tolerance:
        invariant.append("signed_total_curvature")
    if turning_spread <= tolerance:
        invariant.append("turning_number")

    candidate_dependent = (
        "perimeter",
        "rms_curvature",
        "max_abs_curvature",
        "absolute_total_curvature",
    )
    dependent = [metric for metric in candidate_dependent if spread(metric) > tolerance]
    return {
        "height": height,
        "rows": rows,
        "numeric_tolerance": tolerance,
        "invariant_within_tolerance": invariant,
        "gauge_dependent_within_test": dependent,
        "spreads": {
            metric: spread(metric)
            for metric in (
                "signed_total_curvature",
                "turning_number",
                *candidate_dependent,
            )
        },
        "interpretation": (
            "For regular simple closed planar pages, signed total curvature is "
            "protected by the turning-tangent theorem. Local curvature and metric "
            "quantities are not protected by the Infinity-Root construction."
        ),
    }


def infinity_root_book_obj(book: Mapping[str, Any]) -> str:
    """Serialize a book preview as a quad-only Wavefront OBJ string."""

    if book.get("family") != "infinity_root:book":
        raise ValueError("expected an infinity_root:book object")
    lines = [
        "# AdaptiveCAD Infinity Root Book",
        f"# schema: {book.get('schema_version', SCHEMA_VERSION)}",
        f"# contains_gauge_views: {bool(book.get('contains_gauge_views'))}",
    ]
    for vertex in book["vertices"]:
        if len(vertex) != 3:
            raise ValueError("book vertices must be three-dimensional")
        lines.append(f"v {float(vertex[0]):.12g} {float(vertex[1]):.12g} {float(vertex[2]):.12g}")
    for quad in book["quads"]:
        if len(quad) != 4:
            raise ValueError("book preview topology must contain only quads")
        one_based = [int(index) + 1 for index in quad]
        lines.append("f " + " ".join(str(index) for index in one_based))
    return "\n".join(lines) + "\n"


__all__ = [
    "SCHEMA_VERSION",
    "ROOT_OPERATOR",
    "LevelStatus",
    "FractionalGaugeSpec",
    "ProfileLevel",
    "RootJetSamples",
    "CanonicalRootTower",
    "root_operator_samples",
    "tower_from_profile_samples",
    "make_exact_lift_tower",
    "make_infinity_root_profile",
    "make_infinity_root_book",
    "profile_curvature_metrics",
    "compare_fractional_gauge_curvature",
    "infinity_root_book_obj",
]
