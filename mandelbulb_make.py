#!/usr/bin/env python3
"""
Procedural Mandelbulb mesh generator with swappable color fields and Adaptive-π hook.
Generates fractal from mathematical formula, exports STL (geometry) and PLY (with colors).
"""

import argparse
import math
import sys
import os
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from skimage.measure import marching_cubes
import trimesh

# Ensure CUDA DLLs are discoverable on Windows before importing CuPy
if sys.platform.startswith("win"):
    try:
        import importlib.util
        from pathlib import Path

        _dll_specs = [
            importlib.util.find_spec("nvidia.cuda_runtime"),
            importlib.util.find_spec("nvidia.cuda_nvrtc"),
        ]
        for _spec in _dll_specs:
            if _spec and _spec.origin:
                _base = Path(_spec.origin).resolve().parent
                for _sub in ("bin", "lib", "Lib", "DLLs"):
                    _dll_dir = _base / _sub
                    if _dll_dir.exists():
                        os.add_dll_directory(str(_dll_dir))
    except Exception:
        pass

try:  # Optional GPU accelerator
    import cupy as cp  # type: ignore
    _HAVE_CUPY = True
except Exception:  # pragma: no cover - GPU runtime optional
    cp = None  # type: ignore
    _HAVE_CUPY = False

# ---------------------------
# Adaptive-π hook (simple)
# ---------------------------
def pi_adaptive(pi_base, pi_a, alpha, mu, metric_val=0.0):
    """
    Minimal πₐ hook so you can start experimenting.
    We use two terms:
      - gradient-like term (alpha * metric_val) to nudge πₐ
      - decay toward base π (mu)
    Feel free to replace with your full πₐ kernel later.
    """
    # near-regime toggle could use metric_val; keep simple for now
    return pi_a - alpha * metric_val - mu * (pi_a - pi_base)

# ---------------------------
# Adaptive norm (custom √)
# ---------------------------
def adaptive_norm(r, kind="tanh_warp", k=0.12, r0=0.9, sigma=0.35):
    """
    r_a = g(r). Returns (r_a, dr_a_dr) so we can keep the DE derivative stable.
    - kind="tanh_warp": r_a = r * (1 + k * tanh((r - r0)/sigma))
      Push/pull distances near r0; tune k∈[-0.5,0.5], sigma>0
    Replace this with your exact sqrt_a when you're ready.
    """
    if kind == "tanh_warp":
        t = math.tanh((r - r0) / max(1e-8, sigma))
        r_a = r * (1.0 + k * t)
        dt_dr = (1.0 - t*t) / max(1e-8, sigma)
        dr_a_dr = (1.0 + k * t) + r * k * dt_dr
        return r_a, max(dr_a_dr, 1e-6)
    else:
        # Identity as fallback
        return r, 1.0

