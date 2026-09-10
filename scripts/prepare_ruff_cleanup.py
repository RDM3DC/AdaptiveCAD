"""Prepare a reviewable cleanup in a disposable checkout; never push a branch.

Only the known Ruff baseline and its explicit runtime defects are changed.
All optional import checks remain executable. No noqa or policy edits are made.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8-sig")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected exactly one matching block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def diagnostics():
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", ".", "--output-format=json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def preserve_import_contracts(path, rows):
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    replacements = []
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        selected = []
        for alias in node.names:
            if any(alias.lineno <= d["location"]["row"] <= alias.end_lineno and
                   (d["location"]["row"] > alias.lineno or d["location"]["column"] - 1 >= alias.col_offset) and
                   (d["location"]["row"] < alias.end_lineno or d["location"]["column"] - 1 < alias.end_col_offset) for d in rows):
                selected.append(alias)
        if not selected:
            continue
        retained = []
        for alias in selected:
            if alias.asname is None and "." not in alias.name:
                alias.asname = alias.name
            elif alias.asname != alias.name:
                retained.append(alias.asname or alias.name)
        replacement = ast.unparse(node)
        if retained:
            replacement += "\n" + " " * node.col_offset
            replacement += "_retained_import_contract = (" + ", ".join(retained) + ",)"
        start = sum(len(x.encode()) for x in lines[:node.lineno - 1]) + node.col_offset
        stop = sum(len(x.encode()) for x in lines[:node.end_lineno - 1]) + node.end_col_offset
        replacements.append((start, stop, replacement.encode()))
    data = text.encode()
    for start, stop, replacement in sorted(replacements, reverse=True):
        data = data[:start] + replacement + data[stop:]
    path.write_bytes(data)


def main():
    root = Path.cwd()
    before = diagnostics()
    allowed_codes = {"F823", "E401", "I001", "F821", "F401", "E722", "F811", "F841", "F541"}
    if {d["code"] for d in before} - allowed_codes:
        raise RuntimeError("Unexpected lint rule; review rather than applying a blanket fix")
    output = root / "cleanup-review"
    output.mkdir(exist_ok=True)
    (output / "ruff-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    flagged = {Path(d["filename"]).resolve() for d in before}
    for path in flagged:
        path.relative_to(root)
        rows = [d for d in before if Path(d["filename"]).resolve() == path and d["code"] == "F401"]
        if rows:
            preserve_import_contracts(path, rows)
        if any(Path(d["filename"]).resolve() == path and d["code"] == "E722" for d in before):
            text = path.read_text(encoding="utf-8-sig")
            text = re.sub(r"(?m)^([ \t]*)except:([^\n]*)$", r"\1except BaseException:\2", text)
            path.write_text(text, encoding="utf-8")

    replace_once(root / "AdaptiveCAD_Shipping_Track_v1/adaptivecad_fields_optimizer.py",
                 "    ys = np.linspace(-args.R, args.R, ny)\n    import numpy as np\n",
                 "    ys = np.linspace(-args.R, args.R, ny)\n")
    replace_once(root / "adaptivecad/command_defs.py",
                 'class ExportAmaCmd(BaseCmd):\n    title = "Export AMA"\n\n    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path\n        (\n            _,',
                 'class ExportAmaCmd(BaseCmd):\n    title = "Export AMA"\n\n    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path\n        (\n            QInputDialog,')
    replace_once(root / "pathtext/compress_paths.py", "import argparse\nimport json\n",
                 "import argparse\nimport json\nimport math\n")
    replace_once(root / "adaptivecad/plugins/macro_engine.py",
                 "parent_widget: Optional[Widget]", "parent_widget: Optional[QWidget]")
    path = root / "adaptivecad/plugins/macro_engine.py"
    text = path.read_text(encoding="utf-8-sig").replace("  # type: ignore[name-defined]", "")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("# Note: the type hint Widget")) + "\n"
    path.write_text(text, encoding="utf-8")

    path = root / "adaptivecad/gui/analytic_viewport.py"
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    remove = []
    active = {}
    owner = next(n for n in ast.walk(ast.parse(text))
                 if isinstance(n, ast.FunctionDef) and n.name == "_cupy_available")
    for name in ("Line2D", "Arc2D", "Circle2D", "Rect2D"):
        nodes = sorted((n for n in owner.body if isinstance(n, ast.ClassDef) and n.name == name),
                       key=lambda n: n.lineno)
        if len(nodes) != 2 or any(n.decorator_list for n in nodes):
            raise RuntimeError(f"Unexpected class structure for {name}")
        remove.append((nodes[0].lineno - 1, nodes[0].end_lineno))
        active[name] = ast.dump(nodes[-1], include_attributes=False)
    for start, stop in sorted(remove, reverse=True):
        del lines[start:stop]
    text = "".join(lines)
    for name, dump in active.items():
        node = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ClassDef) and n.name == name)
        if ast.dump(node, include_attributes=False) != dump:
            raise RuntimeError("Retained viewport class changed")
    path.write_text(text, encoding="utf-8")

    path = root / "adaptivecad/sketch/geometry.py"
    replace_once(path, '    def point(pt: Vec2) -> "Intersection":',
                 '    def from_point(pt: Vec2) -> "Intersection":')
    replace_once(path, '    def segment(a: Vec2, b: Vec2) -> "Intersection":',
                 '    def from_segment(a: Vec2, b: Vec2) -> "Intersection":')
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("Intersection.point(", "Intersection.from_point(")
    text = text.replace("Intersection.segment(", "Intersection.from_segment(")
    marker = "\ndef _clip_projection("
    if text.count(marker) != 1:
        raise RuntimeError("Unexpected intersection layout")
    text = text.replace(marker,
        '\n# Install compatibility factories after dataclass has captured real None defaults.\n'
        '# Instance payloads shadow these non-data descriptors, preserving both old APIs.\n'
        'setattr(Intersection, "point", staticmethod(Intersection.from_point))\n'
        'setattr(Intersection, "segment", staticmethod(Intersection.from_segment))\n\n'
        'def _clip_projection(', 1)
    path.write_text(text, encoding="utf-8")

    path = root / "adaptivecad/commands/move.py"
    replace_once(path, "from .base import BaseCmd", "from ..command_defs import BaseCmd")
    replace_once(path, "        orig_ref = feat.get_reference_point()",
                 '        preview = getattr(mw, "show_move_preview", None)\n'
                 '        if not callable(preview):\n'
                 '            raise RuntimeError("Move (Snap) needs a host show_move_preview callback")\n'
                 '        orig_ref = feat.get_reference_point()')
    replace_once(path, "            show_move_preview(feat, snapped or world_pt, label)",
                 "            dest = snapped if snapped is not None else world_pt\n"
                 "            preview(feat, dest, label)")

    path = root / "tests/test_meshfree_workbench.py"
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    rows = [d for d in before if Path(d["filename"]).resolve() == path and d["code"] == "F841"]
    for row in sorted({d["location"]["row"] for d in rows}, reverse=True):
        line = lines[row - 1]
        if "widgets = pytest.importorskip(" not in line:
            raise RuntimeError("Unexpected unused assignment")
        lines[row - 1] = line.replace("widgets = ", "", 1)
    path.write_text("".join(lines), encoding="utf-8")
    path = root / "_diag_select.py"
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("    import traceback; traceback.print_exc()", "    import traceback\n\n    traceback.print_exc()")
    path.write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, "-m", "ruff", "check", "--select", "I,E401,F541", "--fix",
                    *[str(p.relative_to(root)) for p in sorted(flagged)]], check=True)
    after = diagnostics()
    (output / "ruff-after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    if after:
        raise RuntimeError(f"{len(after)} diagnostics remain; review required")
    patch = subprocess.check_output(["git", "diff", "--no-ext-diff", "--", "*.py"])
    (output / "cleanup.patch").write_bytes(patch)


if __name__ == "__main__":
    main()
