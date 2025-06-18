from __future__ import annotations

from adaptivecad.command_defs import BaseCmd, DOCUMENT, rebuild_scene
from adaptivecad.cosmic_curve_tools import (
    BizarreCurveFeature,
    CosmicSplineFeature,
    NDFieldExplorerFeature,
)

try:
    from PySide6.QtWidgets import QInputDialog
    HAS_QT = True
except Exception:
    HAS_QT = False


class BizarreCurveCmd(BaseCmd):
    title = "Bizarre Curve"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        if not HAS_QT:
            return
        if BizarreCurveFeature is None:
            return

        r, ok = QInputDialog.getDouble(mw.win, "Bizarre Curve", "Base Radius:", 10.0, 0.1, 1000.0, 2)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(mw.win, "Bizarre Curve", "Height:", 50.0, 0.1, 1000.0, 2)
        if not ok:
            return
        freq, ok = QInputDialog.getDouble(mw.win, "Bizarre Curve", "Frequency:", 1.0, 0.1, 50.0, 2)
        if not ok:
            return
        dist, ok = QInputDialog.getDouble(mw.win, "Bizarre Curve", "Distortion:", 1.0, 0.0, 10.0, 2)
        if not ok:
            return
        segs, ok = QInputDialog.getInt(mw.win, "Bizarre Curve", "Segments:", 200, 10, 1000, 1)
        if not ok:
            return

        feat = BizarreCurveFeature(r, h, freq, dist, segs)
        DOCUMENT.append(feat)
        rebuild_scene(mw.view._display)


class CosmicSplineCmd(BaseCmd):
    title = "Cosmic Spline"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        if not HAS_QT:
            return

        npts, ok = QInputDialog.getInt(mw.win, "Cosmic Spline", "Number of control points:", 4, 2, 20, 1)
        if not ok:
            return
        pts = []
        for i in range(npts):
            x, ok = QInputDialog.getDouble(mw.win, f"Point {i+1}", "X:", 0.0, -1000.0, 1000.0, 2)
            if not ok:
                return
            y, ok = QInputDialog.getDouble(mw.win, f"Point {i+1}", "Y:", 0.0, -1000.0, 1000.0, 2)
            if not ok:
                return
            z, ok = QInputDialog.getDouble(mw.win, f"Point {i+1}", "Z:", 0.0, -1000.0, 1000.0, 2)
            if not ok:
                return
            pts.append((x, y, z))
        degree, ok = QInputDialog.getInt(mw.win, "Cosmic Spline", "Degree:", 3, 2, 5, 1)
        if not ok:
            return
        curv, ok = QInputDialog.getDouble(mw.win, "Cosmic Spline", "Cosmic Curvature:", 0.5, -10.0, 10.0, 2)
        if not ok:
            return

        feat = CosmicSplineFeature(pts, degree, curv)
        DOCUMENT.append(feat)
        rebuild_scene(mw.view._display)


class NDFieldExplorerCmd(BaseCmd):
    title = "ND Field Explorer"

    def run(self, mw) -> None:  # pragma: no cover - runtime GUI path
        if not HAS_QT:
            return

        dims, ok = QInputDialog.getInt(mw.win, "ND Field", "Dimensions:", 3, 1, 6, 1)
        if not ok:
            return
        size, ok = QInputDialog.getInt(mw.win, "ND Field", "Grid size:", 10, 2, 50, 1)
        if not ok:
            return
        ftype, ok = QInputDialog.getItem(
            mw.win,
            "ND Field",
            "Field type:",
            ["scalar_wave", "quantum_field", "cosmic_web", "random"],
            0,
            False,
        )
        if not ok:
            return

        feat = NDFieldExplorerFeature(dims, size, ftype)
        DOCUMENT.append(feat)
        rebuild_scene(mw.view._display)