# ---------------------------
# Fractal core
# ---------------------------
def mandelbulb_orbit(p, power=8.0, bailout=8.0, max_iter=14,
                     pi_mode='fixed', pi_base=math.pi, pi_alpha=0.0, pi_mu=0.0,
                     norm_mode='euclid', norm_kind='tanh_warp', norm_k=0.12, 
                     norm_r0=0.9, norm_sigma=0.35, step_scale=1.0):
    """
    Return:
      de: distance estimate (float) with step_scale applied
      orbit: dict with fields for coloring (nu, trapPlane, trapShell, lastZ, iters, pi_a)
      
    Args:
        norm_mode: 'euclid' (default) or 'adaptive'
        norm_kind, norm_k, norm_r0, norm_sigma: adaptive norm parameters
        step_scale: safety factor for DE (use 0.8 with adaptive norm)
    """
    z = np.array(p, dtype=np.float64)
    dr = 1.0
    r_euclid = 0.0

    trapPlane = 1e9
    trapShell = 1e9
    lastZ     = z.copy()
    iters     = 0

    # π handling
    pi_a = pi_base

    for i in range(max_iter):
        r_euclid = np.linalg.norm(z)
        trapPlane = min(trapPlane, abs(z[1]))
        trapShell = min(trapShell, abs(r_euclid - 1.0))  # R=1 shell

        if r_euclid > bailout:
            iters = i
            break

        # --- Choose norm ---
        if norm_mode == 'adaptive':
            r, dr_a_dr = adaptive_norm(r_euclid, kind=norm_kind, k=norm_k, r0=norm_r0, sigma=norm_sigma)
        else:
            r, dr_a_dr = r_euclid, 1.0

        # spherical from Euclidean vector
        if r_euclid == 0.0:
            theta = 0.0
            phi   = 0.0
        else:
            theta = math.acos(np.clip(z[2] / r_euclid, -1.0, 1.0))
            phi   = math.atan2(z[1], z[0])

        # --- Adaptive π ---
        if pi_mode != 'fixed':
            pi_a = pi_adaptive(pi_base, pi_a, pi_alpha, pi_mu, metric_val=r)

        # raise to power with chain rule for derivative
        rp = r ** power
        dr = dr * power * max(r, 1e-9) ** (power - 1.0) * dr_a_dr + 1.0

        # angles multiplied by power
        thetap = theta * power
        phip   = phi   * power

        # convert back
        st = math.sin(thetap)
        ct = math.cos(thetap)
        cp = math.cos(phip)
        sp = math.sin(phip)

        z = rp * np.array([st*cp, st*sp, ct], dtype=np.float64) + p
        lastZ = z.copy()
        iters = i + 1

    # smooth escape (use Euclidean r for stability)
    rr = max(r_euclid, 1e-8)
    if rr > 1.0:
        nu = float(iters) + 1.0 - math.log(math.log(rr)) / math.log(max(power, 1.001))
    else:
        nu = float(iters)

    # distance estimator with safety scale
    de = 0.5 * math.log(rr) * rr / max(dr, 1e-6) * step_scale

    orbit = dict(
        trapPlane=trapPlane,
        trapShell=trapShell,
        r=rr,
        nu=nu,
        lastZ=lastZ,
        iters=iters,
        pi_a=pi_a
    )
    return de, orbit

def field_sample(bounds, res, power, bailout, max_iter, pi_mode, pi_base, pi_alpha, pi_mu, *, use_gpu=False):
    """
    Sample DE on a 3D grid. Return scalar field (DE minus iso) and store an
    orbit cache at sparsely chosen points for later color interpolation.
    """
    (xmin, xmax, ymin, ymax, zmin, zmax) = bounds
    nx = ny = nz = res

    if use_gpu and not _HAVE_CUPY:
        print("  [!] GPU requested but CuPy is unavailable. Falling back to CPU sampling.")
        use_gpu = False

    if use_gpu:
        return _field_sample_gpu(
            bounds, res, power, bailout, max_iter, pi_mode, pi_base, pi_alpha, pi_mu
        )

    xs = np.linspace(xmin, xmax, nx)
    ys = np.linspace(ymin, ymax, ny)
    zs = np.linspace(zmin, zmax, nz)

    field = np.empty((nx, ny, nz), dtype=np.float32)

    # Iso value (we want DE ~ 0 on surface; use small positive iso)
    iso = 0.0025 * (xmax - xmin)  # scale with box size a little

    cpu_workers = max(1, min((os.cpu_count() or 1), nx))
    env_workers = os.getenv("ADCAD_MANDELBULB_CPU_WORKERS")
    if env_workers:
        try:
            cpu_workers = max(1, min(nx, int(env_workers)))
        except Exception:
            pass
    use_parallel = cpu_workers > 1 and res >= 48

    if use_parallel:
        print(f"  Sampling {nx}x{ny}x{nz} grid (CPU, {cpu_workers} workers)...")

        tasks = [
            (ix, float(x), ys, zs, power, bailout, max_iter, pi_mode, pi_base, pi_alpha, pi_mu, iso)
            for ix, x in enumerate(xs)
        ]

        with ProcessPoolExecutor(max_workers=cpu_workers) as executor:
            for idx, slice_vals in executor.map(_sample_cpu_slice, tasks, chunksize=1):
                field[idx, :, :] = slice_vals
                if idx % 20 == 0:
                    print(f"    Progress: {idx}/{nx}")
        print(f"    Progress: {nx}/{nx}")
    else:
        print(f"  Sampling {nx}x{ny}x{nz} grid (CPU)...")
        for ix, x in enumerate(xs):
            if ix % 20 == 0:
                print(f"    Progress: {ix}/{nx}")
            for iy, y in enumerate(ys):
                for iz, z in enumerate(zs):
                    p = np.array([x, y, z], dtype=np.float64)
                    de, _ = mandelbulb_orbit(
                        p, power=power, bailout=bailout, max_iter=max_iter,
                        pi_mode=pi_mode, pi_base=pi_base, pi_alpha=pi_alpha, pi_mu=pi_mu
                    )
                    field[ix, iy, iz] = de - iso
        print(f"    Progress: {nx}/{nx}")

    return field, (xs, ys, zs)


