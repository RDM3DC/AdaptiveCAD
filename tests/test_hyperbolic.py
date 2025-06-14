import math

from adaptivecad.geom import full_turn_deg, rotate_cmd, pi_a_over_pi


def test_full_turn_deg():
    r = 0.4
    kappa = 1.0
    ratio = pi_a_over_pi(r, kappa)
    # expected ratio from the table is about 1.0269
    assert math.isclose(ratio, 1.0268808145, rel_tol=1e-6)
    d_full = full_turn_deg(r, kappa)
    assert math.isclose(d_full, 360.0 * ratio, rel_tol=1e-6)


def test_rotate_cmd_full_turn():
    r = 0.5
    kappa = 1.0
    d_full = full_turn_deg(r, kappa)
    rad = rotate_cmd(d_full, r, kappa)
    assert math.isclose(rad, 2 * math.pi, rel_tol=1e-6)
