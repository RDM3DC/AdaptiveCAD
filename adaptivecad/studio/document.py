"""Validated curve-native Studio documents. All stored lengths are millimetres."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import tempfile
import uuid
from pathlib import Path

SCHEMA = "adaptivecad.studio/1"
MAX_ACTIVE_BODIES = 48
MAX_FILE_BYTES = 8 * 1024 * 1024
UNIT_MM = {"mm": 1.0, "in": 25.4, "US survey ft": 1200000.0 / 3937.0}
KINDS = {
    "Box": (2, ("Half X", "Half Y", "Half Z"), (20., 14., 8., 0.), (0, 1, 2)),
    "Sphere": (1, ("Radius",), (15., 0., 0., 0.), (0,)),
    "Capsule": (3, ("Radius", "Centre span (Y)"), (8., 25., 0., 0.), (0, 1)),
    "Torus": (4, ("Major radius", "Tube radius"), (20., 5., 0., 0.), (0, 1)),
    "Superellipsoid": (6, ("Radius", "Power"), (20., 4., 0., 0.), (0,)),
    "Mobius": (5, ("Radius", "Half width"), (20., 5., 0., 0.), (0, 1)),
    "Pi bloom": (18, ("Radius", "Bloom", "Petals", "Crown"), (20., .28, 7., .22), (0,)),
}
SKETCH_POINTS = {"line": 2, "rectangle": 2, "circle": 2, "bezier": 4}


def uid():
    return uuid.uuid4().hex


def number(value, name="value", low=-1e6, high=1e6):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number.")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low:g} and {high:g}.")
    return value


def vector(value, size, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f"{name} requires {size} coordinates.")
    return [number(v, name, low, high) for v in value]


def text(value, name, maximum=120):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1 to {maximum} characters.")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"{name} cannot contain control characters.")
    return value


def keys(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected.split()):
        raise ValueError(f"Expected fields: {expected}.")


def new_document(name="Untitled"):
    return {"schema": SCHEMA, "name": name, "units": "mm", "bodies": [], "sketches": []}


def new_body(kind="Box", name=None):
    if kind not in KINDS:
        raise ValueError("Unsupported primitive.")
    return {"id": uid(), "name": name or kind, "kind": kind,
            "params": list(KINDS[kind][2]), "position": [0., 0., 0.],
            "rotation": [0., 0., 0.], "scale": [1., 1., 1.],
            "color": [.23, .55, .85], "enabled": True, "operation": "solid"}


def new_sketch(name="Sketch 1"):
    return {"id": uid(), "name": name, "plane": "XY", "entities": []}


def new_entity(kind, points):
    result = {"id": uid(), "kind": kind, "points": [list(p) for p in points]}
    validate_entity(result)
    return result


def validate_entity(entity):
    keys(entity, "id kind points")
    text(entity["id"], "Entity ID", 64)
    kind = entity["kind"]
    if not isinstance(kind, str) or kind not in SKETCH_POINTS:
        raise ValueError("Unsupported sketch entity.")
    points = entity["points"]
    if not isinstance(points, list) or len(points) != SKETCH_POINTS[kind]:
        raise ValueError("Wrong number of defining points.")
    for p in points:
        vector(p, 2, "Sketch point")
    if kind == "rectangle":
        if min(abs(points[1][i] - points[0][i]) for i in range(2)) < 1e-6:
            raise ValueError("A rectangle needs positive width and height.")
    elif max(math.dist(points[0], p) for p in points[1:]) < 1e-6:
        raise ValueError("The sketch entity has zero extent.")


def validate(document):
    keys(document, "schema name units bodies sketches")
    if document["schema"] != SCHEMA:
        raise ValueError("Unsupported Studio document version.")
    text(document["name"], "Document name")
    if not isinstance(document["units"], str) or document["units"] not in UNIT_MM:
        raise ValueError("Unsupported display units.")
    ids = set()
    def unique(value):
        text(value, "ID", 64)
        if value in ids:
            raise ValueError("Duplicate geometry ID.")
        ids.add(value)
    bodies, sketches = document["bodies"], document["sketches"]
    if not isinstance(bodies, list) or len(bodies) > 512:
        raise ValueError("A document supports at most 512 stored bodies.")
    active = []
    for body in bodies:
        keys(body, "id name kind params position rotation scale color enabled operation")
        unique(body["id"])
        text(body["name"], "Body name")
        kind = body["kind"]
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("Unsupported primitive kind.")
        p = vector(body["params"], 4, "Parameters")
        n = len(KINDS[kind][1])
        if any(p[i] != 0 for i in range(n, 4)):
            raise ValueError("Unused primitive parameters must be zero.")
        for i in KINDS[kind][3]:
            number(p[i], KINDS[kind][1][i], 1e-6, 10000)
        if kind == "Torus" and p[1] >= p[0]:
            raise ValueError("Tube radius must be smaller than major radius.")
        if kind == "Mobius" and p[1] >= p[0]:
            raise ValueError("Half width must be smaller than radius.")
        if kind == "Superellipsoid":
            number(p[1], "Power", 1, 16)
        if kind == "Pi bloom":
            number(p[1], "Bloom", 0, 1)
            number(p[2], "Petals", 2, 32)
            if not p[2].is_integer():
                raise ValueError("Petals must be an integer.")
            number(p[3], "Crown", -.5, .5)
        vector(body["position"], 3, "Position", -10000, 10000)
        vector(body["rotation"], 3, "Rotation", -36000, 36000)
        vector(body["scale"], 3, "Scale", .001, 100)
        vector(body["color"], 3, "Color", 0, 1)
        if type(body["enabled"]) is not bool:
            raise ValueError("Enabled must be Boolean.")
        if body["operation"] not in ("solid", "subtract", "intersect"):
            raise ValueError("Unsupported CSG operation.")
        if body["enabled"]:
            active.append(body)
    if len(active) > MAX_ACTIVE_BODIES:
        raise ValueError("The analytic renderer supports at most 48 enabled bodies. Suppress some first.")
    if active and active[0]["operation"] != "solid":
        raise ValueError("The first enabled body must be Join; CSG evaluates from top to bottom.")
    if not isinstance(sketches, list) or len(sketches) > 100:
        raise ValueError("A document supports at most 100 sketches.")
    count = 0
    for sketch in sketches:
        keys(sketch, "id name plane entities")
        unique(sketch["id"])
        text(sketch["name"], "Sketch name")
        if sketch["plane"] != "XY":
            raise ValueError("This version supports XY sketches only.")
        if not isinstance(sketch["entities"], list):
            raise ValueError("Sketch entities must be a list.")
        count += len(sketch["entities"])
        if count > 10000:
            raise ValueError("Too many sketch entities.")
        for entity in sketch["entities"]:
            validate_entity(entity)
            unique(entity["id"])
    return document


def dumps(document):
    validate(document)
    return json.dumps(document, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def loads(data):
    if not isinstance(data, str) or len(data.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Studio documents must be smaller than 8 MiB.")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        return validate(json.loads(data, object_pairs_hook=pairs))
    except (RecursionError, OverflowError, TypeError, KeyError) as exc:
        raise ValueError("Malformed Studio document.") from exc


def read_document(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Studio document is too large.")
    return loads(raw.decode("utf-8"))


def atomic_write(path, content):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class History:
    """Whole-document transactions: failed edits preserve state and undo history."""
    def __init__(self, document=None):
        self.document = copy.deepcopy(validate(new_document() if document is None else document))
        self.entries = []
        self.index = 0
        self.saved = dumps(self.document)
        self.path = None
        self.disk_digest = None

    @property
    def dirty(self):
        return dumps(self.document) != self.saved

    def execute(self, label, edit):
        before = dumps(self.document)
        candidate = copy.deepcopy(self.document)
        edit(candidate)
        after = dumps(candidate)
        if before == after:
            return False
        self.entries[self.index:] = [(label, before, after)]
        if len(self.entries) > 100:
            self.entries.pop(0)
        self.index = len(self.entries)
        self.document = candidate
        return True

    def undo(self):
        if self.index:
            self.index -= 1
            self.document = loads(self.entries[self.index][1])

    def redo(self):
        if self.index < len(self.entries):
            self.document = loads(self.entries[self.index][2])
            self.index += 1

    def save(self, path):
        path = Path(path).resolve()
        if self.path == path and path.exists() and self.disk_digest:
            if hashlib.sha256(path.read_bytes()).hexdigest() != self.disk_digest:
                raise ValueError("The file changed on disk. Use Save As to avoid overwriting those changes.")
        data = dumps(self.document) + "\n"
        atomic_write(path, data)
        self.path = path
        self.disk_digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
        self.saved = dumps(self.document)

    @classmethod
    def open(cls, path):
        path = Path(path).resolve()
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Studio document is too large.")
        history = cls(loads(raw.decode("utf-8")))
        history.path = path
        history.disk_digest = hashlib.sha256(raw).hexdigest()
        return history


def find_body(document, identifier):
    return next(body for body in document["bodies"] if body["id"] == identifier)


def find_sketch(document, identifier):
    return next(sketch for sketch in document["sketches"] if sketch["id"] == identifier)


def extrude_rectangle(document, sketch_id, entity_id, height):
    """Create an independent box from one XY rectangle, not an associative feature."""
    height = number(height, "Extrusion height (mm)", 1e-6, 10000)
    sketch = find_sketch(document, sketch_id)
    entity = next(e for e in sketch["entities"] if e["id"] == entity_id)
    if entity["kind"] != "rectangle":
        raise ValueError("This analytic backend extrudes rectangles only. General profiles require a BREP backend.")
    a, b = entity["points"]
    body = new_body("Box", "Extruded rectangle")
    body["params"] = [abs(b[0]-a[0])/2, abs(b[1]-a[1])/2, height/2, 0.]
    body["position"] = [(a[0]+b[0])/2, (a[1]+b[1])/2, height/2]
    document["bodies"].append(body)
    return body["id"]


def transform_matrix(body):
    """Conventional T Rz Ry Rx S; degrees for rotation, mm for translation."""
    x, y, z = map(math.radians, body["rotation"])
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rotation = [[cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx],
                [sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx], [-sy, cy*sx, cy*cx]]
    return [[rotation[i][j]*body["scale"][j] for j in range(3)] + [body["position"][i]] for i in range(3)] + [[0., 0., 0., 1.]]