def _sample_cpu_slice(args):
    (
        ix,
        x,
        ys,
        zs,
        power,
        bailout,
        max_iter,
        pi_mode,
        pi_base,
        pi_alpha,
        pi_mu,
        iso,
    ) = args

    ys = np.asarray(ys, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.float64)
    slice_field = np.empty((len(ys), len(zs)), dtype=np.float32)

    for iy, y in enumerate(ys):
        for iz, z in enumerate(zs):
            p = np.array([x, y, z], dtype=np.float64)
            de, _ = mandelbulb_orbit(
                p,
                power=power,
                bailout=bailout,
                max_iter=max_iter,
                pi_mode=pi_mode,
                pi_base=pi_base,
                pi_alpha=pi_alpha,
                pi_mu=pi_mu,
            )
            slice_field[iy, iz] = de - iso

    return ix, slice_field


def _field_sample_gpu(bounds, res, power, bailout, max_iter, pi_mode, pi_base, pi_alpha, pi_mu):
    """GPU sampler using CuPy vectorized iterations."""
    assert _HAVE_CUPY and cp is not None

    dev = cp.cuda.Device()
    dev.use()
    props = cp.cuda.runtime.getDeviceProperties(dev.id)
    name = props.get("name", b"")
    if isinstance(name, bytes):
        try:
            name = name.decode("utf-8", "ignore")
        except Exception:
            name = str(name)
    free_bytes, total_bytes = cp.cuda.runtime.memGetInfo()
    print(
        f"  [GPU] Using device {dev.id}: {str(name).strip()}"
        f" (free {free_bytes / 1e9:.1f}/{total_bytes / 1e9:.1f} GB)"
    )

    setup_start = cp.cuda.Event()
    setup_end = cp.cuda.Event()
    compute_start = cp.cuda.Event()
    compute_end = cp.cuda.Event()

    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    setup_start.record()
    xs = cp.linspace(xmin, xmax, res, dtype=cp.float64)
    ys = cp.linspace(ymin, ymax, res, dtype=cp.float64)
    zs = cp.linspace(zmin, zmax, res, dtype=cp.float64)
    X, Y, Z = cp.meshgrid(xs, ys, zs, indexing='ij')
    setup_end.record()

    iso = 0.0025 * (xmax - xmin)

    z_x = X.copy()
    z_y = Y.copy()
    z_z = Z.copy()

    P_x = X
    P_y = Y
    P_z = Z

    dr = cp.ones_like(X, dtype=cp.float64)
    rr = cp.zeros_like(X, dtype=cp.float64)
    exit_iter = cp.zeros_like(X, dtype=cp.float64)
    pi_a = cp.full_like(X, pi_base, dtype=cp.float64)
    active = cp.ones_like(X, dtype=cp.bool_)
    escaped = cp.zeros_like(X, dtype=cp.bool_)

    bailout_val = float(bailout)
    power_val = float(power)
    log_denom = np.log(max(power_val, 1.001))

    print(f"  Sampling {res}^3 grid (GPU/CuPy)...")
    compute_start.record()

    for i in range(int(max_iter)):
        r = cp.sqrt(z_x * z_x + z_y * z_y + z_z * z_z)

        if pi_mode != 'fixed':
            pi_a = cp.where(active, pi_a - pi_alpha * r - pi_mu * (pi_a - pi_base), pi_a)

        mask_active = active

        r_safe = cp.maximum(r, 1e-12)
        theta = cp.where(mask_active, cp.arccos(cp.clip(z_z / r_safe, -1.0, 1.0)), 0.0)
        phi = cp.where(mask_active, cp.arctan2(z_y, z_x), 0.0)

        rp = cp.power(r_safe, power_val)
        dr = cp.where(mask_active, dr * power_val * cp.power(r_safe, power_val - 1.0) + 1.0, dr)

        thetap = theta * power_val
        phip = phi * power_val
        st = cp.sin(thetap)
        ct = cp.cos(thetap)
        cp_c = cp.cos(phip)
        sp_s = cp.sin(phip)

        new_x = rp * st * cp_c + P_x
        new_y = rp * st * sp_s + P_y
        new_z = rp * ct + P_z

        z_x = cp.where(mask_active, new_x, z_x)
        z_y = cp.where(mask_active, new_y, z_y)
        z_z = cp.where(mask_active, new_z, z_z)

        still_inside = r <= bailout_val
        escaped_now = mask_active & (~still_inside)

        exit_iter = cp.where(escaped_now, float(i + 1), exit_iter)
        rr = cp.where(escaped_now, r, rr)
        escaped = escaped | escaped_now
        active = still_inside & mask_active
        
        # Sync and report progress every few iterations to ensure GPU execution
        if (i + 1) % 3 == 0 or i == int(max_iter) - 1:
            active_count = int(cp.count_nonzero(active).item())
            print(f"    Iteration {i+1}/{int(max_iter)}: {active_count} points still active")
            if active_count == 0:
                break
        elif int(cp.count_nonzero(active).item()) == 0:
            break

    final_r = cp.where(escaped, rr, cp.sqrt(z_x * z_x + z_y * z_y + z_z * z_z))
    exit_iter = cp.where(escaped, exit_iter, float(max_iter))

    de = 0.5 * cp.log(cp.maximum(final_r, 1e-12)) * final_r / cp.maximum(dr, 1e-6)
    field = (de - iso).astype(cp.float32)

    compute_end.record()
    compute_end.synchronize()
    setup_ms = cp.cuda.get_elapsed_time(setup_start, setup_end)
    compute_ms = cp.cuda.get_elapsed_time(compute_start, compute_end)
    print(
        f"  [GPU] Setup {setup_ms / 1000.0:.3f}s · Kernel {compute_ms / 1000.0:.3f}s"
    )
    
    print(f"  [GPU] Transferring {field.nbytes / 1e6:.1f} MB from device to host...")
    transfer_start = cp.cuda.Event()
    transfer_end = cp.cuda.Event()
    transfer_start.record()
    field_cpu = cp.asnumpy(field)
    xs_cpu = cp.asnumpy(xs)
    ys_cpu = cp.asnumpy(ys)
    zs_cpu = cp.asnumpy(zs)
    transfer_end.record()
    transfer_end.synchronize()
    transfer_ms = cp.cuda.get_elapsed_time(transfer_start, transfer_end)
    print(f"  [GPU] Transfer complete in {transfer_ms / 1000.0:.3f}s")
    
    return field_cpu, (xs_cpu, ys_cpu, zs_cpu)

