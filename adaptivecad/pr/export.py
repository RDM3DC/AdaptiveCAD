"""Export Phase-Resolved fields as 3D geometry (STL, OBJ, etc.)."""

from __future__ import annotations

from io import BytesIO
import json
import hashlib
from datetime import datetime, timezone
import sys
from pathlib import Path
import tempfile
from typing import Any
import zipfile
import json
import zipfile

import numpy as np

from .derived import compute_derived_fields


def _write_stl_binary(vertices: np.ndarray, triangles: np.ndarray) -> bytes:
    """Write STL binary format.

    Args:
        vertices: (V, 3) float array of vertex positions
        triangles: (T, 3) int array of triangle indices

    Returns:
        Binary STL data
    """

    buf = BytesIO()

    # 80-byte header
    header = b"Phase-Resolved heightmap" + b"\x00" * (80 - len(b"Phase-Resolved heightmap"))
    buf.write(header)

    # number of triangles (4 bytes, little-endian)
    buf.write(len(triangles).to_bytes(4, byteorder="little"))

    for tri in triangles:
        v0, v1, v2 = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]

        # normal
        e1 = v1 - v0
        e2 = v2 - v0
        normal = np.cross(e1, e2)
        norm = np.linalg.norm(normal)
        if norm > 1e-9:
            normal = normal / norm
        else:
            normal = np.array([0.0, 0.0, 1.0])

        buf.write(normal.astype(np.float32).tobytes())
        buf.write(v0.astype(np.float32).tobytes())
        buf.write(v1.astype(np.float32).tobytes())
        buf.write(v2.astype(np.float32).tobytes())

        # attribute byte count
        buf.write(b"\x00\x00")

    return buf.getvalue()


def export_phase_field_as_heightmap_stl(
    phi: np.ndarray,
    scale_xy: float = 1.0,
    scale_z: float = 1.0,
) -> bytes:
    """Convert a 2D phase field to a 3D heightmap and export as STL.

    Args:
        phi: (N, N) or (N, N, D) phase field (uses first component if multi-channel)
        scale_xy: horizontal scale (meters per grid cell)
        scale_z: vertical scale (height multiplier)

    Returns:
        Binary STL data
    """

    if phi.ndim == 3:
        phi_2d = phi[:, :, 0]
    else:
        phi_2d = phi

    N = phi_2d.shape[0]

    # Normalize and scale height
    h_min = float(np.min(phi_2d))
    h_max = float(np.max(phi_2d))
    h_range = h_max - h_min if h_max > h_min else 1.0
    h_normalized = (phi_2d - h_min) / h_range
    h_scaled = h_normalized * scale_z

    # Build vertices: (i, j) -> (i*dx, j*dy, h[i,j])
    vertices_list = []
    for i in range(N):
        for j in range(N):
            x = float(i) * scale_xy
            y = float(j) * scale_xy
            z = float(h_scaled[i, j])
            vertices_list.append([x, y, z])

    vertices = np.array(vertices_list, dtype=np.float32)

    # Build triangles: for each grid cell (i,j), add two triangles
    triangles_list = []
    for i in range(N - 1):
        for j in range(N - 1):
            # Vertex indices for the 2x2 grid cell
            v00 = i * N + j
            v01 = i * N + (j + 1)
            v10 = (i + 1) * N + j
            v11 = (i + 1) * N + (j + 1)

            # Two triangles per cell
            triangles_list.append([v00, v01, v10])
            triangles_list.append([v01, v11, v10])

    triangles = np.array(triangles_list, dtype=np.uint32)

    return _write_stl_binary(vertices, triangles)


def export_phase_field_as_obj(
    phi: np.ndarray,
    scale_xy: float = 1.0,
    scale_z: float = 1.0,
) -> str:
    """Convert a 2D phase field to an OBJ (Wavefront) file.

    Args:
        phi: (N, N) or (N, N, D) phase field
        scale_xy: horizontal scale
        scale_z: vertical scale

    Returns:
        OBJ file as string
    """

    if phi.ndim == 3:
        phi_2d = phi[:, :, 0]
    else:
        phi_2d = phi

    N = phi_2d.shape[0]

    # Normalize and scale height
    h_min = float(np.min(phi_2d))
    h_max = float(np.max(phi_2d))
    h_range = h_max - h_min if h_max > h_min else 1.0
    h_normalized = (phi_2d - h_min) / h_range
    h_scaled = h_normalized * scale_z

    lines = [
        "# Phase-Resolved heightmap",
        f"# Size: {N}x{N}",
        "",
    ]

    # Vertices
    for i in range(N):
        for j in range(N):
            x = float(i) * scale_xy
            y = float(j) * scale_xy
            z = float(h_scaled[i, j])
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")

    lines.append("")

    # Faces (1-indexed in OBJ)
    for i in range(N - 1):
        for j in range(N - 1):
            v00 = i * N + j + 1
            v01 = i * N + (j + 1) + 1
            v10 = (i + 1) * N + j + 1
            v11 = (i + 1) * N + (j + 1) + 1

            lines.append(f"f {v00} {v01} {v10}")
            lines.append(f"f {v01} {v11} {v10}")

    return "\n".join(lines)


