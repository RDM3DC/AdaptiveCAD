"""Dockable intrinsic-metric workbench for both existing AdaptiveCAD applications.

Only this GUI module requires PySide6. It never changes DOCUMENT, an SDF scene,
world-space coordinates, or a machine toolpath. install_metric_workbench() is
idempotent and uses a separate project and undo history.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from adaptivecad.geom.directional_metric import (
    NormalMetricPatch,
    _finite,
    balanced_directional_patch,
)
from adaptivecad.geom.metric_geodesic import trace_geodesic
from adaptivecad.geom.metric_tools import (
    METRES_PER_UNIT,
    analyze_bezier,
    angle_between,
    disk_area,
    point,
)
from adaptivecad.metric_project import MetricCurve, MetricHistory, MetricProject, atomic_write


class ChartView(QGraphicsView):
    pointPicked = Signal(float, float)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.mapToScene(event.position().toPoint())
            self.pointPicked.emit(p.x(), -p.y())
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        scale = self.transform().m11()
        if 1e-10 < scale * factor < 1e12:
            self.scale(factor, factor)
        event.accept()


class MetricWorkbench(QDockWidget):
    def __init__(self, parent):
        super().__init__("Adaptive-pi metric workbench", parent)
        self.setObjectName("AdaptiveCADMetricWorkbench")
        self.history = MetricHistory()
        self.project_path = None
        self.last_report = None
        self.trace = None
        self._active_curve = ""
        self._refreshing = False
        self._last_geometry_scale = None
        self._host = parent
        parent.installEventFilter(self)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.setWidget(root)
        self.setMinimumWidth(490)
        bar = QToolBar()
        self.actions = {}
        for name, text, callback in (
            ("new", "New", self.new_project), ("open", "Open", self.open_project),
            ("save", "Save", self.save_project), ("save_as", "Save as", lambda: self.save_project(True)),
            ("undo", "Undo model", self.undo), ("redo", "Redo model", self.redo),
        ):
            action = QAction(text, self)
            action.setObjectName("metric_" + name)
            action.triggered.connect(lambda checked=False, f=callback: self._run(f))
            bar.addAction(action)
            self.actions[name] = action
        layout.addWidget(bar)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        note = QLabel("Intrinsic chart XY, not world XYZ or a 3D embedding. "
                      "Preview samples are not authoritative geometry or machine output.")
        note.setWordWrap(True)
        layout.addWidget(note)
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)
        self._build_patch_tab()
        self._build_curve_tab()
        self._build_measure_tab()
        self._build_trace_tab()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.tabs.addTab(self.output, "Results")
        preview = QWidget()
        vbox = QVBoxLayout(preview)
        tools = QHBoxLayout()
        self.heatmap = QCheckBox("Sampled curvature map")
        self.heatmap.toggled.connect(lambda: self._run(self.redraw))
        tools.addWidget(self.heatmap)
        self._button(tools, "Fit chart", self.fit_chart)
        self._button(tools, "Export report", self.export_report)
        vbox.addLayout(tools)
        self.scene = QGraphicsScene(self)
        self.view = ChartView(self.scene)
        self.view.setMinimumHeight(200)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.pointPicked.connect(self.pick_point)
        vbox.addWidget(self.view)
        self.map_label = QLabel("Click the chart to set the measurement point.")
        self.map_label.setWordWrap(True)
        vbox.addWidget(self.map_label)
        splitter.addWidget(preview)
        splitter.setSizes([380, 260])
        self._refresh()

    def _button(self, layout, text, callback):
        button = QPushButton(text)
        button.clicked.connect(lambda checked=False: self._run(callback))
        layout.addWidget(button)
        return button

    def _run(self, callback):
        try:
            return callback()
        except (ValueError, ArithmeticError, OSError, TypeError, RecursionError) as exc:
            QMessageBox.warning(self, "Metric workbench", str(exc))
            return False

    def _tab(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, name)
        return layout

    def _build_patch_tab(self):
        layout = self._tab("Patch")
        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.addItems(["Flat", "Balanced directional", "Positive center curvature",
                              "Negative center curvature"])
        row.addWidget(self.preset)
        self._button(row, "Use preset", self.use_preset)
        self.units = QComboBox()
        self.units.addItems(list(METRES_PER_UNIT))
        row.addWidget(self.units)
        self._button(row, "Convert units", self.convert_units)
        layout.addLayout(row)
        self.patch_editor = QPlainTextEdit()
        self.patch_editor.setObjectName("metric_patch_editor")
        self.patch_editor.setMinimumHeight(145)
        layout.addWidget(self.patch_editor)
        row = QHBoxLayout()
        self._button(row, "Apply editors", self.apply_editors)
        self._button(row, "Revert editors", self.revert_editors)
        self._button(row, "Import patch", self.import_patch)
        self._button(row, "Export patch", self.export_patch)
        layout.addLayout(row)

    def _build_curve_tab(self):
        layout = self._tab("Curves")
        self.curve_select = QComboBox()
        self.curve_select.currentTextChanged.connect(self._select_curve)
        layout.addWidget(self.curve_select)
        self.curve_name = QLineEdit()
        self.curve_name.textEdited.connect(lambda: self._mark_curve_dirty())
        layout.addWidget(self.curve_name)
        self.curve_editor = QPlainTextEdit()
        self.curve_editor.setPlaceholderText("Native Bezier controls in chart units: [[x,y], ...]")
        self.curve_editor.setMaximumHeight(140)
        layout.addWidget(self.curve_editor)
        row = QHBoxLayout()
        self._button(row, "New curve", self.new_curve)
        self._button(row, "Apply editors", self.apply_editors)
        self._button(row, "Reverse", lambda: self.edit_curve("reverse"))
        self._button(row, "Duplicate", lambda: self.edit_curve("duplicate"))
        self._button(row, "Delete", lambda: self.edit_curve("delete"))
        layout.addLayout(row)
        row = QHBoxLayout()
        self.split_t = QLineEdit("0.5")
        self.split_t.setMaximumWidth(70)
        row.addWidget(QLabel("Split t:")); row.addWidget(self.split_t)
        self._button(row, "Split", lambda: self.edit_curve("split"))
        self.transform_values = QLineEdit("[0, 0, 0, 1]")
        self.transform_values.setToolTip("[dx, dy, angle in degrees, uniform scale]; active chart edit")
        row.addWidget(self.transform_values)
        self._button(row, "Transform", lambda: self.edit_curve("transform"))
        layout.addLayout(row)
        row = QHBoxLayout()
        self.curve_t = QLineEdit("0.5")
        self.curve_t.setMaximumWidth(70)
        row.addWidget(QLabel("Inspect t:")); row.addWidget(self.curve_t)
        self._button(row, "Measure selected curve", self.measure_curve)
        layout.addLayout(row)

    def _build_measure_tab(self):
        layout = self._tab("Measure")
        form = QFormLayout()
        self.xy = QLineEdit("[0, 0]")
        self.vector_u = QLineEdit("[1, 0]")
        self.vector_v = QLineEdit("[0, 1]")
        self.radius = QLineEdit("0.5")
        self.sector = QLineEdit("[0, 90]")
        for label, widget in (("Chart point [x,y]",self.xy), ("Vector u",self.vector_u),
                              ("Vector v",self.vector_v), ("Circle radius",self.radius),
                              ("Sector [start,end] degrees",self.sector)):
            form.addRow(label, widget)
        layout.addLayout(form)
        self._button(layout, "Measure point, angle, circle and sector", self.measure)

    def _build_trace_tab(self):
        layout = self._tab("Trace")
        form = QFormLayout()
        self.start = QLineEdit("[-0.5, 0.2]")
        self.direction = QLineEdit("0")
        self.length = QLineEdit("0.8")
        self.transport = QLineEdit("[1, 0]")
        for label, widget in (("Start [x,y]",self.start), ("Launch direction, degrees",self.direction),
                              ("Requested intrinsic length",self.length),
                              ("Parallel-transport vector",self.transport)):
            form.addRow(label, widget)
        layout.addLayout(form)
        note = QLabel("Initial-value geodesic, not a certified shortest route. "
                      "Stops at the patch boundary and reports the actual traced length.")
        note.setWordWrap(True); layout.addWidget(note)
        self._button(layout, "Trace geodesic and transport vector", self.run_trace)

    def _mark_curve_dirty(self):
        self.curve_editor.document().setModified(True)

    def drafts_dirty(self):
        return self.patch_editor.document().isModified() or self.curve_editor.document().isModified()

    def candidate(self):
        project = self.history.current
        patch = project.patch
        curves = list(project.curves)
        if self.patch_editor.document().isModified():
            patch = NormalMetricPatch.from_json(self.patch_editor.toPlainText())
        if self.curve_editor.document().isModified():
            name = self.curve_name.text()
            curve = MetricCurve(name, json.loads(self.curve_editor.toPlainText()))
            if name != self._active_curve and name in {c.name for c in curves}:
                raise ValueError("A different curve already has that name")
            curves = [c for c in curves if c.name != self._active_curve]
            curves.append(curve)
        # Validate the complete candidate once, so shrinking a patch and fixing
        # its curve together is a single transaction, not a partial mutation.
        return MetricProject(patch, tuple(curves), project.name)

    def apply_editors(self):
        project = self.candidate()
        if self.curve_editor.document().isModified():
            self._active_curve = self.curve_name.text()
        self.history.commit(project)
        self._refresh()

    def _require_applied(self):
        if self.drafts_dirty():
            raise ValueError("Apply or revert editor changes before using this tool")

    def revert_editors(self):
        if self.drafts_dirty() and QMessageBox.question(self,"Discard editor changes?",
                "Discard unapplied editor changes?", QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._refresh()

    def _refresh(self):
        self._refreshing = True
        try:
            project = self.history.current
            self.patch_editor.setPlainText(project.patch.to_json())
            self.patch_editor.document().setModified(False)
            self.units.setCurrentText(project.patch.unit)
            names = [c.name for c in project.curves]
            if self._active_curve not in names:
                self._active_curve = names[0] if names else ""
            self.curve_select.clear(); self.curve_select.addItems(names)
            self.curve_select.setCurrentText(self._active_curve)
            self._load_curve_editor()
            self.last_report = self.trace = None
            self.output.clear()
            self.actions["undo"].setEnabled(self.history.can_undo)
            self.actions["redo"].setEnabled(self.history.can_redo)
            label = Path(self.project_path).name if self.project_path else project.name
            self.status.setText(f"{label}{' *' if self.history.dirty else ''} | {project.patch.unit} | "
                                f"{len(project.curves)} native curves | independent metric project")
            geometry_scale = (project.patch.unit, project.patch.radius, project.patch.length_scale)
            if geometry_scale != self._last_geometry_scale:
                r = project.patch.radius
                self.xy.setText("[0,0]"); self.radius.setText(str(.5*r))
                self.start.setText(json.dumps([-.5*r,.2*r])); self.length.setText(str(.8*r))
                self._last_geometry_scale = geometry_scale
            self.redraw()
        finally:
            self._refreshing = False

    def _load_curve_editor(self):
        curve = next((c for c in self.history.current.curves if c.name == self._active_curve),None)
        self.curve_name.setText(curve.name if curve else "")
        self.curve_editor.setPlainText(json.dumps(curve.controls, indent=2) if curve else "[]")
        self.curve_editor.document().setModified(False)

    def _select_curve(self, name):
        if self._refreshing:
            return
        if self.drafts_dirty():
            self.curve_select.blockSignals(True)
            self.curve_select.setCurrentText(self._active_curve)
            self.curve_select.blockSignals(False)
            QMessageBox.warning(self,"Unapplied edits","Apply or revert editor changes before selecting another curve.")
            return
        self._active_curve = name
        self._load_curve_editor()

    def unique_name(self, base, project=None):
        names = {c.name for c in (project or self.history.current).curves}
        base = base[:110]
        value, i = base, 2
        while value in names:
            value = f"{base} {i}"; i += 1
        return value

    def new_curve(self):
        self._require_applied()
        self._active_curve = ""
        self.curve_name.setText(self.unique_name("Curve"))
        r = self.history.current.patch.radius
        self.curve_editor.setPlainText(json.dumps([[-.4*r,0],[0,.4*r],[.4*r,0]],indent=2))
        self.curve_editor.document().setModified(True)
        self.tabs.setCurrentIndex(1)

    def selected_curve(self):
        curve = next((c for c in self.history.current.curves if c.name == self._active_curve),None)
        if curve is None:
            raise ValueError("Create and apply, or select, a native curve first")
        return curve

    def edit_curve(self, operation):
        self._require_applied()
        curve = self.selected_curve(); project = self.history.current
        if operation == "reverse":
            project = project.put_curve(curve.reversed())
        elif operation == "duplicate":
            curve = replace(curve,name=self.unique_name(curve.name + " copy"))
            project = project.put_curve(curve)
        elif operation == "delete":
            project = project.remove_curve(curve.name)
        elif operation == "split":
            left,right = curve.split(float(self.split_t.text()))
            project = project.remove_curve(curve.name)
            left = replace(left,name=self.unique_name(left.name,project))
            project = project.put_curve(left)
            right = replace(right,name=self.unique_name(right.name,project))
            project = project.put_curve(right); curve = left
        elif operation == "transform":
            values = json.loads(self.transform_values.text())
            if not isinstance(values,list) or len(values) != 4:
                raise ValueError("Transform is [dx,dy,angle_degrees,scale]")
            curve = curve.transformed(dx=values[0],dy=values[1],angle=math.radians(_finite(values[2], "angle")),factor=values[3])
            project = project.put_curve(curve)
        self.history.commit(project); self._active_curve = curve.name; self._refresh()

    def use_preset(self):
        self._require_applied()
        p = self.history.current.patch; index = self.preset.currentIndex()
        terms = (() if index == 0 else balanced_directional_patch().terms if index == 1
                 else ((0,0,-.1 if index == 2 else .1),))
        self.history.commit(self.history.current.with_patch(NormalMetricPatch(terms,p.length_scale,p.radius,p.unit)))
        self._refresh()

    def convert_units(self):
        self._require_applied()
        self.history.commit(self.history.current.convert_units(self.units.currentText()))
        self._refresh()

    def undo(self):
        self._require_applied(); self.history.undo(); self._refresh()

    def redo(self):
        self._require_applied(); self.history.redo(); self._refresh()

    def _set_report(self, kind, result, inputs=None):
        p = self.history.current.patch
        text = self.history.current.to_json()
        self.last_report = {"schema":"adaptivecad.metric_report", "version":1,
                            "kind":kind,"unit":p.unit,"project_sha256":hashlib.sha256(text.encode()).hexdigest(),
                            "project":json.loads(text),"inputs":inputs or {},"result":result,
                            "limitations":"Intrinsic chart calculation. Numerical errors are estimates, not certified bounds. Not machine output."}
        self.output.setPlainText(json.dumps(self.last_report,allow_nan=False,indent=2))
        self.tabs.setCurrentWidget(self.output)

    def measure(self):
        self._require_applied(); p = self.history.current.patch
        xy = point(p,json.loads(self.xy.text())); r = float(self.radius.text())
        angles = json.loads(self.sector.text())
        if not isinstance(angles,list) or len(angles)!=2 or not 0 <= angles[1]-angles[0] <= 360:
            raise ValueError("Sector requires ordered angles spanning at most 360 degrees")
        angles = [_finite(a, "sector angle") for a in angles]
        u, v = json.loads(self.vector_u.text()), json.loads(self.vector_v.text())
        result = {"point":xy,"metric":p.metric(*xy),"gaussian_curvature":p.gaussian_curvature(*xy),
                  "intrinsic_angle_degrees":math.degrees(angle_between(p,xy,u,v)),
                  "radius":r,"circle_pi":asdict(p.circle_pi(r)),"disk_area":asdict(disk_area(p,r,abs_tol=max(1e-16,1e-8*p.length_scale**2))),
                  "circumference":asdict(p.sector_length(r)),
                  "sector_length":asdict(p.sector_length(r,*map(math.radians,angles))),
                  "positivity_lower_bound":p.positivity_lower_bound()}
        self._set_report("measurements",result,{"point":xy,"u":u,"v":v,"radius":r,"sector_degrees":angles})

    def measure_curve(self):
        self._require_applied(); curve=self.selected_curve(); p=self.history.current.patch
        self._set_report("native_bezier",{"name":curve.name,"length":asdict(p.bezier_length(curve.native())),
                                           "local":asdict(analyze_bezier(p,curve.native(),float(self.curve_t.text())))},
                         {"curve_name":curve.name,"t":float(self.curve_t.text())})

    def run_trace(self):
        self._require_applied(); angle=math.radians(float(self.direction.text()))
        t = trace_geodesic(self.history.current.patch,json.loads(self.start.text()),
                           (math.cos(angle),math.sin(angle)),float(self.length.text()),
                           transport=json.loads(self.transport.text()))
        self.trace = t
        self.redraw()
        self._set_report("geodesic_initial_value",asdict(t),
                         {"start":json.loads(self.start.text()),"direction_degrees":float(self.direction.text()),
                          "length":float(self.length.text()),"transport":json.loads(self.transport.text()),
                          "tolerance":1e-8,"max_steps":4096})

    def pick_point(self,x,y):
        if math.hypot(x,y) <= self.history.current.patch.radius:
            self.xy.setText(json.dumps([x,y]))
            p=self.history.current.patch
            self.map_label.setText(f"({x:.6g}, {y:.6g}) {p.unit}; K={p.gaussian_curvature(x,y):.6g} {p.unit}^-2")

    def fit_chart(self):
        r=self.history.current.patch.radius
        self.view.fitInView(-1.08*r,-1.08*r,2.16*r,2.16*r,Qt.AspectRatioMode.KeepAspectRatio)

    def redraw(self):
        self.scene.clear(); p=self.history.current.patch; r=p.radius
        pen=QPen(self.palette().text().color()); pen.setCosmetic(True)
        self.scene.addEllipse(-r,-r,2*r,2*r,pen)
        if self.heatmap.isChecked():
            values=[]; n=25; step=2*r/n
            for i in range(n):
                for j in range(n):
                    x,y=-r+(i+.5)*step,-r+(j+.5)*step
                    if math.hypot(abs(x)+step/2,abs(y)+step/2) < r:
                        values.append((x,y,p.gaussian_curvature(x,y)))
            maximum=max((abs(k) for _,_,k in values),default=1) or 1
            for x,y,k in values:
                color=QColor.fromHsvF(.62 if k<0 else .03,abs(k)/maximum*.75,.85,.45)
                self.scene.addRect(x-step/2,-y-step/2,step,step,QPen(Qt.PenStyle.NoPen),color)
            lo=min((k for _,_,k in values),default=0); hi=max((k for _,_,k in values),default=0)
            self.map_label.setText(f"Sampled K range: {lo:.6g} to {hi:.6g} {p.unit}^-2 (not extrema certification).")
        else:
            self.map_label.setText("Click chart to set the measurement point; mouse wheel zooms.")
        curve_pen=QPen(self.palette().highlight().color(),2); curve_pen.setCosmetic(True)
        for curve in self.history.current.curves:
            native=curve.native(); pts=[native.evaluate(i/100) for i in range(101)]
            path=QPainterPath(); path.moveTo(pts[0].x,-pts[0].y)
            for v in pts[1:]: path.lineTo(v.x,-v.y)
            self.scene.addPath(path,curve_pen)
        if self.trace:
            trace_pen=QPen(self.palette().link().color(),2); trace_pen.setCosmetic(True)
            trace_pen.setStyle(Qt.PenStyle.DashLine)
            path=QPainterPath(); path.moveTo(self.trace.points[0][0],-self.trace.points[0][1])
            for x,y in self.trace.points[1:]: path.lineTo(x,-y)
            self.scene.addPath(path,trace_pen)
        self.fit_chart()

    def _maybe_save(self):
        if not self.history.dirty and not self.drafts_dirty(): return True
        choice=QMessageBox.question(self,"Unsaved metric project","Save metric-project changes?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if choice==QMessageBox.StandardButton.Cancel: return False
        if choice==QMessageBox.StandardButton.Discard: return True
        return self._run(self.save_project) is True

    def new_project(self):
        if not self._maybe_save(): return
        self.history.reset(MetricProject()); self.project_path=None; self._active_curve=""; self._refresh()

    def open_project(self):
        filename,_=QFileDialog.getOpenFileName(self,"Open metric project","","Metric project (*.acmetric.json);;JSON (*.json)")
        if not filename: return
        project=MetricProject.load(filename)  # Validate BEFORE discarding existing state.
        if not self._maybe_save(): return
        self.history.reset(project); self.project_path=filename; self._active_curve=""; self._refresh()

    def save_project(self,save_as=False):
        project=self.candidate()  # Invalid edits cannot erase the previous file.
        filename=self.project_path
        if save_as or not filename:
            filename,_=QFileDialog.getSaveFileName(self,"Save metric project",filename or "Untitled.acmetric.json",
                                                  "Metric project (*.acmetric.json)")
            if not filename: return False
            if not filename.endswith(".acmetric.json"): filename += ".acmetric.json"
            # QFileDialog's check may precede appending the suffix.
            if Path(filename).exists() and filename != self.project_path:
                if QMessageBox.question(self,"Replace metric project?",f"Replace {filename}?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return False
        project.save(filename,overwrite=True)
        if self.curve_editor.document().isModified(): self._active_curve=self.curve_name.text()
        self.history.commit(project); self.history.mark_saved(); self.project_path=filename; self._refresh()
        return True

    def import_patch(self):
        self._require_applied()
        filename,_=QFileDialog.getOpenFileName(self,"Import metric patch","","JSON (*.json)")
        if not filename: return
        with Path(filename).open(encoding="utf-8") as f: text=f.read(100001)
        p=NormalMetricPatch.from_json(text)
        self.history.commit(self.history.current.with_patch(p)); self._refresh()

    def _export_text(self,title,text,suffix):
        filename,_=QFileDialog.getSaveFileName(self,title,"metric"+suffix,"JSON (*.json)")
        if not filename: return
        if not filename.endswith(".json"): filename += ".json"
        if Path(filename).exists():
            if QMessageBox.question(self,"Replace file?",f"Replace {filename}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        atomic_write(filename,text,overwrite=True)

    def export_patch(self):
        self._require_applied(); self._export_text("Export metric patch",self.history.current.patch.to_json(),".patch.json")

    def export_report(self):
        self._require_applied()
        if self.last_report is None: raise ValueError("Run a measurement or trace first")
        self._export_text("Export metric report",json.dumps(self.last_report,allow_nan=False,indent=2),".report.json")

    def eventFilter(self,watched,event):
        if watched is self._host and event.type()==QEvent.Type.Close:
            if not self._maybe_save(): event.ignore(); return True
        return super().eventFilter(watched,event)


def install_metric_workbench(window):
    """Attach once to QMainWindow or the existing Playground controller."""
    host=getattr(window,"win",window)
    existing=getattr(host,"_metric_workbench",None)
    if existing is not None: return existing
    dock=MetricWorkbench(host)
    host.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,dock)
    dock.hide()
    menu=host.menuBar().addMenu("Metric tools")
    menu.setObjectName("AdaptiveCADMetricToolsMenu")
    action=dock.toggleViewAction(); action.setText("Open metric workbench")
    menu.addAction(action)
    for label,index in (("Patch editor",0),("Native curve tools",1),("Measurements",2),("Geodesic and transport",3)):
        action=QAction(label,host)
        def show(checked=False,i=index):
            dock.show(); dock.raise_(); dock.tabs.setCurrentIndex(i)
        action.triggered.connect(show); menu.addAction(action)
    host._metric_workbench=dock
    return dock
