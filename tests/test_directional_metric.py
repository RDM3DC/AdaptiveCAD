"""Focused regression tests; no GUI or OpenCascade is required."""

import json
import math

import numpy as np
import pytest

from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.geom.directional_metric import (
    IntegrationError,
    NormalMetricPatch,
    _integrate,
    balanced_directional_patch,
)
from adaptivecad.linalg import Vec3


@pytest.mark.parametrize("xy", [(0, 0), (0.7, 0), (0, -0.6), (0.2, 0.3)])
def test_flat_control(xy):
    p = NormalMetricPatch()
    assert p.metric(*xy) == ((1, 0), (0, 1))
    assert p.gaussian_curvature(*xy) == 0
    assert p.speed(*xy, 3, 4) == pytest.approx(5)
    assert p.circle_pi(math.hypot(*xy)).value == pytest.approx(math.pi)


@pytest.mark.parametrize("theta", [0.0, math.pi / 4, math.pi / 2, -1.3, 2.7])
def test_balanced_exact_formulas(theta):
    p = balanced_directional_patch()
    r, e = 0.75, 0.2
    c = math.cos(2 * theta)
    assert p.directional_pi(r, theta) == pytest.approx(math.pi * (1 + e * r**4 * c))
    expected = -20 * e * r**2 * c / (1 + e * r**4 * c)
    assert p.gaussian_curvature(r * math.cos(theta), r * math.sin(theta)) == pytest.approx(expected, abs=2e-14)
    assert p.circle_pi(r).value == pytest.approx(math.pi, abs=1e-11)


def test_full_circle_is_not_flatness_test():
    p = balanced_directional_patch()
    assert p.circle_pi(0.75).value == pytest.approx(math.pi, abs=1e-11)
    assert p.gaussian_curvature(0.75, 0) < -2
    assert p.gaussian_curvature(0, 0.75) > 2
    first = p.sector_length(0.75, 0, math.pi / 4).value
    second = p.sector_length(0.75, math.pi / 4, math.pi / 2).value
    assert first > second
    # Analytic sector integral of r*(1+e*r^4*cos(2 theta)).
    assert first == pytest.approx(0.75 * (math.pi / 4 + 0.2 * 0.75**4 / 2))


@pytest.mark.parametrize("c", [-0.1, 0.0, 0.3])
def test_constant_A_curvature_and_origin(c):
    p = NormalMetricPatch(((0, 0, c),), length_scale=2, radius=2)
    assert p.metric(0, 0) == ((1, 0), (0, 1))
    assert p.gaussian_curvature(0, 0) == pytest.approx(-3 * c / 4)
    assert p.directional_pi(0, 1.7) == math.pi
    r = 0.6
    F = 1 + c * (r / 2)**2
    assert p.gaussian_curvature(r, 0) == pytest.approx((-3 * c / F + (r / 2)**2 * c**2 / F**2) / 4)


def test_cross_term_and_radial_eigenvalue():
    p = balanced_directional_patch()
    point = np.array([0.4, 0.2])
    g = np.array(p.metric(*point))
    assert g[0, 1] != 0
    assert np.allclose(g @ point, point)
    assert np.linalg.eigvalsh(g).min() > 0
    for v in ([1, 2], [-3, 0.5]):
        assert p.speed(*point, *v)**2 == pytest.approx(np.array(v) @ g @ v)


def test_curvature_independent_polar_second_difference():
    p = NormalMetricPatch(((0, 0, 0.2), (1, 0, 0.08), (0, 2, -0.05)))
    for r, theta in ((0.4, 0.3), (0.7, 1.2), (0.2, 2.1)):
        h = 2e-4
        def J(s):
            return s * p.directional_pi(s, theta) / math.pi
        jpp = (-J(r + 2*h) + 16*J(r+h) - 30*J(r) + 16*J(r-h) - J(r-2*h)) / (12*h*h)
        expected = -jpp / J(r)
        assert p.gaussian_curvature(r*math.cos(theta), r*math.sin(theta)) == pytest.approx(expected, abs=2e-7)


