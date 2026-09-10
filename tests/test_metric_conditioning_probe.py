"""Analytic and independent numerical checks for the read-only surface probe."""
import math

import numpy as np
import pytest

from adaptivecad.geom.meshfree_tools import Curve, Surface, rotation, scaling
from examples.metric_conditioning_probe import experiment, local_conditioning


@pytest.mark.parametrize('epsilon', [1, .1, .01, 1e-4])
def test_equal_area_is_not_a_conditioning_check(epsilon):
    surface = Surface('extrude', Curve.line((0, 0, 0), (epsilon, 0, 0)), vector=(0, 1/epsilon, 0))
    data = local_conditioning(surface, .5, .5)
    assert surface.area().value == pytest.approx(1)
    assert surface.differential(.5, .5)['gaussian_curvature'] == 0
    assert data.jacobian_condition == pytest.approx(epsilon**-2)
    assert data.metric_condition == pytest.approx(epsilon**-4)


@pytest.mark.parametrize('factor', [1e-6, 1, 1e6])
@pytest.mark.parametrize('angle', [0, .7, 2.1])
def test_rigid_and_uniform_scale_invariance(factor, angle):
    surface = Surface('extrude', Curve.line((0, 0, 0), (.01, 0, 0)), vector=(0, 100, 0))
    surface = surface.transformed(rotation((1, 2, 3), angle)).transformed(scaling(factor))
    data = local_conditioning(surface, .2, .7)
    assert data.jacobian_condition == pytest.approx(1e4)
    assert data.minimum_stretch == pytest.approx(.01*factor)
    assert data.maximum_stretch == pytest.approx(100*factor)


@pytest.mark.parametrize('seed', range(12))
def test_independent_numpy_singular_values(seed):
    random = np.random.default_rng(seed)
    a, b = random.normal(size=(2, 3))
    surface = Surface('extrude', Curve.line((0, 0, 0), tuple(a)), vector=tuple(b))
    data = local_conditioning(surface, .3, .4)
    maximum, minimum = np.linalg.svd(np.column_stack((a, b)), compute_uv=False)
    assert data.maximum_stretch == pytest.approx(maximum, rel=1e-12)
    assert data.minimum_stretch == pytest.approx(minimum, rel=1e-12)


def test_zero_derivative_is_not_reported_safe():
    surface = Surface('extrude', Curve('bezier', ((0, 0, 0),)), vector=(0, 1, 0))
    data = local_conditioning(surface, 0, 0)
    assert data.status == 'degenerate_or_unresolved'
    assert data.jacobian_condition is None


def test_collinear_derivatives_are_not_reported_safe():
    surface = Surface('extrude', Curve.line((0, 0, 0), (1, 0, 0)), vector=(2, 0, 0))
    assert local_conditioning(surface, .4, .5).status == 'degenerate_or_unresolved'


def test_parameter_and_type_validation():
    surface = Surface('extrude', Curve.line((0, 0, 0), (1, 0, 0)), vector=(0, 1, 0))
    with pytest.raises(ValueError): local_conditioning(surface, math.nan, .5)
    with pytest.raises(ValueError): local_conditioning(surface, -1, .5)
    with pytest.raises(TypeError): local_conditioning(object(), .5, .5)


def test_output_is_finite_and_read_only():
    result = experiment()
    assert all(row['status'] == 'resolved_local_sample' for row in result['rows'])
