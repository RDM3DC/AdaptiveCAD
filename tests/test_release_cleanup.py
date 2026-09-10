"""Behavioral regressions for the defects exposed by the release lint audit."""
import inspect
import json
import math
import subprocess
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import get_type_hints

import numpy as np
import pytest


@pytest.mark.parametrize("kind", ["none", "point", "segment"])
def test_intersection_payload_defaults_are_values_not_factories(kind):
    from adaptivecad.sketch.geometry import Intersection, Vec2

    a, b = Vec2(0, 0), Vec2(1, 0)
    hit = {"none": lambda: Intersection.none(),
           "point": lambda: Intersection.point(a),
           "segment": lambda: Intersection.segment(a, b)}[kind]()
    assert hit.point == (a if kind == "point" else None)
    assert hit.segment == ((a, b) if kind == "segment" else None)
    assert replace(hit) == hit
    assert asdict(Intersection.none()) == {"kind": "none", "point": None, "segment": None}
    assert all(f.default is None for f in fields(Intersection) if f.name != "kind")
    assert inspect.signature(Intersection).parameters["point"].default is None


def test_intersection_legacy_and_unambiguous_factories_match():
    from adaptivecad.sketch.geometry import Intersection, Vec2, segment_intersection

    a, b, c = Vec2(0, 0), Vec2(2, 0), Vec2(1, 0)
    assert Intersection.point(a) == Intersection.from_point(a)
    assert Intersection.segment(a, b) == Intersection.from_segment(a, b)
    assert segment_intersection(a, b, c, Vec2(3, 0)) == Intersection.segment(c, b)
    assert segment_intersection(a, b, Vec2(1, -1), Vec2(1, 1)) == Intersection.point(c)


@pytest.mark.parametrize("snapped", [None, (0, 0, 0), np.array([2.0, 3.0, 4.0])])
def test_snap_move_uses_host_preview_and_explicit_none_check(snapped):
    from adaptivecad.commands.move import MoveWithSnapCmd

    previews, translations, handlers, rebuilds = [], [], [], []
    feat = SimpleNamespace(get_reference_point=lambda: (1, 1, 1),
                           apply_translation=lambda d: translations.append(d.copy()))
    host = SimpleNamespace(
        selected_feature=lambda: feat, view=object(),
        snap_manager=SimpleNamespace(snap=lambda p, view: (snapped, "endpoint")),
        viewer=SimpleNamespace(set_temp_mouse_handlers=lambda *h: handlers.extend(h)),
        show_move_preview=lambda *p: previews.append(p),
        rebuild_scene=lambda: rebuilds.append(True),
    )
    MoveWithSnapCmd().run(host)
    pointer = (9, 8, 7)
    handlers[0](pointer)
    expected = pointer if snapped is None else snapped
    np.testing.assert_array_equal(previews[0][1], expected)
    assert translations == []
    handlers[1](pointer)
    np.testing.assert_array_equal(translations[0], np.asarray(expected) - 1)
    assert rebuilds == [True]


def test_snap_move_missing_host_contract_fails_before_mutation():
    from adaptivecad.commands.move import MoveWithSnapCmd

    host = SimpleNamespace(selected_feature=lambda: object())
    with pytest.raises(RuntimeError, match="show_move_preview"):
        MoveWithSnapCmd().run(host)


def test_ama_export_binds_optional_input_dialog(monkeypatch, tmp_path):
    import adaptivecad.command_defs as commands

    out = tmp_path / "test.ama"
    writes, messages = [], []
    input_dialog = SimpleNamespace(getItem=lambda *a: ("mm", True))
    file_dialog = SimpleNamespace(getSaveFileName=lambda *a, **k: (str(out), ""))
    monkeypatch.setattr(commands, "_require_command_modules",
                        lambda: (input_dialog, file_dialog, None, None, None))
    monkeypatch.setattr(commands, "DOCUMENT", [object()])
    writer = ModuleType("adaptivecad.io.ama_writer")
    writer.write_ama = lambda *a, **k: writes.append((a, k))
    monkeypatch.setitem(sys.modules, "adaptivecad.io.ama_writer", writer)
    win = SimpleNamespace(statusBar=lambda: SimpleNamespace(showMessage=messages.append))
    commands.ExportAmaCmd().run(SimpleNamespace(win=win))
    assert writes[0][0][1] == str(out)
    assert writes[0][1] == {"units": "mm"}
    assert len(messages) == 1


def test_macro_widget_annotation_is_resolvable():
    pytest.importorskip("PySide6.QtWidgets")
    from adaptivecad.plugins.macro_engine import MacroEngine

    assert "parent_widget" in get_type_hints(MacroEngine.run)


def test_topk_path_compression_executes_curvature_branch(tmp_path):
    src, dest = tmp_path / "in.json", tmp_path / "out.json"
    anchors = [[0, 0], [1, 0], [1, 1], [2, 1], [3, 1]]
    src.write_text(json.dumps({"paths": [{"id": "corner", "anchors": anchors}]}))
    p = subprocess.run([sys.executable, "-m", "pathtext.compress_paths", str(src), str(dest),
                        "--method", "topk", "--target_k", "3"], capture_output=True,
                       text=True, timeout=30, check=False)
    assert p.returncode == 0, p.stderr
    result = json.loads(dest.read_text())["paths"][0]["anchors_cmc"]
    assert result["new_points"] == 3
    assert result["anchors"][0] == anchors[0] and result["anchors"][-1] == anchors[-1]
    assert math.isfinite(result["max_err_px"])


def test_field_optimizer_small_real_sweep_preserves_grid(tmp_path):
    script = Path(__file__).resolve().parents[1] / "AdaptiveCAD_Shipping_Track_v1/adaptivecad_fields_optimizer.py"
    p = subprocess.run([sys.executable, str(script), "--grid", "8", "--seeds", "0",
                        "--coarse", "0.0", "0.5", "--outdir", str(tmp_path)],
                       capture_output=True, text=True, timeout=60, check=False)
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "entangled_sweep_metrics.csv").is_file()
    assert (tmp_path / "figs/rho_sweep_panels.gif").is_file()
