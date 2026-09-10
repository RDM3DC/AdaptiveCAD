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


def test_real_qt_workbench_commands_and_menu_bridge():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PySide6.QtWidgets')
    from adaptivecad.gui.meshfree_workbench import create_workbench, install_meshfree_tools
    app = widgets.QApplication.instance() or widgets.QApplication([])
    window = create_workbench(document=demo_session().document)
    window.show()
    app.processEvents()
    assert window.listing.count() == 9
    window.editor.setPlainText(json.dumps({'op': 'copy', 'source': 'circle', 'name': 'new_circle'}))
    window.execute()
    assert window.listing.count() == 10
    window.undo()
    assert window.listing.count() == 9
    window.redo()
    assert window.listing.count() == 10
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
