from adaptivecad.linalg import Vec3
from adaptivecad.geom import BSplineCurve


def test_bspline_evaluate():
    pts = [Vec3(0.0, 0.0, 0.0), Vec3(1.0, 2.0, 0.0), Vec3(2.0, 0.0, 0.0), Vec3(3.0, 2.0, 0.0)]
    degree = 2
    knots = [0.0, 0.0, 0.0, 1.0, 2.0, 2.0, 2.0]
    curve = BSplineCurve(pts, degree, knots)
    p = curve.evaluate(1.0)
    assert abs(p.x - 1.5) < 1e-6
    assert abs(p.y - 1.0) < 1e-6
    d = curve.derivative(1.0)
    assert abs(d.x - 1.0) < 1e-6
    assert abs(d.y + 2.0) < 1e-6
