#!/usr/bin/env python3
"""Export 2D cross-section slices from analytic AMA / scene JSON.

Supports:
- *True-analytic SDF scenes* stored as a JSON list of primitives in analytic/scene.json.
- *Volume/field scenes* stored as a dict scene.json + fields/*.npy (e.g. phi.npy).

This is separate from export_slices.py (which relies on OCC/BREP).

Outputs per-slice:
- PNG mask (inside=white)
- NPZ with distance + mask + coordinate grids
- SVG contours (optional)

Example:
  python export_sdf_slices.py --ama gyroid_field.ama --axis z --pos -0.5 0 0.5 --res 384 --extent 2.0 --out-dir slices_gyroid
"""

from __future__ import annotations

import argparse
import json
import math
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class SliceConfig:
    axis: str
    positions: list[float]
    res: int
    extent: float
    band: float
    write_svg: bool


def _load_scene_from_ama(path: str) -> object:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    with zipfile.ZipFile(p, "r") as z:
        if "analytic/scene.json" not in z.namelist():
            raise FileNotFoundError("AMA has no analytic/scene.json")
        return json.loads(z.read("analytic/scene.json").decode("utf-8"))


def _load_scene_from_json(path: str) -> object:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw


def _op_from_json(value: object) -> str:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("subtract", "sub"):
            return "subtract"
        if v in ("intersect", "and"):
            return "intersect"
        return "solid"
    try:
        i = int(value or 0)
    except Exception:
        i = 0
    if i == 1:
        return "subtract"
    if i == 2:
        return "intersect"
    return "solid"


def build_scene(scene_list: list[dict[str, object]]):
    """Build an adaptivecad.aacore.sdf.Scene from a scene-list JSON."""
    from adaptivecad.aacore.sdf import Prim, Scene

    scene = Scene()
    scene.prims.clear()

    for entry in scene_list:
        if not isinstance(entry, dict):
            continue

        kind = str(entry.get("kind", "")).strip().lower()
        if not kind:
            continue

        params = entry.get("params")
        if not isinstance(params, list):
            params = [0.5, 0.0, 0.0, 0.0]

        beta = float(entry.get("beta", 0.0) or 0.0)
        op = _op_from_json(entry.get("op", 0))

        color = entry.get("color")
        if isinstance(color, list) and len(color) >= 3:
            col = (float(color[0]), float(color[1]), float(color[2]))
        else:
            col = (0.85, 0.75, 0.55)

        pr = Prim(kind, [float(x) for x in params], beta=beta, op=op, color=col)

        pos_raw = entry.get("pos")
        euler_raw = entry.get("euler")
        scale_raw = entry.get("scale")

        pos = None
        if isinstance(pos_raw, list) and len(pos_raw) >= 3:
            try:
                pos = [float(pos_raw[0]), float(pos_raw[1]), float(pos_raw[2])]
            except Exception:
                pos = None

        euler = None
        if isinstance(euler_raw, list) and len(euler_raw) >= 3:
            try:
                euler = [float(euler_raw[0]), float(euler_raw[1]), float(euler_raw[2])]
            except Exception:
                euler = None

        scale = None
        if isinstance(scale_raw, list) and len(scale_raw) >= 3:
            try:
                scale = [float(scale_raw[0]), float(scale_raw[1]), float(scale_raw[2])]
            except Exception:
                scale = None

        if pos is not None or euler is not None or scale is not None:
            try:
                pr.set_transform(pos=pos, euler=euler, scale=scale)
            except Exception:
                pass

        scene.add(pr)

    return scene


def _select_volume_layer(scene_dict: dict[str, object], layer_name: str | None) -> str:
    layers = scene_dict.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("Volume scene has no 'layers' list")

    if layer_name:
        for layer in layers:
            if isinstance(layer, dict) and str(layer.get("name", "")) == layer_name:
                field = layer.get("field")
                if isinstance(field, str) and field:
                    return field
        raise ValueError(f"No layer named '{layer_name}'")

    # Prefer enabled layer, else first layer.
    for layer in layers:
        if isinstance(layer, dict) and bool(layer.get("enabled", False)):
            field = layer.get("field")
            if isinstance(field, str) and field:
                return field

    first = layers[0]
    if isinstance(first, dict):
        field = first.get("field")
        if isinstance(field, str) and field:
            return field
    raise ValueError("Could not determine volume layer field path")


