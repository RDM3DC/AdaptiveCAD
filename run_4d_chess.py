#!/usr/bin/env python
"""Standalone launcher for the AdaptiveCAD N‑Dimensional (4D) Chess demo.

This avoids importing the full playground / OCC stack so you only need:
  - numpy
  - pyside6

Usage:
  python run_4d_chess.py                # default dims (8,8,4,4)
  python run_4d_chess.py --dims 8 8 3 3  # custom N-d board

On macOS you may optionally set (helps on some configurations):
  export QT_MAC_WANTS_LAYER=1

Press "How to Play" inside the UI for simplified 4D rule summary.
"""
from __future__ import annotations

import os
import sys
import argparse

# Fail fast with a friendly message if PySide6 not installed.
try:
    from PySide6.QtWidgets import QApplication
except ImportError as e:  # pragma: no cover - environment issue
    print("ERROR: PySide6 is not installed. Install with:\n  conda install -c conda-forge pyside6")
    raise SystemExit(1) from e

try:
    import numpy as np  # noqa: F401  (ensure dependency present)
except ImportError as e:  # pragma: no cover
    print("ERROR: numpy is not installed. Install with:\n  conda install -c conda-forge numpy")
    raise SystemExit(1) from e

# Import the widget (only PySide6 + numpy required)
try:
    from adaptivecad.gui.nd_chess_widget import NDChessWidget
except Exception as e:  # pragma: no cover - unexpected
    print(f"ERROR: Could not import NDChessWidget: {e}")
    raise SystemExit(1) from e


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Launch the AdaptiveCAD N-D Chess demo.")
    p.add_argument(
        "--dims",
        metavar="D",
        type=int,
        nargs="+",
        default=[8, 8, 4, 4],
        help="Board dimensions (at least 2 axes of length >= 2). Default: 8 8 4 4",
    )
    p.add_argument(
        "--no-layer-shift",
        action="store_true",
        help="Disable the 4D layer shift move mechanic.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    dims = tuple(args.dims)
    if len(dims) < 2:
        print("ERROR: Need at least two dimensions to render a 2D slice.")
        raise SystemExit(2)

    # Basic sanity: ensure first two dims large enough for standard setup if >=8
    if dims[0] < 8 or dims[1] < 8:
        print("WARNING: First two dimensions < 8; standard chess starting layout may be truncated.")

    app = QApplication.instance() or QApplication(sys.argv)
    w = NDChessWidget(dims=dims)
    if args.no_layer_shift:
        w.allow_layer_shift = False
    w.setWindowTitle(f"AdaptiveCAD ND Chess – dims={dims}")
    w.resize(900, 700)
    w.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
