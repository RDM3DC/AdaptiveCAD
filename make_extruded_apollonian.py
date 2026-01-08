#!/usr/bin/env python3
"""
make_extruded_apollonian.py
---------------------------------

One-shot pipeline to reproduce the animated "Extruded Apollonian fractal" look:

1) Generate Apollonian circle packing JSON (or reuse an existing file)
2) Launch Blender in background
3) Inside Blender, build a Geometry Nodes sweep along a torus-knot path
4) Add curvature/depth-driven material, camera orbit, basic lighting
5) Render a short MP4 spin to the requested output path

Usage (PowerShell):
  ..\.venv\Scripts\python.exe make_extruded_apollonian.py \
    --depth 5 \
    --out-dir .\out \
    --render .\out\extruded_apollonian.mp4

Notes:
- Requires Blender installed; the script will search common Windows install paths.
- You can override with --blender "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


THIS_DIR = Path(__file__).parent


# Common Windows install paths for Blender
DEFAULT_BLENDER_CANDIDATES = [
    r"C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
    r"C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe",
    "blender",  # in PATH
]


def find_blender(blender_arg: Optional[str]) -> Optional[str]:
    if blender_arg:
        exe = Path(blender_arg)
        return str(exe) if exe.exists() else None
    for cand in DEFAULT_BLENDER_CANDIDATES:
        if cand == "blender":
            try:
                out = subprocess.run([cand, "--version"], capture_output=True, text=True, timeout=10)
                if out.returncode == 0:
                    return cand
            except Exception:
                continue
        else:
            if Path(cand).exists():
                return cand
    return None


def generate_apollonian_json(depth: int, outer_radius: float, min_radius: float, out_path: Path) -> Path:
    """Call the local generator to create Apollonian points JSON."""
    # Import directly to avoid launching a subprocess
    sys.path.insert(0, str(THIS_DIR))
    import apollonian_gasket as ag  # type: ignore

    circles = ag.generate_apollonian_packing(max_depth=depth, outer_radius=outer_radius, min_radius=min_radius)

    data = {
        "points": [[float(c.z.real), float(c.z.imag), 0.0] for c in circles],
        "attributes": {
            "radius": [float(c.radius) for c in circles],
            "curvature": [float(abs(c.k)) for c in circles],
            "depth": [int(c.depth) for c in circles],
            "outer_circle": [bool(c.k < 0) for c in circles],
        },
        "metadata": {"count": len(circles), "format": "apollonian_gasket_v1"},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf8")
    return out_path


def _escape(p: Path) -> str:
    # Use raw string with escaped backslashes for safe embedding in Python code
    return str(p).replace("\\", "\\\\")


def build_blender_script(repo_dir: Path, json_path: Path, blend_out: Optional[Path], render_out: Optional[Path],
                         fps: int, seconds: float, twists: float,
                         p: int, q: int, major: float, minor: float, resolution: int) -> str:
    frame_start = 1
    frame_end = max(frame_start + int(round(max(0.1, seconds) * fps)) - 1, frame_start)
    total_twist = twists * 6.283185307179586  # 2*pi

    repo_str = _escape(repo_dir)
    json_str = _escape(json_path)
    blend_str = _escape(blend_out) if blend_out else ""
    render_str = _escape(render_out) if render_out else ""

    return f"""
import sys, os, math
from mathutils import Vector
import bpy

# Make repo modules importable inside Blender
repo_dir = r"{repo_str}"
if repo_dir not in sys.path:
    sys.path.append(repo_dir)

from blender_apollonian_sweep import (
    load_apollonian_data, create_point_cloud_from_data,
    create_spine_curve, setup_twist_animation,
    create_apollonian_sweep_geometry_nodes, create_curvature_material,
)

json_path = r"{json_str}"
blend_out = r"{blend_str}"
render_out = r"{render_str}"
FPS = {fps}
FRAME_START = {frame_start}
FRAME_END = {frame_end}
TOTAL_TWIST = {total_twist}

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.fps = FPS
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END

# Try to enable GPU if available
try:
    prefs = bpy.context.preferences
    cycles_prefs = prefs.addons['cycles'].preferences
    for dev in cycles_prefs.devices:
        if dev.type == 'CUDA':
            dev.use = True
    cycles_prefs.compute_device_type = 'CUDA'
    scene.cycles.device = 'GPU'
except Exception:
    scene.cycles.device = 'CPU'

# Load data and build sweep
data = load_apollonian_data(json_path)
points_obj = create_point_cloud_from_data(data, "ApollonianPoints")
spine_obj = create_spine_curve("torus_knot", p={p}, q={q}, major_radius={major}, minor_radius={minor}, resolution={resolution})
setup_twist_animation(spine_obj, twists_per_loop={twists}, frame_count=FRAME_END)

