#!/usr/bin/env python
"""analytic_viewport_launcher.py

Minimal launcher for the Analytic Viewport Panel (PySide6).

This script is intended to be used by the VS Code task "Launch Analytic Viewport".

Optional CLI features:
- Load an exported Analytic Scene JSON (the format produced by the panel's
    "Export Scene JSON" button)
- Load an AdaptiveCAD AMA (.ama) archive and visualize its NDField values as a
    heightmap mesh overlay (no OCC required)
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

# Ensure project root is importable
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow
except Exception as e:
    print("PySide6 is not available:", e)
    sys.exit(1)

try:
    from adaptivecad.gui.analytic_viewport import (
        AnalyticViewportDashboardWindow,
        AnalyticViewportPanel,
    )
except Exception as e:
    print("Failed to import Analytic Viewer:", e)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="AdaptiveCAD Analytic Viewport Launcher")
    parser.add_argument("--scene-json", type=str, default=None, help="Path to analytic_scene_*.json exported by the viewport")
    parser.add_argument("--ama", type=str, default=None, help="Path to .ama archive to visualize (NDField -> heightmap overlay)")
    parser.add_argument("--ama-field", type=str, default=None, help="Field .npy path inside AMA (default: first fields/*.npy)")
    parser.add_argument("--layer", type=str, default=None, help="Layer id from analytic/scene.json (or a fields/*.npy path inside AMA)")
    parser.add_argument("--scale-xy", type=float, default=None, help="Override XY scale for AMA field heightmap")
    parser.add_argument("--scale-z", type=float, default=None, help="Override Z scale for AMA field heightmap")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        win = AnalyticViewportDashboardWindow()
        panel = win.panel
    except Exception:
        win = QMainWindow()
        win.setWindowTitle("AdaptiveCAD – Analytic Viewport Panel")
        panel = AnalyticViewportPanel(win)
        win.setCentralWidget(panel)

    win.resize(1300, 850)
    win.show()

    def _notify_scene_changed() -> None:
        try:
            panel.view.scene._notify()
        except Exception:
            pass

    def _load_scene_entries(data: object) -> None:

        from adaptivecad.aacore.sdf import (
            KIND_BOX,
            KIND_CAPSULE,
            KIND_GYROID,
            KIND_HELICOID,
            KIND_HYPERBOLIC,
            KIND_KLEIN,
            KIND_MANDELBULB,
            KIND_MENGER,
            KIND_MOBIUS,
            KIND_QUASICRYSTAL,
            KIND_SPHERE,
            KIND_SUPERELLIPSOID,
            KIND_TORUS,
            KIND_TORUS4D,
            KIND_TREFOIL,
            Prim,
        )

        kind_map = {
            "sphere": KIND_SPHERE,
            "box": KIND_BOX,
            "capsule": KIND_CAPSULE,
            "torus": KIND_TORUS,
            "mobius": KIND_MOBIUS,
            "superellipsoid": KIND_SUPERELLIPSOID,
            "quasicrystal": KIND_QUASICRYSTAL,
            "4d torus": KIND_TORUS4D,
            "torus4d": KIND_TORUS4D,
            "mandelbulb": KIND_MANDELBULB,
            "klein bottle": KIND_KLEIN,
            "klein": KIND_KLEIN,
            "menger sponge": KIND_MENGER,
            "menger": KIND_MENGER,
            "hyperbolic tiling": KIND_HYPERBOLIC,
            "hyperbolic": KIND_HYPERBOLIC,
            "gyroid": KIND_GYROID,
            "trefoil knot": KIND_TREFOIL,
            "trefoil": KIND_TREFOIL,
            "helicoid": KIND_HELICOID,
        }

        if not isinstance(data, list):
            raise ValueError("Scene JSON must be a list")

        panel.view.scene.prims.clear()
        for entry in data:
            if not isinstance(entry, dict):
                continue
            kind_name = str(entry.get("kind", "")).strip().lower()
            k = kind_map.get(kind_name)
            if k is None:
                continue
            params = entry.get("params")
            if not isinstance(params, list):
                params = [0.5, 0.0, 0.0, 0.0]
            beta = float(entry.get("beta", 0.0) or 0.0)
            color = entry.get("color")
            if isinstance(color, list) and len(color) >= 3:
                col = (float(color[0]), float(color[1]), float(color[2]))
            else:
                col = (0.85, 0.75, 0.55)
            op_raw = entry.get("op", 0)
            if isinstance(op_raw, str):
                op_name = op_raw.strip().lower()
                if op_name in ("subtract", "sub"):
                    op_val = "subtract"
                elif op_name in ("intersect", "and"):
                    op_val = "intersect"
                else:
                    op_val = "solid"
            else:
                try:
                    op_i = int(op_raw or 0)
                except Exception:
                    op_i = 0
                if op_i == 1:
                    op_val = "subtract"
                elif op_i == 2:
                    op_val = "intersect"
                else:
                    op_val = "solid"

            pr = Prim(k, [float(x) for x in params], beta=beta, color=col, op=op_val)

            pos_raw = entry.get("pos")
            euler_raw = entry.get("euler")
            scale_raw = entry.get("scale")

            pos = None
            if isinstance(pos_raw, list) and len(pos_raw) >= 3:
                try:
                    pos = [float(pos_raw[0]), float(pos_raw[1]), float(pos_raw[2])]
                except Exception:
                    pos = None

            euler = None
            if isinstance(euler_raw, list) and len(euler_raw) >= 3:
                try:
                    euler = [float(euler_raw[0]), float(euler_raw[1]), float(euler_raw[2])]
                except Exception:
                    euler = None

            scale = None
            if isinstance(scale_raw, list) and len(scale_raw) >= 3:
                try:
                    scale = [float(scale_raw[0]), float(scale_raw[1]), float(scale_raw[2])]
                except Exception:
                    scale = None

            if pos is not None or euler is not None or scale is not None:
                try:
                    pr.set_transform(pos=pos, euler=euler, scale=scale)
                except Exception:
                    pass
            panel.view.scene.add(pr)

        _notify_scene_changed()

    # If we're launching to view external content (AMA/scene JSON), start from a
    # clean scene (avoid the built-in demo primitives).
    if args.ama or args.scene_json:
        try:
            panel.view.scene.prims.clear()
        except Exception:
            pass
        _notify_scene_changed()
        try:
            panel.view.update()
        except Exception:
            pass

    def _load_scene_json(path: str) -> None:
        import json

        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        _load_scene_entries(data)

    def _read_ama_analytic_scene(z: zipfile.ZipFile) -> dict | None:
        import json

        try:
            if "analytic/scene.json" not in z.namelist():
                return None
            obj = json.loads(z.read("analytic/scene.json").decode("utf-8"))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _extract_ama_field(ama_path: str, field_path: str | None) -> tuple["object", float | None, float | None, dict | None]:
        import json

        import numpy as np

        ama_p = Path(ama_path)
        if not ama_p.exists():
            raise FileNotFoundError(str(ama_p))

        with zipfile.ZipFile(ama_p, "r") as z:
            scene_obj = _read_ama_analytic_scene(z)
            scene_scale_xy = None
            scene_scale_z = None
            if isinstance(scene_obj, dict):
                # legacy + v0.1 support
                try:
                    scales = scene_obj.get("scales")
                    if isinstance(scales, dict):
                        scene_scale_xy = scales.get("xy")
                        scene_scale_z = scales.get("z")
                except Exception:
                    pass
                try:
                    if scene_scale_xy is None and scene_obj.get("scale_xy") is not None:
                        scene_scale_xy = scene_obj.get("scale_xy")
                    if scene_scale_z is None and scene_obj.get("scale_z") is not None:
                        scene_scale_z = scene_obj.get("scale_z")
                except Exception:
                    pass

            graph = None
            if "model/graph.json" in z.namelist():
                graph = json.loads(z.read("model/graph.json").decode("utf-8"))

            selected_npy = None
            scale_xy = None
            scale_z = None

            if isinstance(graph, list):
                for node in graph:
                    if not isinstance(node, dict):
                        continue
                    if str(node.get("type", "")) != "NDField":
                        continue
                    fields = node.get("fields")
                    if isinstance(fields, dict):
                        selected_npy = fields.get("values")
                    params = node.get("params") if isinstance(node.get("params"), dict) else {}
                    try:
                        if params is not None:
                            scale_xy = params.get("scale_xy")
                            scale_z = params.get("scale_z")
                            if scale_xy is None:
                                spacing = params.get("spacing")
                                if isinstance(spacing, list) and spacing:
                                    scale_xy = float(spacing[0])
                    except Exception:
                        pass
                    break

            if field_path:
                selected_npy = field_path

            if not selected_npy:
                npy_candidates = [n for n in z.namelist() if n.lower().startswith("fields/") and n.lower().endswith(".npy")]
                if not npy_candidates:
                    raise FileNotFoundError("No fields/*.npy found inside AMA")
                selected_npy = npy_candidates[0]

            arr = np.load(BytesIO(z.read(str(selected_npy))))
            out_xy = float(scale_xy) if scale_xy is not None else scene_scale_xy
            out_z = float(scale_z) if scale_z is not None else scene_scale_z
            return arr, out_xy, out_z, scene_obj

    def _apply_vertex_colormap(mesh, cmap: str | None) -> None:
        """Bake a simple vertex colormap based on vertex Z (normalized 0..1)."""
        if mesh is None:
            return
        try:
            import numpy as np
        except Exception:
            return

        cmap = (cmap or "plasma").strip().lower()
        try:
            z = np.asarray(mesh.vertices, dtype=np.float32)[:, 2]
            zmin = float(np.nanmin(z))
            zmax = float(np.nanmax(z))
            if not np.isfinite(zmin) or not np.isfinite(zmax) or abs(zmax - zmin) < 1e-9:
                return
            t = (z - zmin) / (zmax - zmin)
            t = np.clip(t, 0.0, 1.0)
        except Exception:
            return

        def lerp(a, b, x):
            return a + (b - a) * x

        if cmap in ("gray", "greyscale", "grayscale"):
            rgb = np.stack([t, t, t], axis=1)
        elif cmap in ("hsv", "phase"):
            h = t
            i = np.floor(h * 6.0).astype(np.int32)
            f = (h * 6.0) - i
            q = 1.0 - f
            r = np.zeros_like(f)
            g = np.zeros_like(f)
            b = np.zeros_like(f)
            m = (i % 6)
            r[m == 0] = 1.0; g[m == 0] = f[m == 0]
            r[m == 1] = q[m == 1]; g[m == 1] = 1.0
            g[m == 2] = 1.0; b[m == 2] = f[m == 2]
            g[m == 3] = q[m == 3]; b[m == 3] = 1.0
            r[m == 4] = f[m == 4]; b[m == 4] = 1.0
            r[m == 5] = 1.0; b[m == 5] = q[m == 5]
            rgb = np.stack([r, g, b], axis=1)
        elif cmap == "viridis":
            c0 = np.array([0.267, 0.005, 0.329], np.float32)
            c1 = np.array([0.283, 0.141, 0.458], np.float32)
            c2 = np.array([0.254, 0.265, 0.530], np.float32)
            c3 = np.array([0.993, 0.906, 0.144], np.float32)
            rgb = np.zeros((t.shape[0], 3), np.float32)
            m1 = t < 0.33
            m2 = (t >= 0.33) & (t < 0.66)
            m3 = t >= 0.66
            rgb[m1] = lerp(c0, c1, (t[m1] / 0.33)[:, None])
            rgb[m2] = lerp(c1, c2, ((t[m2] - 0.33) / 0.33)[:, None])
            rgb[m3] = lerp(c2, c3, ((t[m3] - 0.66) / 0.34)[:, None])
        else:
            # plasma-ish
            c0 = np.array([0.050, 0.030, 0.528], np.float32)
            c1 = np.array([0.465, 0.004, 0.659], np.float32)
            c2 = np.array([0.796, 0.277, 0.473], np.float32)
            c3 = np.array([0.940, 0.975, 0.131], np.float32)
            rgb = np.zeros((t.shape[0], 3), np.float32)
            m1 = t < 0.33
            m2 = (t >= 0.33) & (t < 0.66)
            m3 = t >= 0.66
            rgb[m1] = lerp(c0, c1, (t[m1] / 0.33)[:, None])
            rgb[m2] = lerp(c1, c2, ((t[m2] - 0.33) / 0.33)[:, None])
            rgb[m3] = lerp(c2, c3, ((t[m3] - 0.66) / 0.34)[:, None])

        rgba = (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
        alpha = np.full((rgba.shape[0], 1), 255, dtype=np.uint8)
        try:
            mesh.visual.vertex_colors = np.concatenate([rgba, alpha], axis=1)
        except Exception:
            pass

    def _frame_camera_to_mesh(mesh) -> None:
        import numpy as np

        try:
            bounds = mesh.bounds
            center = bounds.mean(axis=0)
            extents = bounds[1] - bounds[0]
            radius = float(np.linalg.norm(extents) * 0.6) if np.isfinite(extents).all() else 3.0
        except Exception:
            center = [0.0, 0.0, 0.0]
            radius = 3.0

        try:
            panel.view.cam_target = np.array(center, dtype=np.float32)
            panel.view.distance = max(1.0, radius * 2.0)
            panel.view._update_camera()
        except Exception:
            pass

    def _add_ama_overlay_when_ready() -> None:
        if not args.ama:
            return

        # --- Prefer true analytic SDF scene if present in AMA ---
        try:
            import json
            with zipfile.ZipFile(args.ama, "r") as z:
                if "analytic/scene.json" in z.namelist():
                    scene_raw = json.loads(z.read("analytic/scene.json").decode("utf-8"))
                    if isinstance(scene_raw, list):
                        # Load SDF prim list and skip mesh/field overlay.
                        _load_scene_entries(scene_raw)
                        try:
                            panel.view.update()
                        except Exception:
                            pass
                        return
        except Exception:
            pass

        try:
            import numpy as np
            import trimesh  # type: ignore
        except Exception as exc:
            print(f"Missing dependency for mesh overlay (numpy/trimesh): {exc}")
            return

        # If scene.json defines layers/render, use them unless overridden.
        layer_cmap = None
        render_mode = None
        render_iso = None
        ama_field = args.ama_field
        ui_selected_layer = None

        # Allow --layer to be either a layer id or an explicit fields/*.npy path.
        if args.layer and isinstance(args.layer, str) and args.layer.lower().startswith("fields/") and args.layer.lower().endswith(".npy"):
            ama_field = args.layer
            ui_selected_layer = args.layer

        try:
            phi, detected_xy, detected_z, scene_obj = _extract_ama_field(args.ama, ama_field)
        except Exception as exc:
            print(f"Failed to read AMA field: {exc}")
            return

        # If a layer id was provided, map it to a field_ref via scene.json.
        if args.layer and scene_obj and isinstance(scene_obj, dict):
            layers = scene_obj.get("layers")
            if isinstance(layers, list):
                for layer in layers:
                    if not isinstance(layer, dict):
                        continue
                    if str(layer.get("id", "")) == str(args.layer):
                        ui_selected_layer = str(args.layer)
                        fr = layer.get("field_ref")
                        if isinstance(fr, str) and fr.lower().endswith(".npy"):
                            try:
                                phi, detected_xy, detected_z, _ = _extract_ama_field(args.ama, fr)
                            except Exception:
                                pass
                        if isinstance(layer.get("colormap"), str):
                            layer_cmap = layer.get("colormap")
                        break

        # Pull defaults from scene.render if present
        if scene_obj and isinstance(scene_obj, dict):
            try:
                render = scene_obj.get("render") if isinstance(scene_obj.get("render"), dict) else None
                if render:
                    render_mode = render.get("mode")
                    render_iso = render.get("iso")
                    if not args.layer and isinstance(render.get("source_layer"), str):
                        # If no --layer, follow source_layer
                        src = render.get("source_layer")
                        ui_selected_layer = str(src)
                        layers = scene_obj.get("layers")
                        if isinstance(layers, list):
                            for layer in layers:
                                if not isinstance(layer, dict):
                                    continue
                                if str(layer.get("id", "")) == str(src):
                                    fr = layer.get("field_ref")
                                    if isinstance(fr, str) and fr.lower().endswith(".npy"):
                                        try:
                                            phi, detected_xy, detected_z, _ = _extract_ama_field(args.ama, fr)
                                        except Exception:
                                            pass
                                    if isinstance(layer.get("colormap"), str):
                                        layer_cmap = layer.get("colormap")
                                    break
            except Exception:
                pass

        if ui_selected_layer is None and isinstance(ama_field, str) and ama_field:
            ui_selected_layer = ama_field

        # --- Check for pre-built mesh in the AMA (e.g. ribbons, sweeps) ---
        mesh = None
        tmp_path = None
        try:
            import trimesh
            with zipfile.ZipFile(args.ama, "r") as z:
                mesh_candidates = []
                if isinstance(scene_obj, dict) and isinstance(scene_obj.get("mesh"), str):
                    mesh_candidates.append(scene_obj["mesh"])
                mesh_candidates.extend(["mesh/ribbon.stl", "mesh/surface.stl", "mesh/model.stl"])
                
                for mc in mesh_candidates:
                    if mc in z.namelist():
                        stl_bytes = z.read(mc)
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
                        tmp.write(stl_bytes)
                        tmp.flush()
                        tmp_path = tmp.name
                        tmp.close()
                        mesh = trimesh.load_mesh(tmp_path)
                        if isinstance(mesh, trimesh.Scene):
                            mesh = trimesh.util.concatenate(tuple(mesh.dump()))
                        print(f"Loaded pre-built mesh from AMA: {mc}")
                        break
        except Exception:
            mesh = None

        # --- Fallback: generate heightmap from field (only for square NxN fields) ---
        if mesh is None:
            try:
                from adaptivecad.pr.export import export_phase_field_as_heightmap_stl
            except Exception as exc:
                print(f"Failed to import PR STL exporter: {exc}")
                return

            # Only attempt heightmap conversion for square fields
            if phi.ndim != 2 or phi.shape[0] != phi.shape[1]:
                print(f"Field shape {phi.shape} is not square; cannot generate heightmap. Looking for pre-built mesh...")
                return

            scale_xy = args.scale_xy if args.scale_xy is not None else (detected_xy if detected_xy is not None else 1.0)
            scale_z = args.scale_z if args.scale_z is not None else (detected_z if detected_z is not None else 1.0)

            try:
                stl_bytes = export_phase_field_as_heightmap_stl(np.asarray(phi), scale_xy=float(scale_xy), scale_z=float(scale_z))
            except Exception as exc:
                print(f"Failed to convert field to STL: {exc}")
                return

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
            tmp.write(stl_bytes)
            tmp.flush()
            tmp_path = tmp.name
            tmp.close()

            try:
                mesh = trimesh.load_mesh(tmp_path)
            except Exception as exc:
                print(f"Failed to load STL with trimesh: {exc}")
                return

            # Normalize to a single Trimesh (load_mesh can return a Scene)
            try:
                if isinstance(mesh, trimesh.Scene):
                    mesh = trimesh.util.concatenate(tuple(mesh.dump()))
            except Exception:
                pass
        else:
            # For pre-built meshes, use scene scales if provided
            scale_xy = args.scale_xy if args.scale_xy is not None else (detected_xy if detected_xy is not None else 1.0)
            scale_z = args.scale_z if args.scale_z is not None else (detected_z if detected_z is not None else 1.0)

        # Bake vertex colors from colormap (if any)
        try:
            _apply_vertex_colormap(mesh, layer_cmap)
        except Exception:
            pass

        # Retry until OpenGL context exists
        attempts = {"n": 0}

        def _try_add() -> None:
            attempts["n"] += 1
            ok, err = panel.view.add_mesh_overlay(mesh, source_path=tmp_path)
            if ok:
                # Stash source mesh on the panel so the viewer-side threshold
                # controls can rebuild the overlay without relaunch.
                try:
                    panel._field_overlay_source_mesh = mesh
                    panel._field_overlay_source_path = tmp_path
                    if hasattr(panel, "_apply_field_overlay_clip"):
                        panel._apply_field_overlay_clip()
                except Exception:
                    pass

                # Populate Field Layer dropdown for in-viewer switching.
                try:
                    if hasattr(panel, "set_field_layers_from_ama"):
                        panel.set_field_layers_from_ama(
                            args.ama,
                            scene_obj if isinstance(scene_obj, dict) else None,
                            float(scale_xy) if scale_xy is not None else None,
                            float(scale_z) if scale_z is not None else None,
                            selected=str(ui_selected_layer) if ui_selected_layer is not None else None,
                        )
                except Exception:
                    pass

                # Seed the current layer colormap for viewer-side recoloring.
                try:
                    if layer_cmap is not None:
                        panel._field_current_colormap = str(layer_cmap)
                except Exception:
                    pass

                # If the analytic scene requests iso mode, enable clip UI.
                try:
                    if isinstance(render_mode, str) and render_mode.strip().lower() in ("iso", "isosurface"):
                        if getattr(panel, "_field_clip_chk", None) is not None:
                            panel._field_clip_chk.setChecked(True)
                        if getattr(panel, "_field_clip_spin", None) is not None and render_iso is not None:
                            panel._field_clip_spin.setValue(float(render_iso))
                        if hasattr(panel, "_apply_field_overlay_clip"):
                            panel._apply_field_overlay_clip()
                except Exception:
                    pass
                _frame_camera_to_mesh(mesh)
                return
            if attempts["n"] < 25 and err and "context" in err.lower():
                QTimer.singleShot(100, _try_add)
                return
            if not ok:
                print(f"Failed to add mesh overlay: {err}")

        QTimer.singleShot(150, _try_add)

    def _load_scene_when_ready() -> None:
        if not args.scene_json:
            return

        def _do() -> None:
            try:
                _load_scene_json(args.scene_json)
            except Exception as exc:
                print(f"Failed to load scene JSON: {exc}")

        QTimer.singleShot(0, _do)

    _load_scene_when_ready()
    _add_ama_overlay_when_ready()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
