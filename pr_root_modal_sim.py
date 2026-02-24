#!/usr/bin/env python3
"""PR-Root modal simulator (MVP).

Loads an analytic SDF AMA (list-based scene), voxelizes it, builds a mass–spring
lattice, and solves for the lowest natural frequencies.

It can optionally export a volume AMA with fields you can view/slice.

Example:
  python pr_root_modal_sim.py --ama square_tube_gyroid_PLA_mid.ama --extent 1.6 --res 28 --modes 12 --out-ama modes_mid.ama
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

# Allow running without installing package
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


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

        # Optional transforms
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


def main() -> int:
    ap = argparse.ArgumentParser(description="PR-root modal simulator (voxel + mass-spring)")
    ap.add_argument("--ama", required=True, help="Input analytic SDF .ama (list-based scene.json)")

    ap.add_argument("--extent", type=float, default=1.6, help="Voxelization half-extent in scene units")
    ap.add_argument("--res", type=int, default=28, help="Voxel grid resolution per axis (keep small: 20-40)")
    ap.add_argument("--modes", type=int, default=12, help="Number of modes to solve")

    ap.add_argument(
        "--unit-mm",
        type=float,
        default=25.0,
        help="Physical millimeters per 1.0 scene unit (for approximate Hz)",
    )

    ap.add_argument(
        "--bc",
        choices=["clamp_zmin", "free"],
        default="clamp_zmin",
        help="Boundary condition: clamp one end (recommended) or free-free",
    )
    ap.add_argument("--clamp-thickness", type=int, default=2, help="Clamp thickness in voxel layers")

    ap.add_argument("--out-ama", default=None, help="Optional output .ama with volume fields")

    args = ap.parse_args()

    from adaptivecad.sim.mass_spring import build_lattice_mk, solve_modes
    from adaptivecad.sim.materials import PLA
    from adaptivecad.sim.sdf_io import load_analytic_scene_list_from_ama
    from adaptivecad.sim.sdf_voxelize import voxel_grid, voxelize_scene

    scene_list = load_analytic_scene_list_from_ama(args.ama)
    scene = _build_scene(scene_list)

    extent = float(args.extent)
    res = int(args.res)
    if res < 10:
        raise SystemExit("--res too small")

    print(f"Voxelizing: extent={extent} res={res} ...")
    dist, solid = voxelize_scene(scene, extent=extent, res=res)

    # Physical scaling
    unit_m = float(args.unit_mm) * 1e-3
    voxel_size_m = (2.0 * extent * unit_m) / float(res)

    # Spring constant estimate: k ~ E*A/L with A=dx^2, L=dx => k ~ E*dx
    k_spring = float(PLA.youngs_modulus) * float(voxel_size_m)

    clamp_mask = None
    if args.bc == "clamp_zmin":
        _, _, Z = voxel_grid(extent, res)
        # clamp the minimum-z face layers
        zmin = float(Z.min())
        dz = float((2.0 * extent) / (res - 1)) if res > 1 else 0.0
        clamp_z = zmin + float(max(1, int(args.clamp_thickness))) * dz
        clamp_mask = Z <= clamp_z

    def connected_component_from_seeds(solid_mask: np.ndarray, seeds: np.ndarray) -> np.ndarray:
        """Return voxels in solid connected (6-neigh) to any seed voxel."""
        solid_mask = solid_mask.astype(bool)
        seeds = seeds.astype(bool)
        visited = np.zeros_like(solid_mask, dtype=bool)
        q: list[tuple[int, int, int]] = []

        seed_pts = np.argwhere(solid_mask & seeds)
        for y, x, z in seed_pts:
            visited[y, x, z] = True
            q.append((int(y), int(x), int(z)))

        # 6-neighborhood
        nbr = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        ny, nx, nz = solid_mask.shape
        head = 0
        while head < len(q):
            y, x, z = q[head]
            head += 1
            for dy, dx, dz_ in nbr:
                y2, x2, z2 = y + dy, x + dx, z + dz_
                if 0 <= y2 < ny and 0 <= x2 < nx and 0 <= z2 < nz:
                    if solid_mask[y2, x2, z2] and not visited[y2, x2, z2]:
                        visited[y2, x2, z2] = True
                        q.append((y2, x2, z2))
        return visited

    def largest_connected_component(solid_mask: np.ndarray) -> np.ndarray:
        solid_mask = solid_mask.astype(bool)
        visited = np.zeros_like(solid_mask, dtype=bool)
        best = np.zeros_like(solid_mask, dtype=bool)
        best_n = 0
        nbr = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        ny, nx, nz = solid_mask.shape

        for y0, x0, z0 in np.argwhere(solid_mask & (~visited)):
            q = [(int(y0), int(x0), int(z0))]
            visited[y0, x0, z0] = True
            comp = [(int(y0), int(x0), int(z0))]
            head = 0
            while head < len(q):
                y, x, z = q[head]
                head += 1
                for dy, dx, dz_ in nbr:
                    y2, x2, z2 = y + dy, x + dx, z + dz_
                    if 0 <= y2 < ny and 0 <= x2 < nx and 0 <= z2 < nz:
                        if solid_mask[y2, x2, z2] and not visited[y2, x2, z2]:
                            visited[y2, x2, z2] = True
                            q.append((y2, x2, z2))
                            comp.append((y2, x2, z2))
            if len(comp) > best_n:
                best_n = len(comp)
                best[:] = False
                for y, x, z in comp:
                    best[y, x, z] = True
        return best

    # Remove disconnected "floating islands" to avoid many 0-Hz rigid modes.
    if clamp_mask is not None:
        keep_solid = connected_component_from_seeds(solid, clamp_mask)
        if int(keep_solid.sum()) == 0:
            keep_solid = largest_connected_component(solid)
    else:
        keep_solid = largest_connected_component(solid)

    if int(keep_solid.sum()) != int(solid.sum()):
        print(f"Keeping connected solid: {int(keep_solid.sum())}/{int(solid.sum())} voxels")
        solid = keep_solid
        # Mark removed regions as outside
        dist = np.where(solid, dist, np.float32(+1.0))

    print(f"Building lattice: solid_voxels={int(solid.sum())} ...")
    M, K, inv, idx_map = build_lattice_mk(
        solid,
        voxel_size_m=voxel_size_m,
        density=float(PLA.density),
        k_spring=k_spring,
        clamp_mask=clamp_mask,
    )

    print(f"Solving modes: dof={M.shape[0]} modes={int(args.modes)} ...")
    freq_hz, modes = solve_modes(M, K, num_modes=int(args.modes))

    print("Frequencies (Hz):")
    for i, f in enumerate(freq_hz[: int(args.modes)]):
        print(f"  mode {i:02d}: {float(f):.2f} Hz")

    if args.out_ama:
        # Export a volume AMA containing:
        # - solid mask (0/1)
        # - dist field
        # - mode0 magnitude (on the solid voxels)
        from adaptivecad.sim.export_volume_ama import export_volume_fields_as_ama

        # Reinflate mode0 onto the full grid (only for visualization)
        mode0 = np.zeros((res, res, res, 3), dtype=np.float32)
        pts = np.argwhere(solid)

        m0 = modes[:, 0]
        for y, x, z in pts:
            vid = int(idx_map[int(y), int(x), int(z)])
            if vid < 0:
                continue
            for c in range(3):
                full_d = 3 * vid + c
                red = int(inv[full_d])
                mode0[int(y), int(x), int(z), c] = float(m0[red]) if red >= 0 else 0.0

        mag = np.linalg.norm(mode0, axis=3).astype(np.float32)
        solid_f = solid.astype(np.float32)

        data = export_volume_fields_as_ama(
            fields={
                "solid": solid_f,
                "dist": dist.astype(np.float32),
                "mode0_mag": mag,
            },
            enabled="mode0_mag",
            scale=2.0 * extent,
            units="mm",
            generator="pr_root_modal_sim",
        )
        with open(args.out_ama, "wb") as fp:
            fp.write(data)
        print(f"Wrote: {args.out_ama}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
