#!/usr/bin/env python3
"""
Apollonian Gasket Generator for AdaptiveCAD
============================================

Generates tangent circle packings using Descartes' theorem for use in:
- Blender Geometry Nodes (via point cloud export)
- AdaptiveCAD SDF fields (3D sphere packing)
- Parametric sweep operations along curves

The algorithm uses the complex form of Descartes' theorem to compute
centers and curvatures of mutually tangent circles, creating fractal
structures similar to those in Le Gall's "Extruded Apollonian Fractal".

Usage:
    python apollonian_gasket.py --depth 4 --radius 1.0 --output circles.json
    
Integration:
    import apollonian_gasket
    circles = apollonian_gasket.generate_packing(max_depth=5)
    # Use with AdaptiveCAD fields or export to Blender
"""

import math
import cmath
import json
import argparse
import collections
import itertools
from pathlib import Path
from typing import List, Tuple, NamedTuple, Optional
import numpy as np

class Circle(NamedTuple):
    """Circle with curvature, complex center, and generation depth."""
    k: float        # curvature = 1/radius (negative for outer circle)
    z: complex      # center as complex number x + iy
    depth: int      # generation depth (0 = seed circles)
    
    @property
    def radius(self) -> float:
        """Radius of the circle."""
        return abs(1.0 / self.k) if self.k != 0 else float('inf')
    
    @property
    def center(self) -> Tuple[float, float]:
        """Center as (x, y) tuple."""
        return (self.z.real, self.z.imag)

def descartes_curvature(k1: float, k2: float, k3: float, sign: int = 1) -> float:
    """
    Compute the fourth curvature using Descartes' theorem.
    
    Formula: k4 = k1 + k2 + k3 ± 2√(k1k2 + k2k3 + k3k1)
    
    Args:
        k1, k2, k3: Curvatures of three mutually tangent circles
        sign: ±1 for the two possible solutions
        
    Returns:
        Curvature of the fourth tangent circle
    """
    try:
        discriminant = k1*k2 + k2*k3 + k3*k1
        if discriminant < 0:
            return float('nan')
        return k1 + k2 + k3 + 2*sign*math.sqrt(discriminant)
    except (ValueError, OverflowError):
        return float('nan')

def descartes_center(k1: float, z1: complex, k2: float, z2: complex, 
                    k3: float, z3: complex, k4: float, sign: int = 1) -> complex:
    """
    Compute the center of the fourth circle using complex Descartes theorem.
    
    Formula: z4 = (k1*z1 + k2*z2 + k3*z3 ± 2√(k1*k2*z1*z2 + k2*k3*z2*z3 + k3*k1*z3*z1)) / k4
    
    Args:
        k1, z1: Curvature and center of first circle
        k2, z2: Curvature and center of second circle  
        k3, z3: Curvature and center of third circle
        k4: Curvature of fourth circle (from descartes_curvature)
        sign: ±1 for the two possible solutions
        
    Returns:
        Center of the fourth circle as complex number
    """
    try:
        # Cross terms in the square root
        term = k1*k2*z1*z2 + k2*k3*z2*z3 + k3*k1*z3*z1
        sqrt_term = cmath.sqrt(term)
        
        # Linear combination of centers
        linear = k1*z1 + k2*z2 + k3*z3
        
        return (linear + 2*sign*sqrt_term) / k4
    except (ValueError, OverflowError, ZeroDivisionError):
        return complex(float('nan'), float('nan'))

def generate_seed_circles(outer_radius: float = 1.0) -> List[Circle]:
    """
    Generate the initial seed configuration: outer circle + 3 inner tangent circles.
    
    Uses the symmetric configuration where three equal circles are inscribed
    in the outer circle, all mutually tangent.
    
    Args:
        outer_radius: Radius of the bounding circle
        
    Returns:
        List of 4 seed circles (1 outer + 3 inner)
    """
    # Outer circle (negative curvature)
    k_outer = -1.0 / outer_radius
    z_outer = 0 + 0j
    
    # Inner circles: solve for radius of 3 equal circles in unit circle
    # From geometry: r = R / (1 + 2/√3) where R is outer radius
    inner_radius = outer_radius / (1 + 2/math.sqrt(3))
    k_inner = 1.0 / inner_radius
    
    # Centers at 120° intervals, distance from origin
    distance = outer_radius - inner_radius
    centers = [
        distance * cmath.exp(1j * angle) 
        for angle in [0, 2*math.pi/3, 4*math.pi/3]
    ]
    
    return [
        Circle(k=k_outer, z=z_outer, depth=0),
        Circle(k=k_inner, z=centers[0], depth=0),
        Circle(k=k_inner, z=centers[1], depth=0),
        Circle(k=k_inner, z=centers[2], depth=0),
    ]

