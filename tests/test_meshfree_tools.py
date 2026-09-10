import json
import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from adaptivecad.geom.directional_metric import NormalMetricPatch, balanced_directional_patch
from adaptivecad.geom.meshfree_metric_tools import (
    angle_between,
    area_radius,
    connection,
    disk_area,
    metric_derivatives,
    segment_length,
    trace_geodesic,
)
from adaptivecad.geom.meshfree_tools import (
    Curve,
    Surface,
    apply,
    compose,
    conversion_factor,
    matrix,
    polar_array,
    rectangular_array,
    reflection,
    rotation,
    scaling,
    translation,
    wireframe,
)
from adaptivecad.geom.tool_document import ToolDocument, ToolSession, strict_json


def eq(a, b, atol=1e-8):
    np.testing.assert_allclose(a, b, atol=atol, rtol=1e-9)


def profile():
    return Curve('bezier', ((0, 0, 0), (1, 2, 0), (3, -1, 2), (4, 0, 3)))


def surfaces():
    a = profile()
    b = a.transformed(compose(translation((0, 0, 5)), rotation((0, 0, 1), .3)))
    path = Curve('bezier', ((0, 0, 0), (0, 1, 2), (1, 0, 4)))
    return [Surface('extrude', a, vector=(0, 1, 5)),
            Surface('revolve', a, vector=(1, 2, 3), origin=(1, -2, .5), angle=2.3),
            Surface('loft', a, b), Surface('sweep', a, path)]


@pytest.mark.parametrize('t', [0., .13, .5, .9, 1.])
def test_curve_endpoints_trim_and_reverse(t):
    c = profile()
    eq(c.trim(.2, .8).evaluate(t), c.evaluate(.2+.6*t))
    eq(c.reversed().evaluate(t), c.evaluate(1-t))
    eq(c.reversed().derivative(t), -np.array(c.derivative(1-t)))
    a, b = c.split(.3)
    eq(a.evaluate(t), c.evaluate(.3*t))
    eq(b.evaluate(t), c.evaluate(.3+.7*t))


@pytest.mark.parametrize('curve', [profile(), Curve.arc(radius=2),
    Curve.arc(radius=2, sweep=-2.7).trim(.1, .9).transformed(scaling(3))])
def test_curve_analytic_derivatives(curve):
    h, t = 1e-5, .43
    p, d, dd = curve.jet(t)
    eq(d, (np.array(curve.evaluate(t+h))-curve.evaluate(t-h))/(2*h), 2e-8)
    eq(dd, (np.array(curve.derivative(t+h))-curve.derivative(t-h))/(2*h), 2e-7)
    eq(p, curve.evaluate(t))


def test_lengths_and_stations():
    assert Curve.line((0, 0, 0), (3, 4, 0)).length().value == pytest.approx(5)
    c = Curve.arc(radius=2)
    assert c.length().value == pytest.approx(4*math.pi)
    assert c.curvature(.3) == pytest.approx(.5)
    curved = profile()
    stations = curved.stations(6, abs_tol=1e-7)
    lengths = [curved.trim(a[0], b[0]).length().value for a, b in zip(stations, stations[1:])]
    eq(lengths, [curved.length().value/6]*6, 2e-7)
    assert curved.reversed().length().value == pytest.approx(curved.length().value)


def test_point_curve_and_degenerate_errors():
    c = Curve('bezier', ((1, 2, 3),))
    eq(c.jet(.4), ((1, 2, 3), (0, 0, 0), (0, 0, 0)))
    assert c.length().value == 0
    with pytest.raises(ValueError):
        c.curvature(.2)
    with pytest.raises(ValueError):
        c.stations(4)


@pytest.mark.parametrize('surface', surfaces())
def test_surface_partial_derivatives(surface):
    h, u, v = 1e-5, .37, .41
    p, du, dv, duu, duv, dvv = surface.jet(u, v)
    eq(du, (np.array(surface.evaluate(u+h, v))-surface.evaluate(u-h, v))/(2*h), 1e-7)
    eq(dv, (np.array(surface.evaluate(u, v+h))-surface.evaluate(u, v-h))/(2*h), 1e-7)
    eq(duu, (np.array(surface.jet(u+h, v)[1])-surface.jet(u-h, v)[1])/(2*h), 1e-6)
    eq(duv, (np.array(surface.jet(u, v+h)[1])-surface.jet(u, v-h)[1])/(2*h), 1e-6)
    eq(dvv, (np.array(surface.jet(u, v+h)[2])-surface.jet(u, v-h)[2])/(2*h), 1e-6)
    data = surface.differential(u, v)
    assert np.linalg.eigvalsh(data['metric']).min() > 0
    assert np.dot(data['normal'], du) == pytest.approx(0, abs=1e-10)
    eq(p, surface.evaluate(u, v))


