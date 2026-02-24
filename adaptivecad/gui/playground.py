"""Simplified GUI playground with optional dependencies.

This playground implements advanced parametric shapes including Pi Curve Shell,
Superellipse, Helix, Tapered Cylinder, Capsule and Ellipsoid that demonstrate the
Adaptive Pi Geometry (Ï€â‚) principles.

Now supports an OCC-free fallback mode: if `pythonocc-core` is unavailable, the
application will still start using a minimal placeholder viewer and analytic viewport.
"""

import logging

log = logging.getLogger("adaptivecad.gui")
if not logging.getLogger().hasHandlers():  # lightweight default config
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

HAS_QT = False
HAS_OCC = False

# Detect PySide6
try:  # pragma: no cover - runtime environment dependent
    HAS_QT = True
except Exception:
    HAS_QT = False

# If Qt present, attempt OCC
if HAS_QT:
    try:  # pragma: no cover - runtime environment dependent
        from OCC.Display import backend  # type: ignore

        backend.load_backend("pyside6")  # ensure PySide6 backend
        HAS_OCC = True
    except Exception:
        HAS_OCC = False

# Common imports when Qt exists
if HAS_QT:
    import traceback

    from adaptivecad import settings
    from adaptivecad.gui.viewcube_widget import ViewCubeWidget

    # Optional ND Chess widget
    try:
        from adaptivecad.gui.nd_chess_widget import NDChessWidget
    except Exception:  # pragma: no cover - missing deps
        NDChessWidget = None
    from adaptivecad.ai.intent_router import CADActionBus
    from adaptivecad.geometry.pia_primitives import (
        make_pi_circle_profile,
        upgrade_profile_meta_to_pia,
    )
    from adaptivecad.ui.ai_dock import AICopilotDock

    # Custom tools registry and dock
    try:
        from adaptivecad.plugins.tool_registry import ToolRegistry
        from adaptivecad.ui.custom_tools_dock import CustomToolsDock
    except Exception:
        ToolRegistry = None  # type: ignore
        CustomToolsDock = None  # type: ignore
    # Capability probe (may or may not exist yet when partially installed)
    try:
        from adaptivecad.analytic.capabilities import (
            analytic_available,
            conversion_available,
            exporter_available,
        )
        from adaptivecad.analytic.capabilities import summary as caps_summary
    except Exception:  # capability module optional

        def analytic_available():
            return False

        def exporter_available():
            return False

        def conversion_available():
            return False

        def caps_summary():
            return {"analytic": False, "exporter": False, "conversion": False}

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDockWidget,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    from adaptivecad.sketch_solver import (
        DistanceConstraint,
        EqualLengthConstraint,
        FixedConstraint,
        HorizontalConstraint,
        ParallelConstraint,
        PerpendicularConstraint,
        Sketch,
        VerticalConstraint,
        export_dxf,
    )

    # Feature modules from AdaptiveCAD-light (snaps, measurement, viewports)
    try:
        from adaptivecad.gui.dim_draw import draw_angular_dim, draw_linear_dim, draw_radial_dim
        from adaptivecad.gui.dim_tools import (
            DimAngularTool,
            DimLinearTool,
            DimRadialTool,
            MeasureTool,
            ToolContext,
        )
        from adaptivecad.gui.dimensions import (
            AngularDimension,
            DimStyle,
            LinearDimension,
            RadialDimension,
        )
        from adaptivecad.gui.osnap import osnap_pick
        FEATURES_AVAILABLE = True
    except ImportError as e:
        log.debug(f"Optional features not available: {e}")
        osnap_pick = None
        DimStyle = None
        ToolContext = None
        FEATURES_AVAILABLE = False

    # Analytic conversion commands (guarded so app still launches if package absent)
    try:
        from adaptivecad.analytic.conversion import (
            ConvertAnalyticToMeshCmd,
            ConvertMeshToAnalyticCmd,
        )
    except Exception:  # pragma: no cover - optional module

        class _StubCmd:
            def __init__(self, name):
                self._name = name

            def run(self, mw):
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        mw.win,
                        self._name,
                        f"Module 'adaptivecad.analytic' not available; {self._name} disabled.",
                    )
                except Exception:
                    log.info("%s: analytic module not available.", self._name)

        def ConvertMeshToAnalyticCmd():
            return _StubCmd("Convert Mesh â†’ Analytic")

        def ConvertAnalyticToMeshCmd():
            return _StubCmd("Convert Analytic â†’ Mesh")

    from adaptivecad.command_defs import (
        CutCmd,
        ExportAmaCmd,
        ExportGCodeCmd,
        ExportGCodeDirectCmd,
        ExportStlCmd,
        Feature,
        IntersectCmd,
        MirrorCmd,
        MoveCmd,
        NewBallCmd,
        NewBoxCmd,
        NewConeCmd,
        NewCylCmd,
        NewTorusCmd,
        ScaleCmd,
        ShellCmd,
        UnionCmd,
    )

    # Guard OCC-dependent minimal import command so app can start without OCC
    try:  # pragma: no cover
        from adaptivecad.commands.minimal_import import MinimalImportCmd
    except Exception:

        class MinimalImportCmd:  # fallback stub
            def run(self, mw):  # mw = MainWindow instance
                msg = "OCC not available; STL/STEP import disabled in this session."
                log.info(msg)
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(mw.win, "Import", msg)
                except Exception:
                    pass

    if HAS_OCC:
        pass  # type: ignore
    # Note: legacy backends import removed (module not present in repo)

# Backwards compatibility flag
HAS_GUI = HAS_QT


def _require_gui_modules():
    try:
        # Explicit imports to validate availability; will trigger monkeypatched __import__ in tests
        import PySide6.QtWidgets  # noqa: F401
    except ImportError as e:
        raise RuntimeError(f"GUI dependencies are not available: {e}")
    return True


# If this module is imported in an environment explicitly missing Qt (as in tests),
# expose a sentinel that test can call to assert the failure path.

# Ensure QDockWidget is always imported for all code paths
try:
    from PySide6.QtWidgets import QDockWidget
except ImportError:
    QDockWidget = None

# Define SuperellipseFeature at module level regardless of GUI availability
from adaptivecad.command_defs import Feature


# Helper to gate optional features cleanly
def require(cap_fn, ok_fn, mw, msg: str):
    try:
        if cap_fn():
            return ok_fn()
    except Exception as e:  # capability function itself failed
        log.debug(f"Capability function error: {e}")
    try:
        if HAS_QT:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(mw.win, "Feature Unavailable", msg)
        else:
            log.warning(f"Feature unavailable: {msg}")
    except Exception:
        log.warning(f"Feature unavailable (no UI): {msg}")


# --- PI CURVE SHELL SHAPE TOOL (Parametric Ï€â‚-based surface) ---
class PiCurveShellFeature(Feature):
    def __init__(self, base_radius, height, freq, amp, phase, n_u=60, n_v=30):
        params = {
            "base_radius": base_radius,
            "height": height,
            "freq": freq,
            "amp": amp,
            "phase": phase,
            "n_u": n_u,
            "n_v": n_v,
        }
        shape = self._make_shape(params)
        super().__init__("PiCurveShell", params, shape)

    @staticmethod
    def _make_shape(params):
        import numpy as np

        if not HAS_OCC:
            return None  # Fallback: no geometry
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace  # type: ignore
        from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineSurface  # type: ignore
        from OCC.Core.gp import gp_Pnt  # type: ignore
        from OCC.Core.TColgp import TColgp_Array2OfPnt  # type: ignore

        base_radius = params["base_radius"]
        height = params["height"]
        freq = params["freq"]
        amp = params["amp"]
        phase = params["phase"]
        n_u = params["n_u"]
        n_v = params["n_v"]
        # Generate points for a deformed cylinder shell
        us = np.linspace(0, 2 * np.pi, n_u)
        vs = np.linspace(0, height, n_v)

        def pi_curve(u):
            # Example: Ï€â‚ curve as a sine deformation
            return amp * np.sin(freq * u + phase)

        pts = []
        for v in vs:
            row = []
            for u in us:
                r = base_radius + pi_curve(u)
                x = r * np.cos(u)
                y = r * np.sin(u)
                z = v
                row.append(gp_Pnt(x, y, z))
            pts.append(row)
        # Create faces between grid points
        arr = TColgp_Array2OfPnt(1, n_u, 1, n_v)
        for i in range(n_u):
            for j in range(n_v):
                arr.SetValue(i + 1, j + 1, pts[j][i])

        spline_surface = GeomAPI_PointsToBSplineSurface(arr).Surface()
        face = BRepBuilderAPI_MakeFace(spline_surface, 1e-6).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewPiCurveShellCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Adaptive Pi Curve Shell Parameters")
                layout = QFormLayout(self)
                self.base_radius = QDoubleSpinBox()
                self.base_radius.setRange(0.1, 1000)
                self.base_radius.setValue(20.0)
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(40.0)
                self.freq = QDoubleSpinBox()
                self.freq.setRange(0.1, 20.0)
                self.freq.setValue(3.0)
                self.amp = QDoubleSpinBox()
                self.amp.setRange(0.0, 20.0)
                self.amp.setValue(5.0)
                self.phase = QDoubleSpinBox()
                self.phase.setRange(-10.0, 10.0)
                self.phase.setValue(0.0)
                self.n_u = QSpinBox()
                self.n_u.setRange(8, 200)
                self.n_u.setValue(60)
                self.n_v = QSpinBox()
                self.n_v.setRange(4, 100)
                self.n_v.setValue(30)
                layout.addRow("Base Radius", self.base_radius)
                layout.addRow("Height", self.height)
                layout.addRow("Frequency (Ï€â‚)", self.freq)
                layout.addRow("Amplitude", self.amp)
                layout.addRow("Phase", self.phase)
                layout.addRow("Segments U", self.n_u)
                layout.addRow("Segments V", self.n_v)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)

        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        base_radius = dlg.base_radius.value()
        height = dlg.height.value()
        freq = dlg.freq.value()
        amp = dlg.amp.value()
        phase = dlg.phase.value()
        n_u = dlg.n_u.value()
        n_v = dlg.n_v.value()
        feat = PiCurveShellFeature(base_radius, height, freq, amp, phase, n_u, n_v)
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(
            f"Pi Curve Shell created: r={base_radius}, h={height}, freq={freq}, amp={amp}", 3000
        )


# --- HELIX / SPIRAL SHAPE TOOL (Selectable, parametric) ---
class HelixFeature(Feature):
    def __init__(self, radius, pitch, height, n_points=250):
        params = {
            "radius": radius,
            "pitch": pitch,
            "height": height,
            "n_points": n_points,
        }
        shape = self._make_shape(params)
        super().__init__("Helix", params, shape)

    @staticmethod
    def _make_shape(params):
        import numpy as np

        if not HAS_OCC:
            return None
        from OCC.Core.BRepBuilderAPI import (  # type: ignore
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeWire,
        )
        from OCC.Core.gp import gp_Pnt  # type: ignore

        radius = params["radius"]
        pitch = params["pitch"]
        height = params["height"]
        n = int(params.get("n_points", 250))
        ts = np.linspace(0, 2 * np.pi * height / pitch, n)
        pts = [gp_Pnt(radius * np.cos(t), radius * np.sin(t), pitch * t / (2 * np.pi)) for t in ts]
        wire = BRepBuilderAPI_MakeWire()
        for a, b in zip(pts[:-1], pts[1:]):
            wire.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
        return wire.Wire()

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewHelixCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Helix / Spiral Parameters")
                layout = QFormLayout(self)
                self.radius = QDoubleSpinBox()
                self.radius.setRange(0.1, 1000)
                self.radius.setValue(20.0)
                self.pitch = QDoubleSpinBox()
                self.pitch.setRange(0.1, 1000)
                self.pitch.setValue(5.0)
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(40.0)
                self.n_points = QSpinBox()
                self.n_points.setRange(10, 2000)
                self.n_points.setValue(250)
                layout.addRow("Radius", self.radius)
                layout.addRow("Pitch", self.pitch)
                layout.addRow("Height", self.height)
                layout.addRow("Points", self.n_points)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)

        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        radius = dlg.radius.value()
        pitch = dlg.pitch.value()
        height = dlg.height.value()
        n_points = dlg.n_points.value()
        feat = HelixFeature(radius, pitch, height, n_points)
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(
            f"Helix created: radius={radius}, pitch={pitch}, height={height}", 3000
        )


class SuperellipseFeature(Feature):
    def __init__(self, rx, ry, n, segments=100):
        params = {"rx": rx, "ry": ry, "n": n, "segments": segments}
        shape = self._make_shape(params)
        super().__init__("Superellipse", params, shape)

    @staticmethod
    def _make_shape(params):
        import numpy as np

        if not HAS_OCC:
            return None
        from OCC.Core.BRepBuilderAPI import (  # type: ignore
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_MakeWire,
        )
        from OCC.Core.gp import gp_Pnt  # type: ignore

        rx = params["rx"]
        ry = params["ry"]
        n = params["n"]
        segments = params["segments"]

        # Generate points for superellipse: |x/rx|^n + |y/ry|^n = 1
        ts = np.linspace(0, 2 * np.pi, segments)
        # Convert parametric equations for superellipse
        pts = []
        for t in ts:
            # Parametric form with power of 2/n
            cos_t = np.cos(t)
            sin_t = np.sin(t)
            cos_t_abs = abs(cos_t)
            sin_t_abs = abs(sin_t)

            # Handle zero case to avoid division by zero
            if cos_t_abs < 1e-10:
                x = 0
            else:
                x = rx * np.sign(cos_t) * (cos_t_abs ** (2 / n))

            if sin_t_abs < 1e-10:
                y = 0
            else:
                y = ry * np.sign(sin_t) * (sin_t_abs ** (2 / n))

            pts.append(gp_Pnt(x, y, 0))

        # Create a wire from the points
        wire = BRepBuilderAPI_MakeWire()
        for i in range(segments):
            p1 = pts[i]
            p2 = pts[(i + 1) % segments]
            if p1.Distance(p2) > 1e-7:
                edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
                wire.Add(edge)

        # Create a face from the wire
        face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewSuperellipseCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Superellipse Parameters")
                layout = QFormLayout(self)

                self.rx = QDoubleSpinBox()
                self.rx.setRange(0.1, 1000)
                self.rx.setValue(25.0)

                self.ry = QDoubleSpinBox()
                self.ry.setRange(0.1, 1000)
                self.ry.setValue(15.0)

                self.n = QDoubleSpinBox()
                self.n.setRange(0.1, 10.0)
                self.n.setValue(2.5)
                self.n.setSingleStep(0.1)

                self.segments = QSpinBox()
                self.segments.setRange(12, 200)
                self.segments.setValue(60)

                layout.addRow("X Radius:", self.rx)
                layout.addRow("Y Radius:", self.ry)
                layout.addRow("Exponent (n):", self.n)
                layout.addRow("Segments:", self.segments)

                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)

        dlg = ParamDialog(mw.win)
        if dlg.exec():
            rx = dlg.rx.value()
            ry = dlg.ry.value()
            n = dlg.n.value()
            segments = dlg.segments.value()

            feat = SuperellipseFeature(rx, ry, n, segments)
            try:
                from adaptivecad.command_defs import DOCUMENT

                DOCUMENT.append(feat)
            except Exception:
                pass

            mw.view._display.EraseAll()
            mw.view._display.DisplayShape(feat.shape, update=True)
            mw.view._display.FitAll()
            mw.win.statusBar().showMessage(f"Superellipse created: rx={rx}, ry={ry}, n={n}", 3000)


