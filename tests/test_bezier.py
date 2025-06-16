from adaptivecad.linalg import Vec3
from adaptivecad.geom import BezierCurve


def test_bezier_evaluate():
    curve = BezierCurve(
        [Vec3(0.0, 0.0, 0.0), Vec3(1.0, 2.0, 0.0), Vec3(2.0, 0.0, 0.0)]
    )
    p = curve.evaluate(0.5)
    assert abs(p.x - 1.0) < 1e-6
    assert abs(p.y - 1.0) < 1e-6
    d = curve.derivative(0.5)
    assert abs(d.x - 2.0) < 1e-6
    assert abs(d.y - 0.0) < 1e-6
