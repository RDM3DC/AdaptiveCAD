#!/usr/bin/env python3
"""
AdaptiveCAD Quick Start Demo
============================

This demonstrates the core features you can use right now!
"""

from adaptivecad.linalg import Vec3, Matrix4, Quaternion
from adaptivecad.geom import BezierCurve, BSplineCurve
from adaptivecad.gcode_generator import generate_gcode_from_ama_data
from adaptivecad.io.ama_reader import AMAFile, AMAPart
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

def demo_gcode_workflow():
    """Demonstrate G-code generation workflow"""
    print("\n⚙️  G-code Generation")
    print("=" * 40)
      # Create sample AMA data structure using proper classes
    part = AMAPart(name="sample_part", brep_data=None, metadata={})
    ama_file = AMAFile(manifest={}, parts=[part])
    
    # Generate G-code using the built-in function
    gcode = generate_gcode_from_ama_data(ama_file, tool_diameter=3.0)
    gcode_lines = gcode.split('\n')
    print(f"✓ Generated {len(gcode_lines)} lines of G-code")
    print("First few lines:")
    for line in gcode_lines[:5]:
        if line.strip():
            print(f"  {line}")

def demo_import_handling():
    """Demonstrate how import errors are handled"""
    print("\n🛡️  Import Error Handling")
    print("=" * 40)
    print("The GUI now has improved error handling for STL import issues.")
    print("Common import errors and solutions:")
    print("")
    print("❌ 'SurfaceToBSplineSurface' error:")
    print("   → STL file contains surfaces that can't be converted to B-splines")
    print("   → Solution: Use STEP files or repair the STL mesh")
    print("")
    print("❌ 'SetPoles' attribute error:")
    print("   → Different pythonocc-core versions have different APIs")
    print("   → Solution: Automatic fallback to alternative methods")
    print("")
    print("✅ Error handling features:")
    print("   • Graceful error recovery")
    print("   • Helpful user messages") 
    print("   • Skip problematic surfaces and continue")
    print("   • Multiple fallback methods for API differences")
    print("   • Detailed error logging")

def main():
    """Run the complete demo"""
    print("🚀 AdaptiveCAD Quick Start Demo")
    print("================================\n")
    
    # Run demonstrations
    curve = demo_geometry()
    demo_transformations() 
    demo_gcode_workflow()
    demo_import_handling()
    
    print("\n🎉 Demo Complete!")
    print("\n📋 What you can do next:")
    print("  • Explore the tests/ folder for more examples")
    print("  • Try the command-line tools: python ama2gcode.py --help")
    print("  • Read the README.md for mathematical background")
    print("  • Use the GUI: python -c \"from adaptivecad.gui.playground import main; main()\"")
    print("  • Import STL/STEP files (error handling now improved!)")

if __name__ == "__main__":
    main()
