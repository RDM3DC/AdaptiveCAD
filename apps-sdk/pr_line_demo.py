#!/usr/bin/env python3
"""
PR_Line Demo – minimal phase-resolved polyline bending.

Equations (wrap-safe version):
  Phase diffusion (unit-circle):
    u_i = (cos φ_i, sin φ_i)
    u_i ← normalize(u_i + α (u_{i-1} − 2 u_i + u_{i+1}))
    φ_i ← atan2(u_i.y, u_i.x)

  Wrap-safe edge phase diff:
    Δφ_i = atan2(sin(φ_{i+1} − φ_i), cos(φ_{i+1} − φ_i))

  Gradient magnitude (two variants):
    (A) g_i = |Δφ_i|                      # stronger bending
    (B) g_i = |Δφ_i| / (|e_i| + ε)        # normalized, weaker

  Vertex bend (interior only):
    x_i ← x_i + β (g_{i-1} n_{i-1} − g_i n_i)

  Optional geometric smoothing:
    x_i ← x_i + λ (x_{i-1} − 2 x_i + x_{i+1})

Run:
    python pr_line_demo.py [--steps 50] [--alpha 0.1] [--beta 0.05] [--lam 0.01]
                           [--normalize-edge] [--plot]
"""
from __future__ import annotations

import argparse
import math
import numpy as np


def wrap_angle(a: float) -> float:
    """Map angle to (-π, π]."""
    return math.atan2(math.sin(a), math.cos(a))


def pr_line_step(
    x: np.ndarray,
    phi: np.ndarray,
    alpha: float,
    beta: float,
    lam: float,
    normalize_edge: bool,
    eps: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Single integration step for PR_Line.

    x   : (N, 2) vertex positions
    phi : (N,)   phase values
    Returns updated (x, phi).
    """
    N = len(phi)

    # --- Phase diffusion (unit-circle embedding) ---
    u = np.stack([np.cos(phi), np.sin(phi)], axis=-1)  # (N, 2)
    u_new = u.copy()
    for i in range(1, N - 1):
        lap = u[i - 1] - 2 * u[i] + u[i + 1]
        u_new[i] = u[i] + alpha * lap
        norm = np.linalg.norm(u_new[i]) + eps
        u_new[i] /= norm
    phi_new = np.arctan2(u_new[:, 1], u_new[:, 0])

    # --- Edge quantities ---
    e = np.diff(x, axis=0)  # (N-1, 2)
    e_len = np.linalg.norm(e, axis=1) + eps  # (N-1,)
    t = e / e_len[:, None]  # unit tangent
    n = np.stack([-t[:, 1], t[:, 0]], axis=-1)  # unit normal (90° CCW)

    # Wrap-safe phase diff per edge
    dphi = np.array([wrap_angle(phi_new[i + 1] - phi_new[i]) for i in range(N - 1)])

    # Gradient magnitude
    if normalize_edge:
        g = np.abs(dphi) / e_len
    else:
        g = np.abs(dphi)

    # --- Geometry bend (interior vertices) ---
    x_new = x.copy()
    for i in range(1, N - 1):
        bend = beta * (g[i - 1] * n[i - 1] - g[i] * n[i])
        x_new[i] += bend

    # Optional geometric smoothing
    if lam > 0:
        for i in range(1, N - 1):
            lap_x = x_new[i - 1] - 2 * x_new[i] + x_new[i + 1]
            x_new[i] += lam * lap_x

    return x_new, phi_new


def run_demo(
    n_pts: int = 10,
    steps: int = 50,
    alpha: float = 0.1,
    beta: float = 0.05,
    lam: float = 0.01,
    normalize_edge: bool = False,
    plot: bool = False,
):
    # Initial positions: straight line along x-axis
    x = np.zeros((n_pts, 2), dtype=np.float64)
    x[:, 0] = np.linspace(0, 1, n_pts)

    # Initial phase: sinusoidal
    phi = np.sin(np.linspace(0, 2 * np.pi, n_pts))

    print("PR_Line Demo")
    print(f"  N={n_pts}, steps={steps}, α={alpha}, β={beta}, λ={lam}")
    print(f"  normalize_edge={normalize_edge}")
    print(f"  Initial phase range: [{phi.min():.4f}, {phi.max():.4f}]")
    print()

    history_x = [x.copy()]
    history_phi = [phi.copy()]

    for s in range(steps):
        x, phi = pr_line_step(x, phi, alpha, beta, lam, normalize_edge)
        history_x.append(x.copy())
        history_phi.append(phi.copy())

    y_dev = np.abs(x[:, 1]).max()
    print(f"After {steps} steps:")
    print(f"  Max y-deviation: {y_dev:.4f}")
    print(f"  Final phase range: [{phi.min():.4f}, {phi.max():.4f}]")

    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(10, 4))

            # Left: geometry evolution
            ax = axes[0]
            for i, xh in enumerate(history_x[:: max(1, steps // 5)]):
                c = plt.cm.viridis(i / (len(history_x[:: max(1, steps // 5)]) - 1 + 1e-9))
                ax.plot(xh[:, 0], xh[:, 1], "-o", markersize=4, color=c, label=f"step {i * max(1, steps // 5)}")
            ax.set_xlabel("x")
            ax.set_ylabel("y")
            ax.set_title("PR_Line geometry evolution")
            ax.legend(fontsize=7)
            ax.set_aspect("equal", "box")

            # Right: phase evolution
            ax = axes[1]
            for i, ph in enumerate(history_phi[:: max(1, steps // 5)]):
                c = plt.cm.viridis(i / (len(history_phi[:: max(1, steps // 5)]) - 1 + 1e-9))
                ax.plot(ph, "-o", markersize=4, color=c)
            ax.set_xlabel("vertex index")
            ax.set_ylabel("φ")
            ax.set_title("Phase evolution")

            plt.tight_layout()
            plt.savefig("pr_line_demo.png", dpi=150)
            print("Saved pr_line_demo.png")
            plt.show()
        except ImportError:
            print("matplotlib not available; skipping plot")

    return x, phi


def main():
    ap = argparse.ArgumentParser(description="PR_Line minimal demo")
    ap.add_argument("--n-pts", type=int, default=10, help="number of vertices")
    ap.add_argument("--steps", type=int, default=50, help="integration steps")
    ap.add_argument("--alpha", type=float, default=0.1, help="phase diffusion rate")
    ap.add_argument("--beta", type=float, default=0.05, help="geometry bend rate")
    ap.add_argument("--lam", type=float, default=0.01, help="geometric smoothing rate")
    ap.add_argument("--normalize-edge", action="store_true", help="divide |Δφ| by edge length (weaker bending)")
    ap.add_argument("--plot", action="store_true", help="plot results with matplotlib")
    args = ap.parse_args()

    run_demo(
        n_pts=args.n_pts,
        steps=args.steps,
        alpha=args.alpha,
        beta=args.beta,
        lam=args.lam,
        normalize_edge=args.normalize_edge,
        plot=args.plot,
    )


if __name__ == "__main__":
    main()
