from __future__ import annotations

"""Reliability stress harnesses for AdaptiveCAD.

This module turns the three highest-value engine checks into executable code:

1. Boolean nightmare: OCC-backed union, cut, and intersection using adaptive-pi
   generated solids.
2. STEP round-trip: export a history-derived adaptive-pi solid to STEP and read it
   back into OCC for validity inspection.
3. Performance wall: benchmark the CPU SDF fold against scenes containing up to
   5,000 distinct adaptive-pi-driven features.

The OCC-backed checks remain optional and raise a clear RuntimeError when the
kernel is unavailable. The performance wall benchmark is pure Python and can run
in the default test environment.
"""

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Sequence

import numpy as np

from adaptivecad.aacore.sdf import KIND_PI_BLOOM, Prim, Scene
from adaptivecad.geometry import polar_pi_circle_points

__all__ = [
    "BooleanStressResult",
    "PerformanceSample",
    "ShapeCheckResult",
    "StepRoundTripResult",
    "benchmark_feature_scaling",
    "build_pi_bloom_scene",
    "generate_crucible_report",
    "has_occ",
    "run_boolean_nightmare_test",
    "run_step_round_trip_test",
]


@dataclass(frozen=True)
class ShapeCheckResult:
    valid: bool
    solids: int
    shells: int
    faces: int
    edges: int
    volume: float


@dataclass(frozen=True)
class BooleanStressResult:
    operation: str
    duration_sec: float
    metrics: ShapeCheckResult


@dataclass(frozen=True)
class StepRoundTripResult:
    path: str
    write_ok: bool
    read_ok: bool
    duration_sec: float
    original: ShapeCheckResult
    imported: ShapeCheckResult
    relative_volume_delta: float


@dataclass(frozen=True)
class PerformanceSample:
    feature_count: int
    sample_count: int
    build_seconds: float
    eval_seconds: float
    samples_per_second: float
    mean_distance: float
    min_distance: float
    max_distance: float


def has_occ() -> bool:
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse  # type: ignore
    except Exception:
        return False
    return BRepAlgoAPI_Fuse is not None


def _require_occ() -> dict[str, Any]:
    try:
        from OCC.Core.BRepAlgoAPI import (  # type: ignore
            BRepAlgoAPI_Common,
            BRepAlgoAPI_Cut,
            BRepAlgoAPI_Fuse,
        )
        from OCC.Core.BRepBuilderAPI import (  # type: ignore
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_MakeWire,
        )
        from OCC.Core.BRepCheck import BRepCheck_Analyzer  # type: ignore
        from OCC.Core.BRepGProp import brepgprop  # type: ignore
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism  # type: ignore
        from OCC.Core.GProp import GProp_GProps  # type: ignore
        from OCC.Core.IFSelect import IFSelect_RetDone  # type: ignore
        from OCC.Core.STEPControl import (  # type: ignore
            STEPControl_AsIs,
            STEPControl_Reader,
            STEPControl_Writer,
        )
        from OCC.Core.TopAbs import (  # type: ignore
            TopAbs_EDGE,
            TopAbs_FACE,
            TopAbs_SHELL,
            TopAbs_SOLID,
        )
        from OCC.Core.TopExp import TopExp_Explorer  # type: ignore
        from OCC.Core.gp import gp_Pnt, gp_Vec  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pythonocc-core is required for boolean and STEP crucible checks"
        ) from exc

    return {
        "BRepAlgoAPI_Common": BRepAlgoAPI_Common,
        "BRepAlgoAPI_Cut": BRepAlgoAPI_Cut,
        "BRepAlgoAPI_Fuse": BRepAlgoAPI_Fuse,
        "BRepBuilderAPI_MakeEdge": BRepBuilderAPI_MakeEdge,
        "BRepBuilderAPI_MakeFace": BRepBuilderAPI_MakeFace,
        "BRepBuilderAPI_MakeWire": BRepBuilderAPI_MakeWire,
        "BRepCheck_Analyzer": BRepCheck_Analyzer,
        "brepgprop": brepgprop,
        "BRepPrimAPI_MakePrism": BRepPrimAPI_MakePrism,
        "GProp_GProps": GProp_GProps,
        "IFSelect_RetDone": IFSelect_RetDone,
        "STEPControl_AsIs": STEPControl_AsIs,
        "STEPControl_Reader": STEPControl_Reader,
        "STEPControl_Writer": STEPControl_Writer,
        "TopAbs_EDGE": TopAbs_EDGE,
        "TopAbs_FACE": TopAbs_FACE,
        "TopAbs_SHELL": TopAbs_SHELL,
        "TopAbs_SOLID": TopAbs_SOLID,
        "TopExp_Explorer": TopExp_Explorer,
        "gp_Pnt": gp_Pnt,
        "gp_Vec": gp_Vec,
    }


