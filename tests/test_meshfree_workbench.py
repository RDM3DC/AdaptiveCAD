"""Headless document/CLI tests plus real Qt smoke tests when Qt is installed."""
import json
import os
import subprocess
import sys

import pytest

from adaptivecad.geom.tool_document import ToolDocument
from examples.meshfree_toolkit_demo import demo_session, preview_html


@pytest.fixture(scope='module')
def _qt_application():
    # QApplication must outlive every graphics item and every Qt test window.
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PySide6.QtWidgets')
    app = widgets.QApplication.instance() or widgets.QApplication([])
    yield app


@pytest.fixture
def qt_app(_qt_application):
    from PySide6.QtCore import QCoreApplication, QEvent

    yield _qt_application
    # close() only hides a window. Destroy Qt-owned children while the app lives,
    # rather than depending on Python/Qt garbage-collection order at test return.
    for widget in _qt_application.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _qt_application.processEvents()


def test_demo_roundtrip_and_preview_escaping():
    session = demo_session()
    doc = session.document
    assert ToolDocument.from_json(doc.to_json()) == doc
    assert len(doc.entities) == 9
    text = preview_html(doc)
    assert '<polyline' in text and '<polygon' not in text
    items = tuple(('<script>alert(1)</script>' if n == 'extrusion' else n, e) for n, e in doc.entities)
    escaped = preview_html(ToolDocument(doc.unit, items, doc.metric))
    assert '<script>' not in escaped
    assert '&lt;script&gt;' in escaped


