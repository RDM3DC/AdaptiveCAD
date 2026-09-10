"""Real Qt menu, preview, cancellation, independent undo and stale-state tests."""
import json
import os
from pathlib import Path

import pytest

from adaptivecad.geom.meshfree_tools import Curve
from adaptivecad.geom.tool_document import ToolDocument
from adaptivecad.metric_project import MetricCurve, MetricProject

_APP = None


@pytest.fixture(scope="module")
def application():
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    _APP = widgets.QApplication.instance() or widgets.QApplication([])
    return _APP


@pytest.fixture
def ui(application, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QGraphicsScene, QMessageBox, QWidget
    from shiboken6 import isValid
    existing = tuple(application.topLevelWidgets())
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    yield application
    roots = [w for w in application.topLevelWidgets()
             if w.parentWidget() is None and all(w is not old for old in existing)]
    for root in roots:
        dialog = getattr(root, "_curve_transfer_dialog", None)
        if dialog is not None:
            dialog.reject()
        for widget in [root] + root.findChildren(QWidget):
            if hasattr(widget, "guard_unsaved"):
                widget.guard_unsaved = False
                widget._saved_document = widget.session.document
            if hasattr(widget, "drafts_dirty") and hasattr(widget, "history"):
                widget.history.mark_saved()
                widget.patch_editor.document().setModified(False)
                widget.curve_editor.document().setModified(False)
        for scene in root.findChildren(QGraphicsScene):
            scene.blockSignals(True)
        root.close()
        root.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    assert all(not isValid(root) for root in roots)


def window_and_dialog(app, curve=None):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    if curve is None:
        curve = Curve("bezier", ((-.4, 0, 0), (0, .4, 0), (.4, 0, 0)))
    window = create_integrated_workbench(ToolDocument(entities=(("profile", curve),)))
    window.show()
    app.processEvents()
    window._curve_transfer_action.trigger()
    app.processEvents()
    dialog = window._curve_transfer_dialog
    assert dialog is not None and dialog.isVisible()
    return window, dialog


def test_real_menu_preview_confirm_copy_undo_and_receipt(ui, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    window, dialog = window_and_dialog(ui)
    dock = window._metric_workbench
    source_before, target_before = window.session.document, dock.history.current
    assert not dialog.copy_button.isEnabled()
    QTest.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    assert dialog.prepared is not None
    assert dock.history.current == target_before
    assert not dialog.copy_button.isEnabled()
    dialog.confirm.setChecked(True)
    assert dialog.copy_button.isEnabled()
    screenshot = os.environ.get("CURVE_TRANSFER_SCREENSHOT")
    if screenshot:
        path = Path(screenshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        ui.processEvents()
        assert dialog.grab().save(str(path))
    QTest.mouseClick(dialog.copy_button, Qt.MouseButton.LeftButton)
    ui.processEvents()
    assert window._curve_transfer_dialog is None
    assert window.session.document == source_before
    assert not window.has_unsaved_changes
    assert dock.history.dirty and dock.history.can_undo
    assert dock.selected_curve().name == "profile"
    copied = dock.history.current
    dock.undo()
    assert dock.history.current == target_before
    dock.redo()
    assert dock.history.current == copied
    copied.save(tmp_path / "copied.acmetric.json")
    assert MetricProject.load(tmp_path / "copied.acmetric.json") == copied
    records = []
    monkeypatch.setattr(dock, "_export_text", lambda title, text, suffix: records.append(json.loads(text)))
    window._curve_transfer_receipt_action.trigger()
    assert records[0]["target_curve"]["name"] == "profile"
    assert window.session.document == source_before


def test_cancel_and_input_changes_do_not_mutate(ui):
    window, dialog = window_and_dialog(ui)
    before = window._metric_workbench.history.current
    dialog.prepare()
    dialog.confirm.setChecked(True)
    dialog.origin_edit.setText("[0.1, 0, 0]")
    assert dialog.prepared is None and not dialog.copy_button.isEnabled()
    dialog.prepare()
    dialog.reject()
    ui.processEvents()
    assert window._metric_workbench.history.current == before
    assert not window._metric_workbench.history.can_undo


@pytest.mark.parametrize("reason", ["plane", "disk", "arc", "json"])
def test_invalid_previews_do_not_enable_copy(ui, reason):
    curve = {"plane": Curve.line((0, 0, 1), (.1, 0, 1)),
             "disk": Curve.line((0, 0, 0), (2, 0, 0)), "arc": Curve.arc()}.get(reason)
    window, dialog = window_and_dialog(ui, curve)
    if reason == "json":
        dialog.origin_edit.setText('[0,NaN,0]')
    dialog.prepare()
    dialog.confirm.setChecked(True)
    assert dialog.prepared is None and not dialog.copy_button.isEnabled()
    assert "No changes made" in dialog.summary.toPlainText()
    assert not window._metric_workbench.history.can_undo
    dialog.reject()


@pytest.mark.parametrize("side", ["source", "target", "draft"])
def test_preview_cannot_commit_after_changed_state(ui, side):
    window, dialog = window_and_dialog(ui)
    dialog.prepare()
    dialog.confirm.setChecked(True)
    dock = window._metric_workbench
    if side == "source":
        window.session.execute({"op": "copy", "source": "profile", "name": "other"})
    elif side == "target":
        dock.history.commit(dock.history.current.put_curve(MetricCurve("other", ((0, 0),))))
    else:
        dock.patch_editor.document().setModified(True)
    before = dock.history.current
    dialog.copy_curve()
    assert dock.history.current == before
    assert dialog.receipt is None
    assert not dialog.copy_button.isEnabled()
    dialog.reject()


def test_xz_plane_preview_and_duplicate_name_guard(ui):
    curve = Curve("bezier", ((-.4, 0, 0), (0, 0, .4), (.4, 0, 0)))
    window, dialog = window_and_dialog(ui, curve)
    dialog.plane.setCurrentText("XZ")
    dialog.prepare()
    assert dialog.prepared.curve.controls == ((-.4, 0), (0, .4), (.4, 0))
    dialog.confirm.setChecked(True)
    dialog.copy_curve()
    ui.processEvents()
    window._curve_transfer_action.trigger()
    dialog = window._curve_transfer_dialog
    assert dialog.name_edit.text() == "profile 2"
    dialog.name_edit.setText("profile")
    dialog.prepare()
    assert dialog.prepared is None
    assert len(window._metric_workbench.history.current.curves) == 1
    dialog.reject()


def test_existing_host_child_installs_once_without_replacing_scene(ui):
    from PySide6.QtWidgets import QLabel, QMainWindow

    from adaptivecad.gui.curve_transfer import install_curve_transfer
    from adaptivecad.gui.integrated_workbench import install_integrated_tools
    host = QMainWindow()
    original = QLabel("existing solid view")
    host.setCentralWidget(original)
    dock = install_integrated_tools(host)
    assert dock is install_integrated_tools(host)
    host._meshfree_action.trigger()
    ui.processEvents()
    child = host._meshfree_window
    assert child._curve_transfer_target is dock
    assert child._curve_transfer_action is install_curve_transfer(child, dock)
    assert host.centralWidget() is original
    assert len(child.findChildren(type(child._curve_transfer_action), "SendSelectedCurveToMetric")) == 1