def _count_subshapes(shape: Any, shape_kind: Any, explorer_type: Any) -> int:
    explorer = explorer_type(shape, shape_kind)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _shape_metrics(shape: Any) -> ShapeCheckResult:
    occ = _require_occ()
    analyzer = occ["BRepCheck_Analyzer"](shape)
    props = occ["GProp_GProps"]()
    volume = 0.0
    try:
        occ["brepgprop"].VolumeProperties(shape, props)
        volume = float(props.Mass())
    except Exception:
        volume = 0.0

    return ShapeCheckResult(
        valid=bool(analyzer.IsValid()),
        solids=_count_subshapes(shape, occ["TopAbs_SOLID"], occ["TopExp_Explorer"]),
        shells=_count_subshapes(shape, occ["TopAbs_SHELL"], occ["TopExp_Explorer"]),
        faces=_count_subshapes(shape, occ["TopAbs_FACE"], occ["TopExp_Explorer"]),
        edges=_count_subshapes(shape, occ["TopAbs_EDGE"], occ["TopExp_Explorer"]),
        volume=volume,
    )


def _build_occ_polar_pi_prism(
    *,
    radius: float,
    height: float,
    center: Sequence[float] = (0.0, 0.0, 0.0),
    kappa: float = 0.35,
    angular_amplitude: float = 0.22,
    angular_frequency: int = 5,
    phase: float = 0.0,
    segments: int = 180,
) -> Any:
    occ = _require_occ()
    cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    pts = polar_pi_circle_points(
        radius=radius,
        cx=cx,
        cy=cy,
        segments=segments,
        kappa=kappa,
        scale=radius,
        angular_amplitude=angular_amplitude,
        angular_frequency=angular_frequency,
        phase=phase,
    )

    wire_builder = occ["BRepBuilderAPI_MakeWire"]()
    for index, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(index + 1) % len(pts)]
        edge = occ["BRepBuilderAPI_MakeEdge"](
            occ["gp_Pnt"](float(x0), float(y0), cz),
            occ["gp_Pnt"](float(x1), float(y1), cz),
        ).Edge()
        wire_builder.Add(edge)
    if not wire_builder.IsDone():
        raise RuntimeError("Failed to build adaptive-pi wire")

    face_builder = occ["BRepBuilderAPI_MakeFace"](wire_builder.Wire())
    if not face_builder.IsDone():
        raise RuntimeError("Failed to build adaptive-pi face")

    return occ["BRepPrimAPI_MakePrism"](
        face_builder.Face(), occ["gp_Vec"](0.0, 0.0, float(height))
    ).Shape()


def _make_boolean_operands() -> tuple[Any, Any]:
    left = _build_occ_polar_pi_prism(
        radius=11.5,
        height=14.0,
        center=(0.0, 0.0, -1.5),
        kappa=0.42,
        angular_amplitude=0.24,
        angular_frequency=5,
        phase=0.0,
        segments=200,
    )
    right = _build_occ_polar_pi_prism(
        radius=10.0,
        height=16.0,
        center=(5.5, -2.0, -0.5),
        kappa=0.31,
        angular_amplitude=0.18,
        angular_frequency=4,
        phase=0.85,
        segments=180,
    )
    return left, right


