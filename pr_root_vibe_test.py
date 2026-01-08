#!/usr/bin/env python3
"""PR-Root vibration tester (baseline vs candidate).

This computes a simple harmonic forced-response transmissibility curve using the
PR-root voxel + mass-spring approximation.

Definition used here:
- Clamp the z-min face (Dirichlet) by removing DOFs.
- Apply a unit Z-force distributed across an input band near z-min.
- Measure RMS displacement magnitude in an output band near z-max.
- Transmissibility T(f) = RMS_out / RMS_in.

Outputs:
- CSV with columns: f_hz, T_baseline, T_candidate, ratio, ratio_db
- JSON with metadata + arrays (friendly for Manim)

Example:
  python pr_root_vibe_test.py --baseline square_tube_plain_PLA_mid.ama --candidate square_tube_gyroid_PLA_mid.ama --extent 1.6 --res 24
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import asdict, dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


# Allow running without installing package
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


@dataclass(frozen=True)
class BandSpec:
    extent: float
    res: int
    clamp_layers: int
    in_layers: int
    out_layers: int


def _build_scene(scene_list: list[dict[str, object]]):
    from adaptivecad.aacore.sdf import Prim, Scene

    def op_from_json(v: object) -> str:
        if isinstance(v, str):
            t = v.strip().lower()
            if t in ("subtract", "sub"):
                return "subtract"
            if t in ("intersect", "and"):
                return "intersect"
            return "solid"
        try:
            i = int(v or 0)
        except Exception:
            i = 0
        return "subtract" if i == 1 else ("intersect" if i == 2 else "solid")

    scene = Scene()
    scene.prims.clear()

    for entry in scene_list:
        kind = str(entry.get("kind", "")).strip().lower()
        if not kind:
            continue
        params = entry.get("params")
        if not isinstance(params, list):
            params = [0.5, 0.0, 0.0, 0.0]
        beta = float(entry.get("beta", 0.0) or 0.0)
        op = op_from_json(entry.get("op", 0))

        color = entry.get("color")
        if isinstance(color, list) and len(color) >= 3:
            col = (float(color[0]), float(color[1]), float(color[2]))
        else:
            col = (0.85, 0.75, 0.55)

        pr = Prim(kind, [float(x) for x in params], beta=beta, op=op, color=col)

        pos = entry.get("pos")
        euler = entry.get("euler")
        scale = entry.get("scale")

        def f3(x):
            return [float(x[0]), float(x[1]), float(x[2])]

        try:
            pr.set_transform(
                pos=f3(pos) if isinstance(pos, list) and len(pos) >= 3 else None,
                euler=f3(euler) if isinstance(euler, list) and len(euler) >= 3 else None,
                scale=f3(scale) if isinstance(scale, list) and len(scale) >= 3 else None,
            )
        except Exception:
            pass

        scene.add(pr)

    return scene


def _voxel_grid(extent: float, res: int):
    lin = np.linspace(-float(extent), float(extent), int(res), dtype=np.float32)
    X, Y, Z = np.meshgrid(lin, lin, lin, indexing="xy")
    return X, Y, Z


def _largest_connected_component(solid: np.ndarray) -> np.ndarray:
    solid = solid.astype(bool)
    visited = np.zeros_like(solid, dtype=bool)
    best = np.zeros_like(solid, dtype=bool)
    best_n = 0
    nbr = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    ny, nx, nz = solid.shape

    for y0, x0, z0 in np.argwhere(solid & (~visited)):
        q = [(int(y0), int(x0), int(z0))]
        visited[y0, x0, z0] = True
        comp = [(int(y0), int(x0), int(z0))]
        head = 0
        while head < len(q):
            y, x, z = q[head]
            head += 1
            for dy, dx, dz in nbr:
                y2, x2, z2 = y + dy, x + dx, z + dz
                if 0 <= y2 < ny and 0 <= x2 < nx and 0 <= z2 < nz:
                    if solid[y2, x2, z2] and not visited[y2, x2, z2]:
                        visited[y2, x2, z2] = True
                        q.append((y2, x2, z2))
                        comp.append((y2, x2, z2))
        if len(comp) > best_n:
            best_n = len(comp)
            best[:] = False
            for y, x, z in comp:
                best[y, x, z] = True
    return best


def _build_system(
    ama_path: str,
    *,
    extent: float,
    res: int,
    unit_mm: float,
    clamp_layers: int,
):
    from adaptivecad.sim.materials import PLA
    from adaptivecad.sim.sdf_io import load_analytic_scene_list_from_ama
    from adaptivecad.sim.sdf_voxelize import voxelize_scene
    from adaptivecad.sim.mass_spring import build_lattice_mk

    scene_list = load_analytic_scene_list_from_ama(ama_path)
    scene = _build_scene(scene_list)

    dist, solid = voxelize_scene(scene, extent=float(extent), res=int(res))

    # Keep largest connected component (helps with boolean-perforated parts)
    solid2 = _largest_connected_component(solid)
    if int(solid2.sum()) != int(solid.sum()):
        solid = solid2
        dist = np.where(solid, dist, np.float32(+1.0))

    X, Y, Z = _voxel_grid(extent, res)

    # Physical scaling (approx)
    unit_m = float(unit_mm) * 1e-3
    voxel_size_m = (2.0 * float(extent) * unit_m) / float(res)

    # Spring constant estimate: k ~ E*A/L, with A~dx^2, L~dx => k ~ E*dx
    k_spring = float(PLA.youngs_modulus) * float(voxel_size_m)

    # Clamp z-min layers
    zmin = float(Z.min())
    dz = float((2.0 * float(extent)) / (res - 1)) if res > 1 else 0.0
    clamp_z = zmin + float(max(1, int(clamp_layers))) * dz
    clamp_mask = Z <= clamp_z

    M, K, inv, idx_map = build_lattice_mk(
        solid,
        voxel_size_m=voxel_size_m,
        density=float(PLA.density),
        k_spring=k_spring,
        clamp_mask=clamp_mask,
    )

    return {
        "dist": dist,
        "solid": solid,
        "X": X,
        "Y": Y,
        "Z": Z,
        "M": M,
        "K": K,
        "inv": inv,
        "idx_map": idx_map,
        "voxel_size_m": voxel_size_m,
    }


def _region_dofs(solid: np.ndarray, idx_map: np.ndarray, inv: np.ndarray, mask: np.ndarray) -> np.ndarray:
    pts = np.argwhere(solid & mask)
    dofs: list[int] = []
    for y, x, z in pts:
        vid = int(idx_map[int(y), int(x), int(z)])
        if vid < 0:
            continue
        for c in range(3):
            red = int(inv[3 * vid + c])
            if red >= 0:
                dofs.append(red)
    if not dofs:
        raise ValueError("Region had no free DOFs (check extent/res/bands)")
    return np.array(sorted(set(dofs)), dtype=np.int32)


def _rms_mag(u: np.ndarray, dofs: np.ndarray) -> float:
    # u is reduced DOF vector (complex). dofs selects components.
    sel = u[dofs]
    return float(np.sqrt(np.mean(np.abs(sel) ** 2)))


def transmissibility_curve(
    sysA,
    sysB,
    *,
    band: BandSpec,
    f0: float,
    f1: float,
    n: int,
    eta: float,
) -> dict[str, object]:
    Z = sysA["Z"]
    extent = float(band.extent)
    res = int(band.res)

    zmin = float(Z.min())
    zmax = float(Z.max())
    dz = float((2.0 * extent) / (res - 1)) if res > 1 else 0.0

    clamp_z = zmin + float(max(1, band.clamp_layers)) * dz
    in_z0 = clamp_z + 1.0 * dz
    in_z1 = in_z0 + float(max(1, band.in_layers)) * dz
    out_z1 = zmax - 1.0 * dz
    out_z0 = out_z1 - float(max(1, band.out_layers)) * dz

    in_mask = (Z >= in_z0) & (Z <= in_z1)
    out_mask = (Z >= out_z0) & (Z <= out_z1)

    inA = _region_dofs(sysA["solid"], sysA["idx_map"], sysA["inv"], in_mask)
    outA = _region_dofs(sysA["solid"], sysA["idx_map"], sysA["inv"], out_mask)

    inB = _region_dofs(sysB["solid"], sysB["idx_map"], sysB["inv"], in_mask)
    outB = _region_dofs(sysB["solid"], sysB["idx_map"], sysB["inv"], out_mask)

    def solve_T(M: sp.csr_matrix, K: sp.csr_matrix, in_dofs: np.ndarray, out_dofs: np.ndarray):
        # Unit Z-force distributed across input DOFs (we don't know which are Z only after reduction)
        # so apply equal force to all DOFs in the input region.
        fvec = np.zeros((M.shape[0],), dtype=np.complex128)
        fvec[in_dofs] = 1.0 / float(len(in_dofs))

        freqs = np.linspace(float(f0), float(f1), int(n), dtype=np.float64)
        Tin = np.zeros_like(freqs)
        Tout = np.zeros_like(freqs)

        Kd = K.astype(np.complex128) * (1.0 + 1j * float(eta))
        M2 = M.astype(np.complex128)

        for i, f_hz in enumerate(freqs):
            w = 2.0 * math.pi * float(f_hz)
            A = Kd - (w * w) * M2
            u = spla.spsolve(A, fvec)
            Tin[i] = _rms_mag(u, in_dofs)
            Tout[i] = _rms_mag(u, out_dofs)

        T = Tout / np.maximum(Tin, 1e-18)
        return freqs, T

    fA, TA = solve_T(sysA["M"], sysA["K"], inA, outA)
    fB, TB = solve_T(sysB["M"], sysB["K"], inB, outB)

    ratio = TB / np.maximum(TA, 1e-18)
    ratio_db = 20.0 * np.log10(np.maximum(ratio, 1e-18))

    return {
        "freq_hz": fA.tolist(),
        "T_baseline": TA.tolist(),
        "T_candidate": TB.tolist(),
        "ratio": ratio.tolist(),
        "ratio_db": ratio_db.tolist(),
        "bands": {
            "in": [float(in_z0), float(in_z1)],
            "out": [float(out_z0), float(out_z1)],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="PR-root vibration tester (transmissibility)")
    ap.add_argument("--baseline", required=True, help="Baseline analytic SDF .ama")
    ap.add_argument("--candidate", required=True, help="Candidate analytic SDF .ama")

    ap.add_argument("--extent", type=float, default=1.6)
    ap.add_argument("--res", type=int, default=22)
    ap.add_argument("--unit-mm", type=float, default=25.0)

    ap.add_argument("--clamp-layers", type=int, default=2)
    ap.add_argument("--in-layers", type=int, default=2)
    ap.add_argument("--out-layers", type=int, default=2)

    ap.add_argument("--f0", type=float, default=50.0)
    ap.add_argument("--f1", type=float, default=3000.0)
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--eta", type=float, default=0.05, help="Loss factor damping (dimensionless)")

    ap.add_argument("--out-csv", default="vibe_test.csv")
    ap.add_argument("--out-json", default="vibe_test.json")

    args = ap.parse_args()

    band = BandSpec(
        extent=float(args.extent),
        res=int(args.res),
        clamp_layers=int(args.clamp_layers),
        in_layers=int(args.in_layers),
        out_layers=int(args.out_layers),
    )

    print("Building baseline system...")
    sysA = _build_system(
        args.baseline,
        extent=band.extent,
        res=band.res,
        unit_mm=float(args.unit_mm),
        clamp_layers=band.clamp_layers,
    )
    print("Building candidate system...")
    sysB = _build_system(
        args.candidate,
        extent=band.extent,
        res=band.res,
        unit_mm=float(args.unit_mm),
        clamp_layers=band.clamp_layers,
    )

    print("Solving frequency response...")
    curve = transmissibility_curve(
        sysA,
        sysB,
        band=band,
        f0=float(args.f0),
        f1=float(args.f1),
        n=int(args.n),
        eta=float(args.eta),
    )

    # Write CSV
    with open(args.out_csv, "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["f_hz", "T_baseline", "T_candidate", "ratio", "ratio_db"])
        for f, a, b, r, db in zip(
            curve["freq_hz"],
            curve["T_baseline"],
            curve["T_candidate"],
            curve["ratio"],
            curve["ratio_db"],
            strict=True,
        ):
            w.writerow([f, a, b, r, db])

    meta = {
        "baseline": str(args.baseline),
        "candidate": str(args.candidate),
        "band": asdict(band),
        "unit_mm": float(args.unit_mm),
        "f0": float(args.f0),
        "f1": float(args.f1),
        "n": int(args.n),
        "eta": float(args.eta),
    }

    out = {"meta": meta, "curve": curve}
    with open(args.out_json, "w", encoding="utf-8") as fp:
        json.dump(out, fp, indent=2)

    # Quick headline
    ratio_db = np.array(curve["ratio_db"], dtype=np.float64)
    best = float(ratio_db.min())
    worst = float(ratio_db.max())
    print(f"Wrote: {args.out_csv}")
    print(f"Wrote: {args.out_json}")
    print(f"Candidate vs baseline ratio_db range: [{best:.2f}, {worst:.2f}] dB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
