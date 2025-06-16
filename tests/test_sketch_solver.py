from adaptivecad.sketch_solver import Sketch, FixedConstraint, DistanceConstraint, export_dxf
import math
import os

def test_simple_triangle(tmp_path):
    sketch = Sketch()
    p0 = sketch.add_point(0.0, 0.0)
    p1 = sketch.add_point(1.0, 0.0)
    p2 = sketch.add_point(0.5, 0.8)

    sketch.add_constraint(FixedConstraint(p0, sketch.points[p0]))
    sketch.add_constraint(FixedConstraint(p1, sketch.points[p1]))
    sketch.add_constraint(DistanceConstraint(p0, p2, 1.0))
    sketch.add_constraint(DistanceConstraint(p1, p2, 1.0))

    sketch.solve_least_squares()

    d0 = math.hypot(sketch.points[p0].x - sketch.points[p2].x, sketch.points[p0].y - sketch.points[p2].y)
    d1 = math.hypot(sketch.points[p1].x - sketch.points[p2].x, sketch.points[p1].y - sketch.points[p2].y)
    assert math.isclose(d0, 1.0, abs_tol=1e-6)
    assert math.isclose(d1, 1.0, abs_tol=1e-6)

    dxf_path = tmp_path / "out.dxf"
    export_dxf(sketch, dxf_path)
    assert dxf_path.exists()
    content = dxf_path.read_text()
    assert "LINE" in content and "POINT" in content
