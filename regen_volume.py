#!/usr/bin/env python3
"""Quick script to regenerate volume with better isosurface."""
import sys
sys.path.insert(0, r"C:\Users\RDM3D\AdaptCADKickstarter\AdaptiveCAD")

from adaptivecad.pr.volume import PRVolumeConfig, relax_phase_volume, save_volume_ama, extract_isosurface
import numpy as np

cfg = PRVolumeConfig(
    size=32,
    steps=80,
    dt=0.15,
    diffusion=0.35,
    coupling=0.25,
    coupling_mode="geom_target",
    geom_mode="smooth_noise",
    geom_smooth_iters=4,
    phase_space="unwrapped",
    iso_level=0.0,
    seed=42,
)

print(f"Running 3D phase relaxation ({cfg.size}³)...")
metrics, state = relax_phase_volume(cfg)

phi = state.phi if state.phi.ndim == 3 else state.phi[..., 0]
print(f"φ range: [{phi.min():.3f}, {phi.max():.3f}], mean={phi.mean():.3f}")

# Try different iso levels to find one with good geometry
for iso in [0.0, 0.1, -0.1, 0.2, -0.2, phi.mean()]:
    verts, faces = extract_isosurface(phi, level=iso, scale=15.0)
    print(f"  iso={iso:.2f}: {len(verts)} verts, {len(faces)} faces")

# Use the mean as iso level for best coverage
best_iso = float(phi.mean())
print(f"\nUsing iso={best_iso:.3f} for export")

path = save_volume_ama(state, cfg, r"C:\Users\RDM3D\AdaptCADKickstarter\AdaptiveCAD\pr_volume_good.ama", 
                       iso_level=best_iso, scale=15.0, units="mm")
print(f"Saved: {path}")
