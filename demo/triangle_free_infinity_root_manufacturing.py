#!/usr/bin/env python3
"""Generate printer and CNC jobs from one triangle-free Infinity Root loft."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptivecad.geometry.infinity_root import FractionalGaugeSpec, make_exact_lift_tower
from adaptivecad.manufacturing import (
    AdditivePlanSettings,
    AdditivePostSettings,
    InfinityRootLoftSource,
    SubtractivePlanSettings,
    SubtractivePostSettings,
    audit_triangle_free_job,
    plan_additive_loft,
    plan_subtractive_waterlines,
    postprocess_additive_gcode,
    postprocess_subtractive_gcode,
)


def _sample_path(path, samples_per_segment: int = 5) -> np.ndarray:
    points = []
    for segment in path.segments:
        for index in range(samples_per_segment):
            points.append(segment.evaluate(index / samples_per_segment))
    points.append(path.segments[-1].end)
    return np.asarray(points, dtype=float)


def _svg_curve_path(path, project) -> str:
    start = project(path.segments[0].start)
    commands = [f"M {start[0]:.4f} {start[1]:.4f}"]
    for segment in path.segments:
        p1 = project(segment.p1)
        p2 = project(segment.p2)
        p3 = project(segment.p3)
        commands.append(
            f"C {p1[0]:.4f} {p1[1]:.4f} {p2[0]:.4f} {p2[1]:.4f} "
            f"{p3[0]:.4f} {p3[1]:.4f}"
        )
    commands.append("Z")
    return " ".join(commands)


def _write_curve_svg(source: InfinityRootLoftSource, output_path: Path) -> None:
    rendered: list[tuple[dict, str, str]] = []
    all_points = []
    for record in source.page_records:
        z = float(record["physical_z_mm"])
        outer = source.path_at(
            z,
            radial_offset_mm=source.half_band_width,
            role="preview_outer",
        )

        def project(point, layer_z=z):
            return (point[0] + 0.62 * layer_z, -0.62 * point[1] - 0.78 * layer_z)

        path_data = _svg_curve_path(outer, project)
        sampled = _sample_path(outer)
        projected = np.column_stack(
            (sampled[:, 0] + 0.62 * z, -0.62 * sampled[:, 1] - 0.78 * z)
        )
        all_points.extend(tuple(point) for point in projected)
        color = "#2780ff" if record["canonical"] else "#ffad21"
        rendered.append((dict(record), color, path_data))

    array = np.asarray(all_points, dtype=float)
    minimum = np.min(array, axis=0)
    maximum = np.max(array, axis=0)
    margin = 34.0
    header = 74.0
    width = float(maximum[0] - minimum[0] + 2.0 * margin)
    height = float(maximum[1] - minimum[1] + 2.0 * margin + header)
    translate_x = margin - float(minimum[0])
    translate_y = margin + header - float(minimum[1])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {height:.3f}">',
        '<rect width="100%" height="100%" fill="#07101f"/>',
        '<text x="24" y="31" fill="#f7f9ff" font-family="system-ui" '
        'font-size="21" font-weight="700">Triangle-Free Infinity Root Manufacturing</text>',
        '<text x="24" y="53" fill="#aebbd8" font-family="system-ui" '
        'font-size="12">One periodic Bézier loft → printer layers + CNC waterlines</text>',
        f'<g transform="translate({translate_x:.4f},{translate_y:.4f})">',
    ]
    for record, color, path_data in reversed(rendered):
        dash = "" if record["canonical"] else ' stroke-dasharray="6 4"'
        lines.append(
            f'<path d="{path_data}" fill="none" stroke="{color}" stroke-width="1.8" '
            f'opacity="0.92"{dash}/>'
        )
    lines.extend(["</g>", "</svg>"])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_preview(source: InfinityRootLoftSource, output_path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptivecad-matplotlib")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    figure = plt.figure(figsize=(12.8, 9.2), dpi=150, facecolor="#07101f")
    axis = figure.add_subplot(111, projection="3d", facecolor="#07101f")

    # Thin fabrication cross-sections make the continuous loft visible without
    # introducing a display mesh into the manufacturing route.
    intermediate_z = np.linspace(source.z_min, source.z_max, 21)
    for z in intermediate_z:
        path = source.path_at(
            float(z),
            radial_offset_mm=source.half_band_width,
            role="preview_fabrication_section",
        )
        points = _sample_path(path, samples_per_segment=3)
        axis.plot(
            points[:, 0],
            points[:, 1],
            np.full(points.shape[0], z),
            color="#355d9e",
            linewidth=0.65,
            alpha=0.28,
        )

    for record in source.page_records:
        z = float(record["physical_z_mm"])
        color = "#2780ff" if record["canonical"] else "#ffad21"
        for offset, width, alpha in (
            (source.half_band_width, 2.1, 0.98),
            (-source.half_band_width, 1.0, 0.64),
        ):
            path = source.path_at(z, radial_offset_mm=offset, role="preview_declared_page")
            points = _sample_path(path, samples_per_segment=4)
            axis.plot(
                points[:, 0],
                points[:, 1],
                np.full(points.shape[0], z),
                color=color,
                linewidth=width,
                alpha=alpha,
                linestyle="-" if record["canonical"] else "--",
            )

    radii = np.asarray(source.page_radii, dtype=float)
    radius_max = float(np.max(radii) + source.half_band_width)
    axis.set_xlim(-radius_max, radius_max)
    axis.set_ylim(-radius_max, radius_max)
    axis.set_zlim(source.z_min, source.z_max + 2.0)
    axis.set_box_aspect((2.0 * radius_max, 2.0 * radius_max, 0.95 * radius_max))
    axis.view_init(elev=26.0, azim=-52.0)
    axis.set_axis_off()
    axis.grid(False)

    figure.text(
        0.055,
        0.935,
        "TRIANGLE-FREE FULL STACK",
        color="#f7f9ff",
        fontsize=25,
        fontweight="bold",
    )
    figure.text(
        0.057,
        0.898,
        "One Infinity Root curve source → additive layers + CNC waterlines",
        color="#aebbd8",
        fontsize=12.5,
    )
    legend = figure.legend(
        handles=[
            Patch(facecolor="#2780ff", label="Canonical root pages"),
            Patch(facecolor="#ffad21", label="Fractional gauge pages"),
            Patch(facecolor="#355d9e", label="Physical loft sections"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.946, 0.94),
        frameon=False,
        fontsize=10.5,
    )
    for item in legend.get_texts():
        item.set_color("#dce5fb")
    figure.text(
        0.057,
        0.042,
        "No STL · no OBJ · no surface facets · curve IR remains authoritative",
        color="#8fa0c4",
        fontsize=10.5,
    )
    figure.subplots_adjust(left=0.0, right=1.0, bottom=0.055, top=0.89)
    figure.savefig(
        output_path,
        facecolor=figure.get_facecolor(),
        bbox_inches="tight",
        pad_inches=0.08,
    )
    plt.close(figure)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_bundle(bundle_path: Path, included_paths: tuple[Path, ...]) -> None:
    """Write and validate the benchmark archive before replacing the final file."""

    resolved_bundle = bundle_path.resolve()
    if not included_paths:
        raise ValueError("benchmark bundle must contain at least one file")
    if any(path.resolve() == resolved_bundle for path in included_paths):
        raise ValueError("benchmark bundle cannot include itself")
    names = tuple(path.name for path in included_paths)
    if len(set(names)) != len(names):
        raise ValueError("benchmark bundle member names must be unique")

    temporary_path = bundle_path.with_name(f"{bundle_path.name}.part")
    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in included_paths:
                archive.write(path, arcname=path.name)
            checksums = "\n".join(
                f"{_sha256(path)}  {path.name}" for path in included_paths
            )
            archive.writestr("SHA256SUMS.txt", checksums + "\n")

        with zipfile.ZipFile(temporary_path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise RuntimeError(f"bundle CRC validation failed for {bad_member}")
            expected_names = set(names) | {"SHA256SUMS.txt"}
            if set(archive.namelist()) != expected_names:
                raise RuntimeError("bundle member validation failed")
        os.replace(temporary_path, bundle_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _normal_offset_audit(job) -> dict:
    paths = [
        path
        for layer in job.layers
        for path in layer.paths
        if "normal_offset_method" in path.metadata
    ]
    subdivisions: dict[str, int] = {}
    for path in paths:
        key = str(path.metadata["normal_offset_subdivisions_per_input_span"])
        subdivisions[key] = subdivisions.get(key, 0) + 1
    return {
        "path_count": len(paths),
        "method": (
            paths[0].metadata["normal_offset_method"] if paths else None
        ),
        "maximum_validation_error_mm": max(
            (
                float(path.metadata["normal_offset_max_validation_error_mm"])
                for path in paths
            ),
            default=0.0,
        ),
        "all_within_recorded_tolerance": all(
            float(path.metadata["normal_offset_max_validation_error_mm"])
            <= float(path.metadata["normal_offset_fit_tolerance_mm"])
            for path in paths
        ),
        "subdivisions_per_input_span_histogram": subdivisions,
        "surface_mesh_generated": False,
    }


def _readme(source, additive_job, subtractive_job, report) -> str:
    offset_fits = report["normal_offset_fits"]
    additive_offset_error = offset_fits["additive_perimeters"][
        "maximum_validation_error_mm"
    ]
    cnc_offset_error = offset_fits["subtractive_tool_centers"][
        "maximum_validation_error_mm"
    ]
    return f"""ADAPTIVECAD DIRECT MANUFACTURING — INFINITY ROOT BENCHMARK

