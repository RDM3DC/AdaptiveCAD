import math

from adaptivecad.linalg import Vec3, Quaternion


def test_quaternion_rotation():
    axis = Vec3(0.0, 0.0, 1.0)
    q = Quaternion.from_axis_angle(axis, math.pi / 2)
    v = Vec3(1.0, 0.0, 0.0)
    rotated = q.rotate(v)
    assert math.isclose(rotated.x, 0.0, abs_tol=1e-6)
    assert math.isclose(rotated.y, 1.0, abs_tol=1e-6)
    assert math.isclose(rotated.z, 0.0, abs_tol=1e-6)
