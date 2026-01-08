"""
Blender Integration for Apollonian Gasket Sweep
===============================================

This module provides Blender-specific utilities for importing Apollonian gasket
data and creating procedural sweep geometry using Geometry Nodes.

Features:
- Import circle data from JSON into Blender point clouds
- Generate spine curves (circles, torus knots, custom paths)
- Create Geometry Nodes setups for tube sweeping with twist
- Material utilities for curvature/depth-based coloring

Usage:
    # In Blender's script editor:
    import sys
    sys.path.append('/path/to/AdaptiveCAD')
    from blender_apollonian_sweep import *
    
    # Load gasket data and create sweep
    create_apollonian_sweep('apollonian_points.json')
"""

import bmesh
import mathutils
from mathutils import Vector, Matrix
import json
from typing import List, Tuple, Optional, Dict, Any

try:
    import bpy
    import addon_utils
    IN_BLENDER = True
except ImportError:
    print("Warning: Not running in Blender environment")
    IN_BLENDER = False

def ensure_geometry_nodes():
    """Ensure Geometry Nodes add-on is enabled."""
    if not IN_BLENDER:
        return False
        
    addon_name = "geometry_nodes"
    if not addon_utils.check(addon_name)[1]:
        bpy.ops.preferences.addon_enable(module=addon_name)
        print("Enabled Geometry Nodes add-on")
    return True

def load_apollonian_data(json_path: str) -> Dict[str, Any]:
    """
    Load Apollonian gasket data from JSON file.
    
    Args:
        json_path: Path to JSON file created by apollonian_gasket.py
        
    Returns:
        Dictionary with points and attributes
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    print(f"Loaded {data['metadata']['count']} circles from {json_path}")
    return data

def create_point_cloud_from_data(data: Dict[str, Any], name: str = "ApollonianPoints") -> bpy.types.Object:
    """
    Create a Blender point cloud object from Apollonian data.
    
    Args:
        data: Data dictionary from load_apollonian_data
        name: Name for the created object
        
    Returns:
        Created point cloud object
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    # Create mesh with vertices at circle centers
    mesh = bpy.data.meshes.new(name + "_mesh")
    points = data["points"]
    
    # Convert 2D points to 3D (z=0)
    vertices = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in points]
    mesh.from_pydata(vertices, [], [])
    mesh.update()
    
    # Create object
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    
    # Add custom attributes for Geometry Nodes
    attributes = data.get("attributes", {})
    
    # Add radius attribute
    if "radius" in attributes:
        radius_attr = mesh.attributes.new("radius", 'FLOAT', 'POINT')
        for i, r in enumerate(attributes["radius"]):
            radius_attr.data[i].value = r
    
    # Add curvature attribute  
    if "curvature" in attributes:
        curv_attr = mesh.attributes.new("curvature", 'FLOAT', 'POINT')
        for i, k in enumerate(attributes["curvature"]):
            curv_attr.data[i].value = k
    
    # Add depth attribute
    if "depth" in attributes:
        depth_attr = mesh.attributes.new("depth", 'INT', 'POINT')
        for i, d in enumerate(attributes["depth"]):
            depth_attr.data[i].value = d
    
    # Add outer circle flag
    if "outer_circle" in attributes:
        outer_attr = mesh.attributes.new("outer_circle", 'BOOLEAN', 'POINT')
        for i, is_outer in enumerate(attributes["outer_circle"]):
            outer_attr.data[i].value = is_outer
    
    print(f"Created point cloud '{name}' with {len(vertices)} points and {len(attributes)} attributes")
    return obj