def _make_step_history_shape() -> Any:
    occ = _require_occ()
    base, overlay = _make_boolean_operands()
    cutter = _build_occ_polar_pi_prism(
        radius=4.25,
        height=20.0,
        center=(1.25, 1.0, -3.0),
        kappa=0.24,
        angular_amplitude=0.12,
        angular_frequency=6,
        phase=1.35,
        segments=140,
    )

    fused = occ["BRepAlgoAPI_Fuse"](base, overlay).Shape()
    return occ["BRepAlgoAPI_Cut"](fused, cutter).Shape()


def run_boolean_nightmare_test() -> dict[str, BooleanStressResult]:
    occ = _require_occ()
    left, right = _make_boolean_operands()
    operations = {
        "union": occ["BRepAlgoAPI_Fuse"],
        "difference": occ["BRepAlgoAPI_Cut"],
        "intersection": occ["BRepAlgoAPI_Common"],
    }
    results: dict[str, BooleanStressResult] = {}
    for name, builder in operations.items():
        start = time.perf_counter()
        shape = builder(left, right).Shape()
        elapsed = time.perf_counter() - start
        results[name] = BooleanStressResult(
            operation=name,
            duration_sec=elapsed,
            metrics=_shape_metrics(shape),
        )
    return results


def run_step_round_trip_test(step_path: str | Path | None = None) -> StepRoundTripResult:
    occ = _require_occ()
    shape = _make_step_history_shape()
    original = _shape_metrics(shape)

    if step_path is None:
        handle = NamedTemporaryFile(delete=False, suffix=".step")
        handle.close()
        path = Path(handle.name)
    else:
        path = Path(step_path)

    path.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    writer = occ["STEPControl_Writer"]()
    writer.Transfer(shape, occ["STEPControl_AsIs"])
    write_ok = writer.Write(str(path)) == occ["IFSelect_RetDone"]

    imported_shape = None
    read_ok = False
    if write_ok:
        reader = occ["STEPControl_Reader"]()
        if reader.ReadFile(str(path)) == occ["IFSelect_RetDone"]:
            transferred = int(reader.TransferRoots())
            if transferred > 0:
                imported_shape = reader.OneShape()
                read_ok = True
    duration_sec = time.perf_counter() - start

    imported = _shape_metrics(imported_shape) if imported_shape is not None else ShapeCheckResult(
        valid=False,
        solids=0,
        shells=0,
        faces=0,
        edges=0,
        volume=0.0,
    )

    relative_volume_delta = 0.0
    if original.volume > 1e-9 and imported.volume > 0.0:
        relative_volume_delta = abs(imported.volume - original.volume) / original.volume

    return StepRoundTripResult(
        path=str(path),
        write_ok=write_ok,
        read_ok=read_ok,
        duration_sec=duration_sec,
        original=original,
        imported=imported,
        relative_volume_delta=float(relative_volume_delta),
    )