# --- TAPERED CYLINDER / CONE SHAPE TOOL ---
class TaperedCylinderFeature(Feature):
    def __init__(self, height, radius1, radius2):
        params = {
            "height": height,
            "radius1": radius1,
            "radius2": radius2,
        }
        shape = self._make_shape(params)
        super().__init__("Tapered Cylinder", params, shape)

    @staticmethod
    def _make_shape(params):
        if not HAS_OCC:
            return None
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone  # type: ignore

        height = params["height"]
        radius1 = params["radius1"]
        radius2 = params["radius2"]
        # OCC expects bottom radius, top radius, height
        return BRepPrimAPI_MakeCone(radius1, radius2, height).Shape()

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewTaperedCylinderCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Tapered Cylinder / Cone Parameters")
                layout = QFormLayout(self)
                self.height = QDoubleSpinBox()
                self.height.setRange(1, 1000)
                self.height.setValue(40.0)
                self.radius1 = QDoubleSpinBox()
                self.radius1.setRange(0, 1000)
                self.radius1.setValue(10.0)
                self.radius2 = QDoubleSpinBox()
                self.radius2.setRange(0, 1000)
                self.radius2.setValue(5.0)
                layout.addRow("Height", self.height)
                layout.addRow("Bottom Radius", self.radius1)
                layout.addRow("Top Radius", self.radius2)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)

        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        height = dlg.height.value()
        radius1 = dlg.radius1.value()
        radius2 = dlg.radius2.value()
        feat = TaperedCylinderFeature(height, radius1, radius2)
        # Add to document if available
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(
            f"Tapered Cylinder created: h={height}, r1={radius1}, r2={radius2}", 3000
        )


# --- CAPSULE / PILL SHAPE TOOL (Selectable, like other shapes) ---
class CapsuleFeature(Feature):
    def __init__(self, height, radius):
        params = {
            "height": height,
            "radius": radius,
        }
        shape = self._make_shape(params)
        super().__init__("Capsule", params, shape)

    @staticmethod
    def _make_shape(params):
        if not HAS_OCC:
            return None
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse  # type: ignore
        from OCC.Core.BRepPrimAPI import (  # type: ignore
            BRepPrimAPI_MakeCylinder,
            BRepPrimAPI_MakeSphere,
        )
        from OCC.Core.gp import gp_Pnt  # type: ignore

        height = params["height"]
        radius = params["radius"]
        cyl_height = max(0.0, height - 2 * radius)
        cyl = BRepPrimAPI_MakeCylinder(radius, cyl_height).Shape()
        sph1 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), radius, 0, 0.5 * 3.141592653589793).Shape()
        sph2 = BRepPrimAPI_MakeSphere(
            gp_Pnt(0, 0, cyl_height), radius, 0.5 * 3.141592653589793, 3.141592653589793
        ).Shape()
        fuse1 = BRepAlgoAPI_Fuse(cyl, sph1).Shape()
        capsule = BRepAlgoAPI_Fuse(fuse1, sph2).Shape()
        return capsule

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewCapsuleCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Capsule / Pill Parameters")
                layout = QFormLayout(self)
                self.height = QDoubleSpinBox()
                self.height.setRange(1, 1000)
                self.height.setValue(40.0)
                self.radius = QDoubleSpinBox()
                self.radius.setRange(0.1, 1000)
                self.radius.setValue(10.0)
                layout.addRow("Height", self.height)
                layout.addRow("Radius", self.radius)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)

        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        height = dlg.height.value()
        radius = dlg.radius.value()
        feat = CapsuleFeature(height, radius)
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Capsule created: height={height}, radius={radius}", 3000)


# --- ELLIPSOID SHAPE TOOL (Selectable, like other shapes) ---
class EllipsoidFeature(Feature):
    def __init__(self, rx, ry, rz):
        params = {
            "rx": rx,
            "ry": ry,
            "rz": rz,
        }
        shape = self._make_shape(params)
        super().__init__("Ellipsoid", params, shape)

    @staticmethod
    def _make_shape(params):
        if not HAS_OCC:
            return None
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform  # type: ignore
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere  # type: ignore
        from OCC.Core.gp import (
            gp_Pnt,  # type: ignore
            gp_Trsf,  # type: ignore
        )

        rx = params["rx"]
        ry = params["ry"]
        rz = params["rz"]
        sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 1.0).Shape()
        trsf = gp_Trsf()
        trsf.SetValues(rx, 0, 0, 0, 0, ry, 0, 0, 0, 0, rz, 0)
        ellipsoid = BRepBuilderAPI_Transform(sphere, trsf, True).Shape()
        return ellipsoid

    def rebuild(self):
        self.shape = self._make_shape(self.params)


class NewEllipsoidCmd:
    def __init__(self):
        pass

    def run(self, mw):
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Ellipsoid Parameters")
                layout = QFormLayout(self)
                self.rx = QDoubleSpinBox()
                self.rx.setRange(0.1, 1000)
                self.rx.setValue(20.0)
                self.ry = QDoubleSpinBox()
                self.ry.setRange(0.1, 1000)
                self.ry.setValue(10.0)
                self.rz = QDoubleSpinBox()
                self.rz.setRange(0.1, 1000)
                self.rz.setValue(5.0)
                layout.addRow("Radius X", self.rx)
                layout.addRow("Radius Y", self.ry)
                layout.addRow("Radius Z", self.rz)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)

        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        rx = dlg.rx.value()
        ry = dlg.ry.value()
        rz = dlg.rz.value()
        feat = EllipsoidFeature(rx, ry, rz)
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Ellipsoid created: rx={rx}, ry={ry}, rz={rz}", 3000)


# --- ANALYTIC (SDF/Ï€â‚) BALL DOCK + COMMAND ---
if HAS_QT and QDockWidget:

    class SDFAnalyticBallDock(QDockWidget):
        """Docked viewer that renders a triangle-free analytic ball (SDF) with optional Ï€â‚ scaling."""

        def __init__(self, mw):
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

            super().__init__("Analytic Ball (SDF/Ï€â‚)", mw.win)
            self.setObjectName("SDFAnalyticBallDock")
            self.mw = mw
            self._res = 512
            self._r = 20.0
            self._beta = 0.0

            container = QWidget()
            v = QVBoxLayout(container)
            self.image_label = QLabel("(renderingâ€¦)")
            self.image_label.setAlignment(Qt.AlignCenter)
            v.addWidget(self.image_label)

            row_r = QWidget()
            hr = QHBoxLayout(row_r)
            hr.setContentsMargins(0, 0, 0, 0)
            hr.addWidget(QLabel("Radius r:"))
            self.slider_r = QSlider(Qt.Horizontal)
            self.slider_r.setRange(1, 400)
            self.slider_r.setValue(int(self._r))
            self.slider_r.valueChanged.connect(self._on_change)
            hr.addWidget(self.slider_r)
            v.addWidget(row_r)

            row_b = QWidget()
            hb = QHBoxLayout(row_b)
            hb.setContentsMargins(0, 0, 0, 0)
            hb.addWidget(QLabel("Ï€â‚ Î²:"))
            self.slider_b = QSlider(Qt.Horizontal)
            self.slider_b.setRange(0, 200)
            self.slider_b.setValue(int(self._beta * 100))
            self.slider_b.valueChanged.connect(self._on_change)
            hb.addWidget(self.slider_b)
            v.addWidget(row_b)

            self.setWidget(container)
            self._render_and_set()

        @staticmethod
        def _pia_radius(r, beta):
            kappa = 0.25 * beta
            return float(r * (1.0 + 0.5 * kappa * r * r))

        def _on_change(self, *_):
            self._r = float(self.slider_r.value())
            self._beta = float(self.slider_b.value()) / 100.0
            self._render_and_set()

        def _render_and_set(self):
            import numpy as np
            from PySide6.QtGui import QImage, QPixmap

            res = self._res
            r = max(1.0, self._r)
            beta = max(0.0, self._beta)
            re = self._pia_radius(r, beta)
            span = 1.6 * re
            xs = np.linspace(-span, span, res)
            ys = np.linspace(-span, span, res)
            X, Y = np.meshgrid(xs, ys)
            D = np.sqrt(X * X + Y * Y) - re
            band = np.clip(0.5 - D / (span / res * 2.0), 0.0, 1.0)
            img = (255 * (1.0 - band)).astype(np.uint8)
            qimg = QImage(img.data, res, res, QImage.Format_Grayscale8)
            self.image_label.setPixmap(QPixmap.fromImage(qimg))

else:
    SDFAnalyticBallDock = None  # type: ignore


class NewAnalyticBallCmd:
    """Open/focus the Analytic Ball dock (triangle-free renderer)."""

    def __init__(self):
        pass

    def run(self, mw):
        from PySide6.QtWidgets import QDockWidget

        dock = None
        for d in mw.win.findChildren(QDockWidget):
            if d.objectName() == "SDFAnalyticBallDock":
                dock = d
                break
        if dock is None:
            dock = SDFAnalyticBallDock(mw)
            mw.win.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.show()
        dock.raise_()


# --- ANALYTIC VIEWPORT COMMANDS ---
class NewAnalyticViewportCmd:
    """Creates a new analytic viewport using OpenGL/PyGLM-based renderer."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import Scene as AACoreScene
            from adaptivecad.gui.analytic_viewport import AnalyticViewport

            shared_scene = getattr(mw, "aacore_scene", None) or AACoreScene()
            mw.aacore_scene = shared_scene
            viewport = AnalyticViewport(aacore_scene=shared_scene)
            mw._analytic_viewport = viewport
            viewport.show()
        except Exception as e:
            log.exception("Failed to create analytic viewport: %s", e)


class NewAnalyticViewportPanelCmd:
    """Creates a new analytic viewport with control panel (panel version)."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.gui.analytic_viewport import AnalyticViewportPanel

            shared_scene = getattr(mw, "aacore_scene", None)
            panel = AnalyticViewportPanel(aacore_scene=shared_scene)
            panel.resize(1200, 800)
            panel.setMinimumSize(800, 500)
            panel.show()
            mw._analytic_viewport_panel = panel
            # Provide registry to panel for custom tools (if available)
            try:
                if getattr(mw, "_tool_registry", None) is not None and hasattr(
                    panel, "set_tool_registry"
                ):
                    panel.set_tool_registry(mw._tool_registry)
            except Exception:
                pass
            # optional sync if scene sync method exists
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.exception("Failed to create analytic viewport panel: %s", e)


class NewAnalyticSphereCmd:
    """Creates a new analytic sphere in the scene."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import KIND_SPHERE, Prim

            sc = getattr(mw, "aacore_scene", None)
            if sc is None:
                from adaptivecad.aacore.sdf import Scene as _Scene

                sc = _Scene()
                mw.aacore_scene = sc
            sc.add(Prim(KIND_SPHERE, [0.6, 0, 0, 0], beta=0.05, color=(0.9, 0.5, 0.4)))
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.error("Failed to create analytic sphere: %s", e)


class NewAnalyticBoxCmd:
    """Creates a new analytic box in the scene."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import KIND_BOX, Prim

            sc = getattr(mw, "aacore_scene", None)
            if sc is None:
                from adaptivecad.aacore.sdf import Scene as _Scene

                sc = _Scene()
                mw.aacore_scene = sc
            sc.add(Prim(KIND_BOX, [0.5, 0.5, 0.5, 0], beta=0.0, color=(0.4, 0.7, 0.9)))
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.error("Failed to create analytic box: %s", e)


class NewAnalyticCylinderCmd:
    """Creates a new analytic cylinder in the scene."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import KIND_CAPSULE, Prim

            sc = getattr(mw, "aacore_scene", None)
            if sc is None:
                from adaptivecad.aacore.sdf import Scene as _Scene

                sc = _Scene()
                mw.aacore_scene = sc
            sc.add(Prim(KIND_CAPSULE, [0.3, 1.5, 0, 0], beta=0.02, color=(0.6, 0.9, 0.5)))
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.error("Failed to create analytic cylinder: %s", e)


class NewAnalyticCapsuleCmd:
    """Creates a new analytic capsule in the scene."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import KIND_CAPSULE, Prim

            sc = getattr(mw, "aacore_scene", None)
            if sc is None:
                from adaptivecad.aacore.sdf import Scene as _Scene

                sc = _Scene()
                mw.aacore_scene = sc
            sc.add(Prim(KIND_CAPSULE, [0.3, 1.5, 0, 0], beta=0.02, color=(0.6, 0.9, 0.5)))
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.error("Failed to create analytic capsule: %s", e)


class NewAnalyticTorusCmd:
    """Creates a new analytic torus in the scene."""

    def __init__(self):
        pass

    def run(self, mw):
        try:
            from adaptivecad.aacore.sdf import KIND_TORUS, Prim

            sc = getattr(mw, "aacore_scene", None)
            if sc is None:
                from adaptivecad.aacore.sdf import Scene as _Scene

                sc = _Scene()
                mw.aacore_scene = sc
            sc.add(Prim(KIND_TORUS, [0.9, 0.25, 0, 0], beta=0.03, color=(0.8, 0.6, 0.4)))
            if hasattr(mw, "_sync_analytic_scene"):
                mw._sync_analytic_scene()
        except Exception as e:
            log.error("Failed to create analytic torus: %s", e)

    class NewAnalyticMobiusCmd:
        """Creates a new analytic MÃ¶bius strip in the scene."""

        def __init__(self):
            pass

        def run(self, mw):
            try:
                from adaptivecad.aacore.sdf import KIND_MOBIUS, Prim

                sc = getattr(mw, "aacore_scene", None)
                if sc is None:
                    from adaptivecad.aacore.sdf import Scene as _Scene

                    sc = _Scene()
                    mw.aacore_scene = sc
                # params: [major_radius, width, 0, 0]
                sc.add(Prim(KIND_MOBIUS, [0.9, 0.25, 0, 0], beta=0.02, color=(0.6, 0.8, 0.6)))
                if hasattr(mw, "_sync_analytic_scene"):
                    mw._sync_analytic_scene()
            except Exception as e:
                log.error("Failed to create analytic mobius: %s", e)


# --- PROJECT MANAGEMENT COMMANDS ---
class SaveProjectCmd:
    def __init__(self):
        pass

    def run(self, mw):
        try:
            import json
            import os

            from PySide6.QtWidgets import QFileDialog

            from adaptivecad.command_defs import DOCUMENT

            if not DOCUMENT:
                mw.win.statusBar().showMessage("No shapes in document to save", 3000)
                return

            # Get save location
            path, _filter = QFileDialog.getSaveFileName(
                mw.win,
                "Save AdaptiveCAD Project",
                filter="AdaptiveCAD Project (*.acad);;JSON Files (*.json)",
            )
            if not path:
                return

            # Create project data structure
            project_data = {"version": "1.0", "type": "AdaptiveCAD Project", "features": [], "sketch": {}}

            # Save each feature's data
            for idx, feat in enumerate(DOCUMENT):
                feature_data = {
                    "id": idx,
                    "name": feat.name,
                    "params": feat.params,
                    "type": type(feat).__name__,
                }
                project_data["features"].append(feature_data)

            # Save sketch data if available
            if hasattr(mw, '_sketch_to_dict'):
                project_data["sketch"] = mw._sketch_to_dict()

            # Write project file
            with open(path, "w") as f:
                json.dump(project_data, f, indent=2)

            mw.win.statusBar().showMessage(f"Project saved: {os.path.basename(path)}", 3000)

        except Exception as e:
            mw.win.statusBar().showMessage(f"Error saving project: {str(e)}", 5000)
            print(f"Save project error: {str(e)}")


