"""Curve-native XY sketch canvas. Dimensions are readouts, not constraints."""
from __future__ import annotations
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QWidget
from .document import SKETCH_POINTS, UNIT_MM, new_entity


def curve_path(entity):
    points, kind = entity["points"], entity["kind"]
    path = QPainterPath()
    a, b = points[:2]
    if kind == "circle":
        radius = math.dist(a, b)
        path.addEllipse(QPointF(*a), radius, radius)
    elif kind == "rectangle":
        path.addRect(QRectF(QPointF(*a), QPointF(*b)).normalized())
    elif kind == "line":
        path.moveTo(*a)
        path.lineTo(*b)
    else:
        path.moveTo(*a)
        path.cubicTo(*points[1], *points[2], *points[3])
    return path


def snap_points(entity):
    points, kind = entity["points"], entity["kind"]
    a, b = points[:2]
    if kind == "rectangle":
        corners = [a, [b[0], a[1]], b, [a[0], b[1]]]
        midpoints = [[(p[0]+q[0])/2, (p[1]+q[1])/2] for p,q in zip(corners, corners[1:]+corners[:1])]
        return corners + midpoints + [[(a[0]+b[0])/2, (a[1]+b[1])/2]]
    if kind == "circle":
        r = math.dist(a, b)
        return [a, [a[0]+r, a[1]], [a[0]-r, a[1]], [a[0], a[1]+r], [a[0], a[1]-r]]
    if kind == "bezier":
        return [points[0], points[-1]]
    return points + [[(a[0]+b[0])/2, (a[1]+b[1])/2]]


