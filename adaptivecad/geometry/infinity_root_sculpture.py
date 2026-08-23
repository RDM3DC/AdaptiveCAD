"""Printable desk-sculpture geometry for an Infinity Root Book.

The descriptor mathematics lives in :mod:`adaptivecad.geometry.infinity_root`.
This module turns an ``infinity_root:book`` descriptor into fabrication
geometry without changing the meaning of its pages:

* canonical integer pages become substantial blue ribbon solids;
* fractional gauge views become thinner gold ribbon solids;
* a hidden lower rail holds every page in one physical composition; and
* a broad, flat plinth makes the tilted book suitable for a desk display.

The native OBJ topology contains quads only.  The optional STL serializer is a
compatibility export for conventional slicers and therefore triangulates each
quad at export time.  The component shells intentionally overlap at joints so
that slicers can union them while retaining separate blue/gold tool channels.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

SCULPTURE_SCHEMA_VERSION = "adaptivecad.infinity_root.sculpture/1.0"


@dataclass(frozen=True)
class InfinityRootSculptureSpec:
    """Millimetre-scale fabrication settings for the desk sculpture."""

    tilt_degrees: float = 80.0
    canonical_band_width: float = 3.8
    canonical_page_thickness: float = 2.6
    gauge_band_width: float = 2.4
    gauge_page_thickness: float = 1.8
    rail_min_width: float = 17.0
    rail_min_depth: float = 7.0
    joint_overlap: float = 1.2
    assembly_clearance: float = 2.0
    base_bottom_width: float = 124.0
    base_bottom_depth: float = 70.0
    base_top_inset: float = 6.0
    base_height: float = 8.0
    base_margin: float = 9.0
    pedestal_bottom_width: float = 26.0
    pedestal_bottom_depth: float = 18.0
    pedestal_top_width: float = 20.0
    pedestal_top_depth: float = 13.0
    accent_width: float = 38.0
    accent_depth: float = 1.4
    accent_height: float = 3.2

    def __post_init__(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            number = float(value)
            if not math.isfinite(number) or number <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, number)
        if not 55.0 <= self.tilt_degrees <= 85.0:
            raise ValueError("tilt_degrees must lie between 55 and 85 degrees")
        if 2.0 * self.base_top_inset >= min(
            self.base_bottom_width, self.base_bottom_depth
        ):
            raise ValueError("base_top_inset leaves no top face")
        if self.pedestal_top_width > self.pedestal_bottom_width:
            raise ValueError("pedestal_top_width must not exceed pedestal_bottom_width")
        if self.pedestal_top_depth > self.pedestal_bottom_depth:
            raise ValueError("pedestal_top_depth must not exceed pedestal_bottom_depth")

    @property
    def minimum_feature(self) -> float:
        return min(
            self.canonical_band_width,
            self.canonical_page_thickness,
            self.gauge_band_width,
            self.gauge_page_thickness,
            self.accent_depth,
            self.accent_height,
        )


class _QuadBuilder:
    def __init__(self) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.quads: list[tuple[int, int, int, int]] = []
        self.parts: list[dict[str, Any]] = []

    def add_part(
        self,
        *,
        name: str,
        role: str,
        material: str,
        print_channel: str,
        vertices: Sequence[Sequence[float]],
        quads: Sequence[Sequence[int]],
        metadata: Mapping[str, Any] | None = None,
    ) -> int:
        vertex_start = len(self.vertices)
        face_start = len(self.quads)
        converted_vertices = [
            (float(vertex[0]), float(vertex[1]), float(vertex[2])) for vertex in vertices
        ]
        converted_quads = [
            tuple(vertex_start + int(index) for index in quad) for quad in quads
        ]
        if any(len(quad) != 4 for quad in converted_quads):
            raise ValueError("sculpture native topology accepts quad faces only")
        self.vertices.extend(converted_vertices)
        self.quads.extend(converted_quads)
        part: dict[str, Any] = {
            "name": name,
            "role": role,
            "material": material,
            "print_channel": print_channel,
            "vertex_start": vertex_start,
            "vertex_count": len(converted_vertices),
            "face_start": face_start,
            "face_count": len(converted_quads),
        }
        if metadata:
            part.update(dict(metadata))
        self.parts.append(part)
        return len(self.parts) - 1


def _ring_ribbon_mesh(
    centerline: Sequence[Sequence[float]],
    *,
    band_width: float,
    page_thickness: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int, int]]]:
    points = np.asarray(centerline, dtype=float)
    if points.ndim != 2 or points.shape[0] < 8 or points.shape[1] != 3:
        raise ValueError("a sculpture page needs at least eight three-dimensional points")
    if not np.all(np.isfinite(points)):
        raise ValueError("sculpture page points must be finite")
    if float(np.ptp(points[:, 2])) > 1e-9:
        raise ValueError("each source book page must be planar before sculpture tilt")

    radial = points[:, :2]
    lengths = np.linalg.norm(radial, axis=1)
    if np.any(lengths <= band_width):
        raise ValueError("page band width is too large for the source profile")
    unit = radial / lengths[:, None]
    half_band = 0.5 * band_width
    half_height = 0.5 * page_thickness
    inner = radial - half_band * unit
    outer = radial + half_band * unit
    z = float(points[0, 2])

    vertices: list[tuple[float, float, float]] = []
    for index in range(points.shape[0]):
        vertices.extend(
            [
                (float(outer[index, 0]), float(outer[index, 1]), z - half_height),
                (float(outer[index, 0]), float(outer[index, 1]), z + half_height),
                (float(inner[index, 0]), float(inner[index, 1]), z - half_height),
                (float(inner[index, 0]), float(inner[index, 1]), z + half_height),
            ]
        )

    quads: list[tuple[int, int, int, int]] = []
    sample_count = points.shape[0]
    for index in range(sample_count):
        next_index = (index + 1) % sample_count
        outer_bottom = 4 * index
        outer_top = outer_bottom + 1
        inner_bottom = outer_bottom + 2
        inner_top = outer_bottom + 3
        next_outer_bottom = 4 * next_index
        next_outer_top = next_outer_bottom + 1
        next_inner_bottom = next_outer_bottom + 2
        next_inner_top = next_outer_bottom + 3
        quads.extend(
            [
                (inner_top, outer_top, next_outer_top, next_inner_top),
                (inner_bottom, next_inner_bottom, next_outer_bottom, outer_bottom),
                (outer_bottom, next_outer_bottom, next_outer_top, outer_top),
                (inner_bottom, inner_top, next_inner_top, next_inner_bottom),
            ]
        )
    return vertices, quads


def _frustum_mesh(
    *,
    center_x: float,
    center_y: float,
    bottom_width: float,
    bottom_depth: float,
    top_width: float,
    top_depth: float,
    bottom_z: float,
    top_z: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int, int]]]:
    if top_z <= bottom_z:
        raise ValueError("frustum top_z must exceed bottom_z")
    bx = 0.5 * bottom_width
    by = 0.5 * bottom_depth
    tx = 0.5 * top_width
    ty = 0.5 * top_depth
    vertices = [
        (center_x - bx, center_y - by, bottom_z),
        (center_x + bx, center_y - by, bottom_z),
        (center_x + bx, center_y + by, bottom_z),
        (center_x - bx, center_y + by, bottom_z),
        (center_x - tx, center_y - ty, top_z),
        (center_x + tx, center_y - ty, top_z),
        (center_x + tx, center_y + ty, top_z),
        (center_x - tx, center_y + ty, top_z),
    ]
    quads = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    return vertices, quads


def _box_mesh(
    *,
    center_x: float,
    center_y: float,
    width: float,
    depth: float,
    bottom_z: float,
    top_z: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int, int]]]:
    return _frustum_mesh(
        center_x=center_x,
        center_y=center_y,
        bottom_width=width,
        bottom_depth=depth,
        top_width=width,
        top_depth=depth,
        bottom_z=bottom_z,
        top_z=top_z,
    )


def _rotate_and_place_upper_assembly(
    vertices: Sequence[Sequence[float]],
    *,
    tilt_degrees: float,
    target_min_z: float,
) -> list[tuple[float, float, float]]:
    array = np.asarray(vertices, dtype=float)
    angle = math.radians(tilt_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    transformed = np.empty_like(array)
    transformed[:, 0] = array[:, 0]
    transformed[:, 1] = cosine * array[:, 1] - sine * array[:, 2]
    transformed[:, 2] = sine * array[:, 1] + cosine * array[:, 2]
    transformed[:, 0] -= 0.5 * (float(np.min(transformed[:, 0])) + float(np.max(transformed[:, 0])))
    transformed[:, 1] -= 0.5 * (float(np.min(transformed[:, 1])) + float(np.max(transformed[:, 1])))
    transformed[:, 2] += target_min_z - float(np.min(transformed[:, 2]))
    return [tuple(float(value) for value in vertex) for vertex in transformed]


def _edge_audit(
    quads: Sequence[Sequence[int]], parts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    shell_rows: list[dict[str, Any]] = []
    all_closed = True
    for part in parts:
        start = int(part["face_start"])
        stop = start + int(part["face_count"])
        edge_counts: Counter[tuple[int, int]] = Counter()
        for quad in quads[start:stop]:
            for left, right in zip(quad, (*quad[1:], quad[0])):
                edge_counts[tuple(sorted((int(left), int(right))))] += 1
        boundary = sum(count == 1 for count in edge_counts.values())
        nonmanifold = sum(count > 2 for count in edge_counts.values())
        closed = bool(edge_counts) and boundary == 0 and nonmanifold == 0
        all_closed = all_closed and closed
        shell_rows.append(
            {
                "name": part["name"],
                "closed_edge_manifold": closed,
                "boundary_edges": boundary,
                "nonmanifold_edges": nonmanifold,
            }
        )
    return {
        "all_component_shells_closed_edge_manifold": all_closed,
        "component_shell_count": len(shell_rows),
        "component_shells": shell_rows,
    }


def _face_area_audit(
    vertices: Sequence[Sequence[float]], quads: Sequence[Sequence[int]]
) -> dict[str, Any]:
    points = np.asarray(vertices, dtype=float)
    minimum = math.inf
    degenerate = 0
    for quad in quads:
        a, b, c, d = (points[int(index)] for index in quad)
        area = 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))
        area += 0.5 * float(np.linalg.norm(np.cross(c - a, d - a)))
        minimum = min(minimum, area)
        if area <= 1e-10:
            degenerate += 1
    return {
        "degenerate_quad_count": degenerate,
        "minimum_quad_area_mm2": minimum,
    }


def make_infinity_root_sculpture(
    book: Mapping[str, Any],
    *,
    spec: InfinityRootSculptureSpec | None = None,
) -> dict[str, Any]:
    """Turn an Infinity Root Book descriptor into a tilted desk sculpture."""

    if book.get("family") != "infinity_root:book":
        raise ValueError("expected an infinity_root:book object")
    pages = list(book.get("pages", ()))
    if len(pages) < 2:
        raise ValueError("a sculpture needs at least two Infinity Root Book pages")
    spec = InfinityRootSculptureSpec() if spec is None else spec
    builder = _QuadBuilder()

    bottom_samples: list[tuple[float, float]] = []
    page_widths: list[float] = []
    page_thicknesses: list[float] = []
    for page_index, page in enumerate(pages):
        canonical = bool(page.get("canonical"))
        band_width = spec.canonical_band_width if canonical else spec.gauge_band_width
        thickness = (
            spec.canonical_page_thickness if canonical else spec.gauge_page_thickness
        )
        page_vertices, page_quads = _ring_ribbon_mesh(
            page["points"],
            band_width=band_width,
            page_thickness=thickness,
        )
        status = str(page.get("status", "canonical_integer" if canonical else "gauge_view"))
        material = "canonical_blue" if canonical else "gauge_gold"
        channel = "blue" if canonical else "gold"
        builder.add_part(
            name=f"page_{page_index:02d}_height_{float(page['height']):g}",
            role="canonical_integer_page" if canonical else "fractional_gauge_page",
            material=material,
            print_channel=channel,
            vertices=page_vertices,
            quads=page_quads,
            metadata={
                "height": float(page["height"]),
                "status": status,
                "canonical": canonical,
                "gauge": page.get("gauge"),
                "band_width_mm": band_width,
                "page_thickness_mm": thickness,
            },
        )
        points = np.asarray(page["points"], dtype=float)
        bottom = points[int(np.argmin(points[:, 1]))]
        bottom_samples.append((float(bottom[0]), float(bottom[1])))
        page_widths.append(band_width)
        page_thicknesses.append(thickness)

    bottoms = np.asarray(bottom_samples, dtype=float)
    rail_width = max(
        spec.rail_min_width,
        float(np.ptp(bottoms[:, 0])) + max(page_widths) + 2.0 * spec.joint_overlap,
    )
    rail_depth = max(
        spec.rail_min_depth,
        float(np.ptp(bottoms[:, 1])) + max(page_widths) + 2.0 * spec.joint_overlap,
    )
    rail_center_x = float(np.mean(bottoms[:, 0]))
    rail_center_y = float(np.mean(bottoms[:, 1]))
    page_z = [float(page["z"]) for page in pages]
    rail_bottom_z = min(page_z) - 0.5 * max(page_thicknesses) - spec.joint_overlap
    rail_top_z = max(page_z) + 0.5 * max(page_thicknesses) + spec.joint_overlap
    rail_vertices, rail_quads = _box_mesh(
        center_x=rail_center_x,
        center_y=rail_center_y,
        width=rail_width,
        depth=rail_depth,
        bottom_z=rail_bottom_z,
        top_z=rail_top_z,
    )
    rail_part_index = builder.add_part(
        name="lower_page_rail",
        role="page_spine_and_structural_joint",
        material="spine_blue",
        print_channel="blue",
        vertices=rail_vertices,
        quads=rail_quads,
        metadata={
            "intentional_overlap_joint": True,
            "width_mm": rail_width,
            "depth_mm": rail_depth,
        },
    )

    builder.vertices = _rotate_and_place_upper_assembly(
        builder.vertices,
        tilt_degrees=spec.tilt_degrees,
        target_min_z=spec.base_height + spec.assembly_clearance,
    )
    upper_vertices = np.asarray(builder.vertices, dtype=float)
    upper_min = np.min(upper_vertices, axis=0)
    upper_max = np.max(upper_vertices, axis=0)
    upper_span = upper_max - upper_min

    rail_part = builder.parts[rail_part_index]
    rail_start = int(rail_part["vertex_start"])
    rail_stop = rail_start + int(rail_part["vertex_count"])
    placed_rail = upper_vertices[rail_start:rail_stop]
    rail_low_z = float(np.min(placed_rail[:, 2]))
    lowest = placed_rail[:, 2] <= rail_low_z + 1e-8
    anchor_x = float(np.mean(placed_rail[lowest, 0]))
    anchor_y = float(np.mean(placed_rail[lowest, 1]))

    base_bottom_width = max(spec.base_bottom_width, float(upper_span[0]) + 2 * spec.base_margin)
    base_bottom_depth = max(spec.base_bottom_depth, float(upper_span[1]) + 2 * spec.base_margin)
    base_top_width = base_bottom_width - 2.0 * spec.base_top_inset
    base_top_depth = base_bottom_depth - 2.0 * spec.base_top_inset
    base_vertices, base_quads = _frustum_mesh(
        center_x=0.0,
        center_y=0.0,
        bottom_width=base_bottom_width,
        bottom_depth=base_bottom_depth,
        top_width=base_top_width,
        top_depth=base_top_depth,
        bottom_z=0.0,
        top_z=spec.base_height,
    )
    builder.add_part(
        name="display_plinth",
        role="stable_flat_base",
        material="base_navy",
        print_channel="blue",
        vertices=base_vertices,
        quads=base_quads,
        metadata={
            "bottom_width_mm": base_bottom_width,
            "bottom_depth_mm": base_bottom_depth,
            "height_mm": spec.base_height,
        },
    )

    pedestal_top_z = rail_low_z + spec.joint_overlap
    pedestal_vertices, pedestal_quads = _frustum_mesh(
        center_x=anchor_x,
        center_y=anchor_y,
        bottom_width=spec.pedestal_bottom_width,
        bottom_depth=spec.pedestal_bottom_depth,
        top_width=spec.pedestal_top_width,
        top_depth=spec.pedestal_top_depth,
        bottom_z=spec.base_height - spec.joint_overlap,
        top_z=pedestal_top_z,
    )
    builder.add_part(
        name="book_pedestal",
        role="base_to_page_rail_joint",
        material="spine_blue",
        print_channel="blue",
        vertices=pedestal_vertices,
        quads=pedestal_quads,
        metadata={"intentional_overlap_joint": True},
    )

    # A vertical gold key on the front of the plinth echoes the fractional
    # pages and remains visible in both physical and rendered views.
    accent_center_y = -0.25 * (base_bottom_depth + base_top_depth)
    accent_vertices, accent_quads = _box_mesh(
        center_x=0.0,
        center_y=accent_center_y,
        width=spec.accent_width,
        depth=spec.accent_depth,
        bottom_z=0.5 * (spec.base_height - spec.accent_height),
        top_z=0.5 * (spec.base_height + spec.accent_height),
    )
    builder.add_part(
        name="fractional_gauge_accent",
        role="material_key_for_fractional_pages",
        material="gauge_gold",
        print_channel="gold",
        vertices=accent_vertices,
        quads=accent_quads,
        metadata={"intentional_overlap_joint": True},
    )

    all_vertices = np.asarray(builder.vertices, dtype=float)
    bounds_min = np.min(all_vertices, axis=0)
    bounds_max = np.max(all_vertices, axis=0)
    dimensions = bounds_max - bounds_min
    edge_audit = _edge_audit(builder.quads, builder.parts)
    area_audit = _face_area_audit(builder.vertices, builder.quads)

    return {
        "type": "fabrication_mesh",
        "family": "infinity_root:book_sculpture",
        "descriptor": "infinity_root",
        "schema_version": SCULPTURE_SCHEMA_VERSION,
        "units": "mm",
        "source_book_schema_version": book.get("schema_version"),
        "source_root_jet": book.get("root_jet"),
        "canonical_integer_heights": list(book.get("canonical_integer_heights", ())),
        "contains_gauge_views": bool(book.get("contains_gauge_views")),
        "claim_boundary": book.get("claim_boundary"),
        "fabrication_spec": asdict(spec),
        "vertices": builder.vertices,
        "quads": builder.quads,
        "parts": builder.parts,
        "native_topology": "quad_only_closed_component_shells",
        "joint_strategy": (
            "Closed component shells overlap volumetrically at the page rail, pedestal, "
            "base, and accent joints for slicer union."
        ),
        "bounds_mm": {
            "minimum": [float(value) for value in bounds_min],
            "maximum": [float(value) for value in bounds_max],
            "dimensions": [float(value) for value in dimensions],
        },
        "printability_audit": {
            "native_faces_all_quads": all(len(face) == 4 for face in builder.quads),
            "flat_base_at_z_zero": abs(float(bounds_min[2])) <= 1e-12,
            "minimum_declared_feature_mm": spec.minimum_feature,
            **edge_audit,
            **area_audit,
            "intersection_scope": (
                "Component shells are individually edge-manifold; volumetric joint "
                "intersections are intentionally delegated to slicer union."
            ),
        },
        "print_channels": {
            "blue": "canonical pages, structural rail, pedestal, and base",
            "gold": "fractional gauge pages and the base accent",
        },
    }


def _safe_obj_name(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    return cleaned or "part"


def infinity_root_sculpture_mtl() -> str:
    """Return the blue/gold material library used by the sculpture OBJ."""

    return """# AdaptiveCAD Infinity Root Book materials
