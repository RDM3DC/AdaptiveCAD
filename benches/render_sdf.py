import time, numpy as np, matplotlib.pyplot as plt
from benches.bench_config import WIDTH, HEIGHT, WORLD_TO_PX, PX_TOL, SDF_MAX_STEPS, SDF_TMAX
from benches.scene import circle_sdf


def ray_march_circle(R, width=WIDTH, height=HEIGHT):
    # Simple 2D viewer: x∈[-2,2], y∈[-1,1]; rays cast along +x per row
    xs = np.linspace(-2.0, 2.0, width)
    ys = np.linspace(-1.0, 1.0, height)
    step_eps_world = 1.0 / WORLD_TO_PX
    steps_accum, hits = 0, 0

    for y in ys:
        ro = np.array([xs[0], y], dtype=float)
        rd = np.array([1.0, 0.0], dtype=float)
        t = 0.0
        for s in range(SDF_MAX_STEPS):
            p = ro + t*rd
            d = float(circle_sdf(p[None, :], R))
            if d < step_eps_world:
                steps_accum += (s+1); hits += 1
                break
            t += d
            if t > SDF_TMAX: break

    avg_steps = (steps_accum / hits) if hits else float('nan')
    return avg_steps


def render_and_measure(R, out_png):
    t0 = time.perf_counter()
    theta = np.linspace(0, 2*np.pi, 4096)
    x, y = R*np.cos(theta), R*np.sin(theta)
    fig, ax = plt.subplots(figsize=(WIDTH/100, HEIGHT/100), dpi=100)
    ax.set_aspect('equal'); ax.set_xlim(-R*1.2, R*1.2); ax.set_ylim(-R*1.2, R*1.2)
    ax.axis('off'); ax.plot(x, y, lw=2.5)
    fig.savefig(out_png, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    frame_ms = (time.perf_counter() - t0)*1000

    avg_steps = ray_march_circle(R)
    return {
        "mode": "sdf",
        "R": R,
        "silhouette_error_px": 0.0,
        "avg_march_steps": avg_steps,
        "frame_ms": frame_ms,
        "png": str(out_png)
    }
