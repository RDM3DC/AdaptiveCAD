"""Headless GUI audit: tests what initializes and what fails."""
import importlib
import os
import sys
import traceback

# Ensure the workspace root is on sys.path so we import the local
# adaptivecad package (not a stale editable install elsewhere).
_workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QDockWidget

app = QApplication(sys.argv)

stats = {"ok": 0, "fail": 0, "warn": 0}
failures = []


def ok(area, detail=""):
    stats["ok"] += 1
    tag = f"{area}: {detail}" if detail else area
    print(f"  [OK]   {tag}")


def fail(area, detail=""):
    stats["fail"] += 1
    tag = f"{area}: {detail}" if detail else area
    failures.append(tag)
    print(f"  [FAIL] {tag}")


def warn(area, detail=""):
    stats["warn"] += 1
    tag = f"{area}: {detail}" if detail else area
    print(f"  [WARN] {tag}")


def section(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# ---- 1. MainWindow init ----
section("1. MainWindow initialization")
mw = None
try:
    from adaptivecad.gui.playground import MainWindow

    mw = MainWindow(app)
    ok("MainWindow created")
    print(f"       view type: {type(mw.view).__name__}")

    menubar = mw.win.menuBar()
    menus = []
    for action in menubar.actions():
        m = action.menu()
        if m:
            menus.append(m.title())
    print(f"       Menus: {menus}")

    docks = [d.windowTitle() for d in mw.win.findChildren(QDockWidget)]
    print(f"       Docks: {docks}")
    if not docks:
        warn("MainWindow", "No dock widgets created")
except Exception as e:
    traceback.print_exc()
    fail("MainWindow", str(e)[:120])

# ---- 2. Feature integration modules ----
section("2. Feature integration modules (from AdaptiveCAD-light)")
feature_modules = {
    "adaptivecad.gui.osnap": ["osnap_pick"],
    "adaptivecad.gui.dimensions": ["DimStyle", "LinearDimension", "RadialDimension", "AngularDimension"],
    "adaptivecad.gui.dim_tools": ["DimLinearTool", "DimRadialTool", "DimAngularTool", "MeasureTool", "ToolContext"],
    "adaptivecad.gui.dim_draw": ["draw_linear_dim", "draw_radial_dim", "draw_angular_dim"],
    "adaptivecad.gui.edit_tools": ["BreakTool", "TrimTool", "JoinTool", "ExtendTool"],
    "adaptivecad.gui.edit_ops": ["break_segment_at_point", "trim_segment_to", "join_polylines"],
    "adaptivecad.gui.geometry": ["circle_points", "curve_points", "polyline_length"],
    "adaptivecad.gui.intersect2d": ["seg_seg_intersection", "circle_circle_intersections"],
    "adaptivecad.gui.sketch_mode": ["SketchPlane"],
    "adaptivecad.gui.tools": ["SelectTool"],
}
for mod_name, symbols in feature_modules.items():
    try:
        mod = importlib.import_module(mod_name)
        missing = [s for s in symbols if not hasattr(mod, s)]
        if missing:
            warn(mod_name, f"missing symbols: {missing}")
        else:
            ok(mod_name, f"all {len(symbols)} symbols present")
    except Exception as e:
        fail(mod_name, str(e)[:100])

# ---- 3. Command definitions ----
section("3. Command instantiation audit")
from adaptivecad import command_defs

cmd_classes = []
for name in sorted(dir(command_defs)):
    obj = getattr(command_defs, name)
    if isinstance(obj, type) and name.endswith("Cmd") and name != "BaseCmd":
        cmd_classes.append((name, obj))

print(f"  Found {len(cmd_classes)} command classes")
for name, cls in cmd_classes:
    try:
        inst = cls()
        has_run = hasattr(inst, "run") and callable(inst.run)
        if has_run:
            ok(f"Cmd:{name}", "instantiates, has run()")
        else:
            warn(f"Cmd:{name}", "instantiates but no run()")
    except Exception as e:
        fail(f"Cmd:{name}", str(e)[:100])

# ---- 4. Analytic commands (defined in playground, not command_defs) ----
section("4. Analytic/Menu commands (from playground)")
from adaptivecad.gui import playground as pg_mod

analytic_cmds = [
    "NewAnalyticViewportCmd", "NewAnalyticViewportPanelCmd",
    "NewAnalyticBallCmd", "NewAnalyticSphereCmd", "NewAnalyticBoxCmd",
    "NewAnalyticCylinderCmd", "NewAnalyticCapsuleCmd", "NewAnalyticTorusCmd",
    "ConvertMeshToAnalyticCmd", "ConvertAnalyticToMeshCmd",
    "NewSuperellipseCmd", "NewPiCurveShellCmd", "NewHelixCmd",
    "NewTaperedCylinderCmd", "NewCapsuleCmd", "NewEllipsoidCmd",
    "SaveProjectCmd", "OpenProjectCmd",
]
for name in analytic_cmds:
    obj = getattr(pg_mod, name, None)
    if obj is None:
        fail(f"Analytic:{name}", "not found in playground module")
    elif callable(obj):
        try:
            inst = obj()
            has_run = hasattr(inst, "run") and callable(inst.run)
            if has_run:
                ok(f"Analytic:{name}")
            else:
                warn(f"Analytic:{name}", "no run() method")
        except Exception as e:
            fail(f"Analytic:{name}", f"instantiation error: {str(e)[:80]}")
    else:
        warn(f"Analytic:{name}", f"not callable: {type(obj)}")

# ---- 5. Test analytic command run() where safe ----
section("5. Command.run() smoke test (safe subset, needs mw)")
if mw:
    safe_tests = []
    for name in [
        "NewAnalyticSphereCmd", "NewAnalyticBoxCmd", "NewAnalyticTorusCmd",
        "NewAnalyticCapsuleCmd", "NewAnalyticCylinderCmd",
    ]:
        obj = getattr(pg_mod, name, None)
        if obj:
            safe_tests.append((name, obj))

    for name, cls in safe_tests:
        try:
            inst = cls()
            inst.run(mw)
            ok(f"run:{name}")
        except Exception as e:
            fail(f"run:{name}", f"{type(e).__name__}: {str(e)[:80]}")
else:
    warn("run:*", "Skipped -- MainWindow not available")

# ---- 6. SDF/aacore ----
section("6. SDF/aacore scene operations")
try:
    from adaptivecad.aacore.sdf import (
        KIND_BOX, KIND_SPHERE, KIND_TORUS, KIND_CAPSULE,
        KIND_MANDELBULB, KIND_GYROID, KIND_KLEIN, KIND_TREFOIL,
        KIND_MOBIUS, KIND_SUPERELLIPSOID, KIND_MENGER, KIND_HELICOID,
        KIND_ORBITAL, KIND_HYPERBOLIC,
        Prim, Scene,
    )
    import numpy as np

    sc = Scene()
    test_prims = [
        ("sphere", KIND_SPHERE, [1.0]),
        ("box", KIND_BOX, [0.5, 0.5, 0.5]),
        ("torus", KIND_TORUS, [1.0, 0.3]),
        ("capsule", KIND_CAPSULE, [0.5, 1.0]),
        ("mobius", KIND_MOBIUS, [1.0, 0.1]),
        ("superellipsoid", KIND_SUPERELLIPSOID, [0.8, 0.5]),
        ("gyroid", KIND_GYROID, [1.0, 0.0, 0.05]),
        ("trefoil", KIND_TREFOIL, [1.0, 0.1, 96]),
        ("mandelbulb", KIND_MANDELBULB, [8.0, 2.0, 16, 1.0]),
        ("klein", KIND_KLEIN, [1.0, 2.0, 0.0, 0.1]),
        ("helicoid", KIND_HELICOID, [0.15, 0.55, 0.35, 2.0]),
        ("menger", KIND_MENGER, [3, 1.0]),
        ("hyperbolic", KIND_HYPERBOLIC, [1.0, 7, 3]),
        ("orbital", KIND_ORBITAL, [2, 1, 0, 0.02]),
    ]
    for label, kind, params in test_prims:
        try:
            p = Prim(kind, params)
            sc.add(p)
            ok(f"SDF:{label}")
        except Exception as e:
            fail(f"SDF:{label}", str(e)[:80])

    try:
        pack = sc.to_gpu_structs()
        ok("SDF:to_gpu_structs", f"{len(sc.prims)} prims packed")
    except Exception as e:
        fail("SDF:to_gpu_structs", str(e)[:80])

    try:
        d, _, _ = sc.sdf(np.array([0.0, 0.0, 0.0]))
        ok(f"SDF:eval_at_origin", f"d={d:.4f}")
    except Exception as e:
        fail("SDF:eval_at_origin", str(e)[:80])

    try:
        sc.prims[0].set_transform(pos=[2, 0, 0], euler=[0, 45, 0], scale=[1.5, 1.5, 1.5])
        ok("SDF:set_transform")
    except Exception as e:
        fail("SDF:set_transform", str(e)[:80])
except ImportError as e:
    fail("SDF:import", str(e)[:100])

# ---- 7. Sketch system ----
section("7. Sketch constraint system")
try:
    from adaptivecad.sketch_solver import Sketch, FixedConstraint, DistanceConstraint
    sk = Sketch()
    p0 = sk.add_point(0, 0)
    p1 = sk.add_point(10, 0)
    sk.add_constraint(DistanceConstraint(p0, p1, 10.0))
    sk.solve()
    ok("Sketch:create_and_solve")
except Exception as e:
    fail("Sketch", str(e)[:100])

# ---- 8. Export pipeline ----
section("8. Export pipeline")
try:
    from adaptivecad.gcode_generator import generate_gcode_from_shape
    ok("gcode_generator:import")
except Exception as e:
    fail("gcode_generator:import", str(e)[:100])

try:
    from adaptivecad.aacore.ama_io import write_ama, read_ama
    ok("ama_io:import")
except ImportError:
    try:
        import adaptivecad.aacore.ama_io
        ok("ama_io:import (partial)")
    except Exception as e:
        warn("ama_io:import", str(e)[:100])

# ---- 9. Analytic viewport ----
section("9. Analytic viewport widget")
try:
    from adaptivecad.gui.analytic_viewport import AnalyticViewportPanel
    panel = AnalyticViewportPanel()
    ok("AnalyticViewportPanel:init")
except Exception as e:
    fail("AnalyticViewportPanel:init", str(e)[:100])

# ---- 10. Light playground ----
section("10. Light playground (adaptivecad_playground)")
light_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "AdaptiveCAD-light")
if os.path.isdir(light_path):
    sys.path.insert(0, light_path)
    # The light playground uses bare imports for sibling modules (e.g. "from edit_tools import ...")
    pkg_dir = os.path.join(light_path, "adaptivecad_playground")
    if os.path.isdir(pkg_dir):
        sys.path.insert(0, pkg_dir)
    try:
        from adaptivecad_playground.app import Main as LightPlayground
        pg = LightPlayground()
        ok("LightPlayground:init")
    except Exception as e:
        fail("LightPlayground:init", f"{type(e).__name__}: {str(e)[:100]}")
