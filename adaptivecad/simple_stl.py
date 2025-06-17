import os
import struct
from typing import Tuple, List

import numpy as np


def load_stl(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load an STL file returning vertices and triangle indices.

    The loader supports both binary and ASCII STL formats. Vertices are
    deduplicated and returned as an ``(N, 3)`` float array while ``faces``
    is an ``(M, 3)`` integer array of indices into the vertex array.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "rb") as f:
        header = f.read(80)
        tri_bytes = f.read(4)
        if len(tri_bytes) == 4:
            tri_count = struct.unpack("<I", tri_bytes)[0]
            remaining = f.read()
            expected = tri_count * 50
            if len(remaining) == expected:
                # Binary STL
                dtype = np.dtype([
                    ("normal", "<3f4"),
                    ("v1", "<3f4"),
                    ("v2", "<3f4"),
                    ("v3", "<3f4"),
                    ("attr", "<H"),
                ])
                data = np.frombuffer(remaining, dtype=dtype, count=tri_count)
                verts, faces = _deduplicate(
                    np.vstack([data["v1"], data["v2"], data["v3"]])
                )
                return verts, faces
        # Not binary, fall back to ASCII parsing

    verts_list: List[Tuple[float, float, float]] = []
    faces_list: List[Tuple[int, int, int]] = []
    vert_map: dict[Tuple[float, float, float], int] = {}

    def add_vertex(v: Tuple[float, float, float]) -> int:
        if v in vert_map:
            return vert_map[v]
        vert_map[v] = len(verts_list)
        verts_list.append(v)
        return vert_map[v]

    with open(path, "r", errors="ignore") as f:
        cur_vertices: List[Tuple[float, float, float]] = []
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "vertex":
                cur_vertices.append(
                    (float(parts[1]), float(parts[2]), float(parts[3]))
                )
                if len(cur_vertices) == 3:
                    idx = [add_vertex(v) for v in cur_vertices]
                    faces_list.append(tuple(idx))
                    cur_vertices = []
    verts = np.array(verts_list, dtype=float)
    faces = np.array(faces_list, dtype=int)
    return verts, faces


def _deduplicate(tri_vertices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Helper to deduplicate vertices from stacked triangle vertices."""
    verts_list: List[Tuple[float, float, float]] = []
    vert_map: dict[Tuple[float, float, float], int] = {}
    faces_list: List[Tuple[int, int, int]] = []
    for i in range(0, len(tri_vertices), 3):
        face_idx = []
        for j in range(3):
            v = tuple(float(x) for x in tri_vertices[i + j])
            if v not in vert_map:
                vert_map[v] = len(verts_list)
                verts_list.append(v)
            face_idx.append(vert_map[v])
        faces_list.append(tuple(face_idx))
    verts = np.array(verts_list, dtype=float)
    faces = np.array(faces_list, dtype=int)
    return verts, faces
