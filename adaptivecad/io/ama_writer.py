# adaptivecad/io/ama_writer.py
import json, time, zipfile, tempfile, shutil, os, uuid
from pathlib import Path
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepTools import breptools_Write

__all__ = ["write_ama"]

def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def write_ama(document, path, units="mm", defl=0.05):
    """
    Parameters
    ----------
    document : list[Feature]
        AdaptiveCAD in‑memory feature list (each has .name, .params, .shape).
    path : str | Path
        Destination filename, e.g. 'part.ama'.
    units : str
        'mm' or 'inch'.
    defl : float
        Default modelling tolerance (recorded in manifest only).
    """
    if not document:
        raise ValueError("DOCUMENT list is empty – nothing to export")

    path = Path(path)
    tmp = Path(tempfile.mkdtemp())

    # 1. write manifest.json (high‑level metadata)
    manifest = {
        "format": "AMA",
        "version": "0.1.0",
        "exported": _timestamp(),
        "units": units,
        "features": len(document),
        "tolerance": defl,
        "uuid": str(uuid.uuid4()),
    }
    (tmp / "meta").mkdir()
    (tmp / "meta" / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # 2. write simple feature graph JSON (one node per Feature, linear)
    graph = []
    for idx, feat in enumerate(document):
        node = {
            "id": f"f{idx:03d}",
            "type": feat.name,
            "params": feat.params,
            "geom": f"s{idx:03d}.brep",
            "inputs": [f"f{idx-1:03d}"] if idx else [],
        }
        graph.append(node)
    (tmp / "model").mkdir()
    (tmp / "model" / "graph.json").write_text(json.dumps(graph, indent=2))

    # 3. dump each TopoDS_Shape to /geom/*.brep
    (tmp / "geom").mkdir()
    for idx, feat in enumerate(document):
        fn = tmp / "geom" / f"s{idx:03d}.brep"
        breptools_Write(feat.shape, str(fn))

    # 4. create the ZIP (.ama)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in tmp.rglob("*"):
            z.write(file, file.relative_to(tmp))

    shutil.rmtree(tmp)
    return path