class OpenProjectCmd:
    def __init__(self):
        pass

    def run(self, mw):
        try:
            import json
            import os

            from PySide6.QtWidgets import QFileDialog, QMessageBox

            from adaptivecad.command_defs import DOCUMENT

            # Get file to open
            path, _filter = QFileDialog.getOpenFileName(
                mw.win,
                "Open AdaptiveCAD Project",
                filter="AdaptiveCAD Project (*.acad);;JSON Files (*.json);;All Files (*.*)",
            )
            if not path:
                return

            if not os.path.exists(path):
                QMessageBox.warning(mw.win, "File Not Found", f"Could not find file: {path}")
                return

            # Ask if user wants to clear current document
            if DOCUMENT:
                reply = QMessageBox.question(
                    mw.win,
                    "Clear Current Project?",
                    "Opening a project will replace the current shapes. Continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return

            # Load project file
            with open(path, "r") as f:
                project_data = json.load(f)

            # Clear current document
            DOCUMENT.clear()
            mw.view._display.EraseAll()

            # Recreate features from project data
            features_loaded = 0
            for feat_data in project_data.get("features", []):
                try:
                    feat_type = feat_data.get("type", "")
                    feat_name = feat_data.get("name", "Unknown")
                    feat_params = feat_data.get("params", {})

                    # Try to recreate the feature based on its type
                    feature = None
                    if feat_type == "SuperellipseFeature":
                        feature = SuperellipseFeature(
                            feat_params.get("rx", 25.0),
                            feat_params.get("ry", 15.0),
                            feat_params.get("n", 2.5),
                            feat_params.get("segments", 60),
                        )
                    elif feat_type == "PiCurveShellFeature":
                        feature = PiCurveShellFeature(
                            feat_params.get("base_radius", 20.0),
                            feat_params.get("height", 40.0),
                            feat_params.get("freq", 3.0),
                            feat_params.get("amp", 5.0),
                            feat_params.get("phase", 0.0),
                            feat_params.get("n_u", 60),
                            feat_params.get("n_v", 30),
                        )
                    elif feat_type == "HelixFeature":
                        feature = HelixFeature(
                            feat_params.get("radius", 20.0),
                            feat_params.get("pitch", 5.0),
                            feat_params.get("height", 40.0),
                            feat_params.get("n_points", 250),
                        )
                    elif feat_type == "TaperedCylinderFeature":
                        feature = TaperedCylinderFeature(
                            feat_params.get("height", 40.0),
                            feat_params.get("radius1", 10.0),
                            feat_params.get("radius2", 5.0),
                        )
                    elif feat_type == "CapsuleFeature":
                        feature = CapsuleFeature(
                            feat_params.get("height", 40.0), feat_params.get("radius", 10.0)
                        )
                    elif feat_type == "EllipsoidFeature":
                        feature = EllipsoidFeature(
                            feat_params.get("rx", 20.0),
                            feat_params.get("ry", 10.0),
                            feat_params.get("rz", 5.0),
                        )
                    # For basic shapes, we'll need to import them from command_defs
                    else:
                        # Try to create basic features using the existing command system
                        from adaptivecad.command_defs import Feature

                        # Create a generic feature - this won't have the actual shape
                        # but will preserve the parameter data
                        feature = Feature(feat_name, feat_params, None)

                    if feature:
                        DOCUMENT.append(feature)
                        if hasattr(feature, "shape") and feature.shape:
                            mw.view._display.DisplayShape(feature.shape, update=False)
                        features_loaded += 1

                except Exception as e:
                    print(f"Error loading feature {feat_data.get('name', 'Unknown')}: {e}")
                    continue

            # Update display
            mw.view._display.FitAll()

            # Load sketch data if available
            sketch_data = project_data.get("sketch", {})
            if sketch_data and hasattr(mw, '_sketch_from_dict'):
                try:
                    mw._sketch_from_dict(sketch_data)
                except Exception as e:
                    log.debug(f"Error loading sketch: {e}")

            mw.win.statusBar().showMessage(
                f"Project loaded: {os.path.basename(path)} ({features_loaded} features)", 3000
            )

        except json.JSONDecodeError as e:
            QMessageBox.critical(
                mw.win, "Invalid Project File", f"Could not parse project file: {str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                mw.win, "Error Loading Project", f"Error loading project: {str(e)}"
            )
            print(f"Open project error: {str(e)}")


# --- MAIN WINDOW AND APPLICATION ---
class MainWindow:
    def __init__(self, existing_app=None, *args, **kwargs):
        log.debug("MainWindow.__init__() called")
        if not HAS_GUI:
            log.warning("Qt not available. Cannot create MainWindow.")
            return

        log.debug("GUI dependencies available, initializing...")
        # Initialize the application, optionally using an existing instance
        self.app = existing_app or QApplication.instance() or QApplication([])

        # Initialize state variables
        self.selected_feature = None
        self.property_panel = None
        self.dimension_panel = None
        self.sketch = Sketch()
        self.sketch_summary_label = None
        self.chess_dock = None
        # Analytic viewport integration state
        self._analytic_panel = None  # AnalyticViewportPanel instance (when used as main)
        self._occ_central = None  # Original OCC/fallback central widget
        self._analytic_as_main = False  # Persistence flag
        # AI helper state (for simple OCC-backed actions)
        self._ai_profile_shape = None  # Last 2D profile (face) created by AI for extrusion
        self._ai_last_solid = None  # Last solid created by AI
        self._ai_pending_circle = None  # (cx, cy, r) when created in analytic mode
        self._ai_last_profile_meta = None  # Metadata for last sketch/profile handled by AI
        log.debug("State variables initialized")

        # Create the main window
        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD - Advanced Shapes & Modeling Tools")
        self.win.resize(1024, 768)
        # Apply dark theme to the main window
        self.win.setStyleSheet("""
        /* ── Main Window Base ── */
        QMainWindow { background-color: #1a1d23; color: #cdd6f4; }

        /* ── Menu Bar ── */
        QMenuBar {
            background-color: #11111b;
            color: #cdd6f4;
            border-bottom: 1px solid #313244;
            padding: 2px 0;
            font-size: 12px;
        }
        QMenuBar::item {
            background: transparent;
            padding: 4px 10px;
            border-radius: 4px;
        }
        QMenuBar::item:selected { background-color: #313244; }
        QMenuBar::item:pressed { background-color: #45475a; }

        /* ── Dropdown Menus ── */
        QMenu {
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 4px 0;
        }
        QMenu::item {
            padding: 5px 28px 5px 20px;
            border-radius: 4px;
            margin: 1px 4px;
        }
        QMenu::item:selected { background-color: #313244; }
        QMenu::item:disabled { color: #585b70; }
        QMenu::separator {
            height: 1px;
            background: #313244;
            margin: 4px 8px;
        }
        QMenu::indicator { width: 16px; height: 16px; margin-left: 4px; }

        /* ── Status Bar ── */
        QStatusBar {
            background-color: #11111b;
            color: #a6adc8;
            border-top: 1px solid #313244;
            font-size: 11px;
            padding: 2px 8px;
        }

        /* ── Dock Widgets ── */
        QDockWidget {
            color: #cdd6f4;
            titlebar-close-icon: none;
            titlebar-normal-icon: none;
        }
        QDockWidget::title {
            background-color: #1e1e2e;
            border: 1px solid #313244;
            padding: 6px;
            text-align: left;
        }

        /* ── General Inputs ── */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
            background-color: #11111b;
            border: 1px solid #313244;
            border-radius: 5px;
            padding: 4px 6px;
            color: #cdd6f4;
            selection-background-color: #45475a;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background-color: #1e1e2e;
            border: 1px solid #45475a;
            selection-background-color: #313244;
            color: #cdd6f4;
        }

        /* ── Buttons ── */
        QPushButton {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 5px 12px;
            color: #cdd6f4;
        }
        QPushButton:hover { background-color: #45475a; }
        QPushButton:pressed { background-color: #181825; }
        QPushButton:disabled { color: #585b70; background-color: #1e1e2e; }

        /* ── Group Boxes ── */
        QGroupBox {
            border: 1px solid #313244;
            border-radius: 8px;
            margin-top: 14px;
            padding: 10px 6px 6px 6px;
            color: #cdd6f4;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: #89b4fa;
        }

        /* ── Labels ── */
        QLabel { color: #bac2de; }

        /* ── Checkboxes ── */
        QCheckBox { color: #cdd6f4; spacing: 6px; }
        QCheckBox::indicator {
            width: 16px; height: 16px;
            border-radius: 3px;
            border: 1px solid #45475a;
            background: #11111b;
        }
        QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }

        /* ── Sliders ── */
        QSlider::groove:horizontal { height: 6px; background: #313244; border-radius: 3px; }
        QSlider::handle:horizontal {
            width: 14px; height: 14px; margin: -4px 0;
            background: #89b4fa; border-radius: 7px;
        }
        QSlider::handle:horizontal:hover { background: #b4d0fb; }

        /* ── Scroll Bars ── */
        QScrollBar:vertical {
            width: 8px; background: #1a1d23; border: none;
        }
        QScrollBar::handle:vertical {
            background: #45475a; border-radius: 4px; min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background: #585b70; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal {
            height: 8px; background: #1a1d23; border: none;
        }
        QScrollBar::handle:horizontal {
            background: #45475a; border-radius: 4px; min-width: 20px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

        /* ── Tabs ── */
        QTabWidget::pane { border: 1px solid #313244; background: #1a1d23; }
        QTabBar::tab {
            background: #1e1e2e; border: 1px solid #313244;
            padding: 5px 10px; margin-right: 2px;
            border-top-left-radius: 4px; border-top-right-radius: 4px;
            color: #a6adc8;
        }
        QTabBar::tab:selected { background: #313244; color: #cdd6f4; }

        /* ── Tool Tips ── */
        QToolTip {
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 4px 8px;
        }
        """)
        log.debug("Main window created")

        # Create central widget with OCC viewer or fallback
        central = QWidget()
        layout = QVBoxLayout(central)
        if HAS_OCC:
            try:
                from OCC.Display.qtDisplay import qtViewer3d  # type: ignore

                self.view = qtViewer3d(central)
                layout.addWidget(self.view)
                # Initialize OCC view
                self.view._display.set_bg_gradient_color([50, 50, 50], [10, 10, 10])
                try:
                    self.view._display.display_triedron()
                except Exception:
                    pass
                try:
                    self.view._display.View.SetProj(1, 1, 1)
                    self.view._display.View.SetScale(300)
                except Exception:
                    pass
            except Exception as e:
                log.warning(f"Failed to initialize OCC viewer, using fallback: {e}")
                self.view = self._make_fallback_view(central, layout)
        else:
            self.view = self._make_fallback_view(central, layout)
        self.win.setCentralWidget(central)
        if getattr(self, "view", None) is not None:
            # Radial tool wheel: include common sketch + transform tools
            # (Playground keeps this empty; Analytic Viewport panel owns the wheel.)
            pass
        # Keep reference to original central widget for swapping
        self._occ_central = central

        self._ai_available_tools = [
            "select_tool",
            "create_line",
            "create_circle",
            "create_pi_circle",
            "upgrade_profile_to_pi_a",
            "extrude",
        ]
        self._ai_bus = CADActionBus()

        def _record_profile_meta(meta):
            """Store the latest profile metadata and return summary stats."""
            if meta is None:
                return {}
            self._ai_last_profile_meta = meta
            return {
                "metric": meta.get("metric"),
                "family": meta.get("family", ""),
                "points": len(meta.get("points", [])),
            }

        def _ai_select_tool(tool_id: str) -> dict:
            """Set a logical tool selection (visual only for now)."""
            log.info("AI copilot selecting tool: %s", tool_id)
            try:
                self.win.statusBar().showMessage(f"AI selected tool: {tool_id}", 2000)
            except Exception:
                pass
            return {"selected": tool_id}

        def _ai_create_circle(
            radius: float,
            cx: float | None = None,
            cy: float | None = None,
            segments: int = 256,
        ) -> dict:
            """Create a planar circular profile treated as a pi_a superellipse.
            - OCC mode: builds a Face and displays it; stores as profile for prism.
            - Analytic mode: draws a 2D overlay ring and stores pending (cx, cy, r).
            """
            log.info(
                "AI copilot create_circle radius=%s cx=%s cy=%s seg=%s", radius, cx, cy, segments
            )
            segs = int(segments) if segments is not None else 256
            if segs < 16:
                segs = 16
            if not HAS_OCC:
                try:
                    panel = self._ensure_analytic_panel()
                    if panel is None or not hasattr(panel, "view"):
                        raise RuntimeError("Analytic panel not available")
                    cxv = float(cx) if cx is not None else 0.0
                    cyv = float(cy) if cy is not None else 0.0
                    r = max(0.01, float(radius))
                    import math

                    pts = [
                        (
                            cxv + r * math.cos(2 * math.pi * i / segs),
                            cyv + r * math.sin(2 * math.pi * i / segs),
                        )
                        for i in range(segs + 1)
                    ]
                    if hasattr(panel.view, "add_polyline_overlay"):
                        panel.view.add_polyline_overlay(pts, color=(200, 220, 255), width=2)
                    self._ai_pending_circle = (cxv, cyv, r)
                    self._ai_profile_shape = None
                    self._ai_last_solid = None
                    meta = make_pi_circle_profile(r, cxv, cyv, segs)
                    stats = _record_profile_meta(meta)
                    try:
                        self.win.statusBar().showMessage(
                            f"AI: Circle overlay r={r:g} at ({cxv:g},{cyv:g})", 2500
                        )
                    except Exception:
                        pass
                    return {
                        "ok": True,
                        "profile": {
                            "type": "circle_overlay",
                            "radius": r,
                            "center": [cxv, cyv],
                            "metric": stats.get("metric"),
                            "family": stats.get("family", ""),
                            "points": stats.get("points", 0),
                        },
                    }
                except Exception as e:
                    log.debug(f"AI circle (analytic) failed: {e}")
                    return {"ok": False, "error": str(e)}
            if not hasattr(self, "view") or not hasattr(self.view, "_display"):
                msg = "Viewer not ready"
                try:
                    self.win.statusBar().showMessage(msg, 3000)
                except Exception:
                    pass
                return {"ok": False, "error": msg}
            try:
                from OCC.Core.BRepBuilderAPI import (  # type: ignore
                    BRepBuilderAPI_MakeEdge,
                    BRepBuilderAPI_MakeFace,
                    BRepBuilderAPI_MakeWire,
                )
                from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt  # type: ignore

                cxv = float(cx) if cx is not None else 0.0
                cyv = float(cy) if cy is not None else 0.0
                r = max(0.01, float(radius))
                circ = gp_Circ(gp_Ax2(gp_Pnt(cxv, cyv, 0.0), gp_Dir(0.0, 0.0, 1.0)), r)
                edge = BRepBuilderAPI_MakeEdge(circ).Edge()
                wire = BRepBuilderAPI_MakeWire(edge).Wire()
                face = BRepBuilderAPI_MakeFace(wire).Face()
                self.view._display.DisplayShape(face, update=True)
                self.view._display.FitAll()
                self._ai_profile_shape = face
                self._ai_pending_circle = (cxv, cyv, r)
                meta = make_pi_circle_profile(r, cxv, cyv, segs)
                stats = _record_profile_meta(meta)
                try:
                    self.win.statusBar().showMessage(
                        f"AI: Circle face r={r:g} at ({cxv:g},{cyv:g})", 2500
                    )
                except Exception:
                    pass
                return {
                    "ok": True,
                    "profile": {
                        "type": "circle_face",
                        "radius": r,
                        "center": [cxv, cyv],
                        "metric": stats.get("metric"),
                        "family": stats.get("family", ""),
                        "points": stats.get("points", 0),
                    },
                }
            except Exception as e:
                log.debug(f"AI circle create failed: {e}")
                return {"ok": False, "error": str(e)}

        def _ai_create_pi_circle(
            radius: float,
            cx: float | None = None,
            cy: float | None = None,
            segments: int = 256,
        ) -> dict:
            """Explicit pi_a circle helper that routes to _ai_create_circle."""
            return _ai_create_circle(radius=radius, cx=cx, cy=cy, segments=segments)

        def _ai_upgrade_profile_to_pi_a(profile_id: str | None = None) -> dict:
            """Ensure the last profile carries pi_a metadata."""
            if self._ai_last_profile_meta is None:
                return {"ok": False, "error": "no active/last profile"}
            upgraded = upgrade_profile_meta_to_pia(self._ai_last_profile_meta)
            stats = _record_profile_meta(upgraded)
            return {"ok": True, "profile": stats}

        def _ai_create_line(x1: float, y1: float, x2: float, y2: float) -> dict:
            """Create a straight 2D line.
            - OCC mode: displays an Edge at Z=0.
            - Analytic mode: draws a 2D overlay segment.
            """
            log.info("AI copilot create_line (%s,%s)->(%s,%s)", x1, y1, x2, y2)
            if not HAS_OCC:
                try:
                    panel = self._ensure_analytic_panel()
                    if panel is None or not hasattr(panel, "view"):
                        raise RuntimeError("Analytic panel not available")
                    pts = [(float(x1), float(y1)), (float(x2), float(y2))]
                    if hasattr(panel.view, "add_polyline_overlay"):
                        panel.view.add_polyline_overlay(pts, color=(255, 180, 90), width=3)
                    try:
                        self.win.statusBar().showMessage("AI: Line overlay created", 2000)
                    except Exception:
                        pass
                    return {
                        "ok": True,
                        "line": {"start": [float(x1), float(y1)], "end": [float(x2), float(y2)]},
                    }
                except Exception as e:
                    log.debug(f"AI line (analytic) failed: {e}")
                    return {"ok": False, "error": str(e)}
            # OCC path
            if not hasattr(self, "view") or not hasattr(self.view, "_display"):
                msg = "Viewer not ready"
                try:
                    self.win.statusBar().showMessage(msg, 3000)
                except Exception:
                    pass
                return {"ok": False, "error": msg}
            try:
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge  # type: ignore
                from OCC.Core.gp import gp_Pnt  # type: ignore

                p1 = gp_Pnt(float(x1), float(y1), 0.0)
                p2 = gp_Pnt(float(x2), float(y2), 0.0)
                edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
                self.view._display.DisplayShape(edge, update=True)
                self.view._display.Repaint()
                try:
                    self.win.statusBar().showMessage("AI: Line created", 2000)
                except Exception:
                    pass
                return {
                    "ok": True,
                    "line": {"start": [float(x1), float(y1)], "end": [float(x2), float(y2)]},
                }
            except Exception as e:
                log.debug(f"AI line create failed: {e}")
                return {"ok": False, "error": str(e)}

        def _ai_extrude(distance: float, metric: str | None = "pi_a") -> dict:
            """Extrude the last AI-created profile with pi_a awareness.
            - OCC mode: prisms the last Face.
            - Analytic mode: adds a capsule-like primitive.
            """
            log.info("AI copilot extrude distance=%s metric=%s", distance, metric)
            metric_value = metric or "pi_a"
            if isinstance(metric_value, str):
                metric_value = metric_value.lower()
            else:
                metric_value = "pi_a"
            if metric_value not in ("pi_a", "euclid"):
                metric_value = "pi_a"

            profile_meta = self._ai_last_profile_meta
            if profile_meta is None and self._ai_pending_circle is not None:
                cxv, cyv, rv = self._ai_pending_circle
                profile_meta = make_pi_circle_profile(rv, cxv, cyv)

            want_pia = metric_value == "pi_a" or (
                profile_meta and profile_meta.get("metric") == "pi_a"
            )
            if want_pia and profile_meta is not None and profile_meta.get("metric") != "pi_a":
                profile_meta = upgrade_profile_meta_to_pia(profile_meta)

            stats = _record_profile_meta(profile_meta) if profile_meta is not None else {}

            if not HAS_OCC:
                try:
                    if self._ai_pending_circle is None:
                        raise RuntimeError("No circle profile available to extrude")
                    cx, cy, r = self._ai_pending_circle
                    dz = float(distance)
                    from adaptivecad.aacore.sdf import KIND_CAPSULE, Prim

                    sc = getattr(self, "aacore_scene", None)
                    if sc is None:
                        from adaptivecad.aacore.sdf import Scene as _Scene

                        sc = _Scene()
                        self.aacore_scene = sc
                    prim = Prim(
                        KIND_CAPSULE,
                        [float(r), max(0.01, float(dz)), 0, 0],
                        beta=0.0,
                        color=(0.7, 0.8, 0.95),
                    )
                    sc.add(prim)
                    try:
                        if hasattr(prim, "xform") and hasattr(prim.xform, "translate"):
                            prim.xform.translate([float(cx), float(cy), 0.0])
                    except Exception:
                        pass
                    if hasattr(self, "_sync_analytic_scene"):
                        self._sync_analytic_scene()
                    panel = self._ensure_analytic_panel()
                    if panel:
                        panel.show()
                        panel.raise_()
                    self._ai_last_solid = prim
                    self._ai_profile_shape = None
                    self._ai_pending_circle = None
                    try:
                        self.win.statusBar().showMessage(f"AI: Analytic extrude by {dz:g}", 2500)
                    except Exception:
                        pass
                    return {
                        "ok": True,
                        "extruded": dz,
                        "mode": "analytic",
                        "metric": "pi_a" if want_pia else "euclid",
                        "profile": stats,
                    }
                except Exception as e:
                    log.debug(f"AI extrude (analytic) failed: {e}")
                    return {"ok": False, "error": str(e)}
            if not hasattr(self, "view") or not hasattr(self.view, "_display"):
                msg = "Viewer not ready"
                try:
                    self.win.statusBar().showMessage(msg, 3000)
                except Exception:
                    pass
                return {"ok": False, "error": msg}
            if getattr(self, "_ai_profile_shape", None) is None:
                msg = "No AI-created profile available to extrude. Create a circle first."
                try:
                    self.win.statusBar().showMessage(msg, 3000)
                except Exception:
                    pass
                return {"ok": False, "error": msg}
            try:
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism  # type: ignore
                from OCC.Core.gp import gp_Vec  # type: ignore

                dz = float(distance)
                vec = gp_Vec(0.0, 0.0, dz)
                solid = BRepPrimAPI_MakePrism(self._ai_profile_shape, vec).Shape()
                self.view._display.DisplayShape(solid, update=True)
                self.view._display.FitAll()
                self._ai_last_solid = solid
                self._ai_profile_shape = None
                try:
                    self.win.statusBar().showMessage(f"AI: Extruded by {dz:g}", 2500)
                except Exception:
                    pass
                return {
                    "ok": True,
                    "extruded": dz,
                    "mode": "occ",
                    "metric": "pi_a" if want_pia else "euclid",
                    "profile": stats,
                }
            except Exception as e:
                log.debug(f"AI extrude failed: {e}")
                return {"ok": False, "error": str(e)}

        self._ai_bus.on("select_tool", _ai_select_tool)
        self._ai_bus.on("create_circle", _ai_create_circle)
        self._ai_bus.on("create_pi_circle", _ai_create_pi_circle)
        self._ai_bus.on("upgrade_profile_to_pi_a", _ai_upgrade_profile_to_pi_a)
        self._ai_bus.on("create_line", _ai_create_line)
        self._ai_bus.on("extrude", _ai_extrude)
        # Custom tool registry + dock
        self._tool_registry = None
        if ToolRegistry is not None:
            try:
                self._tool_registry = ToolRegistry(self._ai_bus)
                if CustomToolsDock is not None:

                    def _run_tool_from_dock(tool_id: str):
                        try:
                            self._tool_registry.run(tool_id, parent_widget=self.win)  # type: ignore[union-attr]
                        except Exception:
                            pass

                    def _pin_changed(_tool_id: str, _pinned: bool):
                        try:
                            self._refresh_radial_wheel_pins()
                        except Exception:
                            pass

                    self.custom_tools_dock = CustomToolsDock(
                        self._tool_registry,
                        parent=self.win,
                        run_cb=_run_tool_from_dock,
                        pin_cb=_pin_changed,
                    )
                    self.win.addDockWidget(Qt.LeftDockWidgetArea, self.custom_tools_dock)
                    # Reflect changes in any analytic panel wheel
                    try:
                        self._tool_registry.changed.connect(self._refresh_radial_wheel_pins)
                    except Exception:
                        pass
                    # Populate wheel immediately if panel is open
                    try:
                        self._refresh_radial_wheel_pins()
                    except Exception:
                        pass
            except Exception:
                self._tool_registry = None

        try:
            self.ai_copilot = AICopilotDock(
                self.win,
                available_tools=self._ai_available_tools,
                bus=self._ai_bus,
                model="gpt-4o-mini",
                registry=self._tool_registry,
            )
            self.win.addDockWidget(Qt.RightDockWidgetArea, self.ai_copilot)
        except Exception as exc:
            log.debug("AI copilot dock unavailable: %s", exc)
            self.ai_copilot = None

        # Explicitly enable shape selection mode (fix for lost selection after repo update)
        if hasattr(self.view, "_display") and hasattr(self.view._display, "SetSelectionMode"):
            log.debug("Setting selection mode to 1 (shape selection mode)")
            self.view._display.SetSelectionMode(1)  # 1 = shape selection mode
        else:
            log.debug("Selection mode method not found on display object")

        # Extra initialization safety (idempotent)
        if HAS_OCC and hasattr(self.view, "_display"):
            try:
                self.view._display.set_bg_gradient_color([50, 50, 50], [10, 10, 10])
                self.view._display.display_triedron()
                self.view._display.View.SetProj(1, 1, 1)
                self.view._display.View.SetScale(300)
            except Exception:
                pass
            # Ensure selection mode enabled for shapes
            try:
                if hasattr(self.view._display, "EnableSelection"):
                    self.view._display.EnableSelection()
                elif hasattr(self.view._display, "SetSelectionModeFace"):
                    self.view._display.SetSelectionModeFace()
                elif hasattr(self.view._display, "Context") and hasattr(
                    self.view._display.Context, "ActivateStandardMode"
                ):
                    self.view._display.Context.ActivateStandardMode(0)
            except Exception as e:
                log.debug(f"Could not enable selection mode: {e}")

        # Initialize ViewCube
        if HAS_OCC and hasattr(self.view, "_display"):
            self.viewcube = ViewCubeWidget(self.view._display, self.view)
            self._position_viewcube()
            self.viewcube.show()
            self.setup_view_events()
        else:
            self.viewcube = None

        # Setup selection handling
        self._setup_selection_handling()

        # Shared AACore analytic scene
        try:
            from adaptivecad.aacore.sdf import KIND_CAPSULE, KIND_SPHERE, KIND_TORUS
            from adaptivecad.aacore.sdf import Prim as _Prim
            from adaptivecad.aacore.sdf import Scene as _AACoreScene

            self.aacore_scene = _AACoreScene()
        except Exception:
            self.aacore_scene = None

        # Setup UI menus and toolbar
        self._create_menus_and_toolbar()

        # Create status bar
        self.win.statusBar().showMessage("AdaptiveCAD Advanced Shapes & Modeling Tools Ready")

        # Show welcome screen on first run (deferred to after window is visible)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._show_welcome_if_first_run)

        # Load persisted analytic-main preference and apply if enabled
        try:
            prefs = self._load_analytic_prefs()
            if prefs.get("analytic_as_main"):
                from PySide6.QtCore import QTimer

                def _apply():
                    if hasattr(self, "_analytic_main_action"):
                        if getattr(self, "_analytic_panel", None) is None:
                            try:
                                from adaptivecad.gui.analytic_viewport import AnalyticViewportPanel

                                shared_scene = getattr(self, "aacore_scene", None)
                                self._analytic_panel = AnalyticViewportPanel(
                                    aacore_scene=shared_scene
                                )
                            except Exception as e:
                                log.debug(f"Failed to instantiate analytic panel on startup: {e}")
                                return
                        self._analytic_main_action.setChecked(True)
                        self._toggle_analytic_main(True)

                QTimer.singleShot(0, _apply)
        except Exception as e:
            log.debug(f"Could not apply persisted analytic preference: {e}")

    def _refresh_radial_wheel_pins(self):
        try:
            # AnalyticViewportPanel owns a wheel; if open, reflect pinned tools there
            panel = getattr(self, "_analytic_panel", None)
            if panel is None:
                return
            wheel = getattr(panel, "_radial_wheel", None)
            if wheel is None or self._tool_registry is None:
                return
            from adaptivecad.ui.radial_tool_wheel import ToolSpec

            base = [
                ToolSpec("Polyline", "polyline"),
                ToolSpec("Line", "line"),
                ToolSpec("Arc 3pt", "arc3"),
                ToolSpec("Circle", "circle"),
                ToolSpec("Rect", "rect"),
                ToolSpec("Insert Vtx", "insert_vertex"),
                ToolSpec("Dim", "dimension"),
                ToolSpec("Move", "move"),
                ToolSpec("Rotate", "rotate"),
                ToolSpec("Scale", "scale"),
                ToolSpec("Center", "center_selected"),
                ToolSpec("Reset", "reset_camera"),
                ToolSpec("Undo", "delete_last"),
                ToolSpec("Showcase", "showcase"),
                ToolSpec("Clear", "clear"),
            ]
            for m in self._tool_registry.pinned():
                label = (m.ui.get("icon_text") or m.name)[:10]
                base.append(ToolSpec(label, f"custom:{m.id}"))
            wheel.set_tools(base)
            # Ensure MainWindow intercepts custom:* tool activations
            try:
                if not getattr(wheel, "_custom_registry_handler", False):
                    wheel.toolActivated.connect(self._on_wheel_tool_from_main)
                    setattr(wheel, "_custom_registry_handler", True)
            except Exception:
                pass
        except Exception:
            pass

    def _on_wheel_tool_from_main(self, tool_id: str, _label: str):
        try:
            if not tool_id.startswith("custom:"):
                return
            if self._tool_registry is None:
                return
            tool_id_only = tool_id.split(":", 1)[-1]
            self._tool_registry.run(tool_id_only, parent_widget=self.win)  # type: ignore[union-attr]
        except Exception as e:
            try:
                log.debug(f"custom tool run failed: {e}")
            except Exception:
                pass

    def _setup_selection_handling(self):
        """Setup selection handling for objects in the 3D view."""
        if not HAS_OCC or not hasattr(self.view, "_display"):
            return
        try:
            # Unified selection callback setup
            def on_selection_changed(*_args, **_kwargs):
                self._on_object_selected()

            if hasattr(self.view._display, "register_select_callback"):
                self.view._display.register_select_callback(on_selection_changed)
            # Attempt enabling various selection modes (best-effort)
            for attr in ("SetSelectionModeVertex", "SetSelectionModeShape"):
                if hasattr(self.view._display, attr):
                    try:
                        getattr(self.view._display, attr)()
                    except Exception:
                        pass
        except Exception as e:
            log.debug(f"Could not setup selection handling: {e}")

    def _on_object_selected(self):
        """Handle object selection in the 3D view."""
        log.debug("_on_object_selected called")
        try:
            from adaptivecad.command_defs import DOCUMENT

            # Get selected objects from the display
            selected_shapes = self.view._display.GetSelectedShapes()
            log.debug(
                f"Selected shapes: {selected_shapes}; count={len(selected_shapes) if selected_shapes else 0}"
            )

            # Handle clicks on move arrows first
            if selected_shapes and hasattr(self, "arrow_shapes"):
                log.debug(
                    f"Checking for arrow selection. Arrow shapes: {list(self.arrow_shapes.keys()) if hasattr(self, 'arrow_shapes') else 'None'}"
                )
                for axis, info in self.arrow_shapes.items():
                    if info["shape"] in selected_shapes:
                        log.debug(f"Arrow {axis} selected; initiating move")
                        self._move_along_axis(axis)
                        self.view._display.Context.ClearSelected()
                        return

            if selected_shapes:
                log.debug(
                    f"Processing {len(selected_shapes)} selected shapes; DOCUMENT size={len(DOCUMENT)}"
                )
                # Find the feature that corresponds to the selected shape
                for i, feature in enumerate(DOCUMENT):
                    log.debug(f"Checking feature {i}: {feature.name}")
                    if hasattr(feature, "shape") and feature.shape in selected_shapes:
                        log.debug(f"Found matching feature: {feature.name}")
                        self.selected_feature = feature
                        self._update_property_panel(feature)
                        self._create_move_arrows(feature)
                        self.win.statusBar().showMessage(f"Selected: {feature.name}", 3000)
                        return

                # If no matching feature found, clear selection
                log.debug("No matching feature found for selected shapes")
                self.selected_feature = None
                self._clear_property_panel()
                self._remove_move_arrows()
            else:
                log.debug("No shapes selected; clearing")
                self.selected_feature = None
                self._clear_property_panel()
                self._remove_move_arrows()

        except Exception as e:
            log.error(f"Error handling selection: {e}")
            import traceback

            traceback.print_exc()

    def _update_property_panel(self, feature):
        """Update the property panel with the selected feature's properties."""
        if self.property_panel is None or not hasattr(self, "property_layout"):
            return

        # Clear existing property widgets
        self._clear_property_panel()

        # Add feature name
        name_label = QLabel(f"Selected: {feature.name}")
        name_label.setStyleSheet("font-weight: bold; color: blue; margin-bottom: 5px;")
        self.property_layout.insertWidget(2, name_label)

        # Add feature parameters
        if hasattr(feature, "params") and feature.params:
            params_label = QLabel("Parameters:")
            params_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            self.property_layout.insertWidget(3, params_label)

            # Create editable parameter fields
            for key, value in feature.params.items():
                if key == "consumed":  # Skip internal flags
                    continue

                param_widget = QWidget()
                param_layout = QHBoxLayout(param_widget)
                param_layout.setContentsMargins(0, 2, 0, 2)

                # Parameter name
                param_label = QLabel(f"{key}:")
                param_label.setMinimumWidth(80)
                param_layout.addWidget(param_label)
                # Parameter value (editable if numeric)
                if isinstance(value, (int, float)):
                    editor = QLineEdit(str(value))
                    editor.setMaximumWidth(100)

                    def make_param_setter(param_key, param_type):
                        def setter():
                            try:
                                new_value = param_type(editor.text())
                                feature.params[param_key] = new_value
                                # Rebuild the feature if it has a rebuild method
                                if hasattr(feature, "rebuild"):
                                    feature.rebuild()
                                # Update the display
                                if hasattr(self, "view") and hasattr(self.view, "_display"):
                                    from adaptivecad.command_defs import rebuild_scene

                                    rebuild_scene(self.view._display)
                                self.win.statusBar().showMessage(
                                    f"Updated {param_key} to {new_value}", 2000
                                )
                            except ValueError:
                                editor.setText(str(feature.params[param_key]))  # Revert on error
                                self.win.statusBar().showMessage(
                                    f"Invalid value for {param_key}", 2000
                                )

                        return setter

                    editor.editingFinished.connect(make_param_setter(key, type(value)))
                    param_layout.addWidget(editor)
                else:
                    # Non-editable display
                    value_label = QLabel(str(value))
                    value_label.setStyleSheet("color: gray;")
                    param_layout.addWidget(value_label)

                param_layout.addStretch()
                self.property_layout.insertWidget(self.property_layout.count() - 1, param_widget)

        # Add feature type info
        type_label = QLabel(f"Type: {type(feature).__name__}")
        type_label.setStyleSheet("color: gray; margin-top: 10px;")
        self.property_layout.insertWidget(self.property_layout.count() - 1, type_label)

    def _create_menus_and_toolbar(self):
        """Create all menus and toolbars with proper grouping and analytic mode support."""
        menubar = self.win.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        # New project action
        new_action = QAction("New Project", self.win)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)
        file_menu.addSeparator()

        import_menu = file_menu.addMenu("Import")
        import_simple_action = QAction("STL/STEP (with Progress)", self.win)
        import_simple_action.setShortcut("Ctrl+I")
        import_simple_action.triggered.connect(lambda: self._run_command(MinimalImportCmd()))
        import_menu.addAction(import_simple_action)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export")
        export_stl_action = QAction("Export STL", self.win)
        export_stl_action.setShortcut("Ctrl+E")
        export_stl_action.triggered.connect(lambda: self._run_command(ExportStlCmd()))
        export_menu.addAction(export_stl_action)
        export_ama_action = QAction("Export AMA", self.win)
        export_ama_action.triggered.connect(lambda: self._run_command(ExportAmaCmd()))
        export_menu.addAction(export_ama_action)
        export_gcode_action = QAction("Export G-Code", self.win)
        export_gcode_action.triggered.connect(lambda: self._run_command(ExportGCodeCmd()))
        export_menu.addAction(export_gcode_action)
        export_gcode_direct_action = QAction("Export G-Code (Direct)", self.win)
        export_gcode_direct_action.triggered.connect(
            lambda: self._run_command(ExportGCodeDirectCmd())
        )
        export_menu.addAction(export_gcode_direct_action)
        file_menu.addSeparator()
        save_action = QAction("Save Project...", self.win)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(lambda: self._run_command(SaveProjectCmd()))
        file_menu.addAction(save_action)
        open_action = QAction("Open Project...", self.win)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(lambda: self._run_command(OpenProjectCmd()))
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self.win)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.win.close)
        file_menu.addAction(exit_action)

        # Basic Shapes menu
        basic_menu = menubar.addMenu("Basic Shapes")
        box_action = QAction("Box", self.win)
        box_action.triggered.connect(lambda: self._run_command(NewBoxCmd()))
        basic_menu.addAction(box_action)
        cyl_action = QAction("Cylinder", self.win)
        cyl_action.triggered.connect(lambda: self._run_command(NewCylCmd()))
        basic_menu.addAction(cyl_action)
        ball_action = QAction("Ball", self.win)
        ball_action.triggered.connect(lambda: self._create_ball_via_backend(20.0))
        basic_menu.addAction(ball_action)
        analytic_ball_action = QAction("Analytic Ball (SDF/Ï€â‚)", self.win)
        analytic_ball_action.triggered.connect(lambda: self._run_command(NewAnalyticBallCmd()))
        basic_menu.addAction(analytic_ball_action)
        torus_action = QAction("Torus", self.win)
        torus_action.triggered.connect(lambda: self._run_command(NewTorusCmd()))
        basic_menu.addAction(torus_action)
        cone_action = QAction("Cone", self.win)
        cone_action.triggered.connect(lambda: self._run_command(NewConeCmd()))
        basic_menu.addAction(cone_action)

        # Advanced Shapes menu
        adv_menu = menubar.addMenu("Advanced Shapes")
        super_action = QAction("Superellipse", self.win)
        super_action.triggered.connect(lambda: self._run_command(NewSuperellipseCmd()))
        adv_menu.addAction(super_action)
        pi_shell_action = QAction("Pi Curve Shell (Ï€â‚)", self.win)
        pi_shell_action.triggered.connect(lambda: self._run_command(NewPiCurveShellCmd()))
        adv_menu.addAction(pi_shell_action)
        helix_action = QAction("Helix/Spiral", self.win)
        helix_action.triggered.connect(lambda: self._run_command(NewHelixCmd()))
        adv_menu.addAction(helix_action)
        tapered_action = QAction("Tapered Cylinder", self.win)
        tapered_action.triggered.connect(lambda: self._run_command(NewTaperedCylinderCmd()))
        adv_menu.addAction(tapered_action)
        capsule_action = QAction("Capsule/Pill", self.win)
        capsule_action.triggered.connect(lambda: self._run_command(NewCapsuleCmd()))
        adv_menu.addAction(capsule_action)
        ellipsoid_action = QAction("Ellipsoid", self.win)
        ellipsoid_action.triggered.connect(lambda: self._run_command(NewEllipsoidCmd()))
        adv_menu.addAction(ellipsoid_action)
        # Optionally add dynamic advanced tools if present
        for label, cmd_name in [
            ("ND Field", "NewFieldCmd"),
            ("B Curve", "NewBCurveCmd"),
            ("ND Spline", "NewNDSplineCmd"),
            ("ND Spline Surface", "NewNDSplineSurfaceCmd"),
        ]:
            try:
                cmd = getattr(__import__("adaptivecad.command_defs", fromlist=[cmd_name]), cmd_name)
                action = QAction(label, self.win)
                action.triggered.connect(lambda _=False, c=cmd: self._run_command(c()))
                adv_menu.addAction(action)
            except Exception:
                pass

        # Analytic Shapes menu
        analytic_menu = menubar.addMenu("Analytic Shapes")
        viewport_submenu = analytic_menu.addMenu("Viewport")
        analytic_viewport_action = QAction("New Analytic Viewport", self.win)
        analytic_viewport_action.triggered.connect(
            lambda: self._run_command(NewAnalyticViewportCmd())
        )
        viewport_submenu.addAction(analytic_viewport_action)
        sync_action = QAction("Auto-Sync with Main Viewport", self.win, checkable=True)
        sync_action.setChecked(True)

        def toggle_sync(checked):
            if hasattr(self, "_analytic_sync_timer"):
                (self._analytic_sync_timer.start() if checked else self._analytic_sync_timer.stop())

        sync_action.triggered.connect(toggle_sync)
        viewport_submenu.addAction(sync_action)
        analytic_menu.addSeparator()
        primitives_submenu = analytic_menu.addMenu("Add Primitives")
        analytic_sphere_action = QAction("Sphere", self.win)
        analytic_sphere_action.triggered.connect(lambda: self._run_command(NewAnalyticSphereCmd()))
        primitives_submenu.addAction(analytic_sphere_action)
        analytic_box_action = QAction("Box", self.win)
        analytic_box_action.triggered.connect(lambda: self._run_command(NewAnalyticBoxCmd()))
        primitives_submenu.addAction(analytic_box_action)
        analytic_cylinder_action = QAction("Cylinder", self.win)
        analytic_cylinder_action.triggered.connect(
            lambda: self._run_command(NewAnalyticCylinderCmd())
        )
        primitives_submenu.addAction(analytic_cylinder_action)
        analytic_capsule_action = QAction("Capsule", self.win)
        analytic_capsule_action.triggered.connect(
            lambda: self._run_command(NewAnalyticCapsuleCmd())
        )
        primitives_submenu.addAction(analytic_capsule_action)
        analytic_torus_action = QAction("Torus", self.win)
        analytic_torus_action.triggered.connect(lambda: self._run_command(NewAnalyticTorusCmd()))
        primitives_submenu.addAction(analytic_torus_action)
        utils_submenu = analytic_menu.addMenu("Utilities")
        mesh_to_analytic_action = QAction("Convert Mesh to Analytic", self.win)
        mesh_to_analytic_action.triggered.connect(
            lambda: self._run_command(ConvertMeshToAnalyticCmd())
        )
        utils_submenu.addAction(mesh_to_analytic_action)
        analytic_to_mesh_action = QAction("Convert Analytic to Mesh", self.win)
        analytic_to_mesh_action.triggered.connect(
            lambda: self._run_command(ConvertAnalyticToMeshCmd())
        )
        utils_submenu.addAction(analytic_to_mesh_action)

        # Modeling Tools menu
        modeling_menu = menubar.addMenu("Modeling Tools")
        move_action = QAction("Move", self.win)
        move_action.triggered.connect(lambda: self._run_command(MoveCmd()))
        modeling_menu.addAction(move_action)
        scale_action = QAction("Scale", self.win)
        scale_action.triggered.connect(lambda: self._run_command(ScaleCmd()))
        modeling_menu.addAction(scale_action)
        mirror_action = QAction("Mirror", self.win)
        mirror_action.triggered.connect(lambda: self._run_command(MirrorCmd()))
        modeling_menu.addAction(mirror_action)
        modeling_menu.addSeparator()
        union_action = QAction("Union", self.win)
        union_action.triggered.connect(lambda: self._run_command(UnionCmd()))
        modeling_menu.addAction(union_action)
        cut_action = QAction("Cut", self.win)
        cut_action.triggered.connect(lambda: self._run_command(CutCmd()))
        modeling_menu.addAction(cut_action)
        intersect_action = QAction("Intersect", self.win)
        intersect_action.triggered.connect(lambda: self._run_command(IntersectCmd()))
        modeling_menu.addAction(intersect_action)
        shell_action = QAction("Shell", self.win)
        shell_action.triggered.connect(lambda: self._run_command(ShellCmd()))
        modeling_menu.addAction(shell_action)
        modeling_menu.addSeparator()
        delete_action = QAction("Delete", self.win)
        delete_action.setShortcut("Del")
        delete_action.triggered.connect(self._delete_selected)
        modeling_menu.addAction(delete_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        view_menu = settings_menu.addMenu("View")
        properties_action = QAction("Show Properties Panel", self.win, checkable=True)
        properties_action.setChecked(False)
        properties_action.triggered.connect(self._toggle_properties_panel)
        view_menu.addAction(properties_action)
        dimension_action = QAction("Show Dimension Selector", self.win, checkable=True)
        dimension_action.setChecked(False)
        dimension_action.triggered.connect(self._toggle_dimension_panel)
        view_menu.addAction(dimension_action)
        # Show/Hide AI Copilot dock
        ai_view_action = QAction("Show AI Copilot", self.win, checkable=True)
        ai_view_action.setChecked(bool(getattr(self, "ai_copilot", None)))

        def _toggle_ai(checked: bool):
            dock = getattr(self, "ai_copilot", None)
            if not dock:
                try:
                    self.win.statusBar().showMessage(
                        "AI Copilot unavailable (missing dependencies or init error)", 3000
                    )
                except Exception:
                    pass
                ai_view_action.setChecked(False)
                return
            dock.setVisible(bool(checked))
            if checked:
                dock.raise_()

        ai_view_action.triggered.connect(_toggle_ai)
        view_menu.addAction(ai_view_action)
        view_menu.addAction(
            QAction(
                "Show Analytic Viewport",
                self.win,
                triggered=lambda: self._run_command(NewAnalyticViewportCmd()),
            )
        )
        view_menu.addAction(
            QAction(
                "Show Analytic Viewport (Panel)",
                self.win,
                triggered=lambda: self._run_command(NewAnalyticViewportPanelCmd()),
            )
        )
        view_menu.addSeparator()
        self._analytic_main_action = QAction(
            "Use Analytic Viewport as Main", self.win, checkable=True
        )
        self._analytic_main_action.setChecked(False)
        self._analytic_main_action.triggered.connect(self._toggle_analytic_main)
        view_menu.addAction(self._analytic_main_action)
        viewcube_action = QAction("Show View Cube", self.win, checkable=True)
        viewcube_action.setChecked(True)
        viewcube_action.triggered.connect(lambda checked: self.viewcube.setVisible(checked))
        view_menu.addAction(viewcube_action)
        grid_view_action = QAction("Show Grid", self.win, checkable=True)
        grid_view_action.setChecked(False)
        grid_view_action.triggered.connect(self._toggle_grid_display)
        view_menu.addAction(grid_view_action)
        view_bg_menu = view_menu.addMenu("Background Color")
        bg_dark_action = QAction("Dark", self.win)
        bg_dark_action.triggered.connect(
            lambda: self.view._display.set_bg_gradient_color([50, 50, 50], [10, 10, 10])
        )
        view_bg_menu.addAction(bg_dark_action)
        bg_light_action = QAction("Light", self.win)
        bg_light_action.triggered.connect(
            lambda: self.view._display.set_bg_gradient_color([230, 230, 230], [200, 200, 200])
        )
        view_bg_menu.addAction(bg_light_action)
        bg_blue_action = QAction("Blue", self.win)
        bg_blue_action.triggered.connect(
            lambda: self.view._display.set_bg_gradient_color([5, 20, 76], [5, 39, 175])
        )
        view_bg_menu.addAction(bg_blue_action)
        tessellation_menu = settings_menu.addMenu("Tessellation Quality")

        def set_tessellation(deflection, angle):
            settings.MESH_DEFLECTION = deflection
            settings.MESH_ANGLE = angle
            self.win.statusBar().showMessage(
                f"Tessellation set to: deflection={deflection}, angle={angle}", 3000
            )

        high_quality = QAction("High Quality", self.win)
        high_quality.triggered.connect(lambda: set_tessellation(0.005, 0.01))
        tessellation_menu.addAction(high_quality)
        normal_quality = QAction("Normal Quality", self.win)
        normal_quality.triggered.connect(lambda: set_tessellation(0.01, 0.05))
        tessellation_menu.addAction(normal_quality)
        low_quality = QAction("Low Quality (Faster)", self.win)
        low_quality.triggered.connect(lambda: set_tessellation(0.05, 0.1))
        tessellation_menu.addAction(low_quality)
        triedron_action = QAction("Show Axes Indicator", self.win, checkable=True)
        triedron_action.setChecked(True)

        def _toggle_triedron(checked):
            disp = getattr(self.view, "_display", None)
            if not disp:
                return
            show_fn = getattr(disp, "display_triedron", None)
            hide_fn = getattr(disp, "hide_triedron", None)
            try:
                (
                    show_fn()
                    if checked and callable(show_fn)
                    else hide_fn() if callable(hide_fn) else None
                )
            except Exception:
                pass

        triedron_action.triggered.connect(_toggle_triedron)
        view_menu.addAction(triedron_action)

        # Clear Analytic Overlays
        def _clear_overlays():
            try:
                panel = self._ensure_analytic_panel()
                if panel is None:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self.win, "Analytic Overlays", "Analytic panel not open."
                    )
                    return
                if hasattr(panel, "view") and hasattr(panel.view, "clear_polyline_overlays"):
                    panel.view.clear_polyline_overlays()
                    self.win.statusBar().showMessage("Cleared analytic overlays", 2000)
            except Exception as e:
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self.win, "Analytic Overlays", f"Could not clear overlays: {e}"
                    )
                except Exception:
                    pass

        clear_overlay_action = QAction("Clear Analytic Overlays", self.win)
        clear_overlay_action.triggered.connect(_clear_overlays)
        view_menu.addAction(clear_overlay_action)
        backend_menu = settings_menu.addMenu("Rendering Backend")
        use_analytic_action = QAction(
            "Use Analytic/SDF for default shapes", self.win, checkable=True
        )
        use_analytic_action.setChecked(settings.USE_ANALYTIC_BACKEND)
        use_analytic_action.triggered.connect(
            lambda chk: (
                setattr(settings, "USE_ANALYTIC_BACKEND", bool(chk)),
                self.win.statusBar().showMessage(
                    f"Analytic backend: {'ON' if chk else 'OFF'}", 3000
                ),
            )
        )
        backend_menu.addAction(use_analytic_action)

        # Toolbars
        self.toolbar_occ = self.win.addToolBar("Common Shapes")
        self.toolbar_occ.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # Add tooltips and better organization
        box_action.setToolTip("Create a box/cube (Shortcut: B)")
        self.toolbar_occ.addAction(box_action)
        cyl_action.setToolTip("Create a cylinder (Shortcut: C)")
        self.toolbar_occ.addAction(cyl_action)
        ball_action.setToolTip("Create a sphere (Shortcut: S)")
        self.toolbar_occ.addAction(ball_action)
        analytic_ball_action.setToolTip("Create an analytic sphere using SDF (Shortcut: Shift+S)")
        self.toolbar_occ.addAction(analytic_ball_action)

        self.toolbar_occ.addSeparator()
        super_action.setToolTip("Create a superellipse with adjustable parameters")
        self.toolbar_occ.addAction(super_action)
        pi_shell_action.setToolTip("Create a Pi Curve Shell using adaptive geometry")
        self.toolbar_occ.addAction(pi_shell_action)

        self.toolbar_occ.addSeparator()
        move_action.setToolTip("Move selected objects")
        self.toolbar_occ.addAction(move_action)
        mirror_action.setToolTip("Mirror selected objects")
        self.toolbar_occ.addAction(mirror_action)
        union_action.setToolTip("Union/combine selected objects")
        self.toolbar_occ.addAction(union_action)
        cut_action.setToolTip("Cut/subtract objects")
        self.toolbar_occ.addAction(cut_action)
        delete_action.setToolTip("Delete selected objects (Del)")
        self.toolbar_occ.addAction(delete_action)

        self.toolbar_analytic = self.win.addToolBar("Analytic Quick")
        analytic_view_quick = QAction("Analytic View", self.win)
        analytic_view_quick.triggered.connect(lambda: self._run_command(NewAnalyticViewportCmd()))
        analytic_view_panel_quick = QAction("Analytic Panel", self.win)
        analytic_view_panel_quick.triggered.connect(
            lambda: self._run_command(NewAnalyticViewportPanelCmd())
        )
        self.toolbar_analytic.addAction(analytic_view_quick)
        self.toolbar_analytic.addAction(analytic_view_panel_quick)
        self.toolbar_analytic.addSeparator()
        for act in [
            QAction("Sphere", self.win),
            QAction("Box", self.win),
            QAction("Cylinder", self.win),
            QAction("Capsule", self.win),
            QAction("Torus", self.win),
        ]:
            # Map actions to commands
            mapper = {
                "Sphere": NewAnalyticSphereCmd,
                "Box": NewAnalyticBoxCmd,
                "Cylinder": NewAnalyticCylinderCmd,
                "Capsule": NewAnalyticCapsuleCmd,
                "Torus": NewAnalyticTorusCmd,
            }
            act.triggered.connect(
                lambda _=False, name=act.text(): self._run_command(mapper[name]())
            )
            self.toolbar_analytic.addAction(act)
        self.toolbar_analytic.addSeparator()
        a_export_act = QAction("Export SDFâ†’STL", self.win)
        a_export_act.triggered.connect(lambda: self._run_command(ConvertAnalyticToMeshCmd()))
        self.toolbar_analytic.addAction(a_export_act)
        self.toolbar_analytic.setVisible(False)

        # Games / Help / Conversion / Docs
        games_menu = menubar.addMenu("Games")
        chess_action = QAction("Play 4D Chess", self.win)
        chess_action.triggered.connect(self._open_chess_widget)
        games_menu.addAction(chess_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About AdaptiveCAD", self.win)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        def _require(cap_fn, ok_fn, msg: str):
            if cap_fn():
                return ok_fn()
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self.win, "Feature Unavailable", msg)

        analytic_view_action2 = QAction("Open Analytic Viewport (No Triangles)", self.win)

        def _open_analytic2():
            from adaptivecad.gui.analytic_viewport import AnalyticViewport

            if not hasattr(self, "aacore_scene"):
                try:
                    from adaptivecad.aacore.sdf import Scene as _Scene

                    self.aacore_scene = _Scene()
                except Exception:
                    self.aacore_scene = None
            self.analytic_view = AnalyticViewport(
                parent=self.win, aacore_scene=getattr(self, "aacore_scene", None)
            )
            self.analytic_view.show()

        analytic_view_action2.triggered.connect(
            lambda: _require(
                analytic_available,
                _open_analytic2,
                "Analytic renderer not available.\nInstall OpenGL + analytic modules.",
            )
        )
        help_menu.addAction(analytic_view_action2)
        export_analytic_stl_action2 = QAction("Export Analytic (SDFâ†’STL)", self.win)

        def _export_analytic2():
            from PySide6.QtWidgets import QFileDialog, QMessageBox

            from adaptivecad.aacore.extract.marching_export import export_isosurface_to_stl

            sc = getattr(self, "aacore_scene", None)
            if sc is None or not getattr(sc, "prims", []):
                QMessageBox.information(self.win, "Export", "No analytic objects in the scene.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self.win, "Export Analytic STL", "analytic.stl", "STL (*.stl)"
            )
            if not path:
                return
            export_isosurface_to_stl(sc, path, bbox=((-2, -2, -2), (2, 2, 2)), res=180)
            self.win.statusBar().showMessage(f"Exported: {path}", 4000)

        export_analytic_stl_action2.triggered.connect(
            lambda: _require(
                exporter_available,
                _export_analytic2,
                "Exporter needs: pip install scikit-image numpy-stl",
            )
        )
        help_menu.addAction(export_analytic_stl_action2)
        toggle_log_action = QAction("Enable Debug Logs", self.win, checkable=True)

        def _toggle_logs(checked):
            import logging as _lg

            lvl = _lg.DEBUG if checked else _lg.WARNING
            _lg.getLogger("adaptivecad").setLevel(lvl)
            _lg.getLogger("adaptivecad.gui").setLevel(lvl)
            self.win.statusBar().showMessage(
                f"Log level: {'DEBUG' if checked else 'WARNING'}", 2000
            )

        toggle_log_action.triggered.connect(_toggle_logs)
        help_menu.addAction(toggle_log_action)
        diag_action = QAction("Diagnosticsâ€¦", self.win)

        def _show_diag():
            from PySide6.QtWidgets import QMessageBox

            caps = caps_summary()
            msg = (
                "Capabilities:\n"
                f"â€¢ Analytic renderer: {'Yes' if caps.get('analytic') else 'No'}\n"
                f"â€¢ Exporter (SDFâ†’STL): {'Yes' if caps.get('exporter') else 'No'}\n"
                f"â€¢ OCCâ†’Analytic Conversion: {'Yes' if caps.get('conversion') else 'No'}\n"
            )
            QMessageBox.information(self.win, "AdaptiveCAD Diagnostics", msg)

        diag_action.triggered.connect(_show_diag)
        help_menu.addAction(diag_action)

        conversion_menu = menubar.addMenu("Conversion")
        convert_action = QAction("Convert OCC â†’ Analytic", self.win)

        def _do_convert():
            try:
                from adaptivecad.analytic.conversion import OccToAnalyticCmd

                self._run_command(OccToAnalyticCmd())
            except Exception:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.information(self.win, "Conversion", "Conversion module not available.")

        convert_action.triggered.connect(
            lambda: _require(conversion_available, _do_convert, "Conversion module not available.")
        )
        conversion_menu.addAction(convert_action)

        docs_menu = help_menu.addMenu("Documentation")
        adaptive_pi_action = QAction("Adaptive Pi Axioms", self.win)
        adaptive_pi_action.triggered.connect(
            lambda: self._show_doc_message(
                "Adaptive Pi Axioms",
                "Please see ADAPTIVE_PI_AXIOMS.md in the project root directory for the complete formal axiom set.",
            )
        )
        docs_menu.addAction(adaptive_pi_action)
        modeling_tools_action = QAction("Modeling Tools Reference", self.win)
        modeling_tools_action.triggered.connect(
            lambda: self._show_doc_message(
                "Modeling Tools",
                "Please see MODELING_TOOLS.md in the project root directory for details on all available modeling tools.",
            )
        )
        docs_menu.addAction(modeling_tools_action)

        # Plugins menu (lightweight integration points)
        plugins_menu = menubar.addMenu("Plugins")
        aniso_menu = plugins_menu.addMenu("Anisotropic Distance (FMM-lite)")
        aniso_demo_action = QAction("Compute Demo", self.win)

        def _run_aniso_demo():
            try:
                import contextlib
                import io

                from PySide6.QtWidgets import QMessageBox

                try:
                    from plugins import aniso_distance_plugin as aniso
                except Exception:
                    # Fallback import path if running as a package
                    import importlib

                    aniso = importlib.import_module("plugins.aniso_distance_plugin")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    aniso.compute_demo()
                out = buf.getvalue().strip() or "No output"
                QMessageBox.information(self.win, "Anisotropic Distance â€“ Demo", out)
            except Exception as e:
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(self.win, "Anisotropic Distance", f"Demo failed: {e}")
                except Exception:
                    log.debug(f"Aniso demo failed: {e}")

        aniso_demo_action.triggered.connect(_run_aniso_demo)
        aniso_menu.addAction(aniso_demo_action)
        aniso_trace_action = QAction("Trace Geodesic", self.win)

        def _run_aniso_trace():
            try:
                # Parameter dialog (nx, ny, a, b)
                from PySide6.QtWidgets import (
                    QDialog,
                    QDialogButtonBox,
                    QDoubleSpinBox,
                    QFormLayout,
                    QMessageBox,
                    QSpinBox,
                )

                class _Param(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.setWindowTitle("Trace Geodesic â€“ Parameters")
                        fm = QFormLayout(self)
                        self.nx = QSpinBox()
                        self.nx.setRange(16, 1025)
                        self.nx.setValue(129)
                        self.ny = QSpinBox()
                        self.ny.setRange(16, 1025)
                        self.ny.setValue(129)
                        self.a = QDoubleSpinBox()
                        self.a.setRange(0.01, 1000.0)
                        self.a.setDecimals(4)
                        self.a.setValue(1.3)
                        self.b = QDoubleSpinBox()
                        self.b.setRange(0.01, 1000.0)
                        self.b.setDecimals(4)
                        self.b.setValue(1.0)
                        fm.addRow("nx", self.nx)
                        fm.addRow("ny", self.ny)
                        fm.addRow("a (diag x)", self.a)
                        fm.addRow("b (diag y)", self.b)
                        btn = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                        btn.accepted.connect(self.accept)
                        btn.rejected.connect(self.reject)
                        fm.addWidget(btn)

                dlg = _Param(self.win)
                if not dlg.exec():
                    return
                nx, ny = int(dlg.nx.value()), int(dlg.ny.value())
                a, b = float(dlg.a.value()), float(dlg.b.value())
                # Compute and trace
                from adaptive_pi.aniso_fmm import (
                    anisotropic_fmm,
                    metric_const_aniso,
                    trace_geodesic,
                )

                G = metric_const_aniso(nx, ny, a=a, b=b)
                src = (nx // 2, ny // 2)
                T = anisotropic_fmm(G, src, use_diagonals=True)
                start = (nx - 5, ny // 2)
                path = trace_geodesic(T, G, start, src, step=0.8)
                # Show summary in dialog
                QMessageBox.information(
                    self.win,
                    "Aniso Trace",
                    f"Grid {nx}Ã—{ny}\nG=diag({a:.4f},{b:.4f})\nPath length: {len(path)}\nStart: {start}\nEndâ‰ˆ: {path[-1] if path else start}",
                )
                # Draw overlay in Analytic Viewport (panel)
                try:
                    panel = self._ensure_analytic_panel()
                    if panel is None:
                        return
                    panel.show()
                    # Clear and add overlay
                    if hasattr(panel.view, "clear_polyline_overlays"):
                        panel.view.clear_polyline_overlays()
                    if hasattr(panel.view, "add_polyline_overlay"):
                        # Default mapping: treat grid indices as XY world coords
                        col = (255, 120, 40)
                        panel.view.add_polyline_overlay(
                            path, color=col, width=3, scale=(1.0, 1.0), offset=(0.0, 0.0)
                        )
                except Exception as _e:
                    log.debug(f"Could not draw aniso overlay: {_e}")
            except Exception as e:
                try:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(self.win, "Anisotropic Distance", f"Trace failed: {e}")
                except Exception:
                    log.debug(f"Aniso trace failed: {e}")

        aniso_trace_action.triggered.connect(_run_aniso_trace)
        aniso_menu.addAction(aniso_trace_action)

        # Store menus for analytic mode visibility toggling
        self._menus = {
            "file": file_menu,
            "basic": basic_menu,
            "advanced": adv_menu,
            "analytic": analytic_menu,
            "modeling": modeling_menu,
            "settings": settings_menu,
            "games": games_menu,
            "help": help_menu,
            "conversion": conversion_menu,
            "plugins": plugins_menu,
        }

        # Apply toolbar/menu visibility according to mode
        self._update_toolbars()

    # ---------------- Analytic Viewport Persistence & Toggle Helpers ----------------
    def _prefs_path(self):
        try:
            import os

            return os.path.join(os.path.expanduser("~"), ".adaptivecad_analytic.json")
        except Exception:
            return ".adaptivecad_analytic.json"

    def _load_analytic_prefs(self):
        import json
        import os

        p = self._prefs_path()
        if not os.path.exists(p):
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _save_analytic_prefs(self, updates: dict):
        import json
        import os

        p = self._prefs_path()
        data = {}
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
        data.update(updates)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.debug(f"Failed saving analytic prefs: {e}")

    def _ensure_analytic_panel(self):
        if self._analytic_panel is not None:
            return self._analytic_panel
        try:
            from adaptivecad.gui.analytic_viewport import AnalyticViewportPanel

            shared_scene = getattr(self, "aacore_scene", None)
            panel = AnalyticViewportPanel(aacore_scene=shared_scene)
            self._analytic_panel = panel
            return panel
        except Exception as e:
            log.debug(f"Analytic panel creation failed: {e}")
            return None

    def _toggle_analytic_main(self, checked):
        # QAction passes bool; startup call may pass True directly
        if not isinstance(checked, bool) and hasattr(self, "_analytic_main_action"):
            checked = self._analytic_main_action.isChecked()
        if checked:
            panel = self._ensure_analytic_panel()
            if panel is None:
                if hasattr(self, "_analytic_main_action"):
                    self._analytic_main_action.setChecked(False)
                return
            panel.setMinimumSize(400, 300)
            if self._occ_central is None:
                self._occ_central = self.win.centralWidget()
            self.win.setCentralWidget(panel)
            if getattr(self, "viewcube", None):
                self.viewcube.hide()
            self._analytic_as_main = True
        else:
            if self._occ_central is not None:
                self.win.setCentralWidget(self._occ_central)
                if getattr(self, "viewcube", None):
                    self.viewcube.show()
            self._analytic_as_main = False
        self._save_analytic_prefs({"analytic_as_main": self._analytic_as_main})
        # Update toolbars to reflect new mode
        self._update_toolbars()

    def _update_toolbars(self):
        """Show the appropriate toolbar for the current mode.
        - OCC mode: show `toolbar_occ`, hide `toolbar_analytic`
        - Analytic-as-main: hide `toolbar_occ`, show `toolbar_analytic`
        """
        try:
            occ_tb = getattr(self, "toolbar_occ", None)
            ana_tb = getattr(self, "toolbar_analytic", None)
            if occ_tb is None or ana_tb is None:
                return
            if getattr(self, "_analytic_as_main", False):
                occ_tb.setVisible(False)
                ana_tb.setVisible(True)
                # In analytic mode hide legacy menus
                m = getattr(self, "_menus", {})
                for key in ("basic", "advanced", "modeling", "games"):
                    menu = m.get(key)
                    if menu is not None:
                        menu.menuAction().setVisible(False)
                for key in ("file", "analytic", "settings", "help", "conversion"):
                    menu = m.get(key)
                    if menu is not None:
                        menu.menuAction().setVisible(True)
            else:
                ana_tb.setVisible(False)
                occ_tb.setVisible(True)
                # In OCC mode show all menus
                m = getattr(self, "_menus", {})
                for menu in m.values():
                    try:
                        menu.menuAction().setVisible(True)
                    except Exception:
                        pass
        except Exception:
            pass

    def run_cmd(self, cmd):
        return self._run_command(cmd)

    def _run_command(self, cmd):
        try:
            # Store reference to command to prevent garbage collection during execution
            self._current_command = cmd
            cmd.run(self)
        except Exception as e:
            # Friendly handling when OCC is not installed (analytic-only path)
            msg = str(e)
            occ_missing = isinstance(e, ModuleNotFoundError) and getattr(e, "name", "") in (
                "OCC",
                "OCC.Core",
            )
            occ_missing = occ_missing or ("No module named" in msg and "OCC" in msg)
            if occ_missing:
                try:
                    QMessageBox.information(
                        self.win,
                        "OCC Not Available",
                        "This action requires the OCC backend.\n"
                        "Use the Analytic Viewport and analytic tools in this environment,\n"
                        "or run the conda/OCC path (see README).",
                    )
                except Exception:
                    pass
                # Status bar hint without noisy traceback
                try:
                    self.win.statusBar().showMessage(
                        "OCC backend not available in this environment", 3000
                    )
                except Exception:
                    pass
            else:
                try:
                    QMessageBox.critical(self.win, "Error", f"Error running command: {msg}")
                except Exception:
                    pass
                # Retain minimal console context for non-OCC errors
                try:
                    print(f"Command error: {msg}")
                    print(traceback.format_exc())
                except Exception:
                    pass
        finally:
            # Clear the reference after some delay to allow signals to complete
            # Don't clear immediately as async operations might still be running
            if hasattr(self, "_current_command"):
                if HAS_QT:
                    from PySide6.QtCore import QTimer

                    QTimer.singleShot(1000, lambda: setattr(self, "_current_command", None))

    def _delete_selected(self):
        """Delete the currently selected feature."""
        if self.selected_feature is None:
            QMessageBox.information(self.win, "Delete", "No object selected for deletion.")
            return

        try:
            from adaptivecad.command_defs import DOCUMENT, rebuild_scene

            if self.selected_feature in DOCUMENT:
                DOCUMENT.remove(self.selected_feature)
                self.selected_feature = None
                self._clear_property_panel()
                self._remove_move_arrows()
                rebuild_scene(self.view._display)
                self.win.statusBar().showMessage("Object deleted.", 2000)
            else:
                self.win.statusBar().showMessage("Could not delete object.", 2000)
        except Exception as e:
            QMessageBox.critical(self.win, "Error", f"Error deleting object: {str(e)}")

    def _toggle_properties_panel(self, checked):
        """Toggle the properties panel visibility."""
        if checked:
            self._create_properties_panel()
        else:
            self._hide_properties_panel()

    def _create_properties_panel(self):
        """Create and show the properties panel."""
        if self.property_panel is not None:
            return  # Already created

        # Create a dock widget for properties
        self.property_panel = QDockWidget("Properties", self.win)
        self.property_panel.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create the properties widget
        properties_widget = QWidget()
        self.property_layout = QVBoxLayout(properties_widget)

        # Add a label
        label = QLabel("Object Properties")
        label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        self.property_layout.addWidget(label)

        # Add instructions
        instructions = QLabel("Select an object from the 3D view to see its properties here.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray; margin-bottom: 10px;")
        self.property_layout.addWidget(instructions)

        # Add stretch to push content to top
        self.property_layout.addStretch()

        self.property_panel.setWidget(properties_widget)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.property_panel)
        self.property_panel.show()

    def _hide_properties_panel(self):
        """Hide the properties panel."""
        if self.property_panel is not None:
            self.property_panel.hide()
            self.win.removeDockWidget(self.property_panel)
            self.property_panel = None

    def _clear_property_panel(self):
        """Clear the property panel contents."""
        if self.property_panel is not None and hasattr(self, "property_layout"):
            # Clear all widgets except the first two (label and instructions)
            while self.property_layout.count() > 3:  # Keep label, instructions, and stretch
                child = self.property_layout.takeAt(2)  # Remove items after instructions
                if child.widget():
                    child.widget().deleteLater()  # ------------------------------------------------------------------

    # Move arrows helpers
    # ------------------------------------------------------------------
    def _create_move_arrows(self, feature):
        """Display simple X/Y/Z arrows at the feature center for quick moves."""
        log.debug(f"_create_move_arrows for feature: {feature.name}")
        try:
            from math import pi

            from OCC.Core.Bnd import Bnd_Box
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.BRepBndLib import brepbndlib_Add
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
            from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
            from OCC.Core.TopoDS import TopoDS_Compound

            self._remove_move_arrows()

            box = Bnd_Box()
            brepbndlib_Add(feature.shape, box)
            xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
            cx = (xmin + xmax) / 2.0
            cy = (ymin + ymax) / 2.0
            cz = (zmin + zmax) / 2.0
            size = max(xmax - xmin, ymax - ymin, zmax - zmin) * 0.6
            log.debug(f"Arrow placement center=({cx:.2f},{cy:.2f},{cz:.2f}) size={size:.2f}")

            cyl_r = size * 0.03
            cyl_h = size * 0.8
            cone_r = size * 0.06
            cone_h = size * 0.2

            def make_arrow(axis):
                log.debug(f"Creating arrow axis={axis}")
                cyl = BRepPrimAPI_MakeCylinder(cyl_r, cyl_h).Shape()
                cone = BRepPrimAPI_MakeCone(cone_r, 0, cone_h).Shape()
                tr = gp_Trsf()
                tr.SetTranslation(gp_Vec(0, 0, cyl_h))
                cone = BRepBuilderAPI_Transform(cone, tr, True).Shape()
                comp = TopoDS_Compound()
                builder = BRep_Builder()
                builder.MakeCompound(comp)
                builder.Add(comp, cyl)
                builder.Add(comp, cone)
                if axis == "x":
                    rot = gp_Trsf()
                    rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), -pi / 2)
                    comp = BRepBuilderAPI_Transform(comp, rot, True).Shape()
                elif axis == "y":
                    rot = gp_Trsf()
                    rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), pi / 2)
                    comp = BRepBuilderAPI_Transform(comp, rot, True).Shape()
                tr2 = gp_Trsf()
                tr2.SetTranslation(gp_Vec(cx, cy, cz))
                comp = BRepBuilderAPI_Transform(comp, tr2, True).Shape()
                log.debug(f"Arrow {axis} created")
                return comp

            colors = {"x": "RED", "y": "GREEN", "z": "BLUE"}
            self.arrow_shapes = {}
            for ax in ("x", "y", "z"):
                shp = make_arrow(ax)
                ais = self.view._display.DisplayShape(shp, color=colors[ax], update=False)
                self.arrow_shapes[ax] = {"ais": ais, "shape": shp}
                log.debug(f"Arrow {ax} displayed AIS={ais}")
            self.view._display.Repaint()
            log.debug(f"All arrows created: {list(self.arrow_shapes.keys())}")
        except Exception as e:
            log.error(f"Error creating move arrows: {e}")
            import traceback

            traceback.print_exc()

    def _remove_move_arrows(self):
        log.debug("_remove_move_arrows called")
        if hasattr(self, "arrow_shapes"):
            log.debug(f"Removing {len(self.arrow_shapes)} arrow shapes")
            for info in self.arrow_shapes.values():
                try:
                    if self.view._display.Context.IsDisplayed(info["ais"]):
                        self.view._display.Context.Remove(info["ais"], True)
                        log.debug("Arrow removed")
                except Exception as e:
                    log.error(f"Error removing arrow: {e}")
            self.arrow_shapes = {}
            log.debug("Arrow shapes dictionary cleared")
        else:
            log.debug("No arrow shapes to remove")

    def _move_along_axis(self, axis):
        """Prompt for distance and move selected feature along given axis."""
        log.debug(f"_move_along_axis axis={axis}")
        if self.selected_feature is None:
            log.debug("No selected feature to move")
            return
        log.debug(f"Moving feature: {self.selected_feature.name}")

        from PySide6.QtWidgets import QInputDialog

        dist, ok = QInputDialog.getDouble(
            self.win, "Move", f"Distance along {axis.upper()} (mm)", 10.0
        )
        if not ok:
            log.debug("User cancelled move dialog")
            return
        log.debug(f"User entered distance: {dist}")

        dx = dy = dz = 0.0
        if axis == "x":
            dx = dist
        elif axis == "y":
            dy = dist
        else:
            dz = dist
        log.debug(f"Translation vector dx={dx}, dy={dy}, dz={dz}")

        try:
            log.debug("Calling apply_translation on feature")
            self.selected_feature.apply_translation([dx, dy, dz])
            log.debug("apply_translation completed; rebuilding scene")
            from adaptivecad.command_defs import rebuild_scene

            rebuild_scene(self.view._display)
            log.debug("Scene rebuilt; recreating move arrows")
            self._create_move_arrows(self.selected_feature)
            log.debug("Move operation completed")
        except Exception as e:
            log.error(f"Error moving feature: {e}")
            import traceback

            traceback.print_exc()

    def _toggle_dimension_panel(self, checked):
        """Toggle the dimension selector panel visibility."""
        if checked:
            self._create_dimension_panel()
        else:
            self._hide_dimension_panel()

    def _sync_analytic_scene(self):
        # Called whenever DOCUMENT changes or transforms update
        try:
            # For now AACore scene is shared live; nothing to do.
            vp = getattr(self, "_analytic_viewport", None)
            if vp:
                vp.update()
        except Exception:
            pass

    def _create_dimension_panel(self):
        """Create and show the dimension selector panel."""
        if self.dimension_panel is not None:
            return  # Already created

        # Create a dock widget for dimension selection
        self.dimension_panel = QDockWidget("Dimension Selector", self.win)
        self.dimension_panel.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create the dimension widget
        dimension_widget = QWidget()
        layout = QVBoxLayout(dimension_widget)

        # Add title
        title = QLabel("Multi-Dimensional View Control")
        title.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Add dimension selector
        dim_label = QLabel("Active Dimensions:")
        layout.addWidget(dim_label)

        # Create checkboxes for X, Y, Z, and additional dimensions
        self.dim_checkboxes = {}
        dimensions = ["X", "Y", "Z", "W", "U", "V"]

        for i, dim in enumerate(dimensions):
            checkbox = QCheckBox(f"Dimension {dim}")
            # Default to X, Y, Z enabled for 3D view
            if i < 3:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)
            self.dim_checkboxes[dim] = checkbox
            layout.addWidget(checkbox)

        # Add slice controls for higher dimensions
        layout.addWidget(QLabel("Slice Controls:"))

        # Create sliders for slicing through higher dimensions
        self.slice_controls = {}
        for dim in ["W", "U", "V"]:
            group = QWidget()
            group_layout = QHBoxLayout(group)

            label = QLabel(f"{dim}:")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            value_label = QLabel("50")

            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))

            group_layout.addWidget(label)
            group_layout.addWidget(slider)
            group_layout.addWidget(value_label)

            self.slice_controls[dim] = {"slider": slider, "value_label": value_label}
            layout.addWidget(group)

        # Add projection controls
        layout.addWidget(QLabel("Projection:"))

        projection_combo = QComboBox()
        projection_combo.addItems(["Orthographic", "Perspective", "Isometric"])
        layout.addWidget(projection_combo)

        # Add view preset buttons
        layout.addWidget(QLabel("View Presets:"))

        preset_buttons = QHBoxLayout()

        xy_btn = QPushButton("X-Y")
        xz_btn = QPushButton("X-Z")
        yz_btn = QPushButton("Y-Z")
        iso_btn = QPushButton("ISO")

        xy_btn.clicked.connect(lambda: self._set_view_preset("XY"))
        xz_btn.clicked.connect(lambda: self._set_view_preset("XZ"))
        yz_btn.clicked.connect(lambda: self._set_view_preset("YZ"))
        iso_btn.clicked.connect(lambda: self._set_view_preset("ISO"))

        preset_buttons.addWidget(xy_btn)
        preset_buttons.addWidget(xz_btn)
        preset_buttons.addWidget(yz_btn)
        preset_buttons.addWidget(iso_btn)

        preset_widget = QWidget()
        preset_widget.setLayout(preset_buttons)
        layout.addWidget(preset_widget)

        # Sketch solver quick actions
        sketch_title = QLabel("Sketch Solver (beta)")
        sketch_title.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(sketch_title)

        sketch_btn_row1 = QHBoxLayout()
        new_sketch_btn = QPushButton("New Sketch")
        add_point_btn = QPushButton("Add Point")
        solve_btn = QPushButton("Solve")
        sketch_btn_row1.addWidget(new_sketch_btn)
        sketch_btn_row1.addWidget(add_point_btn)
        sketch_btn_row1.addWidget(solve_btn)
        row1_widget = QWidget()
        row1_widget.setLayout(sketch_btn_row1)
        layout.addWidget(row1_widget)

        sketch_btn_row2 = QHBoxLayout()
        fixed_btn = QPushButton("Add Fixed")
        dist_btn = QPushButton("Add Distance")
        hv_btn = QPushButton("Add H/V")
        sketch_btn_row2.addWidget(fixed_btn)
        sketch_btn_row2.addWidget(dist_btn)
        sketch_btn_row2.addWidget(hv_btn)
        row2_widget = QWidget()
        row2_widget.setLayout(sketch_btn_row2)
        layout.addWidget(row2_widget)

        sketch_btn_row3 = QHBoxLayout()
        parallel_btn = QPushButton("Add Parallel")
        perp_btn = QPushButton("Add Perp")
        equal_btn = QPushButton("Add Equal")
        sketch_btn_row3.addWidget(parallel_btn)
        sketch_btn_row3.addWidget(perp_btn)
        sketch_btn_row3.addWidget(equal_btn)
        row3_widget = QWidget()
        row3_widget.setLayout(sketch_btn_row3)
        layout.addWidget(row3_widget)

        export_btn = QPushButton("Export DXF")
        layout.addWidget(export_btn)

        self.sketch_summary_label = QLabel("Points: 0 | Constraints: 0")
        self.sketch_summary_label.setStyleSheet("color: gray;")
        layout.addWidget(self.sketch_summary_label)

        self._refresh_sketch_summary()

        new_sketch_btn.clicked.connect(self._sketch_reset)
        add_point_btn.clicked.connect(self._sketch_add_point)
        solve_btn.clicked.connect(self._sketch_solve)
        fixed_btn.clicked.connect(self._sketch_add_fixed)
        dist_btn.clicked.connect(self._sketch_add_distance)
        hv_btn.clicked.connect(self._sketch_add_hv)
        parallel_btn.clicked.connect(self._sketch_add_parallel)
        perp_btn.clicked.connect(self._sketch_add_perp)
        equal_btn.clicked.connect(self._sketch_add_equal)
        export_btn.clicked.connect(self._sketch_export_dxf)

        # Add stretch to push content to top
        layout.addStretch()

        self.dimension_panel.setWidget(dimension_widget)
        self.win.addDockWidget(Qt.RightDockWidgetArea, self.dimension_panel)
        self.dimension_panel.show()

    def _hide_dimension_panel(self):
        """Hide the dimension selector panel."""
        if self.dimension_panel is not None:
            self.dimension_panel.hide()
            self.win.removeDockWidget(self.dimension_panel)
            self.dimension_panel = None

    # Sketch solver helpers (hooks into existing solver/model)
    def _refresh_sketch_summary(self):
        if self.sketch_summary_label is None:
            return
        pts = ", ".join(
            [f"{i}:({p.x:.3g},{p.y:.3g})" for i, p in enumerate(getattr(self.sketch, "points", []))]
        )
        cons = len(getattr(self.sketch, "constraints", []))
        txt = f"Points: {len(getattr(self.sketch, 'points', []))} | Constraints: {cons}"
        if pts:
            txt += f" | {pts}"
        self.sketch_summary_label.setText(txt)

    def _sketch_reset(self):
        self.sketch = Sketch()
        self._refresh_sketch_summary()
        try:
            self.win.statusBar().showMessage("Sketch reset", 2000)
        except Exception:
            pass

    def _sketch_add_point(self):
        x, ok = QInputDialog.getDouble(self.win, "Add Point", "X:", 0.0, -1e6, 1e6, 3)
        if not ok:
            return
        y, ok = QInputDialog.getDouble(self.win, "Add Point", "Y:", 0.0, -1e6, 1e6, 3)
        if not ok:
            return
        self.sketch.add_point(float(x), float(y))
        self._refresh_sketch_summary()
        try:
            self.win.statusBar().showMessage("Point added", 1500)
        except Exception:
            pass

    def _sketch_add_fixed(self):
        idx, ok = QInputDialog.getInt(
            self.win, "Add Fixed", "Point index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        if idx < 0 or idx >= len(self.sketch.points):
            QMessageBox.information(self.win, "Sketch", "Invalid point index")
            return
        self.sketch.add_constraint(FixedConstraint(idx, self.sketch.points[idx]))
        self._refresh_sketch_summary()

    def _sketch_add_distance(self):
        idx1, ok = QInputDialog.getInt(
            self.win, "Distance Constraint", "Point A index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        idx2, ok = QInputDialog.getInt(
            self.win, "Distance Constraint", "Point B index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        dist, ok = QInputDialog.getDouble(self.win, "Distance Constraint", "Target distance:", 1.0, 0.0, 1e6, 4)
        if not ok:
            return
        self.sketch.add_constraint(DistanceConstraint(idx1, idx2, float(dist)))
        self._refresh_sketch_summary()

    def _sketch_add_hv(self):
        choice, ok = QInputDialog.getItem(
            self.win, "Horizontal/Vertical", "Constraint type:", ["Horizontal", "Vertical"], 0, False
        )
        if not ok:
            return
        idx1, ok = QInputDialog.getInt(
            self.win, f"{choice} Constraint", "Point A index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        idx2, ok = QInputDialog.getInt(
            self.win, f"{choice} Constraint", "Point B index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        if choice == "Horizontal":
            self.sketch.add_constraint(HorizontalConstraint(idx1, idx2))
        else:
            self.sketch.add_constraint(VerticalConstraint(idx1, idx2))
        self._refresh_sketch_summary()

    def _sketch_add_parallel(self):
        a1, ok = QInputDialog.getInt(
            self.win, "Parallel Constraint", "Segment A start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        a2, ok = QInputDialog.getInt(
            self.win, "Parallel Constraint", "Segment A end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b1, ok = QInputDialog.getInt(
            self.win, "Parallel Constraint", "Segment B start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b2, ok = QInputDialog.getInt(
            self.win, "Parallel Constraint", "Segment B end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        self.sketch.add_constraint(ParallelConstraint(a1, a2, b1, b2))
        self._refresh_sketch_summary()

    def _sketch_add_perp(self):
        a1, ok = QInputDialog.getInt(
            self.win, "Perpendicular Constraint", "Segment A start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        a2, ok = QInputDialog.getInt(
            self.win, "Perpendicular Constraint", "Segment A end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b1, ok = QInputDialog.getInt(
            self.win, "Perpendicular Constraint", "Segment B start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b2, ok = QInputDialog.getInt(
            self.win, "Perpendicular Constraint", "Segment B end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        self.sketch.add_constraint(PerpendicularConstraint(a1, a2, b1, b2))
        self._refresh_sketch_summary()

    def _sketch_add_equal(self):
        a1, ok = QInputDialog.getInt(
            self.win, "Equal Length Constraint", "Segment A start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        a2, ok = QInputDialog.getInt(
            self.win, "Equal Length Constraint", "Segment A end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b1, ok = QInputDialog.getInt(
            self.win, "Equal Length Constraint", "Segment B start index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        b2, ok = QInputDialog.getInt(
            self.win, "Equal Length Constraint", "Segment B end index:", 0, 0, max(0, len(self.sketch.points) - 1), 1
        )
        if not ok:
            return
        self.sketch.add_constraint(EqualLengthConstraint(a1, a2, b1, b2))
        self._refresh_sketch_summary()

    def _sketch_solve(self):
        try:
            self.sketch.solve_least_squares()
            self._refresh_sketch_summary()
            self.win.statusBar().showMessage("Sketch solved", 2000)
        except Exception as e:
            try:
                QMessageBox.information(self.win, "Sketch Solver", f"Solve failed: {e}")
            except Exception:
                pass

    def _sketch_export_dxf(self):
        path, _ = QFileDialog.getSaveFileName(
            self.win, "Export Sketch to DXF", "sketch.dxf", "DXF (*.dxf)"
        )
        if not path:
            return
        try:
            export_dxf(self.sketch, path)
            self.win.statusBar().showMessage(f"Exported: {path}", 3000)
        except Exception as e:
            try:
                QMessageBox.information(self.win, "Sketch Export", f"Export failed: {e}")
            except Exception:
                pass

    def _open_chess_widget(self):
        """Open the ND chess widget in a dock window."""
        if NDChessWidget is None:
            QMessageBox.information(self.win, "4D Chess", "Chess widget not available.")
            return
        if self.chess_dock is None:
            self.chess_widget = NDChessWidget()
            self.chess_dock = QDockWidget("4D Chess", self.win)
            self.chess_dock.setWidget(self.chess_widget)
            self.win.addDockWidget(Qt.RightDockWidgetArea, self.chess_dock)
        else:
            self.chess_dock.show()

    def _toggle_grid_display(self, checked: bool) -> None:
        """Show or hide the viewer grid based on the action state."""
        try:
            if checked:
                if hasattr(self.view._display, "enable_grid"):
                    self.view._display.enable_grid()
                elif hasattr(self.view._display, "display_grid"):
                    self.view._display.display_grid()
                else:
                    self.win.statusBar().showMessage("Grid enable method not found", 2000)
                    return
            else:
                if hasattr(self.view._display, "disable_grid"):
                    self.view._display.disable_grid()
                elif hasattr(self.view._display, "erase_grid"):
                    self.view._display.erase_grid()
                elif hasattr(self.view._display, "display_grid"):
                    try:
                        self.view._display.display_grid(False)
                    except Exception:
                        pass
                else:
                    self.win.statusBar().showMessage("Grid disable method not found", 2000)
                    return
            self.win.statusBar().showMessage(f"Grid {'shown' if checked else 'hidden'}", 2000)
        except Exception as e:
            print(f"Warning: Could not toggle grid: {e}")
            self.win.statusBar().showMessage(f"Error toggling grid: {e}", 3000)

    def _set_view_preset(self, preset):
        """Set a view preset for the 3D view."""
        try:
            if preset == "XY":
                self.view._display.View.SetProj(0, 0, 1)  # Top view
            elif preset == "XZ":
                self.view._display.View.SetProj(0, -1, 0)  # Front view
            elif preset == "YZ":
                self.view._display.View.SetProj(1, 0, 0)  # Right view
            elif preset == "ISO":
                self.view._display.View.SetProj(1, 1, 1)  # Isometric view

            self.view._display.FitAll()
            self.win.statusBar().showMessage(f"View set to {preset}", 2000)
        except Exception as e:
            print(f"Error setting view preset {preset}: {e}")
            self.win.statusBar().showMessage(f"Error setting view preset: {e}", 3000)
            print(f"Error setting view preset {preset}: {e}")

    def _show_not_implemented(self, feature_name):
        QMessageBox.information(
            self.win,
            "Not Implemented",
            f"{feature_name} functionality is not yet implemented.\n"
            "This feature will be added in a future version.",
        )

    def _show_welcome_if_first_run(self):
        """Show welcome dialog with quick tips for new users."""
        import os
        import sys
        # Skip in headless/offscreen mode or during tests
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        if "pytest" in sys.modules:
            return
        # Skip if window isn't visible (called from __init__ before show())
        if not self.win.isVisible():
            return
        prefs = self._load_analytic_prefs()
        if not prefs.get("welcomed", False):
            try:
                from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton, QVBoxLayout

                class WelcomeDialog(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.setWindowTitle("Welcome to AdaptiveCAD")
                        self.setModal(True)
                        self.resize(400, 300)

                        layout = QVBoxLayout(self)

                        # Welcome message
                        welcome_text = QLabel(
                            """
<h2>Welcome to AdaptiveCAD!</h2>
<p>Get started quickly:</p>
<ul>
<li><b>Basic Shapes:</b> Use menu or shortcuts (B=Box, C=Cylinder, S=Sphere)</li>
<li><b>Advanced Shapes:</b> Try Superellipse, Pi Curve Shell, Helix</li>
<li><b>Analytic View:</b> Use Settings → View → Analytic Viewport for SDF rendering</li>
<li><b>File Operations:</b> Ctrl+N (New), Ctrl+O (Open), Ctrl+S (Save)</li>
</ul>
<p>Need help? Check the Help menu for documentation and examples.</p>
                        """
                        )
                        welcome_text.setWordWrap(True)
                        layout.addWidget(welcome_text)

                        # Don't show again checkbox
                        self.dont_show = QCheckBox("Don't show this welcome screen again")
                        layout.addWidget(self.dont_show)

                        # Close button
                        close_btn = QPushButton("Get Started")
                        close_btn.clicked.connect(self.accept)
                        layout.addWidget(close_btn)

                dialog = WelcomeDialog(self.win)
                dialog.exec()

                # Save preference if user checked the box
                if dialog.dont_show.isChecked():
                    self._save_analytic_prefs({"welcomed": True})

            except Exception as e:
                log.debug(f"Could not show welcome dialog: {e}")

    def _new_project(self):
        """Clear the current project and start fresh."""
        try:
            from adaptivecad.command_defs import DOCUMENT

            DOCUMENT.clear()
        except Exception:
            pass

        if hasattr(self.view, "_display"):
            self.view._display.EraseAll()

        self.win.statusBar().showMessage("New project started", 2000)

    def run(self):
        if not HAS_GUI:
            print("Error: Cannot run GUI without Qt.")
            return 1

        # Show the window and run the application
        self.win.show()
        return self.app.exec()

    def _position_viewcube(self):
        if self.viewcube and self.viewcube.parent() is self.view:
            self.viewcube.move(self.view.width() - self.viewcube.width() - 10, 10)

    def setup_view_events(self):
        if not self.viewcube:
            return
        original_resize = self.view.resizeEvent

        def new_resize(event):
            original_resize(event)
            self._position_viewcube()

        self.view.resizeEvent = new_resize

    def _make_fallback_view(self, parent, layout):
        """Create a minimal placeholder viewer when OCC is unavailable."""
        placeholder = QWidget(parent)
        v = QVBoxLayout(placeholder)
        lbl = QLabel(
            "OCC backend not available. Using fallback view.\n"
            "You can still use Analytic Viewport & panel."
        )
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #CCC; background:#222; padding:16px;")
        v.addWidget(lbl)
        placeholder._display = type(
            "DummyDisplay",
            (),
            {
                "EraseAll": lambda self=None: None,
                "DisplayShape": lambda *a, **k: None,
                "FitAll": lambda *a, **k: None,
                "set_bg_gradient_color": lambda *a, **k: None,
                "View": type(
                    "V", (), {"SetProj": lambda *a, **k: None, "SetScale": lambda *a, **k: None}
                )(),
            },
        )()
        layout.addWidget(placeholder)
        return placeholder

    def _show_about(self):
        QMessageBox.about(
            self.win,
            "About AdaptiveCAD",
            """<h2>AdaptiveCAD</h2>
<p>A curvature-first CAD/CAM system based on the Adaptive Pi Geometry.</p>
<p>This application demonstrates parametric shapes and modeling tools
that implement the Ï€â‚ (Adaptive Pi) geometry principles.</p>
<p>For more information, see the documentation files in the project root.</p>
""",
        )

    def _show_doc_message(self, title, message):
        QMessageBox.information(self.win, title, message)

    def _create_ball_via_backend(self, r: float = 20.0):
        from adaptivecad import settings

        if settings.USE_ANALYTIC_BACKEND:
            # open/focus the Analytic dock and set sliders to r / Î²
            cmd = NewAnalyticBallCmd()
            cmd.run(self)
            try:
                dock = [
                    d
                    for d in self.win.findChildren(QDockWidget)
                    if d.objectName() == "SDFAnalyticBallDock"
                ][0]
                dock.slider_r.setValue(int(r))
                dock.slider_b.setValue(int(settings.ANALYTIC_PIA_BETA * 100))
            except Exception:
                pass
        else:
            # fall back to OCC Ball command
            NewBallCmd().run(self)

    # Sketch persistence & serialization helpers
    def _sketch_to_dict(self) -> dict:
        """Serialize sketch to dictionary."""
        if not hasattr(self, 'sketch') or self.sketch is None:
            return {"points": [], "constraints": []}
        
        points = []
        for p in self.sketch.points:
            points.append({"x": float(p.x), "y": float(p.y)})
        
        constraints = []
        for cons in self.sketch.constraints:
            cons_type = type(cons).__name__
            if cons_type == "FixedConstraint":
                constraints.append({"type": "fixed", "idx": cons.idx})
            elif cons_type == "DistanceConstraint":
                constraints.append({"type": "distance", "idx1": cons.idx1, "idx2": cons.idx2, "distance": float(cons.distance)})
            elif cons_type == "HorizontalConstraint":
                constraints.append({"type": "horizontal", "idx1": cons.idx1, "idx2": cons.idx2})
            elif cons_type == "VerticalConstraint":
                constraints.append({"type": "vertical", "idx1": cons.idx1, "idx2": cons.idx2})
            elif cons_type == "ParallelConstraint":
                constraints.append({"type": "parallel", "a1": cons.a1, "a2": cons.a2, "b1": cons.b1, "b2": cons.b2})
            elif cons_type == "PerpendicularConstraint":
                constraints.append({"type": "perpendicular", "a1": cons.a1, "a2": cons.a2, "b1": cons.b1, "b2": cons.b2})
            elif cons_type == "EqualLengthConstraint":
                constraints.append({"type": "equal_length", "a1": cons.a1, "a2": cons.a2, "b1": cons.b1, "b2": cons.b2})
        
        return {"points": points, "constraints": constraints}
    
    def _sketch_from_dict(self, data: dict):
        """Deserialize sketch from dictionary."""
        self.sketch = Sketch()
        
        # Restore points
        for pt in data.get("points", []):
            self.sketch.add_point(float(pt.get("x", 0)), float(pt.get("y", 0)))
        
        # Restore constraints
        for cons_data in data.get("constraints", []):
            cons_type = cons_data.get("type")
            try:
                if cons_type == "fixed":
                    idx = cons_data["idx"]
                    if idx < len(self.sketch.points):
                        self.sketch.add_constraint(FixedConstraint(idx, self.sketch.points[idx]))
                elif cons_type == "distance":
                    idx1, idx2 = cons_data["idx1"], cons_data["idx2"]
                    dist = float(cons_data.get("distance", 1.0))
                    if idx1 < len(self.sketch.points) and idx2 < len(self.sketch.points):
                        self.sketch.add_constraint(DistanceConstraint(idx1, idx2, dist))
                elif cons_type == "horizontal":
                    idx1, idx2 = cons_data["idx1"], cons_data["idx2"]
                    if idx1 < len(self.sketch.points) and idx2 < len(self.sketch.points):
                        self.sketch.add_constraint(HorizontalConstraint(idx1, idx2))
                elif cons_type == "vertical":
                    idx1, idx2 = cons_data["idx1"], cons_data["idx2"]
                    if idx1 < len(self.sketch.points) and idx2 < len(self.sketch.points):
                        self.sketch.add_constraint(VerticalConstraint(idx1, idx2))
                elif cons_type == "parallel":
                    a1, a2, b1, b2 = cons_data["a1"], cons_data["a2"], cons_data["b1"], cons_data["b2"]
                    if all(i < len(self.sketch.points) for i in [a1, a2, b1, b2]):
                        self.sketch.add_constraint(ParallelConstraint(a1, a2, b1, b2))
                elif cons_type == "perpendicular":
                    a1, a2, b1, b2 = cons_data["a1"], cons_data["a2"], cons_data["b1"], cons_data["b2"]
                    if all(i < len(self.sketch.points) for i in [a1, a2, b1, b2]):
                        self.sketch.add_constraint(PerpendicularConstraint(a1, a2, b1, b2))
                elif cons_type == "equal_length":
                    a1, a2, b1, b2 = cons_data["a1"], cons_data["a2"], cons_data["b1"], cons_data["b2"]
                    if all(i < len(self.sketch.points) for i in [a1, a2, b1, b2]):
                        self.sketch.add_constraint(EqualLengthConstraint(a1, a2, b1, b2))
            except Exception as e:
                log.debug(f"Failed to restore constraint {cons_type}: {e}")
        
        self._refresh_sketch_summary()


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":
    main()
