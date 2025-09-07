import time, math, json
import numpy as np
import matplotlib.pyplot as plt
from benches.bench_config import PX_TOL, WORLD_TO_PX, WIDTH, HEIGHT
from benches.scene import param_circle


def chord_error_inscribed_n_gon(R, n):
    return R * (1.0 - math.cos(math.pi / n))

def n_required_for_tol(R, eps_world):
    if eps_world <= 0: return 10_000
    approx = math.pi / math.sqrt(2 * (eps_world / max(R, 1e-12)))
    n = max(3, int(approx))
    targ = 1 - eps_world / max(R, 1e-12)
    while n < 10_000 and math.cos(math.pi/n) < targ:
        n += 1
    return n

def draw_ngon(R, n, ax, **kw):
    t = np.linspace(0, 2*np.pi, n+1)
    x, y = R*np.cos(t), R*np.sin(t)
    ax.plot(x, y, **kw)

def render_and_measure(R, out_png, fixed_n=None):
    """Renders a fixed-n polygon (or n chosen to meet tolerance) and returns metrics."""
    eps_world = PX_TOL / WORLD_TO_PX
    n = fixed_n or n_required_for_tol(R, eps_world)

    t0 = time.perf_counter()
    fig, ax = plt.subplots(figsize=(WIDTH/100, HEIGHT/100), dpi=100)
    ax.set_aspect('equal'); ax.set_xlim(-R*1.2, R*1.2); ax.set_ylim(-R*1.2, R*1.2)
    ax.axis('off')
    draw_ngon(R, n, ax, lw=2.5)
    fig.savefig(out_png, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    ms = (time.perf_counter() - t0)*1000

    err_world = chord_error_inscribed_n_gon(R, n)
    err_px = err_world * WORLD_TO_PX
    tris = 4*n  # if extruded thin ring; rough intuition only
    mesh_size_MB = (tris * 50) / (1024*1024)  # very rough STL-ish estimate

    return {
        "mode": "mesh",
        "R": R, "n_edges": n,
        "silhouette_error_px": err_px,
        "frame_ms": ms,
        "triangles_est": tris,
        "mesh_size_MB_est": mesh_size_MB,
        "png": str(out_png)
    }