def create_spine_curve(curve_type: str = "circle", **kwargs) -> bpy.types.Object:
    """
    Create a spine curve for the sweep operation.
    
    Args:
        curve_type: Type of curve ("circle", "torus_knot", "bezier")
        **kwargs: Curve-specific parameters
        
    Returns:
        Created curve object
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    if curve_type == "circle":
        radius = kwargs.get("radius", 2.0)
        bpy.ops.curve.primitive_nurbs_circle_add(radius=radius)
        curve_obj = bpy.context.active_object
        curve_obj.name = "SpineCurve_Circle"
        
    elif curve_type == "torus_knot":
        # Create a torus knot using script
        p = kwargs.get("p", 3)  # Number of turns around torus
        q = kwargs.get("q", 2)  # Number of turns through hole
        major_radius = kwargs.get("major_radius", 2.0)
        minor_radius = kwargs.get("minor_radius", 0.5)
        resolution = kwargs.get("resolution", 64)
        
        # Create curve data
        curve_data = bpy.data.curves.new("TorusKnot", 'CURVE')
        curve_data.dimensions = '3D'
        
        # Create spline
        spline = curve_data.splines.new('BEZIER')
        spline.bezier_points.add(resolution - 1)  # -1 because one point exists by default
        
        import math
        for i in range(resolution):
            t = 2 * math.pi * i / resolution
            
            # Torus knot parametric equations
            r = minor_radius * math.cos(q * t) + major_radius
            x = r * math.cos(p * t)
            y = r * math.sin(p * t)  
            z = minor_radius * math.sin(q * t)
            
            point = spline.bezier_points[i]
            point.co = (x, y, z)
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
        
        spline.use_cyclic_u = True
        
        # Create object
        curve_obj = bpy.data.objects.new("SpineCurve_TorusKnot", curve_data)
        bpy.context.collection.objects.link(curve_obj)
        
    elif curve_type == "bezier":
        # Create a simple bezier curve
        bpy.ops.curve.primitive_bezier_curve_add()
        curve_obj = bpy.context.active_object
        curve_obj.name = "SpineCurve_Bezier"
        
        # Modify to create more interesting shape
        curve = curve_obj.data
        spline = curve.splines[0]
        
        # Add more points and shape them
        spline.bezier_points.add(2)  # Total of 4 points
        points = [
            Vector((0, 0, 0)),
            Vector((2, 0, 1)), 
            Vector((2, 2, 2)),
            Vector((0, 2, 1))
        ]
        
        for i, pos in enumerate(points):
            spline.bezier_points[i].co = pos
            spline.bezier_points[i].handle_left_type = 'AUTO'
            spline.bezier_points[i].handle_right_type = 'AUTO'
    
    else:
        raise ValueError(f"Unknown curve type: {curve_type}")
    
    return curve_obj

def setup_twist_animation(curve_obj: bpy.types.Object, twists_per_loop: float = 2.0, frame_count: int = 120):
    """
    Set up twist animation for the spine curve.
    
    Args:
        curve_obj: Curve object to animate
        twists_per_loop: Number of twists per animation loop
        frame_count: Total frames in animation
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    curve = curve_obj.data
    
    # Clear existing animation
    curve.animation_data_clear()
    
    # Create tilt keyframes
    total_twist = twists_per_loop * 2 * 3.14159  # Convert to radians
    
    curve.twist_mode = 'Z_UP'
    
    # Set keyframes
    for frame in [1, frame_count]:
        bpy.context.scene.frame_set(frame)
        
        # Calculate twist value
        if frame == 1:
            twist_value = 0.0
        else:
            twist_value = total_twist
        
        # Apply to all spline points
        for spline in curve.splines:
            for point in spline.bezier_points:
                point.tilt = twist_value
                point.keyframe_insert(data_path="tilt", frame=frame)
    
    print(f"Set up twist animation: {twists_per_loop} twists over {frame_count} frames")

