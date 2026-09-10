"""Versioned coefficient-and-native-curve projects for the metric workbench.

Separate from .acad/AMA solids: no automatic conversion between chart coordinates
and world coordinates, no pickle/eval, and no authoritative preview meshes.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .geom.bezier import BezierCurve
from .geom.directional_metric import NormalMetricPatch, _finite
from .geom.metric_tools import point, unit_factor
from .linalg import Vec3

MAX_PROJECT_BYTES = 2_000_000


def _name(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 128
            or not value.isprintable()):
        raise ValueError("Names must contain 1..128 printable characters")
    return value


def _keys(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError("Unexpected or missing record fields")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class MetricCurve:
    name: str
    controls: tuple[tuple[float, float], ...]

    def __post_init__(self):
        _name(self.name)
        if not isinstance(self.controls, (list, tuple)) or not 1 <= len(self.controls) <= 32:
            raise ValueError("Require 1..32 Bezier control points")
        clean = []
        for row in self.controls:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise ValueError("Control points must be chart [x,y] pairs")
            clean.append(tuple(_finite(c, "control coordinate") for c in row))
        object.__setattr__(self, "controls", tuple(clean))

    def native(self) -> BezierCurve:
        return BezierCurve([Vec3(x, y, 0.0) for x, y in self.controls])

    def reversed(self, name=None) -> MetricCurve:
        return MetricCurve(self.name if name is None else name, tuple(reversed(self.controls)))

    def split(self, t: float) -> tuple[MetricCurve, MetricCurve]:
        t = _finite(t, "split parameter")
        if not 0 < t < 1:
            raise ValueError("Split parameter must be strictly between 0 and 1")
        a, b = self.native().subdivide(t)
        return tuple(MetricCurve(self.name[:122] + suffix, tuple((p.x, p.y) for p in curve.control_points))
                     for suffix, curve in ((" left", a), (" right", b)))

    def transformed(self, *, dx=0.0, dy=0.0, angle=0.0, factor=1.0) -> MetricCurve:
        """Active edit of chart coordinates; NOT a metric isometry or unit change."""
        dx, dy, angle, factor = (_finite(v, name) for v, name in
                                 ((dx, "dx"), (dy, "dy"), (angle, "angle"), (factor, "factor")))
        if factor <= 0:
            raise ValueError("Scale must be positive")
        c, s = math.cos(angle), math.sin(angle)
        return MetricCurve(self.name, tuple((dx + factor * (c*x - s*y),
                                             dy + factor * (s*x + c*y))
                                            for x, y in self.controls))


@dataclass(frozen=True)
class MetricProject:
    patch: NormalMetricPatch = NormalMetricPatch()
    curves: tuple[MetricCurve, ...] = ()
    name: str = "Untitled metric project"

    def __post_init__(self):
        _name(self.name)
        if not isinstance(self.patch, NormalMetricPatch):
            raise ValueError("Expected NormalMetricPatch")
        if not isinstance(self.curves, (tuple, list)) or len(self.curves) > 128:
            raise ValueError("At most 128 curves are supported")
        object.__setattr__(self, "curves", tuple(self.curves))
        names = set()
        for curve in self.curves:
            if not isinstance(curve, MetricCurve) or curve.name in names:
                raise ValueError("Curves must have unique names")
            names.add(curve.name)
            for xy in curve.controls:
                point(self.patch, xy)

    def with_patch(self, patch):
        # Validating a replacement before commit protects curves from silent clipping.
        return replace(self, patch=patch)

    def put_curve(self, curve: MetricCurve):
        if not isinstance(curve, MetricCurve):
            raise ValueError("Expected MetricCurve")
        curves = [c for c in self.curves if c.name != curve.name]
        curves.append(curve)
        return replace(self, curves=tuple(curves))

    def remove_curve(self, name):
        if name not in {c.name for c in self.curves}:
            raise ValueError("Unknown curve")
        return replace(self, curves=tuple(c for c in self.curves if c.name != name))

    def convert_units(self, unit):
        factor = unit_factor(self.patch.unit, unit)
        return replace(self, patch=self.patch.scaled(factor, unit=unit),
                       curves=tuple(MetricCurve(c.name, tuple((x*factor, y*factor)
                                   for x, y in c.controls)) for c in self.curves))

    def to_json(self):
        return json.dumps({"schema": "adaptivecad.metric_project", "version": 1,
                           "name": self.name, "patch": json.loads(self.patch.to_json()),
                           "curves": [{"name": c.name, "controls": c.controls} for c in self.curves]},
                          allow_nan=False, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text):
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_PROJECT_BYTES:
            raise ValueError("Project must be a UTF-8 JSON string of at most 2 MB")
        try:
            d = json.loads(text, object_pairs_hook=_pairs)
        except (RecursionError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid project JSON") from exc
        _keys(d, {"schema", "version", "name", "patch", "curves"})
        if (d["schema"] != "adaptivecad.metric_project" or type(d["version"]) is not int
                or d["version"] != 1 or not isinstance(d["curves"], list)):
            raise ValueError("Unsupported metric project schema or version")
        if len(d["curves"]) > 128:
            raise ValueError("At most 128 curves are supported")
        curves = []
        for row in d["curves"]:
            _keys(row, {"name", "controls"})
            curves.append(MetricCurve(row["name"], row["controls"]))
        patch = NormalMetricPatch.from_json(json.dumps(d["patch"], allow_nan=False))
        return cls(patch, tuple(curves), d["name"])

    @classmethod
    def load(cls, filename):
        with Path(filename).open("rb") as stream:
            raw = stream.read(MAX_PROJECT_BYTES + 1)
        if len(raw) > MAX_PROJECT_BYTES:
            raise ValueError("Project exceeds 2 MB")
        return cls.from_json(raw.decode("utf-8"))

    def save(self, filename, *, overwrite=False):
        """Atomic same-directory save; default never overwrites an existing path."""
        atomic_write(filename, self.to_json(), overwrite=overwrite)


def atomic_write(filename, text, *, overwrite=False):
    """Commit a UTF-8 text file after flush/fsync; clean up failed temporary writes."""
    if not isinstance(text, str):
        raise ValueError("Expected text")
    path = Path(filename)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix="." + path.name + ".",
                                         suffix=".tmp", delete=False) as f:
            temp = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if overwrite:
            os.replace(temp, path)
            temp = None
        else:
            # Atomic create-if-absent. Both names are on the same filesystem.
            # An unavailable hardlink operation fails closed, never overwrites.
            os.link(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


class MetricHistory:
    """Bounded immutable model history, independent of the CAD solid undo stack."""
    def __init__(self, project=None, limit=100):
        if type(limit) is not int or limit < 1 or limit > 1000:
            raise ValueError("History limit must be an integer in [1,1000]")
        self.limit = limit
        self.reset(MetricProject() if project is None else project)

    def reset(self, project):
        if not isinstance(project, MetricProject):
            raise ValueError("Expected MetricProject")
        self._states, self._index, self._saved = [project], 0, project

    @property
    def current(self):
        return self._states[self._index]

    @property
    def dirty(self):
        return self.current != self._saved

    @property
    def can_undo(self):
        return self._index > 0

    @property
    def can_redo(self):
        return self._index + 1 < len(self._states)

    def mark_saved(self):
        self._saved = self.current

    def commit(self, project):
        if not isinstance(project, MetricProject):
            raise ValueError("Expected MetricProject")
        if project == self.current:
            return
        states = self._states[:self._index + 1] + [project]
        self._states = states[-(self.limit + 1):]
        self._index = len(self._states) - 1

    def undo(self):
        if self.can_undo:
            self._index -= 1
        return self.current

    def redo(self):
        if self.can_redo:
            self._index += 1
        return self.current
