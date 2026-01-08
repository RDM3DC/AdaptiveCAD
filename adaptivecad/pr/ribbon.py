"""
PR Ribbon — twisted band swept along a centerline with phase twist.

Mathematical model:
  C(s) = centerline curve, s ∈ [0, 2π]
  (T, N, B) = Bishop frame (parallel-transported)
  φ(s) = phase twist angle = φ₀ + m·s
  S(s, u) = C(s) + u·(cos(φ(s))·N(s) + sin(φ(s))·B(s))

This generates Möbius-like and twisted torus-band surfaces.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Literal


@dataclass
class PRRibbonConfig:
    """Configuration for a PR twisted ribbon."""
    
    # Centerline type
    centerline: Literal["circle", "tilted_circle", "lemniscate", "custom"] = "circle"
    
    # Circle/ellipse params
    radius: float = 1.0
    tilt_amplitude: float = 0.3  # z(s) = tilt_amplitude * sin(tilt_freq * s)
    tilt_freq: float = 1.0
    
    # Ribbon width
    width: float = 0.4
    
    # Phase twist
    twist_offset: float = 0.0      # φ₀
    twist_windings: float = 1.0    # m (number of full twists around loop)
    
    # Mesh resolution
    n_s: int = 128  # samples along centerline
    n_u: int = 16   # samples across ribbon width


def _compute_bishop_frame(curve: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute Bishop (parallel-transport) frame along a closed curve.
    
    Args:
        curve: (N, 3) array of curve points
        
    Returns:
        T, N, B: each (N, 3) — tangent, normal, binormal
    """
    N = len(curve)
    eps = 1e-9
    
    # Tangent via central differences (closed curve)
    T = np.zeros_like(curve)
    for i in range(N):
        T[i] = curve[(i + 1) % N] - curve[(i - 1) % N]
    T_norm = np.linalg.norm(T, axis=1, keepdims=True) + eps
    T = T / T_norm
    
    # Initialize first normal perpendicular to T[0]
    t0 = T[0]
    # Find a vector not parallel to t0
    if abs(t0[0]) < 0.9:
        v = np.array([1.0, 0.0, 0.0])
    else:
        v = np.array([0.0, 1.0, 0.0])
    n0 = np.cross(t0, v)
    n0 /= np.linalg.norm(n0) + eps
    
    # Parallel transport around the curve
    Nvec = np.zeros_like(curve)
    Bvec = np.zeros_like(curve)
    Nvec[0] = n0
    Bvec[0] = np.cross(T[0], n0)
    
    for i in range(1, N):
        # Rotation from T[i-1] to T[i]
        t_prev = T[i - 1]
        t_curr = T[i]
        
        # Rodrigues rotation
        axis = np.cross(t_prev, t_curr)
        axis_norm = np.linalg.norm(axis)
        if axis_norm > eps:
            axis /= axis_norm
            cos_theta = np.clip(np.dot(t_prev, t_curr), -1, 1)
            theta = np.arccos(cos_theta)
            # Rotate N[i-1] around axis by theta
            n_prev = Nvec[i - 1]
            Nvec[i] = (
                n_prev * np.cos(theta)
                + np.cross(axis, n_prev) * np.sin(theta)
                + axis * np.dot(axis, n_prev) * (1 - np.cos(theta))
            )
        else:
            Nvec[i] = Nvec[i - 1]
        
        Nvec[i] /= np.linalg.norm(Nvec[i]) + eps
        Bvec[i] = np.cross(T[i], Nvec[i])
        Bvec[i] /= np.linalg.norm(Bvec[i]) + eps
    
    return T, Nvec, Bvec


def generate_centerline(cfg: PRRibbonConfig) -> np.ndarray:
    """Generate the centerline curve C(s)."""
    s = np.linspace(0, 2 * np.pi, cfg.n_s, endpoint=False)
    
    if cfg.centerline == "circle":
        x = cfg.radius * np.cos(s)
        y = cfg.radius * np.sin(s)
        z = np.zeros_like(s)
    elif cfg.centerline == "tilted_circle":
        x = cfg.radius * np.cos(s)
        y = cfg.radius * np.sin(s)
        z = cfg.tilt_amplitude * np.sin(cfg.tilt_freq * s)
    elif cfg.centerline == "lemniscate":
        # Figure-8 / lemniscate of Bernoulli (in 3D with tilt)
        denom = 1 + np.sin(s) ** 2 + 1e-9
        x = cfg.radius * np.cos(s) / denom
        y = cfg.radius * np.sin(s) * np.cos(s) / denom
        z = cfg.tilt_amplitude * np.sin(2 * s)
    else:
        # Default to circle
        x = cfg.radius * np.cos(s)
        y = cfg.radius * np.sin(s)
        z = np.zeros_like(s)
    
    return np.stack([x, y, z], axis=-1)