@pytest.mark.parametrize("factor", [1e-3, 25.4, 1000.0, 1200.0 / 3937.0])
def test_scale_covariance(factor):
    p = balanced_directional_patch()
    q = p.scaled(factor, unit="converted")
    x, y = 0.3, 0.5
    assert np.allclose(q.metric(x*factor, y*factor), p.metric(x, y))
    assert q.gaussian_curvature(x*factor, y*factor) * factor**2 == pytest.approx(p.gaussian_curvature(x, y))
    assert q.sector_length(0.6*factor, 0, 1).value == pytest.approx(factor * p.sector_length(0.6, 0, 1).value)
    assert q.unit == "converted"


def test_native_bezier_flat_and_radial_lengths():
    p = balanced_directional_patch()
    radial = BezierCurve([Vec3(0, 0, 0), Vec3(0.2, 0.1, 0), Vec3(0.6, 0.3, 0)])
    assert p.bezier_length(radial).value == pytest.approx(math.hypot(0.6, 0.3))
    diagonal = BezierCurve([Vec3(-0.3, 0.2, 0), Vec3(0.4, -0.5, 0)])
    assert NormalMetricPatch().bezier_length(diagonal).value == pytest.approx(math.hypot(0.7, -0.7))


def test_native_bezier_subdivision_and_reversal():
    p = balanced_directional_patch()
    curve = BezierCurve([Vec3(-0.6, 0.2, 0), Vec3(-0.2, 0.65, 0), Vec3(0.3, -0.4, 0), Vec3(0.6, 0.2, 0)])
    total = p.bezier_length(curve, abs_tol=1e-11, rel_tol=1e-11)
    left, right = curve.subdivide(0.37)
    split = p.bezier_length(left).value + p.bezier_length(right).value
    assert total.value == pytest.approx(split, abs=2e-9)
    assert total.value == pytest.approx(p.bezier_length(BezierCurve(list(reversed(curve.control_points)))).value, abs=2e-9)
    assert abs(total.value - NormalMetricPatch().bezier_length(curve).value) > 1e-4


def test_stationary_bezier_and_constant():
    p = NormalMetricPatch()
    stationary = BezierCurve([Vec3(0, 0, 0), Vec3(0.2, 0, 0), Vec3(0, 0, 0)])
    assert p.bezier_length(stationary).value == pytest.approx(0.2)
    assert p.bezier_length(BezierCurve([Vec3(0.1, 0.2, 0)])).value == 0


@pytest.mark.parametrize("points", [[], [Vec3(0, 0, 1)], [Vec3(1.1, 0, 0)], [Vec3(float('nan'), 0, 0)]])
def test_native_bezier_invalid(points):
    with pytest.raises(ValueError):
        NormalMetricPatch().bezier_length(BezierCurve(points))


def test_roundtrip_and_sorted_representation():
    p = balanced_directional_patch()
    q = NormalMetricPatch.from_json(p.to_json())
    assert p == q
    assert q.to_json() == p.to_json()
    assert q.metric(0.3, 0.2) == p.metric(0.3, 0.2)
    assert 'triangles' not in p.to_json()
    assert NormalMetricPatch(list(reversed(p.terms))) == p


@pytest.mark.parametrize("change", [
    {"version": 2}, {"version": True}, {"schema": "other"}, {"unit": ""},
    {"radius": -1}, {"length_scale": 0}, {"terms": [[1, 0, float('nan')]]},
    {"terms": [[1, 0, 0.1], [1, 0, 0.2]]}, {"terms": [[-1, 0, 1]]},
    {"terms": [[True, 0, 1]]}, {"terms": [[33, 0, 1]]}, {"extra": 1},
    {"terms": "__import__('os')"},
])
def test_bad_json_schema(change):
    obj = json.loads(NormalMetricPatch().to_json())
    obj.update(change)
    with pytest.raises(ValueError):
        NormalMetricPatch.from_json(json.dumps(obj))


def test_duplicate_json_keys_rejected():
    s = NormalMetricPatch().to_json().replace('"version": 1', '"version": 1, "version": 1')
    with pytest.raises(ValueError):
        NormalMetricPatch.from_json(s)


