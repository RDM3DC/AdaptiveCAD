"""Coefficient, units, domain, audit and atomic-copy regression coverage."""
import json
import math
from dataclasses import replace

import numpy as np
import pytest

from adaptivecad.geom.directional_metric import NormalMetricPatch, balanced_directional_patch
from adaptivecad.geom.meshfree_tools import Curve, Surface, rotation
from adaptivecad.geom.tool_document import ToolDocument
from adaptivecad.metric_curve_transfer import (
    PlaneChartMapping,
    commit_transfer,
    preview_transfer,
    restricted_controls,
)
from adaptivecad.metric_project import MetricCurve, MetricHistory, MetricProject


def model(curve=None, unit="mm"):
    if curve is None:
        curve = Curve("bezier", ((-.4, 0, 0), (0, .4, 0), (.4, 0, 0)))
    return ToolDocument(unit, (("source", curve),))


@pytest.mark.parametrize("interval", [(0, 1), (.2, .8), (.8, .2), (1, 0),
                                     (0, .00001), (.999, 1), (.49, .51)])
@pytest.mark.parametrize("degree", [0, 1, 3, 8, 31])
def test_restriction_keeps_curve_and_parameter_direction(interval, degree):
    rng = np.random.default_rng(170 + degree)
    pts = tuple(tuple(p) for p in rng.uniform(-.35, .35, (degree+1, 3)))
    source = Curve("bezier", pts, interval=interval)
    result = Curve("bezier", restricted_controls(source))
    for t in np.linspace(0, 1, 17):
        np.testing.assert_allclose(result.evaluate(t), source.evaluate(t), atol=2e-14)
        np.testing.assert_allclose(result.derivative(t), source.derivative(t), atol=2e-13)


def test_copy_undo_redo_and_source_immutability(tmp_path):
    source, target = model(), MetricProject()
    history = MetricHistory(target)
    before = source.to_json()
    preview = preview_transfer(source, target, "source", "copied", PlaneChartMapping())
    assert not history.can_undo and not history.dirty
    receipt = commit_transfer(preview, source, history)
    assert source.to_json() == before
    assert len(history.current.curves) == 1 and history.dirty
    assert history.undo() == target
    assert history.redo() == preview.candidate
    path = tmp_path / "copied.acmetric.json"
    history.current.save(path)
    assert MetricProject.load(path) == history.current
    assert json.loads(json.dumps(receipt))["source_geometry"]["kind"] == "bezier"
    assert len(receipt["source_document_sha256"]) == 64
    assert receipt["target_before_sha256"] != receipt["target_after_sha256"]


@pytest.mark.parametrize("source_unit,target_unit", [("mm", "m"), ("m", "mm"),
                                                    ("ft_us", "ft"), ("in", "cm")])
def test_units_and_flat_metric_lengths(source_unit, target_unit):
    from adaptivecad.geom.metric_tools import unit_factor
    factor = unit_factor(source_unit, target_unit)
    src = model(Curve.line((0, 0, 0), (.25, 0, 0)), source_unit)
    target = MetricProject(NormalMetricPatch(radius=1000, length_scale=1000, unit=target_unit))
    p = preview_transfer(src, target, "source", "out", PlaneChartMapping())
    assert p.curve.controls[-1] == pytest.approx((.25*factor, 0))
    length = target.patch.bezier_length(p.curve.native()).value
    assert length == pytest.approx(src.get("source").length().value * factor)


def test_survey_feet_not_relabelled():
    src = model(Curve.line((0, 0, 0), (.25, 0, 0)), "ft_us")
    target = MetricProject(NormalMetricPatch(unit="ft"))
    p = preview_transfer(src, target, "source", "out", PlaneChartMapping())
    assert p.factor == pytest.approx(1.000002000004, rel=1e-13)
    assert p.factor != 1.0


def test_arbitrary_offset_rotated_plane():
    r = rotation((1, 2, 3), 1.2)
    origin = (20, -3, 15)
    u = tuple(r[i][0] for i in range(3))
    v = tuple(r[i][1] for i in range(3))
    controls = ((-.2, .1), (0, .3), (.4, -.1))
    pts = tuple(tuple(origin[k] + x*u[k] + y*v[k] for k in range(3)) for x, y in controls)
    p = preview_transfer(model(Curve("bezier", pts)), MetricProject(), "source", "out",
                         PlaneChartMapping(origin, u, v, 1e-12))
    np.testing.assert_allclose(p.curve.controls, controls, atol=1e-14)