This package is generated from one periodic cubic-Bézier Infinity Root loft.
No STL, OBJ, surface facet, or triangle entity enters the authoritative route.

Source
  ID: {source.source_id}
  Height: {source.z_max - source.z_min:.2f} mm
  Band width: {source.band_width_mm:.2f} mm
  Declared root pages: {len(source.page_records)}
  Bézier spans per closed loop: {len(source.angles)}

Additive job
  Layers: {len(additive_job.layers)}
  Native file: infinity_root_printer_native_g5.gcode
  Compatibility file: infinity_root_printer_linearized.gcode

Subtractive job
  Finish waterlines: {len(subtractive_job.layers)}
  Native file: infinity_root_cnc_native_g5.nc
  Compatibility file: infinity_root_cnc_linearized.nc

Important controller boundary
  Native files use the common XY cubic G5 convention documented in their headers.
  Confirm that exact G5 dialect on the target printer or CNC before execution.
  Linearized files use tolerance-controlled G1 motion but still never construct
  triangles or a surface mesh.

Important machining boundary
  The CNC program contains compensated finish waterlines only. A machinist must
  define stock, roughing, workholding, tool length, work offset, and collision
  clearance before running it.

Audit
  Additive IR triangle-free: {report['additive_ir']['authoritative_ir_triangle_free']}
  Subtractive IR triangle-free: {report['subtractive_ir']['authoritative_ir_triangle_free']}
  Source IDs match: {additive_job.source_id == subtractive_job.source_id}
  Additive normal-offset max validation error: {additive_offset_error:.6f} mm
  CNC normal-offset max validation error: {cnc_offset_error:.6f} mm
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--samples", type=int, default=33)
    parser.add_argument("--layer-height", type=float, default=0.4)
    parser.add_argument("--step-down", type=float, default=2.0)
    parser.add_argument("--gauge-power", type=float, default=0.0)
    args = parser.parse_args()
    if args.samples < 9:
        parser.error("--samples must be at least 9")

    x = tuple(float(value) for value in np.geomspace(0.55, 1.8, args.samples))
    tower = make_exact_lift_tower(x, depth=3, residue=1.0, basepoint=1.0)
    gauge = FractionalGaugeSpec.power_mean(args.gauge_power)
    source = InfinityRootLoftSource.from_tower(
        tower,
        fractional_pages=tuple((index + 0.5, gauge) for index in range(3)),
        radius_mm=38.0,
        page_gap_mm=8.0,
        radial_gain=0.30,
        band_width_mm=8.0,
    )
    additive_job = plan_additive_loft(
        source,
        AdditivePlanSettings(layer_height_mm=args.layer_height),
    )
    subtractive_job = plan_subtractive_waterlines(
        source,
        SubtractivePlanSettings(step_down_mm=args.step_down),
    )
    additive_audit = audit_triangle_free_job(additive_job)
    subtractive_audit = audit_triangle_free_job(subtractive_job)
    printer_native, printer_native_audit = postprocess_additive_gcode(
        additive_job,
        AdditivePostSettings(curve_mode="native"),
    )
    printer_linear, printer_linear_audit = postprocess_additive_gcode(
        additive_job,
        AdditivePostSettings(curve_mode="linearized"),
    )
    cnc_native, cnc_native_audit = postprocess_subtractive_gcode(
        subtractive_job,
        SubtractivePostSettings(curve_mode="native"),
    )
    cnc_linear, cnc_linear_audit = postprocess_subtractive_gcode(
        subtractive_job,
        SubtractivePostSettings(curve_mode="linearized"),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "additive_job": args.output_dir / "infinity_root_additive_curve_job.json",
        "subtractive_job": args.output_dir / "infinity_root_subtractive_curve_job.json",
        "printer_native": args.output_dir / "infinity_root_printer_native_g5.gcode",
        "printer_linear": args.output_dir / "infinity_root_printer_linearized.gcode",
        "cnc_native": args.output_dir / "infinity_root_cnc_native_g5.nc",
        "cnc_linear": args.output_dir / "infinity_root_cnc_linearized.nc",
        "report": args.output_dir / "triangle_free_manufacturing_report.json",
        "svg": args.output_dir / "triangle_free_full_stack.svg",
        "preview": args.output_dir / "triangle_free_full_stack_preview.png",
        "readme": args.output_dir / "README_TRIANGLE_FREE.txt",
        "bundle": args.output_dir / "triangle_free_infinity_root_full_stack.zip",
    }
    paths["additive_job"].write_text(
        json.dumps(additive_job.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    paths["subtractive_job"].write_text(
        json.dumps(subtractive_job.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    paths["printer_native"].write_text(printer_native, encoding="utf-8")
    paths["printer_linear"].write_text(printer_linear, encoding="utf-8")
    paths["cnc_native"].write_text(cnc_native, encoding="utf-8")
    paths["cnc_linear"].write_text(cnc_linear, encoding="utf-8")
    _write_curve_svg(source, paths["svg"])
    _render_preview(source, paths["preview"])

    report = {
        "kind": "adaptivecad_triangle_free_manufacturing_benchmark",
        "source": source.provenance(),
        "same_source_for_both_processes": additive_job.source_id == subtractive_job.source_id,
        "additive_ir": additive_audit,
        "subtractive_ir": subtractive_audit,
        "postprocessors": {
            "printer_native": printer_native_audit,
            "printer_linearized": printer_linear_audit,
            "cnc_native": cnc_native_audit,
            "cnc_linearized": cnc_linear_audit,
        },
        "normal_offset_fits": {
            "additive_perimeters": _normal_offset_audit(additive_job),
            "subtractive_tool_centers": _normal_offset_audit(subtractive_job),
        },
        "primary_route_excluded_formats": ["STL", "OBJ", "triangle_mesh"],
        "claim_boundary": (
            "The curve route is triangle-free. Numerical curve evaluation and optional "
            "G1 controller compatibility remain tolerance-bounded approximations."
        ),
    }
    paths["report"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    paths["readme"].write_text(
        _readme(source, additive_job, subtractive_job, report), encoding="utf-8"
    )

    archive_keys = (
        "additive_job",
        "subtractive_job",
        "printer_native",
        "printer_linear",
        "cnc_native",
        "cnc_linear",
        "report",
        "svg",
        "preview",
        "readme",
    )
    _write_bundle(paths["bundle"], tuple(paths[key] for key in archive_keys))

    print(f"Wrote {paths['bundle']}")
    print(f"Source: {source.source_id}")
    print(
        f"Additive: {len(additive_job.layers)} layers, "
        f"{additive_audit['curve_kind_counts']['cubic_bezier']} cubic curves"
    )
    print(
        f"Subtractive: {len(subtractive_job.layers)} waterlines, "
        f"{subtractive_audit['curve_kind_counts']['cubic_bezier']} cubic curves"
    )
    print(f"Printer native motion: {printer_native_audit['motion_counts']}")
    print(f"CNC native motion: {cnc_native_audit['motion_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
