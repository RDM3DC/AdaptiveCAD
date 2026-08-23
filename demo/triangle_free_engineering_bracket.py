#!/usr/bin/env python3
"""Generate the triangle-free engineering-bracket benchmark bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptivecad.manufacturing import (
    AdditivePostSettings,
    EngineeringBracketSource,
    SubtractivePostSettings,
    plan_engineering_bracket_additive,
    plan_engineering_bracket_subtractive,
    postprocess_additive_gcode,
    postprocess_subtractive_gcode,
    verification_suite,
)


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_bundle(bundle_path: Path, included_paths: Sequence[Path]) -> None:
    resolved_bundle = bundle_path.resolve()
    paths = tuple(included_paths)
    if not paths:
        raise ValueError("benchmark bundle must contain at least one file")
    if any(path.resolve() == resolved_bundle for path in paths):
        raise ValueError("benchmark bundle cannot include itself")
    names = tuple(path.name for path in paths)
    if len(set(names)) != len(names):
        raise ValueError("benchmark bundle member names must be unique")

    temporary_path = bundle_path.with_name(f"{bundle_path.name}.part")
    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in paths:
                archive.write(path, arcname=path.name)
            checksums = "\n".join(
                f"{_sha256(path)}  {path.name}" for path in paths
            )
            archive.writestr("SHA256SUMS.txt", checksums + "\n")
        with zipfile.ZipFile(temporary_path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise RuntimeError(f"bundle CRC validation failed for {bad_member}")
            if set(archive.namelist()) != set(names) | {"SHA256SUMS.txt"}:
                raise RuntimeError("bundle member validation failed")
        os.replace(temporary_path, bundle_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _build_svg(source: EngineeringBracketSource) -> str:
    outer = source.outer
    cutout = source.cutout
    outer_x = outer.center[0] - outer.width_mm / 2.0
    outer_y = outer.center[1] - outer.height_mm / 2.0
    cutout_x = cutout.center[0] - cutout.width_mm / 2.0
    cutout_y = cutout.center[1] - cutout.height_mm / 2.0
    circles = "\n".join(
        (
            f'      <circle cx="{hole.center[0]:.6g}" cy="{hole.center[1]:.6g}" '
            f'r="{hole.radius_mm:.6g}"/>'
        )
        for hole in source.holes
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 820">
  <rect width="1200" height="820" fill="#07101f"/>
  <text x="64" y="72" fill="#f7f9ff" font-family="system-ui" font-size="34"
        font-weight="700">Triangle-Free Engineering Bracket</text>
  <text x="64" y="110" fill="#aebbd8" font-family="system-ui" font-size="18">
    One analytic Boolean source to additive layers and CNC finish contours
  </text>
  <g transform="translate(600 430) scale(9 -9)" fill="none"
     stroke="#3f9cff" stroke-width="0.55">
    <rect x="{outer_x:.6g}" y="{outer_y:.6g}" width="{outer.width_mm:.6g}"
          height="{outer.height_mm:.6g}" rx="{outer.radius_mm:.6g}"/>
    <rect x="{cutout_x:.6g}" y="{cutout_y:.6g}" width="{cutout.width_mm:.6g}"
          height="{cutout.height_mm:.6g}" rx="{cutout.radius_mm:.6g}"/>
{circles}
  </g>
  <text x="64" y="755" fill="#8fa0c4" font-family="monospace" font-size="17">
    {source.source_id} | no authoritative mesh | exact lines and circular arcs
  </text>
</svg>
"""


