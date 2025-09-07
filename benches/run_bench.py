#!/usr/bin/env python3
"""
AdaptiveCAD Bench (single-file)
- Mesh (Euclidean polygon) vs triangle-free SDF rendering of a 2D circle
- Warm-up timing to remove first-frame distortion
- CSV + charts + markdown report
- CLI args for radii, pixel tolerance, π_a beta, output dir

Usage examples:
  python benches/run_bench.py
  python benches/run_bench.py --radii 0.25 0.75 1.5 --tol-px 0.25
  python benches/run_bench.py --pa-beta 0.32 --apply-pa
"""

import argparse, csv, json, math, time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# -------------------------------
# Core helpers
# -------------------------------
def chord_error_inscribed_n_gon(radius: float, n: int) -> float:
    # Max radial deviation between circle and its inscribed n-gon
    return radius * (1.0 - math.cos(math.pi / max(n, 3)))

def n_required_for_tol(radius: float, eps_world: float) -> int:
    """Smallest n such that r*(1 - cos(pi/n)) <= eps_world."""
    if eps_world <= 0:
        return 10000
    # good initial guess via cos x ~ 1 - x^2/2  =>  1 - cos(pi/n) ~ pi^2/(2 n^2)
    approx = math.pi / math.sqrt(2.0 * (eps_world / max(radius, 1e-12)))
    n = max(3, int(approx))
    target = 1.0 - eps_world / max(radius, 1e-12)
    while n < 10000 and math.cos(math.pi / n) < target:
        n += 1
    return n

def circle_sdf(p, R):
    # p: (...,2)
    return np.linalg.norm(p, axis=-1) - R

def ray_march_2d_circle_avg_steps(R, world_to_px=600, width_px=480, height_px=200,
                                  max_steps=256, tmax=4.0):
    """Scanline ray marcher in 2D to estimate avg steps for a circle SDF."""
    xs = np.linspace(-2.0, 2.0, width_px)
    ys = np.linspace(-1.0, 1.0, height_px)
    step_eps_world = 1.0 / world_to_px
    steps_accum, hits = 0, 0
    for y in ys:
        ro = np.array([xs[0], y], dtype=float)
        rd = np.array([1.0, 0.0], dtype=float)
        t = 0.0
        for s in range(max_steps):
            p = ro + t * rd
            d = float(circle_sdf(p[None, :], R))
            if d < step_eps_world:
                steps_accum += (s + 1)
                hits += 1
                break
            t += d
            if t > tmax:
                break
    return (steps_accum / hits) if hits else float("nan")

