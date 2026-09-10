"""Combined API, real Qt coexistence, and non-destructive close/save regressions."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

_APP = None


@pytest.fixture(scope='module')
def application():
    global _APP
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PySide6.QtWidgets')
    _APP = widgets.QApplication.instance() or widgets.QApplication([])
    return _APP


@pytest.fixture
def qt_app(application, monkeypatch):
    from PySide6.QtWidgets import QMessageBox, QGraphicsScene, QWidget
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid
    # Own only windows created by this test. Other suites can retain hidden
    # windows; deleting those here violates their Python/Qt ownership boundary.
    existing = tuple(application.topLevelWidgets())
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Cancel)
    yield application
    roots = [w for w in application.topLevelWidgets()
             if w.parentWidget() is None and all(w is not old for old in existing)]
    for root in roots:
        for widget in [root] + root.findChildren(QWidget):
            if hasattr(widget, 'guard_unsaved'):
                widget.guard_unsaved = False
                widget._saved_document = widget.session.document
            if hasattr(widget, 'drafts_dirty') and hasattr(widget, 'history'):
                widget.history.mark_saved()
                widget.patch_editor.document().setModified(False)
                widget.curve_editor.document().setModified(False)
        # Destruction may emit selection signals after sibling widgets die.
        # Tests run with signals enabled; block only at the ownership teardown.
        for scene in root.findChildren(QGraphicsScene):
            scene.blockSignals(True)
        root.close()
        root.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    assert all(not isValid(root) for root in roots)


def edit_model(window, name='test_line'):
    window.editor.setPlainText(json.dumps({'op': 'line', 'name': name,
                                          'start': [0, 0, 0], 'end': [1, 0, 0]}))
    window.execute()
    assert window.session.document.get(name)


def test_import_and_help_do_not_load_qt():
    script = ('import sys; import adaptivecad.gui.integrated_workbench; '
              'assert not any(k.startswith("PySide6") for k in sys.modules)')
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    help_run = subprocess.run([sys.executable, 'run_workbenches.py', '--help'],
                              capture_output=True, text=True, timeout=15)
    assert help_run.returncode == 0, help_run.stderr
    assert '--metric-project' in help_run.stdout


@pytest.mark.parametrize('xy', [(0, 0), (.4, .2), (-.3, .1)])
def test_both_metric_namespaces_preserve_equivalent_quantities(xy):
    from adaptivecad.geom.directional_metric import balanced_directional_patch
    from adaptivecad.geom import meshfree_metric_tools as toolkit
    from adaptivecad.geom import metric_tools as dock
    patch = balanced_directional_patch()
    np.testing.assert_allclose(toolkit.metric_derivatives(patch, *xy), dock.metric_derivatives(patch, *xy))
    np.testing.assert_allclose(toolkit.connection(patch, *xy), dock.christoffel(patch, *xy), atol=1e-14)
    assert toolkit.angle_between(patch, xy, (1, 2), (2, -1)) == pytest.approx(
        dock.angle_between(patch, xy, (1, 2), (2, -1)))
    assert toolkit.disk_area(patch, .3).value == pytest.approx(dock.disk_area(patch, .3).value)
    assert toolkit.area_radius(patch, math.pi * .3**2) == pytest.approx(.3)


def test_geodesic_result_contracts_remain_distinct():
    from adaptivecad.geom.directional_metric import NormalMetricPatch
    from adaptivecad.geom.meshfree_metric_tools import trace_geodesic as toolkit_trace
    from adaptivecad.geom.metric_geodesic import trace_geodesic as dock_trace
    patch = NormalMetricPatch()
    a = toolkit_trace(patch, (0, 0), (1, 0), .2)
    b = dock_trace(patch, (0, 0), (1, 0), .2)
    assert a.positions[-1] == pytest.approx((.2, 0))
    assert b.points[-1] == pytest.approx((.2, 0))
    assert type(a) is not type(b)


def test_document_schemas_are_not_silently_converted():
    from adaptivecad.geom.tool_document import ToolDocument
    from adaptivecad.metric_project import MetricProject
    a, b = ToolDocument(), MetricProject()
    with pytest.raises((ValueError, TypeError)):
        ToolDocument.from_json(b.to_json())
    with pytest.raises((ValueError, TypeError)):
        MetricProject.from_json(a.to_json())


def test_one_existing_window_two_independent_histories(qt_app):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    window = create_integrated_workbench()
    window.show()
    dock = window._metric_workbench
    original_project = dock.history.current
    edit_model(window)
    assert dock.history.current == original_project
    saved_model = window.session.document
    dock.new_curve()
    dock.apply_editors()
    assert window.session.document == saved_model
    dock.undo()
    assert dock.history.current == original_project
    assert window.session.document == saved_model
    window.undo()
    assert not window.has_unsaved_changes
    assert not hasattr(window, '_meshfree_window')


def test_installers_idempotent_preserve_existing_host(qt_app):
    from PySide6.QtWidgets import QLabel, QMainWindow, QDockWidget
    from adaptivecad.gui.integrated_workbench import install_integrated_tools
    host = QMainWindow()
    central = QLabel('Existing solid scene')
    host.setCentralWidget(central)
    old_menu = host.menuBar().addMenu('Existing modeling commands')
    dock = install_integrated_tools(host)
    assert install_integrated_tools(host) is dock
    assert host.centralWidget() is central
    assert old_menu.menuAction() in host.menuBar().actions()
    assert len(host.findChildren(QDockWidget, 'AdaptiveCADMetricWorkbench')) == 1
    assert sum(a.text() == 'Mesh-free Tools' for a in host.menuBar().actions()) == 1
    host._meshfree_action.trigger()
    child = host._meshfree_window
    host._meshfree_action.trigger()
    assert host._meshfree_window is child
    assert child.guard_unsaved


def test_close_cancel_preserves_both_documents(qt_app):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    window = create_integrated_workbench()
    window.show()
    edit_model(window)
    doc, project = window.session.document, window._metric_workbench.history.current
    assert not window.close()
    assert window.isVisible()
    assert window.session.document == doc
    assert window._metric_workbench.history.current == project


def test_cancelled_save_blocks_close(qt_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    window = create_integrated_workbench()
    window.show()
    edit_model(window)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    assert not window.close()
    assert window.has_unsaved_changes


def test_failed_save_keeps_dirty_state_and_contents(qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    from adaptivecad.geom.tool_document import ToolDocument
    window = create_integrated_workbench()
    edit_model(window)
    path = tmp_path / 'existing.json'
    path.write_text('original data')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(path), ''))
    def fail(*args, **kwargs):
        raise OSError('simulated write failure')
    monkeypatch.setattr(ToolDocument, 'save', fail)
    assert window.save_file() is False
    assert window.has_unsaved_changes
    assert path.read_text() == 'original data'


def test_successful_saves_and_undo_have_independent_dirty_states(qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    from adaptivecad.geom.tool_document import ToolDocument
    from adaptivecad.metric_project import MetricProject
    window = create_integrated_workbench()
    dock = window._metric_workbench
    edit_model(window)
    dock.new_curve()
    dock.apply_editors()
    model_path = tmp_path / 'model.json'
    metric_path = tmp_path / 'metric.acmetric.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(model_path), ''))
    assert window.save_file() is True
    assert not window.has_unsaved_changes and dock.history.dirty
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(metric_path), ''))
    assert dock.save_project() is True
    assert not dock.history.dirty
    assert ToolDocument.load(model_path) == window.session.document
    assert MetricProject.load(metric_path) == dock.history.current
    window.undo()
    assert window.has_unsaved_changes and not dock.history.dirty
    window.redo()
    assert not window.has_unsaved_changes


def test_invalid_open_validates_before_any_save_prompt(qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    window = create_integrated_workbench()
    edit_model(window)
    document = window.session.document
    bad = tmp_path / 'bad.json'
    bad.write_text('{"broken": true}')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(bad), ''))
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid input must fail before asking to discard/save current work')
    monkeypatch.setattr(QMessageBox, 'question', unexpected)
    window.load_file()
    assert window.session.document == document and window.has_unsaved_changes


def test_host_close_cannot_discard_dirty_model_child(qt_app):
    from PySide6.QtWidgets import QMainWindow
    from adaptivecad.gui.integrated_workbench import install_integrated_tools
    host = QMainWindow()
    install_integrated_tools(host)
    host.show()
    host._meshfree_action.trigger()
    child = host._meshfree_window
    edit_model(child)
    assert not host.close()
    assert host.isVisible() and child.isVisible()


def test_metric_draft_cancel_protects_integrated_window(qt_app):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    window = create_integrated_workbench()
    window.show()
    dock = window._metric_workbench
    dock.patch_editor.setPlainText('unapplied draft')
    dock.patch_editor.document().setModified(True)
    assert not window.close()
    assert dock.patch_editor.toPlainText() == 'unapplied draft'


def test_real_combined_preview(qt_app):
    from adaptivecad.gui.integrated_workbench import create_integrated_workbench
    from examples.meshfree_toolkit_demo import demo_session
    window = create_integrated_workbench(demo_session().document)
    window.show()
    dock = window._metric_workbench
    dock.new_curve()
    dock.apply_editors()
    dock.show()
    dock.raise_()
    qt_app.processEvents()
    assert window.listing.count() == 9 and dock.isVisible()
    assert len(dock.history.current.curves) == 1
    assert {item.data(0) for item in window.scene.items()} == {
        n for n, _ in window.session.document.entities
    }
    filename = os.environ.get('INTEGRATED_SCREENSHOT')
    if filename:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        assert window.grab().save(str(path))
