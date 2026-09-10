#!/usr/bin/env python3
# (truncated header for brevity in this file) — full docstring in canvas version
import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def inside_hex_xy(X, Y, R):
    return (np.abs(X) <= R) & (np.abs(X) + np.sqrt(3.0) * np.abs(Y) <= 2 * R)


def gaussian_kernel_fft(nx, ny, sigma):
    kx = np.fft.fftfreq(nx)
    ky = np.fft.fftfreq(ny)
    KX, KY = np.meshgrid(kx, ky, indexing="ij")
    H = np.exp(-2 * (np.pi**2) * (sigma**2) * (KX**2 + KY**2))
    return H


def correlated_fields(nx, ny, corr=0.5, sigma=6.0, seed=0):
    rng = np.random.default_rng(seed)
    u = rng.standard_normal((nx, ny))
    w = rng.standard_normal((nx, ny))
    v = corr * u + np.sqrt(max(0.0, 1.0 - corr**2)) * w
    H = gaussian_kernel_fft(nx, ny, sigma)

    def blur(a):
        Af = np.fft.fftn(a)
        return np.fft.ifftn(Af * H).real

    u_b = blur(u)
    v_b = blur(v)

    def norm01(a):
        mn, mx = a.min(), a.max()
        return (a - mn) / (mx - mn + 1e-12)

    return norm01(u_b), norm01(v_b)


def apply_scenario(lam, alf, scenario, R, xs, ys):
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    M = inside_hex_xy(X, Y, R)
    lam2, alf2 = lam.copy(), alf.copy()
    if scenario == "hotspot":
        bump = np.exp(-(((X - 0.25 * R) ** 2 + (Y + 0.1 * R) ** 2) / (2 * (0.22 * R) ** 2)))
        alf2 = np.clip(alf2 + 0.25 * bump, 0, 1)
    elif scenario == "shear_band":
        band = 0.5 * (np.tanh((Y + 0.2 * R) / (0.05 * R)) - np.tanh((Y - 0.2 * R) / (0.05 * R)))
        lam2 = np.clip(lam2 + 0.2 * band, 0, 1)
    elif scenario == "rim":
        rim = (X**2 + Y**2) / (R**2)
        alf2 = np.clip(alf2 + 0.2 * rim, 0, 1)
    elif scenario == "multi_hotspot":
        b1 = np.exp(-(((X - 0.3 * R) ** 2 + (Y + 0.15 * R) ** 2) / (2 * (0.18 * R) ** 2)))
        b2 = np.exp(-(((X + 0.25 * R) ** 2 + (Y - 0.2 * R) ** 2) / (2 * (0.16 * R) ** 2)))
        alf2 = np.clip(alf2 + 0.18 * (b1 + b2), 0, 1)
    lam2 *= M
    alf2 *= M
    return lam2, alf2


def wire_gyroid_paths(L=40.0, n_cells=3, wires_per_axis=3, amp=4.0, N=120):
    import numpy as np

    xmin = ymin = zmin = -L / 2
    xmax = ymax = zmax = L / 2
    xs = np.linspace(xmin, xmax, N)
    ys = np.linspace(ymin, ymax, N)
    zs = np.linspace(zmin, zmax, N)
    k = 2 * math.pi * n_cells / L
    paths = []
    for i in range(wires_per_axis):
        for j in range(wires_per_axis):
            y0 = ymin + (i + 0.5) * (L / wires_per_axis)
            z0 = zmin + (j + 0.5) * (L / wires_per_axis)
            P = np.stack(
                [xs, y0 + np.sin(k * xs + 0.6 * j) * 4.0, z0 + np.cos(k * xs + 0.4 * i) * 4.0],
                axis=1,
            )
            paths.append(P)
    for i in range(wires_per_axis):
        for j in range(wires_per_axis):
            x0 = xmin + (i + 0.5) * (L / wires_per_axis)
            z0 = zmin + (j + 0.5) * (L / wires_per_axis)
            P = np.stack(
                [x0 + np.sin(k * ys + 0.5 * i) * 4.0, ys, z0 + np.cos(k * ys + 0.7 * j) * 4.0],
                axis=1,
            )
            paths.append(P)
    for i in range(wires_per_axis):
        for j in range(wires_per_axis):
            x0 = xmin + (i + 0.5) * (L / wires_per_axis)
            y0 = ymin + (j + 0.5) * (L / wires_per_axis)
            P = np.stack(
                [x0 + np.sin(k * zs + 0.4 * j) * 4.0, y0 + np.cos(k * zs + 0.6 * i) * 4.0, zs],
                axis=1,
            )
            paths.append(P)
    return paths


