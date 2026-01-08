from __future__ import annotations

import json
import zipfile
from pathlib import Path


def load_analytic_scene_list_from_ama(ama_path: str) -> list[dict[str, object]]:
    """Load list-based analytic SDF scene from an AMA.

    Raises if the AMA is not a list-based analytic SDF scene.
    """
    p = Path(ama_path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    with zipfile.ZipFile(p, "r") as zf:
        if "analytic/scene.json" not in zf.namelist():
            raise FileNotFoundError("AMA missing analytic/scene.json")
        raw = json.loads(zf.read("analytic/scene.json").decode("utf-8"))

    if not isinstance(raw, list):
        raise ValueError("analytic/scene.json is not a list; expected analytic SDF scene")

    out: list[dict[str, object]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
    return out