def test_revolve_respects_axis_origin_and_partial_angle():
    c = Curve.line((1, 2, 0), (1, 2, 3))
    s = Surface('revolve', c, vector=(1, 0, 0), origin=(1, 0, 0), angle=math.pi/2)
    eq(s.evaluate(0, 1), (1, 0, 2))
    eq(s.evaluate(1, 1), (1, -3, 2))
    eq(s.evaluate(.3, 0), c.evaluate(.3))


def test_known_surface_curvatures_and_areas():
    cylinder = Surface('extrude', Curve.arc(radius=2), vector=(0, 0, 3))
    d = cylinder.differential(.3, .4)
    assert d['gaussian_curvature'] == pytest.approx(0)
    assert abs(d['mean_curvature']) == pytest.approx(.25)
    assert cylinder.area().value == pytest.approx(12*math.pi)
    sphere = Surface('revolve', Curve.arc(radius=2, sweep=math.pi), vector=(1, 0, 0))
    d = sphere.differential(.3, .4)
    assert d['gaussian_curvature'] == pytest.approx(.25)
    assert abs(d['mean_curvature']) == pytest.approx(.5)
    assert sphere.area().value == pytest.approx(16*math.pi, rel=1e-8)
    with pytest.raises(ValueError):
        sphere.differential(0, .4)
    torus = Surface('revolve', Curve.arc(center=(3, 0, 0), normal=(0, -1, 0)), vector=(0, 0, 1))
    for u in (.1, .3, .5, .9):
        cosine = math.cos(math.tau*u)
        assert torus.differential(u, .3)['gaussian_curvature'] == pytest.approx(cosine/(3+cosine))
    assert torus.area(abs_tol=1e-6).value == pytest.approx(12*math.pi**2, rel=1e-8)


def test_sweep_and_loft_boundary_contracts():
    loft, sweep = surfaces()[2:]
    for t in (0, .4, 1):
        eq(loft.evaluate(t, 0), loft.profile.evaluate(t))
        eq(loft.evaluate(t, 1), loft.guide.evaluate(t))
        eq(sweep.evaluate(t, 0), sweep.profile.evaluate(t))
        eq(np.array(sweep.evaluate(t, 1))-sweep.evaluate(t, 0),
           np.array(sweep.guide.evaluate(1))-sweep.guide.evaluate(0))


@pytest.mark.parametrize('entity', [profile(), Curve.arc(radius=2)] + surfaces())
def test_transforms_immutability_and_composition(entity):
    before = repr(entity)
    t = compose(translation((2, -3, 5)), rotation((1, 2, 3), .4))
    transformed = entity.transformed(t)
    parameter = (.3,) if isinstance(entity, Curve) else (.3, .6)
    eq(transformed.evaluate(*parameter), apply(t, entity.evaluate(*parameter)))
    eq(entity.transformed(reflection()).transformed(reflection()).evaluate(*parameter), entity.evaluate(*parameter))
    assert repr(entity) == before
    with pytest.raises(FrozenInstanceError):
        entity.kind = 'bad'


def test_surface_scale_and_reflection_curvature():
    s = Surface('revolve', Curve.arc(radius=2, sweep=math.pi), vector=(1, 0, 0))
    original = s.differential(.2, .4)
    d = s.transformed(scaling(3)).differential(.2, .4)
    assert d['gaussian_curvature'] == pytest.approx(original['gaussian_curvature']/9)
    assert d['mean_curvature'] == pytest.approx(original['mean_curvature']/3)
    reflected = s.transformed(reflection()).differential(.2, .4)
    assert reflected['gaussian_curvature'] == pytest.approx(original['gaussian_curvature'])
    assert reflected['mean_curvature'] == pytest.approx(-original['mean_curvature'])


def test_arrays_no_duplicate_full_turn_seam():
    c = Curve.line((1, 0, 0), (2, 0, 0))
    p = polar_array(c, 4)
    eq([x.evaluate(0) for x in p], ((1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)))
    partial = polar_array(c, 3, math.pi)
    eq(partial[-1].evaluate(0), (-1, 0, 0))
    r = rectangular_array(c, 2, 3, (0, 5, 0), (2, 0, 0))
    assert len(r) == 6
    eq(r[-1].evaluate(0), (5, 5, 0))
    with pytest.raises(ValueError):
        rectangular_array(c, 40, 40)