def generate_apollonian_packing(max_depth: int = 4, outer_radius: float = 1.0, 
                               min_radius: float = 1e-6) -> List[Circle]:
    """
    Generate an Apollonian gasket using iterative circle packing.
    
    Starting from seed circles, repeatedly finds new circles tangent to
    each triple of existing circles using Descartes' theorem.
    
    Args:
        max_depth: Maximum recursion depth
        outer_radius: Radius of the bounding circle
        min_radius: Minimum radius threshold (stability cutoff)
        
    Returns:
        List of all circles in the packing
    """
    # Initialize with seed configuration
    circles = generate_seed_circles(outer_radius)
    
    # Track seen circles to avoid duplicates (rounded for numeric stability)
    def circle_key(c: Circle) -> Tuple[float, float, float]:
        return (round(c.k, 6), round(c.z.real, 6), round(c.z.imag, 6))
    
    seen = {circle_key(c) for c in circles}
    
    def add_circle(k: float, z: complex, depth: int) -> bool:
        """Add a new circle if it's valid and unseen."""
        if math.isnan(k) or math.isnan(z.real) or math.isnan(z.imag):
            return False
        if k <= 0:  # Only keep inner circles (positive curvature)
            return False
        if 1.0/k < min_radius:  # Skip tiny circles
            return False
        if abs(z) + 1.0/k > outer_radius + 1e-6:  # Must fit inside outer circle
            return False
            
        circle = Circle(k=k, z=z, depth=depth)
        key = circle_key(circle)
        if key not in seen:
            seen.add(key)
            circles.append(circle)
            return True
        return False
    
    # Iteratively generate new circles
    for depth in range(1, max_depth + 1):
        # Work with snapshot to avoid modifying list during iteration
        current_circles = circles[:]
        new_count = 0
        
        # Try all combinations of 3 circles
        for i, j, l in itertools.combinations(range(len(current_circles)), 3):
            c1, c2, c3 = current_circles[i], current_circles[j], current_circles[l]
            
            # Two possible solutions for the fourth circle
            for sign in [+1, -1]:
                k4 = descartes_curvature(c1.k, c2.k, c3.k, sign)
                if math.isnan(k4) or k4 <= 0:
                    continue
                    
                z4 = descartes_center(c1.k, c1.z, c2.k, c2.z, c3.k, c3.z, k4, sign)
                if add_circle(k4, z4, depth):
                    new_count += 1
        
        print(f"Depth {depth}: added {new_count} circles (total: {len(circles)})")
        
        if new_count == 0:
            print(f"No new circles at depth {depth}, stopping early")
            break
    
    return circles

def export_to_blender_points(circles: List[Circle], output_path: str):
    """
    Export circles as point cloud data for Blender Geometry Nodes.
    
    Creates a JSON file with point positions and attributes that can be
    imported into Blender and used to drive procedural geometry.
    
    Args:
        circles: List of circles to export
        output_path: Path to output JSON file
    """
    points_data = {
        "points": [],
        "attributes": {
            "radius": [],
            "curvature": [],
            "depth": [],
            "outer_circle": []
        },
        "metadata": {
            "count": len(circles),
            "format": "apollonian_gasket_v1",
            "description": "Point cloud data for Apollonian gasket"
        }
    }
    
    for circle in circles:
        points_data["points"].append([circle.z.real, circle.z.imag, 0.0])
        points_data["attributes"]["radius"].append(circle.radius)
        points_data["attributes"]["curvature"].append(abs(circle.k))
        points_data["attributes"]["depth"].append(circle.depth)
        points_data["attributes"]["outer_circle"].append(circle.k < 0)
    
    with open(output_path, 'w') as f:
        json.dump(points_data, f, indent=2)
    
    print(f"Exported {len(circles)} circles to {output_path}")

