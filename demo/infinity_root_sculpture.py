#!/usr/bin/env python3
"""Build the printable, two-color Infinity Root Book desk sculpture."""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptivecad.geometry.infinity_root import (
    FractionalGaugeSpec,
    make_exact_lift_tower,
    make_infinity_root_book,
)
from adaptivecad.geometry.infinity_root_sculpture import (
    InfinityRootSculptureSpec,
    infinity_root_sculpture_mtl,
    infinity_root_sculpture_obj,
    infinity_root_sculpture_stl,
    make_infinity_root_sculpture,
)


def _shade_color(color: tuple[float, float, float], amount: float) -> tuple[float, ...]:
    return tuple(min(1.0, max(0.0, channel * amount)) for channel in color)


def _render_preview(sculpture: dict, output_path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptivecad-matplotlib")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    colors = {
        "canonical_blue": (0.10, 0.39, 0.98),
        "gauge_gold": (1.00, 0.59, 0.08),
        "spine_blue": (0.065, 0.23, 0.56),
        "base_navy": (0.045, 0.13, 0.29),
    }
    alpha = {"gauge_gold": 0.88}
    vertices = np.asarray(sculpture["vertices"], dtype=float)
    light = np.asarray((-0.35, -0.45, 0.82), dtype=float)
    light /= np.linalg.norm(light)

    figure = plt.figure(figsize=(12.8, 9.2), dpi=150, facecolor="#07101f")
    axis = figure.add_subplot(111, projection="3d", facecolor="#07101f")

    bounds = sculpture["bounds_mm"]
    minimum = np.asarray(bounds["minimum"], dtype=float)
    maximum = np.asarray(bounds["maximum"], dtype=float)
    dimensions = maximum - minimum
    floor_pad = 7.0
    floor = [
        [minimum[0] - floor_pad, minimum[1] - floor_pad, -0.15],
        [maximum[0] + floor_pad, minimum[1] - floor_pad, -0.15],
        [maximum[0] + floor_pad, maximum[1] + floor_pad, -0.15],
        [minimum[0] - floor_pad, maximum[1] + floor_pad, -0.15],
    ]
    axis.add_collection3d(
        Poly3DCollection([floor], facecolors="#0d1930", edgecolors="none", alpha=0.86)
    )

    for part in sculpture["parts"]:
        start = int(part["face_start"])
        stop = start + int(part["face_count"])
        polygons = [vertices[np.asarray(face, dtype=int)] for face in sculpture["quads"][start:stop]]
        base_color = colors[str(part["material"])]
        face_colors = []
        for polygon in polygons:
            normal = np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0])
            normal_length = float(np.linalg.norm(normal))
            if normal_length > 1e-14:
                normal /= normal_length
            illumination = 0.58 + 0.42 * max(0.0, float(np.dot(normal, light)))
            shaded = _shade_color(base_color, illumination)
            face_colors.append((*shaded, alpha.get(str(part["material"]), 1.0)))
        collection = Poly3DCollection(
            polygons,
            facecolors=face_colors,
            edgecolors=(0.015, 0.035, 0.075, 0.25),
            linewidths=0.12,
        )
        collection.set_zsort("average")
        axis.add_collection3d(collection)

    pad = 5.0
    axis.set_xlim(minimum[0] - pad, maximum[0] + pad)
    axis.set_ylim(minimum[1] - pad, maximum[1] + pad)
    axis.set_zlim(-0.5, maximum[2] + pad)
    axis.set_box_aspect((dimensions[0], dimensions[1], dimensions[2]))
    axis.view_init(elev=22.0, azim=-52.0)
    axis.set_axis_off()
    axis.grid(False)

    figure.text(
        0.055,
        0.935,
        "INFINITY ROOT BOOK",
        color="#f7f9ff",
        fontsize=25,
        fontweight="bold",
        family="DejaVu Sans",
    )
    figure.text(
        0.057,
        0.898,
        "A printable AdaptiveCAD desk sculpture",
        color="#aebbd8",
        fontsize=12.5,
        family="DejaVu Sans",
    )
    legend = figure.legend(
        handles=[
            Patch(facecolor=colors["canonical_blue"], label="Canonical integer pages"),
            Patch(facecolor=colors["gauge_gold"], label="Fractional gauge views"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.946, 0.938),
        frameon=False,
        ncol=1,
        fontsize=10.5,
    )
    for item in legend.get_texts():
        item.set_color("#dce5fb")
    figure.text(
        0.057,
        0.042,
        (
            f"{dimensions[0]:.0f} × {dimensions[1]:.0f} × {dimensions[2]:.0f} mm  ·  "
            f"quad-native geometry  ·  two aligned print channels"
        ),
        color="#8fa0c4",
        fontsize=10.5,
        family="DejaVu Sans",
    )
    figure.subplots_adjust(left=0.0, right=1.0, bottom=0.055, top=0.89)
    figure.savefig(output_path, facecolor=figure.get_facecolor(), bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)


def _print_notes(sculpture: dict) -> str:
    dimensions = sculpture["bounds_mm"]["dimensions"]
    audit = sculpture["printability_audit"]
    return f"""ADAPTIVECAD INFINITY ROOT BOOK — PRINT PACKAGE

Meaning
  Blue solids: canonical integer Infinity-Root levels.
  Gold solids: explicitly declared fractional gauge views.
  The gold pages are visualizations, not coordinate-free fractional iterates.

Files
  infinity_root_sculpture_quad.obj + .mtl
      Native colored model. Every source face is a quad.
  infinity_root_sculpture_slicer.stl
      Single-color compatibility export; STL triangulates the native quads.
  infinity_root_sculpture_blue.stl / infinity_root_sculpture_gold.stl
      Aligned two-material exports for a toolchanger or multicolor slicer.
  infinity_root_sculpture.json
      Root-jet provenance, page status, fabrication settings, and mesh audit.

Finished size
  {dimensions[0]:.2f} × {dimensions[1]:.2f} × {dimensions[2]:.2f} mm

Suggested FDM setup
  Orientation: use the supplied flat base at Z=0.
  Layer height: 0.20 mm.
  Nozzle: 0.40 mm.
  Walls: 3 or 4.
  Infill: 15–20% gyroid or cubic.
  Supports: build-plate-only if your material needs them; the pages are near vertical.
  For two colors, load both aligned channel STLs without moving either origin.

Mesh audit
  Native faces all quads: {audit['native_faces_all_quads']}
  Closed edge-manifold component shells: {audit['all_component_shells_closed_edge_manifold']}
  Degenerate quads: {audit['degenerate_quad_count']}
  Minimum declared feature: {audit['minimum_declared_feature_mm']:.2f} mm

The closed shells overlap at structural joints. Normal slicer union/repair should be enabled.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--samples", type=int, default=121)
    parser.add_argument("--tilt", type=float, default=80.0)
    parser.add_argument("--gauge-power", type=float, default=0.0)
    args = parser.parse_args()
    if args.samples < 16:
        parser.error("--samples must be at least 16 for fabrication geometry")

    x = tuple(float(value) for value in np.geomspace(0.55, 1.8, args.samples))
    tower = make_exact_lift_tower(x, depth=3, residue=1.0, basepoint=1.0)
    gauge = FractionalGaugeSpec.power_mean(args.gauge_power)
    book = make_infinity_root_book(
        tower,
        fractional_pages=tuple((index + 0.5, gauge) for index in range(3)),
        radius=38.0,
        page_gap=4.8,
        radial_gain=0.30,
    )
    sculpture = make_infinity_root_sculpture(
        book,
        spec=InfinityRootSculptureSpec(tilt_degrees=args.tilt),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": args.output_dir / "infinity_root_sculpture.json",
        "obj": args.output_dir / "infinity_root_sculpture_quad.obj",
        "mtl": args.output_dir / "infinity_root_sculpture.mtl",
        "stl": args.output_dir / "infinity_root_sculpture_slicer.stl",
        "blue": args.output_dir / "infinity_root_sculpture_blue.stl",
        "gold": args.output_dir / "infinity_root_sculpture_gold.stl",
        "preview": args.output_dir / "infinity_root_sculpture_preview.png",
        "notes": args.output_dir / "README_PRINT.txt",
        "bundle": args.output_dir / "infinity_root_sculpture_print_package.zip",
    }
    paths["json"].write_text(json.dumps(sculpture, indent=2) + "\n", encoding="utf-8")
    paths["obj"].write_text(
        infinity_root_sculpture_obj(sculpture, material_filename=paths["mtl"].name),
        encoding="utf-8",
    )
    paths["mtl"].write_text(infinity_root_sculpture_mtl(), encoding="utf-8")
    paths["stl"].write_text(infinity_root_sculpture_stl(sculpture), encoding="utf-8")
    paths["blue"].write_text(
        infinity_root_sculpture_stl(
            sculpture,
            print_channels=("blue",),
            solid_name="infinity_root_blue",
        ),
        encoding="utf-8",
    )
    paths["gold"].write_text(
        infinity_root_sculpture_stl(
            sculpture,
            print_channels=("gold",),
            solid_name="infinity_root_gold",
        ),
        encoding="utf-8",
    )
    paths["notes"].write_text(_print_notes(sculpture), encoding="utf-8")
    _render_preview(sculpture, paths["preview"])

    with zipfile.ZipFile(paths["bundle"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in ("json", "obj", "mtl", "stl", "blue", "gold", "preview", "notes"):
            archive.write(paths[key], arcname=paths[key].name)

    dimensions = sculpture["bounds_mm"]["dimensions"]
    audit = sculpture["printability_audit"]
    print(f"Wrote {paths['bundle']}")
    print(f"Size: {dimensions[0]:.2f} x {dimensions[1]:.2f} x {dimensions[2]:.2f} mm")
    print(f"Native quads: {len(sculpture['quads'])}; vertices: {len(sculpture['vertices'])}")
    print(f"Closed component shells: {audit['all_component_shells_closed_edge_manifold']}")
    print(f"Degenerate quads: {audit['degenerate_quad_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
