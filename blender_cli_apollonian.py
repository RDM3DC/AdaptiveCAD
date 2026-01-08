#!/usr/bin/env python3#!/usr/bin/env python3#!/usr/bin/env python3#!/usr/bin/env python3

"""Command-line Blender harness for generating Apollonian sweep renders.

"""Command-line Blender harness for generating Apollonian sweep renders."""

This script wraps Blender in background mode, produces a temporary scene script

that rebuilds the sweep with Geometry Nodes, and optionally renders the result."""Command-line Blender harness for generating Apollonian sweep renders."""

"""

from __future__ import annotations

from __future__ import annotations

Blender Command-Line Integration for Apollonian Sweep

import argparse

import jsonimport argparse

import os

import subprocessimport jsonThis module creates a temporary Blender script that rebuilds the sweep with a====================================================

import sys

import textwrapimport os

from pathlib import Path

from typing import Any, Dict, Optionalimport subprocessGeometry Nodes network, applies curvature-driven shading, and optionally kicks



import sys

BLENDER_PATHS = [

    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",import textwrapoff a render – all executed through Blender's background CLI.This script allows running the Apollonian gasket sweep generation from the command line

    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",

    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",from pathlib import Path

    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",

    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",from typing import Any, Dict, Optional"""using Blender's background mode, leveraging GPU compute for large datasets.

    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",

    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",

    "blender",

]



BLENDER_PATHS = [

def find_blender_executable() -> Optional[str]:

    """Return the first Blender executable that can be launched."""    r"C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",from __future__ import annotationsFeatures:



    for candidate in BLENDER_PATHS:    r"C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",

        if candidate == "blender":

            try:    r"C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",- Command-line Blender execution for headless processing

                out = subprocess.run(

                    [candidate, "--version"],    r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",

                    capture_output=True,

                    text=True,    r"C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe",import argparse- GPU-accelerated geometry generation using Cycles

                    timeout=10,

                )    r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",

            except (FileNotFoundError, subprocess.TimeoutExpired):

                continue    r"C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe",import json- Batch processing for multiple parameter sets



            if out.returncode == 0:    "blender",

                return candidate

        elif os.path.exists(candidate):]import os- Integration with dual RTX 3090 Ti setup

            return candidate



    return None

import subprocess



def _escape_path(path: str) -> str:def find_blender_executable() -> Optional[str]:

    """Escape backslashes so a Windows path can be embedded in a script."""

    """Return the first Blender executable that can be launched."""import sysUsage:

    return path.replace("\\", "\\\\")





def create_blender_script(    for candidate in BLENDER_PATHS:import textwrap    python blender_cli_apollonian.py --input apollonian_points.json --output sweep.blend

    input_json: str,

    output_blend: str,        if candidate == "blender":

    curve_type: str,

    render_output: Optional[str],            try:from pathlib import Path    

    fps: int,

    duration: float,                probe = subprocess.run(

    resample_count: int,

    profile_scale: float,                    [candidate, "--version"],from typing import Any, Dict, Optional    # With Blender directly:

    twist_turns: float,

    curve_settings: Dict[str, Any],                    capture_output=True,

) -> str:

    """Return a fully-expanded Blender Python script as a string."""                    text=True,    blender --background --python blender_cli_apollonian.py -- --input data.json --output result.blend



    escaped_input = _escape_path(input_json)                    timeout=10,

    escaped_output = _escape_path(output_blend)

    escaped_render = (                )"""

        f'r"{_escape_path(render_output)}"' if render_output else "None"

    )            except (FileNotFoundError, subprocess.TimeoutExpired):



    curve_json = json.dumps(curve_settings, ensure_ascii=True)                continueBLENDER_PATHS = [

    frame_start = 1

    frame_end = max(

        frame_start, frame_start + int(round(max(duration, 0.01) * fps)) - 1

    )            if probe.returncode == 0:    r"C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",import os

    total_twist = twist_turns * 6.283185307179586  # 2 * pi

                return candidate

    script = textwrap.dedent(

        f"""        elif os.path.exists(candidate):    r"C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",import sys

        import bpy

        import json            return candidate

        import math

        import time    r"C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",import json



        INPUT_JSON = r"{escaped_input}"    return None

        OUTPUT_BLEND = r"{escaped_output}"

        RENDER_OUTPUT = {escaped_render}    r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",import argparse

        CURVE_TYPE = "{curve_type}"

        CURVE_PARAMS = json.loads('''{curve_json}''')

        RESAMPLE_COUNT = {resample_count}

        PROFILE_SCALE = {profile_scale}def _escape_path(path: str) -> str:    r"C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe",import subprocess

        TOTAL_TWIST = {total_twist}

        FPS = {fps}    """Escape backslashes so a Windows path can be embedded in a script."""

        FRAME_START = {frame_start}

        FRAME_END = {frame_end}    r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",from pathlib import Path



    return path.replace("\\", "\\\\")

        def clear_scene():

            bpy.ops.wm.read_factory_settings(use_empty=True)    r"C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe",from typing import Optional, Dict, Any, List



    "blender",

        def configure_cycles():

            scene = bpy.context.scene]# Blender executable paths (common locations)

            scene.render.engine = 'CYCLES'

            scene.render.use_file_extension = TrueBLENDER_PATHS = [

            scene.render.fps = FPS

            scene.frame_start = FRAME_START    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",

            scene.frame_end = FRAME_END

def find_blender_executable() -> Optional[str]:    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",

            try:

                prefs = bpy.context.preferences    """Return the first Blender executable that can be launched."""    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",

                cycles_prefs = prefs.addons['cycles'].preferences

    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",

                for device in cycles_prefs.devices:

                    if device.type == 'CUDA':    for candidate in BLENDER_PATHS:    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",

                        device.use = True

        if candidate == "blender":    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",

                cycles_prefs.compute_device_type = 'CUDA'

                scene.cycles.device = 'GPU'            try:    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",

            except Exception as exc:

                print(f"GPU unavailable, fallback to CPU: {{exc}}")                proc = subprocess.run(    "blender",  # If in PATH

                scene.cycles.device = 'CPU'

                    [candidate, "--version"],]

            return scene

                    capture_output=True,



        def load_apollonian(path):                    text=True,def find_blender_executable() -> Optional[str]:

            with open(path, 'r', encoding='utf8') as handle:

                data = json.load(handle)                    timeout=10,    """Find Blender executable on the system."""

            return data

                )    for path in BLENDER_PATHS:



        def create_point_cloud(data):            except (FileNotFoundError, subprocess.TimeoutExpired):        if os.path.exists(path):

            mesh = bpy.data.meshes.new("ApollonianPoints_mesh")

            verts = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in data["points"]]                continue            return path

            mesh.from_pydata(verts, [], [])

            mesh.update()        elif path == "blender":



            obj = bpy.data.objects.new("ApollonianPoints", mesh)            if proc.returncode == 0:            # Check if blender is in PATH

            bpy.context.collection.objects.link(obj)

                return candidate            try:

            attrs = data.get("attributes", {{}})

        elif os.path.exists(candidate):                result = subprocess.run([path, "--version"], 

            def assign_attribute(name, attr_type):

                if name not in attrs:            return candidate                                      capture_output=True, text=True, timeout=10)

                    return

                values = attrs[name]                if result.returncode == 0:

                attribute = mesh.attributes.new(name, attr_type, 'POINT')

                for idx, value in enumerate(values):    return None                    return path

                    attribute.data[idx].value = value

            except (subprocess.TimeoutExpired, FileNotFoundError):

            assign_attribute('radius', 'FLOAT')

            assign_attribute('curvature', 'FLOAT')                continue

            assign_attribute('depth', 'INT')

            assign_attribute('outer_circle', 'BOOLEAN')def _escape_path(path: str) -> str:    return None



            return obj    """Escape backslashes so a Windows path can be embedded in a script."""



def _escape_path(path: str) -> str:

        def create_spine_curve(curve_type, params):

            if curve_type == 'circle':    return path.replace("\\", "\\\\")    """Escape Windows backslashes for embedding in Python source."""

                radius = params.get('radius', 2.0)

                bpy.ops.curve.primitive_nurbs_circle_add(radius=radius)    return path.replace("\\", "\\\\")

                curve_obj = bpy.context.active_object

                curve_obj.name = 'SpineCurve_Circle'            Returns:

                return curve_obj