def render_polygon_png(R, n, out_png, width=640, height=360):
    """PNG ‘frame’ proxy for mesh path (so timing includes plotting & raster)."""
    t0 = time.perf_counter()
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    ax.set_aspect("equal")
    ax.set_xlim(-R*1.2, R*1.2); ax.set_ylim(-R*1.2, R*1.2)
    ax.axis("off")
    theta = np.linspace(0, 2*np.pi, n+1)
    ax.plot(R*np.cos(theta), R*np.sin(theta), lw=2.5)
    fig.savefig(out_png, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return (time.perf_counter() - t0) * 1000.0  # ms

def render_analytic_circle_png(R, out_png, width=640, height=360):
    """PNG ‘frame’ proxy for SDF/analytic path (smooth parametric curve)."""
    t0 = time.perf_counter()
    theta = np.linspace(0, 2*np.pi, 4096)
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    ax.set_aspect("equal")
    ax.set_xlim(-R*1.2, R*1.2); ax.set_ylim(-R*1.2, R*1.2)
    ax.axis("off")
    ax.plot(R*np.cos(theta), R*np.sin(theta), lw=2.5)
    fig.savefig(out_png, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return (time.perf_counter() - t0) * 1000.0  # ms

# -------------------------------
# Bench
# -------------------------------
def run_bench(radii, tol_px, world_to_px, apply_pa, pa_beta,
              width=640, height=360, outdir=Path("bench_out")):
    outdir.mkdir(parents=True, exist_ok=True)

    # Warm-up: one dummy frame for each path to stabilize plotting/timing
    render_polygon_png(0.3, 16, outdir / "_warmup_mesh.png", width, height)
    render_analytic_circle_png(0.3, outdir / "_warmup_sdf.png", width, height)

    rows = []
    for R in radii:
        # π_a scaling (optional)
        s = (1.0 + pa_beta*(R**2)) if apply_pa else 1.0
        R_eff = s * R

        # Mesh path: find n to meet silhouette error <= tol_px
        eps_world = tol_px / world_to_px
        n = n_required_for_tol(R_eff, eps_world)
        mesh_png = outdir / f"mesh_R{R:.3f}_ne{n}.png"
        mesh_ms = render_polygon_png(R_eff, n, mesh_png, width, height)
        err_world = chord_error_inscribed_n_gon(R_eff, n)
        err_px = err_world * world_to_px
        tris_est = 4 * n  # rough intuition if extruded thin ring
        mesh_size_MB = (tris_est * 50) / (1024*1024)  # super rough STL-ish

        # SDF/analytic path
        sdf_png = outdir / f"smooth_R{R:.3f}.png"
        sdf_ms = render_analytic_circle_png(R_eff, sdf_png, width, height)
        avg_steps = ray_march_2d_circle_avg_steps(R_eff, world_to_px=world_to_px)

        rows.append({
            "R_input": R,
            "pa_beta": pa_beta if apply_pa else 0.0,
            "R_effective": R_eff,
            "mesh_n_edges": n,
            "mesh_silhouette_error_px": err_px,
            "mesh_frame_ms": mesh_ms,
            "mesh_triangles_est": tris_est,
            "mesh_size_MB_est": mesh_size_MB,
            "sdf_frame_ms": sdf_ms,
            "sdf_avg_steps": avg_steps,
            "mesh_png": str(mesh_png.name),
            "sdf_png": str(sdf_png.name),
        })

    # Write CSV + JSON
    csv_path = outdir / "summary.csv"
    json_path = outdir / "summary.json"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2)

    # Charts
    radii_eff = np.array([r["R_effective"] for r in rows])
    n_req = np.array([r["mesh_n_edges"] for r in rows])
    mesh_MB = np.array([r["mesh_size_MB_est"] for r in rows])
    sdf_steps = np.array([r["sdf_avg_steps"] for r in rows])

    def save_plot(x, y, title, xlabel, ylabel, fname):
        fig = plt.figure(figsize=(7, 4.2))
        ax = fig.add_subplot(111)
        ax.plot(x, y, linewidth=2)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        fig.tight_layout()
        p = outdir / fname
        fig.savefig(p.as_posix(), dpi=130)
        plt.close(fig)
        return p

    p_edges = save_plot(radii_eff, n_req,
                        "Edges required vs effective radius (≤ tolerance)",
                        "effective radius (world units)", "polygon edges (n)",
                        "plot_edges_vs_radius.png")
    p_mesh = save_plot(radii_eff, mesh_MB,
                       "Rough mesh size vs effective radius (meeting tolerance)",
                       "effective radius (world units)", "approx mesh size (MB)",
                       "plot_mesh_size_vs_radius.png")
    p_steps = save_plot(radii_eff, sdf_steps,
                        "SDF ray-march avg steps vs effective radius",
                        "effective radius (world units)", "avg steps",
                        "plot_sdf_steps_vs_radius.png")

    # Markdown report
    md = outdir / "report.md"
    with open(md, "w") as f:
        f.write("# AdaptiveCAD Bench — 2D Circle\n\n")
        f.write(f"- Pixel tolerance: **{tol_px} px**, world_to_px: **{world_to_px} px/unit**\n")
        f.write(f"- πₐ applied: **{apply_pa}** (β = {pa_beta})\n")
        f.write("\n## Summary charts\n\n")
        f.write(f"![Edges vs radius]({p_edges.name})\n\n")
        f.write(f"![Mesh size vs radius]({p_mesh.name})\n\n")
        f.write(f"![SDF steps vs radius]({p_steps.name})\n\n")
        f.write("## Data\n\n")
        f.write("See `summary.csv` and `summary.json` for raw values.\n")
        f.write("\n## Notes\n")
        f.write("- Mesh path keeps silhouette error ≤ tolerance by increasing edges.\n")
        f.write("- SDF/analytic path targets a pixel-sized epsilon and doesn’t inflate mesh size.\n")
        if apply_pa:
            f.write("- Effective radius uses \( r_a = (1+\\beta r^2) r \\, showing πₐ-driven divergence.\n")

    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "report": str(md),
        "charts": [str(p_edges), str(p_mesh), str(p_steps)],
        "rows": rows,
    }

# -------------------------------
# CLI
# -------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="AdaptiveCAD Bench (2D circle)")
    ap.add_argument("--radii", type=float, nargs="*", default=[0.2, 0.5, 1.0, 1.5],
                    help="List of radii (world units)")
    ap.add_argument("--tol-px", type=float, default=0.5,
                    help="Silhouette tolerance in pixels")
    ap.add_argument("--world-to-px", type=float, default=600,
                    help="Pixels per world unit for measurements")
    ap.add_argument("--apply-pa", action="store_true",
                    help="Apply π_a scaling to radius: r_eff = (1+β r^2) r")
    ap.add_argument("--pa-beta", type=float, default=0.0,
                    help="β value for π_a/π = 1 + β r^2")
    ap.add_argument("--width", type=int, default=640, help="PNG width")
    ap.add_argument("--height", type=int, default=360, help="PNG height")
    ap.add_argument("--outdir", type=str, default="bench_out", help="Output directory")
    return ap.parse_args()

def main():
    args = parse_args()
    res = run_bench(
        radii=args.radii,
        tol_px=args.tol_px,
        world_to_px=args.world_to_px,
        apply_pa=args.apply_pa,
        pa_beta=args.pa_beta,
        width=args.width,
        height=args.height,
        outdir=Path(args.outdir),
    )
    print("Wrote:")
    print(" ", res["csv"])
    print(" ", res["json"])
    print(" ", res["report"])
    for c in res["charts"]:
        print(" ", c)

if __name__ == "__main__":
    main()
