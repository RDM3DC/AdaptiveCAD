"""Inventor-inspired presentation layer over the existing modeling workbench.

Keeps the actual viewport, scene, listing, command editor, model session, and
metric dock. No geometry replacement, renderer rewrite, or shared history.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QTabWidget,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from adaptivecad.geom.meshfree_tools import Curve
from adaptivecad.geom.tool_document import entity_record
from adaptivecad.gui.workbench_commands import (
    CURVE_SOURCE,
    GROUPS,
    UNITS,
    command_defaults,
    field_kind,
    field_text,
    parse_field,
    validate_command,
)

STYLE = """
QMainWindow#AdaptiveCADModelWorkspace { background: #17212e; }
QWidget#ModelCanvas { background: #f1f4f8; }
QWidget#ModelCanvas QLabel { color: #283a50; }
QWidget#ModelRibbon, QWidget#ModelCanvasHeader { background: #223145; color: #edf3fb; }
QWidget#ModelCanvasHeader QLabel { color: #edf3fb; }
QWidget#ModelPanel { background: #202c3b; color: #e2ebf5; }
QWidget#ModelPanel QLabel { color: #c3d1e1; }
QWidget#ModelPanel QLineEdit, QWidget#ModelPanel QTextEdit,
QWidget#ModelPanel QPlainTextEdit, QWidget#ModelPanel QListWidget,
QWidget#ModelPanel QTreeWidget, QWidget#ModelPanel QComboBox {
    background: #17212e; color: #e2ebf5; border: 1px solid #41516a;
    border-radius: 4px; padding: 5px; selection-background-color: #276cab;
}
QWidget#ModelPanel QListWidget::item { padding: 7px; }
QWidget#ModelPanel QListWidget::item:selected { background: #276cab; color: white; }
QWidget#ModelPanel QPushButton, QWidget#ModelRibbon QToolButton {
    background: #30445d; color: #f1f6fc; border: 1px solid #4c6280;
    border-radius: 4px; padding: 7px;
}
QWidget#ModelPanel QPushButton:hover, QWidget#ModelRibbon QToolButton:hover { background: #386b96; }
QWidget#ModelPanel QPushButton:disabled, QWidget#ModelRibbon QToolButton:disabled { color: #91a0b3; background: #253549; }
QTabWidget#ModelRibbon::pane { border: 0; }
QTabWidget#ModelRibbon QTabBar::tab { background: #223145; color: #cad7e8; padding: 8px 20px; }
QTabWidget#ModelRibbon QTabBar::tab:selected { background: #30445d; color: white; border-bottom: 3px solid #64bdff; }
QDockWidget#ModelBrowser::title, QDockWidget#ModelInspector::title,
QDockWidget#ModelConsole::title { background: #293d54; color: white; padding: 7px; }
"""


def _panel():
    widget = QWidget()
    widget.setObjectName("ModelPanel")
    return widget


def _label(text):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class CommandDialog(QDialog):
    """One snapshot, visible units, real backend validation and one atomic commit."""

    def __init__(self, ui, label):
        super().__init__(ui.window)
        self.ui, self.label = ui, label
        self.session = ui.window.session
        self.snapshot = self.session.document
        self.defaults = command_defaults(label, self.snapshot, ui.selected_name())
        self.fields = {}
        self.setObjectName("ModelParameterDialog")
        self.setWindowTitle(label + " — model parameters")
        self.resize(590, 600)
        layout = QVBoxLayout(self)
        note = _label(
            f"Model unit: {self.snapshot.unit}  |  Angles: radians\n"
            "Creates a named snapshot; no automatic overwrite or live feature link. "
            "Surface operations create evaluated sheets, not watertight solids."
        )
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        for key, value in self.defaults.items():
            if key == "op":
                continue
            kind = field_kind(key, value)
            if kind in ("entity", "unit"):
                widget = QComboBox()
                if kind == "unit":
                    widget.addItems(UNITS)
                else:
                    curves_only = key != "source" or self.defaults["op"] in CURVE_SOURCE
                    widget.addItems(
                        [
                            n
                            for n, e in self.snapshot.entities
                            if not curves_only or isinstance(e, Curve)
                        ]
                    )
                widget.setCurrentIndex(widget.findText(str(value)))
            elif kind == "points":
                widget = QPlainTextEdit(field_text(kind, value))
                widget.setMaximumHeight(150)
                widget.setToolTip(
                    "One x, y, z control point per line; 1..32 points. No expressions."
                )
            else:
                widget = QLineEdit(field_text(kind, value))
                widget.setMaxLength(64000 if kind == "vector" else 128)
                if kind == "vector":
                    widget.setToolTip("Three comma-separated finite values: x, y, z")
            widget.setObjectName("model_param_" + key)
            title = key.replace("_", " ").capitalize()
            if key in ("angle", "sweep") or (key == "start" and self.defaults["op"] == "arc"):
                title += " [rad]"
            form.addRow(title, widget)
            self.fields[key] = (kind, widget)
        self.message = _label(
            "Validate checks a temporary session. Apply changes only the model history."
        )
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.validate_button = buttons.addButton(
            "Validate (no changes)", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.apply_button = buttons.addButton(
            "Apply to model", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.validate_button.clicked.connect(self.validate)
        self.apply_button.clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def command(self):
        if self.ui.window.session is not self.session or self.session.document is not self.snapshot:
            raise ValueError(
                "Model changed while this dialog was open. Close and reopen to refresh inputs."
            )
        command = {"op": self.defaults["op"]}
        for key, (kind, widget) in self.fields.items():
            text = (
                widget.currentText()
                if kind in ("entity", "unit")
                else widget.toPlainText()
                if kind == "points"
                else widget.text()
            )
            try:
                command[key] = parse_field(kind, text)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f"{key}: {exc}") from exc
        return command

    def validate(self):
        try:
            candidate = validate_command(self.snapshot, self.command())
            self.message.setText(
                f"Valid: {len(candidate.entities)} model objects; unit {candidate.unit}. No changes made."
            )
            return True
        except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
            self.message.setText(f"No changes made: {exc}")
            return False

    def apply(self):
        try:
            command = self.command()
            validate_command(self.snapshot, command)
            self.session.execute(command)
            self.ui.window.refresh()
            self.ui.window.report.setPlainText(
                f"Applied {self.label} to MODEL. Model Undo restores the previous snapshot.\n"
                "Metric project and metric history unchanged.\n" + json.dumps(command, indent=2)
            )
            self.ui.sync()
            self.accept()
        except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
            self.message.setText(f"No command committed: {exc}")


class WorkbenchUI(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.actions, self.docks = {}, {}
        self.dialog = None
        self.palette_dialog = None
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self.sync)
        self._build()
        window.listing.currentRowChanged.connect(self.sync)
        model = window.listing.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset):
            signal.connect(self.schedule_sync)
        window.report.textChanged.connect(self.show_results)
        self.sync()

    def schedule_sync(self, *args):
        self._sync_timer.start(0)

    def selected_name(self):
        item = self.window.listing.currentItem()
        return item.text() if item is not None else None

    def _action(self, key, title, callback, icon=QStyle.StandardPixmap.SP_FileIcon):
        action = QAction(self.window.style().standardIcon(icon), title, self)
        action.setObjectName("model_ui_" + key)
        action.setToolTip(title)
        action.triggered.connect(lambda checked=False: self.invoke(callback))
        self.actions[key] = action
        return action

    def invoke(self, callback):
        callback()
        self.sync()

    def _button(self, layout, action):
        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(button)
        return button

    def _dock(self, name, title, widget, area):
        dock = QDockWidget(title, self.window)
        dock.setObjectName(name)
        dock.setWidget(widget)
        self.window.addDockWidget(area, dock)
        self.docks[name] = dock
        return dock

    def _build(self):
        w = self.window
        w.setObjectName("AdaptiveCADModelWorkspace")
        w.setWindowTitle("AdaptiveCAD — Model workspace[*]")
        w.setStyleSheet(w.styleSheet() + STYLE)
        # Take ownership before replacing the central widget. Reparent only the
        # existing widgets; never destroy or regenerate an active graphics item.
        self.legacy = w.takeCentralWidget()
        self.legacy.setParent(w)
        self.legacy.hide()
        root = QWidget()
        root.setObjectName("ModelCanvas")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 6, 8, 6)
        header = QWidget()
        header.setObjectName("ModelCanvasHeader")
        head = QHBoxLayout(header)
        head.addWidget(_label("MODEL WORKSPACE  /  NATIVE CURVES + SHEETS"))
        head.addStretch()
        head.addWidget(_label("Isometric wireframe"))
        layout.addWidget(header)
        layout.addWidget(
            _label(
                "Select geometry or a browser item. Drag to pan. Display samples are not stored geometry."
            )
        )
        layout.addWidget(w.view, 1)
        w.view.setBackgroundBrush(QColor("#f1f4f8"))
        w.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w.setCentralWidget(root)
        browser = _panel()
        box = QVBoxLayout(browser)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter model objects…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.filter_objects)
        box.addWidget(self.filter)
        box.addWidget(w.listing, 1)
        box.addWidget(
            _label(
                "Browser filter only. Geometry stays visible.\nObjects are snapshots, not an associative feature tree."
            )
        )
        self._dock("ModelBrowser", "MODEL BROWSER", browser, Qt.DockWidgetArea.LeftDockWidgetArea)
        inspector = _panel()
        box = QVBoxLayout(inspector)
        self.selection_title = _label("Nothing selected")
        box.addWidget(self.selection_title)
        self.properties = QTreeWidget()
        self.properties.setHeaderLabels(["Property", "Value"])
        self.properties.setRootIsDecorated(False)
        self.properties.setAlternatingRowColors(False)
        box.addWidget(self.properties)
        box.addWidget(_label("Native definition • read only"))
        self.definition = QPlainTextEdit()
        self.definition.setReadOnly(True)
        self.definition.setMaximumHeight(210)
        box.addWidget(self.definition)
        box.addWidget(
            _label(
                "Use ribbon commands for named results. Metric measurements use the independent metric dock."
            )
        )
        self._dock(
            "ModelInspector",
            "SELECTION INSPECTOR",
            inspector,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        console = _panel()
        box = QVBoxLayout(console)
        self.console_tabs = QTabWidget()
        advanced = _panel()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.addWidget(
            _label(
                "Advanced model commands • strict JSON, no expression evaluation. Draft text is not saved model data."
            )
        )
        advanced_layout.addWidget(w.templates)
        advanced_layout.addWidget(w.editor)
        apply = QPushButton("Apply JSON / atomic batch to MODEL")
        apply.clicked.connect(lambda: self.invoke(w.execute))
        advanced_layout.addWidget(apply)
        self.console_tabs.addTab(w.report, "Model results")
        self.console_tabs.addTab(advanced, "Advanced commands")
        box.addWidget(self.console_tabs)
        self._dock(
            "ModelConsole",
            "MODEL RESULTS / COMMANDS",
            console,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )
        self._build_actions()
        self._build_ribbon()
        workspace = w.menuBar().addMenu("Workspace")
        for key in ("open", "save", "undo", "redo", "search"):
            workspace.addAction(self.actions[key])
        workspace.addSeparator()
        for dock in self.docks.values():
            workspace.addAction(dock.toggleViewAction())
        workspace.addSeparator()
        for key in ("reset_layout", "save_layout", "restore_layout"):
            workspace.addAction(self.actions[key])
        self.status = _label("")
        w.statusBar().addPermanentWidget(self.status)
        # Model-only keys: never steal text editor or metric-dock undo/delete.
        self.shortcuts = []
        for widget in (w.view, w.listing):
            for sequence, key in (
                ("Ctrl+Z", "undo"),
                ("Ctrl+Y", "redo"),
                ("Delete", "delete"),
                ("F", "fit"),
            ):
                shortcut = QShortcut(QKeySequence(sequence), widget)
                shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
                shortcut.activated.connect(self.actions[key].trigger)
                self.shortcuts.append(shortcut)
        search = QShortcut(QKeySequence("Ctrl+K"), w)
        search.activated.connect(self.command_palette)
        self.shortcuts.append(search)
        self.reset_layout()

    def _build_actions(self):
        w = self.window
        for key, title, callback, icon in (
            ("open", "Open model", w.load_file, QStyle.StandardPixmap.SP_DialogOpenButton),
            ("save", "Save model as", w.save_file, QStyle.StandardPixmap.SP_DialogSaveButton),
            ("undo", "Undo model", w.undo, QStyle.StandardPixmap.SP_ArrowBack),
            ("redo", "Redo model", w.redo, QStyle.StandardPixmap.SP_ArrowForward),
            ("fit", "Fit all", w.fit_view, QStyle.StandardPixmap.SP_TitleBarMaxButton),
            ("delete", "Delete selected", self.delete_selected, QStyle.StandardPixmap.SP_TrashIcon),
            (
                "measure",
                "Measure selected",
                w.measure,
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            (
                "search",
                "Find command  Ctrl+K",
                self.command_palette,
                QStyle.StandardPixmap.SP_FileDialogContentsView,
            ),
        ):
            self._action(key, title, callback, icon)
        for labels in GROUPS.values():
            for label in labels:
                self._action(label, label, lambda name=label: self.open_command(name))
        for key, title, callback in (
            ("zoom_in", "Zoom in", lambda: w.view.scale(1.25, 1.25)),
            ("zoom_out", "Zoom out", lambda: w.view.scale(0.8, 0.8)),
            ("metrics", "Metric workbench", self.show_metrics),
            ("console", "Advanced commands", self.show_console),
            ("reset_layout", "Reset layout", self.reset_layout),
            ("save_layout", "Save layout", self.save_layout),
            ("restore_layout", "Restore layout", self.restore_layout),
        ):
            self._action(key, title, callback)
        if hasattr(w, "_curve_transfer_action"):
            self.actions["transfer"] = w._curve_transfer_action
            self.actions["receipt"] = w._curve_transfer_receipt_action

    def _build_ribbon(self):
        ribbon = QTabWidget()
        ribbon.setObjectName("ModelRibbon")
        ribbon.setDocumentMode(True)
        tabs = {
            "Model": (
                "open",
                "save",
                "Line",
                "Bezier",
                "Circle / arc",
                "Extrude sheet",
                "Revolve sheet",
                "Ruled loft",
                "Translation sweep",
            ),
            "Modify": ("undo", "redo", *GROUPS["Modify"], "delete"),
            "Inspect": ("measure", "metrics", "transfer", "receipt", "Convert units"),
            "View": (
                "fit",
                "zoom_in",
                "zoom_out",
                "console",
                "reset_layout",
                "save_layout",
                "restore_layout",
                "search",
            ),
        }
        for title, keys in tabs.items():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            page = QWidget()
            page.setObjectName("ModelRibbon")
            row = QHBoxLayout(page)
            for key in keys:
                if key in self.actions:
                    self._button(row, self.actions[key])
            row.addStretch()
            scroll.setWidget(page)
            ribbon.addTab(scroll, title)
        ribbon.setFixedHeight(105)
        toolbar = QToolBar("Model ribbon", self.window)
        toolbar.setObjectName("ModelRibbonToolbar")
        toolbar.setMovable(False)
        toolbar.addWidget(ribbon)
        self.window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.ribbon, self.toolbar = ribbon, toolbar

    def sync(self, *args):
        w, name = self.window, self.selected_name()
        doc = w.session.document
        self.actions["undo"].setEnabled(bool(w.session._undo))
        self.actions["redo"].setEnabled(bool(w.session._redo))
        for key in ("measure", "delete"):
            self.actions[key].setEnabled(name is not None)
        self.status.setText(
            f"MODEL: {len(doc.entities)} objects  |  {doc.unit}  |  "
            f"{'Modified' if w.has_unsaved_changes else 'Saved snapshot'}  |  Metric file/history separate"
        )
        self.selection_title.setText(name or "Nothing selected")
        self.properties.clear()
        self.definition.clear()
        if name is not None:
            entity = doc.get(name)
            fields = [
                ("Name", name),
                ("Unit", doc.unit),
                ("Kind", entity.kind),
                (
                    "Representation",
                    "Native curve" if isinstance(entity, Curve) else "Evaluated sheet",
                ),
            ]
            if isinstance(entity, Curve):
                fields.extend(
                    [
                        ("Stored vectors / controls", str(len(entity.points))),
                        ("Parameter interval", str(entity.interval)),
                    ]
                )
            else:
                fields.append(("Solid status", "Sheet only; not certified watertight"))
            for key, value in fields:
                QTreeWidgetItem(self.properties, [key, str(value)])
            self.properties.resizeColumnToContents(0)
            self.definition.setPlainText(
                json.dumps(entity_record(entity), indent=2, allow_nan=False)
            )
        self.filter_objects()

    def filter_objects(self, *args):
        needle = self.filter.text().casefold()
        for i in range(self.window.listing.count()):
            item = self.window.listing.item(i)
            item.setHidden(needle not in item.text().casefold())

    def delete_selected(self):
        name = self.selected_name()
        if (
            name is not None
            and QMessageBox.question(
                self.window,
                "Delete model object",
                f"Delete '{name}' from the model? Model Undo restores it.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.window.delete_selected()

    def open_command(self, label):
        if self.dialog is not None:
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        dialog = CommandDialog(self, label)
        self.dialog = dialog

        def finished(result):
            self.dialog = None
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.open()

    def show_results(self):
        if self.window.report.toPlainText():
            self.console_tabs.setCurrentIndex(0)
            self.docks["ModelConsole"].show()
            self.docks["ModelConsole"].raise_()

    def show_console(self):
        self.console_tabs.setCurrentIndex(1)
        self.docks["ModelConsole"].show()
        self.docks["ModelConsole"].raise_()

    def show_metrics(self):
        dock = getattr(self.window, "_curve_transfer_target", None)
        if dock is not None:
            dock.show()
            dock.raise_()

    def reset_layout(self):
        for name, area in (
            ("ModelBrowser", Qt.DockWidgetArea.LeftDockWidgetArea),
            ("ModelInspector", Qt.DockWidgetArea.RightDockWidgetArea),
            ("ModelConsole", Qt.DockWidgetArea.BottomDockWidgetArea),
        ):
            dock = self.docks[name]
            dock.setFloating(False)
            self.window.addDockWidget(area, dock)
            dock.setVisible(name != "ModelConsole")
        self.window.resizeDocks(
            [self.docks["ModelBrowser"], self.docks["ModelInspector"]],
            [245, 325],
            Qt.Orientation.Horizontal,
        )
        self.window.resizeDocks([self.docks["ModelConsole"]], [230], Qt.Orientation.Vertical)
        self.toolbar.show()
        self.ribbon.setCurrentIndex(0)

    def save_layout(self):
        settings = QSettings("AdaptiveCAD", "ModelWorkspace")
        settings.setValue("dockStateV1", self.window.saveState(1))
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            self.window.report.setPlainText(
                "Could not save UI layout preferences. Model unchanged."
            )
        else:
            self.window.statusBar().showMessage(
                "UI layout saved. No model or metric data written.", 6000
            )

    def restore_layout(self):
        settings = QSettings("AdaptiveCAD", "ModelWorkspace")
        state = settings.value("dockStateV1")
        if state is None or not self.window.restoreState(state, 1):
            self.window.statusBar().showMessage(
                "No compatible saved layout. Use Reset layout.", 6000
            )

    def command_palette(self):
        if self.palette_dialog is not None:
            self.palette_dialog.raise_()
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Find AdaptiveCAD command")
        dialog.resize(560, 480)
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText("Type a command: extrude, metric, fit, save…")
        listing = QListWidget()
        layout.addWidget(search)
        layout.addWidget(listing)
        entries = [(key, action) for key, action in self.actions.items() if key != "search"]

        def update(text):
            listing.clear()
            for key, action in entries:
                if text.casefold() in action.text().casefold() and action.isEnabled():
                    listing.addItem(action.text())
                    listing.item(listing.count() - 1).setData(Qt.ItemDataRole.UserRole, key)
            listing.setCurrentRow(0 if listing.count() else -1)

        def run(*args):
            item = listing.currentItem()
            if item is not None:
                action = self.actions[item.data(Qt.ItemDataRole.UserRole)]
                dialog.accept()
                if action.isEnabled():
                    action.trigger()

        search.textChanged.connect(update)
        search.returnPressed.connect(run)
        listing.itemActivated.connect(run)
        self.palette_dialog = dialog

        def finished(result):
            self.palette_dialog = None
            dialog.deleteLater()

        dialog.finished.connect(finished)
        update("")
        dialog.open()
        search.setFocus()


def install_workbench_ui(window):
    """Idempotent; call only on an existing mesh-free model window after transfer install."""
    existing = getattr(window, "_workbench_ui", None)
    if existing is not None:
        return existing
    ui = WorkbenchUI(window)
    window._workbench_ui = ui
    return ui
