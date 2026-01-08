#!/usr/bin/env python3
"""
Generate a twisted PR ribbon .ama and optionally visualize it.

Examples:
    # Basic Möbius-like ribbon (1 half-twist)
    python pr_ribbon_demo.py --twist 0.5 --out mobius.ama

    # Full twist (blade-like crossing as in the reference image)
    python pr_ribbon_demo.py --twist 1.0 --tilt 0.3 --out ribbon.ama --plot

    # Figure-8 base curve with twist
    python pr_ribbon_demo.py --centerline lemniscate --twist 1.5 --out fig8.ama
"""
from __future__ import annotations

import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser(description="PR Ribbon generator")
    ap.add_argument("--centerline", choices=["circle", "tilted_circle", "lemniscate"], default="tilted_circle")
    ap.add_argument("--radius", type=float, default=1.0, help="centerline radius")
    ap.add_argument("--tilt", type=float, default=0.3, help="z-axis tilt amplitude")
    ap.add_argument("--tilt-freq", type=float, default=1.0, help="tilt frequency")
    ap.add_argument("--width", type=float, default=0.35, help="ribbon half-width")
    ap.add_argument("--twist", type=float, default=1.0, help="number of full twists (m)")
    ap.add_argument("--twist-offset", type=float, default=0.0, help="initial twist angle φ₀")
    ap.add_argument("--n-s", type=int, default=128, help="samples along curve")
    ap.add_argument("--n-u", type=int, default=24, help="samples across ribbon")
    ap.add_argument("--scale", type=float, default=10.0, help="output scale (mm)")
    ap.add_argument("--out", type=str, default="pr_ribbon.ama", help="output .ama path")
    ap.add_argument("--plot", action="store_true", help="show matplotlib 3D plot")
    args = ap.parse_args()

    from adaptivecad.pr.ribbon import PRRibbonConfig, generate_ribbon_mesh, save_ribbon_ama

    cfg = PRRibbonConfig(
        centerline=args.centerline,
        radius=args.radius,
        tilt_amplitude=args.tilt,
        tilt_freq=args.tilt_freq,
        width=args.width,
        twist_offset=args.twist_offset,
        twist_windings=args.twist,
        n_s=args.n_s,
        n_u=args.n_u,
    )

    print(f"Generating PR ribbon: {cfg.centerline}, twist={cfg.twist_windings}, tilt={cfg.tilt_amplitude}")
    
    # Generate mesh for stats / plotting
    verts, faces, phase = generate_ribbon_mesh(cfg)
    print(f"  Vertices: {len(verts)}, Faces: {len(faces)}")
    print(f"  Phase range: [{phase.min():.3f}, {phase.max():.3f}]")
    print(f"  Bounding box: [{verts.min(axis=0)}] → [{verts.max(axis=0)}]")

    # Save .ama
    path = save_ribbon_ama(cfg, args.out, scale=args.scale, units="mm")
    print(f"Saved: {path}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection

            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection="3d")

            # Collect triangles
            tri_verts = verts[faces]
            
            # Color by phase
            face_phase = phase[faces].mean(axis=1)
            face_phase_norm = (face_phase - face_phase.min()) / (face_phase.max() - face_phase.min() + 1e-9)
            colors = plt.cm.plasma(face_phase_norm)
            colors[:, 3] = 0.7  # transparency

            collection = Poly3DCollection(tri_verts, facecolors=colors, edgecolors="k", linewidths=0.1)
            ax.add_collection3d(collection)

            # Set limits
            max_range = np.abs(verts).max() * 1.1
            ax.set_xlim(-max_range, max_range)
            ax.set_ylim(-max_range, max_range)
            ax.set_zlim(-max_range, max_range)
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")
            ax.set_title(f"PR Ribbon — twist={cfg.twist_windings}, tilt={cfg.tilt_amplitude}")

            plt.tight_layout()
            plt.savefig("pr_ribbon_demo.png", dpi=150)
            print("Saved: pr_ribbon_demo.png")
            plt.show()

        except ImportError as e:
            print(f"Plotting unavailable: {e}")


if __name__ == "__main__":
    main()
