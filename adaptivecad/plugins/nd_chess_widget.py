"""
NDChessWidget and FourDChessPlugin for AdaptiveCAD

This module provides a minimal ND chessboard visualizer widget and plugin,
using AdaptiveCAD's geometry and rendering abstractions.
"""
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QComboBox
from PyQt5.QtCore import Qt
 # Import AdaptiveCAD geometry/render if available
try:
    from adaptivecad.geometry import GeometryArray
    from adaptivecad.render import Render2D, Render3D
except ImportError:
    GeometryArray = np.array  # fallback for dev
    Render2D = None
    Render3D = None

class NDChessWidget(QWidget):
    def __init__(self, dims=(8,8,8,8)):
        super().__init__()
        # Track castling rights: [white_king, white_kingside_rook, white_queenside_rook, black_king, black_kingside_rook, black_queenside_rook]
        self.castling_rights = {
            'wK': True, 'wRk': True, 'wRq': True,
            'bK': True, 'bRk': True, 'bRq': True
        }
        self.dims = dims
        self.board = GeometryArray(np.zeros(dims, dtype=int))
        self.slices = [0] * len(dims)
        self.active_axes = (1, 2)  # default: show x, y (for 2D fallback)
        self.active_axes_3d = (0, 1, 2)  # default: show axes 0,1,2 in 3D
        self.slice_axis_3d = 3  # default: axis 3 is the slicing axis
        self.selected_cell = None  # (row, col) in current 2D view
        self.piece_types = {
            0: '',
            1: '♙', -1: '♟',
            2: '♕', -2: '♛',
            3: '♖', -3: '♜',
            4: '♘', -4: '♞',
            5: '♗', -5: '♝',
            6: '♔', -6: '♚'
        }  # pawns, queens, rooks, knights, bishops, kings
        self.init_board()
        self.setup_ui()

    def init_board(self):
        # Standard chess setup for 8x8 board, for all ND slices
        shape = self.board.shape
        if len(shape) >= 2 and shape[0] >= 8 and shape[1] >= 8:
            idx = [slice(None)] * len(shape)
            # White pieces
            # Row 0: R N B Q K B N R
            first_row = [3, 4, 5, 2, 6, 5, 4, 3]
            idx[0] = 0
            for col, val in enumerate(first_row):
                idx[1] = col
                self.board[tuple(idx)] = val
            # Row 1: pawns
            idx[0] = 1
            for col in range(8):
                idx[1] = col
                self.board[tuple(idx)] = 1
            # Black pieces
            # Row 7: r n b q k b n r
            last_row = [-3, -4, -5, -2, -6, -5, -4, -3]
            idx[0] = 7
            for col, val in enumerate(last_row):
                idx[1] = col
                self.board[tuple(idx)] = val
            # Row 6: pawns
            idx[0] = 6
            for col in range(8):
                idx[1] = col
                self.board[tuple(idx)] = -1
    def setup_ui(self):
        from PyQt5.QtWidgets import QPushButton
        layout = QVBoxLayout()
        self.sliders = []
        # 3D axes selector
        n = len(self.dims)
        self.axis_triples = [(i, j, k) for i in range(n) for j in range(i+1, n) for k in range(j+1, n)]
        self.axis_selector_3d = QComboBox()
        self.axis_selector_3d.addItems([f"3D: dims {i},{j},{k}" for i, j, k in self.axis_triples])
        self.axis_selector_3d.currentIndexChanged.connect(self.set_active_axes_3d)
        layout.addWidget(self.axis_selector_3d)
        # Slicer for the remaining axis (for 4D, only one)
        self.slice_slider = None
        self.slice_label = None
        self.setLayout(layout)
        self.update_slice_slider()
        # Add a generic action button
        self.action_button = QPushButton("Action")
        self.action_button.clicked.connect(self.on_action_button)
        layout.addWidget(self.action_button)
        # Enable mouse events
        self.setMouseTracking(True)

    def update_slice_slider(self):
        # Remove old slider if present
        layout = self.layout()
        if hasattr(self, 'slice_slider') and self.slice_slider:
            layout.removeWidget(self.slice_slider)
            self.slice_slider.deleteLater()
            self.slice_slider = None
        if hasattr(self, 'slice_label') and self.slice_label:
            layout.removeWidget(self.slice_label)
            self.slice_label.deleteLater()
            self.slice_label = None
        # Find the slicing axis (not in active_axes_3d)
        axes = set(range(len(self.dims)))
        slicing_axes = list(axes - set(self.active_axes_3d))
        if slicing_axes:
            self.slice_axis_3d = slicing_axes[0]
            from PyQt5.QtWidgets import QSlider, QLabel
            self.slice_slider = QSlider(Qt.Horizontal)
            self.slice_slider.setRange(0, self.dims[self.slice_axis_3d] - 1)
            self.slice_slider.setValue(self.slices[self.slice_axis_3d])
            self.slice_slider.valueChanged.connect(lambda v, idx=self.slice_axis_3d: self.set_slice(idx, v))
            self.slice_label = QLabel(f"Slice dim {self.slice_axis_3d}:")
            h = QHBoxLayout(); h.addWidget(self.slice_label); h.addWidget(self.slice_slider)
            self.layout().insertLayout(1, h)
    def set_active_axes_3d(self, idx):
        self.active_axes_3d = self.axis_triples[idx]
        self.update_slice_slider()
        self.update()

    def on_action_button(self):
        # Placeholder for button action
        print("Action button clicked!")
    def set_slice(self, idx, val):
        self.slices[idx] = val
        self.update()
    def set_active_axes(self, idx):
        self.active_axes = self.axis_pairs[idx]
        self.update()
    def paintEvent(self, event):
        # 3D view with 4D slicing
        if hasattr(self, 'active_axes_3d') and hasattr(self, 'slice_axis_3d') and len(self.dims) >= 4:
            axes = self.active_axes_3d
            slice_axis = self.slice_axis_3d
            fixed = [slice(None) if i in axes else self.slices[i] for i in range(len(self.dims))]
            cube = self.board[tuple(fixed)]
            if 'Render3D' in globals() and Render3D is not None:
                renderer = Render3D(self)
                renderer.draw_cube(cube, cell_size=30, style="chessboard_3d")
                renderer.flush()
                return
            else:
                # fallback: show as text (show one 2D slice of the cube)
                from PyQt5.QtGui import QPainter, QColor
                qp = QPainter(self)
                qp.setFont(qp.font())
                # Show the first 2D slice of the cube
                if cube.ndim == 3:
                    grid = cube[0]
                else:
                    grid = cube
                cell_size = 40
                offset = 20
                for row in range(grid.shape[0]):
                    for col in range(grid.shape[1]):
                        val = grid[row, col]
                        piece = self.piece_types.get(val, str(val) if val != 0 else '')
                        x = offset + col * cell_size
                        y = offset + row * cell_size
                        qp.drawText(x + cell_size//3, y + 2*cell_size//3, piece)
                qp.end()
                return
        # fallback: 2D view
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        cell_size = 40
        offset = 20
        if Render2D:
            renderer = Render2D(self)
            renderer.draw_grid(grid, cell_size=cell_size, offset=offset, style="chessboard")
            # Draw pieces as text if possible
            if hasattr(renderer, 'draw_text'):
                for row in range(grid.shape[0]):
                    for col in range(grid.shape[1]):
                        val = grid[row, col]
                        piece = self.piece_types.get(val, str(val) if val != 0 else '')
                        if piece:
                            x = offset + col * cell_size + cell_size//2
                            y = offset + row * cell_size + cell_size//2
                            renderer.draw_text(piece, x, y, align='center', font_size=20)
            # Highlight selected cell
            if self.selected_cell:
                row, col = self.selected_cell
                if 0 <= row < grid.shape[0] and 0 <= col < grid.shape[1]:
                    if hasattr(renderer, 'draw_rect'):
                        x = offset + col * cell_size
                        y = offset + row * cell_size
                        renderer.draw_rect(x, y, cell_size, cell_size, color='yellow', width=3)
            renderer.flush()
        else:
            # fallback: draw as text and highlight selection
            qp = None
            try:
                from PyQt5.QtGui import QPainter, QColor
                qp = QPainter(self)
                qp.setFont(qp.font())
                for row in range(grid.shape[0]):
                    for col in range(grid.shape[1]):
                        val = grid[row, col]
                        piece = self.piece_types.get(val, str(val) if val != 0 else '')
                        x = offset + col * cell_size
                        y = offset + row * cell_size
                        if self.selected_cell == (row, col):
                            qp.setPen(QColor('yellow'))
                            qp.drawRect(x, y, cell_size, cell_size)
                            qp.setPen(QColor('black'))
                        qp.drawText(x + cell_size//3, y + 2*cell_size//3, piece)
            finally:
                if qp: qp.end()

    def mousePressEvent(self, event):
        # Map mouse click to cell in 2D grid
        cell_size = 40
        offset = 20
        x = event.x() - offset
        y = event.y() - offset
        row = y // cell_size
        col = x // cell_size
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        if 0 <= row < grid.shape[0] and 0 <= col < grid.shape[1]:
            if self.selected_cell is None:
                # Select a piece if present
                if grid[row, col] != 0:
                    self.selected_cell = (row, col)
                    self.update()
            else:
                src_row, src_col = self.selected_cell
                src_val = grid[src_row, src_col]
                dst_val = grid[row, col]
                # Movement rules for all piece types
                color = 1 if src_val > 0 else -1
                abs_val = abs(src_val)
                valid = False
                promote_row = 7 if src_val == 1 else 0
                d_row = row - src_row
                d_col = col - src_col
                # Prevent capturing own pieces
                if dst_val != 0 and (src_val * dst_val) > 0:
                    self.selected_cell = None
                    self.update()
                    return
                # Castling logic (king move two squares horizontally, not in check, not moved, rook not moved, path clear)
                if abs_val == 6 and src_row == row and abs(d_col) == 2:
                    if src_val > 0 and src_row == 0 and src_col == 4:
                        # White king
                        if d_col == 2:
                            # Kingside
                            if self.castling_rights['wK'] and self.castling_rights['wRk'] and grid[0,5] == 0 and grid[0,6] == 0:
                                if self._is_clear_path(grid, 0, 4, 0, 7):
                                    # Move king
                                    self._move_piece(src_row, src_col, 0, 6)
                                    # Move rook
                                    self._move_piece(0, 7, 0, 5)
                                    self.castling_rights['wK'] = False
                                    self.castling_rights['wRk'] = False
                                    self.selected_cell = None
                                    self.update()
                                    return
                        elif d_col == -2:
                            # Queenside
                            if self.castling_rights['wK'] and self.castling_rights['wRq'] and grid[0,1] == 0 and grid[0,2] == 0 and grid[0,3] == 0:
                                if self._is_clear_path(grid, 0, 4, 0, 0):
                                    self._move_piece(src_row, src_col, 0, 2)
                                    self._move_piece(0, 0, 0, 3)
                                    self.castling_rights['wK'] = False
                                    self.castling_rights['wRq'] = False
                                    self.selected_cell = None
                                    self.update()
                                    return
                    elif src_val < 0 and src_row == 7 and src_col == 4:
                        # Black king
                        if d_col == 2:
                            # Kingside
                            if self.castling_rights['bK'] and self.castling_rights['bRk'] and grid[7,5] == 0 and grid[7,6] == 0:
                                if self._is_clear_path(grid, 7, 4, 7, 7):
                                    self._move_piece(src_row, src_col, 7, 6)
                                    self._move_piece(7, 7, 7, 5)
                                    self.castling_rights['bK'] = False
                                    self.castling_rights['bRk'] = False
                                    self.selected_cell = None
                                    self.update()
                                    return
                        elif d_col == -2:
                            # Queenside
                            if self.castling_rights['bK'] and self.castling_rights['bRq'] and grid[7,1] == 0 and grid[7,2] == 0 and grid[7,3] == 0:
                                if self._is_clear_path(grid, 7, 4, 7, 0):
                                    self._move_piece(src_row, src_col, 7, 2)
                                    self._move_piece(7, 0, 7, 3)
                                    self.castling_rights['bK'] = False
                                    self.castling_rights['bRq'] = False
                                    self.selected_cell = None
                                    self.update()
                                    return
                if abs_val == 1:  # Pawn
                    direction = 1 if src_val == 1 else -1
                    # Forward move
                    if (col == src_col and row == src_row + direction and dst_val == 0):
                        valid = True
                    # Double move from starting row
                    elif src_val == 1 and src_row == 1 and col == src_col and row == 3 and grid[2, col] == 0 and dst_val == 0:
                        valid = True
                    elif src_val == -1 and src_row == 6 and col == src_col and row == 4 and grid[5, col] == 0 and dst_val == 0:
                        valid = True
                    # Capture diagonally
                    elif abs(col - src_col) == 1 and row == src_row + direction and dst_val != 0 and (src_val * dst_val) < 0:
                        valid = True
                    if valid:
                        src_idx = list(self.slices)
                        dst_idx = list(self.slices)
                        src_idx[self.active_axes[0]] = src_row
                        src_idx[self.active_axes[1]] = src_col
                        dst_idx[self.active_axes[0]] = row
                        dst_idx[self.active_axes[1]] = col
                        # Promotion check
                        if (col == src_col or abs(col - src_col) == 1) and row == promote_row:
                            self.board[tuple(dst_idx)] = 2 if src_val == 1 else -2
                        else:
                            self.board[tuple(dst_idx)] = self.board[tuple(src_idx)]
                        self.board[tuple(src_idx)] = 0
                        self.selected_cell = None
                        self.update()
                        return
                elif abs_val == 2:  # Queen
                    if (d_row == 0 or d_col == 0 or abs(d_row) == abs(d_col)) and (d_row != 0 or d_col != 0):
                        if self._is_clear_path(grid, src_row, src_col, row, col):
                            valid = True
                elif abs_val == 3:  # Rook
                    if (d_row == 0 or d_col == 0) and (d_row != 0 or d_col != 0):
                        if self._is_clear_path(grid, src_row, src_col, row, col):
                            valid = True
                elif abs_val == 4:  # Knight
                    if (abs(d_row), abs(d_col)) in [(2, 1), (1, 2)]:
                        valid = True
                elif abs_val == 5:  # Bishop
                    if abs(d_row) == abs(d_col) and d_row != 0:
                        if self._is_clear_path(grid, src_row, src_col, row, col):
                            valid = True
                elif abs_val == 6:  # King
                    if max(abs(d_row), abs(d_col)) == 1 and (d_row != 0 or d_col != 0):
                        valid = True
                if valid:
                    self._move_piece(src_row, src_col, row, col)
                    # Update castling rights if king or rook moves
                    if abs_val == 6:
                        if src_val > 0:
                            self.castling_rights['wK'] = False
                        else:
                            self.castling_rights['bK'] = False
                    elif abs_val == 3:
                        if src_val > 0 and src_row == 0:
                            if src_col == 0:
                                self.castling_rights['wRq'] = False
                            elif src_col == 7:
                                self.castling_rights['wRk'] = False
                        elif src_val < 0 and src_row == 7:
                            if src_col == 0:
                                self.castling_rights['bRq'] = False
                            elif src_col == 7:
                                self.castling_rights['bRk'] = False
                    self.selected_cell = None
                    self.update()
                    return
    def _move_piece(self, src_row, src_col, dst_row, dst_col):
        src_idx = list(self.slices)
        dst_idx = list(self.slices)
        src_idx[self.active_axes[0]] = src_row
        src_idx[self.active_axes[1]] = src_col
        dst_idx[self.active_axes[0]] = dst_row
        dst_idx[self.active_axes[1]] = dst_col
        self.board[tuple(dst_idx)] = self.board[tuple(src_idx)]
        self.board[tuple(src_idx)] = 0
    def _is_clear_path(self, grid, src_row, src_col, dst_row, dst_col):
        # Returns True if all squares between src and dst are empty (not including endpoints)
        d_row = dst_row - src_row
        d_col = dst_col - src_col
        step_row = (d_row > 0) - (d_row < 0)
        step_col = (d_col > 0) - (d_col < 0)
        cur_row, cur_col = src_row + step_row, src_col + step_col
        while (cur_row, cur_col) != (dst_row, dst_col):
            if grid[cur_row, cur_col] != 0:
                return False
            cur_row += step_row
            cur_col += step_col
        return True
                # Deselect if invalid move or same cell
        self.selected_cell = None
        self.update()

"""
Minimal integration with AdaptiveCAD playground:
 - Provides FourDChessPlugin for plugin system (dockable widget)
 - Provides add_nd_chess_to_playground(app) for manual integration
"""
# Plugin boilerplate
try:
    from adaptivecad.plugins import PluginBase
except ImportError:
    class PluginBase(object):
        def __init__(self, name=None): self.name = name
        def get_widget(self): return None
        def on_load(self, app): pass

class FourDChessPlugin(PluginBase):
    def __init__(self):
        super().__init__(name="4D Chess Visualizer")
        self.widget = NDChessWidget()
    def get_widget(self):
        return self.widget
    def on_load(self, app):
        # Minimal integration: add as dock widget if possible
        if hasattr(app, 'add_dock_widget'):
            app.add_dock_widget(self.widget, "4D Chess")
        # Optionally, add to playground 3D environment if available
        if hasattr(app, 'add_widget_to_3d_view'):
            app.add_widget_to_3d_view(self.widget)

# Minimal integration function for playground scripts
def add_nd_chess_to_playground(app):
    """
    Minimal integration: add NDChessWidget to AdaptiveCAD playground UI.
    Usage (in playground script):
        from adaptivecad.plugins.nd_chess_widget import add_nd_chess_to_playground
        add_nd_chess_to_playground(app)
    """
    widget = NDChessWidget()
    if hasattr(app, 'add_dock_widget'):
        app.add_dock_widget(widget, "4D Chess")
    elif hasattr(app, 'add_widget_to_3d_view'):
        app.add_widget_to_3d_view(widget)
    else:
        # fallback: show as top-level window
        widget.setWindowTitle("ND Chess Widget")
        widget.show()
    return widget

# Allow running this file directly to test the widget
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = NDChessWidget()
    w.setWindowTitle("ND Chess Widget Test")
    w.resize(500, 500)
    w.show()
    sys.exit(app.exec_())


# Minimal integration function for playground scripts
def add_nd_chess_to_playground(playground):
    """
    Adds the NDChessWidget to the given AdaptiveCAD playground instance as a dockable widget.
    Usage (in a playground script):
        from adaptivecad.plugins.nd_chess_widget import add_nd_chess_to_playground
        add_nd_chess_to_playground(playground)
    """
    widget = NDChessWidget()
    if hasattr(playground, 'add_dock_widget'):
        playground.add_dock_widget(widget, "ND Chess")
    elif hasattr(playground, 'add_widget'):
        playground.add_widget(widget)
    else:
        raise RuntimeError("Playground does not support widget integration.")