# ---------------------------
# Color fields
# ---------------------------
def color_from_orbit(orbit, mode='orbit'):
    """
    Return RGB (0..255) from orbit data using one of:
     - 'ni'    : smooth escape palette
     - 'orbit' : orbit traps (plane+shell)
     - 'angle' : hue from azimuth, sat from polar
    """
    if mode == 'ni':
        t = orbit['nu'] * 0.08
        rgb = iq_palette(t)
        return (np.clip(rgb * 255.0, 0, 255)).astype(np.uint8)

    elif mode == 'orbit':
        a = math.exp(-8.0 * orbit['trapPlane'])
        b = math.exp(-6.0 * orbit['trapShell'])
        t = np.clip(a + 0.5 * b, 0.0, 1.0)
        base = (1 - t) * np.array([0.1, 0.2, 0.5]) + t * np.array([0.9, 0.9, 0.2])
        ni  = (orbit['nu'] * 0.1) % 1.0
        rgb = base * (0.85 + 0.30 * ni)
        return (np.clip(rgb * 255.0, 0, 255)).astype(np.uint8)

    else:  # 'angle'
        z = orbit['lastZ']
        r = max(np.linalg.norm(z), 1e-6)
        phi   = math.atan2(z[1], z[0])                 # [-pi, pi]
        theta = math.acos(np.clip(z[2] / r, -1.0, 1.0))# [0, pi]
        h = (phi / (2.0 * math.pi)) % 1.0
        s = np.clip(theta / math.pi, 0.0, 1.0)
        v = 0.9
        rgb = hsv_to_rgb(h, s, v)
        rgb = rgb * (0.85 + 0.25 * ((orbit['nu']*0.15) % 1.0))
        return (np.clip(rgb * 255.0, 0, 255)).astype(np.uint8)