@pytest.mark.parametrize('operation', [
    lambda: Curve('unknown', ((0, 0, 0),)), lambda: Curve('bezier', ()),
    lambda: Curve.line((0, float('nan'), 0), (0, 0, 0)),
    lambda: Curve.arc(radius=-1), lambda: Curve.arc(normal=(0, 0, 0)),
    lambda: Curve.arc(normal=(1, 0, 0)), lambda: Curve.arc(sweep=8),
    lambda: profile().trim(.2, .2), lambda: profile().split(1),
    lambda: profile().jet(1.1), lambda: scaling(0), lambda: scaling(True),
    lambda: matrix(((1, 2),)), lambda: Surface('revolve', profile(), angle=0),
    lambda: Surface('loft', profile()), lambda: Surface('extrude', profile(), vector=(0, 0, 0)),
    lambda: wireframe(profile(), samples=1), lambda: conversion_factor('feet', 'mm'),
])
def test_bad_geometry_rejected(operation):
    with pytest.raises((ValueError, TypeError)):
        operation()


def test_document_and_command_transactions(tmp_path):
    s = ToolSession()
    commands = [{'op': 'line', 'name': 'p', 'start': [2, 0, 0], 'end': [2, 0, 3]},
                {'op': 'revolve', 'name': 'cylinder', 'source': 'p', 'axis': [0, 0, 1], 'angle': math.tau}]
    s.execute_many(commands)
    doc = s.document
    assert len(doc.entities) == 2
    assert s.undo() and len(s.document.entities) == 0
    assert s.redo() and s.document == doc
    assert ToolDocument.from_json(doc.to_json()) == doc
    path = tmp_path/'part.json'
    doc.save(path)
    assert ToolDocument.load(path) == doc
    with pytest.raises(FileExistsError):
        doc.save(path)
    with pytest.raises(ValueError):
        s.execute_many([{'op': 'copy', 'name': 'new', 'source': 'p'}, commands[0]])
    assert s.document == doc
    with pytest.raises(ValueError):
        s.execute({'op': 'scale', 'source': 'p', 'name': 'p', 'factor': 0, 'replace': True})
    assert s.document == doc
    s.execute({'op': 'move', 'source': 'p', 'name': 'p', 'delta': [1, 0, 0], 'replace': True})
    eq(s.document.get('cylinder').evaluate(0, 0), (2, 0, 0))  # no hidden live references
    assert not s.redo()


@pytest.mark.parametrize('op, extra', [
    ('copy', {}), ('move', {'delta': [1, 2, 3]}),
    ('rotate', {'axis': [0, 1, 0], 'angle': .5}), ('scale', {'factor': 2}),
    ('mirror', {'normal': [1, 0, 0]}), ('trim', {'start': .1, 'stop': .8}),
    ('reverse', {}), ('split', {'parameter': .4}),
    ('rectangular_array', {'rows': 2, 'columns': 3}),
    ('polar_array', {'instances': 4}),
])
def test_edit_commands(op, extra):
    s = ToolSession(ToolDocument(entities=(('p', profile()),)))
    s.execute(dict(op=op, name='output', source='p', **extra))
    assert len(s.document.entities) >= 2
    assert ToolDocument.from_json(s.document.to_json()) == s.document
    assert s.undo() and len(s.document.entities) == 1


def test_units_convert_geometry_and_metric():
    patch = NormalMetricPatch(((0, 0, .2),), unit='ft_us')
    doc = ToolDocument('ft_us', (('p', Curve.line((0, 0, 0), (1, 0, 0))),), patch)
    result = doc.converted('m')
    factor = 1200/3937
    assert result.get('p').length().value == pytest.approx(factor)
    assert result.metric.radius == pytest.approx(factor)
    assert result.metric.gaussian_curvature(0, 0) == pytest.approx(patch.gaussian_curvature(0, 0)/factor**2)
    assert conversion_factor('ft', 'm') == .3048
    assert conversion_factor('ft_us', 'm') != conversion_factor('ft', 'm')
    eq(result.converted('ft_us').get('p').evaluate(1), (1, 0, 0))
    with pytest.raises(ValueError):
        ToolDocument('mm', metric=patch)


@pytest.mark.parametrize('text', ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '[]',
    '{"schema":"adaptivecad.meshfree_tool_document","version":true,"unit":"mm","entities":[],"metric":null}'])
def test_bad_documents(text):
    with pytest.raises(ValueError):
        ToolDocument.from_json(text)


def test_json_unknown_keys_and_commands_rejected():
    obj = strict_json(ToolDocument().to_json())
    obj['executable'] = 'not supported'
    with pytest.raises(ValueError):
        ToolDocument.from_json(json.dumps(obj))
    s = ToolSession()
    with pytest.raises(ValueError):
        s.execute({'op': 'eval', 'code': '1+1'})
    with pytest.raises(ValueError):
        s.execute({'op': 'arc', 'name': 'a', 'colour': 'red'})


