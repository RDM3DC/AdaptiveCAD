import math

import numpy as np
import pytest

from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.geom.directional_metric import NormalMetricPatch, balanced_directional_patch
from adaptivecad.geom.metric_geodesic import trace_geodesic
from adaptivecad.geom.metric_tools import (
    analyze_bezier,
    angle_between,
    christoffel,
    disk_area,
    inner_product,
    metric_derivatives,
    segment_length,
    unit_factor,
)
from adaptivecad.linalg import Vec3


@pytest.mark.parametrize('xy', [(0,0), (.2,.3), (-.4,.2)])
def test_derivatives_against_finite_differences(xy):
    p = balanced_directional_patch()
    dg = np.array(metric_derivatives(p, *xy))
    h = 1e-5
    for k in range(2):
        a, b = list(xy), list(xy)
        a[k] += h; b[k] -= h
        fd = (np.array(p.metric(*a)) - np.array(p.metric(*b))) / (2*h)
        np.testing.assert_allclose(dg[k], fd, atol=2e-10)


def test_metric_compatibility_and_torsion():
    p = balanced_directional_patch()
    g = np.array(p.metric(.3,.5)); dg = np.array(metric_derivatives(p,.3,.5))
    gamma = np.array(christoffel(p,.3,.5))
    np.testing.assert_allclose(gamma, gamma.swapaxes(1,2), atol=1e-15)
    for k in range(2):
        for i in range(2):
            for j in range(2):
                assert dg[k,i,j] == pytest.approx(sum(gamma[l,k,i]*g[l,j] + gamma[l,k,j]*g[i,l]
                                                    for l in range(2)), abs=2e-15)


@pytest.mark.parametrize('r', [0,.1,.5,1])
def test_balanced_area(r):
    assert disk_area(balanced_directional_patch(), r).value == pytest.approx(math.pi*r*r, abs=2e-10)


def test_radial_area_analytic():
    c, r = .2, .7
    p = NormalMetricPatch(((0,0,c),))
    exact = 2*math.pi*((1+c*r*r)**1.5 - 1)/(3*c)
    assert disk_area(p,r).value == pytest.approx(exact, abs=1e-9)


def test_segment_not_claimed_shortest_and_angles():
    p = balanced_directional_patch()
    assert segment_length(p,(0,0),(.3,.4)).value == pytest.approx(.5)
    assert angle_between(p,(.4,.2),(1,2),(-2,1)) != pytest.approx(math.pi/2, abs=1e-5)
    assert angle_between(p,(0,0),(1,0),(0,1)) == pytest.approx(math.pi/2)
    with pytest.raises(ValueError): angle_between(p,(0,0),(0,0),(1,0))


def test_units_distinguish_survey_and_international_feet():
    assert unit_factor('ft_us','m') == 1200/3937
    assert unit_factor('ft','mm') == 304.8
    assert unit_factor('ft_us','ft') != 1.0
    with pytest.raises(ValueError): unit_factor('feet','mm')


def test_curve_curvatures():
    p = NormalMetricPatch()
    c = BezierCurve([Vec3(0,0,0),Vec3(.2,0,0),Vec3(.4,.2,0)])
    a = analyze_bezier(p,c,0)
    assert a.geodesic_curvature == pytest.approx(2.5)
    stationary = BezierCurve([Vec3(0,0,0)])
    assert analyze_bezier(p,stationary,.5).geodesic_curvature is None
    radial = BezierCurve([Vec3(0,0,0),Vec3(.3,.4,0)])
    assert analyze_bezier(balanced_directional_patch(),radial,.5).geodesic_curvature == pytest.approx(0,abs=1e-14)


def test_geodesic_flat_and_parallel_transport():
    t = trace_geodesic(NormalMetricPatch(), (0,0),(3,4), .7, transport=(2,-1))
    assert t.status == 'complete'
    assert t.points[-1] == pytest.approx((.42,.56), abs=1e-13)
    assert t.transported[-1] == pytest.approx((2,-1))
    assert t.distances[-1] == pytest.approx(.7)


