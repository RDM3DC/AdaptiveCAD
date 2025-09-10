"""
ACProj project I/O per spec.

Two entry points:
 - save_acproj(scene_dict_or_list, path, zip_mode=False)
 - load_acproj(path_or_zip)

Notes:
 - We operate primarily on plain Python dicts matching the ACProj schema.
 - If zip_mode is True or path endswith .acprojz, we create a ZIP with
   project.json at root and copy referenced sidecars under meshes/, toolpaths/, thumbs/.
 - Minimal conveniences included (bbox compute if missing, timestamp, version default).
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

__all__ = ["save_acproj", "load_acproj", "ensure_bbox"]


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_bbox(scene: List[Dict[str, Any]], fallback: Tuple[Tuple[float, float, float], Tuple[float, float, float]]=((0,0,0),(0,0,0))):
    """Compute a conservative bbox from any embedded inline mesh data if present.
    If no data can be found, return fallback.
    This is intentionally simple to keep dependencies minimal.
    """
    xmin=ymin=zmin= float("inf")
    xmax=ymax=zmax= float("-inf")
    found=False
    for node in scene or []:
        # Inline mesh example: {type:"Mesh", source:{kind:"INLINE", base64:"..."}} — not standardized for mesh arrays
        # Many callers will fill bbox themselves; here we only aggregate known bbox fields present in each node
        b = node.get("bbox") or node.get("meta", {}).get("bbox")
        if b and isinstance(b, (list, tuple)) and len(b)==2:
            (x0,y0,z0),(x1,y1,z1) = b
            xmin=min(xmin, float(x0)); ymin=min(ymin, float(y0)); zmin=min(zmin, float(z0))
            xmax=max(xmax, float(x1)); ymax=max(ymax, float(y1)); zmax=max(zmax, float(z1))
            found=True
    if not found:
        return fallback
    return [[xmin,ymin,zmin],[xmax,ymax,zmax]]


def _should_zip(path: Union[str, Path], zip_mode: bool) -> bool:
    p = str(path).lower()
    return zip_mode or p.endswith(".acprojz") or p.endswith(".zip")


def _norm_rel(rel: str) -> str:
    rel = rel.replace("\\", "/").lstrip("/")
    # route by extension
    if rel.startswith(("meshes/", "toolpaths/", "thumbs/")):
        return rel
    ext = Path(rel).suffix.lower()
    if ext in (".ama", ".stl", ".obj"):
        return f"meshes/{Path(rel).name}"
    if ext in (".gcode", ".gc"):
        return f"toolpaths/{Path(rel).name}"
    if ext in (".png", ".jpg", ".jpeg"):
        return f"thumbs/{Path(rel).name}"
    return rel


def save_acproj(scene: Union[Dict[str, Any], List[Dict[str, Any]]], path: Union[str, Path], zip_mode: bool=False) -> Path:
    """Save an ACProj JSON or ZIP per spec.

    - If `scene` is a dict, it is treated as the full ACProj JSON document.
    - If `scene` is a list, it is wrapped into a minimal top-level with defaults.
    - If `zip_mode` is True or `path` endswith .acprojz/.zip, we emit a ZIP with project.json
      and copy any external hrefs into meshes/, toolpaths/, thumbs/ dirs.
    """
    path = Path(path)
    if isinstance(scene, dict):
        data = dict(scene)  # shallow copy
    else:
        # Wrap list into top-level
        data = {
            "acproj_version": "1.0.0",
            "created": _ts(),
            "units": "mm",
            "bbox": ensure_bbox(scene),
            "scene": scene,
        }

    data.setdefault("acproj_version", "1.0.0")
    data.setdefault("created", _ts())
    data.setdefault("units", "mm")
    data.setdefault("scene", [])
    data.setdefault("tolerances", {
        "max_angle_err_deg": 0.5,
        "max_chord_err_rel": 0.05,
        "max_edge_len_rel": 0.02,
    })
    data.setdefault("bbox", ensure_bbox(data.get("scene", [])))

    if _should_zip(path, zip_mode):
        if not path.suffix:
            path = path.with_suffix(".acprojz")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            # Write project.json
            buf = json.dumps(data, indent=2).encode("utf-8")
            z.writestr("project.json", buf)

            # Copy sidecars referenced by href
            for node in data.get("scene", []):
                src = (node.get("source") or {}) if isinstance(node, dict) else {}
                href = src.get("href")
                if href and isinstance(href, str):
                    src_path = Path(href)
                    if src_path.exists():
                        arcname = _norm_rel(href)
                        z.write(src_path, arcname)
        return path

    # Plain JSON file (.acproj preferred)
    if path.suffix.lower() not in (".acproj", ".json"):
        path = path.with_suffix(".acproj")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_acproj(path_or_zip: Union[str, Path]) -> Dict[str, Any]:
    """Load ACProj JSON or ZIP variant. Returns the top-level dict.
    If a ZIP, reads project.json inside. Sidecars are not automatically loaded;
    clients can use node["source"]["href"] to open files relative to the ZIP by
    re-opening it and reading that member.
    """
    p = Path(path_or_zip)
    if p.is_file() and zipfile.is_zipfile(str(p)):
        with zipfile.ZipFile(p, "r") as z:
            with z.open("project.json") as f:
                return json.load(f)
    # Plain JSON
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
