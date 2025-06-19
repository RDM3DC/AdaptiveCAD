"""Simple ND Chessboard widget for AdaptiveCAD.

This widget displays an N-dimensional chessboard using a numpy array.
It supports basic 2D rendering with PySide6 QPainter and allows slicing
through additional dimensions via sliders.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QComboBox,
)


class NDChessWidget(QWidget):
    """Minimal N-dimensional chessboard visualizer."""

    def __init__(self, dims=(8, 8, 8, 8)) -> None:
        super().__init__()
        self.dims = dims
        self.board = np.zeros(dims, dtype=int)
        self.slices = [0] * len(dims)
        # Only 2D view is implemented; select axes
        self.axis_pairs = [(i, j) for i in range(len(dims)) for j in range(i + 1, len(dims))]
        self.active_axes = self.axis_pairs[0]
        self._init_board()
        self._setup_ui()

    def _init_board(self) -> None:
        """Initialize board with standard 8x8 chess setup."""
        if self.board.shape[0] < 8 or self.board.shape[1] < 8:
            return
        first_row = [4, 2, 3, 5, 6, 3, 2, 4]
        last_row = [-p for p in first_row]
        self.board[0, :8] = first_row
        self.board[1, :8] = 1
        self.board[6, :8] = -1
        self.board[7, :8] = last_row

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.axis_combo = QComboBox()
        self.axis_combo.addItems([f"Axes {i},{j}" for i, j in self.axis_pairs])
        self.axis_combo.currentIndexChanged.connect(self._set_axes)
        layout.addWidget(self.axis_combo)

        self.slice_sliders = []
        for idx, size in enumerate(self.dims):
            if idx in self.active_axes:
                self.slice_sliders.append(None)
                continue
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, size - 1)
            slider.valueChanged.connect(lambda v, i=idx: self._set_slice(i, v))
            h = QHBoxLayout()
            h.addWidget(QLabel(f"Dim {idx}"))
            h.addWidget(slider)
            layout.addLayout(h)
            self.slice_sliders.append(slider)

    def _set_axes(self, index: int) -> None:
        self.active_axes = self.axis_pairs[index]
        for idx, slider in enumerate(self.slice_sliders):
            if slider is None:
                continue
            if idx in self.active_axes:
                slider.parentWidget().setVisible(False)
            else:
                slider.parentWidget().setVisible(True)
        self.update()

    def _set_slice(self, idx: int, val: int) -> None:
        self.slices[idx] = val
        self.update()

    def paintEvent(self, event) -> None:
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        cell = 40
        off = 20
        qp = QPainter(self)
        qp.fillRect(0, 0, self.width(), self.height(), Qt.white)
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                x = off + c * cell
                y = off + r * cell
                if (r + c) % 2 == 0:
                    qp.fillRect(x, y, cell, cell, Qt.lightGray)
                else:
                    qp.fillRect(x, y, cell, cell, Qt.darkGray)
                val = grid[r, c]
                if val != 0:
                    qp.drawText(x + cell / 3, y + 2 * cell / 3, str(val))
        qp.end()
