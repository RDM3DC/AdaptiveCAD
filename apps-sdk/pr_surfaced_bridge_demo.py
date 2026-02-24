"""PR Surfaced Bridge Demo

Generates a helicoid "surfaced branch cut" mesh and writes it into an .ama so the
Analytic Viewport can render it as a pre-built mesh overlay.

Examples:
  python apps-sdk/pr_surfaced_bridge_demo.py --out surfaced_bridge.ama
  python apps-sdk/pr_surfaced_bridge_demo.py --turns 2 --pitch 0.35 --out sqrt_bridge.ama
  python apps-sdk/pr_surfaced_bridge_demo.py --turns 3 --pitch 0.25 --out triple_sheet.ama

True-analytic (no triangle mesh):
    python apps-sdk/pr_surfaced_bridge_demo.py --surface mobius --analytic --out mobius_analytic.ama
    python apps-sdk/pr_surfaced_bridge_demo.py --surface klein --analytic --out klein_analytic.ama
    python apps-sdk/pr_surfaced_bridge_demo.py --surface knot_ribbon --analytic --out trefoil_analytic.ama
    python apps-sdk/pr_surfaced_bridge_demo.py --surface square_frame --analytic --out square_frame.ama
    python apps-sdk/pr_surfaced_bridge_demo.py --surface square_tube_gyroid --analytic --out square_tube_gyroid.ama
    python apps-sdk/pr_surfaced_bridge_demo.py --surface square_tube --analytic --out square_tube.ama
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running from a fresh environment without installing the package.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output .ama path")
    ap.add_argument(
        "--analytic",
        action="store_true",
        help="Export a true-analytic SDF scene (no triangles). Supported for mobius/klein/knot_ribbon (mapped to trefoil), helicoid/branch (helicoid ribbon), and square_frame (hollow box frame).",
    )

    ap.add_argument(
        "--surface",
        choices=[
            "helicoid",
            "handle",
            "mobius",
            "klein",
            "branch",
            "knot_ribbon",
            "enneper",
            "square_frame",
            "square_tube_gyroid",
            "square_tube",
            "gyroid_contained",
            "gyroid_field",
            "torus4d_contained",
            "mandelbulb_contained",
            "menger_contained",
            "hyperbolic_contained",
            "hyperbolic_field",
            "quasicrystal_field",
            "holonomy_combo",
        ],
        default="helicoid",
    )

    # analytic square frame (outer box minus inner box)
    ap.add_argument(
        "--frame-outer",
        type=float,
        default=1.2,
        help="Outer half-size in X/Y for square_frame",
    )
    ap.add_argument(
        "--frame-depth",
        type=float,
        default=0.25,
        help="Half-size in Z for square_frame",
    )
    ap.add_argument(
        "--frame-wall",
        type=float,
        default=0.18,
        help="Wall thickness for square_frame (outer-inner in XY)",
    )

    ap.add_argument(
        "--tube-outer",
        type=float,
        default=1.0,
        help="Outer half-size in X/Y for square_tube_gyroid",
    )
    ap.add_argument(
        "--tube-depth",
        type=float,
        default=2.0,
        help="Half-size in Z for square_tube_gyroid (deep tube)",
    )
    ap.add_argument(
        "--tube-wall",
        type=float,
        default=0.22,
        help="Wall thickness for square_tube_gyroid",
    )

    # helicoid
    ap.add_argument("--r-inner", type=float, default=0.15)
    ap.add_argument("--r-outer", type=float, default=0.55)
    ap.add_argument("--turns", type=float, default=2.0, help="Full turns around branch point (2 => 0..4π)")
    ap.add_argument("--pitch", type=float, default=0.35, help="Height per turn (2π)")
    ap.add_argument("--helicoid-thickness", type=float, default=0.035, help="Analytic helicoid ribbon thickness")
    ap.add_argument("--n-theta", type=int, default=480)
    ap.add_argument("--n-r", type=int, default=64)

    # handle (two sheets + tube)
    ap.add_argument("--sheet-R", type=float, default=0.70, help="Outer radius of the sheets")
    ap.add_argument("--hole-r", type=float, default=0.20, help="Hole radius and tube radius")
    ap.add_argument("--sheet-z", type=float, default=0.25, help="Half-separation between the two sheets")
    ap.add_argument("--n-z", type=int, default=96, help="Tube subdivisions along Z")

    # mobius
    ap.add_argument("--mobius-R", type=float, default=0.55)
    ap.add_argument("--mobius-width", type=float, default=0.18)
    ap.add_argument("--mobius-twists", type=int, default=1, help="Half-twists (1 = Möbius)")

    # klein
    ap.add_argument("--klein-a", type=float, default=0.35)
    ap.add_argument("--klein-scale", type=float, default=0.95)
    ap.add_argument("--klein-n", type=float, default=2.0, help="Analytic klein: n parameter")
    ap.add_argument("--klein-t-offset", type=float, default=0.0, help="Analytic klein: t_offset parameter")
    ap.add_argument("--klein-thickness", type=float, default=0.10, help="Analytic klein: thickness (GPU only)")

    # branch-cut surfaced sheets + ramps
    ap.add_argument("--branch-r-inner", type=float, default=0.10)
    ap.add_argument("--branch-r-outer", type=float, default=0.80)
    ap.add_argument("--branch-cut-angle", type=float, default=0.20)
    ap.add_argument("--branch-sheet-z", type=float, default=0.20)
    ap.add_argument("--branch-ramp-turns", type=float, default=1.0)
    ap.add_argument("--branch-n-s", type=int, default=220)

    # torus knot ribbon
    ap.add_argument("--knot-R", type=float, default=0.55)
    ap.add_argument("--knot-r", type=float, default=0.22)
    ap.add_argument("--knot-p", type=int, default=2)
    ap.add_argument("--knot-q", type=int, default=3)
    ap.add_argument("--knot-width", type=float, default=0.14)
    ap.add_argument("--knot-twist", type=float, default=1.0, help="Extra twist turns around tangent")

    # analytic trefoil (used when --surface knot_ribbon --analytic)
    ap.add_argument("--trefoil-scale", type=float, default=0.95)
    ap.add_argument("--trefoil-tube", type=float, default=0.11)
    ap.add_argument("--trefoil-samples", type=int, default=128)

    # analytic gyroid-contained
    ap.add_argument("--contain-radius", type=float, default=1.05, help="Containing sphere radius")
    ap.add_argument("--gyroid-scale", type=float, default=1.35)
    ap.add_argument("--gyroid-tau", type=float, default=0.0)
    ap.add_argument("--gyroid-thickness", type=float, default=0.085)

    # analytic quasicrystal field
    ap.add_argument("--qc-scale", type=float, default=1.20)
    ap.add_argument("--qc-iso", type=float, default=0.0)
    ap.add_argument("--qc-thickness", type=float, default=0.055)

    # analytic torus4d-contained
    ap.add_argument("--torus4d-R1", type=float, default=0.85)
    ap.add_argument("--torus4d-R2", type=float, default=0.55)
    ap.add_argument("--torus4d-r", type=float, default=0.28)
    ap.add_argument("--torus4d-w", type=float, default=0.45, help="4D slice position (w_slice)")

    # analytic mandelbulb-contained
    ap.add_argument("--bulb-power", type=float, default=8.0)
    ap.add_argument("--bulb-bailout", type=float, default=2.0)
    ap.add_argument("--bulb-max-iter", type=int, default=16)
    ap.add_argument("--bulb-scale", type=float, default=1.0)

    # analytic menger-contained
    ap.add_argument("--menger-iter", type=int, default=3)
    ap.add_argument("--menger-size", type=float, default=1.0)

    # analytic hyperbolic-contained
    ap.add_argument("--hyp-scale", type=float, default=1.25)
    ap.add_argument("--hyp-order", type=int, default=7)
    ap.add_argument("--hyp-sym", type=int, default=3)

    # analytic holonomy combo
    ap.add_argument("--combo-radius", type=float, default=0.80, help="Core size")
    ap.add_argument("--combo-power", type=float, default=2.6, help="Superellipsoid power")
    ap.add_argument("--combo-trefoil-scale", type=float, default=0.95)
    ap.add_argument("--combo-trefoil-tube", type=float, default=0.09)
    ap.add_argument("--combo-trefoil-samples", type=int, default=160)
    ap.add_argument("--combo-helicoid-r-in", type=float, default=0.22)
    ap.add_argument("--combo-helicoid-r-out", type=float, default=1.05)
    ap.add_argument("--combo-helicoid-pitch", type=float, default=0.55)
    ap.add_argument("--combo-helicoid-turns", type=float, default=2.5)
    ap.add_argument("--combo-helicoid-thickness", type=float, default=0.040)

    # enneper
    ap.add_argument("--enneper-extent", type=float, default=1.65)
    ap.add_argument("--enneper-scale", type=float, default=0.35)
    ap.add_argument("--one-sided", action="store_true", help="Do not duplicate faces for two-sided render")

    args = ap.parse_args()

    from adaptivecad.pr.surfaced_bridge import (
        export_analytic_scene_as_ama,
        export_surfaced_bridge_as_ama,
    )

    if args.analytic:
        # True analytic scenes: store a JSON list of SDF prims into the AMA.
        if args.surface == "mobius":
            scene_list = [
                {
                    "kind": "mobius",
                    "params": [float(args.mobius_R), float(args.mobius_width), 0.0, 0.0],
                }
            ]
        elif args.surface in ("helicoid", "branch"):
            scene_list = [
                {
                    "kind": "helicoid",
                    # params: r_inner, r_outer, pitch, turns; thickness via beta
                    "params": [float(args.r_inner), float(args.r_outer), float(args.pitch), float(args.turns)],
                    "beta": float(args.helicoid_thickness),
                }
            ]
        elif args.surface == "klein":
            scene_list = [
                {
                    "kind": "klein",
                    "params": [
                        float(args.klein_scale),
                        float(args.klein_n),
                        float(args.klein_t_offset),
                        float(args.klein_thickness),
                    ],
                }
            ]
        elif args.surface == "knot_ribbon":
            # Analytic viewport supports a trefoil knot SDF; we map the "knot_ribbon" choice
            # to a trefoil tube in analytic mode.
            scene_list = [
                {
                    "kind": "trefoil",
                    "params": [float(args.trefoil_scale), float(args.trefoil_tube), float(args.trefoil_samples), 0.0],
                }
            ]
        elif args.surface == "square_frame":
            outer = float(args.frame_outer)
            depth = float(args.frame_depth)
            wall = float(args.frame_wall)
            inner = max(0.01, outer - wall)
            # Model: outer box minus slightly deeper inner box -> through-hole frame.
            scene_list = [
                {
                    "kind": "box",
                    "params": [outer, outer, depth, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "box",
                    "params": [inner, inner, depth + 0.05, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "subtract",
                },
            ]
        elif args.surface == "square_tube_gyroid":
            # A deep square tube whose walls are patterned by subtracting a gyroid volume.
            # Tuning knobs for "vibration frequency stuff":
            #   - gyroid_scale: sets unit-cell size (smaller cells -> higher-frequency features)
            #   - gyroid_thickness: controls strut/surface thickness
            outer = float(args.tube_outer)
            depth = float(args.tube_depth)
            wall = float(args.tube_wall)
            inner = max(0.01, outer - wall)
            scene_list = [
                {
                    "kind": "box",
                    "params": [outer, outer, depth, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "box",
                    "params": [inner, inner, depth + 0.10, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "subtract",
                },
                {
                    "kind": "gyroid",
                    "params": [float(args.gyroid_scale), float(args.gyroid_tau), float(args.gyroid_thickness), 0.0],
                    "color": [0.45, 0.80, 0.70],
                    "op": "subtract",
                },
            ]
        elif args.surface == "square_tube":
            # Baseline: deep square tube with no internal lattice.
            outer = float(args.tube_outer)
            depth = float(args.tube_depth)
            wall = float(args.tube_wall)
            inner = max(0.01, outer - wall)
            scene_list = [
                {
                    "kind": "box",
                    "params": [outer, outer, depth, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "box",
                    "params": [inner, inner, depth + 0.10, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "subtract",
                },
            ]
        elif args.surface == "gyroid_contained":
            # Intersect an infinite gyroid shell with a containing sphere.
            scene_list = [
                {
                    "kind": "sphere",
                    "params": [float(args.contain_radius), 0.0, 0.0, 0.0],
                    "color": [0.85, 0.80, 0.72],
                    "op": "solid",
                },
                {
                    "kind": "gyroid",
                    "params": [float(args.gyroid_scale), float(args.gyroid_tau), float(args.gyroid_thickness), 0.0],
                    "color": [0.45, 0.80, 0.70],
                    "op": "intersect",
                },
            ]
        elif args.surface == "gyroid_field":
            scene_list = [
                {
                    "kind": "gyroid",
                    "params": [float(args.gyroid_scale), float(args.gyroid_tau), float(args.gyroid_thickness), 0.0],
                    "color": [0.55, 0.90, 0.80],
                    "op": "solid",
                }
            ]
        elif args.surface == "torus4d_contained":
            # Intersect a 4D torus slice with a containing sphere.
            scene_list = [
                {
                    "kind": "sphere",
                    "params": [float(args.contain_radius), 0.0, 0.0, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "torus4d",
                    "params": [float(args.torus4d_R1), float(args.torus4d_R2), float(args.torus4d_r), float(args.torus4d_w)],
                    "color": [0.75, 0.55, 0.95],
                    "op": "intersect",
                },
            ]
        elif args.surface == "mandelbulb_contained":
            # Intersect a mandelbulb with a containing sphere.
            scene_list = [
                {
                    "kind": "sphere",
                    "params": [float(args.contain_radius), 0.0, 0.0, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "mandelbulb",
                    "params": [float(args.bulb_power), float(args.bulb_bailout), float(args.bulb_max_iter), float(args.bulb_scale)],
                    "color": [0.95, 0.65, 0.35],
                    "op": "intersect",
                },
            ]
        elif args.surface == "menger_contained":
            # Intersect a Menger sponge with a containing sphere.
            scene_list = [
                {
                    "kind": "sphere",
                    "params": [float(args.contain_radius), 0.0, 0.0, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "menger",
                    "params": [float(args.menger_iter), float(args.menger_size), 0.0, 0.0],
                    "color": [0.75, 0.85, 0.55],
                    "op": "intersect",
                },
            ]
        elif args.surface == "hyperbolic_contained":
            # Intersect a hyperbolic tiling SDF with a containing sphere.
            scene_list = [
                {
                    "kind": "sphere",
                    "params": [float(args.contain_radius), 0.0, 0.0, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "hyperbolic",
                    "params": [float(args.hyp_scale), float(args.hyp_order), float(args.hyp_sym), 0.0],
                    "color": [0.55, 0.70, 0.95],
                    "op": "intersect",
                },
            ]
        elif args.surface == "hyperbolic_field":
            scene_list = [
                {
                    "kind": "hyperbolic",
                    "params": [float(args.hyp_scale), float(args.hyp_order), float(args.hyp_sym), 0.0],
                    "color": [0.65, 0.78, 0.98],
                    "op": "solid",
                }
            ]
        elif args.surface == "quasicrystal_field":
            scene_list = [
                {
                    "kind": "quasicrystal",
                    "params": [float(args.qc_scale), float(args.qc_iso), float(args.qc_thickness), 0.0],
                    "color": [0.95, 0.80, 0.45],
                    "op": "solid",
                }
            ]
        elif args.surface == "holonomy_combo":
            # A multi-primitive scene (no containment):
            # - superellipsoid core
            # - trefoil drilled through (subtract)
            # - three rotated helicoid ribbons around it
            scene_list = [
                {
                    "kind": "superellipsoid",
                    "params": [float(args.combo_radius), float(args.combo_power), 0.0, 0.0],
                    "color": [0.86, 0.82, 0.74],
                    "op": "solid",
                },
                {
                    "kind": "trefoil",
                    "params": [
                        float(args.combo_trefoil_scale),
                        float(args.combo_trefoil_tube),
                        float(args.combo_trefoil_samples),
                        0.0,
                    ],
                    "color": [0.95, 0.75, 0.35],
                    "op": "subtract",
                    "euler": [90.0, 0.0, 0.0],
                },
                {
                    "kind": "helicoid",
                    "params": [
                        float(args.combo_helicoid_r_in),
                        float(args.combo_helicoid_r_out),
                        float(args.combo_helicoid_pitch),
                        float(args.combo_helicoid_turns),
                    ],
                    "beta": float(args.combo_helicoid_thickness),
                    "color": [0.55, 0.80, 0.90],
                    "op": "solid",
                    "euler": [0.0, 0.0, 0.0],
                },
                {
                    "kind": "helicoid",
                    "params": [
                        float(args.combo_helicoid_r_in),
                        float(args.combo_helicoid_r_out),
                        float(args.combo_helicoid_pitch),
                        float(args.combo_helicoid_turns),
                    ],
                    "beta": float(args.combo_helicoid_thickness),
                    "color": [0.80, 0.55, 0.95],
                    "op": "solid",
                    "euler": [0.0, 0.0, 120.0],
                },
                {
                    "kind": "helicoid",
                    "params": [
                        float(args.combo_helicoid_r_in),
                        float(args.combo_helicoid_r_out),
                        float(args.combo_helicoid_pitch),
                        float(args.combo_helicoid_turns),
                    ],
                    "beta": float(args.combo_helicoid_thickness),
                    "color": [0.65, 0.90, 0.60],
                    "op": "solid",
                    "euler": [0.0, 0.0, 240.0],
                },
            ]
        else:
            ap.error(
                "--analytic is only supported for --surface mobius|klein|knot_ribbon|helicoid|branch|square_frame|square_tube|square_tube_gyroid|gyroid_contained|gyroid_field|torus4d_contained|mandelbulb_contained|menger_contained|hyperbolic_contained|hyperbolic_field|quasicrystal_field|holonomy_combo"
            )

        data = export_analytic_scene_as_ama(scene_list)
        with open(args.out, "wb") as fp:
            fp.write(data)
        print(f"Wrote: {args.out}")
        print("Tip: launch viewer with:")
        print(f"  python analytic_viewport_launcher.py --ama {args.out}")
        return 0

    from adaptivecad.pr.surfaced_bridge import (
        SurfacedBranchCutConfig,
        SurfacedBridgeConfig,
        SurfacedEnneperConfig,
        SurfacedHandleConfig,
        SurfacedKleinConfig,
        SurfacedMobiusConfig,
        SurfacedTorusKnotRibbonConfig,
        build_branch_cut_ramp_mesh,
        build_enneper_mesh,
        build_handle_bridge_mesh,
        build_helicoid_bridge_mesh,
        build_klein_bottle_mesh,
        build_mobius_mesh,
        build_torus_knot_ribbon_mesh,
    )

    if args.surface in (
        "gyroid_field",
        "hyperbolic_field",
        "quasicrystal_field",
        "square_frame",
        "square_tube_gyroid",
        "square_tube",
    ):
        ap.error("This surface is analytic-only; re-run with --analytic")

    if args.surface == "handle":
        cfg = SurfacedHandleConfig(
            sheet_r_outer=float(args.sheet_R),
            hole_r=float(args.hole_r),
            sheet_z=float(args.sheet_z),
            n_theta=int(args.n_theta),
            n_r=int(args.n_r),
            n_z=int(args.n_z),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_handle_bridge_mesh(cfg)
    elif args.surface == "mobius":
        cfg = SurfacedMobiusConfig(
            R=float(args.mobius_R),
            width=float(args.mobius_width),
            twists=int(args.mobius_twists),
            n_u=int(args.n_theta),
            n_v=int(args.n_r),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_mobius_mesh(cfg)
    elif args.surface == "klein":
        cfg = SurfacedKleinConfig(
            a=float(args.klein_a),
            scale=float(args.klein_scale),
            n_u=int(args.n_theta),
            n_v=int(args.n_r),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_klein_bottle_mesh(cfg)
    elif args.surface == "branch":
        cfg = SurfacedBranchCutConfig(
            r_inner=float(args.branch_r_inner),
            r_outer=float(args.branch_r_outer),
            cut_angle=float(args.branch_cut_angle),
            sheet_z=float(args.branch_sheet_z),
            ramp_turns=float(args.branch_ramp_turns),
            n_theta=int(args.n_theta),
            n_r=int(args.n_r),
            n_s=int(args.branch_n_s),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_branch_cut_ramp_mesh(cfg)
    elif args.surface == "knot_ribbon":
        cfg = SurfacedTorusKnotRibbonConfig(
            R=float(args.knot_R),
            r=float(args.knot_r),
            p=int(args.knot_p),
            q=int(args.knot_q),
            width=float(args.knot_width),
            twist_turns=float(args.knot_twist),
            n_u=int(args.n_theta),
            n_v=int(args.n_r),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_torus_knot_ribbon_mesh(cfg)
    elif args.surface == "enneper":
        cfg = SurfacedEnneperConfig(
            extent=float(args.enneper_extent),
            scale=float(args.enneper_scale),
            n_u=int(args.n_theta),
            n_v=int(args.n_r),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_enneper_mesh(cfg)
    else:
        cfg = SurfacedBridgeConfig(
            r_inner=float(args.r_inner),
            r_outer=float(args.r_outer),
            turns=float(args.turns),
            pitch=float(args.pitch),
            n_theta=int(args.n_theta),
            n_r=int(args.n_r),
            two_sided=not bool(args.one_sided),
        )
        v, f = build_helicoid_bridge_mesh(cfg)

    data = export_surfaced_bridge_as_ama(v, f)
    with open(args.out, "wb") as fp:
        fp.write(data)
    print(f"Wrote: {args.out}")
    print("Tip: launch viewer with:")
    print(f"  python analytic_viewport_launcher.py --ama {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