sweep_obj = create_apollonian_sweep_geometry_nodes(points_obj, spine_obj, "ApollonianSweep")
mat = create_curvature_material("ApollonianMaterial")
sweep_obj.data.materials.clear()
sweep_obj.data.materials.append(mat)

# Camera + light
bpy.ops.object.light_add(type='SUN', location=(8.0, -6.0, 10.0))
light = bpy.context.active_object
light.data.energy = 4.0

bpy.ops.object.camera_add(location=(0.0, -11.0, 4.0))
camera = bpy.context.active_object
rig = bpy.data.objects.new('CameraRig', None)
bpy.context.collection.objects.link(rig)
camera.parent = rig

track = camera.constraints.new(type='TRACK_TO')
track.target = sweep_obj
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

rig.rotation_euler = (0.0, 0.0, 0.0)
rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_START)
rig.rotation_euler = (0.0, 0.0, math.radians(360.0))
rig.keyframe_insert(data_path='rotation_euler', frame=FRAME_END)
if rig.animation_data and rig.animation_data.action:
    for fcurve in rig.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'

scene.camera = camera

# Save .blend if requested
if blend_out:
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)

# Render if requested
if render_out:
    scene.render.filepath = render_out
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    if render_out.lower().endswith((".mp4", ".mov", ".avi")):
        scene.render.image_settings.file_format = 'FFMPEG'
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
        scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
        scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
        scene.render.ffmpeg.gopsize = FPS
        bpy.ops.render.render(animation=True)
    else:
        bpy.ops.render.render(write_still=True)
"""


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Recreate the spinning extruded Apollonian fractal animation")
    p.add_argument("--depth", type=int, default=5, help="Apollonian recursion depth")
    p.add_argument("--outer-radius", type=float, default=1.0, help="Outer circle radius")
    p.add_argument("--min-radius", type=float, default=1e-6, help="Minimum circle radius cutoff")
    p.add_argument("--json", type=str, help="Existing Apollonian points JSON; skip generation if provided")
    p.add_argument("--out-dir", type=str, default=str(THIS_DIR / "out"), help="Output directory for results")
    p.add_argument("--blend", type=str, help="Optional .blend output path")
    p.add_argument("--render", type=str, help="Optional render output (.png/.mp4)")
    p.add_argument("--fps", type=int, default=30, help="Frames per second")
    p.add_argument("--seconds", type=float, default=5.0, help="Animation duration in seconds")
    p.add_argument("--twists", type=float, default=2.0, help="Twists per loop along the spine")
    p.add_argument("--torus-p", type=int, default=3, help="Torus knot p parameter")
    p.add_argument("--torus-q", type=int, default=2, help="Torus knot q parameter")
    p.add_argument("--major", type=float, default=3.0, help="Torus knot major radius")
    p.add_argument("--minor", type=float, default=1.0, help="Torus knot minor radius")
    p.add_argument("--resolution", type=int, default=256, help="Spine curve resolution")
    p.add_argument("--blender", type=str, help="Path to blender.exe (optional)")

    args = p.parse_args(argv)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve input JSON: existing or generated
    if args.json:
        json_path = Path(args.json).resolve()
        if not json_path.exists():
            print(f"Provided --json not found: {json_path}")
            return 2
    else:
        json_path = out_dir / "apollonian_points.json"
        print(f"Generating Apollonian JSON at {json_path} (depth={args.depth})...")
        generate_apollonian_json(args.depth, args.outer_radius, args.min_radius, json_path)

    # Locate Blender
    blender_exe = find_blender(args.blender)
    if not blender_exe:
        print("Could not find Blender. Install Blender or pass --blender to this script.")
        return 3

    # Outputs
    blend_out = Path(args.blend).resolve() if args.blend else out_dir / "apollonian_sweep.blend"
    render_out = Path(args.render).resolve() if args.render else out_dir / "apollonian_spin.mp4"

    # Build a temporary Blender-side script
    script_text = build_blender_script(
        repo_dir=THIS_DIR,
        json_path=json_path,
        blend_out=blend_out,
        render_out=render_out,
        fps=args.fps,
        seconds=args.seconds,
        twists=args.twists,
        p=args.torus_p,
        q=args.torus_q,
        major=args.major,
        minor=args.minor,
        resolution=args.resolution,
    )

    with tempfile.TemporaryDirectory() as td:
        temp_py = Path(td) / "apollonian_build_and_render.py"
        temp_py.write_text(script_text, encoding="utf8")

        cmd = [str(blender_exe), "--background", "--python", str(temp_py)]
        print("Running Blender:")
        print(" ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            print("=== Blender stdout ===\n" + proc.stdout)
        if proc.stderr:
            print("=== Blender stderr ===\n" + proc.stderr)
        if proc.returncode != 0:
            print(f"Blender failed with exit code {proc.returncode}")
            return proc.returncode

    print(f"Done. Blend: {blend_out}\nRender: {render_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