def _slice_volume_field(
    field3d: np.ndarray,
    axis: str,
    pos_world: float,
    scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if field3d.ndim != 3:
        raise ValueError("Volume field must be 3D")
    nx, ny, nz = field3d.shape

    half = 0.5 * float(scale)
    t = (float(pos_world) + half) / (2.0 * half) if half > 0 else 0.5
    t = float(np.clip(t, 0.0, 1.0))

    if axis == "x":
        idx = int(round(t * (nx - 1)))
        sl = field3d[idx, :, :]
        a = np.linspace(-half, half, ny, dtype=np.float32)
        b = np.linspace(-half, half, nz, dtype=np.float32)
        X, Y = np.meshgrid(a, b, indexing="xy")
    elif axis == "y":
        idx = int(round(t * (ny - 1)))
        sl = field3d[:, idx, :]
        a = np.linspace(-half, half, nx, dtype=np.float32)
        b = np.linspace(-half, half, nz, dtype=np.float32)
        X, Y = np.meshgrid(a, b, indexing="xy")
    elif axis == "z":
        idx = int(round(t * (nz - 1)))
        sl = field3d[:, :, idx]
        a = np.linspace(-half, half, nx, dtype=np.float32)
        b = np.linspace(-half, half, ny, dtype=np.float32)
        X, Y = np.meshgrid(a, b, indexing="xy")
    else:
        raise ValueError("axis must be x, y, or z")

    # Ensure 2D float32
    return sl.astype(np.float32), X.astype(np.float32), Y.astype(np.float32)


def _grid_for_slice(axis: str, pos: float, res: int, extent: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lin = np.linspace(-float(extent), float(extent), int(res), dtype=np.float32)
    A, B = np.meshgrid(lin, lin, indexing="xy")

    if axis == "z":
        X, Y, Z = A, B, np.full_like(A, float(pos), dtype=np.float32)
    elif axis == "y":
        X, Y, Z = A, np.full_like(A, float(pos), dtype=np.float32), B
    elif axis == "x":
        X, Y, Z = np.full_like(A, float(pos), dtype=np.float32), A, B
    else:
        raise ValueError("axis must be x, y, or z")
    return X, Y, Z


def slice_distance(scene, cfg: SliceConfig) -> Iterable[tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Yield (pos, dist, mask, X, Y) for each slice."""
    res = int(cfg.res)
    extent = float(cfg.extent)
    band = max(1e-6, float(cfg.band))

    for pos in cfg.positions:
        X, Y, Z = _grid_for_slice(cfg.axis, float(pos), res, extent)
        dist = np.empty((res, res), dtype=np.float32)

        # Simple CPU evaluation (loop). Reasonable for ~256-512 res and a few slices.
        for j in range(res):
            for i in range(res):
                d, _, _ = scene.sdf((float(X[j, i]), float(Y[j, i]), float(Z[j, i])))
                dist[j, i] = float(d)

        mask = (dist <= 0.0).astype(np.uint8) * 255
        band_mask = (np.abs(dist) <= 0.5 * band).astype(np.uint8) * 255
        yield float(pos), dist, mask, band_mask, X, Y


def _write_png(path: Path, img_u8: np.ndarray) -> None:
    try:
        from skimage.io import imsave  # type: ignore

        imsave(str(path), img_u8)
        return
    except Exception:
        pass

    # Fallback: write .npy instead
    np.save(str(path.with_suffix(".npy")), img_u8)


def _write_svg_contours(path: Path, band_mask: np.ndarray, X: np.ndarray, Y: np.ndarray) -> None:
    try:
        from skimage import measure  # type: ignore
    except Exception:
        return

    # Find contours at 0.5 in [0,1]
    contours = measure.find_contours((band_mask > 0).astype(np.float32), 0.5)
    if not contours:
        return

    # Map pixel coords -> world coords.
    # contours are in (row, col) with row=Y index, col=X index.
    h, w = band_mask.shape
    xs = X[0, :]
    ys = Y[:, 0]

    def px_to_world(rc: np.ndarray) -> np.ndarray:
        rr = np.clip(rc[:, 0], 0, h - 1)
        cc = np.clip(rc[:, 1], 0, w - 1)
        xi = np.interp(cc, np.arange(w), xs)
        yi = np.interp(rr, np.arange(h), ys)
        return np.stack([xi, yi], axis=1)

    # SVG viewBox in world units
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    vb = f"{xmin} {ymin} {xmax - xmin} {ymax - ymin}"

    # Build paths
    paths = []
    for c in contours:
        pts = px_to_world(c)
        if pts.shape[0] < 8:
            continue
        d = [f"M {pts[0,0]:.6g} {pts[0,1]:.6g}"]
        for k in range(1, pts.shape[0]):
            d.append(f"L {pts[k,0]:.6g} {pts[k,1]:.6g}")
        d.append("Z")
        paths.append(" ".join(d))

    if not paths:
        return

    svg = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"{vb}\">",
        "  <g fill=\"none\" stroke=\"black\" stroke-width=\"0.01\">",
    ]
    for d in paths:
        svg.append(f"    <path d=\"{d}\"/>")
    svg.append("  </g>")
    svg.append("</svg>")

    path.write_text("\n".join(svg), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Export 2D slices from an analytic SDF scene")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ama", type=str, help="Path to .ama with analytic/scene.json")
    src.add_argument("--scene-json", type=str, help="Path to analytic scene JSON (list only)")

    ap.add_argument("--axis", choices=["x", "y", "z"], default="z")
    ap.add_argument("--pos", nargs="+", type=float, required=True, help="Slice positions along axis")
    ap.add_argument("--res", type=int, default=384, help="Image resolution per slice")
    ap.add_argument("--extent", type=float, default=2.0, help="Half-width of slice window in world units")
    ap.add_argument("--band", type=float, default=0.03, help="Thickness band (for contour extraction) in world units")
    ap.add_argument("--out-dir", type=str, default="sdf_slices")
    ap.add_argument("--svg", action="store_true", help="Also write SVG contour paths")
    ap.add_argument(
        "--layer",
        type=str,
        default=None,
        help="For volume scenes (dict scene.json), choose layer name (default: first enabled)",
    )
    ap.add_argument(
        "--iso",
        type=float,
        default=None,
        help="Iso threshold (default: from scene.json if present, else 0.0)",
    )

    args = ap.parse_args()

    if args.ama:
        raw_scene = _load_scene_from_ama(args.ama)
        tag = Path(args.ama).stem
        ama_path = args.ama
    else:
        raw_scene = _load_scene_from_json(args.scene_json)
        tag = Path(args.scene_json).stem
        ama_path = None

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = SliceConfig(
        axis=str(args.axis),
        positions=[float(x) for x in args.pos],
        res=int(args.res),
        extent=float(args.extent),
        band=float(args.band),
        write_svg=bool(args.svg),
    )

    if isinstance(raw_scene, list):
        scene = build_scene(raw_scene)  # type: ignore[arg-type]
        for pos, dist, mask, band_mask, X, Y in slice_distance(scene, cfg):
            safe = f"{pos:+.4f}".replace("+", "p").replace("-", "m").replace(".", "_")
            base = out_dir / f"{tag}_{cfg.axis}_{safe}"

            _write_png(base.with_suffix(".png"), mask)
            np.savez_compressed(
                str(base.with_suffix(".npz")),
                dist=dist,
                mask=mask,
                band_mask=band_mask,
                X=X,
                Y=Y,
                axis=cfg.axis,
                pos=pos,
            )
            if cfg.write_svg:
                _write_svg_contours(base.with_suffix(".svg"), band_mask, X, Y)

            print(
                f"Wrote: {base.with_suffix('.png').name} (+ .npz{', .svg' if cfg.write_svg else ''})"
            )
    elif isinstance(raw_scene, dict):
        if not ama_path:
            raise ValueError("Volume slicing currently requires --ama (to read fields/*.npy)")
        field_path = _select_volume_layer(raw_scene, args.layer)
        vol = raw_scene.get("volume")
        scale = 2.0
        iso = 0.0
        if isinstance(vol, dict):
            scale = float(vol.get("scale", scale) or scale)
            iso = float(vol.get("iso_level", iso) or iso)
        if args.iso is not None:
            iso = float(args.iso)

        with zipfile.ZipFile(ama_path, "r") as z:
            import io

            arr = np.load(io.BytesIO(z.read(field_path)))

        for pos in cfg.positions:
            sl, X, Y = _slice_volume_field(arr, cfg.axis, float(pos), scale)
            dist = sl
            mask = (dist <= iso).astype(np.uint8) * 255
            band_mask = (np.abs(dist - iso) <= 0.5 * float(cfg.band)).astype(np.uint8) * 255

            safe = f"{float(pos):+.4f}".replace("+", "p").replace("-", "m").replace(".", "_")
            base = out_dir / f"{tag}_{cfg.axis}_{safe}"

            _write_png(base.with_suffix(".png"), mask)
            np.savez_compressed(
                str(base.with_suffix(".npz")),
                dist=dist,
                mask=mask,
                band_mask=band_mask,
                X=X,
                Y=Y,
                axis=cfg.axis,
                pos=float(pos),
                iso=float(iso),
                layer=str(field_path),
                scale=float(scale),
            )
            if cfg.write_svg:
                _write_svg_contours(base.with_suffix(".svg"), band_mask, X, Y)

            print(
                f"Wrote: {base.with_suffix('.png').name} (+ .npz{', .svg' if cfg.write_svg else ''})"
            )
    else:
        raise ValueError("Unsupported analytic/scene.json format")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
