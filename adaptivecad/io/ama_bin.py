"""
AMA v1 (binary) read/write utilities.

Supports a minimal subset per spec:
 - Header with MAGIC "AMA1" (4B), VERSION u16 (0x0100), FLAGS u16
 - META_LEN u32, RESERVED u32 (0)
 - META_JSON (UTF-8), JSON contains minimal fields
 - CHUNK_TBL: u32 chunk_count, then entries of (KIND u32, OFFSET u64, LENGTH u64)
 - PAYLOADS aligned to 16 bytes

Implemented chunks:
 - 1 VERT: float32 xyz (N x 3)
 - 5 TRI:  uint32 i0 i1 i2 (M x 3)

Optional chunks are ignored on read but preserved metadata can describe them.
"""
from __future__ import annotations

import io
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

__all__ = [
    "AMA_MAGIC",
    "AMA_VERSION",
    "write_ama_bin",
    "read_ama_bin",
]

AMA_MAGIC = b"AMA1"
AMA_VERSION = 0x0100

K_VERT = 1
K_NORM = 2
K_UV = 3
K_RGBA8 = 4
K_TRI = 5
K_QUAD = 6
K_EDGES = 7
K_ATTR = 8
K_COMP = 9


def _pad16(n: int) -> int:
    r = (16 - (n % 16)) % 16
    return r


def write_ama_bin(path, verts, tris, meta: Optional[Dict]=None, flags: int=0) -> Path:
    """Write AMA v1 binary with minimal chunks: VERT + TRI.
    - verts: numpy-like (N,3) float32 or list of tuples
    - tris: numpy-like (M,3) uint32 or list of tuples
    """
    import numpy as np
    path = Path(path)
    verts = np.asarray(verts, dtype=np.float32).reshape((-1,3))
    tris = np.asarray(tris, dtype=np.uint32).reshape((-1,3))

    meta = dict(meta or {})
    meta.setdefault("units", "mm")
    meta.setdefault("vertex_count", int(verts.shape[0]))
    meta.setdefault("tri_count", int(tris.shape[0]))

    # Prepare JSON
    meta_json = json.dumps(meta, separators=(",", ":")).encode("utf-8")

    # Compute offsets
    header_size = 0x10  # up to RESERVED
    chunk_tbl_size = 4 + 2 * (4 + 8 + 8)  # count + 2 entries

    offs = header_size + len(meta_json)
    offs += _pad16(offs)
    chunk_tbl_offs = offs
    offs += chunk_tbl_size
    offs += _pad16(offs)

    # Payloads
    vert_offs = offs
    vert_len = int(verts.nbytes)
    offs += vert_len
    offs += _pad16(offs)

    tri_offs = offs
    tri_len = int(tris.nbytes)
    offs += tri_len
    offs += _pad16(offs)

    # Write file
    with open(path, "wb") as f:
        # Header
        f.write(AMA_MAGIC)
        f.write(struct.pack("<H", AMA_VERSION))
        f.write(struct.pack("<H", flags))
        f.write(struct.pack("<I", len(meta_json)))
        f.write(struct.pack("<I", 0))  # RESERVED
        # META_JSON
        f.write(meta_json)
        pad = _pad16(f.tell())
        if pad:
            f.write(b"\x00" * pad)

        # Chunk table
        assert f.tell() == chunk_tbl_offs
        f.write(struct.pack("<I", 2))  # two chunks
        f.write(struct.pack("<IQQ", K_VERT, vert_offs, vert_len))
        f.write(struct.pack("<IQQ", K_TRI, tri_offs, tri_len))
        pad = _pad16(f.tell())
        if pad:
            f.write(b"\x00" * pad)

        # Payloads
        assert f.tell() == vert_offs
        f.write(verts.tobytes(order="C"))
        pad = _pad16(f.tell())
        if pad:
            f.write(b"\x00" * pad)

        assert f.tell() == tri_offs
        f.write(tris.tobytes(order="C"))
        pad = _pad16(f.tell())
        if pad:
            f.write(b"\x00" * pad)
    return path


def read_ama_bin(path) -> Tuple:
    """Read AMA v1 binary, returning (verts, tris, meta, chunks) where chunks is a dict of raw bytes for unknown chunks.
    """
    import numpy as np
    with open(path, "rb") as f:
        data = f.read()

    view = memoryview(data)
    if view[:4].tobytes() != AMA_MAGIC:
        raise ValueError("Not an AMA1 file")
    pos = 4
    version = struct.unpack_from("<H", view, pos)[0]; pos += 2
    if version != AMA_VERSION:
        raise ValueError(f"Unsupported AMA version: {version}")
    flags = struct.unpack_from("<H", view, pos)[0]; pos += 2
    meta_len = struct.unpack_from("<I", view, pos)[0]; pos += 4
    _reserved = struct.unpack_from("<I", view, pos)[0]; pos += 4

    meta_json = json.loads(view[pos:pos+meta_len].tobytes().decode("utf-8"))
    pos += meta_len
    # align 16
    pad = (16 - (pos % 16)) % 16
    pos += pad

    # chunk table
    chunk_count = struct.unpack_from("<I", view, pos)[0]; pos += 4
    entries = []
    for _ in range(chunk_count):
        kind, off, length = struct.unpack_from("<IQQ", view, pos)
        pos += (4 + 8 + 8)
        entries.append((kind, off, length))
    # align
    pad = (16 - (pos % 16)) % 16
    pos += pad

    verts = None
    tris = None
    extras: Dict[int, bytes] = {}
    for kind, off, length in entries:
        payload = view[off: off+length]
        if kind == K_VERT:
            arr = np.frombuffer(payload, dtype=np.float32)
            if arr.size % 3 != 0:
                raise ValueError("VERT chunk not multiple of 3 floats")
            verts = arr.reshape((-1,3))
        elif kind == K_TRI:
            arr = np.frombuffer(payload, dtype=np.uint32)
            if arr.size % 3 != 0:
                raise ValueError("TRI chunk not multiple of 3 uint32")
            tris = arr.reshape((-1,3))
        else:
            extras[kind] = payload.tobytes()

    if verts is None or tris is None:
        raise ValueError("Missing required VERT/TRI chunks")
    return verts, tris, meta_json, extras