def export_to_adaptivecad_field(circles: List[Circle], output_path: str):
    """
    Export circles as AdaptiveCAD field data for SDF operations.
    
    Creates a Python module with circle data that can be imported
    by AdaptiveCAD field utilities for 3D sphere packing.
    
    Args:
        circles: List of circles to export  
        output_path: Path to output Python file
    """
    with open(output_path, 'w') as f:
        f.write('"""Generated Apollonian gasket data for AdaptiveCAD fields."""\n\n')
        f.write('import numpy as np\n\n')
        
        # Export as numpy arrays for efficient field operations
        f.write('# Circle data: [x, y, radius, curvature, depth]\n')
        f.write('CIRCLES = np.array([\n')
        
        for circle in circles:
            if circle.k > 0:  # Only inner circles for 3D sphere packing
                f.write(f'    [{circle.z.real:.8f}, {circle.z.imag:.8f}, '
                       f'{circle.radius:.8f}, {circle.k:.8f}, {circle.depth}],\n')
        
        f.write('])\n\n')
        
        # Add utility functions for field operations
        f.write('''
def sphere_sdf(p, center, radius):
    """SDF for a sphere at center with given radius."""
    return np.linalg.norm(p - center, axis=-1) - radius

def apollonian_spheres_sdf(p, extrude_height=1.0):
    """
    SDF for extruded Apollonian spheres.
    
    Args:
        p: Query points as (..., 3) array
        extrude_height: Height to extrude circles into cylinders
        
    Returns:
        SDF values
    """
    # Convert 2D circles to 3D cylinders
    distances = []
    for circle_data in CIRCLES:
        x, y, r = circle_data[:3]
        center_2d = np.array([x, y])
        
        # Cylinder SDF: max(circle_distance, height_distance)
        p_xy = p[..., :2]
        p_z = p[..., 2]
        
        circle_dist = np.linalg.norm(p_xy - center_2d, axis=-1) - r
        height_dist = np.abs(p_z) - extrude_height/2
        
        cylinder_dist = np.maximum(circle_dist, height_dist)
        distances.append(cylinder_dist)
    
    # Union of all cylinders (minimum distance)
    return np.minimum.reduce(distances) if distances else np.full(p.shape[:-1], float('inf'))

def apollonian_coloring(p):
    """
    Generate color values based on circle properties.
    
    Returns:
        RGB colors based on curvature and depth
    """
    colors = np.zeros(p.shape[:-1] + (3,))
    
    for i, circle_data in enumerate(CIRCLES):
        x, y, r, k, depth = circle_data
        center_2d = np.array([x, y])
        
        # Distance to circle center (2D)
        p_xy = p[..., :2]
        dist_to_center = np.linalg.norm(p_xy - center_2d, axis=-1)
        
        # Points inside this circle
        inside = dist_to_center < r
        
        if np.any(inside):
            # Color by curvature (red) and depth (green/blue)
            curvature_color = min(k / 10.0, 1.0)  # Normalize curvature
            depth_color = depth / max(CIRCLES[:, 4])  # Normalize depth
            
            colors[inside, 0] = curvature_color  # Red channel
            colors[inside, 1] = depth_color      # Green channel  
            colors[inside, 2] = 1.0 - depth_color  # Blue channel
    
    return colors
''')
    
    print(f"Exported AdaptiveCAD field module to {output_path}")

def visualize_packing(circles: List[Circle], output_path: Optional[str] = None):
    """
    Create a simple matplotlib visualization of the circle packing.
    
    Args:
        circles: List of circles to visualize
        output_path: Optional path to save the plot
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        print("matplotlib not available, skipping visualization")
        return
    
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_aspect('equal')
    
    # Color by depth
    max_depth = max(c.depth for c in circles) if circles else 1
    colors = plt.cm.viridis(np.linspace(0, 1, max_depth + 1))
    
    for circle in circles:
        x, y = circle.center
        r = circle.radius
        
        # Choose color based on depth and whether it's the outer circle
        if circle.k < 0:  # Outer circle
            color = 'black'
            fill = False
            linewidth = 2
        else:
            color = colors[circle.depth]
            fill = True
            linewidth = 0.5
        
        circle_patch = patches.Circle((x, y), r, color=color, fill=fill, 
                                    linewidth=linewidth, alpha=0.7)
        ax.add_patch(circle_patch)
    
    # Set limits based on outer circle
    outer_r = max(c.radius for c in circles if c.k < 0) if any(c.k < 0 for c in circles) else 1.0
    margin = outer_r * 0.1
    ax.set_xlim(-outer_r - margin, outer_r + margin)
    ax.set_ylim(-outer_r - margin, outer_r + margin)
    
    ax.set_title(f'Apollonian Gasket ({len(circles)} circles)', fontsize=14)
    ax.grid(True, alpha=0.3)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved visualization to {output_path}")
    else:
        plt.show()
    
    plt.close()

def main():
    parser = argparse.ArgumentParser(description='Generate Apollonian gasket for AdaptiveCAD')
    parser.add_argument('--depth', type=int, default=4, help='Maximum recursion depth')
    parser.add_argument('--radius', type=float, default=1.0, help='Outer circle radius')
    parser.add_argument('--min-radius', type=float, default=1e-6, help='Minimum circle radius')
    parser.add_argument('--output', type=str, default='apollonian', help='Output file prefix')
    parser.add_argument('--format', choices=['json', 'field', 'both'], default='both', 
                       help='Output format')
    parser.add_argument('--visualize', action='store_true', help='Create matplotlib visualization')
    
    args = parser.parse_args()
    
    print(f"Generating Apollonian gasket (depth={args.depth}, radius={args.radius})")
    circles = generate_apollonian_packing(args.depth, args.radius, args.min_radius)
    
    print(f"Generated {len(circles)} circles")
    
    # Export in requested formats
    if args.format in ['json', 'both']:
        json_path = f"{args.output}_points.json"
        export_to_blender_points(circles, json_path)
    
    if args.format in ['field', 'both']:
        field_path = f"{args.output}_field.py"
        export_to_adaptivecad_field(circles, field_path)
    
    # Optional visualization
    if args.visualize:
        viz_path = f"{args.output}_visualization.png"
        visualize_packing(circles, viz_path)

if __name__ == '__main__':
    main()