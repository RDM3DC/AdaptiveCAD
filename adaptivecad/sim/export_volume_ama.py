from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

import numpy as np


def export_volume_fields_as_ama(
    *,
    fields: dict[str, np.ndarray],
    enabled: str,
    scale: float,
    units: str = "mm",
    generator: str = "adaptivecad.sim",
) -> bytes:
    """Create a volume-style AMA that the Analytic Viewport can load.

    This matches the existing pattern used by pr_volume.ama, but without a mesh.

    - fields: mapping name -> 3D numpy array
    - enabled: which field name is enabled by default
    - scale: world span used to map slice positions (see export_sdf_slices.py)
    """
    if enabled not in fields:
        raise ValueError("enabled field must exist")

    layers = []
    manifest_fields: dict[str, Any] = {}

    for name, arr in fields.items():
        if not isinstance(arr, np.ndarray) or arr.ndim != 3:
            raise ValueError(f"field '{name}' must be a 3D numpy array")
        path = f"fields/{name}.npy"
        layers.append(
            {
                "name": str(name),
                "field": path,
                "colormap": "viridis" if name != enabled else "plasma",
                "enabled": bool(name == enabled),
            }
        )
        manifest_fields[str(name)] = {
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "path": path,
        }

    scene = {
        "layers": layers,
        "render": {"wireframe": False, "shading": "smooth", "iso_level": 0.0},
        "volume": {"shape": list(next(iter(fields.values())).shape), "iso_level": 0.0, "scale": float(scale)},
    }

    manifest = {
        "type": "sim_volume",
        "fields": manifest_fields,
    }

    provenance = {
        "generator": str(generator),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units": str(units),
        "mode": "volume_fields",
        "checksums": {name: hashlib.sha256(arr.tobytes()).hexdigest()[:16] for name, arr in fields.items()},
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, arr in fields.items():
            arr_io = io.BytesIO()
            np.save(arr_io, arr)
            zf.writestr(f"fields/{name}.npy", arr_io.getvalue())

        zf.writestr("analytic/scene.json", json.dumps(scene, indent=2))
        zf.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("meta/provenance.json", json.dumps(provenance, indent=2))

    return buf.getvalue()
