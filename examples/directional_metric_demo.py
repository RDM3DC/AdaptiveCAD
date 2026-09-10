"""Run from the repository root: python -m examples.directional_metric_demo."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.geom.directional_metric import NormalMetricPatch, balanced_directional_patch
from adaptivecad.linalg import Vec3


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Mesh-free directional metric measurement demo")
    parser.add_argument("--output", type=Path, help="Optional JSON report; refuses to overwrite")
    parser.add_argument("--scale", type=float, default=100.0, help="Patch radius/scale in mm")
    args = parser.parse_args(argv)
    patch = balanced_directional_patch(length_scale=args.scale)
    L = patch.length_scale
    curve = BezierCurve([Vec3(-0.6*L, 0.2*L, 0), Vec3(-0.2*L, 0.65*L, 0),
                         Vec3(0.3*L, -0.4*L, 0), Vec3(0.6*L, 0.2*L, 0)])
    flat = NormalMetricPatch(length_scale=L, radius=L)
    report = {
        "status": "synthetic intrinsic-geometry example; not a physical validation",
        "unit": patch.unit,
        "patch": json.loads(patch.to_json()),
        "circle_pi_at_0.75L": asdict(patch.circle_pi(0.75*L)),
        "directions": [],
        "native_bezier_flat_length": asdict(flat.bezier_length(curve)),
        "native_bezier_intrinsic_length": asdict(patch.bezier_length(curve)),
        "notes": "Lengths are numerical integrals; no triangles or embedded surface are generated.",
    }
    for theta in (0, math.pi/4, math.pi/2):
        report["directions"].append({
            "theta_degrees": math.degrees(theta),
            "directional_pi": patch.directional_pi(0.75*L, theta),
            "K_times_L_squared": patch.gaussian_curvature(
                0.75*L*math.cos(theta), 0.75*L*math.sin(theta)) * L*L,
        })
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
