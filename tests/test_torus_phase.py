import math

import numpy as np

from adaptivecad.torus_phase import ParityTracker, TorusPath, unwrap_1d, wrap_to_pi


def test_unwrap_1d_continuity_across_branch_cut():
    # Jump from +179deg to -179deg should unwrap as +2deg step, not -358deg.
    a = np.deg2rad([179.0, -179.0, -178.0])
    u = unwrap_1d(a)
    assert abs((u[1] - u[0]) - math.radians(2.0)) < 1e-6
    assert abs((u[2] - u[1]) - math.radians(1.0)) < 1e-6


def test_torus_path_windings():
    # Two full longitudinal turns, one negative meridional turn.
    t = np.linspace(0.0, 1.0, 200)
    theta = 4.0 * math.pi * t
    phi = -2.0 * math.pi * t
    angles = np.column_stack([wrap_to_pi(theta), wrap_to_pi(phi)])
    p = TorusPath(angles, phase_space="wrapped")
    wth, wph = p.windings()
    assert wth == 2
    assert wph == -1


def test_parity_tracker_toggles_on_branch_crossing():
    pt = ParityTracker()
    # Force a wrapped discontinuity.
    seq = np.deg2rad([170.0, 179.0, -179.0, -170.0])
    parities = [pt.update(float(x)) for x in seq]
    # There should be at least one toggle when crossing the cut.
    assert len(set(parities)) > 1


def test_phase_safe_interpolation_no_big_jumps():
    # A path with a wrap discontinuity; interpolation should stay continuous in the lift.
    a0 = np.deg2rad([170.0, 0.0])
    a1 = np.deg2rad([-170.0, 0.0])
    p = TorusPath(np.vstack([a0, a1]), phase_space="wrapped")
    p2 = p.interpolate(25).unwrap().angles
    # Max step should be well under pi (continuous unwrapped path).
    steps = np.abs(np.diff(p2[:, 0]))
    assert float(np.max(steps)) < math.pi / 2