def test_trim_then_plane_check_not_entire_original_controls():
    source = model(Curve.line((0, 0, 0), (20, 0, 0)).trim(.01, .02).reversed())
    p = preview_transfer(source, MetricProject(), "source", "out", PlaneChartMapping())
    np.testing.assert_allclose(p.curve.controls, ((.4, 0), (.2, 0)))


@pytest.mark.parametrize("kwargs", [{"x_axis": (0, 0, 0)}, {"y_axis": (1, 0, 0)},
                                    {"y_axis": (1, 1, 0)}, {"origin": (0, math.nan, 0)},
                                    {"origin": (0, 1)}, {"plane_tolerance": -1},
                                    {"plane_tolerance": math.inf}, {"plane_tolerance": True}])
def test_bad_mapping_rejected(kwargs):
    with pytest.raises((ValueError, TypeError)):
        PlaneChartMapping(**kwargs)


@pytest.mark.parametrize("shape", [Curve.arc(), Surface("extrude", Curve.arc(), vector=(0, 0, 1)),
                                   Curve("bezier", ((0, 0, 0),)*33)])
def test_no_silent_fitting_or_degree_reduction(shape):
    with pytest.raises(ValueError, match="supports"):
        preview_transfer(model(shape), MetricProject(), "source", "out", PlaneChartMapping())


def test_plane_and_control_hull_gates_are_not_sample_tests():
    outside = model(Curve("bezier", ((0, 0, 0), (2, 0, 0), (0, 0, 0))))
    with pytest.raises(ValueError, match="control hull"):
        preview_transfer(outside, MetricProject(), "source", "out", PlaneChartMapping())
    # endpoints lie in the plane but an interior control does not.
    nonplanar = model(Curve("bezier", ((0, 0, 0), (0, .2, .01), (.2, 0, 0))))
    with pytest.raises(ValueError, match="outside the declared plane"):
        preview_transfer(nonplanar, MetricProject(), "source", "out", PlaneChartMapping())


def test_explicit_residual_removal_is_reported():
    src = model(Curve.line((0, 0, 1e-7), (.25, 0, 1e-7)))
    p = preview_transfer(src, MetricProject(), "source", "out", PlaneChartMapping(plane_tolerance=1e-6))
    assert p.max_plane_residual == pytest.approx(1e-7)
    assert p.curve.controls[-1] == (.25, 0)
    assert p.receipt()["max_control_plane_residual_source_units"] == pytest.approx(1e-7)


def test_duplicate_invalid_name_capacity_and_no_clipping():
    src = model()
    existing = MetricCurve("out", ((0, 0),))
    target = MetricProject(curves=(existing,))
    with pytest.raises(ValueError, match="already exists"):
        preview_transfer(src, target, "source", "out", PlaneChartMapping())
    for name in ["", "\n", "a"*129]:
        with pytest.raises(ValueError):
            preview_transfer(src, target, "source", name, PlaneChartMapping())
    full = MetricProject(curves=tuple(MetricCurve(str(i), ((0, 0),)) for i in range(128)))
    with pytest.raises(ValueError):
        preview_transfer(src, full, "source", "out", PlaneChartMapping())
    assert target.curves == (existing,)


@pytest.mark.parametrize("side", ["source", "target", "forged"])
def test_stale_or_forged_preview_cannot_mutate_history(side):
    src = model()
    history = MetricHistory()
    p = preview_transfer(src, history.current, "source", "out", PlaneChartMapping())
    if side == "source":
        src = model(Curve.line((0, 0, 0), (.1, .1, 0)))
    elif side == "target":
        history.commit(history.current.put_curve(MetricCurve("other", ((0, 0),))))
    else:
        p = replace(p, candidate=MetricProject())
    state = (history.current, history.can_undo, history.can_redo, history.dirty)
    with pytest.raises(ValueError):
        commit_transfer(p, src, history)
    assert (history.current, history.can_undo, history.can_redo, history.dirty) == state


def test_curved_chart_is_not_claimed_isometric():
    src = model(Curve.line((-.4, .3, 0), (.4, .3, 0)))
    target = MetricProject(balanced_directional_patch())
    p = preview_transfer(src, target, "source", "out", PlaneChartMapping())
    assert p.candidate.patch is target.patch
    assert "no live link" in p.receipt()["note"]
    assert p.curve.controls == ((-.4, .3), (.4, .3))