def generate_ribbon_mesh(cfg: PRRibbonConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate a twisted ribbon mesh.
    
    Returns:
        vertices: (n_s * n_u, 3)
        faces: (M, 3) triangle indices
        phase: (n_s * n_u,) phase value at each vertex
    """
    # Centerline
    C = generate_centerline(cfg)
    n_s = cfg.n_s
    n_u = cfg.n_u
    
    # Bishop frame
    T, N, B = _compute_bishop_frame(C)
    
    # Parameter grids
    s_vals = np.linspace(0, 2 * np.pi, n_s, endpoint=False)
    u_vals = np.linspace(-cfg.width, cfg.width, n_u)
    
    # Phase twist: φ(s) = φ₀ + m·s
    phi = cfg.twist_offset + cfg.twist_windings * s_vals
    
    # Build surface S(s, u) = C(s) + u·(cos(φ)·N + sin(φ)·B)
    vertices = []
    phase_out = []
    
    for i, si in enumerate(s_vals):
        cos_phi = np.cos(phi[i])
        sin_phi = np.sin(phi[i])
        frame_dir = cos_phi * N[i] + sin_phi * B[i]
        
        for j, uj in enumerate(u_vals):
            pt = C[i] + uj * frame_dir
            vertices.append(pt)
            phase_out.append(phi[i])
    
    vertices = np.array(vertices, dtype=np.float32)
    phase_out = np.array(phase_out, dtype=np.float32)
    
    # Build faces (quad grid → triangles)
    faces = []
    for i in range(n_s):
        i_next = (i + 1) % n_s
        for j in range(n_u - 1):
            # Quad corners
            v00 = i * n_u + j
            v01 = i * n_u + j + 1
            v10 = i_next * n_u + j
            v11 = i_next * n_u + j + 1
            
            # Two triangles per quad
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])
    
    faces = np.array(faces, dtype=np.int32)
    
    return vertices, faces, phase_out


def export_ribbon_as_ama(
    cfg: PRRibbonConfig,
    filename: str = "pr_ribbon.ama",
    scale: float = 1.0,
    units: str = "mm",
) -> bytes:
    """
    Export a PR ribbon as an .ama archive.
    
    The archive contains:
      - mesh/ribbon.stl (tessellated surface)
      - fields/phase.npy (phase values per vertex)
      - analytic/scene.json (layer + colormap config)
      - analytic/manifest.json (field registry)
      - meta/provenance.json
    """
    import io
    import json
    import zipfile
    import hashlib
    from datetime import datetime, timezone
    
    # Generate mesh
    verts, faces, phase = generate_ribbon_mesh(cfg)
    verts = verts * scale
    
    # Build STL
    try:
        import trimesh
        mesh = trimesh.Trimesh(vertices=verts, faces=faces)
        stl_io = io.BytesIO()
        mesh.export(stl_io, file_type="stl")
        stl_bytes = stl_io.getvalue()
    except ImportError:
        # Fallback: write ASCII STL manually
        lines = ["solid ribbon"]
        for f in faces:
            v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            n_len = np.linalg.norm(n)
            if n_len > 1e-9:
                n = n / n_len
            else:
                n = np.array([0, 0, 1])
            lines.append(f"  facet normal {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
            lines.append("    outer loop")
            lines.append(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}")
            lines.append(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}")
            lines.append(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}")
            lines.append("    endloop")
            lines.append("  endfacet")
        lines.append("endsolid ribbon")
        stl_bytes = "\n".join(lines).encode("utf-8")
    
    # Phase field as 2D grid for visualization (n_s x n_u)
    phase_2d = phase.reshape((cfg.n_s, cfg.n_u))
    
    # Scene JSON
    scene = {
        "layers": [
            {"name": "phase", "field": "fields/phase.npy", "colormap": "plasma", "enabled": True},
        ],
        "mesh": "mesh/ribbon.stl",
        "render": {"wireframe": False, "shading": "smooth"},
    }
    
    # Manifest
    manifest = {
        "fields": {
            "phase": {"shape": list(phase_2d.shape), "dtype": "float32", "path": "fields/phase.npy"},
        },
        "config": {
            "centerline": cfg.centerline,
            "radius": cfg.radius,
            "tilt_amplitude": cfg.tilt_amplitude,
            "tilt_freq": cfg.tilt_freq,
            "width": cfg.width,
            "twist_offset": cfg.twist_offset,
            "twist_windings": cfg.twist_windings,
            "n_s": cfg.n_s,
            "n_u": cfg.n_u,
        },
    }
    
    # Provenance
    provenance = {
        "generator": "adaptivecad.pr.ribbon",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units": units,
        "scale": scale,
        "checksum_phase": hashlib.sha256(phase_2d.tobytes()).hexdigest()[:16],
    }
    
    # Pack into zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mesh/ribbon.stl", stl_bytes)
        
        phase_io = io.BytesIO()
        np.save(phase_io, phase_2d)
        zf.writestr("fields/phase.npy", phase_io.getvalue())
        
        zf.writestr("analytic/scene.json", json.dumps(scene, indent=2))
        zf.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("meta/provenance.json", json.dumps(provenance, indent=2))
    
    return buf.getvalue()


def save_ribbon_ama(
    cfg: PRRibbonConfig,
    path: str,
    scale: float = 1.0,
    units: str = "mm",
) -> str:
    """Save ribbon .ama to disk and return the path."""
    data = export_ribbon_as_ama(cfg, scale=scale, units=units)
    with open(path, "wb") as f:
        f.write(data)
    return path


__all__ = [
    "PRRibbonConfig",
    "generate_centerline",
    "generate_ribbon_mesh",
    "export_ribbon_as_ama",
    "save_ribbon_ama",
]
