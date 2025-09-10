import os
from pathlib import Path

import numpy as np

from adaptivecad.io.acproj import save_acproj, load_acproj
from adaptivecad.io.ama_bin import write_ama_bin, read_ama_bin


def test_acproj_json_roundtrip(tmp_path: Path):
    scene = [
        {
            "type": "ParamShape",
            "id": "shape_001",
            "subtype": "superellipse",
            "params": {"a": 40.0, "b": 25.0, "n": 3.2, "thickness": 2.0},
            "xform": [[1,0,0,0],[0,1,0,0],[0,0,1,0]],
            "display": {"color":[0.9,0.9,0.95], "visible": True},
            "bbox": [[-10,-10,0],[10,10,0]],
        },
        {
            "type": "Toolpath",
            "id": "tp_001",
            "source": {"kind":"GCODE", "href":"./toolpaths/tp_001.gcode"},
        },
    ]
    out = tmp_path / "proj.acproj"
    p = save_acproj(scene, out)
    assert p.exists()
    data = load_acproj(p)
    assert data["acproj_version"].startswith("1.")
    assert data["units"] in ("mm", "in")
    assert isinstance(data["scene"], list)


def test_acproj_zip_with_sidecar(tmp_path: Path):
    # create a sidecar toolpath
    tp_dir = tmp_path / "toolpaths"
    tp_dir.mkdir()
    tp = tp_dir / "tp_007.gcode"
    tp.write_text("G1 X0 Y0\nG1 X10 Y0\n")

    scene = [
        {"type":"Toolpath", "id":"tp_007", "source": {"kind":"GCODE", "href": str(tp)}},
    ]
    out = tmp_path / "proj.acprojz"
    p = save_acproj(scene, out, zip_mode=True)
    assert p.exists()
    data = load_acproj(p)
    assert data["scene"][0]["source"]["kind"] == "GCODE"


def test_ama_bin_roundtrip(tmp_path: Path):
    # simple square tri mesh
    V = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], dtype=np.float32)
    T = np.array([[0,1,2],[0,2,3]], dtype=np.uint32)
    meta = {"name":"part101", "units":"mm"}
    out = tmp_path / "part.ama"
    p = write_ama_bin(out, V, T, meta)
    assert p.exists()
    v2, t2, m2, extras = read_ama_bin(p)
    assert v2.shape == (4,3)
    assert t2.shape == (2,3)
    assert m2["units"] == "mm"
    assert extras == {}