else:
    warn("LightPlayground", f"path not found: {light_path}")

# ---- 11. Menu action wiring ----
section("11. Menu action wiring")
if mw:
    from PySide6.QtCore import SIGNAL

    _triggered_sig = SIGNAL("triggered()")
    menubar = mw.win.menuBar()
    total_actions = 0
    connected_actions = 0
    unconnected = []
    for menu_action in menubar.actions():
        menu = menu_action.menu()
        if not menu:
            continue
        menu_title = menu.title()
        for action in menu.actions():
            if action.isSeparator():
                continue
            sub = action.menu()
            if sub:
                for sub_action in sub.actions():
                    if sub_action.isSeparator():
                        continue
                    total_actions += 1
                    if sub_action.receivers(_triggered_sig) > 0:
                        connected_actions += 1
                    else:
                        unconnected.append(f"{menu_title} > {sub.title()} > {sub_action.text()}")
            else:
                total_actions += 1
                if action.receivers(_triggered_sig) > 0:
                    connected_actions += 1
                else:
                    unconnected.append(f"{menu_title} > {action.text()}")

    ok(f"MenuActions", f"{connected_actions}/{total_actions} connected")
    for u in unconnected:
        warn(f"MenuAction:unconnected", u)
else:
    warn("MenuActions", "Skipped -- MainWindow not available")


# ---- Summary ----
section("SUMMARY")
print(f"  OK:   {stats['ok']}")
print(f"  WARN: {stats['warn']}")
print(f"  FAIL: {stats['fail']}")
if failures:
    print()
    print("  FAILURES:")
    for f in failures:
        print(f"    - {f}")

app.quit()
sys.exit(1 if stats["fail"] > 0 else 0)
