"""Optional standalone PySide6 workbench for the tested mesh-free tool API.

Launch: python -m adaptivecad.gui.meshfree_workbench
Embedding: install_meshfree_tools(existing_qmainwindow)
No existing GUI, main scene or AMA document is modified automatically.
"""
from __future__ import annotations

import json
import math
import sys

from adaptivecad.geom.meshfree_tools import Curve, wireframe
from adaptivecad.geom.tool_document import ToolDocument, ToolSession, strict_json

PRESETS = {
    'Line': {'op': 'line', 'name': 'line', 'start': [10, 0, 0], 'end': [10, 0, 20]},
    'Bezier': {'op': 'bezier', 'name': 'profile', 'points': [[0, 0, 0], [8, 0, 2], [10, 0, 10], [3, 0, 20]]},
    'Circle / arc': {'op': 'arc', 'name': 'circle', 'radius': 10, 'sweep': math.tau},
    'Extrude sheet': {'op': 'extrude', 'name': 'extrusion', 'source': 'circle', 'vector': [0, 0, 20]},
    'Revolve sheet': {'op': 'revolve', 'name': 'revolution', 'source': 'line', 'axis': [0, 0, 1], 'angle': 1.5*math.pi},
    'Ruled loft': {'op': 'loft', 'name': 'loft', 'source': 'circle', 'target': 'circle_top'},
    'Translation sweep': {'op': 'sweep', 'name': 'sweep', 'source': 'circle', 'path': 'profile'},
    'Move / copy': {'op': 'move', 'name': 'circle_top', 'source': 'circle', 'delta': [0, 0, 20]},
    'Copy': {'op': 'copy', 'name': 'copy', 'source': 'line'},
    'Rotate': {'op': 'rotate', 'name': 'rotated', 'source': 'line', 'axis': [1, 0, 0], 'angle': math.pi/4},
    'Scale': {'op': 'scale', 'name': 'scaled', 'source': 'circle', 'factor': 2},
    'Mirror': {'op': 'mirror', 'name': 'mirrored', 'source': 'profile', 'normal': [1, 0, 0]},
    'Trim by parameter': {'op': 'trim', 'name': 'trimmed', 'source': 'profile', 'start': .2, 'stop': .8},
    'Split': {'op': 'split', 'name': 'split', 'source': 'profile', 'parameter': .5},
    'Reverse': {'op': 'reverse', 'name': 'reversed', 'source': 'profile'},
    'Rectangular array': {'op': 'rectangular_array', 'name': 'array', 'source': 'circle', 'rows': 2, 'columns': 3,
                          'row_step': [0, 25, 0], 'column_step': [25, 0, 0]},
    'Polar array': {'op': 'polar_array', 'name': 'polar', 'source': 'line', 'instances': 6},
    'Convert units': {'op': 'convert_units', 'unit': 'ft_us'},
    'Delete': {'op': 'delete', 'source': 'line'},
}


