from __future__ import annotations

import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
import zipfile

import numpy as np

from .derived import compute_derived_fields


def _load_field_from_ama(z: zipfile.ZipFile, *, field_path: str = "fields/f000_field.npy") -> np.ndarray:
    raw = z.read(field_path)
    buf = BytesIO(raw)
    arr = np.load(buf, allow_pickle=False)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D field in {field_path}, got shape={arr.shape}")
    return np.asarray(arr, dtype=np.float32)


def _ensure_analytic_payload(
    *,
    field: np.ndarray,
    scale_xy: float = 1.0,
    scale_z: float = 1.0,
    units: str = "mm",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    n = int(field.shape[0])
    x_extent = float((n - 1) * float(scale_xy))
    zmin = float(np.min(field))
    zmax = float(np.max(field))

    manifest: Dict[str, Any] = {
        "format": "AdaptiveCAD.AnalyticPayload",
        "schema_version": "0.1.0",
        "units": str(units),
        "domain": {"size": [n, n], "extents": [[0.0, x_extent], [0.0, x_extent], [zmin, zmax]]},
        "scales": {"xy": float(scale_xy), "z": float(scale_z)},
        "fields": [
            {
                "id": "field",
                "path": "fields/f000_field.npy",
                "dtype": "float32",
                "shape": [n, n],
                "meaning": "field",
            }
        ],
    }

    scene: Dict[str, Any] = {
        "format": "AdaptiveCAD.AnalyticScene",
        "version": "0.1.0",
        "camera": None,
        "layers": [
            {
                "id": "field",
                "label": "Field",
                "kind": "field",
                "field_ref": "fields/f000_field.npy",
                "colormap": "plasma",
            }
        ],
        "render": {"mode": "heightmap", "source_layer": "field", "iso": 0.50},
        "scales": {"xy": float(scale_xy), "z": float(scale_z)},
        "units": str(units),
    }

    return manifest, scene


def _append_unique_layers(
    analytic_manifest: Dict[str, Any],
    analytic_scene: Dict[str, Any],
    *,
    layers: Dict[str, Dict[str, Any]],
) -> None:
    mf_fields = analytic_manifest.get("fields")
    if not isinstance(mf_fields, list):
        mf_fields = []
        analytic_manifest["fields"] = mf_fields

    sc_layers = analytic_scene.get("layers")
    if not isinstance(sc_layers, list):
        sc_layers = []
        analytic_scene["layers"] = sc_layers

    existing_paths = {str(x.get("path")) for x in mf_fields if isinstance(x, dict) and isinstance(x.get("path"), str)}
    existing_scene_ids = {str(x.get("id")) for x in sc_layers if isinstance(x, dict) and isinstance(x.get("id"), str)}

    for lid, spec in layers.items():
        path = str(spec["path"])
        if path not in existing_paths:
            mf_fields.append(spec["manifest"])
            existing_paths.add(path)
        if lid not in existing_scene_ids:
            sc_layers.append(spec["scene"])
            existing_scene_ids.add(lid)


def augment_ama_with_derived_fields(
    ama_path: str | Path,
    *,
    out_path: str | Path | None = None,
    include: Iterable[str] = ("gradmag", "laplacian", "curvature", "smooth"),
    smooth_iters: int = 4,
    scale_xy: float = 1.0,
    scale_z: float = 1.0,
    units: str = "mm",
) -> Dict[str, Any]:
    """Create a new AMA with extra derived field layers added.

    This is a safe, non-destructive tool: by default it writes a new file.
    """

    src = Path(ama_path)
    if not src.exists():
        raise FileNotFoundError(str(src))

    if out_path is None:
        out = src.with_name(src.stem + "_aug" + src.suffix)
    else:
        out = Path(out_path)

    with zipfile.ZipFile(src, "r") as z:
        names = set(z.namelist())
        field = _load_field_from_ama(z)

        analytic_manifest: Dict[str, Any] | None = None
        analytic_scene: Dict[str, Any] | None = None

        if "analytic/manifest.json" in names:
            try:
                analytic_manifest = json.loads(z.read("analytic/manifest.json").decode("utf-8"))
            except Exception:
                analytic_manifest = None
        if "analytic/scene.json" in names:
            try:
                analytic_scene = json.loads(z.read("analytic/scene.json").decode("utf-8"))
            except Exception:
                analytic_scene = None

        if not isinstance(analytic_manifest, dict) or not isinstance(analytic_scene, dict):
            analytic_manifest, analytic_scene = _ensure_analytic_payload(
                field=field,
                scale_xy=scale_xy,
                scale_z=scale_z,
                units=units,
            )

        derived = compute_derived_fields(field, include=include, smooth_iters=smooth_iters)

        layer_specs: Dict[str, Dict[str, Any]] = {}
        n = int(field.shape[0])

        def add_layer(lid: str, *, path: str, meaning: str, label: str, cmap: str):
            layer_specs[lid] = {
                "path": path,
                "manifest": {"id": lid, "path": path, "dtype": "float32", "shape": [n, n], "meaning": meaning},
                "scene": {"id": lid, "label": label, "kind": "field", "field_ref": path, "colormap": cmap},
            }

        if "gradmag" in derived:
            add_layer("gradmag", path="fields/gradmag.npy", meaning="|∇field|", label="Gradient Magnitude", cmap="viridis")
        if "laplacian" in derived:
            add_layer("laplacian", path="fields/laplacian.npy", meaning="Δ field", label="Laplacian", cmap="diverge")
        if "curvature" in derived:
            add_layer("curvature", path="fields/curvature.npy", meaning="mean_curvature(heightmap)", label="Mean Curvature", cmap="diverge")
        if "smooth" in derived:
            add_layer("smooth", path="fields/smooth.npy", meaning="smoothed(field)", label="Smoothed Field", cmap="plasma")

        _append_unique_layers(analytic_manifest, analytic_scene, layers=layer_specs)

        # Build new zip from scratch to avoid duplicate-name ambiguity.
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z2:
            for name in z.namelist():
                if name in {"analytic/manifest.json", "analytic/scene.json"}:
                    continue
                if name in {"fields/gradmag.npy", "fields/laplacian.npy", "fields/curvature.npy", "fields/smooth.npy"}:
                    continue
                z2.writestr(name, z.read(name))

            z2.writestr("analytic/manifest.json", json.dumps(analytic_manifest, indent=2))
            z2.writestr("analytic/scene.json", json.dumps(analytic_scene, indent=2))

            for lid, arr in derived.items():
                buf = BytesIO()
                np.save(buf, np.asarray(arr, dtype=np.float32))
                if lid == "gradmag":
                    z2.writestr("fields/gradmag.npy", buf.getvalue())
                elif lid == "laplacian":
                    z2.writestr("fields/laplacian.npy", buf.getvalue())
                elif lid == "curvature":
                    z2.writestr("fields/curvature.npy", buf.getvalue())
                elif lid == "smooth":
                    z2.writestr("fields/smooth.npy", buf.getvalue())

    return {
        "ok": True,
        "in_path": str(src),
        "out_path": str(out),
        "added": sorted(list(derived.keys())),
    }


__all__ = ["augment_ama_with_derived_fields"]
