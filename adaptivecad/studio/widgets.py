"""Original ribbon, command palette and orientation controls for Studio."""
from __future__ import annotations
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QScrollArea, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)


def icon(name, color="#65b5fa"):
    """Small original vector icons; no Autodesk images, fonts, or assets."""
    pix = QPixmap(48, 48); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 2.1)); p.setBrush(Qt.BrushStyle.NoBrush)
    if name in ("Box", "Superellipsoid", "extrude", "new"):
        p.drawPolygon(QPolygonF([QPointF(9,17), QPointF(24,8), QPointF(39,17), QPointF(39,34), QPointF(24,42), QPointF(9,34)]))
        p.drawLine(9,17,24,25); p.drawLine(39,17,24,25); p.drawLine(24,25,24,42)
    elif name in ("Sphere", "circle", "Capsule"):
        p.drawEllipse(QRectF(8,8,32,32)); p.drawEllipse(QRectF(17,8,14,32)); p.drawLine(9,24,39,24)
    elif name in ("Torus", "Mobius", "Pi bloom"):
        p.drawEllipse(QRectF(5,12,38,25)); p.drawEllipse(QRectF(14,18,20,11))
    elif name in ("bezier", "line", "rectangle", "sketch"):
        from PySide6.QtGui import QPainterPath
        if name == "rectangle": p.drawRect(7,12,34,25)
        elif name == "line": p.drawLine(8,38,39,9)
        else:
            path=QPainterPath(QPointF(7,36)); path.cubicTo(12,2,33,45,40,10); p.drawPath(path)
        p.drawRect(5,34,5,5); p.drawRect(37,7,5,5)
    elif name in ("undo", "redo"):
        if name == "redo": p.translate(48,0); p.scale(-1,1)
        p.drawArc(QRectF(12,14,29,26), 0, 220*16)
        p.drawLine(12,14,12,28); p.drawLine(12,14,26,14)
    elif name in ("cut", "join", "intersect"):
        p.drawRect(6,9,23,23); p.drawEllipse(QRectF(18,20,23,23))
    elif name in ("save", "open"):
        p.drawRoundedRect(QRectF(9,7,30,34),2,2); p.drawRect(16,8,16,11); p.drawRect(15,28,18,12)
    elif name in ("move", "fit", "iso"):
        p.drawLine(5,24,43,24); p.drawLine(24,5,24,43)
        for a,b,c,d in [(5,24,11,18),(5,24,11,30),(43,24,37,18),(43,24,37,30),(24,5,18,11),(24,5,30,11)]:
            p.drawLine(a,b,c,d)
    elif name == "delete":
        p.drawLine(9,12,39,12); p.drawRect(14,12,20,28); p.drawLine(19,6,29,6)
    else:
        p.drawRoundedRect(QRectF(8,8,32,32),6,6)
        font=p.font(); font.setPointSize(15); font.setBold(True); p.setFont(font)
        p.drawText(QRectF(8,8,32,32), Qt.AlignmentFlag.AlignCenter, name[:1].upper())
    p.end()
    return QIcon(pix)


class Ribbon(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.setDocumentMode(True)
        self.setMinimumHeight(146); self.setMaximumHeight(162)
        self.pages = {}

    def add_page(self, title, groups):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget(); row = QHBoxLayout(host); row.setContentsMargins(10,4,10,2); row.setSpacing(10)
        for label, actions in groups:
            group=QWidget(); box=QVBoxLayout(group); box.setContentsMargins(0,0,6,0); box.setSpacing(2)
            buttons=QHBoxLayout(); buttons.setSpacing(2)
            for action in actions:
                button=QToolButton(); button.setObjectName("ribbonButton")
                button.setDefaultAction(action); button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                button.setIconSize(QSize(34,34)); button.setMinimumSize(68,75)
                buttons.addWidget(button)
            box.addLayout(buttons)
            caption=QLabel(label); caption.setObjectName("groupCaption"); caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(caption); row.addWidget(group)
            rule=QFrame(); rule.setFrameShape(QFrame.Shape.VLine); rule.setObjectName("ribbonRule"); row.addWidget(rule)
        row.addStretch(); scroll.setWidget(host)
        self.pages[title] = self.addTab(scroll, title)


class CommandPalette(QDialog):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command search"); self.resize(540,430)
        layout=QVBoxLayout(self)
        self.query=QLineEdit(); self.query.setPlaceholderText("Search commands, tools and views…")
        self.results=QListWidget()
        layout.addWidget(self.query); layout.addWidget(self.results)
        self.actions=actions
        self.query.textChanged.connect(self.filter)
        self.query.returnPressed.connect(self.run_selected)
        self.results.itemActivated.connect(lambda _: self.run_selected())
        self.filter("")

    def filter(self, query):
        self.results.clear()
        terms=query.casefold().split()
        for action in self.actions:
            hay=(action.text()+" "+action.toolTip()).casefold()
            if all(term in hay for term in terms):
                item=QListWidgetItem(action.icon(), action.text()+"    "+action.shortcut().toString())
                item.setData(Qt.ItemDataRole.UserRole, action)
                if not action.isEnabled():
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    item.setToolTip(action.toolTip())
                self.results.addItem(item)
        for i in range(self.results.count()):
            if self.results.item(i).flags() & Qt.ItemFlag.ItemIsEnabled:
                self.results.setCurrentRow(i); break

    def run_selected(self):
        item=self.results.currentItem()
        if item:
            action=item.data(Qt.ItemDataRole.UserRole)
            if action.isEnabled():
                self.accept(); action.trigger()


class OrientationControl(QWidget):
    requested = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(116,116)
        self.setToolTip("Click a face for a standard view. Right-click for all views.")
        self.faces=[("Top", [(58,7),(103,29),(58,52),(13,29)]),
                    ("Front", [(13,29),(58,52),(58,96),(13,72)]),
                    ("Right", [(58,52),(103,29),(103,72),(58,96)])]
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for (name, points), fill in zip(self.faces, ("#d7e5f2", "#aabed1", "#8ca7c0")):
            poly=QPolygonF([QPointF(x,y) for x,y in points])
            p.setPen(QPen(QColor("#526b83"),1)); p.setBrush(QColor(fill)); p.drawPolygon(poly)
            p.setPen(QColor("#16334e"))
            p.drawText(poly.boundingRect(), Qt.AlignmentFlag.AlignCenter, name.upper())
        p.setPen(QColor("#7f9eb9")); p.drawText(QRectF(10,98,100,17), Qt.AlignmentFlag.AlignCenter, "ORIENTATION")

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            menu=QMenu(self)
            for view in ("Iso","Top","Bottom","Front","Back","Left","Right","Fit"):
                menu.addAction(view, lambda checked=False, v=view: self.requested.emit(v))
            menu.exec(event.globalPosition().toPoint()); return
        for name,points in self.faces:
            if QPolygonF([QPointF(x,y) for x,y in points]).containsPoint(event.position(), Qt.FillRule.OddEvenFill):
                self.requested.emit(name); return
