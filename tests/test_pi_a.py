import math
from adaptivecad.geom import geodesic_distance, HyperbolicConstraint


def test_geodesic_distance_origin():
    p1 = (0.0, 0.0, 0.0)
    p2 = (1.0, 0.0, 0.0)
    d = geodesic_distance(p1, p2, 1.0)
    assert math.isclose(d, 1.0, rel_tol=1e-6)


def test_constraint_update():
    cons = HyperbolicConstraint((1.0, 0.0, 0.0), 1.0)
    p = (0.0, 0.0, 0.0)
    p_new = cons.update(p, step=0.5)
    assert geodesic_distance(p_new, cons.target, 1.0) < geodesic_distance(
        p, cons.target, 1.0
    )