def create_apollonian_sweep_geometry_nodes(points_obj: bpy.types.Object, 
                                          spine_obj: bpy.types.Object,
                                          name: str = "ApollonianSweep") -> bpy.types.Object:
    """
    Create a Geometry Nodes setup for sweeping Apollonian circles along a spine.
    
    Args:
        points_obj: Point cloud object with circle data
        spine_obj: Spine curve object
        name: Name for the created object
        
    Returns:
        Object with Geometry Nodes modifier
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    ensure_geometry_nodes()
    
    # Create empty mesh object for the geometry nodes
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    
    # Add Geometry Nodes modifier
    mod = obj.modifiers.new(name="GeometryNodes", type='NODES')
    
    # Create node group
    node_group = bpy.data.node_groups.new(name + "_NodeGroup", 'GeometryNodeTree')
    mod.node_group = node_group
    
    # Create nodes
    nodes = node_group.nodes
    links = node_group.links
    
    # Input and output nodes
    group_input = nodes.new('NodeGroupInput')
    group_output = nodes.new('NodeGroupOutput')
    
    # Add input sockets
    node_group.inputs.new('NodeSocketGeometry', 'Points')
    node_group.inputs.new('NodeSocketGeometry', 'Spine')
    node_group.inputs.new('NodeSocketFloat', 'Profile Scale')
    node_group.inputs.new('NodeSocketInt', 'Profile Resolution')
    
    # Add output socket
    node_group.outputs.new('NodeSocketGeometry', 'Geometry')
    
    # Set default values
    mod["Input_3"] = 1.0  # Profile Scale
    mod["Input_4"] = 16   # Profile Resolution
    
    # Create profile circle
    profile_circle = nodes.new('GeometryNodeCurvePrimitiveCircle')
    profile_circle.inputs['Radius'].default_value = 0.1  # Will be scaled by radius attribute
    
    # Instance profile circles on points
    instance_on_points = nodes.new('GeometryNodeInstanceOnPoints')
    
    # Scale instances by radius attribute
    scale_node = nodes.new('GeometryNodeInputNamedAttribute')
    scale_node.inputs['Name'].default_value = 'radius'
    
    scale_instances = nodes.new('GeometryNodeScaleInstances')
    
    # Realize instances to get actual geometry
    realize_instances = nodes.new('GeometryNodeRealizeInstances')
    
    # Curve to mesh for sweep
    curve_to_mesh = nodes.new('GeometryNodeCurveToMesh')
    
    # Position nodes
    group_input.location = (-800, 0)
    profile_circle.location = (-600, -200)
    scale_node.location = (-600, -400)
    instance_on_points.location = (-400, 0)
    scale_instances.location = (-200, 0)
    realize_instances.location = (0, 0)
    curve_to_mesh.location = (200, 0)
    group_output.location = (400, 0)
    
    # Link nodes
    links.new(group_input.outputs['Points'], instance_on_points.inputs['Points'])
    links.new(profile_circle.outputs['Curve'], instance_on_points.inputs['Instance'])
    links.new(instance_on_points.outputs['Instances'], scale_instances.inputs['Instances'])
    links.new(scale_node.outputs['Attribute'], scale_instances.inputs['Scale'])
    links.new(scale_instances.outputs['Instances'], realize_instances.inputs['Geometry'])
    links.new(realize_instances.outputs['Geometry'], curve_to_mesh.inputs['Profile Curve'])
    links.new(group_input.outputs['Spine'], curve_to_mesh.inputs['Path Curve'])
    links.new(curve_to_mesh.outputs['Mesh'], group_output.inputs['Geometry'])
    
    # Set object inputs
    mod["Input_2"] = points_obj   # Points input
    mod["Input_3"] = spine_obj    # Spine input
    
    print(f"Created Geometry Nodes setup for {name}")
    return obj

def create_curvature_material(name: str = "ApollonianMaterial") -> bpy.types.Material:
    """
    Create a material that colors based on curvature and depth attributes.
    
    Args:
        name: Name for the created material
        
    Returns:
        Created material
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    
    # Attribute nodes for curvature and depth
    curvature_attr = nodes.new('ShaderNodeAttribute')
    curvature_attr.attribute_name = 'curvature'
    
    depth_attr = nodes.new('ShaderNodeAttribute')
    depth_attr.attribute_name = 'depth'
    
    # Color ramps for mapping values
    curv_ramp = nodes.new('ShaderNodeValToRGB')
    depth_ramp = nodes.new('ShaderNodeValToRGB')
    
    # Set up curvature color ramp (red to yellow for high curvature)
    curv_ramp.color_ramp.elements[0].color = (0.2, 0.2, 0.8, 1.0)  # Blue for low curvature
    curv_ramp.color_ramp.elements[1].color = (1.0, 0.5, 0.0, 1.0)  # Orange for high curvature
    
    # Set up depth color ramp (blue to red for depth)
    depth_ramp.color_ramp.elements[0].color = (0.0, 1.0, 0.0, 1.0)  # Green for shallow
    depth_ramp.color_ramp.elements[1].color = (1.0, 0.0, 1.0, 1.0)  # Magenta for deep
    
    # Mix colors
    mix_node = nodes.new('ShaderNodeMix')
    mix_node.data_type = 'RGBA'
    mix_node.inputs['Fac'].default_value = 0.5
    
    # Position nodes
    output.location = (400, 0)
    principled.location = (200, 0)
    mix_node.location = (0, 0)
    curv_ramp.location = (-200, 100)
    depth_ramp.location = (-200, -100)
    curvature_attr.location = (-400, 100)
    depth_attr.location = (-400, -100)
    
    # Link nodes
    links.new(curvature_attr.outputs['Fac'], curv_ramp.inputs['Fac'])
    links.new(depth_attr.outputs['Fac'], depth_ramp.inputs['Fac'])
    links.new(curv_ramp.outputs['Color'], mix_node.inputs['Color1'])
    links.new(depth_ramp.outputs['Color'], mix_node.inputs['Color2'])
    links.new(mix_node.outputs['Result'], principled.inputs['Base Color'])
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    print(f"Created curvature-based material: {name}")
    return mat