def test_cli_real_files_and_no_overwrite(tmp_path):
    command = [sys.executable, '-m', 'examples.meshfree_toolkit_demo', '--out', str(tmp_path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    document = ToolDocument.load(tmp_path/'document.json')
    assert len(document.entities) == 9
    report = json.loads((tmp_path/'report.json').read_text())
    assert len(report['surfaces']) == 4
    before = (tmp_path/'document.json').read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert second.returncode != 0
    assert (tmp_path/'document.json').read_bytes() == before


def test_real_qt_workbench_commands_and_menu_bridge(tmp_path, monkeypatch, qt_app):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PySide6.QtWidgets')
    from adaptivecad.gui.meshfree_workbench import create_workbench, install_meshfree_tools
    app = qt_app
    window = create_workbench(document=demo_session().document)
    window.show()
    app.processEvents()

    def bounds_for(name):
        bounds = None
        for item in window.scene.items():
            if item.data(0) == name:
                item_bounds = item.path().boundingRect()
                bounds = item_bounds if bounds is None else bounds.united(item_bounds)
        assert bounds is not None
        return bounds

    def highlighted_names():
        return {item.data(0) for item in window.scene.items() if item.pen().widthF() > 0}

    assert window.listing.count() == 9
    assert window.listing.currentItem().text() == 'circle'
    assert {item.data(0) for item in window.scene.items()} == {
        name for name, _ in window.session.document.entities
    }
    circle_bounds = bounds_for('circle')
    translated_bounds = bounds_for('circle_top')
    assert translated_bounds.width() == pytest.approx(circle_bounds.width()*.5)
    assert translated_bounds.height() == pytest.approx(circle_bounds.height()*.5)
    assert translated_bounds.center().x() > circle_bounds.center().x()
    assert translated_bounds.center().y() < circle_bounds.center().y()
    window.view.resetTransform()
    window.view.scale(.01, .01)
    window.fit_view()
    assert window.view.transform().m11() > .01
    selected_items = [item for item in window.scene.items() if item.data(0) == 'circle']
    other_items = [item for item in window.scene.items() if item.data(0) != 'circle']
    assert selected_items and other_items
    assert selected_items[0].pen().widthF() > other_items[0].pen().widthF()
    profile_item = next(item for item in window.scene.items() if item.data(0) == 'profile')
    profile_item.setSelected(True)
    app.processEvents()
    assert window.listing.currentItem().text() == 'profile'
    window.listing.setCurrentRow(0)
    window.editor.setPlainText(json.dumps({'op': 'copy', 'source': 'circle', 'name': 'new_circle'}))
    window.execute()
    assert window.listing.count() == 10
    assert window.listing.currentItem().text() == 'circle'
    window.undo()
    assert window.listing.count() == 9
    assert window.listing.currentItem().text() == 'circle'
    window.redo()
    assert window.listing.count() == 10
    assert window.listing.currentItem().text() == 'circle'
    window.delete_selected()
    assert window.listing.count() == 9
    assert 'circle' not in [window.listing.item(i).text() for i in range(window.listing.count())]
    selected_after_delete = window.listing.currentItem().text()
    assert highlighted_names() == {selected_after_delete}
    window.undo()
    assert window.listing.count() == 10
    assert 'circle' in [window.listing.item(i).text() for i in range(window.listing.count())]
    assert window.listing.currentItem().text() == selected_after_delete
    assert highlighted_names() == {selected_after_delete}
    window.redo()
    assert window.listing.count() == 9
    assert 'circle' not in [window.listing.item(i).text() for i in range(window.listing.count())]
    assert window.listing.currentItem().text() == selected_after_delete
    window.undo()
    saved_document = window.session.document
    save_path = tmp_path/'workbench.json'
    monkeypatch.setattr(widgets.QFileDialog, 'getSaveFileName',
                        lambda *args, **kwargs: (str(save_path), 'Mesh-free JSON (*.json)'))
    window.save_file()
    assert ToolDocument.load(save_path) == saved_document
    window.delete_selected()
    assert window.session.document != saved_document
    monkeypatch.setattr(widgets.QFileDialog, 'getOpenFileName',
                        lambda *args, **kwargs: (str(save_path), 'Mesh-free JSON (*.json)'))
    monkeypatch.setattr(widgets.QMessageBox, 'question',
                        lambda *args, **kwargs: widgets.QMessageBox.StandardButton.Yes)
    window.load_file()
    assert window.session.document == saved_document
    loaded_item = next(item for item in window.scene.items() if item.data(0) == 'profile')
    loaded_item.setSelected(True)
    app.processEvents()
    assert window.listing.currentItem().text() == 'profile'
    previous = window.session.document
    window.editor.setPlainText('{"op":"eval"}')
    window.execute()
    assert window.session.document == previous
    window.listing.setCurrentRow(0)
    window.measure()
    assert 'length' in window.report.toPlainText()
    parent = widgets.QMainWindow()
    action = install_meshfree_tools(parent)
    assert action is install_meshfree_tools(parent)
    action.trigger()
    app.processEvents()
    assert parent._meshfree_window.isVisible()
    parent._meshfree_window.close()
    parent.close()
    window.close()


def test_selection_keeps_event_targets_alive_and_does_not_rebuild(monkeypatch, qt_app):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6.QtWidgets')
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from shiboken6 import isValid

    import adaptivecad.gui.meshfree_workbench as workbench
    from adaptivecad.geom.tool_document import ToolSession

    session = ToolSession()
    session.execute_many([
        {'op': 'line', 'name': 'first', 'start': [0, 0, 0], 'end': [10, -10, 0]},
        {'op': 'line', 'name': 'second', 'start': [0, 0, 20], 'end': [10, -10, 20]},
    ])
    app = qt_app
    window = workbench.create_workbench(document=session.document)
    window.show()
    app.processEvents()
    items = {item.data(0): item for item in window.scene.items()}
    document = window.session.document
    transform = window.view.transform()

    def unexpected_rebuild(*args, **kwargs):
        pytest.fail('Selection must not regenerate wireframes or replace scene items')

    monkeypatch.setattr(workbench, 'wireframe', unexpected_rebuild)
    try:
        for name in ('second', 'first') * 5:
            items[name].setSelected(True)
            assert all(isValid(item) for item in items.values())
            assert window.listing.currentItem().text() == name
            assert {item.data(0) for item in window.scene.selectedItems()} == {name}
            assert all(window.scene.items().count(item) == 1 for item in items.values())
            row = 0 if name == 'second' else 1
            window.listing.setCurrentRow(row)
            assert all(isValid(item) for item in items.values())
            assert {item.data(0) for item in window.scene.selectedItems()} == {
                window.listing.currentItem().text()
            }

        # Exercise real press/release dispatch, not only setSelected() signals.
        for name in ('second', 'first') * 3:
            item = items[name]
            center = window.view.mapFromScene(item.mapToScene(item.path().pointAtPercent(.5)))
            hits = [center + QPoint(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
                    if window.view.itemAt(center + QPoint(dx, dy)) is item]
            assert hits, f'No clickable viewport point for {name}'
            QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, hits[0])
            app.processEvents()
            assert all(isValid(target) for target in items.values())
            assert window.listing.currentItem().text() == name
        assert window.session.document == document
        assert window.view.transform() == transform
        window.scene.clearSelection()
        assert window.listing.currentRow() == -1
        assert not window.scene.selectedItems()
        assert all(isValid(item) for item in items.values())
    finally:
        window.close()


def test_model_refresh_blocks_selection_signals_through_empty_and_undo(qt_app):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6.QtWidgets')
    from adaptivecad.geom.tool_document import ToolSession
    from adaptivecad.gui.meshfree_workbench import create_workbench

    session = ToolSession()
    session.execute({'op': 'line', 'name': 'only', 'start': [0, 0, 0], 'end': [1, 1, 0]})
    app = qt_app
    window = create_workbench(document=session.document)
    callbacks = []
    window.scene.selectionChanged.connect(lambda: callbacks.append(True))
    try:
        for _ in range(3):
            window.delete_selected()
            assert window.listing.count() == 0
            assert not window.scene.items()
            assert not window.scene.signalsBlocked()
            assert not window.listing.signalsBlocked()
            window.undo()
            assert window.listing.currentItem().text() == 'only'
            assert {item.data(0) for item in window.scene.selectedItems()} == {'only'}
            window.redo()
            assert not window.scene.items()
            window.undo()
            app.processEvents()
        assert not callbacks, 'No selection callbacks may escape a scene rebuild'
    finally:
        window.close()
