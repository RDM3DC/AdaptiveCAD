#!/usr/bin/env python3
"""
AdaptiveCAD Quick Start Demo - Working Version
==============================================

This demonstrates the core features you can use right now!
"""

from adaptivecad.linalg import Vec3, Matrix4, Quaternion
from adaptivecad.geom import BezierCurve
import numpy as np

def demo_geometry():
    """Demonstrate geometric operations"""
    print("🎯 AdaptiveCAD Geometry Demo")
    print("=" * 40)
    
    # Create a Bezier curve
    control_points = [
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 2.0, 0.0), 
        Vec3(3.0, 1.0, 0.0),
        Vec3(4.0, 0.0, 0.0)
    ]
    
    curve = BezierCurve(control_points)
    print(f"✓ Created Bezier curve with {len(control_points)} control points")
    
    # Evaluate curve at different parameters
    print("\n📐 Curve Evaluation:")
    for u in [0.0, 0.25, 0.5, 0.75, 1.0]:
        point = curve.evaluate(u)
        print(f"  u={u:.2f} → Point({point.x:.2f}, {point.y:.2f}, {point.z:.2f})")
    
    # Demonstrate subdivision
    print("\n✂️  Curve Subdivision at u=0.5:")
    left, right = curve.subdivide(0.5)
    print(f"  Left curve: {len(left.control_points)} points")
    print(f"  Right curve: {len(right.control_points)} points")
    
    return curve

def demo_transformations():
    """Demonstrate 3D transformations"""
    print("\n🔄 3D Transformations")
    print("=" * 40)
    
    # Create a point
    point = Vec3(1.0, 0.0, 0.0)
    print(f"Original point: ({point.x}, {point.y}, {point.z})")
    
    # Create rotation matrix (90 degrees around Z-axis)
    angle_rad = np.pi / 2
    z_axis = Vec3(0, 0, 1)
    quaternion = Quaternion.from_axis_angle(z_axis, angle_rad)
    rotation = Matrix4.from_quaternion(quaternion)
    
    # Apply transformation
    transformed = rotation.transform_point(point)
    print(f"After 90° Z-rotation: ({transformed.x:.3f}, {transformed.y:.3f}, {transformed.z:.3f})")

def demo_linear_algebra():
    """Demonstrate vector operations"""
    print("\n🧮 Linear Algebra Operations")
    print("=" * 40)
    
    # Vector operations
    v1 = Vec3(1.0, 2.0, 3.0)
    v2 = Vec3(4.0, 5.0, 6.0)
    
    print(f"Vector 1: ({v1.x}, {v1.y}, {v1.z})")
    print(f"Vector 2: ({v2.x}, {v2.y}, {v2.z})")
    
    # Addition
    v_sum = v1 + v2
    print(f"Sum: ({v_sum.x}, {v_sum.y}, {v_sum.z})")
    
    # Cross product
    cross = v1.cross(v2)
    print(f"Cross product: ({cross.x:.1f}, {cross.y:.1f}, {cross.z:.1f})")
      # Magnitude
    print(f"V1 magnitude: {v1.norm():.3f}")

def main():
    """Run the complete demo"""
    print("🚀 AdaptiveCAD Quick Start Demo")
    print("================================\n")
    
    # Run demonstrations
    curve = demo_geometry()
    demo_transformations() 
    demo_linear_algebra()
    
    print("\n🎉 Demo Complete!")
    print("\n📋 What you can do next:")
    print("  • Explore the tests/ folder for more examples")
    print("  • Try the command-line tools: python ama2gcode.py --help")
    print("  • Read the README.md for mathematical background")
    print("  • Set up conda environment for full GUI access")
    print("  • Run 'python -m pytest tests/' to see all features")

if __name__ == "__main__":
    main()