def generate(output_directory: Path) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    source = EngineeringBracketSource.default()
    additive = plan_engineering_bracket_additive(source)
    subtractive = plan_engineering_bracket_subtractive(source)
    additive_dict = additive.to_dict()
    subtractive_dict = subtractive.to_dict()
    contract_report = verification_suite(
        (
            ("engineering_bracket_additive_curve_job.json", additive_dict),
            ("engineering_bracket_subtractive_curve_job.json", subtractive_dict),
        )
    )
    if not contract_report["passed"]:
        raise RuntimeError("engineering bracket failed the triangle-free contract")

    printer_native, printer_native_audit = postprocess_additive_gcode(
        additive,
        AdditivePostSettings(
            curve_mode="native",
            work_offset_x_mm=150.0,
            work_offset_y_mm=100.0,
            retraction_feed_mm_min=1800.0,
        ),
    )
    printer_linear, printer_linear_audit = postprocess_additive_gcode(
        additive,
        AdditivePostSettings(
            curve_mode="linearized",
            work_offset_x_mm=150.0,
            work_offset_y_mm=100.0,
            chord_tolerance_mm=additive.tolerance_mm,
            retraction_feed_mm_min=1800.0,
        ),
    )
    cnc_native, cnc_native_audit = postprocess_subtractive_gcode(
        subtractive,
        SubtractivePostSettings(curve_mode="native"),
    )
    cnc_linear, cnc_linear_audit = postprocess_subtractive_gcode(
        subtractive,
        SubtractivePostSettings(
            curve_mode="linearized",
            chord_tolerance_mm=subtractive.tolerance_mm,
        ),
    )

    additive_stats = contract_report["job_audits"][0]["statistics"]
    subtractive_stats = contract_report["job_audits"][1]["statistics"]
    benchmark_report = {
        "kind": "adaptivecad_triangle_free_engineering_benchmark",
        "contract_gate_passed": True,
        "same_source_for_both_processes": contract_report["shared_source"]["passed"],
        "source": source.to_dict(),
        "additive_ir": additive_stats,
        "subtractive_ir": subtractive_stats,
        "postprocessors": {
            "printer_native": printer_native_audit,
            "printer_linearized": printer_linear_audit,
            "cnc_native": cnc_native_audit,
            "cnc_linearized": cnc_linear_audit,
        },
        "authoritative_route": {
            "representation": "analytic lines and circular arcs",
            "boolean_method": "analytic_regularized_difference_of_planar_primitives",
            "fillet_method": "exact_circular_arc",
            "triangle_mesh_input": False,
            "mesh_created": False,
            "scale_gate_factors": contract_report["scale_factors"],
        },
        "manufacturing_boundary": (
            "Reference postprocessor output only. Printer and CNC programs require "
            "target-machine review; CNC contains finish contours only."
        ),
        "claim_boundary": source.to_dict()["claim_boundary"],
    }

    files = {
        "engineering_bracket_source.json": source.to_dict(),
        "engineering_bracket_additive_curve_job.json": additive_dict,
        "engineering_bracket_subtractive_curve_job.json": subtractive_dict,
        "engineering_bracket_contract_report.json": contract_report,
        "engineering_bracket_benchmark_report.json": benchmark_report,
    }
    written: list[Path] = []
    for name, value in files.items():
        path = output_directory / name
        _write_json(path, value)
        written.append(path)

    text_files = {
        "engineering_bracket_printer_native_arcs.gcode": printer_native,
        "engineering_bracket_printer_linearized.gcode": printer_linear,
        "engineering_bracket_cnc_native_arcs.nc": cnc_native,
        "engineering_bracket_cnc_linearized.nc": cnc_linear,
        "engineering_bracket_preview.svg": _build_svg(source),
    }
    for name, value in text_files.items():
        path = output_directory / name
        _write_text(path, value)
        written.append(path)

    bundle = output_directory / "triangle_free_engineering_bracket.zip"
    _write_bundle(bundle, written)
    return {
        "source_id": source.source_id,
        "contract_gate_passed": True,
        "same_source_for_both_processes": True,
        "additive_layers": additive_stats["layer_count"],
        "additive_paths": additive_stats["path_count"],
        "additive_segments": additive_stats["segment_count"],
        "subtractive_passes": subtractive_stats["layer_count"],
        "subtractive_paths": subtractive_stats["path_count"],
        "subtractive_segments": subtractive_stats["segment_count"],
        "bundle": str(bundle),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("triangle_free_engineering_bracket_output"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = generate(args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
