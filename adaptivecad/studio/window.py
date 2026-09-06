"""Inventor-inspired native desktop workspace, backed by AdaptiveCAD's analytic scene.

This is a new application shell, not a replacement for the geometry kernel.
Legacy launchers remain available. Unsupported modelling tools are explicitly disabled.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDockWidget, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QTabWidget, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .backend import make_viewport
from .document import (
    History, KINDS, UNIT_MM, atomic_write, dumps, extrude_rectangle, find_body,
    find_sketch, new_body, new_document, new_sketch, uid, validate,
)
from .sketch import SketchCanvas
from .svg_export import export_sketch
from .theme import stylesheet
from .widgets import CommandPalette, OrientationControl, Ribbon, icon

ROLE = Qt.ItemDataRole.UserRole


class DocumentTab(QWidget):
    def __init__(self, history, window):
        super().__init__(window)
        self.history = history
        self.recovery_id = uid()
        self.selection = None  # (body, id), (sketch, id), or (entity, sketch_id, entity_id)
        self.active_sketch = None
        self.is_sketch = False
        self.canvas = SketchCanvas(self)
        self.breadcrumb = QLabel(); self.breadcrumb.setObjectName("breadcrumb")
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        layout.addWidget(self.breadcrumb)
        self.error_banner = QLabel(); self.error_banner.setWordWrap(True); self.error_banner.hide()
        self.error_banner.setStyleSheet("background: #5d3030; color: #fff0e7; padding: 8px;")
        layout.addWidget(self.error_banner)
        self.stack = QStackedWidget(); layout.addWidget(self.stack)
        host = QWidget(); grid = QGridLayout(host); grid.setContentsMargins(0,0,0,0)
        self.render_error = ""
        try:
            self.viewport = make_viewport(host, window.safe_mode)
        except Exception as exc:
            self.viewport = make_viewport(host, True)
            self.render_error = str(exc)
            self.viewport.setText("3D RENDERER UNAVAILABLE\n\n" + str(exc) + "\n\nInstall the Studio dependencies and check your OpenGL driver.\nDocuments and 2D sketching remain available.")
        grid.addWidget(self.viewport,0,0)
        self.orientation = OrientationControl(host)
        grid.addWidget(self.orientation,0,0,Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.orientation.requested.connect(window.set_view)
        self.orientation.setVisible(hasattr(self.viewport,"set_document"))
        self.stack.addWidget(host); self.stack.addWidget(self.canvas)
        self.canvas.entityCreated.connect(lambda entity: window.add_entity(self, entity))
        self.canvas.entitySelected.connect(lambda identifier: window.select_entity(self, identifier))
        self.canvas.message.connect(window.log)
        self.canvas.cursorMoved.connect(lambda x,y: window.cursor_position(self, x,y))
        if hasattr(self.viewport,"picked"):
            self.viewport.picked.connect(lambda index: window.select_rendered(self, index))
            self.viewport.contextRequested.connect(window.context_menu)
            self.viewport.renderFailed.connect(lambda msg: self.report_render_error(window, msg))


    def report_render_error(self, window, message):
        self.error_banner.setText("Renderer error: " + message + " — try --safe-mode to keep editing documents and sketches.")
        self.error_banner.show()
        window.log("Renderer: " + message)


class StudioWindow(QMainWindow):
    def __init__(self, *, safe_mode=False, settings=None, recovery_dir=None):
        super().__init__()
        self.safe_mode = safe_mode
        self.settings = settings or QSettings("AdaptiveCAD", "Studio")
        self.dark = str(self.settings.value("dark", "true")).lower() == "true"
        self.recovery_dir = Path(recovery_dir) if recovery_dir else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/"studio-recovery"
        self._refreshing = False
        self._part_number = 0
        self.actions = {}
        self.setWindowTitle("AdaptiveCAD Studio")
        self.setMinimumSize(900,560)
        available = self.screen().availableGeometry()
        self.resize(min(1500,max(900,available.width()-40)), min(920,max(560,available.height()-60)))
        self.setAcceptDrops(True)
        self._make_actions()
        self._make_ui()
        self._make_docks()
        self._make_menus()
        self.setStyleSheet(stylesheet(self.dark))
        geometry = self.settings.value("geometry")
        state = self.settings.value("layout")
        if geometry is not None: self.restoreGeometry(geometry)
        if state is not None: self.restoreState(state,1)
        elif self.height()<760:
            self.history_dock.hide(); self.messages_dock.hide()
        self.new_document()
        self.recovery_timer = QTimer(self)
        self.recovery_timer.timeout.connect(self.write_recovery)
        self.recovery_timer.start(60000)

    @property
    def tab(self):
        return self.tabs.currentWidget()

    def log(self, message):
        self.messages.appendPlainText(str(message))
        self.statusBar().showMessage(str(message),8000)

    def guarded(self, call):
        try:
            return call()
        except Exception as exc:
            self.log(str(exc))
            QMessageBox.warning(self,"AdaptiveCAD Studio",str(exc))
            return None

    def action(self, key, title, callback, shortcut=None, hint="", checkable=False):
        act = QAction(icon(key),title,self)
        act.setObjectName("studio." + key)
        act.setToolTip(hint or title)
        act.setCheckable(checkable)
        if shortcut: act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(lambda checked=False: self.guarded(callback))
        self.addAction(act); self.actions[key]=act
        return act

    def _make_actions(self):
        self.action("new","New part",self.new_document,"Ctrl+N")
        self.action("open","Open",self.open_dialog,"Ctrl+O","Open a native .acstudio document")
        self.action("save","Save",self.save_document,"Ctrl+S")
        self.action("save_as","Save as",lambda: self.save_document(save_as=True),"Ctrl+Shift+S")
        self.action("undo","Undo",self.undo,"Ctrl+Z")
        self.action("redo","Redo",self.redo,"Ctrl+Y")
        self.action("duplicate","Duplicate",self.duplicate,"Ctrl+D")
        self.action("delete","Delete",self.delete_selected,"Delete")
        self.action("rename","Rename",self.rename_selected,"F2")
        self.action("suppress","Suppress / enable",self.toggle_suppressed,hint="Suppression removes the operand from ordered CSG evaluation; it is not display-only hiding.")
        self.action("earlier","Move earlier",lambda:self.reorder(-1))
        self.action("later","Move later",lambda:self.reorder(1))
        for kind in KINDS:
            self.action(kind,kind,lambda k=kind:self.add_body(k))
        self.action("sketch","New sketch",self.create_sketch,"Ctrl+Shift+K","Create a curve-native XY sketch")
        self.action("edit_sketch","Edit sketch",self.edit_sketch)
        self.action("finish","Finish sketch",self.finish_sketch)
        for tool in ("line","rectangle","circle","bezier"):
            self.action(tool,tool.title(),lambda t=tool:self.sketch_tool(t))
        self.action("select","Select",lambda:self.sketch_tool("select"))
        self.action("extrude","Extrude rectangle",self.extrude,hint="Create an independent analytic box from the selected XY rectangle. Not associative; general profiles are not supported here.")
        for key,title,op in (("join","Join","solid"),("cut","Cut","subtract"),("intersect","Intersect","intersect")):
            self.action(key,title,lambda value=op:self.set_operation(value),hint="Set the selected operand's operation against ALL preceding enabled operands (ordered CSG).")
        for key,title in (("move","Move"),("rotate","Rotate"),("scale","Scale")):
            self.action(key,title,lambda field=key:self.focus_transform(field),hint="Edit placement numerically in Properties; Apply commits an undoable edit.")
        for key,title in (("revolve","Revolve"),("loft","Loft"),("fillet","Fillet"),("constraints","Constraints"),("step","STEP export")):
            act=self.action(key,title,lambda:None,hint="Not implemented in the Studio analytic document backend. Use the legacy solid tools where available.")
            act.setEnabled(False)
        self.action("fit","Fit",lambda:self.set_view("Fit"),"F")
        for view in ("Iso","Top","Front","Right"):
            self.action(view,view,lambda v=view:self.set_view(v))
        self.action("grid","Sketch grid",lambda:self.toggle_canvas("grid"),checkable=True)
        self.action("snap","Sketch snap",lambda:self.toggle_canvas("snap"),"F9",checkable=True)
        self.action("ortho","Sketch ortho",lambda:self.toggle_canvas("ortho"),"F8",checkable=True)
        self.action("dimensions","Readout dimensions",lambda:self.toggle_canvas("dimensions"),checkable=True)
        self.action("svg","Export sketch SVG",self.export_svg)
        self.action("snapshot","Save PNG",self.save_snapshot,hint="Capture the current workspace as a PNG preview, not CAD geometry.")
        self.action("validate","Validate document",self.validate_document)
        self.action("measure","Origin distance",self.measure_origins,hint="Measure between two body placement origins, not face-to-face clearance.")
        self.action("definition","Source definition",self.show_definition)
        self.action("search","Command search",self.command_search,"Ctrl+K")
        self.action("theme","Light / dark",self.toggle_theme)
        self.action("layout","Reset layout",self.reset_layout)
        self.action("legacy","Legacy Playground",self.launch_legacy)
        self.action("help","Studio guide",self.open_guide,"F1")
        self.action("demo","Bearing demo",self.add_demo)

    def _make_ui(self):
        quick=QToolBar("Quick access",self); quick.setObjectName("studioQuickAccess"); quick.setMovable(False)
        self.addToolBar(quick)
        brand=QLabel("ADAPTIVECAD  /  STUDIO"); brand.setObjectName("brand"); quick.addWidget(brand)
        for key in ("new","open","save","undo","redo"): quick.addAction(self.actions[key])
        spacer=QWidget(); from PySide6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred); quick.addWidget(spacer)
        quick.addAction(self.actions["search"]); quick.addAction(self.actions["theme"])
        central=QWidget(); layout=QVBoxLayout(central); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        self.ribbon=Ribbon()
        def group(name,keys): return name,[self.actions[k] for k in keys]
        self.ribbon.add_page("3D Model",[
            group("Create",["Box","Sphere","Capsule","Torus"]),group("Sketch",["sketch","extrude"]),
            group("Modify",["move","rotate","scale","duplicate"]),group("Combine (ordered CSG)",["join","cut","intersect"]),
            group("Solid backend needed",["revolve","loft","fillet"])])
        self.ribbon.add_page("Sketch",[
            group("Sketch",["sketch","edit_sketch","finish"]),group("Draw",["select","line","rectangle","circle","bezier"]),
            group("Precision",["snap","ortho","dimensions"]),group("Output",["extrude","svg"]),group("Solver needed",["constraints"])])
        self.ribbon.add_page("Inspect",[group("Inspect",["measure","validate","definition"]),group("Capture",["snapshot","svg","step"])])
        self.ribbon.add_page("View",[group("Orient",["Iso","Top","Front","Right","fit"]),group("Workspace",["grid","theme","layout"])])
        self.ribbon.add_page("Tools",[group("Analytic shapes",["Superellipsoid","Mobius","Pi bloom"]),group("Resources",["demo","legacy","help"])])
        layout.addWidget(self.ribbon)
        self.tabs=QTabWidget(); self.tabs.setObjectName("documentTabs"); self.tabs.setDocumentMode(True); self.tabs.setTabsClosable(True); self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(lambda _:self.refresh())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs,1); self.setCentralWidget(central)
        self.selection_status=QLabel("Ready"); self.unit_status=QLabel("mm"); self.coordinate_status=QLabel("")
        self.statusBar().addWidget(self.selection_status,1)
        self.statusBar().addPermanentWidget(self.coordinate_status)
        self.statusBar().addPermanentWidget(self.unit_status)

    def _dock(self,title,name,widget,area):
        dock=QDockWidget(title,self); dock.setObjectName(name); dock.setWidget(widget)
        self.addDockWidget(area,dock)
        return dock

    def _make_docks(self):
        browser=QWidget(); box=QVBoxLayout(browser); box.setContentsMargins(6,6,6,6)
        self.filter=QLineEdit(); self.filter.setPlaceholderText("Filter model browser…"); self.filter.textChanged.connect(self.filter_tree)
        box.addWidget(self.filter)
        self.tree=QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.setIndentation(17)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda pos:self.context_menu(self.tree.viewport().mapToGlobal(pos)))
        self.tree.itemSelectionChanged.connect(self.tree_selected)
        self.tree.itemChanged.connect(self.tree_changed)
        self.tree.itemDoubleClicked.connect(lambda item,col:self.guarded(self.edit_sketch) if item.data(0,ROLE) and item.data(0,ROLE)[0] in ("sketch","entity") else None)
        box.addWidget(self.tree)
        self.browser_dock=self._dock("Model browser","studioBrowser",browser,Qt.DockWidgetArea.LeftDockWidgetArea)
        self.browser_dock.setMinimumWidth(210)
        self.inspector=QScrollArea(); self.inspector.setWidgetResizable(True); self.inspector.setMinimumWidth(260)
        self.properties_dock=self._dock("Properties","studioProperties",self.inspector,Qt.DockWidgetArea.RightDockWidgetArea)
        self.history_list=QListWidget()
        self.history_dock=self._dock("Undo history","studioHistory",self.history_list,Qt.DockWidgetArea.BottomDockWidgetArea)
        self.messages=QPlainTextEdit(); self.messages.setReadOnly(True); self.messages.setMaximumBlockCount(1000)
        self.messages_dock=self._dock("Messages","studioMessages",self.messages,Qt.DockWidgetArea.BottomDockWidgetArea)
        self.tabifyDockWidget(self.history_dock,self.messages_dock); self.history_dock.raise_()
        self.resizeDocks([self.browser_dock,self.properties_dock],[235,290],Qt.Orientation.Horizontal)
        self.resizeDocks([self.history_dock],[125],Qt.Orientation.Vertical)

    def _make_menus(self):
        file=self.menuBar().addMenu("&File")
        for key in ("new","open","save","save_as","svg","snapshot"): file.addAction(self.actions[key])
        self.recent=file.addMenu("Recent documents"); self.recent.aboutToShow.connect(self.rebuild_recent)
        file.addSeparator(); file.addAction("Exit",self.close)
        edit=self.menuBar().addMenu("&Edit")
        for key in ("undo","redo","rename","duplicate","delete","suppress","earlier","later"): edit.addAction(self.actions[key])
        view=self.menuBar().addMenu("&Window")
        for dock in (self.browser_dock,self.properties_dock,self.history_dock,self.messages_dock): view.addAction(dock.toggleViewAction())
        view.addAction(self.actions["layout"]); view.addAction(self.actions["theme"])
        help_menu=self.menuBar().addMenu("&Help"); help_menu.addAction(self.actions["help"]); help_menu.addAction(self.actions["legacy"])

    def new_document(self):
        self._part_number += 1
        return self.add_tab(History(new_document(f"Part {self._part_number}")))

    def add_tab(self,history):
        tab=DocumentTab(history,self)
        index=self.tabs.addTab(tab,history.document["name"]); self.tabs.setCurrentIndex(index)
        self.refresh()
        if hasattr(tab.viewport,"fit_document"):
            tab.viewport.fit_document(history.document); tab.viewport.set_orientation("Iso")
        if tab.render_error: self.log("Renderer unavailable: " + tab.render_error)
        return tab

    def transaction(self,label,edit,tab=None):
        tab=tab or self.tab
        if tab is None: return
        try:
            changed=tab.history.execute(label,edit)
        except Exception:
            self.refresh(); raise
        if changed:
            self.refresh(); self.log(label)

    def refresh(self):
        if not hasattr(self,"tree") or self.tab is None or self._refreshing: return
        self._refreshing=True
        try:
            tab=self.tab; doc=tab.history.document
            if tab.active_sketch and not any(s["id"]==tab.active_sketch for s in doc["sketches"]):
                tab.active_sketch=None; tab.is_sketch=False
            valid_keys={("body",b["id"]) for b in doc["bodies"]} | {("sketch",s["id"]) for s in doc["sketches"]}
            valid_keys |= {("entity",s["id"],e["id"]) for s in doc["sketches"] for e in s["entities"]}
            if tab.selection not in valid_keys: tab.selection=None
            for i in range(self.tabs.count()):
                other=self.tabs.widget(i)
                title=other.history.path.stem if other.history.path else other.history.document["name"]
                self.tabs.setTabText(i,title+(" *" if other.history.dirty else ""))
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex())+" — AdaptiveCAD Studio")
            self.tree.clear()
            root=QTreeWidgetItem(self.tree,[doc["name"]]); root.setExpanded(True)
            origin=QTreeWidgetItem(root,["Origin / work planes"])
            for plane in ("XY","XZ","YZ"): QTreeWidgetItem(origin,[plane+" plane"])
            bodies=QTreeWidgetItem(root,[f"Bodies ({len(doc['bodies'])}) — ordered CSG"]); bodies.setExpanded(True)
            for index,b in enumerate(doc["bodies"]):
                word={"solid":"Join","subtract":"Cut","intersect":"Intersect"}[b["operation"]]
                item=QTreeWidgetItem(bodies,[f"{index+1:02d}  {b['name']}  ·  {word}"])
                key=("body",b["id"]); item.setData(0,ROLE,key); item.setIcon(0,icon(b["kind"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0,Qt.CheckState.Checked if b["enabled"] else Qt.CheckState.Unchecked)
                item.setToolTip(0,"Checked = included in CSG. Unchecked = suppressed, changing evaluated geometry.")
                if tab.selection==key: item.setSelected(True)
            sketches=QTreeWidgetItem(root,[f"Sketches ({len(doc['sketches'])})"]); sketches.setExpanded(True)
            for s in doc["sketches"]:
                item=QTreeWidgetItem(sketches,[s["name"]+" · XY"]); key=("sketch",s["id"])
                item.setData(0,ROLE,key); item.setIcon(0,icon("sketch")); item.setExpanded(s["id"]==tab.active_sketch)
                if tab.selection==key: item.setSelected(True)
                for i,e in enumerate(s["entities"]):
                    child=QTreeWidgetItem(item,[f"{e['kind'].title()} {i+1}"]); key=("entity",s["id"],e["id"])
                    child.setData(0,ROLE,key); child.setIcon(0,icon(e["kind"]))
                    if tab.selection==key: child.setSelected(True)
            self.filter_tree(self.filter.text())
            if hasattr(tab.viewport,"set_document"):
                tab.viewport.set_document(doc)
                selected=tab.selection[1] if tab.selection and tab.selection[0]=="body" else None
                tab.viewport.selected_index=tab.viewport.render_ids.index(selected) if selected in tab.viewport.render_ids else -1
                tab.viewport.scene.bg_color[:]=[.08,.105,.14] if self.dark else [.80,.85,.91]
            tab.canvas.dark=self.dark
            if tab.active_sketch:
                sketch=find_sketch(doc,tab.active_sketch)
                selected=tab.selection[2] if tab.selection and tab.selection[0]=="entity" and tab.selection[1]==tab.active_sketch else ""
                tab.canvas.set_entities(sketch["entities"],selected,doc["units"])
            else:
                tab.canvas.set_entities([],units=doc["units"])
            tab.stack.setCurrentIndex(1 if tab.is_sketch else 0)
            tab.breadcrumb.setText(f"{doc['name']}   /   {'XY sketch' if tab.is_sketch else 'Analytic model'}   /   {doc['units']}   /   Curve-native source")
            self.build_inspector()
            self.history_list.clear()
            for i,(label,_,_) in enumerate(tab.history.entries):
                self.history_list.addItem(("[redo] " if i>=tab.history.index else "") + label)
            if tab.history.index: self.history_list.setCurrentRow(tab.history.index-1)
            self.selection_status.setText(f"{sum(b['enabled'] for b in doc['bodies'])}/48 enabled bodies   |   {len(doc['sketches'])} sketches")
            self.unit_status.setText("  " + doc["units"] + "  ")
            self.update_actions()
        finally:
            self._refreshing=False

    def update_actions(self):
        tab=self.tab; sel=tab.selection; doc=tab.history.document
        body=bool(sel and sel[0]=="body")
        sketch=bool(sel and sel[0] in ("sketch","entity"))
        entity=bool(sel and sel[0]=="entity")
        self.actions["undo"].setEnabled(tab.history.index>0)
        self.actions["redo"].setEnabled(tab.history.index<len(tab.history.entries))
        for key in ("duplicate","delete","definition"): self.actions[key].setEnabled(bool(sel))
        self.actions["rename"].setEnabled(bool(sel and not entity))
        for key in ("suppress","earlier","later","join","cut","intersect","move","rotate","scale"): self.actions[key].setEnabled(body)
        for key in ("line","rectangle","circle","bezier","select","grid","snap","ortho","dimensions","finish"): self.actions[key].setEnabled(tab.is_sketch)
        for key in ("grid","snap","ortho","dimensions"):
            self.actions[key].setChecked(getattr(tab.canvas,key))
        self.actions["edit_sketch"].setEnabled(sketch)
        self.actions["svg"].setEnabled(sketch or tab.active_sketch is not None)
        self.actions["measure"].setEnabled(len(doc["bodies"])>=2)
        rectangular=False
        if entity:
            s=find_sketch(doc,sel[1]); rectangular=next(e for e in s["entities"] if e["id"]==sel[2])["kind"]=="rectangle"
        self.actions["extrude"].setEnabled(rectangular)
        for key in ("Iso","Top","Front","Right"):
            self.actions[key].setEnabled(not tab.is_sketch and hasattr(tab.viewport,"set_orientation"))

    def filter_tree(self,text):
        def visit(item):
            own=text.casefold() in item.text(0).casefold()
            child_match=False
            for i in range(item.childCount()): child_match=visit(item.child(i)) or child_match
            show=own or child_match or not text
            item.setHidden(not show)
            if text and child_match: item.setExpanded(True)
            return show
        for i in range(self.tree.topLevelItemCount()): visit(self.tree.topLevelItem(i))

    def tree_selected(self):
        if self._refreshing or self.tab is None: return
        items=self.tree.selectedItems()
        self.tab.selection=tuple(items[0].data(0,ROLE)) if items and items[0].data(0,ROLE) else None
        if self.tab.selection and self.tab.selection[0] in ("sketch","entity"):
            self.tab.active_sketch=self.tab.selection[1]
        self.refresh()

    def tree_changed(self,item,column):
        if self._refreshing or self.tab is None: return
        key=item.data(0,ROLE)
        if key and key[0]=="body":
            value=item.checkState(0)==Qt.CheckState.Checked
            self.guarded(lambda:self.transaction("Change suppression",lambda d:find_body(d,key[1]).update(enabled=value)))

    def select_rendered(self,tab,index):
        if tab is not self.tab: return
        ids=tab.viewport.render_ids
        tab.selection=("body",ids[index]) if 0<=index<len(ids) else None
        self.refresh()

    def select_entity(self,tab,identifier):
        if tab is not self.tab: return
        tab.selection=("entity",tab.active_sketch,identifier) if identifier else ("sketch",tab.active_sketch)
        self.refresh()

    def context_menu(self,position):
        menu=QMenu(self)
        for key in ("edit_sketch","rename","duplicate","suppress","earlier","later","delete","fit"):
            menu.addAction(self.actions[key])
        menu.exec(position)

    def _spin(self,value,unit=1.,low=-1e6,high=1e6):
        spin=QDoubleSpinBox(); spin.setDecimals(8); spin.setRange(low/unit,high/unit)
        spin.setValue(value/unit); spin.setKeyboardTracking(False)
        spin.setSingleStep(max(.00000001,1./unit))
        return spin

    def build_inspector(self):
        host=QWidget(); outer=QVBoxLayout(host); outer.setContentsMargins(12,8,12,12)
        self.inspector_fields={}; self.transform_focus={}
        doc=self.tab.history.document; sel=self.tab.selection; unit=UNIT_MM[doc["units"]]
        title=QLabel("Document" if not sel else sel[0].title()); title.setObjectName("inspectorTitle"); outer.addWidget(title)
        form=QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow); outer.addLayout(form)
        def note(message):
            label=QLabel(message); label.setObjectName("hint"); label.setWordWrap(True); outer.addWidget(label)
        def field(key,index,value,label,length=False,low=-1e6,high=1e6):
            conversion=unit if length else 1.
            spin=self._spin(value,conversion,low,high)
            spin.setObjectName(f"property.{key}.{index}")
            form.addRow(label,spin)
            # Retain the original exact value when a rounded display field is untouched.
            self.inspector_fields[(key,index)]=(spin,spin.value(),conversion)
            return spin
        if not sel:
            self.property_name=QLineEdit(doc["name"]); form.addRow("Name",self.property_name)
            combo=QComboBox(); combo.addItems(list(UNIT_MM)); combo.setCurrentText(doc["units"])
            form.addRow("Display units",combo)
            combo.currentTextChanged.connect(lambda value:self.guarded(lambda:self.transaction("Change display units",lambda d:d.update(units=value))))
            note("Lengths are stored in millimetres. Display units do not change geometry. Select a body or sketch to edit its definition.")
            apply=QPushButton("Apply document name"); apply.setObjectName("primary")
            apply.clicked.connect(lambda:self.guarded(lambda:self.transaction("Rename document",lambda d:d.update(name=self.property_name.text().strip()))))
            outer.addWidget(apply)
        elif sel[0]=="body":
            body=find_body(doc,sel[1]); self.property_name=QLineEdit(body["name"]); form.addRow("Name",self.property_name)
            form.addRow("Primitive",QLabel(body["kind"]))
            self.property_operation=QComboBox()
            for label,op in (("Join preceding result","solid"),("Cut preceding result","subtract"),("Intersect preceding result","intersect")):
                self.property_operation.addItem(label,op)
            self.property_operation.setCurrentIndex(self.property_operation.findData(body["operation"]))
            form.addRow("Operation",self.property_operation)
            labels=KINDS[body["kind"]][1]; lengths=KINDS[body["kind"]][3]
            for i,label in enumerate(labels): field("params",i,body["params"][i],label+(" ("+doc["units"]+")" if i in lengths else ""),i in lengths)
            for key,label,short in (("position","Placement","move"),("rotation","Rotation","rotate"),("scale","Scale","scale")):
                for i,axis in enumerate("XYZ"):
                    spin=field(key,i,body[key][i],f"{label} {axis}"+(" (deg)" if key=="rotation" else ""),key=="position",.001 if key=="scale" else -10000,100 if key=="scale" else 10000)
                    if i==0: self.transform_focus[short]=spin
            color=QPushButton("Body appearance…"); color.clicked.connect(lambda:self.guarded(self.choose_color)); outer.addWidget(color)
            note("Join / Cut / Intersect act on the entire preceding CSG result. Parameters and placements commit together with Apply.")
            apply=QPushButton("Apply parameters"); apply.setObjectName("primary"); apply.clicked.connect(lambda:self.guarded(self.apply_properties)); outer.addWidget(apply)
        elif sel[0]=="sketch":
            sketch=find_sketch(doc,sel[1]); self.property_name=QLineEdit(sketch["name"])
            form.addRow("Name",self.property_name); form.addRow("Plane",QLabel("XY")); form.addRow("Entities",QLabel(str(len(sketch["entities"]))))
            edit=QPushButton("Edit sketch"); edit.setObjectName("primary"); edit.clicked.connect(lambda:self.guarded(self.edit_sketch)); outer.addWidget(edit)
            apply=QPushButton("Apply name"); apply.clicked.connect(lambda:self.guarded(self.apply_properties)); outer.addWidget(apply)
            note("Line, circle, rectangle and cubic Bezier definitions. Dimensional readouts are not constraint-solver dimensions.")
        else:
            entity=self.selected_record(); form.addRow("Entity",QLabel(entity["kind"].title()))
            for i,point in enumerate(entity["points"]):
                for axis,value in enumerate(point): field("point",i*2+axis,value,f"P{i+1} {'XY'[axis]} ({doc['units']})",True)
            apply=QPushButton("Apply defining points"); apply.setObjectName("primary"); apply.clicked.connect(lambda:self.guarded(self.apply_properties)); outer.addWidget(apply)
            if entity["kind"]=="rectangle":
                extrude=QPushButton("Extrude rectangle…"); extrude.clicked.connect(lambda:self.guarded(self.extrude)); outer.addWidget(extrude)
            note("Curves stay analytic in the saved document and SVG. Bezier points are control points, not polyline vertices.")
        outer.addStretch()
        old=self.inspector.takeWidget()
        if old: old.deleteLater()
        self.inspector.setWidget(host)

    def selected_record(self):
        doc=self.tab.history.document; sel=self.tab.selection
        if not sel: return doc
        if sel[0]=="body": return find_body(doc,sel[1])
        sketch=find_sketch(doc,sel[1])
        return sketch if sel[0]=="sketch" else next(e for e in sketch["entities"] if e["id"]==sel[2])

    def apply_properties(self):
        sel=self.tab.selection; updated=copy.deepcopy(self.selected_record())
        if sel[0] in ("body","sketch"): updated["name"]=self.property_name.text().strip()
        if sel[0]=="body": updated["operation"]=self.property_operation.currentData()
        for (key,index),(spin,original,conversion) in self.inspector_fields.items():
            if spin.value()!=original:
                if key=="point": updated["points"][index//2][index%2]=spin.value()*conversion
                else: updated[key][index]=spin.value()*conversion
        def edit(d):
            if sel[0]=="body": find_body(d,sel[1]).update(updated)
            elif sel[0]=="sketch": find_sketch(d,sel[1]).update(updated)
            else: next(e for e in find_sketch(d,sel[1])["entities"] if e["id"]==sel[2]).update(updated)
        self.transaction("Edit " + sel[0],edit)

    def focus_transform(self,key):
        self.properties_dock.show(); self.properties_dock.raise_()
        spin=self.transform_focus.get(key)
        if spin: spin.setFocus(); spin.selectAll(); self.inspector.ensureWidgetVisible(spin)

    def choose_color(self):
        body=self.selected_record()
        color=QColorDialog.getColor(QColor.fromRgbF(*body["color"]),self,"Body appearance")
        if color.isValid():
            identifier=body["id"]
            self.transaction("Change appearance",lambda d:find_body(d,identifier).update(color=[color.redF(),color.greenF(),color.blueF()]))

    def add_body(self,kind):
        body=new_body(kind); empty=not self.tab.history.document["bodies"]
        self.transaction("Create " + kind,lambda d:d["bodies"].append(body))
        self.tab.selection=("body",body["id"]); self.tab.is_sketch=False; self.refresh()
        if empty: self.set_view("Fit")

    def create_sketch(self):
        sketch=new_sketch("Sketch " + str(len(self.tab.history.document["sketches"])+1))
        self.transaction("Create sketch",lambda d:d["sketches"].append(sketch))
        self.tab.selection=("sketch",sketch["id"]); self.tab.active_sketch=sketch["id"]
        self.edit_sketch()

    def edit_sketch(self):
        sel=self.tab.selection
        if not sel or sel[0] not in ("sketch","entity"): return
        self.tab.active_sketch=sel[1]; self.tab.is_sketch=True
        self.ribbon.setCurrentIndex(self.ribbon.pages["Sketch"]); self.refresh()
        self.tab.canvas.setFocus()

    def finish_sketch(self):
        self.tab.canvas.cancel(); self.tab.is_sketch=False
        self.ribbon.setCurrentIndex(self.ribbon.pages["3D Model"]); self.refresh()

    def sketch_tool(self,tool):
        if self.tab.is_sketch: self.tab.canvas.set_tool(tool)

    def add_entity(self,tab,entity):
        if not tab.active_sketch: return
        try:
            self.transaction("Draw " + entity["kind"],lambda d:find_sketch(d,tab.active_sketch)["entities"].append(entity),tab)
            tab.selection=("entity",tab.active_sketch,entity["id"]); self.refresh()
        except Exception as exc: self.log(str(exc))

    def extrude(self):
        sel=self.tab.selection
        if not sel or sel[0]!="entity": return
        unit=UNIT_MM[self.tab.history.document["units"]]
        value,ok=QInputDialog.getDouble(self,"Extrude rectangle","Height ("+self.tab.history.document["units"]+")",20/unit,.000001/unit,10000/unit,8)
        if not ok: return
        created=[]
        self.transaction("Extrude rectangle (independent box)",lambda d:created.append(extrude_rectangle(d,sel[1],sel[2],value*unit)))
        self.tab.selection=("body",created[0]); self.finish_sketch(); self.set_view("Fit")

    def set_operation(self,operation):
        if self.tab.selection and self.tab.selection[0]=="body":
            identifier=self.tab.selection[1]
            self.transaction("Change CSG operation",lambda d:find_body(d,identifier).update(operation=operation))

    def toggle_suppressed(self):
        sel=self.tab.selection
        if sel and sel[0]=="body":
            self.transaction("Change suppression",lambda d:find_body(d,sel[1]).update(enabled=not find_body(d,sel[1])["enabled"]))

    def reorder(self,direction):
        sel=self.tab.selection
        if not sel or sel[0]!="body": return
        def edit(d):
            index=next(i for i,b in enumerate(d["bodies"]) if b["id"]==sel[1]); target=index+direction
            if 0<=target<len(d["bodies"]): d["bodies"].insert(target,d["bodies"].pop(index))
        self.transaction("Reorder CSG operand",edit)

    def duplicate(self):
        sel=self.tab.selection
        if not sel: return
        record=copy.deepcopy(self.selected_record()); record["id"]=uid()
        if "name" in record: record["name"]=(record["name"][:110]+" copy")
        if sel[0]=="body":
            record["position"][0]+=10
            edit=lambda d:d["bodies"].append(record); selected=("body",record["id"])
        elif sel[0]=="sketch":
            for entity in record["entities"]: entity["id"]=uid()
            edit=lambda d:d["sketches"].append(record); selected=("sketch",record["id"])
        else:
            for point in record["points"]: point[0]+=10
            edit=lambda d:find_sketch(d,sel[1])["entities"].append(record); selected=("entity",sel[1],record["id"])
        self.transaction("Duplicate " + sel[0],edit); self.tab.selection=selected; self.refresh()

    def delete_selected(self):
        sel=self.tab.selection
        if not sel: return
        def edit(d):
            if sel[0]=="body": d["bodies"]=[b for b in d["bodies"] if b["id"]!=sel[1]]
            elif sel[0]=="sketch": d["sketches"]=[s for s in d["sketches"] if s["id"]!=sel[1]]
            else:
                sketch=find_sketch(d,sel[1]); sketch["entities"]=[e for e in sketch["entities"] if e["id"]!=sel[2]]
        self.transaction("Delete " + sel[0],edit)

    def rename_selected(self):
        sel=self.tab.selection
        if not sel or sel[0]=="entity": return
        value,ok=QInputDialog.getText(self,"Rename","Name",text=self.selected_record()["name"])
        if ok:
            self.transaction("Rename " + sel[0],lambda d:(find_body(d,sel[1]) if sel[0]=="body" else find_sketch(d,sel[1])).update(name=value.strip()))

    def undo(self):
        self.tab.canvas.cancel(); self.tab.history.undo(); self.refresh()

    def redo(self):
        self.tab.canvas.cancel(); self.tab.history.redo(); self.refresh()

    def set_view(self,view):
        tab=self.tab
        if not tab: return
        if tab.is_sketch:
            if view=="Fit": tab.canvas.fit_all()
            return
        if hasattr(tab.viewport,"fit_document"):
            if view=="Fit": tab.viewport.fit_document(tab.history.document)
            else: tab.viewport.set_orientation(view)

    def toggle_canvas(self,field):
        setattr(self.tab.canvas,field,not getattr(self.tab.canvas,field)); self.tab.canvas.update(); self.update_actions()

    def cursor_position(self,tab,x,y):
        if tab is self.tab:
            unit=UNIT_MM[tab.history.document["units"]]
            self.coordinate_status.setText(f"X {x/unit:.4f}   Y {y/unit:.4f}   ")

    def toggle_theme(self):
        self.dark=not self.dark; self.settings.setValue("dark",str(self.dark).lower())
        self.setStyleSheet(stylesheet(self.dark)); self.refresh()

    def reset_layout(self):
        for dock,area in ((self.browser_dock,Qt.DockWidgetArea.LeftDockWidgetArea),(self.properties_dock,Qt.DockWidgetArea.RightDockWidgetArea),(self.history_dock,Qt.DockWidgetArea.BottomDockWidgetArea),(self.messages_dock,Qt.DockWidgetArea.BottomDockWidgetArea)):
            dock.setFloating(False); self.addDockWidget(area,dock); dock.show()
        self.tabifyDockWidget(self.history_dock,self.messages_dock); self.history_dock.raise_()
        self.resizeDocks([self.browser_dock,self.properties_dock],[235,290],Qt.Orientation.Horizontal)
        self.resizeDocks([self.history_dock],[125],Qt.Orientation.Vertical)

    def command_search(self):
        CommandPalette(list(self.actions.values()),self).exec()

    def open_path(self,path):
        path=Path(path).resolve()
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).history.path==path: self.tabs.setCurrentIndex(i); return
        history=History.open(path)
        tab=self.add_tab(history); self.remember_path(path); return tab

    def open_dialog(self):
        filename,_=QFileDialog.getOpenFileName(self,"Open Studio document","","AdaptiveCAD Studio (*.acstudio)")
        if filename: self.open_path(filename)

    def remember_path(self,path):
        previous=self.settings.value("recent",[])
        if not isinstance(previous,list): previous=[]
        self.settings.setValue("recent",[str(path)]+[p for p in previous if p!=str(path)][:9])

    def rebuild_recent(self):
        self.recent.clear(); paths=self.settings.value("recent",[])
        if not isinstance(paths,list): paths=[]
        for path in paths:
            self.recent.addAction(path,lambda checked=False,p=path:self.guarded(lambda:self.open_path(p)))

    def save_document(self,save_as=False,tab=None):
        tab=tab or self.tab; path=tab.history.path
        if save_as or path is None:
            filename,_=QFileDialog.getSaveFileName(self,"Save Studio document",str(path or (tab.history.document["name"]+".acstudio")),"AdaptiveCAD Studio (*.acstudio)")
            if not filename: return False
            path=Path(filename)
            if path.suffix.lower()!=".acstudio": path=path.with_suffix(".acstudio")
            if str(path)!=filename and path.exists():
                if QMessageBox.question(self,"Replace existing file?",str(path)+" already exists. Replace it?",QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes: return False
        for i in range(self.tabs.count()):
            other=self.tabs.widget(i)
            if other is not tab and other.history.path==Path(path).resolve():
                raise ValueError("That file is open in another tab. Save to a different path.")
        tab.history.save(path); self.remember_path(path); self.remove_recovery(tab); self.refresh(); self.log("Saved " + str(path)); return True

    def can_close(self,tab):
        if not tab.history.dirty: return True
        answer=QMessageBox.question(self,"Unsaved changes","Save changes to " + tab.history.document["name"]+"?",QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel: return False
        if answer==QMessageBox.StandardButton.Save:
            try: return self.save_document(tab=tab)
            except Exception as exc: self.log(str(exc)); QMessageBox.warning(self,"Save failed",str(exc)); return False
        return True

    def close_tab(self,index):
        tab=self.tabs.widget(index)
        if not self.can_close(tab): return
        self.remove_recovery(tab); self.tabs.removeTab(index); tab.deleteLater()
        if self.tabs.count()==0: self.new_document()

    def write_recovery(self):
        try:
            self.recovery_dir.mkdir(parents=True,exist_ok=True)
            for i in range(self.tabs.count()):
                tab=self.tabs.widget(i)
                if tab.history.dirty: atomic_write(self.recovery_dir/(tab.recovery_id+".acstudio"),dumps(tab.history.document)+"\n")
                else: self.remove_recovery(tab)
        except OSError as exc: self.log("Recovery snapshot could not be written: " + str(exc))

    def remove_recovery(self,tab):
        try: (self.recovery_dir/(tab.recovery_id+".acstudio")).unlink(missing_ok=True)
        except OSError as exc: self.log("Could not remove recovery snapshot: " + str(exc))

    def offer_recovery(self):
        files=list(self.recovery_dir.glob("*.acstudio")) if self.recovery_dir.exists() else []
        if not files: return
        answer=QMessageBox.question(self,"Recover documents",f"Found {len(files)} recovery snapshot(s). Open them as unsaved documents?",QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes: return
        for path in files:
            try:
                history=History.open(path); history.path=None; history.disk_digest=None; history.saved=dumps(new_document())
                tab=self.add_tab(history); tab.recovery_id=path.stem
            except Exception as exc: self.log("Recovery failed for " + path.name + ": " + str(exc))

    def closeEvent(self,event):
        tabs=[self.tabs.widget(i) for i in range(self.tabs.count())]
        if not all(self.can_close(tab) for tab in tabs): event.ignore(); return
        self.settings.setValue("geometry",self.saveGeometry()); self.settings.setValue("layout",self.saveState(1))
        self.settings.sync()
        for tab in tabs: self.remove_recovery(tab)
        event.accept()

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() and u.toLocalFile().lower().endswith(".acstudio") for u in event.mimeData().urls()): event.acceptProposedAction()

    def dropEvent(self,event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".acstudio"): self.guarded(lambda p=url.toLocalFile():self.open_path(p))
        event.acceptProposedAction()

    def export_svg(self):
        identifier=self.tab.active_sketch
        if self.tab.selection and self.tab.selection[0] in ("sketch","entity"): identifier=self.tab.selection[1]
        if not identifier: return
        filename,_=QFileDialog.getSaveFileName(self,"Export curve-native sketch","sketch.svg","SVG (*.svg)")
        if filename:
            export_sketch(find_sketch(self.tab.history.document,identifier),filename); self.log("Exported exact sketch definitions to " + filename)

    def save_snapshot(self):
        filename,_=QFileDialog.getSaveFileName(self,"Save workspace image","AdaptiveCAD_Studio.png","PNG (*.png)")
        if filename and not self.grab().save(filename,"PNG"): raise OSError("The PNG image could not be saved.")

    def validate_document(self):
        validate(self.tab.history.document)
        QMessageBox.information(self,"Document validation","PASS: document schema, finite coordinates, unique IDs, primitive parameters, CSG ordering and active-body limit.\n\nThis is not a solid-manufacturing or geometry-tolerance certification.")

    def show_definition(self):
        dialog=QDialog(self); dialog.setWindowTitle("Authoritative source definition"); dialog.resize(620,580)
        layout=QVBoxLayout(dialog); text=QPlainTextEdit(); text.setReadOnly(True); text.setPlainText(json.dumps(self.selected_record(),indent=2)); layout.addWidget(text)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(dialog.reject); layout.addWidget(close); dialog.exec()

    def measure_origins(self):
        bodies=self.tab.history.document["bodies"]
        if len(bodies)<2: return
        dialog=QDialog(self); dialog.setWindowTitle("Distance between body origins")
        layout=QVBoxLayout(dialog); form=QFormLayout(); a=QComboBox(); b=QComboBox()
        for body in bodies: a.addItem(body["name"],body["id"]); b.addItem(body["name"],body["id"])
        b.setCurrentIndex(1); form.addRow("From",a); form.addRow("To",b); layout.addLayout(form)
        result=QLabel(); layout.addWidget(result)
        def update():
            unit=UNIT_MM[self.tab.history.document["units"]]
            x=find_body(self.tab.history.document,a.currentData())["position"]; y=find_body(self.tab.history.document,b.currentData())["position"]
            result.setText(f"Origin distance: {math.dist(x,y)/unit:.8g} {self.tab.history.document['units']}\nNot a surface clearance measurement.")
        a.currentIndexChanged.connect(update); b.currentIndexChanged.connect(update); update()
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(dialog.reject); layout.addWidget(close); dialog.exec()

    def launch_legacy(self):
        root=Path(__file__).resolve().parents[2]; launcher=root/"run_enhanced_playground.py"
        if not launcher.is_file(): raise FileNotFoundError("Legacy launcher not found in this checkout.")
        success,_=QProcess.startDetached(sys.executable,[str(launcher)],str(root))
        if not success: raise RuntimeError("Could not launch the legacy Playground.")
        self.log("Started the legacy Playground in a separate process; Studio documents are not transferred.")

    def open_guide(self):
        path=Path(__file__).resolve().parents[2]/"docs"/"STUDIO_GUI.md"
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))): raise RuntimeError("Could not open the Studio guide.")

    def add_demo(self):
        from .sample import bearing_demo
        tab=self.new_document()
        self.transaction("Load analytic bearing demo",lambda d:d.update(bearing_demo()),tab)
        self.set_view("Iso"); self.set_view("Fit")
