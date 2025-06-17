"""Simplified GUI playground with optional dependencies."""

try:
    import PySide6  # type: ignore
    from OCC.Display import backend  # type: ignore
except Exception:  # pragma: no cover - optional GUI deps missing
    HAS_GUI = False
else:
    HAS_GUI = True  # Ensure HAS_GUI is set to True here
    from math import pi, cos, sin
    import os
    import sys
    import numpy as np
    import traceback
    from adaptivecad import settings
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QInputDialog, QMessageBox, QCheckBox, 
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, 
        QPushButton, QDockWidget, QLineEdit, QToolBar, QToolButton, QMenu
    )
    from PySide6.QtGui import QAction, QIcon, QCursor, QPixmap  # Added QPixmap for custom icon loading
    from PySide6.QtCore import Qt, QObject, QEvent  # Original import
    from OCC.Core.AIS import AIS_Shape
    from OCC.Core.TopoDS import TopoDS_Face
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from adaptivecad.push_pull import PushPullFeatureCmd
    from adaptivecad.gui.viewcube_widget import ViewCubeWidget
    # Ensure this block is indented
    from adaptivecad.command_defs import (
        NewBoxCmd,
        NewCylCmd,
        ExportStlCmd,
        ExportAmaCmd,
        ExportGCodeCmd,
        ExportGCodeDirectCmd,
        MoveCmd,
        UnionCmd,
        CutCmd,
        NewNDBoxCmd,
        NewNDFieldCmd,
        NewBezierCmd,
        NewBSplineCmd,
        NewBallCmd,
        NewTorusCmd,
        NewConeCmd,
        LoftCmd,
        SweepAlongPathCmd,
        ShellCmd,
        IntersectCmd,
        RevolveCmd,
        ScaleCmd,
        rebuild_scene,
        DOCUMENT,
    )
    # Ensure PiSquareCmd import is here and indented
    from adaptivecad.commands.pi_square_cmd import PiSquareCmd
    from adaptivecad.commands.draped_sheet_cmd import DrapedSheetCmd # Add this import

    # Optional anti-aliasing support (this and subsequent code should now be correctly aligned)
    try:
        from OCC.Core.V3d import V3d_View
        from OCC.Core.Graphic3d import Graphic3d_RenderingParams

        AA_AVAILABLE = True

        class AA:
            V3d_MSAA_8X = 8

    except Exception:
        AA_AVAILABLE = False    # Minimal Props class for volume calculation
    class Props:
        def Volume(self, shape):
            try:
                from OCC.Core.GProp import GProp_GProps
                from OCC.Core.BRepGProp import BRepGProp

                props = GProp_GProps()
                # Use static method BRepGProp.VolumeProperties instead of deprecated function
                BRepGProp.VolumeProperties(shape, props)
                return props.Mass()
            except Exception:
                return 0.0

    # Stub classes for missing NDField components
    def plot_nd_slice(data):
        """Stub function for plotting ND slices."""
        print(
            f"plot_nd_slice called with data shape: {getattr(data, 'shape', 'unknown')}"
        )


# --- Advanced NDSliceWidget with PCA and Matplotlib integration ---
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QCheckBox, QGroupBox, QDockWidget
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from sklearn.decomposition import PCA