def export_phase_field_as_ama(
    phi: np.ndarray,
    *,
    falsifier_residual: np.ndarray | None = None,
    cosmo_meta: dict[str, Any] | None = None,
    scale_xy: float = 1.0,
    scale_z: float = 1.0,
    filename: str = "pr_phase_field.ama",
    params: dict[str, Any] | None = None,
    units: str = "mm",
    defl: float = 0.05,
) -> bytes:
    """Export a PR phase field using the AdaptiveCAD kernel + AMA format.

    This uses pythonocc-core (OCC) as the geometry kernel:
    1) Convert the field to a heightmap STL (mesh)
    2) Load the STL into a TopoDS_Shape via OCC
    3) Write an .ama archive via adaptivecad.io.ama_writer

    If OCC is unavailable, this falls back to an analytic-only AMA payload
    (zip with fields + analytic metadata) which is sufficient for the
    πₐ-pure analytic viewport tooling.

    The resulting AMA will include:
    - meta/manifest.json
    - model/graph.json
    - geom/s000.brep (TopoDS_Shape serialized)
    - fields/f000_field.npy (phase field values)
    """

    def _stable_json_bytes(obj: Any) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _build_cosmo_meta_default() -> dict[str, Any]:
        # Best-effort provenance; callers can override by passing cosmo_meta.
        return {
            "ama_version": "0.1",
            "model": {
                "name": "AdaptiveCAD-PR",
                "pr_root": {
                    "pi_a": "adaptive",
                    "invariants": ["2pi_a", "w", "b", "C"],
                },
            },
            "run": {
                "solver": "adaptivecad.pr.export_phase_field_as_ama",
                "solver_version": "unknown",
                "git_commit": "unknown",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "seed": (params.get("seed") if isinstance(params, dict) else None),
                "platform": {
                    "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                },
            },
            "numerics": {
                "grid": [int(phi_2d.shape[0]), int(phi_2d.shape[1])],
                "integrator": "explicit_euler",
                "step_size": (params.get("dt") if isinstance(params, dict) else None),
            },
            "observables": {},
            "tests": [],
        }

    occ_available = True
    try:
        from OCC.Core.StlAPI import StlAPI_Reader  # type: ignore
        from OCC.Core.TopoDS import TopoDS_Shape  # type: ignore
    except Exception:
        occ_available = False

    if phi.ndim == 3:
        phi_2d = phi[:, :, 0]
    else:
        phi_2d = phi

    N = int(phi_2d.shape[0])
    export_params: dict[str, Any] = {
        "source": "PR",
        "size": N,
        "scale_xy": float(scale_xy),
        "scale_z": float(scale_z),
    }
    if params:
        export_params.update(params)

    # Attach optional, verifiable cosmological metadata.
    # This does not change core AMA structure; it adds files under meta/.
    try:
        import sys
    except Exception:
        sys = None  # type: ignore

    cosmo_obj = cosmo_meta if isinstance(cosmo_meta, dict) else None
    if cosmo_obj is None:
        try:
            cosmo_obj = _build_cosmo_meta_default()
        except Exception:
            cosmo_obj = None
    cosmo_bytes = _stable_json_bytes(cosmo_obj) if cosmo_obj is not None else None
    cosmo_header = None
    if cosmo_bytes is not None:
        cosmo_header = {
            "meta_format": "json",
            "meta_path": "meta/cosmo_meta.json",
            "meta_len": int(len(cosmo_bytes)),
            "meta_sha256": hashlib.sha256(cosmo_bytes).hexdigest(),
            "schema": "AdaptiveCAD.CosmoMeta",
            "schema_version": "0.1.0",
        }

    if not occ_available:
        # Analytic-only AMA (OCC-free).
        vals = np.asarray(phi_2d, dtype=np.float32)
        try:
            derived = compute_derived_fields(vals)
        except Exception:
            derived = {}

        residual = None
        if falsifier_residual is not None:
            residual = np.asarray(falsifier_residual, dtype=np.float32)

        Nf = int(vals.shape[0])
        x_extent = float((Nf - 1) * float(scale_xy))
        zmin = float(np.min(vals))
        zmax = float(np.max(vals))

        analytic_manifest: dict[str, Any] = {
            "format": "AdaptiveCAD.AnalyticPayload",
            "schema_version": "0.1.0",
            "units": str(units),
            "domain": {
                "size": [Nf, Nf],
                "extents": [[0.0, x_extent], [0.0, x_extent], [zmin, zmax]],
            },
            "scales": {"xy": float(scale_xy), "z": float(scale_z)},
            "fields": [
                {
                    "id": "field",
                    "path": "fields/f000_field.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "pr_field",
                },
            ],
        }
        if isinstance(derived.get("gradmag"), np.ndarray):
            analytic_manifest["fields"].append(
                {
                    "id": "gradmag",
                    "path": "fields/gradmag.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "|∇field|",
                }
            )
        if isinstance(derived.get("laplacian"), np.ndarray):
            analytic_manifest["fields"].append(
                {
                    "id": "laplacian",
                    "path": "fields/laplacian.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "Δ field",
                }
            )
        if isinstance(derived.get("curvature"), np.ndarray):
            analytic_manifest["fields"].append(
                {
                    "id": "curvature",
                    "path": "fields/curvature.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "mean_curvature(heightmap)",
                }
            )
        if isinstance(derived.get("smooth"), np.ndarray):
            analytic_manifest["fields"].append(
                {
                    "id": "smooth",
                    "path": "fields/smooth.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "smoothed(field)",
                }
            )
        if residual is not None and residual.shape[:2] == (Nf, Nf):
            analytic_manifest["fields"].append(
                {
                    "id": "falsifier",
                    "path": "fields/f003_residual.npy",
                    "dtype": "float32",
                    "shape": [Nf, Nf],
                    "meaning": "plaquette_falsifier_residual",
                }
            )

        analytic_scene: dict[str, Any] = {
            "format": "AdaptiveCAD.AnalyticScene",
            "version": "0.1.0",
            "camera": None,
            "layers": [
                {
                    "id": "field",
                    "kind": "field",
                    "field_ref": "fields/f000_field.npy",
                    "colormap": "plasma",
                }
            ],
            "render": {
                "mode": "heightmap",
                "source_layer": "field",
                "iso": 0.50,
            },
            "scales": {"xy": float(scale_xy), "z": float(scale_z)},
            "units": str(units),
        }
        if isinstance(derived.get("gradmag"), np.ndarray):
            analytic_scene["layers"].append(
                {
                    "id": "gradmag",
                    "label": "Gradient Magnitude",
                    "kind": "field",
                    "field_ref": "fields/gradmag.npy",
                    "colormap": "viridis",
                }
            )
        if isinstance(derived.get("laplacian"), np.ndarray):
            analytic_scene["layers"].append(
                {
                    "id": "laplacian",
                    "label": "Laplacian",
                    "kind": "field",
                    "field_ref": "fields/laplacian.npy",
                    "colormap": "diverge",
                }
            )
        if isinstance(derived.get("curvature"), np.ndarray):
            analytic_scene["layers"].append(
                {
                    "id": "curvature",
                    "label": "Mean Curvature",
                    "kind": "field",
                    "field_ref": "fields/curvature.npy",
                    "colormap": "diverge",
                }
            )
        if isinstance(derived.get("smooth"), np.ndarray):
            analytic_scene["layers"].append(
                {
                    "id": "smooth",
                    "label": "Smoothed Field",
                    "kind": "field",
                    "field_ref": "fields/smooth.npy",
                    "colormap": "plasma",
                }
            )
        if residual is not None and residual.shape[:2] == (Nf, Nf):
            analytic_scene["layers"].append(
                {
                    "id": "falsifier",
                    "kind": "field",
                    "field_ref": "fields/f003_residual.npy",
                    "colormap": "magma",
                }
            )

        # Root-level manifest.json to keep simple AMA readers from erroring.
        ama_manifest = {
            "version": "0.1.0",
            "source": "PR",
            "parts": [],
            "params": export_params,
        }

        buf_zip = BytesIO()
        with zipfile.ZipFile(buf_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(ama_manifest, indent=2))
            z.writestr("analytic/manifest.json", json.dumps(analytic_manifest, indent=2))
            z.writestr("analytic/scene.json", json.dumps(analytic_scene, indent=2))

            if cosmo_bytes is not None and cosmo_header is not None:
                z.writestr("meta/cosmo_meta.json", cosmo_bytes)
                z.writestr("meta/cosmo_header.json", json.dumps(cosmo_header, indent=2))

            buf = BytesIO()
            np.save(buf, vals)
            z.writestr("fields/f000_field.npy", buf.getvalue())

            if isinstance(derived.get("gradmag"), np.ndarray):
                buf = BytesIO()
                np.save(buf, np.asarray(derived["gradmag"], dtype=np.float32))
                z.writestr("fields/gradmag.npy", buf.getvalue())
            if isinstance(derived.get("laplacian"), np.ndarray):
                buf = BytesIO()
                np.save(buf, np.asarray(derived["laplacian"], dtype=np.float32))
                z.writestr("fields/laplacian.npy", buf.getvalue())
            if isinstance(derived.get("curvature"), np.ndarray):
                buf = BytesIO()
                np.save(buf, np.asarray(derived["curvature"], dtype=np.float32))
                z.writestr("fields/curvature.npy", buf.getvalue())
            if isinstance(derived.get("smooth"), np.ndarray):
                buf = BytesIO()
                np.save(buf, np.asarray(derived["smooth"], dtype=np.float32))
                z.writestr("fields/smooth.npy", buf.getvalue())

            if residual is not None and residual.shape[:2] == (Nf, Nf):
                buf = BytesIO()
                np.save(buf, residual)
                z.writestr("fields/f003_residual.npy", buf.getvalue())

            z.writestr(
                "meta/info.json",
                json.dumps(
                    {
                        "source": "PR",
                        "export": export_params,
                        "note": "OCC not available; analytic-only AMA",
                        "cosmo_header": "meta/cosmo_header.json" if cosmo_header is not None else None,
                    },
                    indent=2,
                ),
            )

        return buf_zip.getvalue()

    from adaptivecad.commands import Feature
    from adaptivecad.io.ama_writer import write_ama

    stl_bytes = export_phase_field_as_heightmap_stl(phi_2d, scale_xy=scale_xy, scale_z=scale_z)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        stl_path = tmpdir_path / "pr_heightmap.stl"
        stl_path.write_bytes(stl_bytes)

        reader = StlAPI_Reader()
        shape = TopoDS_Shape()
        ok = reader.Read(shape, str(stl_path))
        if not ok or shape.IsNull():
            raise RuntimeError("OCC failed to load STL into a shape")

        feature = Feature(
            name="NDField",
            params={
                **export_params,
                "dim": 2,
                "origin": [0.0, 0.0],
                "axes": [[1.0, 0.0], [0.0, 1.0]],
                "spacing": [float(scale_xy), float(scale_xy)],
            },
            shape=shape,
        )

        # Attach field values so ama_writer exports fields/f000_field.npy
        feature.values = np.asarray(phi_2d, dtype=np.float32)

        ama_path = tmpdir_path / filename
        write_ama([feature], ama_path, units=units, defl=float(defl))

        # Embed an analytic-first payload so non-OCC viewers can consume the AMA
        # deterministically (layers + suggested scaling). This keeps the door open
        # for true SDF/implicit rendering later while remaining mesh-overlay compatible.
        try:
            # Derived fields (best-effort): grad magnitude for a second layer.
            vals = np.asarray(phi_2d, dtype=np.float32)
            try:
                derived = compute_derived_fields(vals)
            except Exception:
                derived = {}

            residual = None
            if falsifier_residual is not None:
                residual = np.asarray(falsifier_residual, dtype=np.float32)

            Nf = int(vals.shape[0])
            x_extent = float((Nf - 1) * float(scale_xy))
            zmin = float(np.min(vals))
            zmax = float(np.max(vals))

            analytic_manifest = {
                "format": "AdaptiveCAD.AnalyticPayload",
                "schema_version": "0.1.0",
                "units": str(units),
                "domain": {
                    "size": [Nf, Nf],
                    "extents": [[0.0, x_extent], [0.0, x_extent], [zmin, zmax]],
                },
                "scales": {"xy": float(scale_xy), "z": float(scale_z)},
                "fields": [
                    {
                        "id": "field",
                        "path": "fields/f000_field.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "pr_field",
                    },
                ],
            }
            if isinstance(derived.get("gradmag"), np.ndarray):
                analytic_manifest["fields"].append(
                    {
                        "id": "gradmag",
                        "path": "fields/gradmag.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "|∇field|",
                    }
                )
            if isinstance(derived.get("laplacian"), np.ndarray):
                analytic_manifest["fields"].append(
                    {
                        "id": "laplacian",
                        "path": "fields/laplacian.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "Δ field",
                    }
                )
            if isinstance(derived.get("curvature"), np.ndarray):
                analytic_manifest["fields"].append(
                    {
                        "id": "curvature",
                        "path": "fields/curvature.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "mean_curvature(heightmap)",
                    }
                )
            if isinstance(derived.get("smooth"), np.ndarray):
                analytic_manifest["fields"].append(
                    {
                        "id": "smooth",
                        "path": "fields/smooth.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "smoothed(field)",
                    }
                )
            if residual is not None and residual.shape[:2] == (Nf, Nf):
                analytic_manifest["fields"].append(
                    {
                        "id": "falsifier",
                        "path": "fields/f003_residual.npy",
                        "dtype": "float32",
                        "shape": [Nf, Nf],
                        "meaning": "plaquette_falsifier_residual",
                    }
                )

            analytic_scene = {
                "format": "AdaptiveCAD.AnalyticScene",
                "version": "0.1.0",
                "camera": None,
                "layers": [
                    {
                        "id": "field",
                        "kind": "field",
                        "field_ref": "fields/f000_field.npy",
                        "colormap": "plasma",
                    }
                ],
                "render": {
                    "mode": "heightmap",
                    "source_layer": "field",
                    "iso": 0.50,
                },
                "scales": {"xy": float(scale_xy), "z": float(scale_z)},
                "units": str(units),
            }
            if isinstance(derived.get("gradmag"), np.ndarray):
                analytic_scene["layers"].append(
                    {
                        "id": "gradmag",
                        "label": "Gradient Magnitude",
                        "kind": "field",
                        "field_ref": "fields/gradmag.npy",
                        "colormap": "viridis",
                    }
                )
            if isinstance(derived.get("laplacian"), np.ndarray):
                analytic_scene["layers"].append(
                    {
                        "id": "laplacian",
                        "label": "Laplacian",
                        "kind": "field",
                        "field_ref": "fields/laplacian.npy",
                        "colormap": "diverge",
                    }
                )
            if isinstance(derived.get("curvature"), np.ndarray):
                analytic_scene["layers"].append(
                    {
                        "id": "curvature",
                        "label": "Mean Curvature",
                        "kind": "field",
                        "field_ref": "fields/curvature.npy",
                        "colormap": "diverge",
                    }
                )
            if isinstance(derived.get("smooth"), np.ndarray):
                analytic_scene["layers"].append(
                    {
                        "id": "smooth",
                        "label": "Smoothed Field",
                        "kind": "field",
                        "field_ref": "fields/smooth.npy",
                        "colormap": "plasma",
                    }
                )
            if residual is not None and residual.shape[:2] == (Nf, Nf):
                analytic_scene["layers"].append(
                    {
                        "id": "falsifier",
                        "kind": "field",
                        "field_ref": "fields/f003_residual.npy",
                        "colormap": "magma",
                    }
                )

            with zipfile.ZipFile(ama_path, "a", compression=zipfile.ZIP_DEFLATED) as z:
                if cosmo_bytes is not None and cosmo_header is not None:
                    z.writestr("meta/cosmo_meta.json", cosmo_bytes)
                    z.writestr("meta/cosmo_header.json", json.dumps(cosmo_header, indent=2))
                # Append derived field(s)
                if isinstance(derived.get("gradmag"), np.ndarray):
                    buf = BytesIO()
                    np.save(buf, np.asarray(derived["gradmag"], dtype=np.float32))
                    z.writestr("fields/gradmag.npy", buf.getvalue())
                if isinstance(derived.get("laplacian"), np.ndarray):
                    buf = BytesIO()
                    np.save(buf, np.asarray(derived["laplacian"], dtype=np.float32))
                    z.writestr("fields/laplacian.npy", buf.getvalue())
                if isinstance(derived.get("curvature"), np.ndarray):
                    buf = BytesIO()
                    np.save(buf, np.asarray(derived["curvature"], dtype=np.float32))
                    z.writestr("fields/curvature.npy", buf.getvalue())
                if isinstance(derived.get("smooth"), np.ndarray):
                    buf = BytesIO()
                    np.save(buf, np.asarray(derived["smooth"], dtype=np.float32))
                    z.writestr("fields/smooth.npy", buf.getvalue())
                if residual is not None and residual.shape[:2] == (Nf, Nf):
                    buf = BytesIO()
                    np.save(buf, residual)
                    z.writestr("fields/f003_residual.npy", buf.getvalue())
                # Append analytic payload
                z.writestr("analytic/manifest.json", json.dumps(analytic_manifest, indent=2))
                z.writestr("analytic/scene.json", json.dumps(analytic_scene, indent=2))
        except Exception:
            # Best-effort; AMA remains valid without these files.
            pass
        return ama_path.read_bytes()


__all__ = [
    "export_phase_field_as_heightmap_stl",
    "export_phase_field_as_obj",
    "export_phase_field_as_ama",
]
