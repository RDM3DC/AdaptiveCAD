"""Real Qt widget/interaction tests; no OCC, OpenGL viewport or fake Qt mocks."""
import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest

pytest.importorskip('PySide6')
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from adaptivecad.geom.directional_metric import NormalMetricPatch
from adaptivecad.gui.metric_workbench import install_metric_workbench
from adaptivecad.metric_project import MetricProject


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dock(app, monkeypatch):
    host=QMainWindow(); host.setWindowTitle('AdaptiveCAD metric tools test host'); host.resize(1300,900)
    d=install_metric_workbench(host); d.show(); host.show(); app.processEvents()
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k: QMessageBox.StandardButton.Ok)
    yield d
    d.history.mark_saved(); d.patch_editor.document().setModified(False); d.curve_editor.document().setModified(False)
    host.removeEventFilter(d); host.close(); host.deleteLater(); app.processEvents()


def test_installer_idempotent_and_menu(dock):
    host=dock.parentWidget()
    assert install_metric_workbench(host) is dock
    assert install_metric_workbench(type('Host',(),{'win':host})()) is dock
    menus=[a.menu() for a in host.menuBar().actions() if a.menu()]
    assert len([m for m in menus if m.objectName()=='AdaptiveCADMetricToolsMenu'])==1
    menu=next(m for m in menus if m.objectName()=='AdaptiveCADMetricToolsMenu')
    menu.actions()[-1].trigger()
    assert dock.tabs.currentIndex()==3


def test_edit_measure_split_undo_save_reopen(dock,tmp_path,monkeypatch):
    dock.preset.setCurrentIndex(1); dock.use_preset()
    dock.new_curve(); dock.apply_editors()
    assert len(dock.history.current.curves)==1
    dock.measure_curve(); assert dock.last_report['kind']=='native_bezier'
    dock.edit_curve('split'); assert len(dock.history.current.curves)==2
    assert dock.last_report is None
    dock.undo(); assert len(dock.history.current.curves)==1
    dock.redo(); assert len(dock.history.current.curves)==2
    path=tmp_path/'document.acmetric.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    assert dock.save_project() is True
    assert not dock.history.dirty
    assert MetricProject.load(path)==dock.history.current
    saved=dock.history.current
    dock.new_project(); assert not dock.history.current.curves
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    dock.open_project(); assert dock.history.current==saved


def test_invalid_draft_never_overwrites_file(dock,tmp_path):
    path=tmp_path/'a.acmetric.json'; dock.history.current.save(path); original=path.read_bytes()
    dock.project_path=str(path); before=dock.history.current
    dock.patch_editor.setPlainText('{bad'); dock.patch_editor.document().setModified(True)
    with pytest.raises(ValueError): dock.save_project()
    assert path.read_bytes()==original and dock.history.current==before
    with pytest.raises(ValueError): dock.run_trace()


def test_joint_patch_and_curve_edit_atomic(dock):
    dock.new_curve(); dock.apply_editors()
    dock.patch_editor.setPlainText(NormalMetricPatch(radius=.1).to_json())
    dock.patch_editor.document().setModified(True)
    dock.curve_editor.setPlainText('[[0,0],[0.05,0]]'); dock.curve_editor.document().setModified(True)
    dock.apply_editors()
    assert dock.history.current.patch.radius==.1
    assert dock.history.current.curves[0].controls[-1]==(.05,0)


def test_measure_trace_map_and_report_invalidation(dock,tmp_path,monkeypatch,app):
    dock.preset.setCurrentIndex(1); dock.use_preset(); dock.measure()
    assert dock.last_report['result']['disk_area']['value']>0
    dock.run_trace(); assert dock.trace.status=='complete'
    assert dock.last_report['kind']=='geodesic_initial_value'
    dock.heatmap.setChecked(True); app.processEvents()
    assert 'Sampled K range' in dock.map_label.text()
    screenshot=os.environ.get('METRIC_WORKBENCH_SCREENSHOT')
    if screenshot:
        path=Path(screenshot); path.parent.mkdir(parents=True,exist_ok=True)
        assert dock.parentWidget().grab().save(str(path))
    report_path=tmp_path/'report.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(report_path),''))
    dock.export_report()
    assert json.loads(report_path.read_text())['project_sha256']==dock.last_report['project_sha256']
    dock.units.setCurrentText('ft_us'); dock.convert_units()
    assert dock.last_report is None and dock.trace is None
    assert dock.history.current.patch.unit=='ft_us'


def test_cancel_close_preserves_edits(dock,monkeypatch):
    dock.new_curve()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Cancel)
    event=QCloseEvent()
    assert dock.eventFilter(dock._host,event) is True
    assert not event.isAccepted() and dock.drafts_dirty()


def test_cancel_save_then_close_does_not_discard(dock,monkeypatch):
    dock.new_curve(); dock.apply_editors()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:('',''))
    assert dock._maybe_save() is False
    assert dock.history.dirty


def test_actions_execute_and_bad_transform_is_nonmutating(dock):
    dock.new_curve(); dock.apply_editors(); before=dock.history.current
    dock.transform_values.setText('[10,0,0,1]')
    with pytest.raises(ValueError): dock.edit_curve('transform')
    assert dock.history.current==before
    dock.actions['undo'].trigger(); assert not dock.history.current.curves
    dock.actions['redo'].trigger(); assert dock.history.current==before
