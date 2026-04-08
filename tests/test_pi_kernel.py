import math

import numpy as np

from adaptivecad.app.phase_tools import build_polar_pi_adaptive_circle_prims
from adaptivecad.geometry import make_polar_pi_circle_profile
from adaptivecad.pi.kernel import PiAParams, adaptive_arc_length, make_adaptive_circle, pi_a
from adaptivecad.pi.kernel import make_polar_adaptive_circle, polar_pi_a


def test_pi_reduces_to_plain_when_kappa_zero():
    params = PiAParams(beta=0.5, s0=1.0, clamp=0.3)
    assert abs(pi_a(0.0, 1.0, params) - math.pi) < 1e-12


def test_clamp_limits_fractional_change():
    params = PiAParams(beta=10.0, s0=1.0, clamp=0.1)
    pa = pi_a(kappa=100.0, scale=10.0, params=params)
    frac = abs(pa / math.pi - 1.0)
    assert frac <= 0.1000001


def test_adaptive_arc_length_scales_linearly():
    params = PiAParams(beta=0.25, s0=1.0, clamp=0.3)
    r = 2.0
    ang = math.pi / 3
    L0 = ang * r
    L1 = adaptive_arc_length(r, ang, kappa=0.5, scale=1.0, params=params)
    # not equal unless kappa==0; positive scaling expected
    assert L1 > 0.9 * L0 and L1 < 1.5 * L0


def test_make_circle_shape():
    pts = make_adaptive_circle(radius=1.0, n=128, kappa=0.0, scale=1.0)
    assert pts.shape == (128, 2)
    # approximate radius from mean distance
    r_est = np.mean(np.sqrt(pts[:, 0] ** 2 + pts[:, 1] ** 2))
    assert abs(r_est - 1.0) < 1e-2


def test_polar_pi_field_varies_with_angle():
    params = PiAParams(beta=0.2, s0=1.0, clamp=0.3)
    theta = np.linspace(0.0, 2.0 * math.pi, 16, endpoint=False)
    field = polar_pi_a(theta, kappa=0.4, scale=1.0, params=params, angular_amplitude=0.25, angular_frequency=3)
    assert field.shape == theta.shape
    assert np.max(field) > np.min(field)
    assert np.all(field > 0.0)


def test_make_polar_adaptive_circle_creates_lobed_boundary():
    pts = make_polar_adaptive_circle(
        radius=1.0,
        n=180,
        kappa=0.5,
        scale=1.0,
        angular_amplitude=0.2,
        angular_frequency=3,
    )
    radii = np.sqrt(pts[:, 0] ** 2 + pts[:, 1] ** 2)
    assert pts.shape == (180, 2)
    assert np.max(radii) - np.min(radii) > 0.05


def test_make_polar_profile_exposes_pi_a_metadata():
    profile = make_polar_pi_circle_profile(
        radius=2.0,
        cx=1.0,
        cy=-0.5,
        segments=64,
        kappa=0.35,
        angular_amplitude=0.2,
        angular_frequency=4,
    )
    assert profile["metric"] == "pi_a"
    assert profile["family"] == "pi_a:polar_circle"
    assert profile["closed"] is True
    assert len(profile["points"]) == 64
    assert profile["params"]["angular_frequency"] == 4


def test_build_polar_pi_adaptive_circle_prims_returns_capsules():
    prims = build_polar_pi_adaptive_circle_prims(available=12, n=36)
    assert prims
    assert len(prims) <= 12
    assert all(pr.kind == 3 for pr in prims)
    assert all(getattr(pr, "display_name", "").startswith("Polar πₐ Shape") for pr in prims)