newmtl canonical_blue
Ka 0.025 0.065 0.140
Kd 0.105 0.390 0.950
Ks 0.620 0.760 1.000
Ns 96.0
d 1.0
illum 2

newmtl gauge_gold
Ka 0.150 0.090 0.015
Kd 0.950 0.565 0.070
Ks 1.000 0.825 0.350
Ns 128.0
d 0.88
illum 2

newmtl spine_blue
Ka 0.018 0.045 0.090
Kd 0.055 0.175 0.430
Ks 0.270 0.430 0.720
Ns 72.0
d 1.0
illum 2

newmtl base_navy
Ka 0.012 0.022 0.045
Kd 0.030 0.080 0.180
Ks 0.180 0.310 0.520
Ns 64.0
d 1.0
illum 2
"""


def infinity_root_sculpture_obj(
    sculpture: Mapping[str, Any],
    *,
    material_filename: str = "infinity_root_sculpture.mtl",
) -> str:
    """Serialize the native colored sculpture as a quad-only OBJ."""

    if sculpture.get("family") != "infinity_root:book_sculpture":
        raise ValueError("expected an infinity_root:book_sculpture object")
    lines = [
        "# AdaptiveCAD Infinity Root Book desk sculpture",
        f"# schema: {sculpture.get('schema_version', SCULPTURE_SCHEMA_VERSION)}",
        "# units: millimetres",
        "# native faces: quads only",
        f"mtllib {_safe_obj_name(material_filename)}",
        "o Infinity_Root_Book_Sculpture",
    ]
    for vertex in sculpture["vertices"]:
        lines.append(
            f"v {float(vertex[0]):.12g} {float(vertex[1]):.12g} {float(vertex[2]):.12g}"
        )
    for part in sculpture["parts"]:
        lines.append(f"g {_safe_obj_name(part['name'])}")
        lines.append(f"usemtl {_safe_obj_name(part['material'])}")
        start = int(part["face_start"])
        stop = start + int(part["face_count"])
        for quad in sculpture["quads"][start:stop]:
            if len(quad) != 4:
                raise ValueError("native sculpture topology must contain only quads")
            lines.append("f " + " ".join(str(int(index) + 1) for index in quad))
    return "\n".join(lines) + "\n"


def infinity_root_sculpture_stl(
    sculpture: Mapping[str, Any],
    *,
    print_channels: Sequence[str] | None = None,
    solid_name: str = "infinity_root_book_sculpture",
) -> str:
    """Serialize a conventional ASCII STL, triangulating native quads on export."""

    if sculpture.get("family") != "infinity_root:book_sculpture":
        raise ValueError("expected an infinity_root:book_sculpture object")
    selected = None if print_channels is None else {str(channel) for channel in print_channels}
    if selected is not None and not selected:
        raise ValueError("print_channels must select at least one channel")
    points = np.asarray(sculpture["vertices"], dtype=float)
    triangles: list[tuple[int, int, int]] = []
    for part in sculpture["parts"]:
        if selected is not None and str(part["print_channel"]) not in selected:
            continue
        start = int(part["face_start"])
        stop = start + int(part["face_count"])
        for a, b, c, d in sculpture["quads"][start:stop]:
            triangles.extend(((int(a), int(b), int(c)), (int(a), int(c), int(d))))
    if not triangles:
        raise ValueError("the selected print channels contain no faces")

    lines = [f"solid {_safe_obj_name(solid_name)}"]
    for triangle in triangles:
        a, b, c = (points[index] for index in triangle)
        normal = np.cross(b - a, c - a)
        length = float(np.linalg.norm(normal))
        if length <= 1e-14:
            raise ValueError("cannot export a degenerate STL facet")
        normal /= length
        lines.append(f"  facet normal {normal[0]:.9g} {normal[1]:.9g} {normal[2]:.9g}")
        lines.append("    outer loop")
        for vertex in (a, b, c):
            lines.append(f"      vertex {vertex[0]:.9g} {vertex[1]:.9g} {vertex[2]:.9g}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {_safe_obj_name(solid_name)}")
    return "\n".join(lines) + "\n"


__all__ = [
    "SCULPTURE_SCHEMA_VERSION",
    "InfinityRootSculptureSpec",
    "make_infinity_root_sculpture",
    "infinity_root_sculpture_mtl",
    "infinity_root_sculpture_obj",
    "infinity_root_sculpture_stl",
]
