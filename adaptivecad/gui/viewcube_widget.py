from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QFont

class ViewCubeWidget(QWidget):
    def __init__(self, occ_display, parent=None):
        super().__init__(parent)
        self.occ_display = occ_display
        self.setFixedSize(90, 90)
        self.views = {
            "Top": (45, 15),
            "Front": (45, 75),
            "Left": (10, 45),
            "Right": (80, 45),
            "Home": (45, 45),
        }
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor(32, 32, 32, 220))
        qp.drawRect(0, 0, 90, 90)
        qp.setFont(QFont("Arial", 9, QFont.Bold))
        for label, (x, y) in self.views.items():
            qp.setPen(QColor("#37e8ff") if label == "Home" else QColor("#fff"))
            qp.drawText(QRect(x-16, y-10, 32, 20), Qt.AlignCenter, label)

    def mousePressEvent(self, event):
        pos = event.pos()
        for label, (x, y) in self.views.items():
            if (QPoint(x, y) - pos).manhattanLength() < 20:
                self.snap_view(label)
                break

    def snap_view(self, label):
        vmap = {
            "Top": self.occ_display.View_Top,
            "Front": self.occ_display.View_Front,
            "Left": self.occ_display.View_Left,
            "Right": self.occ_display.View_Right,
            "Home": self.occ_display.View_Iso,
        }
        if label in vmap:
            vmap[label]()
            self.occ_display.FitAll()