def create_apollonian_sweep(json_path: str, 
                           curve_type: str = "torus_knot",
                           animate_twist: bool = True,
                           **curve_kwargs) -> Dict[str, bpy.types.Object]:
    """
    Complete workflow: load data, create sweep, and set up materials.
    
    Args:
        json_path: Path to Apollonian gasket JSON data
        curve_type: Type of spine curve to create
        animate_twist: Whether to animate the twist
        **curve_kwargs: Arguments for curve creation
        
    Returns:
        Dictionary of created objects
    """
    if not IN_BLENDER:
        raise RuntimeError("Must be run in Blender")
    
    print(f"Creating Apollonian sweep from {json_path}")
    
    # Load data and create point cloud
    data = load_apollonian_data(json_path)
    points_obj = create_point_cloud_from_data(data, "ApollonianPoints")
    
    # Create spine curve
    spine_obj = create_spine_curve(curve_type, **curve_kwargs)
    
    # Set up twist animation
    if animate_twist:
        setup_twist_animation(spine_obj, twists_per_loop=2.0, frame_count=120)
    
    # Create sweep geometry
    sweep_obj = create_apollonian_sweep_geometry_nodes(points_obj, spine_obj, "ApollonianSweep")
    
    # Create and assign material
    material = create_curvature_material("ApollonianMaterial")
    sweep_obj.data.materials.append(material)
    
    # Set up scene
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 120
    bpy.context.view_layer.objects.active = sweep_obj
    
    print("Apollonian sweep creation complete!")
    
    return {
        'points': points_obj,
        'spine': spine_obj, 
        'sweep': sweep_obj,
        'material': material
    }

# Example usage for Blender script editor
EXAMPLE_SCRIPT = '''
"""
Example: Create Apollonian Sweep in Blender

Copy this into Blender's script editor and run it after generating
the gasket data with apollonian_gasket.py.
"""

import sys
import os

# Add AdaptiveCAD to path (modify as needed)
adaptivecad_path = r"C:/Users/YourName/AdaptiveCAD"
if adaptivecad_path not in sys.path:
    sys.path.append(adaptivecad_path)

from blender_apollonian_sweep import create_apollonian_sweep

# Path to generated JSON data
json_path = os.path.join(adaptivecad_path, "apollonian_points.json")

# Create the sweep (torus knot with custom parameters)
objects = create_apollonian_sweep(
    json_path=json_path,
    curve_type="torus_knot",
    p=3,                    # Torus knot parameter
    q=2,                    # Torus knot parameter
    major_radius=3.0,       # Size of torus
    minor_radius=1.0,       # Thickness of torus
    resolution=64,          # Curve resolution
    animate_twist=True      # Enable twist animation
)

print("Created objects:", list(objects.keys()))

# Optional: set up render settings for animation
import bpy
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.frame_current = 1

# Optional: add a camera and lighting
bpy.ops.object.camera_add(location=(5, -5, 3))
bpy.ops.object.light_add(type='SUN', location=(3, 3, 10))
'''

if __name__ == "__main__" and IN_BLENDER:
    print("Blender Apollonian Sweep module loaded successfully")
    print("Use create_apollonian_sweep() to generate sweep geometry")
    print("See EXAMPLE_SCRIPT for usage example")