def iq_palette(t):
    # Inigo Quilez-like cosine palette: a + b*cos(2π(c t + d))
    a = np.array([0.50, 0.50, 0.50])
    b = np.array([0.50, 0.50, 0.50])
    c = np.array([1.00, 1.00, 1.00])
    d = np.array([0.00, 0.33, 0.67])
    return a + b * np.cos(2.0 * math.pi * (c * t + d))

def hsv_to_rgb(h, s, v):
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i % 6
    if   i == 0: r,g,b = v,t,p
    elif i == 1: r,g,b = q,v,p
    elif i == 2: r,g,b = p,v,t
    elif i == 3: r,g,b = p,q,v
    elif i == 4: r,g,b = t,p,v
    else:        r,g,b = v,p,q
    return np.array([r,g,b])

# ---------------------------
# Build mesh
# ---------------------------
def build_mesh(field, axes, color_mode, power, bailout, max_iter, pi_mode, pi_base, pi_alpha, pi_mu,
               norm_mode='euclid', norm_k=0.12, norm_r0=0.9, norm_sigma=0.35,
               orbit_shell=1.0, use_gpu_colors=False):
    """
    Build mesh from field with optional GPU-accelerated vertex coloring.
    
    Args:
        use_gpu_colors: If True and CuPy available, compute colors on GPU
        norm_mode: 'euclid' or 'adaptive'
        norm_k, norm_r0, norm_sigma: adaptive norm parameters
        orbit_shell: shell radius for orbit trap coloring
    """
    xs, ys, zs = axes
    # marching_cubes expects array ordered (z,y,x); ours is (x,y,z)
    # we transpose to (z, y, x)
    vol = np.transpose(field, (2,1,0))
    # spacing per axis
    dx = (xs[-1]-xs[0])/(len(xs)-1) if len(xs) > 1 else 1.0
    dy = (ys[-1]-ys[0])/(len(ys)-1) if len(ys) > 1 else 1.0
    dz = (zs[-1]-zs[0])/(len(zs)-1) if len(zs) > 1 else 1.0

    print("  Running marching cubes...")
    verts, faces, norms, _ = marching_cubes(vol, level=0.0, spacing=(dz, dy, dx))

    # marching_cubes returns vertices in (z,y,x) space rooted at (0, 0, 0)
    # We need to transform to world coordinates
    # verts are in index space, so we convert: (iz, iy, ix) -> (z, y, x)
    verts_world = np.zeros_like(verts)
    verts_world[:, 0] = xs[0] + verts[:, 2] * dx  # x from index 2
    verts_world[:, 1] = ys[0] + verts[:, 1] * dy  # y from index 1
    verts_world[:, 2] = zs[0] + verts[:, 0] * dz  # z from index 0

    print(f"  Generated mesh: {len(verts_world)} vertices, {len(faces)} faces")

    # Per-vertex colors
    if use_gpu_colors and _HAVE_CUPY:
        print("  Computing vertex colors (GPU)...")
        try:
            from gpu_vertex_colors import compute_vertex_colors_gpu
            color_mode_int = {'ni': 0, 'orbit': 1, 'angle': 2}.get(color_mode, 1)
            pi_mode_int = 0 if pi_mode == 'fixed' else 1
            norm_mode_int = 0 if norm_mode == 'euclid' else 1
            
            colors = compute_vertex_colors_gpu(
                verts_world,
                power=power,
                bailout=bailout,
                max_iter=max_iter,
                color_mode=color_mode_int,
                orbit_shell=orbit_shell,
                pi_mode=pi_mode_int,
                pi_base=pi_base,
                pi_alpha=pi_alpha,
                pi_mu=pi_mu,
                norm_mode=norm_mode_int,
                norm_k=norm_k,
                norm_r0=norm_r0,
                norm_sigma=norm_sigma
            )
            print(f"  GPU coloring complete for {len(verts_world)} vertices")
        except Exception as e:
            print(f"  GPU coloring failed ({e}), falling back to CPU")
            use_gpu_colors = False
    
    if not use_gpu_colors or not _HAVE_CUPY:
        print("  Computing vertex colors (CPU)...")
        colors = np.zeros((verts_world.shape[0], 3), dtype=np.uint8)
        for i, v in enumerate(verts_world):
            if i % 1000 == 0:
                print(f"    Progress: {i}/{len(verts_world)}")
            de, ob = mandelbulb_orbit(
                v, power=power, bailout=bailout, max_iter=max_iter,
                pi_mode=pi_mode, pi_base=pi_base, pi_alpha=pi_alpha, pi_mu=pi_mu,
                norm_mode=norm_mode, norm_k=norm_k, norm_r0=norm_r0, norm_sigma=norm_sigma
            )
            colors[i] = color_from_orbit(ob, mode=color_mode)
    
    return verts_world, faces, colors

