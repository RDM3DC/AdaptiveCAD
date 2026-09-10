"""Headless form adapter for existing mesh-free commands; no new geometry API."""

from __future__ import annotations

import copy
import math
import re

from adaptivecad.geom.meshfree_tools import Curve
from adaptivecad.geom.tool_document import ToolSession, strict_json
from adaptivecad.gui.meshfree_workbench import PRESETS

CURVE_SOURCE = frozenset({"extrude", "revolve", "loft", "sweep", "trim", "reverse", "split"})
UNITS = ("mm", "cm", "m", "in", "ft", "ft_us")
GROUPS = {
    "Model": (
        "Line",
        "Bezier",
        "Circle / arc",
        "Extrude sheet",
        "Revolve sheet",
        "Ruled loft",
        "Translation sweep",
    ),
    "Modify": (
        "Move / copy",
        "Copy",
        "Rotate",
        "Scale",
        "Mirror",
        "Trim by parameter",
        "Split",
        "Reverse",
        "Rectangular array",
        "Polar array",
    ),
    "Inspect": ("Convert units",),
}


def unique_name(document, base):
    """Reserve a base and generated suffixes without silently overwriting arrays."""
    names = {name for name, _ in document.entities}
    base = base[:100]
    candidate, index = base, 1
    while candidate in names or any(n.startswith(candidate + "_") for n in names):
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def command_defaults(label, document, selected=None):
    command = copy.deepcopy(PRESETS[label])
    op = command["op"]
    if "name" in command:
        command["name"] = unique_name(document, command["name"])
    choices = [
        n for n, entity in document.entities if op not in CURVE_SOURCE or isinstance(entity, Curve)
    ]
    if "source" in command:
        command["source"] = selected if selected in choices else (choices[0] if choices else "")
    curves = [n for n, e in document.entities if isinstance(e, Curve)]
    for key in ("target", "path"):
        if key in command:
            command[key] = next((n for n in curves if n != command.get("source")), "")
    extras = {
        "arc": {"center": [0, 0, 0], "normal": [0, 0, 1], "x_direction": [1, 0, 0], "start": 0.0},
        "revolve": {"origin": [0, 0, 0]},
        "rotate": {"origin": [0, 0, 0]},
        "scale": {"origin": [0, 0, 0]},
        "mirror": {"origin": [0, 0, 0]},
        "polar_array": {"axis": [0, 0, 1], "origin": [0, 0, 0], "angle": math.tau},
    }
    command.update(extras.get(op, {}))
    return command


def field_kind(key, value):
    if key in ("source", "target", "path"):
        return "entity"
    if key == "unit":
        return "unit"
    if key == "points":
        return "points"
    if isinstance(value, (list, tuple)):
        return "vector"
    if isinstance(value, str):
        return "text"
    if key in ("rows", "columns", "instances"):
        return "integer"
    return "number"


def field_text(kind, value):
    if kind == "points":
        return "\n".join(", ".join(str(v) for v in row) for row in value)
    if kind == "vector":
        return ", ".join(str(v) for v in value)
    return str(value)


def _finite(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Numbers must be finite")
    return value


def _vector(text):
    values = [v.strip() for v in text.split(",")]
    if len(values) != 3:
        raise ValueError("Enter three comma-separated coordinates: x, y, z")
    return [_finite(v) for v in values]


def parse_field(kind, text):
    if not isinstance(text, str) or len(text) > 64000:
        raise ValueError("Field input is too large")
    if kind == "text":
        # Preserve names exactly; the kernel owns name validation.
        return text
    value = text.strip()
    if kind == "entity":
        return text
    if kind == "unit":
        if value not in UNITS:
            raise ValueError("Choose an explicit supported unit")
        return value
    if kind == "integer":
        if not re.fullmatch(r"[+-]?\d{1,10}", value):
            raise ValueError("Enter an integer")
        return int(value)
    if kind == "number":
        return _finite(value)
    if kind == "vector":
        return _vector(value)
    if kind == "points":
        rows = (
            strict_json(value)
            if value.startswith("[")
            else [_vector(row) for row in value.splitlines() if row.strip()]
        )
        if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
            raise ValueError("Enter 1..32 control points, one x, y, z row per line")
        result = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != 3:
                raise ValueError("Every control point needs three coordinates")
            if any(type(v) not in (float, int) for v in row):
                raise ValueError("Control coordinates must be numbers, not strings or booleans")
            result.append([_finite(v) for v in row])
        return result
    raise ValueError("Unsupported form field")


def validate_command(document, command):
    """Use the real backend on a separate session; never commit the user's history."""
    return ToolSession(document).execute(command)