def build_pi_bloom_scene(feature_count: int, *, spacing: float = 3.0) -> Scene:
    scene = Scene()
    per_axis = max(1, int(math.ceil(feature_count ** (1.0 / 3.0))))
    for index in range(int(feature_count)):
        x_index = index % per_axis
        y_index = (index // per_axis) % per_axis
        z_index = index // (per_axis * per_axis)

        radius = 0.52 + 0.04 * float(index % 5)
        bloom = 0.16 + 0.025 * float(index % 7)
        petals = 5.0 + float(index % 6)
        crown = 0.08 + 0.02 * float(index % 5)
        beta = 0.015 + 0.004 * float(index % 4)

        prim = Prim(
            KIND_PI_BLOOM,
            [radius, bloom, petals, crown],
            beta=beta,
            color=(0.96, 0.42, 0.58),
        )
        prim.set_transform(
            pos=[x_index * spacing, y_index * spacing, z_index * spacing],
            euler=[0.0, float((index * 17) % 360), 0.0],
            scale=[1.0, 1.0, 1.0],
        )
        scene.add(prim)
    return scene


def _sample_points(feature_count: int, sample_count: int, spacing: float) -> np.ndarray:
    per_axis = max(1, int(math.ceil(feature_count ** (1.0 / 3.0))))
    extent = spacing * max(per_axis - 1, 1)
    rng = np.random.default_rng(20260328)
    low = np.array([-spacing, -spacing, -spacing], dtype=np.float64)
    high = np.array([extent + spacing, extent + spacing, extent + spacing], dtype=np.float64)
    return rng.uniform(low, high, size=(sample_count, 3))


def benchmark_feature_scaling(
    *,
    counts: Iterable[int] = (128, 512, 2048, 5000),
    sample_count: int = 8,
    spacing: float = 3.0,
) -> list[PerformanceSample]:
    sample_count = max(1, int(sample_count))
    results: list[PerformanceSample] = []
    for raw_count in counts:
        feature_count = max(1, int(raw_count))
        build_start = time.perf_counter()
        scene = build_pi_bloom_scene(feature_count, spacing=spacing)
        build_seconds = time.perf_counter() - build_start

        points = _sample_points(feature_count, sample_count, spacing)
        distances: list[float] = []
        eval_start = time.perf_counter()
        for point in points:
            dist, _, _ = scene.sdf(point)
            distances.append(float(dist))
        eval_seconds = time.perf_counter() - eval_start

        distances_np = np.asarray(distances, dtype=np.float64)
        results.append(
            PerformanceSample(
                feature_count=feature_count,
                sample_count=sample_count,
                build_seconds=float(build_seconds),
                eval_seconds=float(eval_seconds),
                samples_per_second=float(sample_count / max(eval_seconds, 1e-9)),
                mean_distance=float(np.mean(distances_np)),
                min_distance=float(np.min(distances_np)),
                max_distance=float(np.max(distances_np)),
            )
        )
    return results


def generate_crucible_report(
    *,
    include_occ: bool = True,
    step_path: str | Path | None = None,
    perf_counts: Iterable[int] = (128, 512, 2048, 5000),
    perf_samples: int = 8,
) -> dict[str, Any]:
    report: dict[str, Any] = {}

    if include_occ and has_occ():
        boolean_results = run_boolean_nightmare_test()
        report["boolean_nightmare"] = {
            name: asdict(result) for name, result in boolean_results.items()
        }
        report["step_round_trip"] = asdict(run_step_round_trip_test(step_path))
    else:
        reason = "OCC unavailable" if include_occ else "OCC checks disabled"
        report["boolean_nightmare"] = {"skipped": True, "reason": reason}
        report["step_round_trip"] = {"skipped": True, "reason": reason}

    report["performance_wall"] = [
        asdict(sample)
        for sample in benchmark_feature_scaling(counts=perf_counts, sample_count=perf_samples)
    ]
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AdaptiveCAD reliability crucible.")
    parser.add_argument("--skip-occ", action="store_true", help="Skip OCC-backed boolean and STEP checks")
    parser.add_argument("--step-out", type=Path, default=None, help="Optional STEP output path for the round-trip check")
    parser.add_argument(
        "--perf-counts",
        type=int,
        nargs="*",
        default=[128, 512, 2048, 5000],
        help="Feature counts to benchmark for the performance wall",
    )
    parser.add_argument(
        "--perf-samples",
        type=int,
        default=8,
        help="Number of sample points to evaluate per feature-count tier",
    )
    args = parser.parse_args(argv)

    report = generate_crucible_report(
        include_occ=not args.skip_occ,
        step_path=args.step_out,
        perf_counts=args.perf_counts,
        perf_samples=args.perf_samples,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())