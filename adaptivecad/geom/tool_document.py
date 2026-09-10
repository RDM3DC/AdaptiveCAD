"""Strict mesh-free tool document and atomic, undoable command session.

This is a separate versioned document, NOT a replacement for existing AMA,
STEP or sketch formats. It has no expression evaluation or executable payloads.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .directional_metric import NormalMetricPatch
from .meshfree_tools import (
    Curve,
    Surface,
    conversion_factor,
    polar_array,
    rectangular_array,
    reflection,
    rotation,
    scaling,
    translation,
)


def strict_json(text):
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise ValueError("JSON input must be text of at most 2 MB")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"Duplicate key: {key}")
            out[key] = value
        return out
    def constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid or excessively nested JSON") from exc


def _keys(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= set(obj) or set(obj)-set(required)-set(optional):
        raise ValueError(f"Expected required keys {tuple(required)}; optional {tuple(optional)}")


def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 128 or any(ord(c) < 32 for c in value):
        raise ValueError("Name must contain 1..128 printable characters")
    return value


def entity_record(entity):
    if isinstance(entity, Curve):
        return {"type": "curve", "kind": entity.kind, "points": entity.points,
                "interval": entity.interval, "start": entity.start, "sweep": entity.sweep}
    if isinstance(entity, Surface):
        return {"type": "surface", "kind": entity.kind, "profile": entity_record(entity.profile),
                "guide": None if entity.guide is None else entity_record(entity.guide),
                "vector": entity.vector, "origin": entity.origin, "angle": entity.angle,
                "transform": entity.transform}
    raise ValueError("Unsupported entity")


def entity_from_record(obj, *, curve_only=False):
    if not isinstance(obj, dict):
        raise ValueError("Expected entity object")
    if obj.get("type") == "curve":
        _keys(obj, ("type", "kind", "points", "interval", "start", "sweep"))
        return Curve(obj["kind"], obj["points"], obj["interval"], obj["start"], obj["sweep"])
    if not curve_only and obj.get("type") == "surface":
        _keys(obj, ("type", "kind", "profile", "guide", "vector", "origin", "angle", "transform"))
        profile = entity_from_record(obj["profile"], curve_only=True)
        guide = None if obj["guide"] is None else entity_from_record(obj["guide"], curve_only=True)
        return Surface(obj["kind"], profile, guide, obj["vector"], obj["origin"], obj["angle"], obj["transform"])
    raise ValueError("Unsupported entity type or nested surface")


@dataclass(frozen=True)
class ToolDocument:
    unit: str = "mm"
    entities: tuple = ()
    metric: NormalMetricPatch | None = None

    def __post_init__(self):
        conversion_factor(self.unit, self.unit)
        items = tuple((name(n), e) for n, e in self.entities)
        if len(items) > 1000 or len({n for n, _ in items}) != len(items):
            raise ValueError("Require unique names and at most 1000 entities")
        if any(not isinstance(e, (Curve, Surface)) for _, e in items):
            raise ValueError("Only validated curves/surfaces are supported")
        if self.metric is not None and (not isinstance(self.metric, NormalMetricPatch) or self.metric.unit != self.unit):
            raise ValueError("Metric and document must have identical explicit units")
        object.__setattr__(self, "entities", items)

    def get(self, key):
        name(key)
        for n, e in self.entities:
            if key == n:
                return e
        raise ValueError(f"Unknown entity: {key}")

    def converted(self, target):
        factor = conversion_factor(self.unit, target)
        transform = scaling(factor)
        return ToolDocument(target, tuple((n, e.transformed(transform)) for n, e in self.entities),
                            None if self.metric is None else self.metric.scaled(factor, unit=target))

    def to_json(self):
        obj = {"schema": "adaptivecad.meshfree_tool_document", "version": 1, "unit": self.unit,
               "entities": [{"name": n, "geometry": entity_record(e)} for n, e in self.entities],
               "metric": None if self.metric is None else json.loads(self.metric.to_json())}
        return json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)

    @classmethod
    def from_json(cls, text):
        obj = strict_json(text)
        _keys(obj, ("schema", "version", "unit", "entities", "metric"))
        if obj["schema"] != "adaptivecad.meshfree_tool_document" or type(obj["version"]) is not int or obj["version"] != 1:
            raise ValueError("Unsupported document schema/version")
        if not isinstance(obj["entities"], list) or len(obj["entities"]) > 1000:
            raise ValueError("Expected at most 1000 entity records")
        items = []
        for row in obj["entities"]:
            _keys(row, ("name", "geometry"))
            items.append((row["name"], entity_from_record(row["geometry"])))
        metric = None if obj["metric"] is None else NormalMetricPatch.from_json(json.dumps(obj["metric"], allow_nan=False))
        return cls(obj["unit"], tuple(items), metric)

    def save(self, path, *, overwrite=False):
        """Refuse overwrite by default. Only a complete validated record is written."""
        if type(overwrite) is not bool:
            raise ValueError("overwrite must be boolean")
        text = self.to_json()
        destination = Path(path)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                             prefix=".meshfree-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            if overwrite:
                os.replace(temporary, destination)
            else:
                # Atomic create-if-absent; never clobbers a competing writer.
                os.link(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        with Path(path).open(encoding="utf-8") as stream:
            text = stream.read(2_000_001)
        return cls.from_json(text)


COMMANDS = {
    "line": ({"start", "end"}, set()),
    "bezier": ({"points"}, set()),
    "arc": (set(), {"center", "radius", "normal", "x_direction", "start", "sweep"}),
    "extrude": ({"source", "vector"}, set()),
    "revolve": ({"source", "axis", "angle"}, {"origin"}),
    "loft": ({"source", "target"}, set()),
    "sweep": ({"source", "path"}, set()),
    "move": ({"source", "delta"}, set()),
    "copy": ({"source"}, set()),
    "rotate": ({"source", "axis", "angle"}, {"origin"}),
    "scale": ({"source", "factor"}, {"origin"}),
    "mirror": ({"source", "normal"}, {"origin"}),
    "trim": ({"source", "start", "stop"}, set()),
    "reverse": ({"source"}, set()),
    "split": ({"source", "parameter"}, set()),
    "rectangular_array": ({"source", "rows", "columns"}, {"row_step", "column_step"}),
    "polar_array": ({"source", "instances"}, {"angle", "axis", "origin"}),
}


class ToolSession:
    """Snapshot undo/redo, atomic multi-command batches, bounded history."""
    def __init__(self, document=None):
        self.document = ToolDocument() if document is None else document
        if not isinstance(self.document, ToolDocument):
            raise ValueError("Expected ToolDocument")
        self._undo, self._redo = [], []

    def _commit(self, document):
        if document != self.document:
            self._undo.append(self.document)
            self._undo = self._undo[-100:]
            self._redo.clear()
            self.document = document

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self.document)
        self.document = self._undo.pop()
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self.document)
        self.document = self._redo.pop()
        return True

    def execute(self, command):
        return self.execute_many([command])

    def execute_many(self, commands):
        commands = tuple(commands)
        if not 1 <= len(commands) <= 1000:
            raise ValueError("A batch must contain 1..1000 commands")
        candidate = self.document
        for command in commands:
            candidate = self._apply(candidate, command)
        self._commit(candidate)
        return self.document

    @staticmethod
    def _apply(document, command):
        if not isinstance(command, dict) or not isinstance(command.get("op"), str):
            raise ValueError("Command requires an op string")
        op = command["op"]
        if op == "convert_units":
            _keys(command, ("op", "unit"))
            return document.converted(command["unit"])
        if op == "delete":
            _keys(command, ("op", "source"))
            document.get(command["source"])
            return replace(document, entities=tuple((n, e) for n, e in document.entities if n != command["source"]))
        if op == "set_metric":
            _keys(command, ("op", "metric"))
            metric = NormalMetricPatch.from_json(json.dumps(command["metric"], allow_nan=False))
            return replace(document, metric=metric)
        if op not in COMMANDS:
            raise ValueError(f"Unsupported operation: {op}")
        required, optional = COMMANDS[op]
        _keys(command, required | {"op", "name"}, optional | {"replace"})
        n = name(command["name"])
        overwrite = command.get("replace", False)
        if type(overwrite) is not bool:
            raise ValueError("replace must be a boolean")
        source = document.get(command["source"]) if "source" in command else None
        if op in ("extrude", "revolve", "loft", "sweep", "trim", "reverse", "split") and not isinstance(source, Curve):
            raise ValueError(f"{op} requires a Curve source")
        args = {k: command[k] for k in required | optional if k in command and k != "source"}
        if op == "line":
            entity = Curve.line(**args)
        elif op == "bezier":
            entity = Curve("bezier", args["points"])
        elif op == "arc":
            entity = Curve.arc(**args)
        elif op == "extrude":
            entity = Surface(op, source, vector=args["vector"])
        elif op == "revolve":
            entity = Surface(op, source, vector=args["axis"], angle=args["angle"], origin=args.get("origin", (0, 0, 0)))
        elif op in ("loft", "sweep"):
            guide = document.get(args["target" if op == "loft" else "path"])
            entity = Surface(op, source, guide)
        elif op == "copy":
            entity = source
        elif op in ("move", "rotate", "scale", "mirror"):
            function = {"move": translation, "rotate": rotation, "scale": scaling, "mirror": reflection}[op]
            entity = source.transformed(function(**args))
        elif op == "trim":
            entity = source.trim(**args)
        elif op == "reverse":
            entity = source.reversed()
        elif op == "split":
            entity = source.split(args["parameter"])
        elif op == "rectangular_array":
            entity = rectangular_array(source, **args)
        else:
            entity = polar_array(source, **args)
        additions = ((n, entity),) if not isinstance(entity, tuple) else tuple((name(f"{n}_{i+1}"), e) for i, e in enumerate(entity))
        new_names = {key for key, _ in additions}
        collisions = new_names & {key for key, _ in document.entities}
        if collisions and not overwrite:
            raise ValueError(f"Names already exist: {sorted(collisions)}; use replace=true explicitly")
        kept = tuple((key, e) for key, e in document.entities if key not in new_names)
        return replace(document, entities=kept + additions)
