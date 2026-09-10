import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QScrollArea, QWidget

from adaptivecad.gui.metric_dock_layout import prepare_metric_dock
from adaptivecad.gui.metric_workbench import install_metric_workbench


@pytest.mark.parametrize("with_peer", [False, True])
def test_layout_is_scrolled_tabbed_and_idempotent(with_peer):
    app = QApplication.instance() or QApplication([])
    host = QMainWindow()
    peer = None
    if with_peer:
        peer = QDockWidget("Existing tools", host)
        peer.setWidget(QWidget())
        host.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, peer)
    dock = install_metric_workbench(host)
    root = dock.widget()
    project = dock.history.current
    prepare_metric_dock(host, dock)
    assert isinstance(dock.widget(), QScrollArea)
    assert dock.widget().widget() is root
    assert dock.history.current is project
    assert prepare_metric_dock(host, dock) is dock
    assert dock.widget().widget() is root
    if peer:
        assert dock in host.tabifiedDockWidgets(peer)
    dock.new_curve()
    dock.apply_editors()
    assert len(dock.history.current.curves) == 1
    dock.history.mark_saved()
    host.removeEventFilter(dock)
    host.close()
    host.deleteLater()
    app.processEvents()