def create_workbench(parent=None, document=None):
    """Lazy Qt import keeps core geometry usable on headless machines."""
    try:
        from PySide6.QtCore import QSignalBlocker, Qt
        from PySide6.QtGui import QPainterPath, QPen
        from PySide6.QtWidgets import (
            QComboBox, QFileDialog, QGraphicsScene, QGraphicsView, QHBoxLayout,
            QGraphicsItem, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton,
            QSplitter, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError as exc:
        raise RuntimeError('This workbench requires PySide6 in your AdaptiveCAD environment') from exc

    class Workbench(QMainWindow):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle('AdaptiveCAD — Mesh-free Tool Workbench')
            self.resize(1180, 760)
            self.session = ToolSession(document)
            root = QWidget()
            self.setCentralWidget(root)
            layout = QVBoxLayout(root)
            layout.addWidget(QLabel('Evaluated curves and sheets • angles in radians • wireframe preview only • not machine output'))
            bar = QHBoxLayout()
            layout.addLayout(bar)
            for label, method in [('Open', self.load_file), ('Save as', self.save_file),
                                  ('Undo', self.undo), ('Redo', self.redo), ('Fit all', self.fit_view),
                                  ('Delete selected', self.delete_selected), ('Measure selected', self.measure)]:
                button = QPushButton(label)
                button.clicked.connect(method)
                bar.addWidget(button)
            split = QSplitter()
            layout.addWidget(split)
            controls = QWidget()
            col = QVBoxLayout(controls)
            split.addWidget(controls)
            self.templates = QComboBox()
            self.templates.addItems(PRESETS)
            col.addWidget(self.templates)
            self.editor = QTextEdit()
            col.addWidget(self.editor)
            execute = QPushButton('Apply command / atomic command batch')
            execute.clicked.connect(self.execute)
            col.addWidget(execute)
            self.listing = QListWidget()
            col.addWidget(self.listing)
            self.report = QTextEdit()
            self.report.setReadOnly(True)
            col.addWidget(self.report)
            self.scene = QGraphicsScene()
            self.scene.selectionChanged.connect(self.select_scene_item)
            self.view = QGraphicsView(self.scene)
            split.addWidget(self.view)
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            split.setSizes([430, 750])
            self.templates.currentTextChanged.connect(self.template)
            self.listing.currentRowChanged.connect(self.highlight_selection)
            self.template(self.templates.currentText())
            self.refresh()

        def template(self, label):
            self.editor.setPlainText(json.dumps(PRESETS[label], indent=2))

        def select_scene_item(self):
            selected = self.scene.selectedItems()
            if not selected:
                self.listing.setCurrentRow(-1)
                return
            current = self.listing.currentItem()
            current_name = current.text() if current is not None else None
            # setSelected(True) can add a second object; prefer the new object.
            name = next((item.data(0) for item in selected
                         if item.data(0) != current_name), selected[0].data(0))
            for row in range(self.listing.count()):
                if self.listing.item(row).text() == name:
                    self.listing.setCurrentRow(row)
                    self.highlight_selection(row)
                    return

        def highlight_selection(self, row):
            """Change selection in place; never delete an active Qt event target."""
            name = (self.listing.item(row).text()
                    if 0 <= row < self.listing.count() else None)
            normal_pen = QPen(Qt.GlobalColor.darkGray, 0)
            selected_pen = QPen(Qt.GlobalColor.darkCyan, 2)
            with QSignalBlocker(self.scene):
                for item in self.scene.items():
                    selected = item.data(0) == name
                    item.setPen(selected_pen if selected else normal_pen)
                    item.setSelected(selected)

        def failure(self, error):
            self.report.setPlainText(f'No command committed. {type(error).__name__}: {error}')

        def execute(self):
            try:
                obj = strict_json(self.editor.toPlainText())
                self.session.execute_many(obj if isinstance(obj, list) else [obj])
                self.refresh()
                self.report.setPlainText('Committed. Undo restores the complete previous document.')
            except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
                self.failure(exc)

        def refresh(self):
            current = self.listing.currentItem()
            selected_name = current.text() if current is not None else None
            selected_row = self.listing.currentRow()
            with QSignalBlocker(self.listing):
                self.listing.clear()
                self.listing.addItems([n for n, _ in self.session.document.entities])
                if self.listing.count():
                    row = next((i for i in range(self.listing.count())
                                if self.listing.item(i).text() == selected_name), None)
                    if row is None:
                        row = max(0, min(selected_row, self.listing.count()-1))
                    self.listing.setCurrentRow(row)
            self.statusBar().showMessage(f'{len(self.session.document.entities)} objects | unit: {self.session.document.unit}')
            self.draw(self.listing.currentRow(), fit=True)

        def draw(self, row, fit=False):
            # Model edits rebuild items; selection callbacks must not run mid-clear.
            with QSignalBlocker(self.scene):
                self._rebuild_scene(row, fit)

        def _rebuild_scene(self, row, fit):
            self.scene.clear()
            entities = self.session.document.entities
            if not entities:
                return
            try:
                selected_name = (self.listing.item(row).text()
                                 if 0 <= row < self.listing.count() else None)
                projected_entities = []
                for name, entity in entities:
                    paths = wireframe(entity)
                    projected = [[(.8660254*(x-y), .5*(x+y)-z) for x, y, z in path]
                                  for path in paths if path]
                    if projected:
                        projected_entities.append((name, projected))
                values = [p for _, paths in projected_entities for path in paths for p in path]
                if not values:
                    return
                xmin, xmax = min(x for x, _ in values), max(x for x, _ in values)
                ymin, ymax = min(y for _, y in values), max(y for _, y in values)
                scale = max(xmax-xmin, ymax-ymin, 1e-100)
                # Normalize huge/small model coordinates for stable display only.
                normal_pen = QPen(Qt.GlobalColor.darkGray, 0)
                selected_pen = QPen(Qt.GlobalColor.darkCyan, 2)
                for name, paths in projected_entities:
                    pen = selected_pen if name == selected_name else normal_pen
                    for poly in paths:
                        path = QPainterPath()
                        for i, (x, y) in enumerate(poly):
                            xy = ((x-xmin)/scale*500, (y-ymin)/scale*500)
                            path.moveTo(*xy) if i == 0 else path.lineTo(*xy)
                        item = self.scene.addPath(path, pen)
                        item.setData(0, name)
                        item.setToolTip(name)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                self.highlight_selection(row)
                if fit:
                    self.fit_view()
            except (ValueError, ArithmeticError) as exc:
                self.report.setPlainText(f'Display failed; geometry preserved: {exc}')

        def fit_view(self):
            bounds = self.scene.itemsBoundingRect()
            if not bounds.isEmpty():
                self.view.fitInView(bounds.adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)

        def measure(self):
            row = self.listing.currentRow()
            if row < 0:
                return
            try:
                name, entity = self.session.document.entities[row]
                report = {'name': name, 'unit': self.session.document.unit, 'kind': entity.kind}
                if isinstance(entity, Curve):
                    value = entity.length()
                    report.update(length=value.value, estimated_error=value.estimated_error)
                else:
                    value = entity.area()
                    report.update(parameter_area=value.value, estimated_error=value.estimated_error,
                                  midpoint_differential=entity.differential(.5, .5))
                self.report.setPlainText(json.dumps(report, indent=2, allow_nan=False))
            except (ValueError, ArithmeticError) as exc:
                self.report.setPlainText(f'Measurement unavailable: {exc}')

        def delete_selected(self):
            row = self.listing.currentRow()
            if row < 0:
                return
            name = self.listing.item(row).text()
            try:
                self.session.execute({'op': 'delete', 'source': name})
                self.refresh()
                self.report.setPlainText(f'Deleted {name}. Undo restores the complete previous document.')
            except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
                self.failure(exc)

        def undo(self):
            self.session.undo()
            self.refresh()

        def redo(self):
            self.session.redo()
            self.refresh()

        def load_file(self):
            path, _ = QFileDialog.getOpenFileName(self, 'Open mesh-free document', '', 'Mesh-free JSON (*.json)')
            if not path:
                return
            try:
                candidate = ToolDocument.load(path)
                if self.session.document != ToolDocument() and QMessageBox.question(self, 'Replace workbench document?',
                    'Open replaces this workbench document. Unsaved changes are not saved automatically.') != QMessageBox.StandardButton.Yes:
                    return
                self.session = ToolSession(candidate)
                self.refresh()
            except (ValueError, OSError, TypeError) as exc:
                self.failure(exc)

        def save_file(self):
            path, _ = QFileDialog.getSaveFileName(self, 'Save mesh-free document', '', 'Mesh-free JSON (*.json)')
            if path:
                try:
                    self.session.document.save(path, overwrite=True)  # dialog confirms overwriting
                except (ValueError, OSError) as exc:
                    self.report.setPlainText(f'Save failed: {exc}')

    return Workbench()


def install_meshfree_tools(window):
    """Explicit opt-in menu bridge; retain one workbench per parent window."""
    from PySide6.QtGui import QAction
    if getattr(window, '_meshfree_action', None) is not None:
        return window._meshfree_action
    action = QAction('Mesh-free Tool Workbench', window)
    def show():
        if getattr(window, '_meshfree_window', None) is None:
            window._meshfree_window = create_workbench(window)
        window._meshfree_window.show()
        window._meshfree_window.raise_()
    action.triggered.connect(show)
    window.menuBar().addMenu('Mesh-free Tools').addAction(action)
    window._meshfree_action = action
    return action


def main():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        window = create_workbench()
        window.show()
        return app.exec()
    except (ImportError, RuntimeError) as exc:
        print(f'{exc}. Headless alternative: python -m examples.meshfree_toolkit_demo', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
