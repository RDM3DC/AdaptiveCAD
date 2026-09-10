"""Real Qt UI contracts on the integrated model, not a simulated mock window."""

import json
import os
from pathlib import Path

import pytest

from adaptivecad.geom.tool_document import ToolSession

_APP = None


@pytest.fixture(scope="module")
def application():
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    _APP = widgets.QApplication.instance() or widgets.QApplication([])
    return _APP


@pytest.fixture
def app(application, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QGraphicsScene, QMessageBox, QWidget
    from shiboken6 import isValid

    old = tuple(application.topLevelWidgets())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    yield application
    roots = [
        w
        for w in application.topLevelWidgets()
        if w.parentWidget() is None and all(w is not previous for previous in old)
    ]
    for root in roots:
        for widget in [root] + root.findChildren(QWidget):
            if hasattr(widget, "guard_unsaved"):
                widget.guard_unsaved = False
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


def create(app, classic=False):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench

    s = ToolSession()
    s.execute_many(
        [
            {"op": "line", "name": "first", "start": [0, 0, 0], "end": [0.4, -0.4, 0]},
            {"op": "line", "name": "second", "start": [0, 0, 0.4], "end": [0.4, -0.4, 0.4]},
        ]
    )
    w = create_integrated_workbench(s.document, professional_ui=not classic)
    w.show()
    app.processEvents()
    return w


def test_install_preserves_scene_widgets_and_is_idempotent(app):
    from adaptivecad.gui.workbench_ui import install_workbench_ui

    w = create(app, classic=True)
    originals = w.view, w.scene, w.listing, w.editor, w.report, w.session
    entities = tuple(w.scene.items())
    ui = install_workbench_ui(w)
    assert install_workbench_ui(w) is ui
    assert originals == (w.view, w.scene, w.listing, w.editor, w.report, w.session)
    assert all(item in w.scene.items() for item in entities)
    assert not hasattr(w, "_meshfree_window")
    assert len(ui.docks) == 3
    assert ui.ribbon.count() == 4
    assert w.centralWidget().layout().stretch(2) == 1


def test_real_click_selection_keeps_native_targets(app, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from shiboken6 import isValid

    import adaptivecad.gui.meshfree_workbench as backend

    w = create(app)
    w.fit_view()
    app.processEvents()
    items = {item.data(0): item for item in w.scene.items()}
    before = w.session.document
    transform = w.view.transform()
    monkeypatch.setattr(
        backend, "wireframe", lambda *a, **k: pytest.fail("Selection rebuilt geometry")
    )
    for name in ("second", "first") * 3:
        item = items[name]
        center = w.view.mapFromScene(item.mapToScene(item.path().pointAtPercent(0.5)))
        hits = [
            center + QPoint(dx, dy)
            for dx in range(-3, 4)
            for dy in range(-3, 4)
            if w.view.itemAt(center + QPoint(dx, dy)) is item
        ]
        assert hits
        QTest.mouseClick(
            w.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, hits[0]
        )
        app.processEvents()
        assert w.listing.currentItem().text() == name
        assert w._workbench_ui.selection_title.text() == name
        assert all(isValid(target) and target in w.scene.items() for target in items.values())
    assert w.session.document is before
    assert w.view.transform() == transform


def test_browser_filter_is_visual_and_does_not_mutate_geometry(app):
    w = create(app)
    doc = w.session.document
    items = tuple(w.scene.items())
    w._workbench_ui.filter.setText("SECOND")
    assert w.listing.item(0).isHidden() and not w.listing.item(1).isHidden()
    assert w.session.document is doc
    assert all(item in w.scene.items() and item.isVisible() for item in items)
    w._workbench_ui.filter.clear()
    assert not any(w.listing.item(i).isHidden() for i in range(2))


def test_form_validate_cancel_apply_and_independent_histories(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    w = create(app)
    ui, metric = w._workbench_ui, w._metric_workbench
    old_model, old_metric = w.session.document, metric.history.current
    undo_count = len(w.session._undo)
    ui.actions["Line"].trigger()
    d = ui.dialog
    app.processEvents()
    d.fields["name"][1].setText("created")
    QTest.mouseClick(d.validate_button, Qt.MouseButton.LeftButton)
    assert "Valid:" in d.message.text()
    assert w.session.document is old_model and len(w.session._undo) == undo_count
    QTest.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert ui.dialog is None
    assert w.session.document.get("created")
    assert metric.history.current is old_metric
    assert len(w.session._undo) == undo_count + 1
    ui.actions["undo"].trigger()
    assert w.session.document == old_model
    ui.actions["redo"].trigger()
    assert w.session.document.get("created")
    saved = w.session.document
    ui.open_command("Rotate")
    ui.dialog.reject()
    assert w.session.document is saved


def test_invalid_and_stale_dialogs_do_not_commit(app):
    w = create(app)
    ui = w._workbench_ui
    ui.open_command("Line")
    d = ui.dialog
    old = w.session.document
    d.fields["start"][1].setText("NaN, 0, 0")
    d.apply()
    assert w.session.document is old
    assert "No command committed" in d.message.text()
    d.fields["start"][1].setText("0, 0, 0")
    w.session.execute({"op": "copy", "name": "elsewhere", "source": "first"})
    w.refresh()
    changed = w.session.document
    d.apply()
    assert w.session.document is changed
    assert "Model changed" in d.message.text()
    d.reject()


def test_delete_confirmation_is_undoable(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    w = create(app)
    ui, old = w._workbench_ui, w.session.document
    ui.actions["delete"].trigger()
    assert w.session.document is old
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    ui.actions["delete"].trigger()
    assert len(w.session.document.entities) == 1
    ui.actions["undo"].trigger()
    assert w.session.document == old


def test_model_shortcuts_cannot_steal_metric_editor_undo(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QShortcut

    w = create(app)
    for widget in (w.view, w.listing):
        shortcuts = widget.findChildren(QShortcut)
        assert len(shortcuts) == 4
        assert all(s.context() == Qt.ShortcutContext.WidgetShortcut for s in shortcuts)
    assert not w._metric_workbench.findChildren(QShortcut)


def test_transfer_action_reuses_original_guarded_dialog(app):
    w = create(app)
    ui, metric = w._workbench_ui, w._metric_workbench
    before = w.session.document
    assert ui.actions["transfer"] is w._curve_transfer_action
    ui.actions["transfer"].trigger()
    dialog = w._curve_transfer_dialog
    assert dialog is not None
    dialog.prepare()
    assert dialog.prepared is not None
    assert not dialog.copy_button.isEnabled()
    dialog.confirm.setChecked(True)
    dialog.copy_curve()
    app.processEvents()
    assert w.session.document is before
    assert len(metric.history.current.curves) == 1
    assert ui.actions["receipt"] is w._curve_transfer_receipt_action
    assert ui.actions["receipt"].isEnabled()


def test_draft_metric_and_dirty_model_still_block_close(app):
    w = create(app)
    w._metric_workbench.patch_editor.document().setModified(True)
    assert not w.close()
    w._metric_workbench.patch_editor.document().setModified(False)
    w.session.execute({"op": "copy", "name": "new", "source": "first"})
    w.refresh()
    assert not w.close()


def test_layout_save_restore_does_not_write_document(app, tmp_path):
    from PySide6.QtCore import QSettings

    w = create(app)
    ui = w._workbench_ui
    before = w.session.document, w._metric_workbench.history.current
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    try:
        ui.save_layout()
        ui.docks["ModelBrowser"].hide()
        ui.restore_layout()
        assert not ui.docks["ModelBrowser"].isHidden()
        assert (w.session.document, w._metric_workbench.history.current) == before
        assert list(tmp_path.rglob("*.ini"))
    finally:
        QSettings.setDefaultFormat(QSettings.Format.NativeFormat)


def test_command_search_opens_a_real_parameter_form(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit

    w = create(app)
    ui = w._workbench_ui
    ui.command_palette()
    search = ui.palette_dialog.findChild(QLineEdit)
    search.setText("Extrude sheet")
    QTest.keyClick(search, Qt.Key.Key_Return)
    app.processEvents()
    assert ui.palette_dialog is None
    assert ui.dialog.label == "Extrude sheet"
    ui.dialog.reject()


def test_ui_screenshot_and_native_definition(app):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    from examples.meshfree_toolkit_demo import demo_session

    w = create_integrated_workbench(demo_session().document)
    w.show()
    app.processEvents()
    w.fit_view()
    ui = w._workbench_ui
    assert json.loads(ui.definition.toPlainText())["type"] in ("curve", "surface")
    output = os.environ.get("WORKBENCH_UI_SCREENSHOT")
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        assert w.grab().save(str(target))
        ui.open_command("Extrude sheet")
        app.processEvents()
        assert ui.dialog.grab().save(str(target.with_name("model-parameters.png")))
        ui.dialog.reject()
        ui.show_metrics()
        app.processEvents()
        assert w.grab().save(str(target.with_name("model-and-metric.png")))
