"""Demo: unwrap → interpolate → rewrap on a torus.

Run:
    python AdaptiveCAD/examples/torus_phase_demo.py

This prints winding numbers and writes a small CSV of embedded XYZ points.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np

# Allow running as: `python AdaptiveCAD/examples/torus_phase_demo.py`
# from the repo root by ensuring `AdaptiveCAD/` is on sys.path.
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from adaptivecad.torus_phase import TorusPath, wrap_to_pi


def main() -> None:
    # Build a path that crosses the branch cut in theta.
    # theta goes from +170° to +550° (i.e., crosses +180°), phi slowly advances.
    t = np.linspace(0.0, 1.0, 80)
    theta = math.radians(170.0) + (2.0 * math.pi * 1.05) * t
    phi = (2.0 * math.pi * 0.25) * t

    wrapped = np.column_stack([wrap_to_pi(theta), wrap_to_pi(phi)])
    path = TorusPath(wrapped, phase_space="wrapped")

    wth, wph = path.windings()
    print(f"Windings: theta={wth}, phi={wph}")

    dense = path.interpolate(300)
    xyz = dense.to_xyz(R=25.0, r=8.0)

    out = Path(__file__).with_suffix(".csv")
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x", "y", "z"])
        w.writerows(xyz.tolist())

    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