@pytest.mark.parametrize("kwargs", [
    {"length_scale": float('inf')}, {"radius": float('nan')}, {"length_scale": True},
    {"terms": ((0, 0, -2),)}, {"terms": ((1, 0, 3),)}, {"unit": None},
])
def test_invalid_patch(kwargs):
    with pytest.raises(ValueError):
        NormalMetricPatch(**kwargs)


def test_conservative_bound_not_point_sampling():
    # Negative odd-power pocket cannot be missed just because the origin is fine.
    with pytest.raises(ValueError, match="Positivity"):
        NormalMetricPatch(((31, 0, 2),))
    p = balanced_directional_patch()
    for theta in np.linspace(0, 2 * math.pi, 33):
        assert (p.directional_pi(0.99, theta) / math.pi)**2 >= p.positivity_lower_bound()


@pytest.mark.parametrize("r,theta", [(-0.1, 0), (1.1, 0), (0, float('nan')), (float('inf'), 0)])
def test_invalid_directional_point(r, theta):
    with pytest.raises(ValueError):
        NormalMetricPatch().directional_pi(r, theta)


def test_grid_axis_order_and_values():
    p = balanced_directional_patch()
    xs, ys = np.linspace(-0.4, 0.4, 5), np.linspace(-0.3, 0.3, 4)
    g = p.metric_grid(xs, ys)
    assert g.shape == (5, 4, 2, 2)
    assert np.allclose(g[3, 2], p.metric(xs[3], ys[2]))
    assert np.linalg.eigvalsh(g).min() > 0


@pytest.mark.parametrize("xs,ys", [([0], [0, 0.1]), ([0.1, 0], [0, 0.1]),
                                    ([0, 0.1, 0.4], [0, 0.1]), ([0, 1], [0, 1]),
                                    ([0, float('inf')], [0, 0.1])])
def test_invalid_grids(xs, ys):
    with pytest.raises(ValueError):
        NormalMetricPatch().metric_grid(xs, ys)


def test_quadrature_tolerances_and_failure():
    result = _integrate(lambda x: math.exp(x), 0, 1, 1e-10, 0)
    assert result.value == pytest.approx(math.e - 1, abs=1e-10)
    assert result.estimated_error <= 1e-10
    with pytest.raises(IntegrationError):
        _integrate(math.exp, 0, 1, 1e-16, 0, panels=1, max_depth=0)
    for kwargs in ({"abs_tol": 0}, {"rel_tol": -1}, {"max_depth": -1}):
        with pytest.raises(ValueError):
            NormalMetricPatch().sector_length(0.5, **kwargs)
    with pytest.raises(ValueError):
        NormalMetricPatch().sector_length(0.5, 2, 1)


def test_symmetry_and_angle_registration():
    p = balanced_directional_patch()
    assert p.directional_pi(0.7, 0.3) == pytest.approx(p.directional_pi(0.7, 0.3 + 2 * math.pi))
    assert p.gaussian_curvature(0.4, 0.2) == pytest.approx(p.gaussian_curvature(-0.4, -0.2))
    assert p.directional_pi(0.7, 0) != p.directional_pi(0.7, math.pi / 2)


def test_boundary_and_near_center():
    p = balanced_directional_patch()
    for theta in np.linspace(0, 2 * math.pi, 1001):
        assert math.isfinite(p.directional_pi(p.radius, theta))
    assert np.allclose(p.metric(1e-12, -1e-12), np.eye(2))
    assert p.gaussian_curvature(1e-12, 0) == pytest.approx(-4e-24, abs=1e-36)


def test_example_import_safe():
    from examples.directional_metric_demo import main
    assert callable(main)


def test_example_cli_report_and_no_overwrite(tmp_path, capsys):
    from examples.directional_metric_demo import main
    path = tmp_path / "report.json"
    assert main(["--output", str(path), "--scale", "10"]) == 0
    report = json.loads(path.read_text())
    assert report["patch"]["length_scale"] == 10
    assert report["circle_pi_at_0.75L"]["value"] == pytest.approx(math.pi)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        main(["--output", str(path), "--scale", "10"])
    assert path.read_bytes() == original
    capsys.readouterr()
