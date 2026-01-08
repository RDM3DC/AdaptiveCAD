"""generate_binary_blackholes_ama.py

Creates a πₐ-pure, OCC-free AMA artifact that looks like a "binary blackhole" field:
- A 2D scalar field with two deep potential wells and a collision-like bridge.
- Stored as fields/f000_field.npy
- Includes analytic/scene.json so the analytic viewport launcher can visualize it.

Usage:
  python generate_binary_blackholes_ama.py --out binary_blackholes.ama --size 128 --scale-xy 1.0 --scale-z 1.0

Then:
  python ..\analytic_viewport_launcher.py --ama binary_blackholes.ama
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def make_binary_blackholes_field(size: int, *, eps: float = 0.06) -> np.ndarray:
    """Return a (size,size) field with two wells and a bridge."""

    n = int(size)
    if n < 8:
        raise ValueError("size must be >= 8")

    # Normalized domain [-1,1]x[-1,1]
    xs = np.linspace(-1.0, 1.0, n, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, n, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys, indexing="xy")

    # Two centers (like a binary system)
    c1 = (-0.45, 0.00)
    c2 = (0.45, 0.00)

    r1 = np.sqrt((X - c1[0]) ** 2 + (Y - c1[1]) ** 2 + eps**2)
    r2 = np.sqrt((X - c2[0]) ** 2 + (Y - c2[1]) ** 2 + eps**2)

    # Potential wells
    pot = -1.0 / r1 - 1.0 / r2

    # Add a mild "collision bridge" between wells (a gaussian tube along X axis)
    bridge = np.exp(-(Y * 5.0) ** 2) * np.exp(-(X * 1.2) ** 2)
    pot = pot - 0.35 * bridge

    # Map to a friendly 0..1 range
    pot = pot.astype(np.float32)
    pot = (pot - float(np.min(pot))) / max(1e-9, float(np.max(pot) - np.min(pot)))

    # Invert so wells are "deep" (low) visually if using heightmap
    phi = 1.0 - pot
    return phi.astype(np.float32)


def write_ama(out_path: Path, field: np.ndarray, *, scale_xy: float, scale_z: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _stable_json_bytes(obj: object) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    scene = {
        "format": "AdaptiveCAD.AnalyticScene",
        "version": "0.1.0",
        "kind": "ndfield_heightmap",
        "scales": {"xy": float(scale_xy), "z": float(scale_z)},
        "layers": [
            {
                "id": "field",
                "label": "Binary Blackholes",
                "field_ref": "fields/f000_field.npy",
                "colormap": "plasma",
            }
        ],
        "render": {
            "mode": "iso",
            "iso": 0.55,
            "source_layer": "field",
        },
        "units": "mm",
    }

    manifest = {
        "format": "AdaptiveCAD.AnalyticManifest",
        "version": "0.1.0",
        "kind": "ndfield",
        "fields": [
            {
                "id": "field",
                "path": "fields/f000_field.npy",
                "dtype": str(field.dtype),
                "shape": list(field.shape),
            }
        ],
    }

    cosmo_meta = {
        "ama_version": "0.1",
        "model": {
            "name": "BinaryBlackholesDemo",
            "pr_root": {
                "pi_a": "adaptive",
                "invariants": ["2pi_a", "w", "b", "C"],
            },
        },
        "run": {
            "solver": "generate_binary_blackholes_ama.make_binary_blackholes_field",
            "solver_version": "0.1.0",
            "git_commit": "unknown",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "seed": None,
            "platform": {"python": __import__("sys").version.split()[0]},
        },
        "numerics": {
            "grid": [int(field.shape[0]), int(field.shape[1])],
            "integrator": "procedural",
            "step_size": None,
        },
        "observables": {},
        "tests": [],
    }
    cosmo_bytes = _stable_json_bytes(cosmo_meta)
    cosmo_header = {
        "meta_format": "json",
        "meta_path": "meta/cosmo_meta.json",
        "meta_len": int(len(cosmo_bytes)),
        "meta_sha256": hashlib.sha256(cosmo_bytes).hexdigest(),
        "schema": "AdaptiveCAD.CosmoMeta",
        "schema_version": "0.1.0",
    }

    # Store as a zip-based AMA
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"version": "0.1.0", "parts": []}, indent=2))
        z.writestr("analytic/scene.json", json.dumps(scene, indent=2))
        z.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))

        z.writestr("meta/cosmo_meta.json", cosmo_bytes)
        z.writestr("meta/cosmo_header.json", json.dumps(cosmo_header, indent=2))

        # Write numpy bytes directly
        buf = _npy_bytes(field)
        z.writestr("fields/f000_field.npy", buf)

        # Minimal meta (optional)
        z.writestr(
            "meta/info.json",
            json.dumps(
                {
                    "generator": "generate_binary_blackholes_ama.py",
                    "size": int(field.shape[0]),
                    "cosmo_header": "meta/cosmo_header.json",
                },
                indent=2,
            ),
        )


def _npy_bytes(arr: np.ndarray) -> bytes:
    import io

    bio = io.BytesIO()
    np.save(bio, arr)
    return bio.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True, help="Output .ama path")
    ap.add_argument("--size", type=int, default=128, help="Field resolution")
    ap.add_argument("--scale-xy", type=float, default=1.0, help="XY scale")
    ap.add_argument("--scale-z", type=float, default=1.0, help="Z scale")
    args = ap.parse_args()

    out = Path(args.out)
    field = make_binary_blackholes_field(int(args.size))
    write_ama(out, field, scale_xy=float(args.scale_xy), scale_z=float(args.scale_z))
    print(f"ok: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
