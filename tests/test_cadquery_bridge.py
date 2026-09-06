"""Focused tests for the optional, triangle-free CadQuery bridge."""
import math
from pathlib import Path
import subprocess
import sys

import pytest

cq = pytest.importorskip('cadquery')
from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.geom.cadquery_bridge import (
    bezier_bridge_error, bezier_edge, bezier_wire, export_brep_clean,
    triangulated_face_count,
)
from adaptivecad.linalg import Vec3


def curve(points):
    return BezierCurve([Vec3(*p) for p in points])


@pytest.mark.parametrize('degree', [1, 2, 3, 5, 10])
def test_parameter_preserving_transfer(degree):
    c = curve([(i * 17.3, math.sin(i) * 41, math.cos(i) * 7) for i in range(degree+1)])
    edge = bezier_edge(c)
    assert edge.isValid()
    assert bezier_bridge_error(c, edge, samples=101) < 1e-10


def test_stationary_midpoint_is_not_a_constant_curve():
    c = curve([(0, 0, 0), (1, 0, 0), (0, 0, 0), (1, 0, 0)])
    assert c.derivative(.5).norm() == 0
    assert bezier_edge(c).isValid()


@pytest.mark.parametrize('points', [[], [(0, 0, 0)], [(1, 1, 1)]*4,
    [(0, 0, 0), (float('nan'), 1, 0)], [(i, 0, 0) for i in range(27)]])
def test_invalid_poles_rejected(points):
    with pytest.raises(ValueError):
        bezier_edge(curve(points))


@pytest.mark.parametrize('tolerance', [0, -1, float('inf'), float('nan')])
def test_invalid_tolerance_rejected(tolerance):
    with pytest.raises(ValueError):
        bezier_edge(curve([(0, 0, 0), (1, 1, 0)]), tolerance=tolerance)


def square(z):
    points = [(0, 0, z), (30, 0, z), (30, 20, z), (0, 20, z), (0, 0, z)]
    return [curve([a, b]) for a, b in zip(points, points[1:])]


def test_closed_wire_and_disconnected_spans():
    spans = square(0)
    assert bezier_wire(spans, closed=True).IsClosed()
    with pytest.raises(ValueError, match='connected'):
        bezier_wire([spans[0], spans[2]])
    with pytest.raises(ValueError, match='connected'):
        bezier_wire(spans[:-1], closed=True)
    with pytest.raises(ValueError):
        bezier_wire([])


def test_clean_export_does_not_mutate_display_mesh(tmp_path):
    shape = cq.Workplane('XY').box(20, 30, 40).val()
    shape.tessellate(.1)
    before = triangulated_face_count(shape)
    assert before > 0
    path = export_brep_clean(shape, tmp_path / 'nested' / 'part.brep')
    restored = cq.Shape.importBrep(str(path))
    assert triangulated_face_count(shape) == before
    assert triangulated_face_count(restored) == 0
    assert restored.isValid()
    assert restored.Volume() == pytest.approx(shape.Volume())


@pytest.mark.parametrize('scale', [.1, 1, 2])
def test_loft_brep_step_roundtrip(tmp_path, scale):
    shape = cq.Solid.makeLoft([bezier_wire(square(z), closed=True) for z in (0, 15)])
    shape = shape.scale(scale)
    path = export_brep_clean(shape, tmp_path / 'loft.brep')
    native = cq.Shape.importBrep(str(path))
    assembly = cq.Assembly(name='bridge_test')
    assembly.add(native, name='Bezier_loft')
    assembly.export(str(tmp_path / 'loft.step'), 'STEP')
    restored = cq.importers.importStep(str(tmp_path / 'loft.step')).val()
    assert restored.isValid()
    assert len(restored.Solids()) == 1
    assert restored.Volume() == pytest.approx(30*20*15*scale**3, rel=1e-8)
    assert triangulated_face_count(native) == 0


def test_optional_dependency_stays_lazy():
    code = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'cadquery' or name.startswith('OCP'):
        raise ImportError('disabled for test')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from adaptivecad.geom.cadquery_bridge import bezier_edge
from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.linalg import Vec3
try:
    bezier_edge(BezierCurve([Vec3(0,0,0),Vec3(1,0,0)]))
except ImportError as exc:
    assert 'optional bridge' in str(exc)
else:
    raise AssertionError('expected missing-dependency message')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