class SketchCanvas(QWidget):
    entityCreated = Signal(dict)
    entitySelected = Signal(str)
    message = Signal(str)
    cursorMoved = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sketchCanvas")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.tool = "select"
        self.points = []
        self.entities = []
        self.selected_id = ""
        self.units = "mm"
        self.zoom = 6.0
        self.offset = QPointF()
        self.cursor_world = [0., 0.]
        self.grid = self.snap = self.dimensions = self.dark = True
        self.ortho = False
        self._pan = None

    def set_tool(self, tool):
        if tool != "select" and tool not in SKETCH_POINTS:
            raise ValueError("Unsupported sketch tool.")
        self.cancel()
        self.tool = tool
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.CrossCursor)
        self.message.emit("Select an entity" if tool == "select" else f"{tool.title()}: click {SKETCH_POINTS[tool]} defining points; Esc cancels")
        self.setFocus()
        self.update()

    def cancel(self):
        self.points = []
        self.update()

    def set_entities(self, entities, selected="", units="mm"):
        self.entities = entities
        self.selected_id = selected
        self.units = units
        self.update()

    def to_world(self, point):
        return [(point.x()-self.width()/2-self.offset.x())/self.zoom,
                -(point.y()-self.height()/2-self.offset.y())/self.zoom]

    def to_screen(self, point):
        return QPointF(self.width()/2+self.offset.x()+point[0]*self.zoom,
                       self.height()/2+self.offset.y()-point[1]*self.zoom)

    def grid_step(self):
        return 10.0 ** math.ceil(math.log10(22/max(self.zoom, 1e-9)))

    def snap_world(self, point):
        point = list(point)
        if self.snap:
            candidates = [p for entity in self.entities for p in snap_points(entity)]
            closest = min(candidates, key=lambda p: math.dist(p, point), default=None)
            if closest is not None and math.dist(closest, point)*self.zoom < 9:
                point = list(closest)
            else:
                step = self.grid_step()
                point = [round(c/step)*step for c in point]
        if self.ortho and self.points and self.tool == "line":
            start = self.points[0]
            if abs(point[0]-start[0]) > abs(point[1]-start[1]):
                point[1] = start[1]
            else:
                point[0] = start[0]
        return point

    def fit_all(self):
        if not self.entities:
            self.zoom, self.offset = 6., QPointF()
        else:
            rect = curve_path(self.entities[0]).boundingRect()
            for entity in self.entities[1:]:
                rect = rect.united(curve_path(entity).boundingRect())
            self.zoom = max(.02, min(500., min(max(1, self.width()-100)/max(rect.width(), 1), max(1, self.height()-100)/max(rect.height(), 1))))
            self.offset = QPointF(-rect.center().x()*self.zoom, rect.center().y()*self.zoom)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg, grid, fg = ("#17202b", "#283644", "#72baff") if self.dark else ("#f5f7fa", "#e0e5eb", "#215e91")
        p.fillRect(self.rect(), QColor(bg))
        origin = self.to_screen([0, 0])
        if self.grid:
            step = self.grid_step()*self.zoom
            p.setPen(QPen(QColor(grid), 1))
            x = origin.x() % step
            while x < self.width():
                p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
                x += step
            y = origin.y() % step
            while y < self.height():
                p.drawLine(QPointF(0, y), QPointF(self.width(), y))
                y += step
        p.setPen(QPen(QColor("#99595a"), 1))
        p.drawLine(QPointF(0, origin.y()), QPointF(self.width(), origin.y()))
        p.setPen(QPen(QColor("#528c70"), 1))
        p.drawLine(QPointF(origin.x(), 0), QPointF(origin.x(), self.height()))
        p.save()
        p.translate(origin)
        p.scale(self.zoom, -self.zoom)
        for entity in self.entities:
            selected = entity["id"] == self.selected_id
            pen = QPen(QColor("#ffbe63" if selected else fg), 2.4 if selected else 1.6)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPath(curve_path(entity))
            if selected:
                for point in snap_points(entity):
                    p.drawEllipse(QPointF(*point), 3/self.zoom, 3/self.zoom)
        if self.points:
            preview = self.points + [self.cursor_world]
            pen = QPen(QColor("#f6c76f"), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            if len(preview) == SKETCH_POINTS.get(self.tool):
                p.drawPath(curve_path({"kind": self.tool, "points": preview}))
            else:
                path = QPainterPath(QPointF(*preview[0]))
                for point in preview[1:]:
                    path.lineTo(*point)
                p.drawPath(path)
        p.restore()
        p.setPen(QColor("#bccad9" if self.dark else "#4c6177"))
        p.drawText(20, 30, f"XY SKETCH / {self.tool.upper()} / {self.units}")
        p.drawText(20, self.height()-20, "Middle drag: pan   Wheel: zoom   F8: ortho   F9: snap   Esc: cancel")
        if self.dimensions and self.selected_id:
            entity = next((e for e in self.entities if e["id"] == self.selected_id), None)
            if entity:
                a, b = entity["points"][:2]
                unit = UNIT_MM[self.units]
                if entity["kind"] == "rectangle":
                    label = f"W {abs(b[0]-a[0])/unit:.4g}   H {abs(b[1]-a[1])/unit:.4g} {self.units}"
                elif entity["kind"] == "circle":
                    label = f"Diameter {2*math.dist(a,b)/unit:.4g} {self.units}"
                elif entity["kind"] == "line":
                    label = f"Length {math.dist(a,b)/unit:.4g} {self.units}"
                else:
                    label = "Cubic Bezier: 4 defining control points"
                p.drawText(20, 54, label + " (readout)")

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = event.position()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        raw = self.to_world(event.position())
        if self.tool == "select":
            stroker = QPainterPathStroker()
            stroker.setWidth(12/self.zoom)
            result = ""
            for entity in reversed(self.entities):
                if stroker.createStroke(curve_path(entity)).contains(QPointF(*raw)):
                    result = entity["id"]
                    break
            self.entitySelected.emit(result)
        else:
            self.points.append(self.snap_world(raw))
            if len(self.points) == SKETCH_POINTS[self.tool]:
                try:
                    self.entityCreated.emit(new_entity(self.tool, self.points))
                except ValueError as exc:
                    self.message.emit(str(exc))
                self.points = []
            self.update()

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            self.offset += event.position()-self._pan
            self._pan = event.position()
        self.cursor_world = self.snap_world(self.to_world(event.position()))
        self.cursorMoved.emit(*self.cursor_world)
        self.update()

    def mouseReleaseEvent(self, event):
        self._pan = None

    def wheelEvent(self, event):
        before = self.to_world(event.position())
        self.zoom = max(.02, min(500., self.zoom*math.exp(event.angleDelta().y()/1200)))
        self.offset += event.position()-self.to_screen(before)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.set_tool("select")
            event.accept()
        else:
            event.ignore()