@pytest.mark.parametrize('xy', [(0, 0), (.1, -.3), (.4, .2)])
def test_metric_derivatives_and_connection(xy):
    p = balanced_directional_patch()
    analytical = metric_derivatives(p, *xy)
    h = 1e-6
    for k in range(2):
        a, b = list(xy), list(xy)
        a[k] += h
        b[k] -= h
        eq(analytical[k], (np.array(p.metric(*a))-p.metric(*b))/(2*h), 1e-9)
    gamma = np.array(connection(p, *xy))
    eq(gamma, gamma.transpose(0, 2, 1))
    g = np.array(p.metric(*xy))
    for k in range(2):
        eq(analytical[k], gamma[:, k, :].T@g + g@gamma[:, k, :])


def test_metric_measurement_controls():
    p = NormalMetricPatch(radius=2)
    assert segment_length(p, (0, 0), (1, 1)).value == pytest.approx(math.sqrt(2))
    assert angle_between(p, (0, 0), (1, 0), (0, 1)) == pytest.approx(math.pi/2)
    assert disk_area(p, 1).value == pytest.approx(math.pi)
    assert area_radius(p, math.pi*.3**2) == pytest.approx(.3, abs=1e-7)
    balanced = balanced_directional_patch()
    assert disk_area(balanced, .8).value == pytest.approx(math.pi*.8**2, abs=1e-8)
    assert area_radius(p, 0) == 0
    with pytest.raises(ValueError):
        area_radius(p, 100)
    with pytest.raises(ValueError):
        angle_between(p, (0, 0), (0, 0), (1, 0))


def test_flat_geodesic_and_parallel_transport():
    p = NormalMetricPatch(radius=4)
    result = trace_geodesic(p, (.1, .2), (3, 4), 1, transport=(1, 2))
    eq(result.positions[-1], (.7, 1.))
    eq(result.tangents[-1], (.6, .8))
    eq(result.transported_vectors[-1], (1, 2))
    assert result.arclengths[-1] == result.length == 1
    assert result.max_speed_drift < 1e-12


def test_curved_geodesic_reversal_scaling_and_transport():
    p = balanced_directional_patch()
    result = trace_geodesic(p, (-.2, .2), (1, .1), .5, transport=(0, 1), tolerance=1e-10)
    back = trace_geodesic(p, result.positions[-1], -np.array(result.tangents[-1]), .5, tolerance=1e-10)
    eq(back.positions[-1], (-.2, .2), 2e-8)
    scaled = trace_geodesic(p.scaled(1000), (-200, 200), (1, .1), 500, tolerance=1e-10)
    eq(np.array(scaled.positions[-1])/1000, result.positions[-1], 2e-9)
    lengths = [p.speed(*xy, *w) for xy, w in zip(result.positions, result.transported_vectors)]
    eq(lengths, [lengths[0]]*len(lengths), 2e-8)
    assert result.max_speed_drift < 1e-8


def test_geodesic_against_independent_scipy_solver():
    integrate = pytest.importorskip('scipy.integrate')
    p = balanced_directional_patch()
    start, velocity = (-.3, .25), (1, -.15)
    speed = p.speed(*start, *velocity)
    y0 = start + tuple(v/speed for v in velocity)
    # Separate solver and finite-difference metric derivatives.
    def rhs(_, y):
        xy, v = y[:2], y[2:]
        step = 1e-5
        dg = []
        for k in range(2):
            d = np.zeros(2)
            d[k] = step
            dg.append((np.array(p.metric(*(xy+d)))-p.metric(*(xy-d)))/(2*step))
        dg = np.array(dg)
        inv = np.linalg.inv(p.metric(*xy))
        gamma = np.einsum('ka,aij->kij', inv, .5*(dg.transpose(1, 0, 2)+dg.transpose(1, 2, 0)-dg))
        return np.r_[v, -np.einsum('kij,i,j->k', gamma, v, v)]
    reference = integrate.solve_ivp(rhs, (0, .6), y0, method='DOP853', rtol=1e-11, atol=1e-12)
    actual = trace_geodesic(p, start, velocity, .6, tolerance=1e-10)
    assert reference.success
    eq(actual.positions[-1], reference.y[:2, -1], 2e-8)
    eq(actual.tangents[-1], reference.y[2:, -1], 2e-8)


@pytest.mark.parametrize('kwargs', [dict(direction=(0, 0)), dict(length=-1), dict(tolerance=0),
                                   dict(max_steps=True), dict(max_steps=1), dict(length=4)])
def test_invalid_or_incomplete_geodesic_is_not_success(kwargs):
    args = dict(start=(0, 0), direction=(1, 0), length=.5)
    args.update(kwargs)
    with pytest.raises((ValueError, ArithmeticError)):
        trace_geodesic(NormalMetricPatch(), **args)
