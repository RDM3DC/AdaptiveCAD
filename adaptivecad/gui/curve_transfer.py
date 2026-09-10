"""Opt-in, preview-before-copy bridge between the two existing workbenches."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from adaptivecad.geom.tool_document import strict_json
from adaptivecad.metric_curve_transfer import PlaneChartMapping, commit_transfer, preview_transfer

PLANES = {
    "XY": ((1, 0, 0), (0, 1, 0)),
    "XZ": ((1, 0, 0), (0, 0, 1)),
    "YZ": ((0, 1, 0), (0, 0, 1)),
}


class CurveTransferDialog(QDialog):
    """Retained, asynchronously opened dialog; no nested exec event loop."""
    def __init__(self, source_window, target_dock):
        super().__init__(source_window)
        self.source_window, self.target_dock = source_window, target_dock
        selected = source_window.listing.currentItem()
        if selected is None:
            raise ValueError("Select a model line or Bezier curve first")
        target_dock._require_applied()
        self.source_name = selected.text()
        self.source = source_window.session.document
        self.target = target_dock.history.current
        self.prepared = None
        self.receipt = None
        self.setWindowTitle("Send selected curve to metric tools")
        self.resize(710, 830)
        layout = QVBoxLayout(self)
        label = QLabel(f"Source: {self.source_name} [{self.source.unit}]\n"
                       f"Target: {self.target.name} [{self.target.patch.unit}], "
                       f"disk radius {self.target.patch.radius:.9g}\n"
                       "One-time copy. The original model is unchanged; undo belongs to the metric dock.")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        form = QFormLayout()
        self.name_edit = QLineEdit(target_dock.unique_name(self.source_name))
        self.plane = QComboBox()
        self.plane.addItems([*PLANES, "Custom"])
        self.origin_edit = QLineEdit("[0, 0, 0]")
        self.x_edit = QLineEdit("[1, 0, 0]")
        self.y_edit = QLineEdit("[0, 1, 0]")
        self.tolerance_edit = QLineEdit("1e-9")
        for title, widget in (("Copy name", self.name_edit), ("Declared plane", self.plane),
                              (f"Origin [{self.source.unit}]", self.origin_edit),
                              ("Chart X axis (direction)", self.x_edit),
                              ("Chart Y axis (direction)", self.y_edit),
                              (f"Allowed plane residual [{self.source.unit}]", self.tolerance_edit)):
            form.addRow(title, widget)
        layout.addLayout(form)
        note = QLabel("Axes must be perpendicular. Units convert automatically, but coordinates are not "
                      "automatically fitted to the disk. A curved metric is not a planar CAD-face embedding. "
                      "Arcs and surfaces are rejected, never sampled into replacement Beziers.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.preview_button = QPushButton("Preview mapping (no changes)")
        self.preview_button.clicked.connect(self.prepare)
        layout.addWidget(self.preview_button)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumHeight(170)
        layout.addWidget(self.view)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(145)
        layout.addWidget(self.summary)
        self.confirm = QCheckBox("I confirm this declared plane-to-chart mapping and any stated residual removal.")
        layout.addWidget(self.confirm)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.copy_button = self.buttons.addButton("Copy to metric project", QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_curve)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for editor in (self.name_edit, self.origin_edit, self.x_edit, self.y_edit, self.tolerance_edit):
            editor.textChanged.connect(self.invalidate)
        self.plane.currentTextChanged.connect(self.set_plane)
        self.confirm.toggled.connect(self.update_copy_state)
        self.set_plane(self.plane.currentText())

    def set_plane(self, name):
        custom = name == "Custom"
        self.x_edit.setReadOnly(not custom)
        self.y_edit.setReadOnly(not custom)
        if not custom:
            u, v = PLANES[name]
            self.x_edit.setText(json.dumps(u))
            self.y_edit.setText(json.dumps(v))
        self.invalidate()

    def invalidate(self, *_):
        self.prepared = None
        self.confirm.setChecked(False)
        self.copy_button.setEnabled(False)
        self.scene.clear()
        self.summary.setPlainText("Preview the current inputs, then confirm the mapping. No changes made.")

    def update_copy_state(self, *_):
        self.copy_button.setEnabled(self.prepared is not None and self.confirm.isChecked())

    def prepare(self):
        self.invalidate()
        try:
            self.target_dock._require_applied()
            if self.source_window.session.document != self.source or self.target_dock.history.current != self.target:
                raise ValueError("Document changed; close and reopen this dialog to refresh units and mapping")
            mapping = PlaneChartMapping(strict_json(self.origin_edit.text()),
                                        strict_json(self.x_edit.text()), strict_json(self.y_edit.text()),
                                        float(self.tolerance_edit.text()))
            self.prepared = preview_transfer(self.source, self.target, self.source_name,
                                            self.name_edit.text(), mapping)
            p = self.prepared
            self.summary.setPlainText(
                f"VALID: {len(p.curve.controls)} native controls; no curve fitting.\n"
                f"Unit factor: {p.factor:.17g} ({self.source.unit} -> {self.target.patch.unit})\n"
                f"Maximum control-plane residual removed: {p.max_plane_residual:.9g} {self.source.unit}\n"
                f"Maximum mapped control radius: {p.max_control_radius:.9g} {self.target.patch.unit}\n"
                "Whole curve is bounded by this control hull (floating-point check).\n"
                "Preview below is sampled for display only. Nothing has been copied yet.")
            radius = self.target.patch.radius
            pen = QPen(self.palette().text().color())
            pen.setCosmetic(True)
            self.scene.addEllipse(-200, -200, 400, 400, pen)
            native = p.curve.native()
            path = QPainterPath()
            for i in range(81):
                q = native.evaluate(i/80)
                xy = (q.x/radius*200, -q.y/radius*200)
                path.moveTo(*xy) if i == 0 else path.lineTo(*xy)
            line_pen = QPen(self.palette().highlight().color(), 2)
            line_pen.setCosmetic(True)
            self.scene.addPath(path, line_pen)
            self.view.fitInView(-220, -220, 440, 440, Qt.AspectRatioMode.KeepAspectRatio)
        except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
            self.prepared = None
            self.summary.setPlainText(f"No changes made: {exc}")
        self.update_copy_state()

    def copy_curve(self):
        if self.prepared is None or not self.confirm.isChecked():
            return
        try:
            dock = self.target_dock
            dock._require_applied()
            receipt = commit_transfer(self.prepared, self.source_window.session.document, dock.history)
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.invalidate()
            self.summary.setPlainText(f"No copy committed: {exc}. Close and reopen to refresh document state.")
            return
        self.receipt = receipt
        self.source_window._last_curve_transfer_receipt = json.dumps(receipt, indent=2, allow_nan=False)
        self.source_window._curve_transfer_receipt_action.setEnabled(True)
        dock._active_curve = self.prepared.curve.name
        dock._refresh()  # invalidates measurements/traces from the previous project
        dock.show()
        dock.raise_()
        dock.tabs.setCurrentIndex(1)
        self.source_window.report.setPlainText(
            f"Copied '{self.prepared.curve.name}' to metric tools. Source unchanged.\n"
            "Use the metric dock's Undo model to undo this copy. Save the metric project separately.\n"
            "Metric transfer > Export last transfer receipt records the mapping and hashes.")
        self.accept()


def install_curve_transfer(source_window, target_dock):
    """Attach once to a model window, targeting the explicitly supplied dock."""
    existing = getattr(source_window, "_curve_transfer_action", None)
    if existing is not None:
        if source_window._curve_transfer_target is not target_dock:
            raise ValueError("This model window already has a different metric transfer target")
        return existing
    source_window._curve_transfer_target = target_dock
    source_window._last_curve_transfer_receipt = None
    menu = source_window.menuBar().addMenu("Metric transfer")
    menu.setObjectName("AdaptiveCADCurveTransferMenu")
    action = QAction("Send selected curve to metric tools...", source_window)
    action.setObjectName("SendSelectedCurveToMetric")
    export = QAction("Export last transfer receipt...", source_window)
    export.setEnabled(False)
    source_window._curve_transfer_receipt_action = export

    def show():
        current = getattr(source_window, "_curve_transfer_dialog", None)
        if current is not None:
            current.raise_()
            return
        try:
            dialog = CurveTransferDialog(source_window, target_dock)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(source_window, "Curve transfer", str(exc))
            return
        source_window._curve_transfer_dialog = dialog
        def finished(_result):
            source_window._curve_transfer_dialog = None
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.open()

    def export_receipt():
        text = source_window._last_curve_transfer_receipt
        if text is not None:
            # Reuse the existing atomic, overwrite-confirming report export path.
            target_dock._run(lambda: target_dock._export_text("Export transfer receipt", text, ".transfer.json"))

    action.triggered.connect(show)
    export.triggered.connect(export_receipt)
    menu.addAction(action)
    menu.addAction(export)
    source_window._curve_transfer_action = action
    return action
