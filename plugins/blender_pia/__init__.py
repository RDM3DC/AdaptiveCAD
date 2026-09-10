bl_info = {
    "name": "Adaptive Pi (πₐ) Tools",
    "blender": (3, 0, 0),
    "category": "Add Mesh",
    "version": (0, 2, 0),
    "author": "RDM3DC",
    "description": "Adaptive-π circle & heatmap tools",
}

import json
import math
import os

import bmesh
import bpy
import numpy as np

_retained_import_contract = (np,)
from mathutils import Vector as Vector

# Shared config file (same as FreeCAD workbench)
CFG_DIR = os.path.join(os.path.expanduser("~"), ".adaptivecad")
CFG_PATH = os.path.join(CFG_DIR, "pia_settings.json")
DEFAULTS = {"beta": 0.2, "s0": 1.0, "clamp": 0.3, "segments": 96}


def load_cfg():
    try:
        if os.path.exists(CFG_PATH):
            return json.loads(open(CFG_PATH, "r").read())
    except BaseException:
        pass
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_PATH, "w") as f:
        f.write(json.dumps(DEFAULTS, indent=2))
    return DEFAULTS.copy()


def save_cfg(cfg):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_PATH, "w") as f:
        f.write(json.dumps(cfg, indent=2))


def pi_a(kappa, scale, beta=0.2, s0=1.0, clamp=0.3):
    base = math.pi
    s0 = max(s0, 1e-9)
    frac = beta * (kappa * (scale / s0)) ** 2
    frac = max(-clamp, min(clamp, frac))
    return base * (1.0 + frac)


def make_adaptive_circle(radius, n, kappa, scale, beta, s0, clamp):
    pts = []
    pa = pi_a(kappa, scale, beta, s0, clamp)
    total_angle = 2.0 * math.pi * (pa / math.pi)
    for i in range(n):
        theta = total_angle * (i / float(n))
        pts.append((radius * math.cos(theta), radius * math.sin(theta), 0.0))
    return pts


class PIA_OT_add_circle(bpy.types.Operator):
    bl_idname = "mesh.add_pia_circle"
    bl_label = "Add Adaptive-π Circle"
    bl_options = {"REGISTER", "UNDO"}
    radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.001, max=1e6)
    segments: bpy.props.IntProperty(name="Segments", default=96, min=8, max=4096)
    kappa: bpy.props.FloatProperty(name="Curvature κ (1/m)", default=0.0, min=0.0, max=1e3)

    def execute(self, context):
        cfg = load_cfg()
        beta, s0, clamp = cfg.get("beta", 0.2), cfg.get("s0", 1.0), cfg.get("clamp", 0.3)
        n = self.segments or int(cfg.get("segments", 96))
        pts = make_adaptive_circle(
            self.radius, n, self.kappa, max(self.radius, 1e-9), beta, s0, clamp
        )
        mesh = bpy.data.meshes.new("PiACircle")
        edges = [(i, (i + 1) % len(pts)) for i in range(len(pts))]
        mesh.from_pydata(pts, edges, [])
        obj = bpy.data.objects.new("PiACircle", mesh)
        context.collection.objects.link(obj)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


def curvature_proxy(v):
    # Simple proxy: average deviation of neighbor directions (polyline-ish proxy)
    nbrs = [e.other_vert(v) for e in v.link_edges]
    if not nbrs:
        return 0.0
    dirs = []
    for n in nbrs:
        d = n.co - v.co
        if d.length > 1e-9:
            dirs.append(d.normalized())
    if len(dirs) < 2:
        return 0.0
    s = 0.0
    for i in range(len(dirs) - 1):
        s += 1.0 - max(-1.0, min(1.0, dirs[i].dot(dirs[i + 1])))
    return s / (len(dirs) - 1)


class PIA_OT_heatmap(bpy.types.Operator):
    bl_idname = "object.pia_heatmap"
    bl_label = "PiA Heatmap (vertex colors)"
    bl_options = {"REGISTER", "UNDO"}
    clamp: bpy.props.FloatProperty(name="Clamp", default=0.3, min=0.0, max=1.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object")
            return {"CANCELLED"}
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        layer = bm.loops.layers.color.get("pia") or bm.loops.layers.color.new("pia")

        # compute proxy curvature per vertex
        kmap = {}
        for v in bm.verts:
            k = curvature_proxy(v)
            kmap[v.index] = min(self.clamp, max(0.0, k))

        for f in bm.faces:
            for loop in f.loops:
                kval = kmap.get(loop.vert.index, 0.0) / max(1e-9, self.clamp)
                col = (kval, 0.0, 1.0 - kval, 1.0)
                loop[layer] = col
        bm.to_mesh(me)
        bm.free()
        me.update()
        return {"FINISHED"}


class PIA_OT_settings(bpy.types.Operator):
    bl_idname = "wm.pia_settings"
    bl_label = "PiA Settings"
    bl_options = {"REGISTER", "UNDO"}
    beta: bpy.props.FloatProperty(name="beta", default=0.2, min=0.0, max=10.0, precision=4)
    s0: bpy.props.FloatProperty(name="s0 (m)", default=1.0, min=1e-6, max=1e6, precision=6)
    clamp: bpy.props.FloatProperty(name="clamp", default=0.3, min=0.0, max=1.0, precision=3)
    segments: bpy.props.IntProperty(name="segments", default=96, min=8, max=4096)

    def invoke(self, context, event):
        cfg = load_cfg()
        self.beta = cfg.get("beta", 0.2)
        self.s0 = cfg.get("s0", 1.0)
        self.clamp = cfg.get("clamp", 0.3)
        self.segments = cfg.get("segments", 96)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        cfg = {
            "beta": self.beta,
            "s0": self.s0,
            "clamp": self.clamp,
            "segments": int(self.segments),
        }
        save_cfg(cfg)
        self.report({"INFO"}, "PiA settings saved")
        return {"FINISHED"}


def menu_func(self, context):
    self.layout.operator(PIA_OT_add_circle.bl_idname, icon="MESH_CIRCLE")
    self.layout.operator(PIA_OT_heatmap.bl_idname, icon="GROUP_VCOL")


classes = (PIA_OT_add_circle, PIA_OT_heatmap, PIA_OT_settings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