class NDSliceWidget(QWidget):
    """Interactive NDField slicer with axis selection and PCA auto-projection."""
    def __init__(self, ndfield, callback=None, parent=None):
        super().__init__(parent)
        self.ndfield = ndfield
        self.callback = callback
        self.slice_indices = [None] * ndfield.ndim
        self.pca_enabled = False
        self.axis_x = 0
        self.axis_y = 1 if ndfield.ndim > 1 else 0
        self._build_ui()
        self._update_plot()

    def _build_ui(self):
        layout = QVBoxLayout()

        # Axis selection controls
        axis_group = QGroupBox("Axis Selection")
        axis_layout = QHBoxLayout()
        self.axis_x_combo = QComboBox()
        self.axis_y_combo = QComboBox()
        for i in range(self.ndfield.ndim):
            self.axis_x_combo.addItem(f"Axis {i}", i)
            self.axis_y_combo.addItem(f"Axis {i}", i)
        self.axis_x_combo.setCurrentIndex(self.axis_x)
        self.axis_y_combo.setCurrentIndex(self.axis_y)
        self.axis_x_combo.currentIndexChanged.connect(self._on_axis_changed)
        self.axis_y_combo.currentIndexChanged.connect(self._on_axis_changed)
        axis_layout.addWidget(QLabel("X:"))
        axis_layout.addWidget(self.axis_x_combo)
        axis_layout.addWidget(QLabel("Y:"))
        axis_layout.addWidget(self.axis_y_combo)
        axis_group.setLayout(axis_layout)
        layout.addWidget(axis_group)

        # Slicing controls
        self.slice_combos = []
        slice_group = QGroupBox("Slice Selection")
        slice_layout = QHBoxLayout()
        for i, dim in enumerate(self.ndfield.grid_shape):
            if i in (self.axis_x, self.axis_y):
                self.slice_combos.append(None)
                continue
            combo = QComboBox()
            combo.addItem("All", None)
            for idx in range(dim):
                combo.addItem(str(idx), idx)
            combo.currentIndexChanged.connect(self._make_slice_callback(i, combo))
            slice_layout.addWidget(QLabel(f"Dim {i}"))
            slice_layout.addWidget(combo)
            self.slice_combos.append(combo)
        slice_group.setLayout(slice_layout)
        layout.addWidget(slice_group)

        # PCA checkbox
        self.pca_checkbox = QCheckBox("Auto-project with PCA (best 2D)")
        self.pca_checkbox.stateChanged.connect(self._on_pca_toggled)
        layout.addWidget(self.pca_checkbox)

        # Update button
        update_btn = QPushButton("Update Slice")
        update_btn.clicked.connect(self._update_plot)
        layout.addWidget(update_btn)

        # Matplotlib Figure
        self.fig = Figure(figsize=(4, 4))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.setLayout(layout)

    def _make_slice_callback(self, axis, combo):
        def update(_):
            val = combo.currentData()
            self.slice_indices[axis] = val
        return update

    def _on_axis_changed(self, _):
        self.axis_x = self.axis_x_combo.currentData()
        self.axis_y = self.axis_y_combo.currentData()
        # Rebuild slice controls for new axes
        for i, combo in enumerate(self.slice_combos):
            if combo is not None:
                combo.setEnabled(i not in (self.axis_x, self.axis_y))
        self._update_plot()

    def _on_pca_toggled(self, state):
        self.pca_enabled = bool(state)
        self._update_plot()

    def _get_slice(self):
        # Build slice tuple for numpy
        slicer = []
        for i, dim in enumerate(self.ndfield.grid_shape):
            if i == self.axis_x or i == self.axis_y:
                slicer.append(slice(None))
            else:
                idx = self.slice_indices[i]
                slicer.append(idx if idx is not None else slice(None))
        return tuple(slicer)

    def _update_plot(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        data = self.ndfield.values[self._get_slice()]
        # If PCA is enabled and ndim > 2, flatten and project
        if self.pca_enabled and self.ndfield.ndim > 2:
            # Reshape to (N, D)
            coords = np.stack(np.meshgrid(*[np.arange(s) for s in data.shape], indexing='ij'), -1).reshape(-1, data.ndim)
            flat_vals = data.flatten()
            pca = PCA(n_components=2)
            coords_2d = pca.fit_transform(coords)
            sc = ax.scatter(coords_2d[:, 0], coords_2d[:, 1], c=flat_vals, cmap='viridis')
            self.fig.colorbar(sc, ax=ax)
            ax.set_title("PCA Projection")
        else:
            # Show as image if 2D, else flatten
            if data.ndim == 2:
                im = ax.imshow(data, cmap='viridis', origin='lower', aspect='auto')
                self.fig.colorbar(im, ax=ax)
                ax.set_title(f"Slice [{self.axis_x}, {self.axis_y}]")
            else:
                ax.plot(data.flatten())
                ax.set_title("1D Slice")
        self.canvas.draw()
        if self.callback:
            self.callback(self.slice_indices)

    HAS_GUI = True


def get_custom_icon(icon_name):
    """Load a custom icon from the project root directory."""
    # Get the project root directory (parent of the current directory)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    icon_path = os.path.join(project_root, f"{icon_name}.png")
    
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    else:
        # Fallback to theme icon if custom icon doesn't exist
        return QIcon.fromTheme(icon_name)
    
if not HAS_GUI:




    class MainWindow:
        # --- HELIX / SPIRAL SHAPE TOOL (Selectable, parametric) ---
        from adaptivecad.command_defs import Feature
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
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
                from OCC.Core.gp import gp_Pnt
                import numpy as np
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
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
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
                mw.win.statusBar().showMessage(f"Helix created: radius={radius}, pitch={pitch}, height={height}", 3000)

        # Register Helix tool after add_shape_tool is defined (moved below)
        """Placeholder when GUI deps are unavailable."""
        pass
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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
                from OCC.Core.gp import gp_Pnt
                from OCC.Core.gp import gp_Trsf
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
                rx = params["rx"]
                ry = params["ry"]
                rz = params["rz"]
                sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 1.0).Shape()
                trsf = gp_Trsf()
                trsf.SetValues(
                    rx, 0, 0, 0,
                    0, ry, 0, 0,
                    0, 0, rz, 0
                )
                ellipsoid = BRepBuilderAPI_Transform(sphere, trsf, True).Shape()
                return ellipsoid

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewEllipsoidCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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
                feat = MainWindow.EllipsoidFeature(rx, ry, rz)
                try:
                    from adaptivecad.command_defs import DOCUMENT
                    DOCUMENT.append(feat)
                except Exception:
                    pass
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage(f"Ellipsoid created: rx={rx}, ry={ry}, rz={rz}", 3000)
        # Register Ellipsoid tool after add_shape_tool is defined (moved below)

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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
                from OCC.Core.gp import gp_Pnt
                from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
                height = params["height"]
                radius = params["radius"]
                cyl_height = max(0.0, height - 2 * radius)
                cyl = BRepPrimAPI_MakeCylinder(radius, cyl_height).Shape()
                sph1 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), radius, 0, 0.5 * 3.141592653589793).Shape()
                sph2 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, cyl_height), radius, 0.5 * 3.141592653589793, 3.141592653589793).Shape()
                fuse1 = BRepAlgoAPI_Fuse(cyl, sph1).Shape()
                capsule = BRepAlgoAPI_Fuse(fuse1, sph2).Shape()
                return capsule

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewCapsuleCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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
                feat = MainWindow.CapsuleFeature(height, radius)
                try:
                    from adaptivecad.command_defs import DOCUMENT
                    DOCUMENT.append(feat)
                except Exception:
                    pass
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage(f"Capsule created: height={height}, radius={radius}", 3000)

        # --- SUPERELLIPSE SHAPE TOOL ---
        class SuperellipseFeature(Feature):
            def __init__(self, a, b, n, height):
                params = {"a": a, "b": b, "n": n, "height": height}
                shape = self._make_shape(params)
                super().__init__("Superellipse", params, shape)

            @staticmethod
            def _make_shape(params):
                from OCC.Core.gp import gp_Pnt
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
                from OCC.Core.gp import gp_Vec
                import numpy as np
                a = params["a"]
                b = params["b"]
                n = params["n"]
                height = params["height"]
                ts = np.linspace(0, 2 * np.pi, 60)
                pts = []
                for t in ts:
                    ct = np.cos(t)
                    st = np.sin(t)
                    x = np.sign(ct) * (abs(ct) ** (2 / n)) * a
                    y = np.sign(st) * (abs(st) ** (2 / n)) * b
                    pts.append(gp_Pnt(x, y, 0))
                wire = BRepBuilderAPI_MakeWire()
                for p1, p2 in zip(pts, pts[1:] + [pts[0]]):
                    wire.Add(BRepBuilderAPI_MakeEdge(p1, p2).Edge())
                prism = BRepPrimAPI_MakePrism(wire.Wire(), gp_Vec(0, 0, height))
                return prism.Shape()

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewSuperellipseCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
                class ParamDialog(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.setWindowTitle("Superellipse Parameters")
                        layout = QFormLayout(self)
                        self.a = QDoubleSpinBox(); self.a.setRange(1, 1000); self.a.setValue(20.0)
                        self.b = QDoubleSpinBox(); self.b.setRange(1, 1000); self.b.setValue(20.0)
                        self.n = QDoubleSpinBox(); self.n.setRange(0.1, 10.0); self.n.setValue(2.0)
                        self.height = QDoubleSpinBox(); self.height.setRange(0.1, 1000); self.height.setValue(10.0)
                        layout.addRow("A", self.a)
                        layout.addRow("B", self.b)
                        layout.addRow("Exponent", self.n)
                        layout.addRow("Height", self.height)
                        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                        buttons.accepted.connect(self.accept)
                        buttons.rejected.connect(self.reject)
                        layout.addWidget(buttons)
                dlg = ParamDialog(mw.win)
                if not dlg.exec():
                    return
                feat = SuperellipseFeature(dlg.a.value(), dlg.b.value(), dlg.n.value(), dlg.height.value())
                try:
                    from adaptivecad.command_defs import DOCUMENT
                    DOCUMENT.append(feat)
                except Exception:
                    pass
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage("Superellipse created", 3000)
        # Register Capsule tool after add_shape_tool is defined (moved below)

    def start_snap_workflow(self):
        self.snap_phase = None
        self.active_snap = None
        self.target_snap = None
        self.snap_ref_marker = None
        self.snap_target_marker = None
        self.clear_snap_markers()
        self.win.statusBar().showMessage("Select object and snap point to use as reference.")

    def _on_mouse_press_snap(self, x, y, buttons, modifiers):
        """Handle mouse press events for snap workflow."""
        # Check if we're in snap mode and handle accordingly
        if hasattr(self, "snap_phase") and self.snap_phase is not None:
            # Handle snap workflow (simplified version for now)
            return True
        
        # If not in snap mode, return False to continue with normal handling
        return False

    def _on_mouse_press(self, x, y, buttons, modifiers):
        # --- SNAP WORKFLOW ---
        if getattr(self, "snap_phase", None) is None:
            # Check if a feature is selected
            if self.selected_feature:
                self.show_snap_points(self.selected_feature)
                self.snap_phase = "reference"
                self.win.statusBar().showMessage("Click a snap marker to pick reference point.")
            return True
        elif self.snap_phase == "reference":
            # Check if a snap marker was clicked
            marker = self._find_snap_marker_near(x, y)
            if marker:
                marker_obj, pt, snap_type, feature = marker
                self.active_snap = {"feature": feature, "point": pt, "type": snap_type}
                self.snap_ref_marker = marker_obj
                self.highlight_snap_marker(marker_obj)
                self.win.statusBar().showMessage(f"Reference snap: {snap_type}. Now select target object.")
                self.snap_phase = "target_select"
                self.clear_snap_markers()
            return True
        elif self.snap_phase == "target_select":
            # Wait for user to select a target feature
            if self.selected_feature and self.selected_feature != self.active_snap["feature"]:
                self.show_snap_points(self.selected_feature)
                self.snap_phase = "target"
                self.win.statusBar().showMessage("Click a snap marker on target object.")
            return True
        elif self.snap_phase == "target":
            marker = self._find_snap_marker_near(x, y)
            if marker:
                marker_obj, pt, snap_type, feature = marker
                self.target_snap = {"feature": feature, "point": pt, "type": snap_type}
                self.snap_target_marker = marker_obj
                self.highlight_snap_marker(marker_obj)
                # Move feature
                self.move_feature_to_snap(self.active_snap["feature"], self.active_snap["point"], pt)
                self.clear_snap_markers()
                self.snap_phase = None
                self.win.statusBar().showMessage("Snapped! Press ESC to cancel or start again.")
            return True
        return False

    def _find_snap_marker_near(self, x, y, tol=12):
        # Find a snap marker near the mouse click (screen coords)
        if not hasattr(self, "snap_markers"):
            return None
        for marker, pt, snap_type, feature in self.snap_markers:
            # Project marker to screen
            try:
                screen_pt = self.view._display.View.Project(marker.Component().X(), marker.Component().Y(), marker.Component().Z())
                if abs(screen_pt[0] - x) < tol and abs(screen_pt[1] - y) < tol:
                    return (marker, pt, snap_type, feature)
            except Exception:
                continue
        return None

    def move_feature_to_snap(self, feature, ref_point, target_point):
        import numpy as np
        delta = np.array(target_point) - np.array(ref_point)
        feature.apply_translation(delta)
        rebuild_scene(self.view._display)

    def keyPressEvent(self, event):
        # ESC cancels snap workflow
        if event.key() == self.Qt.Key_Escape:
            self.start_snap_workflow()
            self.win.statusBar().showMessage("Snap canceled.")
            return
        self._keyPressEvent(event)

    # Optionally, call self.start_snap_workflow() in __init__ or after selection
        """Placeholder when GUI deps are unavailable."""

    def _require_gui_modules():
        raise RuntimeError(
            "PySide6 and pythonocc-core are required to run the playground"
        )

else:
    # Real implementation would go here in a full installation. We keep it minimal
    # for testing without GUI dependencies.
    from PySide6.QtWidgets import QApplication, QMainWindow  # type: ignore

    def _require_gui_modules():
        """Import optional GUI modules required for GUI execution."""
        try:
            from PySide6.QtWidgets import (
                QApplication,
                QMainWindow,
                QToolBar,
                QMessageBox,
                QLabel,
            )
            from PySide6.QtGui import QIcon, QAction
            from OCC.Display import backend

            backend.load_backend("pyside6")
            from OCC.Display.qtDisplay import qtViewer3d
        except Exception as exc:  # pragma: no cover - import error path
            raise RuntimeError(
                "GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6"
            ) from exc

        return (
            QApplication,
            QMainWindow,
            qtViewer3d,
            QAction,
            QIcon,
            QToolBar,
            QMessageBox,
            QLabel,
        )

    class MainWindow:
        def __init__(self) -> None:
            self.app = QApplication([])
            self.win = QMainWindow()


def helix_wire(radius=20, pitch=5, height=40, n=250):
    """Create a helix wire shape."""
    try:
        from OCC.Core.BRepBuilderAPI import (
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeWire,
        )
        from OCC.Core.gp import gp_Pnt

        ts = np.linspace(0, 2 * pi * height / pitch, n)
        pts = [
            gp_Pnt(radius * cos(t), radius * sin(t), pitch * t / (2 * pi)) for t in ts
        ]
        wire = BRepBuilderAPI_MakeWire()
        for a, b in zip(pts[:-1], pts[1:]):
            wire.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
        return wire.Wire()
    except Exception as exc:
        print(f"Error creating helix: {exc}")
        return None


def on_select(shape, *k):
    """Selection callback for interactive shape selection."""
    try:
        t = shape.ShapeType()
        print("Selected", t, "-", shape)
    except Exception as exc:
        print(f"Selection error: {exc}")


def _demo_primitives(display):
    """Create a demo scene using simple primitives."""
    if display is None:
        return

    try:
        from adaptivecad import geom, linalg
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    except ImportError as exc:
        print(f"Error loading modules: {exc}")
        print("Make sure pythonocc-core and PySide6 are installed:")
        print("    conda install -c conda-forge pythonocc-core pyside6")
        return
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return

    try:
        # Clear previous demo if any
        display.EraseAll()

        # Create a box and a helix
        box = BRepPrimAPI_MakeBox(50, 50, 10).Shape()
        helx = helix_wire()

        # Display the shapes
        display.DisplayShape(box, update=False, transparency=0.2)
        if helx:  # Only display helix if created successfully
            display.DisplayShape(helx, color="YELLOW")

        # Apply shading for better visualization
        try:
            if hasattr(display, "SetShadingMode"):
                display.SetShadingMode(3)  # Phong shading
        except Exception as exc:
            print(f"Could not set shading mode: {exc}")

        display.FitAll()
    except Exception as exc:
        print(f"Error creating demo scene: {exc}")
        # Fall back to simpler demo if full scene fails
        try:
            simple_shape = BRepPrimAPI_MakeBox(100, 100, 100).Shape()
            display.DisplayShape(simple_shape)
            display.FitAll()
        except Exception as e:
            print(f"Failed to create even a simple demo shape: {e}")


class SettingsDialog:
    @staticmethod
    def show(parent):
        defl = settings.MESH_DEFLECTION
        angle = settings.MESH_ANGLE
        defl, ok = QInputDialog.getDouble(
            parent,
            "Mesh Deflection",
            "Deflection (mm, lower=smoother):",
            defl,
            0.001,
            1.0,
            3,
        )
        if not ok:
            return
        angle, ok = QInputDialog.getDouble(
            parent,
            "Mesh Angle",
            "Angle (radians, lower=smoother):",
            angle,
            0.001,
            1.0,
            3,
        )
        if not ok:
            return

        # GPU acceleration checkbox
        box = QMessageBox(parent)
        box.setWindowTitle("GPU Support")
        box.setText("Enable GPU acceleration?")
        cb = QCheckBox("Enable GPU")
        cb.setChecked(settings.USE_GPU)
        box.setCheckBox(cb)
        box.exec()

        settings.MESH_DEFLECTION = defl
        settings.MESH_ANGLE = angle
        settings.USE_GPU = cb.isChecked()

        # ...existing code...


class MainWindow:
    def resizeEvent(self, event):
        if hasattr(self, "_position_viewcube"):
            self._position_viewcube()
        super(type(self.win), self.win).resizeEvent(event)

    def add_view_toolbar(self):
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QToolBar

        tb = QToolBar("Views", self.win)
        self.win.addToolBar(tb)
        occ_display = self.view._display
        view_map = {
            "Home": occ_display.View_Iso,
            "Top": occ_display.View_Top,
            "Bottom": occ_display.View_Bottom,
            "Front": occ_display.View_Front,
            "Back": occ_display.View_Rear,
            "Left": occ_display.View_Left,
            "Right": occ_display.View_Right,
        }
        for name, fn in view_map.items():
            act = QAction(name, self.win)

            def make_slot(f):
                return lambda checked=False: [f(), occ_display.FitAll()]

            act.triggered.connect(make_slot(fn))
            tb.addAction(act)
        self.views_toolbar = tb

    def add_view_mode_toolbar(self):
        """Add a toolbar for display modes like shaded or wireframe."""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QToolBar

        tb = QToolBar("Display Modes", self.win)
        self.win.addToolBar(tb)

        modes = {
            "Shaded": 1,
            "Wireframe": 0,
            "Hidden Lines": 2,
        }

        for label, mode in modes.items():
            act = QAction(label, self.win)
            act.triggered.connect(lambda checked=False, m=mode: self.set_view_mode(m))
            tb.addAction(act)

        self.view_mode_toolbar = tb

    def set_view_mode(self, mode: int) -> None:
        """Apply the given OCC display mode to all displayed objects."""
        ctx = self.view._display.Context
        for ais in ctx.DisplayedObjects():
            try:
                ctx.SetDisplayMode(ais, mode, True)
            except Exception:
                pass
        ctx.UpdateCurrentViewer()

    def clear_property_panel(self, show_placeholder=True):
        """Remove all widgets from the property panel."""
        from PySide6.QtWidgets import QLabel
        # Remove all widgets and layouts from the property panel
        while self.property_layout.count():
            item = self.property_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            layout = item.layout()
            if layout:
                while layout.count():
                    subitem = layout.takeAt(0)
                    subwidget = subitem.widget()
                    if subwidget:
                        subwidget.deleteLater()
        if show_placeholder:
            self.property_layout.addWidget(QLabel("No selection."))

    def _init_property_panel(self):
        from PySide6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt

        self.property_dock = QDockWidget("Properties", self.win)
        self.property_widget = QWidget()
        self.property_layout = QVBoxLayout()
        self.property_widget.setLayout(self.property_layout)
        self.property_dock.setWidget(self.property_widget)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.property_dock)
        self.property_dock.setVisible(True)
        self.selected_feature = None  # Track the currently selected feature

    def _build_snap_menu(self):
        snap_menu = self.win.menuBar().addMenu("Snaps")
        self.snap_actions = {}
        for _, strat in self.snap_manager.strategies:
            name = strat.__name__
            act = QAction(name.replace("_", " ").title(), self.win, checkable=True)
            act.setChecked(self.snap_manager.is_enabled(name))
            act.toggled.connect(
                lambda checked, n=name: self.snap_manager.enable_strategy(n, checked)
            )
            snap_menu.addAction(act)
            self.snap_actions[name] = act

    def _show_properties(self, obj):
        from PySide6.QtWidgets import QLabel, QLineEdit, QHBoxLayout

        # Clear previous widgets
        self.clear_property_panel(show_placeholder=False)
        self.property_layout.addWidget(QLabel(f"Type: {type(obj).__name__}"))

        # Show editable attributes (simple, non-callable, non-private)
        def is_editable(val):
            return isinstance(val, (int, float, str, bool))

        # If this is a Feature with params, show params as editable fields
        is_feature = hasattr(obj, "params") and isinstance(
            getattr(obj, "params", None), dict
        )
        params = obj.params if is_feature else None
        shown_attrs = set()
        param_editors = {}
        if params:
            for key, val in params.items():
                row = QHBoxLayout()
                row.addWidget(QLabel(f"{key}: "))
                if is_editable(val):
                    editor = QLineEdit(str(val))
                    param_editors[key] = (editor, type(val))
                    row.addWidget(editor)
                else:
                    row.addWidget(QLabel(str(val)))
                self.property_layout.addLayout(row)
                shown_attrs.add(key)

            # Add Apply button for param updates
            from PySide6.QtWidgets import QPushButton

            apply_btn = QPushButton("Apply")

            def on_apply():
                for k, (editor, typ) in param_editors.items():
                    text = editor.text()
                    try:
                        if typ is bool:
                            new_val = text.lower() in ("1", "true", "yes", "on")
                        else:
                            new_val = typ(text)
                        obj.params[k] = new_val
                    except Exception:
                        editor.setText(str(obj.params[k]))  # revert
                # If the feature has a rebuild/update method, call it
                if hasattr(obj, "rebuild") and callable(obj.rebuild):
                    obj.rebuild()
                # Always update the viewer
                if hasattr(self, "view") and hasattr(self.view, "_display"):
                    try:
                        rebuild_scene(self.view._display)
                    except Exception:
                        pass

            apply_btn.clicked.connect(on_apply)
            self.property_layout.addWidget(apply_btn)
        # Show other attributes as before
        for attr in dir(obj):
            if (
                attr.startswith("_")
                or callable(getattr(obj, attr))
                or attr in shown_attrs
            ):
                continue
            val = getattr(obj, attr)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{attr}: "))
            if is_editable(val):
                editor = QLineEdit(str(val))

                def make_setter(attr_name, typ):
                    def setter():
                        text = editor.text()
                        try:
                            if typ is bool:
                                new_val = text.lower() in ("1", "true", "yes", "on")
                            else:
                                new_val = typ(text)
                            setattr(obj, attr_name, new_val)
                            if hasattr(self, "view") and hasattr(self.view, "_display"):
                                try:
                                    rebuild_scene(self.view._display)
                                except Exception:
                                    pass
                        except Exception as e:
                            editor.setText(str(getattr(obj, attr_name)))  # revert

                    return setter

                editor.editingFinished.connect(make_setter(attr, type(val)))
                row.addWidget(editor)
            else:
                row.addWidget(QLabel(str(val)))
            self.property_layout.addLayout(row)

        # Track the selected feature for deletion
        from adaptivecad.command_defs import Feature

        if isinstance(obj, Feature):
            self.selected_feature = obj
        else:
            self.selected_feature = None

    def show_ndfield_slicer(self, ndfield):
        """Show the advanced NDField slicer dock for a given NDField object."""
        # Remove previous slicer if present
        if hasattr(self, 'ndfield_slicer_dock') and self.ndfield_slicer_dock is not None:
            self.ndfield_slicer_dock.setParent(None)
            self.ndfield_slicer_dock.deleteLater()
        def on_slice_update(slice_indices):
            # Optionally handle slice updates (e.g., update other UI)
            pass
        self.ndfield_slicer = NDSliceWidget(ndfield, on_slice_update)
        dock = QDockWidget("NDField Slicer", self.win)
        dock.setWidget(self.ndfield_slicer)
        self.win.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.ndfield_slicer_dock = dock

    def add_ndfield_slicer_menu(self):
        """Add NDField Slicer Demo action to the menu bar."""
        ndfield_action = self.win.menuBar().addAction("NDField Slicer Demo")
        def launch_ndfield_demo():
            from adaptivecad.ndfield import NDField
            grid_shape = [8, 8, 8, 8]
            values = np.random.rand(*grid_shape)
            ndfield = NDField(grid_shape, values)
            self.show_ndfield_slicer(ndfield)
        ndfield_action.triggered.connect(launch_ndfield_demo)

    from adaptivecad.command_defs import BaseCmd

    def run_cmd(self, cmd: BaseCmd) -> None:
        """Run a command on the main window."""
        try:
            print(f"Running command: {cmd.__class__.__name__}")
            cmd.run(self)
            print(f"Command completed: {cmd.__class__.__name__}")
        except Exception as e:
            import traceback
            print(f"Error running command {cmd.__class__.__name__}: {e}")
            print(traceback.format_exc())
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self.win, "Command Error", f"Error executing {cmd.__class__.__name__}:\n\n{e}")
                self.win.statusBar().showMessage(f"Command failed: {e}", 4000)
            except:
                print("Could not display error dialog")
                pass

    """Main Playground window."""
    def __init__(self, existing_app=None) -> None:
        print("MainWindow.__init__ starting")
        # Initialize attributes
        self.app = None
        self.win = None
        self.view = None
        self.current_mode = "Navigate"  # Navigate, Pick, PushPull, Sketch
        self.push_pull_cmd: PushPullFeatureCmd | None = None
        self.initial_drag_pos = None  # For PushPull dragging
        print("MainWindow attributes initialized")
        
        # Import Qt here to ensure it's defined
        from PySide6.QtCore import Qt
        self.Qt = Qt # Store Qt for use in _keyPressEvent

        # Get the required GUI modules
        result = _require_gui_modules()
        (
            QApplication,
            QMainWindow,
            qtViewer3d,
            QAction,
            QIcon,
            QToolBar,
            q_message_box,  # Renamed to avoid conflict if self.QMessageBox is used elsewhere
            QLabel,
        ) = result
        self.QMessageBox = q_message_box  # Store as instance attribute

        # Store GUI classes as instance attributes for use throughout the class
        self.QApplication = QApplication
        self.QMainWindow = QMainWindow
        self.qtViewer3d = qtViewer3d
        self.QAction = QAction
        self.QIcon = QIcon
        self.QToolBar = QToolBar
        self.QLabel = QLabel

        # Check if GUI modules are available
        if qtViewer3d is None:
            print(
                "GUI extras not installed. Run:\n   conda install -c conda-forge pythonocc-core pyside6"
            )
            return

        # Set up the application
        if existing_app is not None:
            # Use the provided QApplication instance
            self.app = existing_app
        else:
            # Check if there's an existing QApplication instance
            existing_qapp = QApplication.instance()
            if existing_qapp is not None:
                self.app = existing_qapp
                print("Using existing QApplication instance")
            else:
                # Create a new QApplication instance
                self.app = QApplication(sys.argv)
                print("Created new QApplication instance")

        self.win = QMainWindow()
        self.win.setWindowTitle("AdaptiveCAD – Playground")
        self.view = qtViewer3d(self.win)
        self.win.setCentralWidget(self.view)
        self.view.show()  # Explicitly show the view

        # Add NDField Slicer menu action
        self.add_ndfield_slicer_menu()

        # Initialize snap marker
        self.current_snap_marker = None

        # Enable GPU acceleration when requested
        if settings.USE_GPU:
            try:
                view = self.view._display.View
                if hasattr(view, "SetRaytracingMode"):
                    view.SetRaytracingMode(True)
            except Exception as exc:
                print(f"Could not enable GPU acceleration: {exc}")

        # --- Add View Cube overlay ---
        self.viewcube = ViewCubeWidget(self.view._display, self.view)
        self._position_viewcube()
        self.viewcube.show()

        # Reposition cube on view resize
        original_resize = self.view.resizeEvent

        def resizeEvent(evt):
            if original_resize:
                original_resize(evt)
            self._position_viewcube()

        self.view.resizeEvent = resizeEvent

        # Add menu toggle for View Cube
        viewcube_action = QAction("Show View Cube", self.win, checkable=True)
        viewcube_action.setChecked(True)

        def toggle_cube(checked):
            self.viewcube.setVisible(checked)

        viewcube_action.triggered.connect(toggle_cube)
        self.win.menuBar().addAction(viewcube_action)
        self._init_property_panel()  # Initialize property dock
        from PySide6.QtCore import Qt
        from adaptivecad.gui.snap_menu import SnapMenu
        self.snap_menu = SnapMenu(self)
        self.win.addDockWidget(Qt.RightDockWidgetArea, self.snap_menu)
        # Initialize SnapManager
        from adaptivecad.snap import SnapManager
        from adaptivecad.snap_strategies import (
            grid_snap,
            endpoint_snap,
            midpoint_snap,
            center_snap,
        )

        self.snap_manager = SnapManager()
        # world-space tolerance for snap strategies
        self.snap_world_tol = 0.5
        self.snap_manager.register(endpoint_snap, priority=20)
        self.snap_manager.register(midpoint_snap, priority=15)
        self.snap_manager.register(center_snap, priority=15)
        self.snap_manager.register(grid_snap, priority=10)
        self.current_snap_point = None
        # Note: Snap tolerance slider will be added in the run method        # Override mouse events instead of connecting to signals that don't exist
        # Override the qtViewer3d's mouse event handlers
        original_mouseMoveEvent = self.view.mouseMoveEvent
        original_mousePressEvent = self.view.mousePressEvent
        original_mouseReleaseEvent = self.view.mouseReleaseEvent
        
        def mouseMoveEvent_override(event):
            # Call the original handler first
            original_mouseMoveEvent(event)
            # Fix: Use a valid method to convert screen to world coordinates
            try:
                # Use position() instead of pos() to avoid deprecation warning
                pos = event.position() if hasattr(event, 'position') else event.pos()
                x, y = int(pos.x()), int(pos.y())
                
                if hasattr(self.view._display, "View") and hasattr(
                    self.view._display.View, "ConvertToGrid"
                ):
                    world_pt = self.view._display.View.ConvertToGrid(x, y)
                elif hasattr(self.view._display, "ConvertToPoint"):
                    world_pt = self.view._display.ConvertToPoint(x, y)
                elif hasattr(self.view._display, "convertToPoint"):
                    world_pt = self.view._display.convertToPoint(x, y)
                else:
                    # Fallback: just use zeros or the event position as a placeholder
                    world_pt = [0.0, 0.0, 0.0]
            except:  # Fallback if any conversion fails
                world_pt = [0.0, 0.0, 0.0]
            
            self._on_mouse_move(world_pt)
            
        def mousePressEvent_override(event):
            # Call the original handler first
            original_mousePressEvent(event)
            # Then call our custom handler
            # Use position() instead of pos() to avoid deprecation warning
            pos = event.position() if hasattr(event, 'position') else event.pos()
            self._on_mouse_press(
                int(pos.x()), int(pos.y()), event.buttons(), event.modifiers()
            )

        def mouseReleaseEvent_override(event):
            # Call the original handler first
            original_mouseReleaseEvent(event)
            # Then call our custom handler
            # Use position() instead of pos() to avoid deprecation warning
            pos = event.position() if hasattr(event, 'position') else event.pos()
            self._on_mouse_release(
                int(pos.x()), int(pos.y()), event.buttons(), event.modifiers()
            )

        # Apply the overrides
        self.view.mouseMoveEvent = mouseMoveEvent_override
        self.view.mousePressEvent = mousePressEvent_override
        self.view.mouseReleaseEvent = mouseReleaseEvent_override

        # Viewport polish - try each enhancement feature
        try:
            # Try displaying trihedron (axes)
            if hasattr(self.view._display, "DisplayTrihedron"):
                self.view._display.DisplayTrihedron()
            elif hasattr(self.view._display, "display_trihedron"):
                self.view._display.display_trihedron()
            else:
                print(
                    "Warning: Trihedron display method not found. Skipping axes display."
                )
        except Exception as e:
            print(f"Warning: Could not display trihedron: {e}")

        try:
            # Try enabling grid
            if hasattr(self.view._display, "enable_grid"):
                self.view._display.enable_grid()
            elif hasattr(self.view._display, "display_grid"):
                self.view._display.display_grid()
            else:
                print("Warning: Grid enable method not found. Skipping grid display.")
        except Exception as e:
            print(f"Warning: Could not enable grid: {e}")

        # Try setting anti-aliasing
        if AA_AVAILABLE:
            try:
                self.view._display.View.SetAntialiasingMode(AA.V3d_MSAA_8X)
            except Exception as exc:
                print(f"Warning: Could not enable anti-aliasing: {exc}")

        # Try setting background gradient colors
        try:
            self.view._display.SetBgGradientColor(0.12, 0.12, 0.12, 0.18, 0.18, 0.18)
        except Exception as e:
            print(f"Warning: Could not set background color: {e}")
            try:
                # Fallback to any available background color method
                if hasattr(self.view._display, "set_bg_gradient_color"):
                    self.view._display.set_bg_gradient_color(
                        0.12, 0.12, 0.12, 0.18, 0.18, 0.18
                    )
            except:
                print(
                    "Could not set background color using any known method."
                )  # Property tool and selection callback

        try:
            self.props_tool = Props()

            def on_select(shape, *k):
                # If selection is a list, unwrap it
                if isinstance(shape, list) and shape:
                    shape = shape[0]
                try:
                    t = (
                        shape.ShapeType()
                        if hasattr(shape, "ShapeType")
                        else type(shape).__name__
                    )
                    try:
                        mass = round(self.props_tool.Volume(shape), 3)
                    except Exception:
                        mass = "n/a"
                    self.win.statusBar().showMessage(
                        f"Selected {t} | volume ≈ {mass} mm³"
                    )
                except Exception as e:
                    print(f"Selection callback error: {e}")

                # --- Show properties in side panel if shape is a Feature or NDField ---
                from adaptivecad.command_defs import DOCUMENT

                found = None
                for feat in DOCUMENT:
                    if hasattr(feat, "shape") and hasattr(shape, "IsEqual"):
                        try:
                            if shape.IsEqual(feat.shape):
                                found = feat
                                break
                        except Exception:
                            continue
                if found is not None:
                    self._show_properties(found)
                else:
                    # Try NDField: look for .shape or .values attribute
                    from adaptivecad.ndfield import NDField

                    for obj in DOCUMENT:
                        if isinstance(obj, NDField):
                            self._show_properties(obj)
                            break
                    else:
                        # Fallback: show the shape itself
                        self._show_properties(shape)

            # Try to register selection callback
            if hasattr(self.view._display, "register_select_callback"):
                self.view._display.register_select_callback(on_select)
            elif hasattr(self.view._display, "SetSelectionCallBack"):
                self.view._display.SetSelectionCallBack(on_select)
            else:
                print(
                    "Warning: Could not register selection callback - method not found"
                )

            # Try to set selection mode for edges
            try:
                if hasattr(self.view._display, "SetSelectionModeEdge"):
                    self.view._display.SetSelectionModeEdge()
                elif hasattr(self.view._display, "set_selection_mode_edge"):
                    self.view._display.set_selection_mode_edge()
                else:
                    print("Warning: Could not enable edge selection - method not found")
            except Exception as e:
                print(f"Warning: Could not set selection mode: {e}")
        except Exception as e:
            print(f"Warning: Could not set up selection callback: {e}")

        # Create menu bar with reload action
        reload_action = self.win.menuBar().addAction("Reload  (R)")
        reload_action.setShortcut("R")
        reload_action.triggered.connect(self._build_demo)

        # Add Grid Snap toggle action
        grid_snap_action = QAction("Toggle Grid Snap (G)", self.win)
        grid_snap_action.setShortcut("G")
        grid_snap_action.triggered.connect(self.toggle_grid_snap)
        self.win.addAction(grid_snap_action)  # Add to window to catch shortcut

        # Add Push-Pull mode toggle action
        push_pull_action = QAction("Push-Pull (P)", self.win)
        push_pull_action.setShortcut("P")
        push_pull_action.triggered.connect(self.toggle_push_pull_mode)
        self.win.addAction(push_pull_action)

        # Add Settings action to menu
        settings_action = self.win.menuBar().addAction("Settings")
        settings_action.triggered.connect(
            lambda: (SettingsDialog.show(self.win), self._build_demo())
        )  # Set status bar message with navigation help
        self.win.statusBar().showMessage(
            "LMB‑drag = rotate | MMB = pan | Wheel = zoom | Shift+MMB = fit"
        )

        # --- SINGLE TOOLBAR WITH MENU BUTTONS ---
        from PySide6.QtWidgets import QToolButton, QMenu, QMessageBox

        self.main_toolbar = QToolBar("Main", self.win)
        self.main_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.win.addToolBar(Qt.TopToolBarArea, self.main_toolbar)

        # File menu (for export/save)
        file_menu = QMenu("File", self.win)
        def add_file_action(text, icon_name, cmd_cls):
            act = QAction(QIcon.fromTheme(icon_name), text, self.win)
            act.triggered.connect(lambda: self.run_cmd(cmd_cls()))
            file_menu.addAction(act)
        add_file_action("Export STL", "document-save", ExportStlCmd)
        add_file_action("Export AMA", "document-save", ExportAmaCmd)
        add_file_action("Export GCode", "document-save", ExportGCodeCmd)
        # --- Import πₐ command ------------------------------------------------
        from adaptivecad.commands.import_conformal import ImportConformalCmd
        import_action = QAction(
            get_custom_icon("adashaper"),
            "Import πₐ Conformal",
            self.win,
        )
        import_action.triggered.connect(
            lambda: self.run_cmd(ImportConformalCmd())
        )
        file_menu.addAction(import_action)

        file_btn = QToolButton(self.win)
        file_btn.setText("File")
        file_btn.setIcon(QIcon.fromTheme("document-save"))
        file_btn.setPopupMode(QToolButton.InstantPopup)
        file_btn.setMenu(file_menu)
        self.main_toolbar.addWidget(file_btn)

        # Dedicated toolbar button for import
        import_btn = QToolButton(self.win)
        import_btn.setText("Import πₐ")
        import_btn.setIcon(get_custom_icon("adashaper"))
        import_btn.setToolTip(
            "Import file and apply πₐ conformation (prompts for κ)"
        )
        import_btn.clicked.connect(lambda: self.run_cmd(ImportConformalCmd()))
        self.main_toolbar.addWidget(import_btn)

        # --- SHAPES TOOLBAR RESTRUCTURED WITH CATEGORY MENUS ---
        self.shapes_toolbar = QToolBar("Shapes", self.win)
        self.shapes_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.win.addToolBar(Qt.TopToolBarArea, self.shapes_toolbar)

        def add_shape_action(menu, text, icon_name, cmd_cls, use_custom=False):
            icon = get_custom_icon(icon_name) if use_custom else QIcon.fromTheme(icon_name)
            act = QAction(icon, text, self.win)
            act.triggered.connect(lambda: self.run_cmd(cmd_cls()))
            menu.addAction(act)

        construct_menu = QMenu("Construct", self.win)
        procedural_menu = QMenu("Procedural", self.win)
        highdim_menu = QMenu("High-Dim", self.win)

        construct_btn = QToolButton(self.win)
        construct_btn.setText("Construct")
        construct_btn.setIcon(QIcon.fromTheme("folder"))
        construct_btn.setPopupMode(QToolButton.InstantPopup)
        construct_btn.setMenu(construct_menu)
        self.shapes_toolbar.addWidget(construct_btn)

        proc_btn = QToolButton(self.win)
        proc_btn.setText("Procedural")
        proc_btn.setIcon(QIcon.fromTheme("applications-graphics"))
        proc_btn.setPopupMode(QToolButton.InstantPopup)
        proc_btn.setMenu(procedural_menu)
        self.shapes_toolbar.addWidget(proc_btn)

        hd_btn = QToolButton(self.win)
        hd_btn.setText("High-Dim")
        hd_btn.setIcon(QIcon.fromTheme("view-restore"))
        hd_btn.setPopupMode(QToolButton.InstantPopup)
        hd_btn.setMenu(highdim_menu)
        self.shapes_toolbar.addWidget(hd_btn)

        # Import Feature class before using it
        from adaptivecad.command_defs import Feature

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
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
                from OCC.Core.gp import gp_Pnt
                import numpy as np
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
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
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
                mw.win.statusBar().showMessage(f"Helix created: radius={radius}, pitch={pitch}, height={height}", 3000)

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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
                from OCC.Core.gp import gp_Pnt, gp_Trsf
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
                rx = params["rx"]
                ry = params["ry"]
                rz = params["rz"]
                sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 1.0).Shape()
                trsf = gp_Trsf()
                trsf.SetValues(
                    rx, 0, 0, 0,
                    0, ry, 0, 0,
                    0, 0, rz, 0
                )
                ellipsoid = BRepBuilderAPI_Transform(sphere, trsf, True).Shape()
                return ellipsoid

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewEllipsoidCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
                from OCC.Core.gp import gp_Pnt
                from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
                height = params["height"]
                radius = params["radius"]
                cyl_height = max(0.0, height - 2 * radius)
                cyl = BRepPrimAPI_MakeCylinder(radius, cyl_height).Shape()
                sph1 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), radius, 0, 0.5 * np.pi).Shape()
                sph2 = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, cyl_height), radius, 0.5 * np.pi, np.pi).Shape()
                fuse1 = BRepAlgoAPI_Fuse(cyl, sph1).Shape()
                capsule = BRepAlgoAPI_Fuse(fuse1, sph2).Shape()
                return capsule

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewCapsuleCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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

        # Register advanced shape tools in menus
        add_shape_action(procedural_menu, "Helix", "media-playlist-shuffle", NewHelixCmd)
        add_shape_action(procedural_menu, "Ellipsoid", "media-record", NewEllipsoidCmd)
        add_shape_action(procedural_menu, "Capsule", "media-record", NewCapsuleCmd)

        # --- ADAPTIVE PI CURVE SHELL TOOL ---
        from adaptivecad.command_defs import Feature
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
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
                from OCC.Core.gp import gp_Pnt
                import numpy as np
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
                    # Example: πₐ curve as a sine deformation
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
                from OCC.Core.TColgp import TColgp_Array2OfPnt
                arr = TColgp_Array2OfPnt(1, n_u, 1, n_v)
                for i in range(n_u):
                    for j in range(n_v):
                        arr.SetValue(i+1, j+1, pts[j][i])
                face = BRepBuilderAPI_MakeFace(arr, 1e-6).Face()
                return face

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewPiCurveShellCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
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
                        layout.addRow("Frequency (πₐ)", self.freq)
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
                mw.win.statusBar().showMessage(f"Pi Curve Shell created: r={base_radius}, h={height}, freq={freq}, amp={amp}", 3000)

        add_shape_action(procedural_menu, "Pi Curve Shell", "adacurve", NewPiCurveShellCmd, True)
        add_shape_action(procedural_menu, "Superellipse", "draw-bezier", NewSuperellipseCmd)

        # Capsule tool is now registered below using add_shape_tool

        # --- TAPERED CYLINDER / CONE SHAPE TOOL ---
        from adaptivecad.command_defs import Feature
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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
                height = params["height"]
                r1 = params["radius1"]
                r2 = params["radius2"]
                # OCC's MakeCone: (bottom_radius, top_radius, height)
                return BRepPrimAPI_MakeCone(r1, r2, height).Shape()

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewTaperedCylinderCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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
                # Clear previous shapes for consistency with other shape tools
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage(f"Tapered Cylinder created: height={height}, r1={radius1}, r2={radius2}", 3000)


        add_shape_action(construct_menu, "Box", "view-cube", NewBoxCmd)
        add_shape_action(construct_menu, "Cylinder", "media-optical", NewCylCmd)
        add_shape_action(construct_menu, "Tapered Cylinder", "media-eject", NewTaperedCylinderCmd)
        add_shape_action(procedural_menu, "Bezier Curve", "adacurve", NewBezierCmd, True)
        add_shape_action(procedural_menu, "B-spline Curve", "adacurve", NewBSplineCmd, True)
        add_shape_action(highdim_menu, "ND Box", "cube1", NewNDBoxCmd, True)
        add_shape_action(highdim_menu, "ND Field", "view-list-tree", NewNDFieldCmd)
        add_shape_action(construct_menu, "Ball", "media-record", NewBallCmd)
        add_shape_action(construct_menu, "Torus", "preferences-desktop-theme", NewTorusCmd)
        add_shape_action(construct_menu, "Cone", "media-eject", NewConeCmd)
        add_shape_action(construct_menu, "Revolve", "object-rotate-right", RevolveCmd)

        # --- ROUNDED BOX SHAPE TOOL (Selectable, like other shapes) ---
        from adaptivecad.command_defs import Feature
        class RoundedBoxFeature(Feature):
            def __init__(self, length, width, height, fillet):
                params = {
                    "length": length,
                    "width": width,
                    "height": height,
                    "fillet": fillet,
                }
                shape = self._make_shape(params)
                super().__init__("Rounded Box", params, shape)

            @staticmethod
            def _make_shape(params):
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
                from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
                from OCC.Core.TopExp import TopExp_Explorer
                from OCC.Core.TopAbs import TopAbs_EDGE
                length = params["length"]
                width = params["width"]
                height = params["height"]
                fillet = params["fillet"]
                box = BRepPrimAPI_MakeBox(length, width, height).Shape()
                if fillet > 0:
                    mk_fillet = BRepFilletAPI_MakeFillet(box)
                    exp = TopExp_Explorer(box, TopAbs_EDGE)
                    while exp.More():
                        edge = exp.Current()
                        mk_fillet.Add(fillet, edge)
                        exp.Next()
                    return mk_fillet.Shape()
                else:
                    return box

            def rebuild(self):
                self.shape = self._make_shape(self.params)

        class NewRoundedBoxCmd:
            def __init__(self):
                pass
            def run(self, mw):
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
                class ParamDialog(QDialog):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.setWindowTitle("Rounded Box Parameters")
                        layout = QFormLayout(self)
                        self.length = QDoubleSpinBox()
                        self.length.setRange(1, 1000)
                        self.length.setValue(40.0)
                        self.width = QDoubleSpinBox()
                        self.width.setRange(1, 1000)
                        self.width.setValue(30.0)
                        self.height = QDoubleSpinBox()
                        self.height.setRange(1, 1000)
                        self.height.setValue(20.0)
                        self.fillet = QDoubleSpinBox()
                        self.fillet.setRange(0, 100)
                        self.fillet.setValue(4.0)
                        layout.addRow("Length", self.length)
                        layout.addRow("Width", self.width)
                        layout.addRow("Height", self.height)
                        layout.addRow("Fillet Radius", self.fillet)
                        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                        buttons.accepted.connect(self.accept)
                        buttons.rejected.connect(self.reject)
                        layout.addWidget(buttons)
                dlg = ParamDialog(mw.win)
                if not dlg.exec():
                    return
                length = dlg.length.value()
                width = dlg.width.value()
                height = dlg.height.value()
                fillet = dlg.fillet.value()
                feat = RoundedBoxFeature(length, width, height, fillet)
                # Add to document if available
                try:
                    from adaptivecad.command_defs import DOCUMENT
                    DOCUMENT.append(feat)
                except Exception:
                    pass
                # Clear previous shapes for consistency with other shape tools
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage(f"Rounded Box created: {length}×{width}×{height}, fillet={fillet}", 3000)
        add_shape_action(procedural_menu, "Rounded Box", "view-cube", NewRoundedBoxCmd)

        # --- TAPERED CYLINDER / CONE SHAPE TOOL (Selectable, like other shapes) ---
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
                from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
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
                from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox
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
                # Clear previous shapes for consistency with other shape tools
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(feat.shape, update=True)
                mw.view._display.FitAll()
                mw.win.statusBar().showMessage(f"Tapered Cylinder created: height={height}, bottom radius={radius1}, top radius={radius2}", 3000)
        add_shape_action(construct_menu, "Tapered Cylinder", "media-eject", NewTaperedCylinderCmd)
        add_shape_action(procedural_menu, "π‑Square", "draw-rectangle", PiSquareCmd)
        add_shape_action(procedural_menu, "Draped Sheet", "adasurface", DrapedSheetCmd, True)
        add_shape_action(construct_menu, "Loft", "document-new", LoftCmd)
        add_shape_action(construct_menu, "Sweep", "media-seek-forward", SweepAlongPathCmd)
        add_shape_action(construct_menu, "Shell", "edit-undo", ShellCmd)

        # Tools menu
        tools_menu = QMenu("Tools", self.win)

        def add_tool_action(text, icon_name, handler, use_custom=False):
            # Use custom icon if specified, otherwise use theme icon
            icon = get_custom_icon(icon_name) if use_custom else QIcon.fromTheme(icon_name)
            act = QAction(icon, text, self.win)
            act.triggered.connect(handler)
            tools_menu.addAction(act)

        add_tool_action("Move", "transform-move", lambda: self.run_cmd(MoveCmd()))
        add_tool_action("Scale", "zoom-in", lambda: self.run_cmd(ScaleCmd()))
        add_tool_action(
            "Push-Pull", "transform-scale", lambda: self.enter_push_pull_mode()
        )
        add_tool_action("Union", "union", lambda: self.run_cmd(UnionCmd()), True)  # Using custom union icon
        add_tool_action("Cut", "edit-cut", lambda: self.run_cmd(CutCmd()))
        add_tool_action("Intersect", "zoom-original", lambda: self.run_cmd(IntersectCmd()))
        
        def on_delete():
            if self.selected_feature is not None:
                from adaptivecad.gui.delete_utils import delete_selected_feature

                deleted = delete_selected_feature(self.selected_feature)
                if deleted:
                    self.selected_feature = None
                    self.clear_property_panel()
                    rebuild_scene(self.view._display)
                    self.win.statusBar().showMessage("Object deleted.", 2000)
                else:
                    self.win.statusBar().showMessage("Could not delete object.", 2000)
            else:
                QMessageBox.information(
                    self.win, "Delete", "No object selected for deletion."
                )

        add_tool_action("Delete", "edit-delete", on_delete)
        add_tool_action("Clear Selection", "edit-clear", self.clear_property_panel)
        tools_btn = QToolButton(self.win)
        tools_btn.setText("Tools")
        tools_btn.setIcon(QIcon.fromTheme("transform-move"))
        tools_btn.setPopupMode(QToolButton.InstantPopup)
        tools_btn.setMenu(tools_menu)
        self.main_toolbar.addWidget(tools_btn)

        # Settings menu (single action)
        settings_btn = QToolButton(self.win)
        settings_btn.setText("Settings")
        settings_btn.setIcon(QIcon.fromTheme("preferences-system"))
        settings_btn.setPopupMode(QToolButton.InstantPopup)
        settings_menu = QMenu("Settings", self.win)
        settings_action = QAction("Settings", self.win)
        settings_action.triggered.connect(
            lambda: (SettingsDialog.show(self.win), self._build_demo())
        )
        settings_menu.addAction(settings_action)
        settings_btn.setMenu(settings_menu)
        self.main_toolbar.addWidget(settings_btn)

        # Add Views toolbar (unchanged)
        self.add_view_toolbar()
        # Add toolbar for display modes (shaded, wireframe, etc.)
        self.add_view_mode_toolbar()

    def _build_demo(self) -> None:
        """Build or rebuild the demo scene."""
        if (
            hasattr(self, "view")
            and self.view is not None
            and hasattr(self.view, "_display")
        ):
            _demo_primitives(self.view._display)
        self.clear_property_panel()
        
        # Add debug button for import testing
        from PySide6.QtWidgets import QPushButton
        debug_btn = QPushButton("Debug Import")
        self.property_layout.addWidget(debug_btn)
        
        def debug_import():
            try:
                print("Attempting to debug import functionality...")
                from adaptivecad.commands.import_conformal import ImportConformalCmd
                cmd = ImportConformalCmd()
                print("Created ImportConformalCmd instance")
                self.run_cmd(cmd)
                print("Called run_cmd with ImportConformalCmd")
            except Exception as e:
                import traceback
                print(f"Debug import error: {e}")
                print(traceback.format_exc())
                
        debug_btn.clicked.connect(debug_import)

    def _position_viewcube(self):
        if hasattr(self, "viewcube") and self.viewcube.parent() is self.view:
            self.viewcube.move(self.view.width() - self.viewcube.width() - 10, 10)

    def _on_mouse_press(self, x, y, buttons, modifiers):
        # Check if we're in the snap workflow first
        if hasattr(self, "snap_phase") and self._on_mouse_press_snap(x, y, buttons, modifiers):
            return
            
        if self.current_mode == "PushPull" and self.push_pull_cmd:
            if not self.push_pull_cmd.selected_face:  # If no face is selected yet for PP
                # Try to pick a face
                selected_objects = self.view._display.GetSelectedObjects()
                if selected_objects:
                    # We have a selection, try to get the selected face
                    for obj in selected_objects:
                        try:
                            if hasattr(obj, "GetObject") and obj.GetObject().ShapeType() == 4:  # 4 is FACE
                                self.push_pull_cmd.select_face(obj.GetObject())
                                self.initial_drag_pos = (x, y)
                                return
                        except Exception as exc:
                            print(f"Error selecting face: {exc}")
                else:
                    # No selection, tell user to select a face
                    self.win.statusBar().showMessage("Select a face to push-pull")
            elif self.push_pull_cmd.selected_face:
                # If we have a face selected, store initial drag position
                self.initial_drag_pos = (x, y)
                return

        if self.current_mode == "Move" and self.selected_feature:
            # Start move operation
            self.initial_drag_pos = (x, y)
            self.win.statusBar().showMessage("Drag to move object")
            return

    def _on_mouse_move(self, world_pt):
        if (
            self.current_mode == "PushPull"
            and self.push_pull_cmd
            and self.push_pull_cmd.selected_face
            and self.initial_drag_pos
        ):
            # Get initial and current mouse positions in screen coordinates
            x0, y0 = self.initial_drag_pos
            from PySide6.QtGui import QCursor

            x1 = self.view.mapFromGlobal(QCursor.pos()).x()
            y1 = self.view.mapFromGlobal(QCursor.pos()).y()
            
            # Calculate the delta move in screen coordinates
            dx = x1 - x0
            
            # Convert to a reasonable scaling factor for the push-pull
            # Scale based on view width for consistent experience
            scale_factor = dx / self.view.width() * 100.0
            
            # Update the push-pull visualization
            self.push_pull_cmd.update_depth(scale_factor)
            self.view._display.Repaint()
            return
        if self.current_mode == "Move" and self.move_dragging and self.move_feature:
            # Snap or free move
            snapped, label = self.snap_manager.snap(world_pt, self.view)
            preview_pt = snapped if snapped is not None else world_pt
            orig = self.move_orig_ref
            delta = np.array(preview_pt) - np.array(orig)
            # Apply translation as preview (not committed)
            self.move_feature.apply_translation(delta)
            self.rebuild_scene()
            # Optionally show a marker or label
            if snapped is not None:
                self.show_snap_marker(snapped, label)
            else:
                self.hide_snap_marker()
        else:
            snapped, label = self.snap_manager.snap(world_pt, self.view)
            if snapped is not None:
                self.show_snap_marker(snapped, label)
                self.current_snap_point = snapped
            else:
                self.hide_snap_marker()
                self.current_snap_point = world_pt

    def _on_mouse_release(self, x, y, buttons, modifiers):
        if self.current_mode == "PushPull" and self.push_pull_cmd and self.initial_drag_pos:
            # Finalize the push-pull operation
            depth = self.push_pull_cmd.current_depth
            if depth != 0:  # Only apply if some change was made
                self.push_pull_cmd.apply_depth(depth)
                rebuild_scene(self.view._display)
                self.win.statusBar().showMessage(f"Push-pull applied: depth = {depth:.2f}")
            self.initial_drag_pos = None
            return
            
        if self.current_mode == "Move" and self.selected_feature and self.initial_drag_pos:
            # Finalize the move operation
            self.initial_drag_pos = None
            rebuild_scene(self.view._display)
            self.win.statusBar().showMessage("Move complete")
            return
        # ...existing code for other modes...

    def add_snap_tolerance_slider(self):
        """Add a slider to control snap tolerance to the property panel"""
        from PySide6.QtWidgets import QSlider, QLabel, QHBoxLayout
        from PySide6.QtCore import Qt

        slider_layout = QHBoxLayout()
        label = QLabel(f"Snap Tolerance: {self.snap_manager.tol_px} px")
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(2)
        slider.setMaximum(32)
        slider.setValue(self.snap_manager.tol_px)
        slider.valueChanged.connect(
            lambda val: self._on_snap_tolerance_changed(val, label)
        )
        slider_layout.addWidget(label)
        slider_layout.addWidget(slider)
        self.property_layout.addLayout(slider_layout)

    def update_snap_points_display(self):
        """Refresh the viewer when snap settings change."""
        if hasattr(self.view, "_display"):
            try:
                self.view._display.Context.UpdateCurrentViewer()
            except Exception:
                pass

    def _on_snap_tolerance_changed(self, value, label):
        """Update snap tolerance when the slider is moved"""
        self.snap_manager.set_tolerance(value)
        label.setText(f"Snap Tolerance: {value} px")
        self.win.statusBar().showMessage(f"Snap tolerance set to {value} pixels", 2000)

    def _on_mouse_press(self, x, y, buttons, modifiers):
        # Try snap workflow first
        if self._on_mouse_press_snap(x, y, buttons, modifiers):
            return
        # ...existing code for PushPull and other modes...

    def toggle_grid_snap(self):
        is_on = self.snap_manager.toggle_strategy("grid_snap")
        if hasattr(self, "snap_actions") and "grid_snap" in self.snap_actions:
            self.snap_actions["grid_snap"].setChecked(is_on)
        status_message = f"Grid Snap {'ON' if is_on else 'OFF'}"
        self.win.statusBar().showMessage(status_message, 2000)

    def enter_push_pull_mode(self):
        if self.current_mode == "PushPull":
            return
        self.current_mode = "PushPull"
        self.push_pull_cmd = PushPullFeatureCmd()
        # Change cursor, update status bar, etc.
        self.win.statusBar().showMessage(
            "Push-Pull Mode: Click a face to select, then drag. Press P to exit."
        )
        # Set selection mode to faces if possible/needed
        self.view._display.SetSelectionMode(
            2
        )  # 2 for AIS_Shape::SelectionMode(SM_Face)
        # print("Entered Push-Pull mode. SelectionMode set to Face.")

    def exit_push_pull_mode(self):
        if self.current_mode != "PushPull":
            return

        if (
            self.push_pull_cmd
            and self.push_pull_cmd.preview_shape
            and self.view._display.Context.IsDisplayed(self.push_pull_cmd.preview_shape)
        ):
            self.view._display.Context.Remove(self.push_pull_cmd.preview_shape, True)

        self.current_mode = "Navigate"  # Or "Pick"
        self.push_pull_cmd = None
        self.initial_drag_pos = None
        self.win.statusBar().showMessage(
            "Exited Push-Pull mode. Back to Navigate.", 2000
        )
        self.view._display.SetSelectionMode(
            1
        )  # 1 for AIS_Shape::SelectionMode(SM_Object) or default
        # print("Exited Push-Pull mode. SelectionMode set to Object.")
        rebuild_scene(self.view._display)  # Ensure scene is correct

    def toggle_push_pull_mode(self):
        if self.current_mode == "PushPull":
            if (
                self.push_pull_cmd
            ):  # If a command is active, cancel it before exiting mode
                self.push_pull_cmd.cancel(self)
            else:
                self.exit_push_pull_mode()
        else:
            self.enter_push_pull_mode()

    def enter_move_mode(self):
        """Enter Move mode: drag selected object with free move + snap."""
        self.current_mode = "Move"
        self.move_dragging = False
        self.move_start_pos = None
        self.move_orig_ref = None
        self.move_feature = self.selected_feature

    def show_snap_marker(self, point, label=""):
        """Show a visual marker at the snap point."""
        try:
            from OCC.Core.AIS import AIS_Point
            from OCC.Core.gp import gp_Pnt
            from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_RED
            
            # Remove any existing snap marker
            self.hide_snap_marker()
            
            # Create a simple point marker at the snap point
            gp_point = gp_Pnt(point[0], point[1], point[2])
            marker = AIS_Point(gp_point)
            
            # Try to style the marker with basic settings
            try:
                # Set color to red for visibility
                marker.SetColor(Quantity_Color(Quantity_NOC_RED))
            except:
                pass  # Color setting may fail in some versions
            
            # Display the marker
            self.view._display.Context.Display(marker, True)
            self.current_snap_marker = marker
            
            # Update status bar with snap information
            if label:
                self.win.statusBar().showMessage(f"Snap: {label}", 2000)
        except Exception as e:
            # If marker creation fails, just show status message
            if label:
                self.win.statusBar().showMessage(f"Snap: {label}", 2000)
    
    def hide_snap_marker(self):
        """Hide the current snap marker."""
        try:
            if hasattr(self, 'current_snap_marker') and self.current_snap_marker:
                self.view._display.Context.Erase(self.current_snap_marker, True)
                self.current_snap_marker = None
        except Exception as e:
            # If hiding fails, just clear the reference
            self.current_snap_marker = None

    def _keyPressEvent(self, event):
        # Handle global key presses or mode-specific ones
        vk = event.key()
        vmap = {
            self.Qt.Key_H: self.view._display.View_Iso,
            self.Qt.Key_T: self.view._display.View_Top,
            self.Qt.Key_B: self.view._display.View_Bottom,
            self.Qt.Key_F: self.view._display.View_Front,
            self.Qt.Key_R: self.view._display.View_Rear,
            self.Qt.Key_L: self.view._display.View_Left,
            self.Qt.Key_Y: self.view._display.View_Right,
        }
        if vk in vmap:
            vmap[vk]()
            self.view._display.FitAll()
            event.accept()
            return
        if self.current_mode == "PushPull" and self.push_pull_cmd:
            if vk == self.Qt.Key_Return or vk == self.Qt.Key_Enter:
                self.push_pull_cmd.commit(self)
                return  # Event handled
            elif vk == self.Qt.Key_Escape:
                self.push_pull_cmd.cancel(self)
                return  # Event handled
        if self.current_mode == "Move":
            if vk == self.Qt.Key_Escape:
                # Cancel move mode on Escape
                self.current_mode = "Navigate"
                self.move_dragging = False
                self.move_feature = None
                self.win.statusBar().showMessage("Move mode canceled.", 2000)
                return  # Event handled
        # Allow event to propagate for other shortcuts (R, G, P etc.)
        # For now, simply not consuming it should allow other shortcuts to work.
        pass

    def run(self):
        """Run the main window application."""
        if not self.app or not self.win:
            print("Error: Application not properly initialized")
            return

        # Install event filter to catch key events in main window
        from PySide6.QtCore import QObject, QEvent

        class KeyPressFilter(QObject):
            def __init__(self, main_window):
                super().__init__()
                self.main_window = main_window

            def eventFilter(self, obj, event):
                if event.type() == QEvent.KeyPress:
                    self.main_window._keyPressEvent(event)
                return super().eventFilter(obj, event)

        # Install the filter
        self.event_filter = KeyPressFilter(self)
        self.win.installEventFilter(self.event_filter)
        # Show the window and run the application
        self.win.show()
        self.win.setGeometry(100, 100, 1024, 768)  # Set a reasonable default size
        self._build_demo()  # Build demo scene AFTER window is shown

        try:
            # Add snap tolerance slider to property panel after window is shown
            self.add_snap_tolerance_slider()
        except Exception as e:
            print(f"Could not add snap tolerance slider: {e}")

        # Execute the application
        return self.app.exec()

    # --- END SNAP WORKFLOW PATCH ---


def main() -> None:
    MainWindow().run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()


def compute_offset(mouse_start, mouse_current, face_normal, view):
    """Project drag vector onto face normal to get signed offset for Push-Pull."""
    pt_start = view._display.ConvertToGrid(*mouse_start)
    pt_curr = view._display.ConvertToGrid(*mouse_current)
    v = np.array(
        [
            pt_curr.X() - pt_start.X(),
            pt_curr.Y() - pt_start.Y(),
            pt_curr.Z() - pt_start.Z(),
        ]
    )
    n = np.array([face_normal.X(), face_normal.Y(), face_normal.Z()])
    offset = np.dot(v, n)
    return offset
