from __future__ import annotations

"""Simple command framework for the AdaptiveCAD GUI.

This module defines primitives for creating and manipulating geometry in the
GUI playground.  All GUI dependencies are imported lazily so the rest of the
package can be used without installing ``pythonocc-core`` or ``PyQt``.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from adaptivecad.io.ama_writer import write_ama

# ---------------------------------------------------------------------------
# Optional GUI helpers
# ---------------------------------------------------------------------------

def _require_command_modules():
    """Import optional GUI modules required for command execution."""
    try:
        from PySide6.QtWidgets import QInputDialog, QFileDialog
        from OCC.Core.BRepPrimAPI import (
            BRepPrimAPI_MakeBox,
            BRepPrimAPI_MakeCylinder,
        )
        from OCC.Core.StlAPI import StlAPI_Writer
    except Exception as exc:  # pragma: no cover - import error path
        raise RuntimeError(
            "GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6"
        ) from exc

    return (
        QInputDialog,
        QFileDialog,
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        StlAPI_Writer,
    )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    """Record for a model feature."""

    name: str
    params: Dict[str, Any]
    shape: Any  # OCC TopoDS_Shape


# Global in-memory document tree
DOCUMENT: List[Feature] = []


def rebuild_scene(display) -> None:
    """Re-display all shapes in the document."""
    display.EraseAll()
    for feat in DOCUMENT:
        display.DisplayShape(feat.shape, update=False)
    display.FitAll()


# ---------------------------------------------------------------------------
# Command classes
# ---------------------------------------------------------------------------

class BaseCmd:
    """Base command interface."""

    title = "Base"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        raise NotImplementedError


class NewBoxCmd(BaseCmd):
    title = "Box"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            QInputDialog,
            _,
            BRepPrimAPI_MakeBox,
            _,
            _,
        ) = _require_command_modules()

        l, ok = QInputDialog.getDouble(mw.win, "Box", "Length (mm)", 50, 1)
        if not ok:
            return
        w, ok = QInputDialog.getDouble(mw.win, "Box", "Width (mm)", 50, 1)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(mw.win, "Box", "Height (mm)", 20, 1)
        if not ok:
            return

        shape = BRepPrimAPI_MakeBox(l, w, h).Shape()
        DOCUMENT.append(Feature("Box", {"l": l, "w": w, "h": h}, shape))
        rebuild_scene(mw.view._display)


class NewCylCmd(BaseCmd):
    title = "Cylinder"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            QInputDialog,
            _,
            _,
            BRepPrimAPI_MakeCylinder,
            _,
        ) = _require_command_modules()

        r, ok = QInputDialog.getDouble(mw.win, "Cylinder", "Radius (mm)", 10, 1)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(mw.win, "Cylinder", "Height (mm)", 40, 1)
        if not ok:
            return

        shape = BRepPrimAPI_MakeCylinder(r, h).Shape()
        DOCUMENT.append(Feature("Cyl", {"r": r, "h": h}, shape))
        rebuild_scene(mw.view._display)


class ExportStlCmd(BaseCmd):
    title = "Export STL"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            _,
            QFileDialog,
            _,
            _,
            StlAPI_Writer,
        ) = _require_command_modules()

        if not DOCUMENT:
            return

        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save STL", filter="STL (*.stl)"
        )
        if not path:
            return

        writer = StlAPI_Writer()
        err = writer.Write(DOCUMENT[-1].shape, path)
        if err == 1:
            mw.win.statusBar().showMessage(f"STL saved ➡ {path}")
        else:
            mw.win.statusBar().showMessage("Failed to save STL")


class ExportAmaCmd(BaseCmd):
    title = "Export AMA"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        (
            _,
            QFileDialog,
            _,
            _,
            _,
        ) = _require_command_modules()

        if not DOCUMENT:
            return

        path, _filter = QFileDialog.getSaveFileName(
            mw.win, "Save AMA", filter="AMA (*.ama)"
        )
        if not path:
            return

        write_ama(DOCUMENT, path)
        mw.win.statusBar().showMessage(f"AMA saved ➡ {path}")
