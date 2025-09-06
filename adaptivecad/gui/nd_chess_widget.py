"""ND Chessboard widget for AdaptiveCAD (with simple 4D rules).

This widget displays an N-dimensional chessboard backed by a numpy array and a
2D slice renderer. It now supports:

- Basic chess piece setup and Unicode rendering
- Click-to-select and move with legal-move highlights (no check rules)
- Turn handling and simple win detect (capturing king)
- Slicing through extra dimensions via sliders
- 4D layer shift move: move a piece to another slice on a non-view axis
- Built-in "How to Play" dialog describing the simplified 4D rules

Notes:
- Chess legality is simplified: no check/checkmate, castling, en passant, or
  promotion UI (pawns auto-promote to queen on last rank). The goal is a
  visual, approachable 4D chess demo.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QComboBox,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QListWidget,
)


class BoardCanvas(QWidget):
    """Dedicated paint surface for the chess board grid.

    Separating drawing from the parent container prevents overlapping layouts
    or stylesheet backgrounds from obscuring the board (seen as large dark
    rectangle previously). The parent NDChessWidget owns game state; this
    canvas just renders and forwards mouse events.
    """

    def __init__(self, parent: 'NDChessWidget') -> None:  # noqa: F821 (forward ref)
        super().__init__(parent)
        self.setMinimumSize(480, 480)

    # Use parent state for rendering
    def paintEvent(self, event):  # noqa: D401
        parent = self.parent()  # NDChessWidget
        if parent is None:
            return
        ndw = parent  # type: ignore
        ax1, ax2 = ndw.active_axes
        fixed = [slice(None) if i in ndw.active_axes else ndw.slices[i] for i in range(len(ndw.dims))]
        grid = ndw.board[tuple(fixed)]
        if grid.size == 0:
            return
        off = 18
        avail_w = max(50, self.width() - off * 2)
        avail_h = max(50, self.height() - off * 2)
        cell_w = avail_w / grid.shape[1]
        cell_h = avail_h / grid.shape[0]
        cell = int(min(72, cell_w, cell_h))
        board_w = cell * grid.shape[1]
        board_h = cell * grid.shape[0]
        start_x = (self.width() - board_w) // 2
        start_y = (self.height() - board_h) // 2
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        qp.fillRect(0, 0, self.width(), self.height(), ndw.theme.get('bg', Qt.white))

        font = QFont()
        font.setBold(True)
        font.setPointSizeF(max(10.0, cell * 0.50))
        qp.setFont(font)
        light_sq = ndw.theme.get('light', Qt.lightGray)
        dark_sq = ndw.theme.get('dark', Qt.darkGray)
        sel_col = ndw.theme.get('sel', Qt.yellow)
        move_col = ndw.theme.get('move', Qt.green)

        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                x = start_x + c * cell
                y = start_y + r * cell
                base_color = light_sq if (r + c) % 2 == 0 else dark_sq
                qp.fillRect(x, y, cell, cell, base_color)
                if ndw.selected == (r, c):
                    qp.fillRect(x, y, cell, cell, sel_col)
                elif (r, c) in ndw.legal_moves:
                    qp.fillRect(x, y, cell, cell, move_col)
                if ndw.last_move and ((r, c) in ndw.last_move):
                    qp.setPen(QPen(Qt.red, 2))
                    qp.drawRect(x, y, cell, cell)
                val = int(grid[r, c])
                if val != 0:
                    sym = ndw.symbols.get(val, str(val))
                    qp.setPen(Qt.white if base_color == dark_sq else Qt.black)
                    qp.drawText(x + cell * 0.18, y + cell * 0.72, sym)
                    qp.setPen(Qt.black)
        # Coordinates
        qp.setPen(Qt.black)
        col_labels = [chr(ord('a') + i) if i < 26 else str(i) for i in range(grid.shape[1])]
        for c in range(grid.shape[1]):
            x = start_x + c * cell + cell * 0.40
            qp.drawText(x, start_y - 6, col_labels[c])
        for r in range(grid.shape[0]):
            y = start_y + r * cell + cell * 0.60
            label = str(grid.shape[0] - r) if grid.shape[0] == 8 else str(r)
            qp.drawText(start_x - 18, y, label)
        qp.end()

    # Forward mouse events to parent logic after translating coords
    def mousePressEvent(self, event):
        parent = self.parent()
        if parent is None:
            return
        # Translate event position into board cell and delegate using NDChessWidget's existing logic
        # Reuse code by setting an attribute the parent mousePressEvent expects.
        parent._forwarded_mouse_event_pos = event.position()  # type: ignore[attr-defined]
        parent._canvas_mouse_press(event)  # type: ignore



class NDChessWidget(QWidget):
    """N-dimensional chessboard visualizer with simple gameplay."""

    def __init__(self, dims=(8, 8, 4, 4)) -> None:
        super().__init__()
        self.dims = dims
        self.board = np.zeros(dims, dtype=int)
        self.pid = np.zeros(dims, dtype=int)  # piece id map
        self.piece_info: dict[int, dict] = {}
        self._next_pid = 1
        self.slices = [0] * len(dims)
        # Only 2D view is implemented; select axes
        self.axis_pairs = [(i, j) for i in range(len(dims)) for j in range(i + 1, len(dims))]
        self.active_axes = self.axis_pairs[0]
        # Gameplay state
        self.current_player = 1  # 1 = white (positive), -1 = black (negative)
        self.selected = None  # (r, c) on current slice
        self.legal_moves = set()  # set[(r, c)] on current slice
        self.special_moves = {}  # map[(r,c)] -> {'type': 'castle_ks'|'castle_qs'|'en_passant', 'extra': {...}}
        self.last_move = None  # ((r0, c0), (r1, c1)) on current slice
        self.en_passant_target = None  # full ND index of target square
        self.en_passant_pawn_id = None
        self.history = []  # list of snapshots for undo
        self.allow_layer_shift = True
    # --- AI / NPC configuration ---
    self.ai_enabled_black = False  # Black side automated
    self.ai_enabled_white = False  # White side automated (used for self-play)
    self.self_play = False         # If True both sides automated
    self.ai_delay_ms = 400         # Delay so user can observe moves
    self.game_over = False
        self.theme = {
            'light': Qt.lightGray,
            'dark': Qt.darkGray,
            'sel': Qt.yellow,
            'move': Qt.green,
            'border': Qt.red,
            'bg': Qt.white,
        }
        # Piece symbols (Unicode)
        self.symbols = {
            1: "♙", 2: "♘", 3: "♗", 4: "♖", 5: "♕", 6: "♔",
            -1: "♟", -2: "♞", -3: "♝", -4: "♜", -5: "♛", -6: "♚",
        }
        self._init_board()
        self._setup_ui()

    def _new_pid(self, t: int, player: int) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.piece_info[pid] = {'type': t, 'player': player, 'moved': False}
        return pid

    def _place(self, idx_tuple: tuple, t: int, player: int) -> None:
        self.board[idx_tuple] = player * t
        self.pid[idx_tuple] = self._new_pid(t, player)

    def _init_board(self) -> None:
        """Initialize board with standard 8x8 chess setup."""
        if self.board.shape[0] < 8 or self.board.shape[1] < 8:
            return
        # Clear pid map and info
        self.pid[:] = 0
        self.piece_info.clear()
        first_row = [4, 2, 3, 5, 6, 3, 2, 4]
        last_row = [-p for p in first_row]
        # Place along first two axes at other slices index 0
        fixed = [0] * len(self.dims)
        ax1, ax2 = 0, 1  # initial axes assumption for setup
        for c in range(8):
            fixed[ax1] = 0
            fixed[ax2] = c
            self._place(tuple(fixed), abs(first_row[c]), 1)
            fixed[ax1] = 1
            self._place(tuple(fixed), 1, 1)
            fixed[ax1] = self.dims[ax1] - 2
            self._place(tuple(fixed), 1, -1)
            fixed[ax1] = self.dims[ax1] - 1
            self._place(tuple(fixed), abs(last_row[c]), -1)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top controls: axes, turn, buttons
        top = QHBoxLayout()
        self.axis_combo = QComboBox()
        self.axis_combo.addItems([f"Axes {i},{j}" for i, j in self.axis_pairs])
        self.axis_combo.currentIndexChanged.connect(self._set_axes)
        top.addWidget(QLabel("View:"))
        top.addWidget(self.axis_combo)

        self.turn_label = QLabel("Turn: White")
        top.addWidget(self.turn_label)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_board)
        top.addWidget(self.reset_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_game)
        top.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self._load_game)
        top.addWidget(self.load_btn)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self._undo)
        top.addWidget(self.undo_btn)

        self.options_btn = QPushButton("Options")
        self.options_btn.clicked.connect(self._open_options)
        top.addWidget(self.options_btn)

        self.rules_btn = QPushButton("How to Play")
        self.rules_btn.clicked.connect(self._show_rules)
        top.addWidget(self.rules_btn)

        # Theme combo
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Classic", "Blue", "High Contrast"])
        self.theme_combo.currentIndexChanged.connect(self._apply_theme)
        top.addWidget(QLabel("Theme:"))
        top.addWidget(self.theme_combo)

    # --- AI Control Buttons ---
    self.ai_black_btn = QPushButton("NPC Black")
    self.ai_black_btn.setCheckable(True)
    self.ai_black_btn.setToolTip("Toggle simple NPC for Black side")
    self.ai_black_btn.toggled.connect(self._toggle_ai_black)
    top.addWidget(self.ai_black_btn)

    self.self_play_btn = QPushButton("Self-Play")
    self.self_play_btn.setCheckable(True)
    self.self_play_btn.setToolTip("Let the engine play both sides")
    self.self_play_btn.toggled.connect(self._toggle_self_play)
    top.addWidget(self.self_play_btn)

    step_ai_btn = QPushButton("Step NPC")
    step_ai_btn.setToolTip("Force an immediate NPC move (if its turn)")
    step_ai_btn.clicked.connect(self._step_ai_once)
    top.addWidget(step_ai_btn)

        top.addStretch(1)
        layout.addLayout(top)

        # Status label (e.g., check info)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Board + move list side-by-side
        board_row = QHBoxLayout()
        self.canvas = BoardCanvas(self)
        board_row.addWidget(self.canvas, 4)
        self.move_list = QListWidget()
        board_row.addWidget(self.move_list, 1)
        layout.addLayout(board_row)

        # Slicing controls for non-view axes + layer shift move
        self.slice_sliders = []
        self.layer_shift_controls = []
        self.slice_rows = []  # QWidget containers for visibility toggling
        for idx, size in enumerate(self.dims):
            if idx in self.active_axes:
                self.slice_sliders.append(None)
                self.layer_shift_controls.append(None)
                self.slice_rows.append(None)
                continue
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.addWidget(QLabel(f"Dim {idx} slice:"))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, size - 1)
            slider.setValue(0)
            slider.valueChanged.connect(lambda v, i=idx: self._set_slice(i, v))
            row.addWidget(slider)

            minus_btn = QPushButton("Shift -1")
            plus_btn = QPushButton("Shift +1")
            minus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, -1))
            plus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, +1))
            row.addWidget(minus_btn)
            row.addWidget(plus_btn)

            layout.addWidget(row_widget)
            self.slice_sliders.append(slider)
            self.layer_shift_controls.append((minus_btn, plus_btn))
            self.slice_rows.append(row_widget)

    def _set_axes(self, index: int) -> None:
        self.active_axes = self.axis_pairs[index]
        for idx, row_widget in enumerate(self.slice_rows):
            if row_widget is None:
                continue
            if idx in self.active_axes:
                # Hide slicing + shift controls for active axes
                row_widget.setVisible(False)
            else:
                row_widget.setVisible(True)
        self._clear_selection()
        self.update()

    def _set_slice(self, idx: int, val: int) -> None:
        self.slices[idx] = val
        self._clear_selection()
        self.update()

    # --- Simple gameplay helpers ---
    def _reset_board(self) -> None:
        self.board[:] = 0
        self.pid[:] = 0
        self.piece_info.clear()
        self._init_board()
        self.current_player = 1
        self.turn_label.setText("Turn: White")
        self.selected = None
        self.legal_moves.clear()
        self.last_move = None
        self.status_label.setText("")
        self.history.clear()
        self.en_passant_target = None
        self.en_passant_pawn_id = None
        self.update()

    def _show_rules(self) -> None:
        text = (
            "4D Chess (demo rules):\n\n"
            "- Board: 8x8 grid with extra hidden dimensions (slices).\n"
            "- View: Pick any 2 axes to see a 2D slice; use sliders to change other dimensions.\n"
            "- Turns: White (positive pieces) then Black (negative pieces).\n"
            "- Moves: Standard chess piece moves within the current 2D slice.\n"
            "- Special: Castling and en passant supported (slice-scoped).\n"
            "- Check/mate: Check, checkmate and stalemate detection occurs in the current slice.\n"
            "- Promotion: Pawns auto-promote to a queen on the last rank.\n"
            "- 4D Layer Shift: As a full move, a selected piece may shift to an adjacent\n"
            "  slice on a non-view axis using Shift -1/+1 (if enabled). The target square must be empty.\n"
            "- Win: Capturing the opponent king also ends the game.\n\n"
            "Tip: Change axes to explore different planes; use layer shift to move between slices."
        )
        QMessageBox.information(self, "How to Play 4D Chess (Demo)", text)

    def _clear_selection(self) -> None:
        self.selected = None
        self.legal_moves.clear()
        self.update()

    def _coord_to_index(self, r: int, c: int):
        # Build full ND index tuple for current slice coordinates
        idx = list(self.slices)
        ax1, ax2 = self.active_axes
        idx[ax1] = r
        idx[ax2] = c
        return tuple(idx)

    def _get_cell(self, r: int, c: int) -> int:
        return int(self.board[self._coord_to_index(r, c)])

    def _set_cell(self, r: int, c: int, val: int) -> None:
        self.board[self._coord_to_index(r, c)] = val

    def _get_pid(self, r: int, c: int) -> int:
        return int(self.pid[self._coord_to_index(r, c)])

    def _set_pid(self, r: int, c: int, pid: int) -> None:
        self.pid[self._coord_to_index(r, c)] = pid

    def _in_bounds(self, r: int, c: int) -> bool:
        ax1, ax2 = self.active_axes
        return 0 <= r < self.dims[ax1] and 0 <= c < self.dims[ax2]

    def _ray_moves(self, r, c, dr, dc, player):
        moves = []
        rr, cc = r + dr, c + dc
        while self._in_bounds(rr, cc):
            v = self._get_cell(rr, cc)
            if v == 0:
                moves.append((rr, cc))
            else:
                if (v > 0) != (player > 0):
                    moves.append((rr, cc))
                break
            rr += dr
            cc += dc
        return moves

    def _knight_moves(self, r, c, player):
        res = []
        for dr, dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
            rr, cc = r+dr, c+dc
            if not self._in_bounds(rr, cc):
                continue
            v = self._get_cell(rr, cc)
            if v == 0 or ((v > 0) != (player > 0)):
                res.append((rr, cc))
        return res

    def _king_moves(self, r, c, player):
        res = []
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r+dr, c+dc
                if not self._in_bounds(rr, cc):
                    continue
                v = self._get_cell(rr, cc)
                if v == 0 or ((v > 0) != (player > 0)):
                    res.append((rr, cc))
        return res

    def _pawn_moves(self, r, c, player):
        res = []
        forward = 1 if player > 0 else -1
        # forward step
        rr, cc = r + forward, c
        if self._in_bounds(rr, cc) and self._get_cell(rr, cc) == 0:
            res.append((rr, cc))
            # double step from starting rank
            start_rank = 1 if player > 0 else (self.dims[self.active_axes[0]] - 2)
            rr2 = r + 2*forward
            if r == start_rank and self._in_bounds(rr2, cc) and self._get_cell(rr2, cc) == 0:
                res.append((rr2, cc))
        # captures
        for dc in (-1, 1):
            rr, cc = r + forward, c + dc
            if not self._in_bounds(rr, cc):
                continue
            v = self._get_cell(rr, cc)
            if v != 0 and ((v > 0) != (player > 0)):
                res.append((rr, cc))
        # en passant capture (if target is set and adjacent)
        if self.en_passant_target is not None:
            # map target to current slice coords
            idx = list(self._coord_to_index(r, c))
            ax1, ax2 = self.active_axes
            # target must share non-view slices and be at (r+forward, c±1)
            t = self.en_passant_target
            if all((k in (ax1, ax2)) or (t[k] == idx[k]) for k in range(len(idx))):
                tr, tc = t[ax1], t[ax2]
                if tr == r + forward and abs(tc - c) == 1:
                    res.append((tr, tc))
        return res

    def _legal_moves_for(self, r: int, c: int) -> set[tuple[int, int]]:
        v = self._get_cell(r, c)
        if v == 0:
            return set()
        player = 1 if v > 0 else -1
        t = abs(v)
        moves = []
        if t == 1:  # pawn
            moves += self._pawn_moves(r, c, player)
        elif t == 2:  # knight
            moves += self._knight_moves(r, c, player)
        elif t == 3:  # bishop
            for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                moves += self._ray_moves(r, c, dr, dc, player)
        elif t == 4:  # rook
            for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
                moves += self._ray_moves(r, c, dr, dc, player)
        elif t == 5:  # queen
            for dr, dc in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                moves += self._ray_moves(r, c, dr, dc, player)
        elif t == 6:  # king
            moves += self._king_moves(r, c, player)
            # Castling (within this slice)
            self._maybe_add_castling_moves(r, c, player, moves)
        return set(moves)

    def _maybe_add_castling_moves(self, r: int, c: int, player: int, moves_list: list):
        # Conditions: king and rook unmoved, empty between, not in check, path not attacked
        pid = self._get_pid(r, c)
        info = self.piece_info.get(pid)
        if not info or info.get('moved') or abs(self._get_cell(r, c)) != 6:
            return
        ax1, ax2 = self.active_axes
        # Rook positions in this slice: columns 0 and last on same row
        for side, rook_c in [('qs', 0), ('ks', self.dims[ax2]-1)]:
            rook_pid = self._get_pid(r, rook_c)
            rook_val = self._get_cell(r, rook_c)
            if abs(rook_val) != 4 or (1 if rook_val>0 else -1) != player:
                continue
            rinfo = self.piece_info.get(rook_pid)
            if not rinfo or rinfo.get('moved'):
                continue
            # squares between empty
            step = 1 if rook_c > c else -1
            path_cols = list(range(c+step, rook_c, step))
            if any(self._get_cell(r, cc) != 0 for cc in path_cols):
                continue
            # king path squares (excluding starting square): c + step, and c + 2*step
            kp = [c + step, c + 2*step]
            # must not be in check at start or over these squares
            if self._is_in_check(player):
                continue
            safe = True
            for kc in kp:
                if self._square_attacked(r, kc, -player):
                    safe = False
                    break
            if not safe:
                continue
            dest = (r, c + 2*step)
            moves_list.append(dest)
            # register special
            self.special_moves[dest] = {'type': f'castle_{side}', 'rook_c': rook_c, 'king_from': (r,c), 'king_to': dest}

    def _promote_if_needed(self, r: int, c: int) -> None:
        ax1, _ = self.active_axes
        v = self._get_cell(r, c)
        t = abs(v)
        if t != 1:
            return
        if (v > 0 and r == self.dims[ax1] - 1) or (v < 0 and r == 0):
            # update board value and piece type to queen
            new_val = 5 if v > 0 else -5
            self._set_cell(r, c, new_val)  # promote to queen
            pid = self._get_pid(r, c)
            if pid in self.piece_info:
                self.piece_info[pid]['type'] = 5

    def _update_check_status(self) -> None:
        # Informational: evaluate check status within the current slice only
        # Find kings on current slice
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        white_king = None
        black_king = None
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                v = int(grid[r, c])
                if v == 6:
                    white_king = (r, c)
                elif v == -6:
                    black_king = (r, c)
        status = []
        # Check if square is attacked by opponent pieces (within this slice)
        def is_attacked(target_rc, by_player):
            tr, tc = target_rc
            for rr in range(grid.shape[0]):
                for cc in range(grid.shape[1]):
                    vv = self._get_cell(rr, cc)
                    if vv == 0 or (1 if vv > 0 else -1) != by_player:
                        continue
                    moves = self._legal_moves_for(rr, cc)
                    if (tr, tc) in moves:
                        return True
            return False
        if white_king and is_attacked(white_king, -1):
            status.append("White in check (this slice)")
        if black_king and is_attacked(black_king, 1):
            status.append("Black in check (this slice)")
        self.status_label.setText(" · ".join(status))
        if not status:
            self.status_label.setText("")

    def _shift_selected(self, dim: int, delta: int) -> None:
        # Move selected piece by +/-1 slice along a non-view axis
        if self.selected is None:
            return
        if dim in self.active_axes:
            return
        if not self.allow_layer_shift:
            return
        r, c = self.selected
        src_idx = list(self._coord_to_index(r, c))
        dst_idx = src_idx.copy()
        dst_idx[dim] = max(0, min(self.dims[dim] - 1, dst_idx[dim] + delta))
        dst_idx = tuple(dst_idx)
        if dst_idx == tuple(src_idx):
            return
        val = int(self.board[tuple(src_idx)])
        if val == 0 or (1 if val > 0 else -1) != self.current_player:
            return
        if int(self.board[dst_idx]) != 0:
            return  # must be empty to shift
        # Execute shift as a full move
        self._push_history()
        self.board[tuple(src_idx)] = 0
        self.board[dst_idx] = val
        # move pid
        pid = int(self.pid[tuple(src_idx)])
        self.pid[tuple(src_idx)] = 0
        self.pid[dst_idx] = pid
        self.selected = None
        self.legal_moves.clear()
        self.last_move = None
        # Layer shift cancels en passant
        self.en_passant_target = None
        self.en_passant_pawn_id = None
        self.current_player *= -1
        self.turn_label.setText("Turn: White" if self.current_player > 0 else "Turn: Black")
        self.update()

    # --- Attack / check helpers (slice-scoped) ---
    def _square_attacked(self, r: int, c: int, by_player: int) -> bool:
        # iterate opponent pieces and see if (r,c) is in their pseudo-legal moves
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        for rr in range(grid.shape[0]):
            for cc in range(grid.shape[1]):
                v = int(grid[rr, cc])
                if v == 0 or (1 if v>0 else -1) != by_player:
                    continue
                t = abs(v)
                if t == 1:
                    # pawn attacks
                    fwd = 1 if by_player>0 else -1
                    if (rr + fwd, cc - 1) == (r, c) or (rr + fwd, cc + 1) == (r, c):
                        return True
                else:
                    # generate pseudo moves (no check filter)
                    if t == 2:
                        moves = self._knight_moves(rr, cc, by_player)
                    elif t == 3:
                        moves = []
                        for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                            moves += self._ray_moves(rr, cc, dr, dc, by_player)
                    elif t == 4:
                        moves = []
                        for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
                            moves += self._ray_moves(rr, cc, dr, dc, by_player)
                    elif t == 5:
                        moves = []
                        for dr, dc in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                            moves += self._ray_moves(rr, cc, dr, dc, by_player)
                    else:
                        moves = self._king_moves(rr, cc, by_player)
                    if (r, c) in moves:
                        return True
        return False

    def _find_king(self, player: int):
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                if int(grid[r, c]) == (6 if player>0 else -6):
                    return (r, c)
        return None

    def _is_in_check(self, player: int) -> bool:
        k = self._find_king(player)
        if not k:
            return False
        return self._square_attacked(k[0], k[1], -player)

    def _filtered_legal_moves(self, r: int, c: int):
        # Compute moves and filter out ones that leave king in check
        self.special_moves = {}
        raw = self._legal_moves_for(r, c)
        specials = dict(self.special_moves) if self.special_moves else {}
        # En passant mark if applicable
        moving_val = self._get_cell(r, c)
        if abs(moving_val) == 1 and self.en_passant_target is not None:
            ax1, ax2 = self.active_axes
            t = self.en_passant_target
            if all((k in (ax1, ax2)) or (t[k] == self.slices[k]) for k in range(len(self.slices))):
                tr, tc = t[ax1], t[ax2]
                if (tr, tc) in raw and self._get_cell(tr, tc) == 0:
                    specials[(tr, tc)] = {'type': 'en_passant'}
        legal = set()
        for dst in raw:
            if self._would_leave_king_in_check((r, c), dst, specials.get(dst)):
                continue
            legal.add(dst)
        # Keep only specials for legal destinations
        self.special_moves = {d: specials[d] for d in specials if d in legal}
        return legal

    def _would_leave_king_in_check(self, src, dst, special=None) -> bool:
        # Snapshot arrays
        board0 = self.board.copy()
        pid0 = self.pid.copy()
        info0 = {k: v.copy() for k, v in self.piece_info.items()}
        ep0 = self.en_passant_target
        ep_pid0 = self.en_passant_pawn_id
        try:
            self._apply_move(src, dst, special, simulate=True)
            return self._is_in_check(self.current_player)
        finally:
            self.board = board0
            self.pid = pid0
            self.piece_info = info0
            self.en_passant_target = ep0
            self.en_passant_pawn_id = ep_pid0

    def _push_history(self):
        snap = {
            'board': self.board.copy(),
            'pid': self.pid.copy(),
            'piece_info': {k: v.copy() for k, v in self.piece_info.items()},
            'current_player': self.current_player,
            'selected': self.selected,
            'last_move': self.last_move,
            'en_passant_target': self.en_passant_target,
            'en_passant_pawn_id': self.en_passant_pawn_id,
            'slices': list(self.slices),
            'active_axes': tuple(self.active_axes),
        }
        self.history.append(snap)

    def _undo(self) -> None:
        if not self.history:
            return
        snap = self.history.pop()
        self.board = snap['board']
        self.pid = snap['pid']
        self.piece_info = snap['piece_info']
        self.current_player = snap['current_player']
        self.selected = snap['selected']
        self.last_move = snap['last_move']
        self.en_passant_target = snap['en_passant_target']
        self.en_passant_pawn_id = snap['en_passant_pawn_id']
        self.slices = snap['slices']
        self.active_axes = snap['active_axes']
        # UI
        self.turn_label.setText("Turn: White" if self.current_player > 0 else "Turn: Black")
        self._update_check_status()
        self.update()

    def _apply_theme(self):
        t = self.theme_combo.currentText()
        if t == 'Classic':
            self.theme.update({'light': Qt.lightGray, 'dark': Qt.darkGray, 'bg': Qt.white})
        elif t == 'Blue':
            from PySide6.QtGui import QColor
            self.theme.update({'light': QColor(190,210,240), 'dark': QColor(60,90,140), 'bg': Qt.white})
        else:
            from PySide6.QtGui import QColor
            self.theme.update({'light': QColor(240,240,240), 'dark': QColor(30,30,30), 'bg': Qt.white})
        self.update()

    def _open_options(self) -> None:
        # Lightweight inline dialog constructed here to avoid new file
        from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QCheckBox, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("4D Chess Options")
        form = QFormLayout(dlg)
        sp_dims = []
        for i, val in enumerate(self.dims):
            sb = QSpinBox()
            sb.setRange(2, 16)
            sb.setValue(val)
            sp_dims.append(sb)
            form.addRow(f"Dimension {i} size", sb)
        chk_shift = QCheckBox("Enable 4D layer shift moves")
        chk_shift.setChecked(self.allow_layer_shift)
        form.addRow(chk_shift)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if not dlg.exec():
            return
        new_dims = tuple(sb.value() for sb in sp_dims)
        self.allow_layer_shift = chk_shift.isChecked()
        if new_dims != self.dims:
            # Reset game with new dims
            self._push_history()
            self.dims = new_dims
            self.board = np.zeros(self.dims, dtype=int)
            self.pid = np.zeros(self.dims, dtype=int)
            self.piece_info.clear()
            self.slices = [0] * len(self.dims)
            # rebuild axes
            self.axis_pairs = [(i, j) for i in range(len(self.dims)) for j in range(i + 1, len(self.dims))]
            self.axis_combo.clear()
            self.axis_combo.addItems([f"Axes {i},{j}" for i, j in self.axis_pairs])
            self.active_axes = self.axis_pairs[0]
            # rebuild slice rows UI
            for w in self.slice_rows:
                if w:
                    w.setParent(None)
            self.slice_sliders.clear()
            self.layer_shift_controls.clear()
            self.slice_rows.clear()
            for idx, size in enumerate(self.dims):
                if idx in self.active_axes:
                    self.slice_sliders.append(None)
                    self.layer_shift_controls.append(None)
                    self.slice_rows.append(None)
                    continue
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.addWidget(QLabel(f"Dim {idx} slice:"))
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, size - 1)
                slider.setValue(0)
                slider.valueChanged.connect(lambda v, i=idx: self._set_slice(i, v))
                row.addWidget(slider)
                minus_btn = QPushButton("Shift -1")
                plus_btn = QPushButton("Shift +1")
                minus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, -1))
                plus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, +1))
                row.addWidget(minus_btn)
                row.addWidget(plus_btn)
                self.layout().addWidget(row_widget)
                self.slice_sliders.append(slider)
                self.layer_shift_controls.append((minus_btn, plus_btn))
                self.slice_rows.append(row_widget)
            # re-init game pieces
            self._reset_board()

    def paintEvent(self, event) -> None:  # noqa: D401
        # Intentionally left blank; board is painted by BoardCanvas child.
        super().paintEvent(event)

    # Ensure board repaints when parent update() is invoked
    def update(self):  # noqa: D401
        super().update()
        if hasattr(self, 'canvas'):
            self.canvas.update()

    # --- AI / NPC Logic -------------------------------------------------
    def _toggle_ai_black(self, on: bool):
        self.ai_enabled_black = on
        if on:
            # Turning on black NPC cancels white-only automation unless self-play
            if not self.self_play:
                self.ai_enabled_white = False
        self._maybe_schedule_ai()

    def _toggle_self_play(self, on: bool):
        self.self_play = on
        if on:
            self.ai_enabled_black = True
            self.ai_black_btn.setChecked(True)
            self.ai_enabled_white = True
        else:
            self.ai_enabled_white = False
        self._maybe_schedule_ai()

    def _step_ai_once(self):
        if self.game_over:
            return
        if (self.current_player < 0 and self.ai_enabled_black) or (self.current_player > 0 and (self.ai_enabled_white or self.self_play)):
            self._perform_ai_move()

    def _maybe_schedule_ai(self):
        if self.game_over:
            return
        if (self.current_player < 0 and self.ai_enabled_black) or (self.current_player > 0 and (self.ai_enabled_white or self.self_play)):
            QTimer.singleShot(self.ai_delay_ms, self._perform_ai_move)

    def _perform_ai_move(self):
        if self.game_over:
            return
        player = self.current_player
        if (player < 0 and not self.ai_enabled_black) or (player > 0 and not (self.ai_enabled_white or self.self_play)):
            return  # User toggled off while waiting
        moves = self._all_legal_moves_for(player)
        if not moves:
            return
        best_score = None
        best_moves = []
        for src, dst, special in moves:
            sc = self._score_move(src, dst, special)
            if best_score is None or sc > best_score:
                best_score = sc
                best_moves = [(src, dst, special)]
            elif sc == best_score:
                best_moves.append((src, dst, special))
        import random
        src, dst, special = random.choice(best_moves)
        self._apply_move(src, dst, special)
        self.selected = None
        self.legal_moves.clear()
        self._post_move_checks()

    def _all_legal_moves_for(self, player: int):
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        results = []
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                v = int(grid[r, c])
                if v == 0 or (1 if v > 0 else -1) != player:
                    continue
                legal = self._filtered_legal_moves(r, c)
                specials_map = dict(self.special_moves)
                for dst in legal:
                    results.append(((r, c), dst, specials_map.get(dst)))
        return results

    def _score_move(self, src, dst, special):
        values = {1: 100, 2: 320, 3: 330, 4: 500, 5: 900, 6: 20000}
        sr, sc = src
        dr, dc = dst
        moving = abs(int(self._get_cell(sr, sc)))
        captured = abs(int(self._get_cell(dr, dc)))
        score = 0
        if captured:
            score += values.get(captured, 0) + 5 - values.get(moving, 0) * 0.01
        if moving == 1:  # pawn advancement
            direction = 1 if self._get_cell(sr, sc) > 0 else -1
            score += direction * (sr - dr) * 10
        if special and isinstance(special.get('type'), str) and special['type'].startswith('castle'):
            score += 30
        import random
        score += random.random() * 2.0
        return score

    # --- Mouse interaction ---
    def _canvas_mouse_press(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        # Recompute geometry consistent with BoardCanvas.paintEvent
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        if grid.size == 0:
            return
        w = self.canvas.width()
        h = self.canvas.height()
        off = 18
        avail_w = max(50, w - off * 2)
        avail_h = max(50, h - off * 2)
        cell_w = avail_w / grid.shape[1]
        cell_h = avail_h / grid.shape[0]
        cell = int(min(72, cell_w, cell_h))
        board_w = cell * grid.shape[1]
        board_h = cell * grid.shape[0]
        start_x = (w - board_w) // 2
        start_y = (h - board_h) // 2
        pos = getattr(self, '_forwarded_mouse_event_pos', event.position())
        x = pos.x()
        y = pos.y()
        if x < start_x or y < start_y or x >= start_x + board_w or y >= start_y + board_h:
            return
        col = int((x - start_x) // cell)
        row = int((y - start_y) // cell)
        if not self._in_bounds(row, col):
            return
        val = self._get_cell(row, col)
        if self.selected is None:
            if val == 0:
                return
            player = 1 if val > 0 else -1
            if player != self.current_player:
                return
            self.selected = (row, col)
            # reset specials, compute filtered legal moves
            self.special_moves = {}
            self.legal_moves = self._filtered_legal_moves(row, col)
            self.update()
            return
        # If clicking on a legal move, execute it
        if (row, col) in self.legal_moves:
            src = self.selected
            dst = (row, col)
            special = self.special_moves.get(dst)
            self._apply_move(src, dst, special)
            self.selected = None
            self.legal_moves.clear()
            self._post_move_checks()
            return
        # Otherwise, update selection if clicking own piece, or clear
        if val != 0 and (1 if val > 0 else -1) == self.current_player:
            self.selected = (row, col)
            self.legal_moves = self._legal_moves_for(row, col)
        else:
            self.selected = None
            self.legal_moves.clear()
        self._update_check_status()
        self.update()
    # Backwards compatibility if parent receives clicks directly
    def mousePressEvent(self, event) -> None:  # pragma: no cover - prefer canvas events
        self._canvas_mouse_press(event)

    # --- Move execution and game state ---
    def _square_to_notation(self, r: int, c: int) -> str:
        file = chr(ord('a') + c)
        rank = str(self.dims[self.active_axes[0]] - r)
        return f"{file}{rank}"

    def _post_move_checks(self):
        # Switch turn already done in _apply_move
        self.turn_label.setText("Turn: White" if self.current_player > 0 else "Turn: Black")
        self._update_check_status()
        # Mate/stalemate detection within slice
        player = self.current_player
        has_move = self._has_any_legal_move(player)
        in_check = self._is_in_check(player)
        if not has_move:
            if in_check:
                QMessageBox.information(self, "Checkmate", ("Black" if player>0 else "White") + " wins (checkmate)")
            else:
                QMessageBox.information(self, "Stalemate", "No legal moves (this slice)")
        self.update()

    def _has_any_legal_move(self, player: int) -> bool:
        ax1, ax2 = self.active_axes
        fixed = [slice(None) if i in self.active_axes else self.slices[i] for i in range(len(self.dims))]
        grid = self.board[tuple(fixed)]
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                v = int(grid[r, c])
                if v == 0 or (1 if v>0 else -1) != player:
                    continue
                # compute moves
                self.special_moves = {}
                raw = self._filtered_legal_moves(r, c)
                if raw:
                    return True
        return False

    def _apply_move(self, src, dst, special=None, simulate=False):
        # Save history if real move
        if not simulate:
            self._push_history()
        # Clear en passant by default
        prev_en_passant = (self.en_passant_target, self.en_passant_pawn_id)
        self.en_passant_target = None
        self.en_passant_pawn_id = None
        moving_val = self._get_cell(*src)
        moving_pid = self._get_pid(*src)
        player = 1 if moving_val>0 else -1
        capture_val = self._get_cell(*dst)
        capture_pid = self._get_pid(*dst)
        # En passant capture handling
        if special and special.get('type') == 'en_passant':
            # remove the pawn that moved two squares (behind dst)
            ax1, ax2 = self.active_axes
            fwd = -1 if player>0 else 1  # captured pawn is behind destination relative to mover
            cap_r, cap_c = dst[0] + fwd, dst[1]
            self._set_cell(cap_r, cap_c, 0)
            self._set_pid(cap_r, cap_c, 0)
            capture_val = 1 * (-player)  # for notation
        # Castling: move rook too
        if special and special.get('type', '').startswith('castle_'):
            side = 'ks' if 'ks' in special['type'] else 'qs'
            rook_from_c = special['rook_c']
            step = 1 if rook_from_c > src[1] else -1
            king_to = special['king_to']
            rook_to_c = king_to[1] - step
            # move rook
            rook_val = self._get_cell(src[0], rook_from_c)
            rook_pid = self._get_pid(src[0], rook_from_c)
            self._set_cell(src[0], rook_from_c, 0)
            self._set_pid(src[0], rook_from_c, 0)
            self._set_cell(src[0], rook_to_c, rook_val)
            self._set_pid(src[0], rook_to_c, rook_pid)
            if rook_pid in self.piece_info:
                self.piece_info[rook_pid]['moved'] = True
        # Move piece
        self._set_cell(*src, 0)
        self._set_pid(*src, 0)
        self._set_cell(*dst, moving_val)
        self._set_pid(*dst, moving_pid)
        if moving_pid in self.piece_info:
            self.piece_info[moving_pid]['moved'] = True
        # Promotion
        self._promote_if_needed(*dst)
        # If pawn double-stepped, set en passant target
        if abs(moving_val) == 1 and capture_val == 0 and src[1] == dst[1] and abs(dst[0]-src[0]) == 2:
            mid_r = (src[0] + dst[0]) // 2
            mid_c = src[1]
            self.en_passant_target = self._coord_to_index(mid_r, mid_c)
            self.en_passant_pawn_id = moving_pid
        # Notation and turn update (only if real)
        if not simulate:
            # Detect king capture (direct move capture)
            if abs(capture_val) == 6:
                winner = "White" if self.current_player > 0 else "Black"
                QMessageBox.information(self, "Game Over", f"{winner} wins (king captured)")
            # Notation string
            note = self._move_to_string(src, dst, moving_val, capture_val, special)
            prefix = "W:" if self.current_player > 0 else "B:"
            self.move_list.addItem(f"{prefix} {note}")
            self.last_move = (src, dst)
            self.current_player *= -1

    def _move_to_string(self, src, dst, moving_val, capture_val, special):
        # Castle notation
        if special and special.get('type','').startswith('castle_'):
            return "O-O" if 'ks' in special['type'] else "O-O-O"
        # Piece letter
        t = abs(moving_val)
        piece = {1:'',2:'N',3:'B',4:'R',5:'Q',6:'K'}[t]
        s = ''
        if t == 1 and capture_val != 0:
            s += chr(ord('a') + src[1])
        s += piece
        if capture_val != 0:
            s += 'x'
        s += self._square_to_notation(*dst)
        # Promotion marker
        dst_val = self._get_cell(*dst)
        if t == 1 and abs(dst_val) == 5 and (abs(dst[0]-src[0])>0):
            s += "=Q"
        return s

    # --- Save / Load ---
    def _save_game(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save 4D Chess Game", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            import json
            data = {
                "dims": list(self.dims),
                "board": self.board.tolist(),
                "pid": self.pid.tolist(),
                "piece_info": self.piece_info,
                "slices": list(self.slices),
                "active_axes": list(self.active_axes),
                "current_player": int(self.current_player),
                "last_move": list(self.last_move) if self.last_move else None,
                "en_passant_target": list(self.en_passant_target) if self.en_passant_target else None,
                "en_passant_pawn_id": int(self.en_passant_pawn_id) if self.en_passant_pawn_id else None,
                "allow_layer_shift": bool(self.allow_layer_shift),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            self.status_label.setText(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_game(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load 4D Chess Game", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            dims = tuple(int(x) for x in data.get("dims", self.dims))
            board_list = data.get("board")
            arr = np.array(board_list, dtype=int)
            if arr.shape != dims:
                raise ValueError("Board shape does not match dims in file")
            self.dims = dims
            self.board = arr
            pid_list = data.get("pid")
            if pid_list is not None:
                self.pid = np.array(pid_list, dtype=int)
            else:
                self.pid = np.zeros(self.dims, dtype=int)
            self.piece_info = {int(k): v for k, v in data.get("piece_info", {}).items()}
            self.slices = list(data.get("slices", self.slices))
            self.active_axes = tuple(data.get("active_axes", self.active_axes))
            self.current_player = int(data.get("current_player", 1))
            self.last_move = tuple(map(tuple, data["last_move"])) if data.get("last_move") else None
            ep = data.get("en_passant_target")
            self.en_passant_target = tuple(ep) if ep is not None else None
            self.en_passant_pawn_id = data.get("en_passant_pawn_id")
            self.allow_layer_shift = bool(data.get("allow_layer_shift", True))
            self.selected = None
            self.legal_moves.clear()
            # Rebuild axes menu to reflect possibly different dims
            self.axis_pairs = [(i, j) for i in range(len(self.dims)) for j in range(i + 1, len(self.dims))]
            self.axis_combo.clear()
            self.axis_combo.addItems([f"Axes {i},{j}" for i, j in self.axis_pairs])
            try:
                idx = self.axis_pairs.index(self.active_axes)
            except Exception:
                idx = 0
                self.active_axes = self.axis_pairs[0]
            self.axis_combo.setCurrentIndex(idx)
            # Rebuild slice rows to match new dims
            for w in self.slice_rows:
                if w:
                    w.setParent(None)
            self.slice_sliders.clear()
            self.layer_shift_controls.clear()
            self.slice_rows.clear()
            # Recreate sliders
            for idx, size in enumerate(self.dims):
                if idx in self.active_axes:
                    self.slice_sliders.append(None)
                    self.layer_shift_controls.append(None)
                    self.slice_rows.append(None)
                    continue
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.addWidget(QLabel(f"Dim {idx} slice:"))
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, size - 1)
                slider.setValue(self.slices[idx] if idx < len(self.slices) else 0)
                slider.valueChanged.connect(lambda v, i=idx: self._set_slice(i, v))
                row.addWidget(slider)
                minus_btn = QPushButton("Shift -1")
                plus_btn = QPushButton("Shift +1")
                minus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, -1))
                plus_btn.clicked.connect(lambda _=False, i=idx: self._shift_selected(i, +1))
                row.addWidget(minus_btn)
                row.addWidget(plus_btn)
                self.layout().addWidget(row_widget)
                self.slice_sliders.append(slider)
                self.layer_shift_controls.append((minus_btn, plus_btn))
                self.slice_rows.append(row_widget)
            self.turn_label.setText("Turn: White" if self.current_player > 0 else "Turn: Black")
            self.status_label.setText(f"Loaded: {path}")
            self._update_check_status()
            self.update()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
