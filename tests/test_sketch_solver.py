import math

from adaptivecad.sketch_solver import (
    DistanceConstraint,
    EqualLengthConstraint,
    FixedConstraint,
    HorizontalConstraint,
    ParallelConstraint,
    PerpendicularConstraint,
    Sketch,
    VerticalConstraint,
    export_dxf,
)


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

    d0 = math.hypot(
        sketch.points[p0].x - sketch.points[p2].x, sketch.points[p0].y - sketch.points[p2].y
    )
    d1 = math.hypot(
        sketch.points[p1].x - sketch.points[p2].x, sketch.points[p1].y - sketch.points[p2].y
    )
    assert math.isclose(d0, 1.0, abs_tol=1e-6)
    assert math.isclose(d1, 1.0, abs_tol=1e-6)

    dxf_path = tmp_path / "out.dxf"
    export_dxf(sketch, dxf_path)
    assert dxf_path.exists()
    content = dxf_path.read_text()
    assert "LINE" in content and "POINT" in content


def test_right_angle_and_equal_lengths():
    sketch = Sketch()
    p0 = sketch.add_point(0.0, 0.0)
    p1 = sketch.add_point(1.1, 0.2)
    p2 = sketch.add_point(0.2, 1.2)

    sketch.add_constraint(FixedConstraint(p0, sketch.points[p0]))
    sketch.add_constraint(HorizontalConstraint(p0, p1))
    sketch.add_constraint(VerticalConstraint(p0, p2))
    sketch.add_constraint(PerpendicularConstraint(p0, p1, p0, p2))
    sketch.add_constraint(EqualLengthConstraint(p0, p1, p0, p2))

    sketch.solve_least_squares()

    d01 = math.hypot(sketch.points[p0].x - sketch.points[p1].x, sketch.points[p0].y - sketch.points[p1].y)
    d02 = math.hypot(sketch.points[p0].x - sketch.points[p2].x, sketch.points[p0].y - sketch.points[p2].y)
    dot = (sketch.points[p1].x - sketch.points[p0].x) * (sketch.points[p2].x - sketch.points[p0].x) + (
        sketch.points[p1].y - sketch.points[p0].y
    ) * (sketch.points[p2].y - sketch.points[p0].y)

    assert math.isclose(sketch.points[p1].y, sketch.points[p0].y, abs_tol=1e-6)
    assert math.isclose(sketch.points[p2].x, sketch.points[p0].x, abs_tol=1e-6)
    assert math.isclose(dot, 0.0, abs_tol=1e-6)
    assert math.isclose(d01, d02, rel_tol=1e-6, abs_tol=1e-6)


def test_parallel_segments():
    sketch = Sketch()
    p0 = sketch.add_point(0.0, 0.0)
    p1 = sketch.add_point(1.0, 0.0)
    p2 = sketch.add_point(0.0, 1.1)
    p3 = sketch.add_point(1.2, 1.4)

    sketch.add_constraint(FixedConstraint(p0, sketch.points[p0]))
    sketch.add_constraint(FixedConstraint(p1, sketch.points[p1]))
    sketch.add_constraint(ParallelConstraint(p0, p1, p2, p3))
    sketch.add_constraint(HorizontalConstraint(p0, p1))
    sketch.add_constraint(HorizontalConstraint(p2, p3))

    sketch.solve_least_squares()

    dy_top = sketch.points[p3].y - sketch.points[p2].y
    dy_bottom = sketch.points[p1].y - sketch.points[p0].y
    assert math.isclose(dy_bottom, 0.0, abs_tol=1e-6)
    assert math.isclose(dy_top, 0.0, abs_tol=1e-6)
    assert math.isclose(sketch.points[p3].y, sketch.points[p2].y, abs_tol=1e-6)
