#!/usr/bin/env python3
"""Generate an AdaptiveCAD Infinity Root Book preview.

The JSON file preserves the sampled root jet and page provenance.  The OBJ uses
quad faces only.  The SVG is a lightweight isometric preview that requires no
GUI or plotting dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptivecad.geometry.infinity_root import (
    FractionalGaugeSpec,
    compare_fractional_gauge_curvature,
    infinity_root_book_obj,
    make_exact_lift_tower,
    make_infinity_root_book,
)


def _svg_preview(book: dict) -> str:
    projected_pages: list[tuple[dict, list[tuple[float, float]]]] = []
    all_points: list[tuple[float, float]] = []
    for page in book["pages"]:
        projected = [(18.0 * x + 7.0 * z, -18.0 * y - 10.0 * z) for x, y, z in page["points"]]
        projected_pages.append((page, projected))
        all_points.extend(projected)

    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    margin = 40.0
    width = max_x - min_x + 2.0 * margin
    height = max_y - min_y + 2.0 * margin + 72.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {height:.3f}">',
        '<rect width="100%" height="100%" fill="#0b1020"/>',
        '<text x="24" y="32" fill="#f7f8fc" font-family="system-ui" '
        'font-size="20" font-weight="700">AdaptiveCAD Infinity Root Book</text>',
        '<text x="24" y="54" fill="#aeb8d4" font-family="system-ui" '
        'font-size="12">Solid blue: canonical integer level · dashed gold: gauge view</text>',
        f'<g transform="translate({margin - min_x:.3f},{margin + 72.0 - min_y:.3f})">',
    ]
    for page, points in reversed(projected_pages):
        encoded = " ".join(f"{x:.3f},{y:.3f}" for x, y in points + [points[0]])
        if page["canonical"]:
            color = "#65a9ff"
            dash = ""
            opacity = "0.76"
        else:
            color = "#ffc857"
            dash = ' stroke-dasharray="7 5"'
            opacity = "0.9"
        lines.append(
            f'<polyline points="{encoded}" fill="none" stroke="{color}" '
            f'stroke-width="2" opacity="{opacity}"{dash}/>'
        )
    lines.extend(["</g>", "</svg>"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--samples", type=int, default=181)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--residue", type=float, default=1.0)
    parser.add_argument("--gauge-power", type=float, default=0.0)
    parser.add_argument(
        "--integer-only",
        action="store_true",
        help="omit the explicitly gauged half-level visualization pages",
    )
    args = parser.parse_args()

    if args.samples < 3:
        parser.error("--samples must be at least 3")
    x = tuple(float(value) for value in np.geomspace(0.55, 1.8, args.samples))
    tower = make_exact_lift_tower(
        x,
        depth=args.depth,
        residue=args.residue,
        basepoint=1.0,
    )
    gauge = FractionalGaugeSpec.power_mean(args.gauge_power)
    fractional_pages = ()
    if not args.integer_only:
        fractional_pages = tuple((index + 0.5, gauge) for index in range(args.depth))

    book = make_infinity_root_book(
        tower,
        fractional_pages=fractional_pages,
        radius=10.0,
        page_gap=2.0,
        radial_gain=0.38,
    )
    if args.depth > 0:
        comparison_power = 1.0 if abs(args.gauge_power - 1.0) > 1e-12 else 0.0
        book["gauge_curvature_comparison"] = compare_fractional_gauge_curvature(
            tower,
            height=0.5,
            gauges=(gauge, FractionalGaugeSpec.power_mean(comparison_power)),
            radius=10.0,
            radial_gain=0.38,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "infinity_root_book.json"
    obj_path = args.output_dir / "infinity_root_book.obj"
    svg_path = args.output_dir / "infinity_root_book.svg"
    json_path.write_text(json.dumps(book, indent=2) + "\n", encoding="utf-8")
    obj_path.write_text(infinity_root_book_obj(book), encoding="utf-8")
    svg_path.write_text(_svg_preview(book), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {obj_path} ({len(book['quads'])} quad faces; no triangles)")
    print(f"Wrote {svg_path}")
    print(book["claim_boundary"])
    if "gauge_curvature_comparison" in book:
        comparison = book["gauge_curvature_comparison"]
        print(
            "Curvature invariants within tolerance: "
            + ", ".join(comparison["invariant_within_tolerance"])
        )
        print(
            "Gauge-dependent metrics in this comparison: "
            + ", ".join(comparison["gauge_dependent_within_test"])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
