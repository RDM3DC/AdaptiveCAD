"""Headless document/CLI tests plus real Qt smoke tests when Qt is installed."""
import json
import os
import subprocess
import sys

import pytest

from adaptivecad.geom.tool_document import ToolDocument
from examples.meshfree_toolkit_demo import demo_session, preview_html


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


def test_real_qt_workbench_commands_and_menu_bridge(tmp_path, monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PySide6.QtWidgets')
    from adaptivecad.gui.meshfree_workbench import create_workbench, install_meshfree_tools
    app = widgets.QApplication.instance() or widgets.QApplication([])
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