def wire_metrics(L=40.0, wires_per_axis=3, r_wire=0.6, n_cells=3, N=120):
    import numpy as np

    paths = wire_gyroid_paths(L, n_cells, wires_per_axis, 4.0, N)
    total_len = 0.0
    taus = []
    for P in paths:
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1).sum()
        total_len += seg
        taus.append(seg / L)
    tau_mean = float(np.mean(taus))
    vol = math.pi * (r_wire**2) * total_len
    bbox_vol = L**3
    Aeff = vol / L
    density = vol / bbox_vol
    return dict(total_len=total_len, tau=tau_mean, A_eff=Aeff, density=density)


def try_publish(topic, payload_json):
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String
    except Exception:
        print(payload_json)
        return False
    rclpy.init()

    class Pub(Node):
        def __init__(self):
            super().__init__("adaptivecad_fields_pub")
            self.pub = self.create_publisher(String, topic, 10)
            msg = String()
            msg.data = payload_json
            self.pub.publish(msg)
            self.get_logger().info(f"Published to {topic}")

    node = Pub()
    import rclpy as _r

    _r.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    _r.shutdown()
    return True


def run_sweep(args):
    outdir = Path(args.outdir)
    (outdir / "figs").mkdir(parents=True, exist_ok=True)
    nx = ny = args.grid
    xs = np.linspace(-args.R, args.R, nx)
    ys = np.linspace(-args.R, args.R, ny)
    import pandas as pd

    rows = []
    sums = {}

    def summarize(sums):
        ss = []
        for rho, d in sums.items():

            def mean_std(arr):
                a = np.array(arr, float)
                return (
                    float(a.mean()) if a.size else float("inf"),
                    float(a.std(ddof=0)) if a.size else 0.0,
                )

            A_m, A_s = mean_std(d["A_eff"])
            D_m, D_s = mean_std(d["density"])
            T_m, T_s = mean_std(d["tau"])
            X_m, X_s = mean_std(d["DeltaT"])
            ss.append(
                {
                    "rho": rho,
                    "A_eff_mean": A_m,
                    "A_eff_std": A_s,
                    "density_mean": D_m,
                    "density_std": D_s,
                    "tau_mean": T_m,
                    "tau_std": T_s,
                    "DeltaT_mean": X_m,
                    "DeltaT_std": X_s,
                }
            )
        ss.sort(key=lambda r: r["rho"])
        return ss

    coarse = sorted(set([float(x) for x in args.coarse]))
    seeds = args.seeds
    sums = {rho: {"A_eff": [], "density": [], "tau": [], "DeltaT": []} for rho in coarse}
    for rho in coarse:
        for seed in seeds:
            lam, alf = correlated_fields(nx, ny, corr=rho, sigma=args.sigma, seed=seed)
            lam, alf = apply_scenario(lam, alf, args.scenario, args.R, xs, ys)
            X, Y = np.meshgrid(xs, ys, indexing="ij")
            M = inside_hex_xy(X, Y, args.R)
            lam_h = lam[M]
            alf_h = alf[M]
            lam_mean = float(lam_h.mean()) if lam_h.size else 0.5
            alf_mean = float(alf_h.mean()) if alf_h.size else 0.5
            r_wire = args.r_wire0 * (1.0 + args.gam_w * lam_mean)
            t_skin = args.t0 * (1.0 + args.gam_a * alf_mean)
            met = wire_metrics(L=40.0, wires_per_axis=3, r_wire=r_wire, n_cells=3, N=120)
            A_eff = met["A_eff"]
            density = met["density"]
            tau = met["tau"]
            dT = 1.0 / (A_eff + args.kappa * t_skin)
            rows.append(
                {
                    "stage": "coarse",
                    "scenario": args.scenario,
                    "rho": rho,
                    "seed": seed,
                    "lambda_mean": lam_mean,
                    "alpha_mean": alf_mean,
                    "r_wire_mm": r_wire,
                    "t_skin_mm": t_skin,
                    "A_eff_proxy": A_eff,
                    "density_proxy": density,
                    "tortuosity": tau,
                    "DeltaT_proxy": dT,
                    "feasible": (density <= args.density_max and tau <= args.tau_max),
                }
            )
            sums[rho]["A_eff"].append(A_eff)
            sums[rho]["density"].append(density)
            sums[rho]["tau"].append(tau)
            sums[rho]["DeltaT"].append(dT)
            if args.publish:
                payload = json.dumps(
                    {
                        "stage": "coarse",
                        "scenario": args.scenario,
                        "rho": rho,
                        "seed": seed,
                        "stats": {
                            "lam_mean": lam_mean,
                            "alpha_mean": alf_mean,
                            "r_wire_mm": r_wire,
                            "t_skin_mm": t_skin,
                            "A_eff": A_eff,
                            "density": density,
                            "tau": tau,
                            "DeltaT": dT,
                        },
                    }
                )
                try_publish("/adaptivecad/fields", payload)
    df_rows = pd.DataFrame(rows)
    df_rows.to_csv(outdir / "entangled_sweep_metrics.csv", index=False)
    sum_coarse = summarize(sums)
    pd.DataFrame(sum_coarse).to_csv(outdir / "summary_coarse.csv", index=False)
    # One plot (ΔT vs rho) to keep this file compact
    xs_plot = [r["rho"] for r in sum_coarse]
    ys_plot = [r["DeltaT_mean"] for r in sum_coarse]
    es = [r["DeltaT_std"] for r in sum_coarse]
    fig = plt.figure(figsize=(7, 5))
    plt.errorbar(xs_plot, ys_plot, yerr=es, marker="o")
    plt.xlabel("ρ (correlation)")
    plt.ylabel("ΔT proxy (lower better)")
    plt.tight_layout()
    fig.savefig(outdir / "DeltaT_vs_rho.png", dpi=160)
    plt.close(fig)
    # Simple panel GIF across rho (seed 0)
    import io as _io

    frames = []
    nx = ny = args.grid
    for rho in xs_plot:
        lam, alf = correlated_fields(nx, ny, corr=rho, sigma=args.sigma, seed=0)
        lam, alf = apply_scenario(lam, alf, args.scenario, args.R, xs, ys)
        fig, axs = plt.subplots(1, 2, figsize=(8.6, 4.0))
        axs[0].imshow(lam.T, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], aspect="equal")
        axs[0].set_title(f"λ (ρ={rho})")
        axs[0].set_axis_off()
        axs[1].imshow(alf.T, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], aspect="equal")
        axs[1].set_title(f"α (ρ={rho})")
        axs[1].set_axis_off()
        fig.tight_layout()
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=140)
        plt.close(fig)
        buf.seek(0)
        frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=128))
    gif = outdir / "figs" / "rho_sweep_panels.gif"
    (outdir / "figs").mkdir(exist_ok=True)
    frames[0].save(
        gif, save_all=True, append_images=frames[1:], duration=900, loop=0, optimize=True
    )
    print(json.dumps({"outdir": str(outdir.resolve())}))


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scenario",
        type=str,
        default="hotspot",
        choices=["hotspot", "shear_band", "rim", "multi_hotspot", "uniform"],
    )
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument(
        "--coarse", type=float, nargs="+", default=[0.0, 0.1, 0.2, 0.25, 0.3, 0.5, 0.75]
    )
    ap.add_argument("--refine_width", type=float, default=0.2)
    ap.add_argument("--refine_step", type=float, default=0.05)
    ap.add_argument("--density_max", type=float, default=0.15)
    ap.add_argument("--tau_max", type=float, default=4.0)
    ap.add_argument("--R", type=float, default=25.0)
    ap.add_argument("--grid", type=int, default=180)
    ap.add_argument("--sigma", type=float, default=6.0)
    ap.add_argument("--t0", type=float, default=2.0)
    ap.add_argument("--r_wire0", type=float, default=0.6)
    ap.add_argument("--gam_w", type=float, default=0.30)
    ap.add_argument("--gam_a", type=float, default=0.60)
    ap.add_argument("--kappa", type=float, default=0.4)
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--outdir", type=str, default="optimizer_results")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_sweep(args)