def create_blender_script(        Generated Python script as string

            if curve_type == 'torus_knot':

                import math    input_json: str,    """



                p_val = params.get('p', 3)    output_blend: str,    

                q_val = params.get('q', 2)

                major = params.get('major_radius', 3.0)    curve_type: str,    escaped_input = _escape_path(input_json)

                minor = params.get('minor_radius', 1.0)

                resolution = max(4, params.get('resolution', 128))    render_output: Optional[str],    escaped_output = _escape_path(output_blend)



                curve_data = bpy.data.curves.new('SpineCurve_TorusKnot', 'CURVE')    fps: int,    escaped_render = _escape_path(render_output) if render_output else "None"

                curve_data.dimensions = '3D'

                spline = curve_data.splines.new('NURBS')    duration: float,

                spline.points.add(resolution)

    resample_count: int,    frame_start = 1

                for i in range(resolution + 1):

                    t = (i / resolution) * 2.0 * math.pi    profile_scale: float,    frame_end = max(frame_start, frame_start + int(round(max(duration, 0.1) * fps)) - 1)

                    r_val = minor * math.cos(q_val * t) + major

                    x = r_val * math.cos(p_val * t)    twist_turns: float,    do_animation = render_output and render_output.lower().endswith(('.mp4', '.mov', '.avi'))

                    y = r_val * math.sin(p_val * t)

                    z = minor * math.sin(q_val * t)    curve_settings: Dict[str, Any],

                    spline.points[i].co = (x, y, z, 1.0)

) -> str:    script = f'''

                spline.use_cyclic_u = True

                curve_obj = bpy.data.objects.new('SpineCurve_TorusKnot', curve_data)    """Return a fully-expanded Blender Python script as a string."""import bpy

                bpy.context.collection.objects.link(curve_obj)

                return curve_objimport bmesh



            if curve_type == 'bezier':    escaped_input = _escape_path(input_json)import math

                bpy.ops.curve.primitive_bezier_curve_add()

                curve_obj = bpy.context.active_object    escaped_output = _escape_path(output_blend)import mathutils

                curve_obj.name = 'SpineCurve_Bezier'

                return curve_obj    escaped_render = (from mathutils import Vector, Matrix



            raise ValueError(f"Unsupported curve type: {{curve_type}}")        f"r\"{_escape_path(render_output)}\"" if render_output else "None"import json



    )import sys

        def build_geometry_nodes(points_obj, spine_obj, attribute_stats):

            mesh = bpy.data.meshes.new('ApollonianSweep_mesh')import os

            sweep_obj = bpy.data.objects.new('ApollonianSweep', mesh)

            bpy.context.collection.objects.link(sweep_obj)    curve_json = json.dumps(curve_settings, ensure_ascii=True)import time



            modifier = sweep_obj.modifiers.new(name='GeometryNodes', type='NODES')    frame_start = 1

            node_group = bpy.data.node_groups.new('ApollonianSweepNodes', 'GeometryNodeTree')

            modifier.node_group = node_group    frame_end = max(print("=== Apollonian Sweep Generation ===")



            nodes = node_group.nodes        frame_start,print(f"Blender version: {{bpy.app.version_string}}")

            links = node_group.links

        frame_start + int(round(max(duration, 0.01) * fps)) - 1,print(f"Input JSON: {escaped_input}")

            nodes.clear()

    )print(f"Output blend: {escaped_output}")

            group_in = nodes.new('NodeGroupInput')

            group_in.location = (-1200, 0)    total_twist = twist_turns * 6.283185307179586  # 2 * pi

            group_out = nodes.new('NodeGroupOutput')

            group_out.location = (600, 0)# Clear existing mesh objects



            if hasattr(node_group, 'interface'):    # fmt: offbpy.ops.object.select_all(action='SELECT')

                node_group.interface.clear()

                node_group.interface.new_socket(    script = textwrap.dedent(bpy.ops.object.delete(use_global=False, confirm=False)

                    name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry'

                )        f"""

            else:

                node_group.outputs.clear()        import bpy# Set up GPU rendering if available

                node_group.outputs.new('NodeSocketGeometry', 'Geometry')

        import jsonscene = bpy.context.scene

            points_info = nodes.new('GeometryNodeObjectInfo')

            points_info.location = (-1000, 240)        import mathscene.render.engine = 'CYCLES'

            points_info.inputs[0].default_value = points_obj

            points_info.transform_space = 'RELATIVE'        import timescene.render.use_file_extension = True



            curve_info = nodes.new('GeometryNodeObjectInfo')scene.render.fps = {fps}

            curve_info.location = (-1000, -240)

            curve_info.inputs[0].default_value = spine_obj        INPUT_JSON = r"{escaped_input}"scene.frame_start = {frame_start}

            curve_info.transform_space = 'RELATIVE'

        OUTPUT_BLEND = r"{escaped_output}"scene.frame_end = {frame_end}

            outer_attr = nodes.new('GeometryNodeInputNamedAttribute')

            outer_attr.location = (-1200, 400)        RENDER_OUTPUT = {escaped_render}

            outer_attr.data_type = 'BOOLEAN'

            outer_attr.inputs[0].default_value = 'outer_circle'        CURVE_TYPE = "{curve_type}"# Try to enable GPU compute



            invert_outer = nodes.new('FunctionNodeBooleanMath')        CURVE_PARAMS = json.loads('''{curve_json}''')try:

            invert_outer.location = (-1000, 420)

            invert_outer.operation = 'NOT'        RESAMPLE_COUNT = {resample_count}    preferences = bpy.context.preferences



            separate_points = nodes.new('GeometryNodeSeparateGeometry')        PROFILE_SCALE = {profile_scale}    cycles_prefs = preferences.addons['cycles'].preferences

            separate_points.location = (-800, 240)

        TOTAL_TWIST = {total_twist}    

            radius_attr = nodes.new('GeometryNodeInputNamedAttribute')

            radius_attr.location = (-1200, 120)        FPS = {fps}    # Enable all CUDA devices (for dual RTX 3090 Ti)

            radius_attr.data_type = 'FLOAT'

            radius_attr.inputs[0].default_value = 'radius'        FRAME_START = {frame_start}    for device in cycles_prefs.devices:



            curvature_attr = nodes.new('GeometryNodeInputNamedAttribute')        FRAME_END = {frame_end}        if device.type == 'CUDA':

            curvature_attr.location = (-1200, -40)

            curvature_attr.data_type = 'FLOAT'            device.use = True

            curvature_attr.inputs[0].default_value = 'curvature'

            print(f"Enabled CUDA device: {{device.name}}")

            depth_attr = nodes.new('GeometryNodeInputNamedAttribute')

            depth_attr.location = (-1200, -200)        def clear_scene():    

            depth_attr.data_type = 'INT'

            depth_attr.inputs[0].default_value = 'depth'            bpy.ops.wm.read_factory_settings(use_empty=True)    cycles_prefs.compute_device_type = 'CUDA'



            circle_profile = nodes.new('GeometryNodeCurvePrimitiveCircle')    scene.cycles.device = 'GPU'

            circle_profile.location = (-620, 80)

            circle_profile.inputs['Resolution'].default_value = 96    print("GPU compute enabled for Cycles")



            radius_scale = nodes.new('ShaderNodeMath')        def configure_cycles():    

            radius_scale.location = (-820, 120)

            radius_scale.operation = 'MULTIPLY'            scene = bpy.context.sceneexcept Exception as e:

            radius_scale.inputs[1].default_value = PROFILE_SCALE

            scene.render.engine = 'CYCLES'    print(f"Could not enable GPU compute: {{e}}")

            scale_vector = nodes.new('ShaderNodeCombineXYZ')

            scale_vector.location = (-620, 120)            scene.render.use_file_extension = True    scene.cycles.device = 'CPU'



            instance_profiles = nodes.new('GeometryNodeInstanceOnPoints')            scene.render.fps = FPS

            instance_profiles.location = (-420, 240)

            scene.frame_start = FRAME_START# Load Apollonian data

            realize_profiles = nodes.new('GeometryNodeRealizeInstances')

            realize_profiles.location = (-220, 240)            scene.frame_end = FRAME_ENDdef load_apollonian_data(json_path):



            store_radius = nodes.new('GeometryNodeStoreNamedAttribute')    with open(json_path, 'r') as f:

            store_radius.location = (-20, 240)

            store_radius.data_type = 'FLOAT'            try:        data = json.load(f)

            store_radius.domain = 'POINT'

            store_radius.inputs['Name'].default_value = 'radius'                prefs = bpy.context.preferences    print(f"Loaded {{data['metadata']['count']}} circles")



            store_curvature = nodes.new('GeometryNodeStoreNamedAttribute')                cycles_prefs = prefs.addons['cycles'].preferences    return data

            store_curvature.location = (180, 240)

            store_curvature.data_type = 'FLOAT'

            store_curvature.domain = 'POINT'

            store_curvature.inputs['Name'].default_value = 'curvature'                for device in cycles_prefs.devices:# Create point cloud from data



            store_depth = nodes.new('GeometryNodeStoreNamedAttribute')                    if device.type == 'CUDA':def create_point_cloud_from_data(data, name="ApollonianPoints"):

            store_depth.location = (380, 240)

            store_depth.data_type = 'INT'                        device.use = True    mesh = bpy.data.meshes.new(name + "_mesh")

            store_depth.domain = 'POINT'

            store_depth.inputs['Name'].default_value = 'depth'    points = data["points"]



            resample_curve = nodes.new('GeometryNodeResampleCurve')                cycles_prefs.compute_device_type = 'CUDA'    

            resample_curve.location = (-620, -240)

            resample_curve.inputs['Count'].default_value = RESAMPLE_COUNT                scene.cycles.device = 'GPU'    # Convert 2D points to 3D



            spline_parameter = nodes.new('GeometryNodeSplineParameter')            except Exception as exc:  # noqa: BLE001    vertices = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in points]

            spline_parameter.location = (-420, -420)

                print(f"GPU unavailable, fallback to CPU: {{exc}}")    mesh.from_pydata(vertices, [], [])

            tilt_math = nodes.new('ShaderNodeMath')

            tilt_math.location = (-220, -420)                scene.cycles.device = 'CPU'    mesh.update()

            tilt_math.operation = 'MULTIPLY'

            tilt_math.inputs[1].default_value = TOTAL_TWIST    



            set_curve_tilt = nodes.new('GeometryNodeSetCurveTilt')            return scene    obj = bpy.data.objects.new(name, mesh)

            set_curve_tilt.location = (-20, -240)

    bpy.context.collection.objects.link(obj)

            curve_to_mesh = nodes.new('GeometryNodeCurveToMesh')

            curve_to_mesh.location = (180, -240)    

            curve_to_mesh.inputs['Fill Caps'].default_value = False

        def load_apollonian(path):    # Add custom attributes

            shade_smooth = nodes.new('GeometryNodeSetShadeSmooth')

            shade_smooth.location = (380, -240)            with open(path, 'r', encoding='utf8') as handle:    attributes = data.get("attributes", {{}})

            shade_smooth.inputs['Shade Smooth'].default_value = True

                data = json.load(handle)    

            links.new(outer_attr.outputs['Attribute'], invert_outer.inputs[0])

            links.new(points_info.outputs['Geometry'], separate_points.inputs['Geometry'])            return data    if "radius" in attributes:

            links.new(invert_outer.outputs['Boolean'], separate_points.inputs['Selection'])

        radius_attr = mesh.attributes.new("radius", 'FLOAT', 'POINT')

            links.new(radius_attr.outputs['Attribute'], radius_scale.inputs[0])

            links.new(radius_scale.outputs['Value'], scale_vector.inputs['X'])        for i, r in enumerate(attributes["radius"]):

            links.new(radius_scale.outputs['Value'], scale_vector.inputs['Y'])

            links.new(radius_scale.outputs['Value'], scale_vector.inputs['Z'])        def create_point_cloud(data):            radius_attr.data[i].value = r



            links.new(separate_points.outputs['Selection'], instance_profiles.inputs['Points'])            mesh = bpy.data.meshes.new("ApollonianPoints_mesh")    

            links.new(circle_profile.outputs['Curve'], instance_profiles.inputs['Instance'])

            links.new(scale_vector.outputs['Vector'], instance_profiles.inputs['Scale'])            verts = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in data["points"]]    if "curvature" in attributes:



            links.new(instance_profiles.outputs['Instances'], realize_profiles.inputs['Geometry'])            mesh.from_pydata(verts, [], [])        curv_attr = mesh.attributes.new("curvature", 'FLOAT', 'POINT')

            links.new(realize_profiles.outputs['Geometry'], store_radius.inputs['Geometry'])

            links.new(radius_attr.outputs['Attribute'], store_radius.inputs['Value'])            mesh.update()        for i, k in enumerate(attributes["curvature"]):



            links.new(store_radius.outputs['Geometry'], store_curvature.inputs['Geometry'])            curv_attr.data[i].value = k

            links.new(curvature_attr.outputs['Attribute'], store_curvature.inputs['Value'])

            obj = bpy.data.objects.new("ApollonianPoints", mesh)    

            links.new(store_curvature.outputs['Geometry'], store_depth.inputs['Geometry'])

            links.new(depth_attr.outputs['Attribute'], store_depth.inputs['Value'])            bpy.context.collection.objects.link(obj)    if "depth" in attributes:



            links.new(curve_info.outputs['Geometry'], resample_curve.inputs['Curve'])        depth_attr = mesh.attributes.new("depth", 'INT', 'POINT')

            links.new(resample_curve.outputs['Curve'], set_curve_tilt.inputs['Curve'])

            links.new(spline_parameter.outputs['Factor'], tilt_math.inputs[0])            attrs = data.get("attributes", {{}})        for i, d in enumerate(attributes["depth"]):

            links.new(tilt_math.outputs['Value'], set_curve_tilt.inputs['Tilt'])

            depth_attr.data[i].value = d

            links.new(set_curve_tilt.outputs['Curve'], curve_to_mesh.inputs['Curve'])

            links.new(store_depth.outputs['Geometry'], curve_to_mesh.inputs['Profile Curve'])            def assign_attribute(name, attr_type):    

            links.new(curve_to_mesh.outputs['Mesh'], shade_smooth.inputs['Geometry'])

            links.new(shade_smooth.outputs['Geometry'], group_out.inputs['Geometry'])                if name not in attrs:    print(f"Created point cloud with {{len(vertices)}} points")



            points_obj.hide_render = True                    return    return obj

            points_obj.hide_set(True)

            spine_obj.hide_render = True                values = attrs[name]

            spine_obj.hide_set(True)

                attribute = mesh.attributes.new(name, attr_type, 'POINT')# Create spine curve

            sweep_obj.data.clear_geometry()

            return sweep_obj                for idx, value in enumerate(values):def create_spine_curve(curve_type="{curve_type}", **kwargs):



                    attribute.data[idx].value = value    if curve_type == "circle":

        def create_material(stats):

            curvature_min, curvature_max = stats['curvature']        radius = kwargs.get("radius", 2.0)

            depth_min, depth_max = stats['depth']

            assign_attribute('radius', 'FLOAT')        bpy.ops.curve.primitive_nurbs_circle_add(radius=radius)

            mat = bpy.data.materials.new('ApollonianMaterial')

            mat.use_nodes = True            assign_attribute('curvature', 'FLOAT')        curve_obj = bpy.context.active_object



            nodes = mat.node_tree.nodes            assign_attribute('depth', 'INT')        curve_obj.name = "SpineCurve_Circle"

            links = mat.node_tree.links

            nodes.clear()            assign_attribute('outer_circle', 'BOOLEAN')        



            output = nodes.new('ShaderNodeOutputMaterial')    elif curve_type == "torus_knot":

            output.location = (600, 0)

            return obj        p = kwargs.get("p", 3)

            principled = nodes.new('ShaderNodeBsdfPrincipled')

            principled.location = (200, 40)        q = kwargs.get("q", 2) 

            principled.inputs['Metallic'].default_value = 0.65

            principled.inputs['Roughness'].default_value = 0.25        major_radius = kwargs.get("major_radius", 2.0)



            emission = nodes.new('ShaderNodeEmission')        def create_spine_curve(curve_type, params):        minor_radius = kwargs.get("minor_radius", 0.5)

            emission.location = (200, -200)

            emission.inputs['Strength'].default_value = 1.0            if curve_type == 'circle':        resolution = kwargs.get("resolution", 64)



            add_shader = nodes.new('ShaderNodeAddShader')                radius = params.get('radius', 2.0)        

            add_shader.location = (400, -80)

                bpy.ops.curve.primitive_nurbs_circle_add(radius=radius)        curve_data = bpy.data.curves.new("TorusKnot", 'CURVE')

            curvature_attr = nodes.new('ShaderNodeAttribute')

            curvature_attr.location = (-600, 120)                curve_obj = bpy.context.active_object        curve_data.dimensions = '3D'

            curvature_attr.attribute_name = 'curvature'

                curve_obj.name = 'SpineCurve_Circle'        

            curvature_map = nodes.new('ShaderNodeMapRange')

            curvature_map.location = (-400, 120)                return curve_obj        spline = curve_data.splines.new('BEZIER')

            curvature_map.inputs['From Min'].default_value = curvature_min

            curvature_map.inputs['From Max'].default_value = max(curvature_max, curvature_min + 1e-5)        spline.bezier_points.add(resolution - 1)

            curvature_map.clamp = True

            if curve_type == 'torus_knot':        

            curvature_ramp = nodes.new('ShaderNodeValToRGB')

            curvature_ramp.location = (-200, 120)                import math        import math

            curvature_ramp.color_ramp.interpolation = 'EASE'

            curvature_ramp.color_ramp.elements[0].color = (0.1, 0.2, 0.7, 1.0)        for i in range(resolution):

            curvature_ramp.color_ramp.elements[1].color = (1.0, 0.7, 0.2, 1.0)

                p_val = params.get('p', 3)            t = 2 * math.pi * i / resolution

            depth_attr = nodes.new('ShaderNodeAttribute')

            depth_attr.location = (-600, -160)                q_val = params.get('q', 2)            

            depth_attr.attribute_name = 'depth'

                major = params.get('major_radius', 3.0)            r = minor_radius * math.cos(q * t) + major_radius

            depth_map = nodes.new('ShaderNodeMapRange')

            depth_map.location = (-400, -160)                minor = params.get('minor_radius', 1.0)            x = r * math.cos(p * t)

            depth_map.inputs['From Min'].default_value = depth_min

            depth_map.inputs['From Max'].default_value = max(depth_max, depth_min + 1e-5)                resolution = max(4, params.get('resolution', 128))            y = r * math.sin(p * t)

            depth_map.clamp = True

            depth_map.inputs['To Min'].default_value = 0.2            z = minor_radius * math.sin(q * t)

            depth_map.inputs['To Max'].default_value = 4.0

                curve_data = bpy.data.curves.new('SpineCurve_TorusKnot', 'CURVE')            

            links.new(curvature_attr.outputs['Fac'], curvature_map.inputs['Value'])

            links.new(curvature_map.outputs['Result'], curvature_ramp.inputs['Fac'])                curve_data.dimensions = '3D'            point = spline.bezier_points[i]

            links.new(curvature_ramp.outputs['Color'], principled.inputs['Base Color'])

            links.new(curvature_ramp.outputs['Color'], emission.inputs['Color'])                spline = curve_data.splines.new('NURBS')            point.co = (x, y, z)



            links.new(depth_attr.outputs['Fac'], depth_map.inputs['Value'])                spline.points.add(resolution)            point.handle_left_type = 'AUTO'

            links.new(depth_map.outputs['Result'], emission.inputs['Strength'])

            point.handle_right_type = 'AUTO'

            links.new(principled.outputs['BSDF'], add_shader.inputs[0])

            links.new(emission.outputs['Emission'], add_shader.inputs[1])                for i in range(resolution + 1):        

            links.new(add_shader.outputs['Shader'], output.inputs['Surface'])

                    t = (i / resolution) * 2.0 * math.pi        spline.use_cyclic_u = True

            mat.use_backface_culling = False

            return mat                    r_val = minor * math.cos(q_val * t) + major        



                    x = r_val * math.cos(p_val * t)        curve_obj = bpy.data.objects.new("SpineCurve_TorusKnot", curve_data)

        def add_camera_and_light(target_obj):

            bpy.ops.object.light_add(type='SUN', location=(6.0, -6.0, 8.0))                    y = r_val * math.sin(p_val * t)        bpy.context.collection.objects.link(curve_obj)

            light = bpy.context.active_object

            light.data.energy = 5.5                    z = minor * math.sin(q_val * t)        



            bpy.ops.object.camera_add(location=(0.0, -10.0, 4.0))                    spline.points[i].co = (x, y, z, 1.0)    else:

            camera = bpy.context.active_object

            camera.name = 'ApollonianCamera'        bpy.ops.curve.primitive_bezier_curve_add()



            rig = bpy.data.objects.new('CameraRig', None)                spline.use_cyclic_u = True        curve_obj = bpy.context.active_object

            bpy.context.collection.objects.link(rig)

            camera.parent = rig                curve_obj = bpy.data.objects.new('SpineCurve_TorusKnot', curve_data)        curve_obj.name = "SpineCurve_Bezier"



            constraint = camera.constraints.new(type='TRACK_TO')                bpy.context.collection.objects.link(curve_obj)    

            constraint.target = target_obj

            constraint.track_axis = 'TRACK_NEGATIVE_Z'                return curve_obj    return curve_obj

            constraint.up_axis = 'UP_Y'



            rig.rotation_euler = (0.0, 0.0, 0.0)

            rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_START)            if curve_type == 'bezier':# Setup Geometry Nodes for sweep

            rig.rotation_euler = (0.0, 0.0, math.radians(360.0))

            rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_END)                bpy.ops.curve.primitive_bezier_curve_add()def create_sweep_geometry_nodes(points_obj, spine_obj, name="ApollonianSweep"):



            if rig.animation_data and rig.animation_data.action:                curve_obj = bpy.context.active_object    # Create target mesh object

                for fcurve in rig.animation_data.action.fcurves:

                    for keyframe in fcurve.keyframe_points:                curve_obj.name = 'SpineCurve_Bezier'    mesh = bpy.data.meshes.new(name + "_mesh")

                        keyframe.interpolation = 'LINEAR'

                return curve_obj    obj = bpy.data.objects.new(name, mesh)

            bpy.context.scene.camera = camera

    bpy.context.collection.objects.link(obj)



        clear_scene()            raise ValueError(f"Unsupported curve type: {{curve_type}}")

        scene = configure_cycles()

    # Add Geometry Nodes modifier

        print('Loading Apollonian data...')

        data = load_apollonian(INPUT_JSON)    mod = obj.modifiers.new(name="GeometryNodes", type='NODES')



        curvature_values = data.get('attributes', {{}}).get('curvature', [1.0])        def build_geometry_nodes(points_obj, spine_obj, attribute_stats):

        depth_values = data.get('attributes', {{}}).get('depth', [0])

        attribute_stats = {{            mesh = bpy.data.meshes.new('ApollonianSweep_mesh')    node_group = bpy.data.node_groups.new(name + "_NodeGroup", 'GeometryNodeTree')

            'curvature': (min(curvature_values), max(curvature_values)),

            'depth': (min(depth_values), max(depth_values)),            sweep_obj = bpy.data.objects.new('ApollonianSweep', mesh)    mod.node_group = node_group

        }}

            bpy.context.collection.objects.link(sweep_obj)

        points_obj = create_point_cloud(data)

        spine_obj = create_spine_curve(CURVE_TYPE, CURVE_PARAMS)    nodes = node_group.nodes



        print('Building Geometry Nodes sweep...')            modifier = sweep_obj.modifiers.new(name='GeometryNodes', type='NODES')    links = node_group.links

        sweep_obj = build_geometry_nodes(points_obj, spine_obj, attribute_stats)

            node_group = bpy.data.node_groups.new('ApollonianSweepNodes', 'GeometryNodeTree')

        print('Assigning material...')

        material = create_material(attribute_stats)            modifier.node_group = node_group    nodes.clear()

        sweep_obj.data.materials.clear()

        sweep_obj.data.materials.append(material)    links.clear()



        bpy.context.view_layer.objects.active = sweep_obj            nodes = node_group.nodes



        add_camera_and_light(sweep_obj)            links = node_group.links    input_node = nodes.new('NodeGroupInput')



        print('Saving blend file...')    input_node.location = (-900, 0)

        bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)

            nodes.clear()

        if RENDER_OUTPUT not in (None, ''):

            print('Rendering to', RENDER_OUTPUT)    output_node = nodes.new('NodeGroupOutput')

            scene.render.filepath = RENDER_OUTPUT

            scene.render.resolution_x = 1920            group_in = nodes.new('NodeGroupInput')    output_node.location = (700, 0)

            scene.render.resolution_y = 1080

            scene.cycles.samples = 128            group_in.location = (-1200, 0)



            if RENDER_OUTPUT.lower().endswith(('.mp4', '.mov', '.avi')):            group_out = nodes.new('NodeGroupOutput')    interface = getattr(node_group, 'interface', None)

                scene.render.image_settings.file_format = 'FFMPEG'

                scene.render.ffmpeg.format = 'MPEG4'            group_out.location = (600, 0)    if interface is not None:

                scene.render.ffmpeg.codec = 'H264'

                scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'        # Ensure a single geometry output socket is present

                scene.render.ffmpeg.ffmpeg_preset = 'GOOD'

                scene.render.ffmpeg.gopsize = FPS            if hasattr(node_group, 'interface'):        interface.clear()

                bpy.ops.render.render(animation=True)

            else:                node_group.interface.clear()        interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

                bpy.ops.render.render(write_still=True)

        """                node_group.interface.new_socket(    else:

    )

                    name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry'        node_group.outputs.clear()

    return script

                )        node_group.outputs.new('NodeSocketGeometry', 'Geometry')



def run_blender_apollonian(            else:

    input_json: str,

    output_blend: str,                node_group.outputs.clear()    # Bring external geometry into the graph

    curve_type: str = 'torus_knot',

    render_output: Optional[str] = None,                node_group.outputs.new('NodeSocketGeometry', 'Geometry')    points_info = nodes.new('GeometryNodeObjectInfo')

    blender_path: Optional[str] = None,

    fps: int = 30,    points_info.location = (-700, 220)

    duration: float = 4.0,

    resample_count: int = 512,            points_info = nodes.new('GeometryNodeObjectInfo')    points_info.inputs[0].default_value = points_obj

    profile_scale: float = 0.95,

    twist_turns: float = 1.5,            points_info.location = (-1000, 240)    points_info.inputs[1].default_value = False

    **curve_kwargs: Any,

) -> bool:            points_info.inputs[0].default_value = points_obj    points_info.transform_space = 'RELATIVE'

    """Generate the sweep by running Blender in background mode."""

            points_info.transform_space = 'RELATIVE'

    if blender_path is None:

        blender_path = find_blender_executable()    curve_info = nodes.new('GeometryNodeObjectInfo')

        if blender_path is None:

            print('Unable to locate a Blender executable')            curve_info = nodes.new('GeometryNodeObjectInfo')    curve_info.location = (-700, -220)

            return False

            curve_info.location = (-1000, -240)    curve_info.inputs[0].default_value = spine_obj

    blender_path = str(Path(blender_path).resolve())

    input_path = Path(input_json).resolve()            curve_info.inputs[0].default_value = spine_obj    curve_info.inputs[1].default_value = False

    output_path = Path(output_blend).resolve()

            curve_info.transform_space = 'RELATIVE'    curve_info.transform_space = 'RELATIVE'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    render_path = Path(render_output).resolve() if render_output else None

    if render_path:

        render_path.parent.mkdir(parents=True, exist_ok=True)            outer_attr = nodes.new('GeometryNodeInputNamedAttribute')    separate_outer = nodes.new('GeometryNodeSeparateGeometry')



    curve_settings = {            outer_attr.location = (-1200, 400)    separate_outer.location = (-500, 220)

        'torus_knot': {

            'p': curve_kwargs.get('p') or curve_kwargs.get('torus_p') or 3,            outer_attr.data_type = 'BOOLEAN'

            'q': curve_kwargs.get('q') or curve_kwargs.get('torus_q') or 2,

            'major_radius': curve_kwargs.get('major_radius', 3.0),            outer_attr.inputs[0].default_value = 'outer_circle'    outer_flag_attr = nodes.new('GeometryNodeInputNamedAttribute')

            'minor_radius': curve_kwargs.get('minor_radius', 1.0),

            'resolution': curve_kwargs.get('resolution', 256),    outer_flag_attr.location = (-900, 220)

        },

        'circle': {            invert_outer = nodes.new('FunctionNodeBooleanMath')    outer_flag_attr.data_type = 'BOOLEAN'

            'radius': curve_kwargs.get('radius', 2.0),

        },            invert_outer.location = (-1000, 420)    outer_flag_attr.inputs[0].default_value = "outer_circle"

        'bezier': {},

    }.get(curve_type, {})            invert_outer.operation = 'NOT'



    script_content = create_blender_script(    radius_attr = nodes.new('GeometryNodeInputNamedAttribute')

        str(input_path),

        str(output_path),            separate_points = nodes.new('GeometryNodeSeparateGeometry')    radius_attr.location = (-900, -40)

        curve_type,

        str(render_path) if render_path else None,            separate_points.location = (-800, 240)    radius_attr.data_type = 'FLOAT'

        fps=fps,

        duration=duration,    radius_attr.inputs[0].default_value = "radius"

        resample_count=resample_count,

        profile_scale=profile_scale,            radius_attr = nodes.new('GeometryNodeInputNamedAttribute')

        twist_turns=twist_turns,

        curve_settings=curve_settings,            radius_attr.location = (-1200, 120)    curvature_attr = nodes.new('GeometryNodeInputNamedAttribute')

    )

            radius_attr.data_type = 'FLOAT'    curvature_attr.location = (-900, -240)

    temp_script = output_path.parent / 'apollonian_temp_script.py'

    temp_script.write_text(script_content, encoding='utf8')            radius_attr.inputs[0].default_value = 'radius'    curvature_attr.data_type = 'FLOAT'



    try:    curvature_attr.inputs[0].default_value = "curvature"

        cmd = [

            blender_path,            curvature_attr = nodes.new('GeometryNodeInputNamedAttribute')

            '--background',

            '--python',            curvature_attr.location = (-1200, -40)    depth_attr = nodes.new('GeometryNodeInputNamedAttribute')

            str(temp_script),

        ]            curvature_attr.data_type = 'FLOAT'    depth_attr.location = (-900, -440)

        print('Running Blender command:')

        print(' '.join(cmd))            curvature_attr.inputs[0].default_value = 'curvature'    depth_attr.data_type = 'INT'



        result = subprocess.run(    depth_attr.inputs[0].default_value = "depth"

            cmd,

            capture_output=True,            depth_attr = nodes.new('GeometryNodeInputNamedAttribute')

            text=True,

            cwd=str(input_path.parent),            depth_attr.location = (-1200, -200)    circle_profile = nodes.new('GeometryNodeCurvePrimitiveCircle')

        )

            depth_attr.data_type = 'INT'    circle_profile.location = (-500, 40)

        if result.stdout:

            print('=== Blender stdout ===')            depth_attr.inputs[0].default_value = 'depth'    circle_profile.inputs['Resolution'].default_value = 48

            print(result.stdout)



        if result.stderr:

            print('=== Blender stderr ===')            circle_profile = nodes.new('GeometryNodeCurvePrimitiveCircle')    radius_scale = nodes.new('ShaderNodeMath')

            print(result.stderr)

            circle_profile.location = (-620, 80)    radius_scale.location = (-700, -40)

        if result.returncode == 0:

            print(f'Blender completed successfully: {output_path}')            circle_profile.inputs['Resolution'].default_value = 96    radius_scale.operation = 'MULTIPLY'

            return True

    radius_scale.inputs[1].default_value = 0.985

        print(f'Blender exited with status {result.returncode}')

        return False            radius_scale = nodes.new('ShaderNodeMath')

    finally:

        try:            radius_scale.location = (-820, 120)    combine_scale = nodes.new('ShaderNodeCombineXYZ')

            temp_script.unlink()

        except FileNotFoundError:            radius_scale.operation = 'MULTIPLY'    combine_scale.location = (-500, -40)

            pass

            radius_scale.inputs[1].default_value = PROFILE_SCALE



def batch_process(    instance_on_points = nodes.new('GeometryNodeInstanceOnPoints')

    data_dir: str,

    output_dir: str,            scale_vector = nodes.new('ShaderNodeCombineXYZ')    instance_on_points.location = (-300, 220)

    blender_path: Optional[str],

    fps: int,            scale_vector.location = (-620, 120)

    duration: float,

    resample_count: int,    realize_instances = nodes.new('GeometryNodeRealizeInstances')

    profile_scale: float,

    twist_turns: float,            instance_profiles = nodes.new('GeometryNodeInstanceOnPoints')    realize_instances.location = (-100, 220)

    curve_type: str,

) -> None:            instance_profiles.location = (-420, 240)

    """Process all JSON files in *data_dir* into *output_dir*."""

    store_radius = nodes.new('GeometryNodeStoreNamedAttribute')

    data_path = Path(data_dir)

    output_path = Path(output_dir)            realize_profiles = nodes.new('GeometryNodeRealizeInstances')    store_radius.location = (100, 220)

    output_path.mkdir(parents=True, exist_ok=True)

            realize_profiles.location = (-220, 240)    store_radius.data_type = 'FLOAT'

    json_files = sorted(data_path.glob('*.json'))

    if not json_files:    store_radius.domain = 'POINT'

        print(f'No JSON files found in {data_dir}')

        return            store_radius = nodes.new('GeometryNodeStoreNamedAttribute')    store_radius.inputs[2].default_value = "radius"



    for json_file in json_files:            store_radius.location = (-20, 240)

        target_blend = output_path / f'{json_file.stem}_sweep.blend'

        target_render = output_path / f'{json_file.stem}.png'            store_radius.data_type = 'FLOAT'    store_curvature = nodes.new('GeometryNodeStoreNamedAttribute')

        print(f'\nProcessing {json_file.name} -> {target_blend.name}')

        run_blender_apollonian(            store_radius.domain = 'POINT'    store_curvature.location = (300, 220)

            str(json_file),

            str(target_blend),            store_radius.inputs['Name'].default_value = 'radius'    store_curvature.data_type = 'FLOAT'

            curve_type=curve_type,

            render_output=str(target_render),    store_curvature.domain = 'POINT'

            blender_path=blender_path,

            fps=fps,            store_curvature = nodes.new('GeometryNodeStoreNamedAttribute')    store_curvature.inputs[2].default_value = "curvature"

            duration=duration,

            resample_count=resample_count,            store_curvature.location = (180, 240)

            profile_scale=profile_scale,

            twist_turns=twist_turns,            store_curvature.data_type = 'FLOAT'    store_depth = nodes.new('GeometryNodeStoreNamedAttribute')

        )

            store_curvature.domain = 'POINT'    store_depth.location = (500, 220)



def build_argument_parser() -> argparse.ArgumentParser:            store_curvature.inputs['Name'].default_value = 'curvature'    store_depth.data_type = 'INT'

    parser = argparse.ArgumentParser(

        description='Generate Apollonian sweep geometry through Blender CLI.',    store_depth.domain = 'POINT'

    )

            store_depth = nodes.new('GeometryNodeStoreNamedAttribute')    store_depth.inputs[2].default_value = "depth"

    parser.add_argument('--input', help='Input Apollonian JSON file')

    parser.add_argument('--output', help='Destination .blend file path')            store_depth.location = (380, 240)

    parser.add_argument('--render', help='Optional render output path (.png/.mp4)')

    parser.add_argument(            store_depth.data_type = 'INT'    resample_curve = nodes.new('GeometryNodeResampleCurve')

        '--curve-type',

        default='torus_knot',            store_depth.domain = 'POINT'    resample_curve.location = (-500, -240)

        choices=['torus_knot', 'circle', 'bezier'],

        help='Spine curve preset to use',            store_depth.inputs['Name'].default_value = 'depth'    resample_curve.inputs['Count'].default_value = 1024

    )

    parser.add_argument('--blender-path', help='Explicit Blender executable path')

    parser.add_argument('--batch-dir', help='Process every JSON file in this directory')

    parser.add_argument('--batch-output', help='Where to store batch results (.blend/.png)')            resample_curve = nodes.new('GeometryNodeResampleCurve')    spline_parameter = nodes.new('GeometryNodeSplineParameter')

    parser.add_argument('--fps', type=int, default=30, help='Render frames per second')

    parser.add_argument('--duration', type=float, default=4.0, help='Animation duration (seconds)')            resample_curve.location = (-620, -240)    spline_parameter.location = (-500, -440)

    parser.add_argument('--resample-count', type=int, default=512, help='Spine resample count')

    parser.add_argument('--profile-scale', type=float, default=0.95, help='Scale factor applied to circle radii')            resample_curve.inputs['Count'].default_value = RESAMPLE_COUNT

    parser.add_argument('--twist-turns', type=float, default=1.5, help='Total twist turns applied along the spine')

    parser.add_argument('--torus-p', type=int, default=3, help='Torus knot p parameter')    tilt_factor = nodes.new('ShaderNodeMath')

    parser.add_argument('--torus-q', type=int, default=2, help='Torus knot q parameter')

    parser.add_argument('--major-radius', type=float, default=3.0, help='Torus knot major radius')            spline_parameter = nodes.new('GeometryNodeSplineParameter')    tilt_factor.location = (-300, -440)

    parser.add_argument('--minor-radius', type=float, default=1.0, help='Torus knot minor radius')

    parser.add_argument('--resolution', type=int, default=256, help='Curve resolution for torus knot')            spline_parameter.location = (-420, -420)    tilt_factor.operation = 'MULTIPLY'

    parser.add_argument('--circle-radius', type=float, default=2.5, help='Radius for circle spine')

    return parser    tilt_factor.inputs[1].default_value = 6.283185307179586



            tilt_math = nodes.new('ShaderNodeMath')

def main(argv: Optional[list[str]] = None) -> int:

    parser = build_argument_parser()            tilt_math.location = (-220, -420)    set_curve_tilt = nodes.new('GeometryNodeSetCurveTilt')

    args = parser.parse_args(argv)

            tilt_math.operation = 'MULTIPLY'    set_curve_tilt.location = (-100, -240)

    if args.batch_dir and args.batch_output:

        batch_process(            tilt_math.inputs[1].default_value = TOTAL_TWIST

            args.batch_dir,

            args.batch_output,    curve_to_mesh = nodes.new('GeometryNodeCurveToMesh')

            blender_path=args.blender_path,

            fps=args.fps,            set_curve_tilt = nodes.new('GeometryNodeSetCurveTilt')    curve_to_mesh.location = (120, -240)

            duration=args.duration,

            resample_count=args.resample_count,            set_curve_tilt.location = (-20, -240)    curve_to_mesh.inputs['Fill Caps'].default_value = False

            profile_scale=args.profile_scale,

            twist_turns=args.twist_turns,

            curve_type=args.curve_type,

        )            curve_to_mesh = nodes.new('GeometryNodeCurveToMesh')    shade_smooth = nodes.new('GeometryNodeSetShadeSmooth')

        return 0

            curve_to_mesh.location = (180, -240)    shade_smooth.location = (320, -240)

    if not args.input or not args.output:

        parser.error('Either provide --input and --output or use batch mode.')            curve_to_mesh.inputs['Fill Caps'].default_value = False    shade_smooth.inputs['Shade Smooth'].default_value = True



    curve_kwargs: Dict[str, Any] = {

        'torus_p': args.torus_p,

        'torus_q': args.torus_q,            shade_smooth = nodes.new('GeometryNodeSetShadeSmooth')    # Link points filtering chain

        'major_radius': args.major_radius,

        'minor_radius': args.minor_radius,            shade_smooth.location = (380, -240)    links.new(points_info.outputs['Geometry'], separate_outer.inputs['Geometry'])

        'resolution': args.resolution,

        'radius': args.circle_radius,            shade_smooth.inputs['Shade Smooth'].default_value = True    links.new(outer_flag_attr.outputs['Attribute'], separate_outer.inputs['Selection'])

    }



    ok = run_blender_apollonian(

        args.input,            links.new(outer_attr.outputs['Attribute'], invert_outer.inputs[0])    # Build profile instances

        args.output,

        curve_type=args.curve_type,            links.new(points_info.outputs['Geometry'], separate_points.inputs['Geometry'])    links.new(separate_outer.outputs['Inverted'], instance_on_points.inputs['Points'])

        render_output=args.render,

        blender_path=args.blender_path,            links.new(invert_outer.outputs['Boolean'], separate_points.inputs['Selection'])    links.new(circle_profile.outputs['Curve'], instance_on_points.inputs['Instance'])

        fps=args.fps,

        duration=args.duration,    links.new(radius_attr.outputs['Attribute'], radius_scale.inputs[0])

        resample_count=args.resample_count,

        profile_scale=args.profile_scale,            links.new(radius_attr.outputs['Attribute'], radius_scale.inputs[0])    links.new(radius_scale.outputs[0], combine_scale.inputs['X'])

        twist_turns=args.twist_turns,

        **curve_kwargs,            links.new(radius_scale.outputs['Value'], scale_vector.inputs['X'])    links.new(radius_scale.outputs[0], combine_scale.inputs['Y'])

    )

            links.new(radius_scale.outputs['Value'], scale_vector.inputs['Y'])    links.new(radius_scale.outputs[0], combine_scale.inputs['Z'])

    return 0 if ok else 1

            links.new(radius_scale.outputs['Value'], scale_vector.inputs['Z'])    links.new(combine_scale.outputs['Vector'], instance_on_points.inputs['Scale'])



if __name__ == '__main__':    links.new(instance_on_points.outputs['Instances'], realize_instances.inputs['Geometry'])

    sys.exit(main())

            links.new(separate_points.outputs['Selection'], instance_profiles.inputs['Points'])

            links.new(circle_profile.outputs['Curve'], instance_profiles.inputs['Instance'])    # Store attributes for shading

            links.new(scale_vector.outputs['Vector'], instance_profiles.inputs['Scale'])    links.new(realize_instances.outputs['Geometry'], store_radius.inputs['Geometry'])

    links.new(radius_attr.outputs['Attribute'], store_radius.inputs['Value'])

            links.new(instance_profiles.outputs['Instances'], realize_profiles.inputs['Geometry'])    links.new(store_radius.outputs['Geometry'], store_curvature.inputs['Geometry'])

            links.new(realize_profiles.outputs['Geometry'], store_radius.inputs['Geometry'])    links.new(curvature_attr.outputs['Attribute'], store_curvature.inputs['Value'])

            links.new(radius_attr.outputs['Attribute'], store_radius.inputs['Value'])    links.new(store_curvature.outputs['Geometry'], store_depth.inputs['Geometry'])

    links.new(depth_attr.outputs['Attribute'], store_depth.inputs['Value'])

            links.new(store_radius.outputs['Geometry'], store_curvature.inputs['Geometry'])

            links.new(curvature_attr.outputs['Attribute'], store_curvature.inputs['Value'])    # Prepare swept curve with stable frame

    links.new(curve_info.outputs['Geometry'], resample_curve.inputs['Curve'])

            links.new(store_curvature.outputs['Geometry'], store_depth.inputs['Geometry'])    links.new(resample_curve.outputs['Curve'], set_curve_tilt.inputs['Curve'])

            links.new(depth_attr.outputs['Attribute'], store_depth.inputs['Value'])    links.new(spline_parameter.outputs['Factor'], tilt_factor.inputs[0])

    links.new(tilt_factor.outputs[0], set_curve_tilt.inputs['Tilt'])

            links.new(curve_info.outputs['Geometry'], resample_curve.inputs['Curve'])

            links.new(resample_curve.outputs['Curve'], set_curve_tilt.inputs['Curve'])    # Sweep profile along path

            links.new(spline_parameter.outputs['Factor'], tilt_math.inputs[0])    links.new(set_curve_tilt.outputs['Curve'], curve_to_mesh.inputs['Curve'])

            links.new(tilt_math.outputs['Value'], set_curve_tilt.inputs['Tilt'])    links.new(store_depth.outputs['Geometry'], curve_to_mesh.inputs['Profile Curve'])

    links.new(curve_to_mesh.outputs['Mesh'], shade_smooth.inputs['Geometry'])

            links.new(set_curve_tilt.outputs['Curve'], curve_to_mesh.inputs['Curve'])    links.new(shade_smooth.outputs['Geometry'], output_node.inputs['Geometry'])

            links.new(store_depth.outputs['Geometry'], curve_to_mesh.inputs['Profile Curve'])

            links.new(curve_to_mesh.outputs['Mesh'], shade_smooth.inputs['Geometry'])    # Hide helper objects so only the generated mesh renders

            links.new(shade_smooth.outputs['Geometry'], group_out.inputs['Geometry'])    points_obj.hide_render = True

    points_obj.hide_set(True)

            points_obj.hide_render = True    spine_obj.hide_render = True

            points_obj.hide_set(True)    spine_obj.hide_set(True)

            spine_obj.hide_render = True

            spine_obj.hide_set(True)    print(f"Created Geometry Nodes setup for {{name}}")

    return obj

            sweep_obj.data.clear_geometry()

            return sweep_obj# Create material with curvature coloring

def create_curvature_material(name="ApollonianMaterial"):

    mat = bpy.data.materials.new(name)

        def create_material(stats):    mat.use_nodes = True

            curvature_min, curvature_max = stats['curvature']    

            depth_min, depth_max = stats['depth']    nodes = mat.node_tree.nodes

    links = mat.node_tree.links

            mat = bpy.data.materials.new('ApollonianMaterial')    

            mat.use_nodes = True    nodes.clear()

    

            nodes = mat.node_tree.nodes    output = nodes.new('ShaderNodeOutputMaterial')

            links = mat.node_tree.links    principled = nodes.new('ShaderNodeBsdfPrincipled')

            nodes.clear()    

    # Simple metallic material for now

            output = nodes.new('ShaderNodeOutputMaterial')    principled.inputs['Metallic'].default_value = 0.8

            output.location = (600, 0)    principled.inputs['Roughness'].default_value = 0.2

    principled.inputs['Base Color'].default_value = (0.8, 0.3, 0.1, 1.0)

            principled = nodes.new('ShaderNodeBsdfPrincipled')    

            principled.location = (200, 40)    links.new(principled.outputs['BSDF'], output.inputs['Surface'])

            principled.inputs['Metallic'].default_value = 0.65    

            principled.inputs['Roughness'].default_value = 0.25    return mat



            emission = nodes.new('ShaderNodeEmission')# Main execution

            emission.location = (200, -200)try:

            emission.inputs['Strength'].default_value = 1.0    print("Loading Apollonian data...")

    start_time = time.time()

            add_shader = nodes.new('ShaderNodeAddShader')    

            add_shader.location = (400, -80)    data = load_apollonian_data("{escaped_input}")

    points_obj = create_point_cloud_from_data(data)

            curvature_attr = nodes.new('ShaderNodeAttribute')    

            curvature_attr.location = (-600, 120)    print("Creating spine curve...")

            curvature_attr.attribute_name = 'curvature'    spine_obj = create_spine_curve()

    

            curvature_map = nodes.new('ShaderNodeMapRange')    print("Setting up sweep geometry...")

            curvature_map.location = (-400, 120)    sweep_obj = create_sweep_geometry_nodes(points_obj, spine_obj)

            curvature_map.inputs['From Min'].default_value = curvature_min    

            curvature_map.inputs['From Max'].default_value = max(curvature_max, curvature_min + 1e-5)    print("Creating materials...")

            curvature_map.clamp = True    material = create_curvature_material()

    sweep_obj.data.materials.append(material)

            curvature_ramp = nodes.new('ShaderNodeValToRGB')    

            curvature_ramp.location = (-200, 120)    # Set active object and save

            curvature_ramp.color_ramp.interpolation = 'EASE'    bpy.context.view_layer.objects.active = sweep_obj

            curvature_ramp.color_ramp.elements[0].color = (0.1, 0.2, 0.7, 1.0)    

            curvature_ramp.color_ramp.elements[1].color = (1.0, 0.7, 0.2, 1.0)    print("Saving blend file...")

    bpy.ops.wm.save_as_mainfile(filepath="{escaped_output}")

            depth_attr = nodes.new('ShaderNodeAttribute')    

            depth_attr.location = (-600, -160)    total_time = time.time() - start_time

            depth_attr.attribute_name = 'depth'    print(f"=== Completed in {{total_time:.2f}} seconds ===")

    

            depth_map = nodes.new('ShaderNodeMapRange')    # Optional: render if requested

            depth_map.location = (-400, -160)    render_output = "{escaped_render}"

            depth_map.inputs['From Min'].default_value = depth_min    if render_output and render_output != "None":

            depth_map.inputs['From Max'].default_value = max(depth_max, depth_min + 1e-5)        print("Setting up render...")

            depth_map.clamp = True        scene.render.filepath = render_output

            depth_map.inputs['To Min'].default_value = 0.2        scene.render.resolution_x = 1920

            depth_map.inputs['To Max'].default_value = 4.0        scene.render.resolution_y = 1080

        scene.cycles.samples = 128

            links.new(curvature_attr.outputs['Fac'], curvature_map.inputs['Value'])

            links.new(curvature_map.outputs['Result'], curvature_ramp.inputs['Fac'])        # Add basic lighting

            links.new(curvature_ramp.outputs['Color'], principled.inputs['Base Color'])        bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

            links.new(curvature_ramp.outputs['Color'], emission.inputs['Color'])        light_obj = bpy.context.active_object

        light_obj.data.energy = 5.0

            links.new(depth_attr.outputs['Fac'], depth_map.inputs['Value'])

            links.new(depth_map.outputs['Result'], emission.inputs['Strength'])        # Add camera with simple orbit animation

        bpy.ops.object.camera_add(location=(0, -8, 3))

            links.new(principled.outputs['BSDF'], add_shader.inputs[0])        camera_obj = bpy.context.active_object

            links.new(emission.outputs['Emission'], add_shader.inputs[1])        camera_obj.name = "ApollonianCamera"

            links.new(add_shader.outputs['Shader'], output.inputs['Surface'])        bpy.context.scene.camera = camera_obj



            mat.use_backface_culling = False        rig = bpy.data.objects.new("CameraRig", None)

            return mat        rig.empty_display_type = 'PLAIN_AXES'

        bpy.context.collection.objects.link(rig)

        camera_obj.parent = rig

        def add_camera_and_light(target_obj):

            bpy.ops.object.light_add(type='SUN', location=(6.0, -6.0, 8.0))        # Track camera to sweep object

            light = bpy.context.active_object        track = camera_obj.constraints.new(type='TRACK_TO')

            light.data.energy = 5.5        track.target = sweep_obj

        track.track_axis = 'TRACK_NEGATIVE_Z'

            bpy.ops.object.camera_add(location=(0.0, -10.0, 4.0))        track.up_axis = 'UP_Y'

            camera = bpy.context.active_object

            camera.name = 'ApollonianCamera'        rig.rotation_euler = (0.0, 0.0, 0.0)

        rig.keyframe_insert(data_path="rotation_euler", frame={frame_start})

            rig = bpy.data.objects.new('CameraRig', None)        rig.rotation_euler = (0.0, 0.0, math.radians(360.0))

            bpy.context.collection.objects.link(rig)        rig.keyframe_insert(data_path="rotation_euler", frame={frame_end})

            camera.parent = rig

        if rig.animation_data and rig.animation_data.action:

            constraint = camera.constraints.new(type='TRACK_TO')            for fcurve in rig.animation_data.action.fcurves:

            constraint.target = target_obj                for keyframe in fcurve.keyframe_points:

            constraint.track_axis = 'TRACK_NEGATIVE_Z'                    keyframe.interpolation = 'LINEAR'

            constraint.up_axis = 'UP_Y'

        if {str(do_animation)}:

            rig.rotation_euler = (0.0, 0.0, 0.0)            scene.render.image_settings.file_format = 'FFMPEG'

            rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_START)            scene.render.ffmpeg.format = 'MPEG4'

            rig.rotation_euler = (0.0, 0.0, math.radians(360.0))            scene.render.ffmpeg.codec = 'H264'

            rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_END)            scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'

            scene.render.ffmpeg.ffmpeg_preset = 'GOOD'

            if rig.animation_data and rig.animation_data.action:            scene.render.ffmpeg.gopsize = {fps}

                for fcurve in rig.animation_data.action.fcurves:            print("Starting animation render...")

                    for keyframe in fcurve.keyframe_points:            bpy.ops.render.render(animation=True)

                        keyframe.interpolation = 'LINEAR'            print(f"Video saved to {{render_output}}")

        else:

            bpy.context.scene.camera = camera            print("Starting still render...")

            bpy.ops.render.render(write_still=True)

            print(f"Render saved to {{render_output}}")

        clear_scene()    Returns:

        scene = configure_cycles()        True if successful, False otherwise

    """

        print('Loading Apollonian data...')    

        data = load_apollonian(INPUT_JSON)    if blender_path is None:

        blender_path = find_blender_executable()

        curvature_values = data.get('attributes', {{}}).get('curvature', [1.0])        if blender_path is None:

        depth_values = data.get('attributes', {{}}).get('depth', [0])            print("Could not find Blender executable")

        attribute_stats = {{            return False

            'curvature': (min(curvature_values), max(curvature_values)),    

            'depth': (min(depth_values), max(depth_values)),    blender_path = str(Path(blender_path).resolve())

        }}    input_json_path = Path(input_json).resolve()

    output_blend_path = Path(output_blend).resolve()

        points_obj = create_point_cloud(data)    output_blend_path.parent.mkdir(parents=True, exist_ok=True)

        spine_obj = create_spine_curve(CURVE_TYPE, CURVE_PARAMS)    render_output_path = Path(render_output).resolve() if render_output else None

    if render_output_path:

        print('Building Geometry Nodes sweep...')        render_output_path.parent.mkdir(parents=True, exist_ok=True)

        sweep_obj = build_geometry_nodes(points_obj, spine_obj, attribute_stats)

    print(f"Using Blender: {blender_path}")

        print('Assigning material...')    

        material = create_material(attribute_stats)    # Create temporary script file with absolute paths

        sweep_obj.data.materials.clear()    script_content = create_blender_script(

        sweep_obj.data.materials.append(material)        str(input_json_path),

        str(output_blend_path),

        bpy.context.view_layer.objects.active = sweep_obj        curve_type,

        str(render_output_path) if render_output_path else None,

        add_camera_and_light(sweep_obj)        fps=fps,

        duration=duration,

        print('Saving blend file...')        **kwargs

        bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)    )

    

        if RENDER_OUTPUT not in (None, ''):    script_path = output_blend_path.parent / "temp_apollonian_script.py"

            print('Rendering to', RENDER_OUTPUT)    with open(script_path, 'w') as f:

            scene.render.filepath = RENDER_OUTPUT        f.write(script_content)

            scene.render.resolution_x = 1920    

            scene.render.resolution_y = 1080    try:

            scene.cycles.samples = 128        # Run Blender in background mode

        cmd = [

            if RENDER_OUTPUT.lower().endswith(('.mp4', '.mov', '.avi')):            blender_path,

                scene.render.image_settings.file_format = 'FFMPEG'            "--background",

                scene.render.ffmpeg.format = 'MPEG4'            "--python",

                scene.render.ffmpeg.codec = 'H264'            str(script_path.resolve())

                scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'        ]

                scene.render.ffmpeg.ffmpeg_preset = 'GOOD'        

                scene.render.ffmpeg.gopsize = FPS        print(f"Running command: {' '.join(cmd)}")

                bpy.ops.render.render(animation=True)        

            else:        result = subprocess.run(

                bpy.ops.render.render(write_still=True)            cmd, 

        """            capture_output=True, 

    )            text=True, 

    # fmt: on            cwd=str(input_json_path.parent)

        )

    return script        

        # Print output

        if result.stdout:

def run_blender_apollonian(            print("=== Blender Output ===")

    input_json: str,            print(result.stdout)

    output_blend: str,        

    curve_type: str = 'torus_knot',        if result.stderr:

    render_output: Optional[str] = None,            print("=== Blender Errors ===")

    blender_path: Optional[str] = None,            print(result.stderr)

    fps: int = 30,        

    duration: float = 4.0,        if result.returncode == 0:

    resample_count: int = 512,            print(f"Successfully created {output_blend}")

    profile_scale: float = 0.95,            return True

    twist_turns: float = 1.5,        else:

    **curve_kwargs: Any,            print(f"Blender process failed with return code {result.returncode}")

) -> bool:            return False

    """Generate the sweep by running Blender in background mode."""            

    except Exception as e:

    if blender_path is None:        print(f"Failed to run Blender: {e}")

        blender_path = find_blender_executable()        return False

        if blender_path is None:    

            print('Unable to locate a Blender executable')    finally:

            return False        # Clean up temporary script

        if script_path.exists():

    blender_path = str(Path(blender_path).resolve())            script_path.unlink()

    input_path = Path(input_json).resolve()

    output_path = Path(output_blend).resolve()def batch_process_apollonian(data_dir: str, output_dir: str, 

                           blender_path: Optional[str] = None,

    output_path.parent.mkdir(parents=True, exist_ok=True)                           fps: int = 30,

    render_path = Path(render_output).resolve() if render_output else None                           duration: float = 4.0):

    if render_path:    """

        render_path.parent.mkdir(parents=True, exist_ok=True)    Batch process multiple Apollonian datasets.

    

    curve_settings = {    Args:

        'torus_knot': {        data_dir: Directory containing JSON data files

            'p': curve_kwargs.get('p') or curve_kwargs.get('torus_p') or 3,        output_dir: Directory for output .blend files

            'q': curve_kwargs.get('q') or curve_kwargs.get('torus_q') or 2,        blender_path: Path to Blender executable

            'major_radius': curve_kwargs.get('major_radius', 3.0),    """

            'minor_radius': curve_kwargs.get('minor_radius', 1.0),    data_path = Path(data_dir)

            'resolution': curve_kwargs.get('resolution', 256),    output_path = Path(output_dir)

        },    output_path.mkdir(exist_ok=True)

        'circle': {    

            'radius': curve_kwargs.get('radius', 2.0),    json_files = list(data_path.glob("*.json"))

        },    

        'bezier': {},    if not json_files:

    }.get(curve_type, {})        print(f"No JSON files found in {data_dir}")

        return

    script_content = create_blender_script(    

        str(input_path),    print(f"Found {len(json_files)} JSON files to process")

        str(output_path),    

        curve_type,    for json_file in json_files:

        str(render_path) if render_path else None,        print(f"\\nProcessing {json_file.name}...")

        fps=fps,        

        duration=duration,        output_blend = output_path / f"{json_file.stem}_sweep.blend"

        resample_count=resample_count,        render_output = output_path / f"{json_file.stem}_render.png"

        profile_scale=profile_scale,        

        twist_turns=twist_turns,        success = run_blender_apollonian(

        curve_settings=curve_settings,            str(json_file),

    )            str(output_blend),

            curve_type="torus_knot",

    temp_script = output_path.parent / 'apollonian_temp_script.py'            render_output=str(render_output),

    temp_script.write_text(script_content, encoding='utf8')            blender_path=blender_path,

            fps=fps,

    try:            duration=duration

        cmd = [        )

            blender_path,        

            '--background',        if success:

            '--python',            print(f"✓ Created {output_blend}")

            str(temp_script),        else:

        ]            print(f"✗ Failed to process {json_file}")

        print('Running Blender command:')

        print(' '.join(cmd))def main():

    parser = argparse.ArgumentParser(description='Blender CLI Apollonian Sweep Generator')

        result = subprocess.run(    parser.add_argument('--input', required=True, help='Input JSON file from apollonian_gasket.py')

            cmd,    parser.add_argument('--output', required=True, help='Output .blend file path')

            capture_output=True,    parser.add_argument('--curve-type', choices=['circle', 'torus_knot', 'bezier'], 

            text=True,                       default='torus_knot', help='Type of spine curve')

            cwd=str(input_path.parent),    parser.add_argument('--render', help='Optional render output path (.png)')

        )    parser.add_argument('--blender-path', help='Path to Blender executable')

    parser.add_argument('--batch-dir', help='Batch process directory (overrides --input)')

        if result.stdout:    parser.add_argument('--batch-output', help='Batch output directory')

            print('=== Blender stdout ===')    parser.add_argument('--fps', type=int, default=30, help='Render frames per second')

            print(result.stdout)    parser.add_argument('--duration', type=float, default=4.0, help='Animation duration in seconds')

    

        if result.stderr:    # Torus knot parameters

            print('=== Blender stderr ===')    parser.add_argument('--torus-p', type=int, default=3, help='Torus knot p parameter')

            print(result.stderr)    parser.add_argument('--torus-q', type=int, default=2, help='Torus knot q parameter')

    parser.add_argument('--major-radius', type=float, default=3.0, help='Torus major radius')

        if result.returncode == 0:    parser.add_argument('--minor-radius', type=float, default=1.0, help='Torus minor radius')

            print(f'Blender completed successfully: {output_path}')    parser.add_argument('--resolution', type=int, default=64, help='Curve resolution')

            return True    

    args = parser.parse_args()

        print(f'Blender exited with status {result.returncode}')    

        return False    if args.batch_dir and args.batch_output:

    finally:        # Batch processing mode

        try:        batch_process_apollonian(

            temp_script.unlink()            args.batch_dir,

        except FileNotFoundError:            args.batch_output,

            pass            args.blender_path,

            fps=args.fps,

            duration=args.duration

def batch_process(        )

    data_dir: str,    else:

    output_dir: str,        # Single file processing

    blender_path: Optional[str],        curve_kwargs = {

    fps: int,            'p': args.torus_p,

    duration: float,            'q': args.torus_q,

    resample_count: int,            'major_radius': args.major_radius,

    profile_scale: float,            'minor_radius': args.minor_radius,

    twist_turns: float,            'resolution': args.resolution

    curve_type: str,        }

) -> None:        

    """Process all JSON files in *data_dir* into *output_dir*."""        success = run_blender_apollonian(

            args.input,

    data_path = Path(data_dir)            args.output,

    output_path = Path(output_dir)            args.curve_type,

    output_path.mkdir(parents=True, exist_ok=True)            args.render,

            args.blender_path,

    json_files = sorted(data_path.glob('*.json'))            fps=args.fps,

    if not json_files:            duration=args.duration,

        print(f'No JSON files found in {data_dir}')            **curve_kwargs

        return        )

        

    for json_file in json_files:        if success:

        target_blend = output_path / f'{json_file.stem}_sweep.blend'            print("\\n✓ Apollonian sweep generation completed successfully")

        target_render = output_path / f'{json_file.stem}.png'        else:

        print(f'\nProcessing {json_file.name} -> {target_blend.name}')            print("\\n✗ Apollonian sweep generation failed")

        run_blender_apollonian(            sys.exit(1)

            str(json_file),

            str(target_blend),if __name__ == '__main__':

            curve_type=curve_type,    main()
            render_output=str(target_render),
            blender_path=blender_path,
            fps=fps,
            duration=duration,
            resample_count=resample_count,
            profile_scale=profile_scale,
            twist_turns=twist_turns,
        )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Generate Apollonian sweep geometry through Blender CLI.',
    )

    parser.add_argument('--input', help='Input Apollonian JSON file')
    parser.add_argument('--output', help='Destination .blend file path')
    parser.add_argument('--render', help='Optional render output path (.png/.mp4)')
    parser.add_argument(
        '--curve-type',
        default='torus_knot',
        choices=['torus_knot', 'circle', 'bezier'],
        help='Spine curve preset to use',
    )
    parser.add_argument('--blender-path', help='Explicit Blender executable path')
    parser.add_argument('--batch-dir', help='Process every JSON file in this directory')
    parser.add_argument('--batch-output', help='Where to store batch results (.blend/.png)')
    parser.add_argument('--fps', type=int, default=30, help='Render frames per second')
    parser.add_argument('--duration', type=float, default=4.0, help='Animation duration (seconds)')
    parser.add_argument('--resample-count', type=int, default=512, help='Spine resample count')
    parser.add_argument('--profile-scale', type=float, default=0.95, help='Scale factor applied to circle radii')
    parser.add_argument('--twist-turns', type=float, default=1.5, help='Total twist turns applied along the spine')
    parser.add_argument('--torus-p', type=int, default=3, help='Torus knot p parameter')
    parser.add_argument('--torus-q', type=int, default=2, help='Torus knot q parameter')
    parser.add_argument('--major-radius', type=float, default=3.0, help='Torus knot major radius')
    parser.add_argument('--minor-radius', type=float, default=1.0, help='Torus knot minor radius')
    parser.add_argument('--resolution', type=int, default=256, help='Curve resolution for torus knot')
    parser.add_argument('--circle-radius', type=float, default=2.5, help='Radius for circle spine')
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.batch_dir and args.batch_output:
        batch_process(
            args.batch_dir,
            args.batch_output,
            blender_path=args.blender_path,
            fps=args.fps,
            duration=args.duration,
            resample_count=args.resample_count,
            profile_scale=args.profile_scale,
            twist_turns=args.twist_turns,
            curve_type=args.curve_type,
        )
        return 0

    if not args.input or not args.output:
        parser.error('Either provide --input and --output or use batch mode.')

    curve_kwargs: Dict[str, Any] = {
        'torus_p': args.torus_p,
        'torus_q': args.torus_q,
        'major_radius': args.major_radius,
        'minor_radius': args.minor_radius,
        'resolution': args.resolution,
        'radius': args.circle_radius,
    }

    ok = run_blender_apollonian(
        args.input,
        args.output,
        curve_type=args.curve_type,
        render_output=args.render,
        blender_path=args.blender_path,
        fps=args.fps,
        duration=args.duration,
        resample_count=args.resample_count,
        profile_scale=args.profile_scale,
        twist_turns=args.twist_turns,
        **curve_kwargs,
    )

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