def test_geodesic_boundary_and_inward_start():
    t = trace_geodesic(NormalMetricPatch(), (0,0),(1,0), 2)
    assert t.status == 'boundary'
    assert t.points[-1][0] == pytest.approx(1,abs=2e-8)
    assert t.distances[-1] < t.requested_length
    t = trace_geodesic(NormalMetricPatch(), (1,0),(-1,0), .1)
    assert t.points[-1] == pytest.approx((.9,0))


def test_geodesic_metric_conservation_reversal_and_scale():
    p = balanced_directional_patch()
    t = trace_geodesic(p, (-.5,.2), (1,.2), .8, tolerance=1e-10)
    assert t.status == 'complete'
    assert t.max_speed_error < 1e-8
    assert t.max_transport_norm_error < 1e-8
    b = trace_geodesic(p,t.points[-1],tuple(-x for x in t.velocities[-1]),.8,tolerance=1e-10)
    assert b.points[-1] == pytest.approx(t.points[0],abs=1e-8)
    factor=304.8
    q=trace_geodesic(p.scaled(factor),(-.5*factor,.2*factor),(1,.2),.8*factor,tolerance=1e-10)
    assert np.array(q.points)/factor == pytest.approx(np.array(t.points),abs=1e-9)
    norms=[inner_product(p, xy, w, w) for xy,w in zip(t.points,t.transported)]
    assert max(norms)-min(norms) < 2e-8


def test_geodesic_independent_scipy_integrator():
    from scipy.integrate import solve_ivp
    p=balanced_directional_patch(); start=(-.5,.2); v=np.array([1.,.2]); v/=p.speed(*start,*v)
    def rhs(s,z):
        gamma=np.array(christoffel(p,*z[:2]))
        return np.r_[z[2:], -np.einsum('kij,i,j->k',gamma,z[2:],z[2:])]
    ref=solve_ivp(rhs,(0,.8),[*start,*v],rtol=1e-12,atol=1e-13,method='DOP853')
    assert ref.success
    t=trace_geodesic(p,start,(1,.2),.8,tolerance=1e-10)
    assert t.points[-1] == pytest.approx(ref.y[:2,-1],abs=2e-9)


@pytest.mark.parametrize('kwargs', [{'length':-1},{'direction':(0,0)}, {'start':(2,0)},
                                    {'max_steps':True},{'tolerance':0}, {'initial_step':0}])
def test_bad_geodesic_inputs(kwargs):
    args=dict(patch=NormalMetricPatch(),start=(0,0),direction=(1,0),length=.2)
    args.update(kwargs)
    with pytest.raises(ValueError): trace_geodesic(**args)


def test_budget_is_failure_not_success():
    from adaptivecad.geom.directional_metric import IntegrationError
    with pytest.raises(IntegrationError): trace_geodesic(NormalMetricPatch(),(0,0),(1,0),.8,max_steps=1)


def test_small_disk_and_huge_requested_length_do_not_fake_boundary():
    p = NormalMetricPatch(radius=1e-10)
    t = trace_geodesic(p, (0, 0), (1, 0), 5e-11)
    assert t.status == "complete"
    assert t.distances[-1] == pytest.approx(5e-11, rel=1e-7, abs=1e-24)
    t = trace_geodesic(NormalMetricPatch(), (0, 0), (1, 0), 1e20)
    assert t.status == "boundary"
    assert t.distances[-1] == pytest.approx(1, abs=2e-8)


def test_boundary_tangent_and_zero_length():
    t = trace_geodesic(NormalMetricPatch(), (1, 0), (0, 1), .1)
    assert t.status == "boundary" and t.distances[-1] == 0
    t = trace_geodesic(NormalMetricPatch(), (1, 0), (1, 0), 0)
    assert t.status == "complete" and len(t.points) == 1