def save_meshes(verts, faces, colors, outfile):
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    # STL (no color)
    stl_path = f"{outfile}.stl"
    mesh.export(stl_path)

    # PLY (vertex colors)
    mesh_vc = mesh.copy()
    mesh_vc.visual.vertex_colors = np.column_stack([colors, np.full(len(colors), 255, dtype=np.uint8)])  # Add alpha
    ply_path = f"{outfile}_color.ply"
    mesh_vc.export(ply_path)
    return stl_path, ply_path

# ---------------------------
# Main
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Procedural Mandelbulb mesh with Adaptive-π and custom norm.")
    ap.add_argument("--res", type=int, default=256, help="Grid resolution per axis (e.g., 128..512).")
    ap.add_argument("--power", type=float, default=8.0, help="Mandelbulb power.")
    ap.add_argument("--bailout", type=float, default=8.0, help="Bailout radius.")
    ap.add_argument("--max-iter", type=int, default=14, help="Max fractal iterations.")
    ap.add_argument("--bounds", type=float, nargs=6, default=[-1.6,1.6,-1.6,1.6,-1.6,1.6], help="Sampling bounds xmin xmax ymin ymax zmin zmax.")
    ap.add_argument("--color", choices=["ni","orbit","angle"], default="orbit", help="Color field.")
    ap.add_argument("--outfile", type=str, default="mandelbulb", help="Output base filename (no extension).")
    ap.add_argument("--gpu", action="store_true", help="Use CuPy GPU acceleration for field sampling.")
    ap.add_argument("--gpu-colors", action="store_true", help="Use GPU for vertex coloring (requires --gpu).")

    # πₐ params
    ap.add_argument("--pi-mode", choices=["fixed","adaptive"], default="fixed", help="Use fixed π or adaptive πₐ.")
    ap.add_argument("--pi-base", type=float, default=math.pi, help="Base π target.")
    ap.add_argument("--pi-alpha", type=float, default=0.0, help="Gradient-like term for πₐ.")
    ap.add_argument("--pi-mu", type=float, default=0.05, help="Decay to π base for πₐ.")
    
    # Adaptive norm params
    ap.add_argument("--norm-mode", choices=["euclid","adaptive"], default="euclid", help="Use Euclidean or adaptive norm.")
    ap.add_argument("--norm-kind", choices=["tanh_warp"], default="tanh_warp", help="Adaptive norm function.")
    ap.add_argument("--norm-k", type=float, default=0.12, help="Adaptive norm k parameter.")
    ap.add_argument("--norm-r0", type=float, default=0.9, help="Adaptive norm r0 parameter.")
    ap.add_argument("--norm-sigma", type=float, default=0.35, help="Adaptive norm sigma parameter.")
    ap.add_argument("--step-scale", type=float, default=1.0, help="DE safety scale (use 0.8 with adaptive norm).")
    ap.add_argument("--orbit-shell", type=float, default=1.0, help="Shell radius for orbit trap coloring.")

    args = ap.parse_args()

    print(f"[•] Mandelbulb Generator")
    print(f"    Power: {args.power}, Bailout: {args.bailout}, Max iterations: {args.max_iter}")
    print(f"    Resolution: {args.res}^3 voxels")
    print(f"    Color mode: {args.color}")
    print(f"    Pi mode: {args.pi_mode}")
    if args.pi_mode == 'adaptive':
        print(f"      Pi_base: {args.pi_base}, alpha: {args.pi_alpha}, mu: {args.pi_mu}")
    print(f"    Norm mode: {args.norm_mode}")
    if args.norm_mode == 'adaptive':
        print(f"      kind: {args.norm_kind}, k: {args.norm_k}, r0: {args.norm_r0}, sigma: {args.norm_sigma}")
        print(f"      step_scale: {args.step_scale}")
    
    print(f"\n[•] Sampling field @ res={args.res} in bounds={args.bounds} ...")
    field, axes = field_sample(
        tuple(args.bounds), args.res, args.power, args.bailout, args.max_iter,
        args.pi_mode, args.pi_base, args.pi_alpha, args.pi_mu, use_gpu=args.gpu
    )

    print("\n[•] Building mesh from field...")
    use_gpu_colors = args.gpu_colors and args.gpu and _HAVE_CUPY
    verts, faces, colors = build_mesh(
        field, axes, args.color, args.power, args.bailout, args.max_iter,
        args.pi_mode, args.pi_base, args.pi_alpha, args.pi_mu,
        norm_mode=args.norm_mode, norm_k=args.norm_k, norm_r0=args.norm_r0, 
        norm_sigma=args.norm_sigma, orbit_shell=args.orbit_shell,
        use_gpu_colors=use_gpu_colors
    )

    if len(verts) == 0:
        print("[!] No vertices generated. Try adjusting parameters or bounds.")
        return 1

    print(f"\n[•] Saving meshes...")
    stl_path, ply_path = save_meshes(verts, faces, colors, args.outfile)

    print(f"\n[*] Wrote: {stl_path}")
    print(f"[*] Wrote: {ply_path}")
    print("[*] Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())