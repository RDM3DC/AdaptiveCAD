"""Minimal AdaptiveCAD AMA viewer (OCC).

Opens an .ama archive, loads embedded BREP geometry, and displays it using
pythonocc-core's SimpleGui viewer.

Supports both:
- Modern AMA layout (written by adaptivecad.io.ama_writer):
    meta/manifest.json
    model/graph.json
    geom/s###.brep
    fields/f###_field.npy (optional)
- Legacy AMA layout (adaptivecad.io.ama_reader):
    manifest.json
    parts/<name>.brep

Usage (recommended on Windows):
  conda run -n adaptivecad python ama_viewer.py path\\to\\file.ama

Notes:
- Requires pythonocc-core.
- This is a local GUI utility (not suitable for headless MCP execution).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


def _ensure_repo_on_path() -> None:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


@dataclass(frozen=True)
class _BrepEntry:
    name: str
    data: bytes


def _load_brep_from_bytes(brep_bytes: bytes):
    try:
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepTools import breptools_Read
        from OCC.Core.TopoDS import TopoDS_Shape
    except Exception as exc:
        raise ImportError("pythonocc-core is required to view BREP geometry") from exc

    with tempfile.NamedTemporaryFile(suffix=".brep", delete=False) as tmp:
        tmp.write(brep_bytes)
        tmp_path = tmp.name

    try:
        builder = BRep_Builder()
        shape = TopoDS_Shape()
        breptools_Read(shape, tmp_path, builder)
        return shape
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _iter_modern_ama_entries(z: zipfile.ZipFile) -> Iterable[_BrepEntry]:
    names = set(z.namelist())

    if "model/graph.json" in names:
        try:
            graph = json.loads(z.read("model/graph.json").decode("utf-8"))
        except Exception:
            graph = None

        if isinstance(graph, list):
            for node in graph:
                if not isinstance(node, dict):
                    continue
                geom = node.get("geom")
                if not isinstance(geom, str) or not geom.endswith(".brep"):
                    continue
                entry_name = f"geom/{geom}" if not geom.startswith("geom/") else geom
                if entry_name in names:
                    yield _BrepEntry(name=node.get("id", entry_name), data=z.read(entry_name))

    # Fallback: any geom/*.brep
    for entry_name in sorted(names):
        if entry_name.startswith("geom/") and entry_name.endswith(".brep"):
            yield _BrepEntry(name=entry_name, data=z.read(entry_name))


def _iter_legacy_ama_entries(ama_path: Path) -> Iterable[_BrepEntry]:
    # Legacy reader expects manifest.json + parts/*.brep
    _ensure_repo_on_path()

    try:
        from adaptivecad.io.ama_reader import read_ama
    except Exception:
        return

    ama = read_ama(str(ama_path))
    if not ama or not getattr(ama, "parts", None):
        return

    for part in ama.parts:
        name = getattr(part, "name", "part")
        data = getattr(part, "brep_data", None) or b""
        if data:
            yield _BrepEntry(name=name, data=data)


def _iter_brep_entries(ama_path: Path) -> list[_BrepEntry]:
    entries: list[_BrepEntry] = []

    with zipfile.ZipFile(ama_path, "r") as z:
        names = set(z.namelist())

        # Prefer modern AMA layout.
        if any(n.startswith("geom/") for n in names):
            entries.extend(list(_iter_modern_ama_entries(z)))

        # If not modern, try legacy reader.
        if not entries and ("manifest.json" in names or any(n.startswith("parts/") for n in names)):
            entries.extend(list(_iter_legacy_ama_entries(ama_path)))

        # Last resort: any *.brep anywhere in the zip.
        if not entries:
            for entry_name in sorted(names):
                if entry_name.endswith(".brep"):
                    entries.append(_BrepEntry(name=entry_name, data=z.read(entry_name)))

    # De-dupe by (name, size) while preserving order.
    seen: set[tuple[str, int]] = set()
    uniq: list[_BrepEntry] = []
    for e in entries:
        key = (e.name, len(e.data))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def _show_shapes(shapes, title: str) -> None:
    try:
        from OCC.Display.SimpleGui import init_display
    except Exception as exc:
        raise ImportError("pythonocc-core viewer (OCC.Display.SimpleGui) is required") from exc

    display, start_display, _add_menu, _add_func_to_menu = init_display()

    try:
        # DisplayShape accepts a single shape or a list.
        display.DisplayShape(shapes, update=True)
        display.FitAll()

        # Best-effort window title.
        if hasattr(display, "View") and hasattr(display.View, "SetWindowTitle"):
            display.View.SetWindowTitle(title)
    except Exception:
        # Even if title setting fails, keep the viewer up.
        pass

    start_display()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="View an AdaptiveCAD .ama archive in an OCC window.")
    parser.add_argument("ama", type=str, help="Path to .ama file")
    parser.add_argument("--index", type=int, default=-1, help="If provided, view only one shape by index (0-based)")
    args = parser.parse_args(argv)

    ama_path = Path(args.ama).expanduser().resolve()
    if not ama_path.exists():
        print(f"ERROR: AMA file not found: {ama_path}")
        return 2

    try:
        entries = _iter_brep_entries(ama_path)
    except zipfile.BadZipFile:
        print(f"ERROR: Not a valid .ama (zip) file: {ama_path}")
        return 2

    if not entries:
        print(f"ERROR: No .brep geometry found inside: {ama_path}")
        return 3

    if args.index >= 0:
        if args.index >= len(entries):
            print(f"ERROR: --index {args.index} out of range (0..{len(entries)-1})")
            return 2
        entries = [entries[args.index]]

    print(f"Loaded {len(entries)} shape(s) from: {ama_path}")
    for i, e in enumerate(entries):
        print(f"  [{i}] {e.name} ({len(e.data)} bytes)")

    shapes = [_load_brep_from_bytes(e.data) for e in entries]
    title = f"AdaptiveCAD AMA Viewer - {ama_path.name}"
    _show_shapes(shapes if len(shapes) > 1 else shapes[0], title=title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
