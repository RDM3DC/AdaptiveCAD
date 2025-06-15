from adaptivecad.linalg import Vec3
from adaptivecad.geom import BezierCurve
import numpy as np

# Create a Bezier curve
control_points = [Vec3(0.0, 0.0, 0.0), Vec3(1.0, 2.0, 0.0), Vec3(2.0, 0.0, 0.0)]
curve = BezierCurve(control_points)

# Evaluate the curve at multiple points
print("Evaluating Bezier curve at different points:")
for u in [0.0, 0.25, 0.5, 0.75, 1.0]:
    point = curve.evaluate(u)
    print(f"u = {u:.2f}: Point({point.x:.2f}, {point.y:.2f}, {point.z:.2f})")

# Demonstrate subdivision
print("\nSubdividing the curve at u = 0.5:")
left, right = curve.subdivide(0.5)
print("Left curve control points:")
for p in left.control_points:
    print(f"  ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})")
print("Right curve control points:")
for p in right.control_points:
    print(f"  ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})")

# Import other components to show them working
from adaptivecad.geom import BSplineCurve
from adaptivecad.geom import full_turn_deg, rotate_cmd, pi_a_over_pi

print("\nDemonstrating hyperbolic geometry functions:")
r = 0.5
kappa = 1.0
ratio = pi_a_over_pi(r, kappa)
print(f"Pi_a/Pi ratio at r={r} with kappa={kappa}: {ratio:.4f}")
print(f"Full turn in degrees: {full_turn_deg(r, kappa):.4f}")
