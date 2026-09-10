"""Launch an existing CAD host with both independently owned workbenches.

Importing this module does not import Qt or start an application.
"""
from __future__ import annotations

import argparse
import sys


def build_window(ui="playground"):
    from .integrated_workbench import install_integrated_tools

    if ui == "playground":
        from .playground import MainWindow
        window = MainWindow()
    elif ui == "sdf":
        from adaptivecad.app.main_window import AdaptiveCADApp
        window = AdaptiveCADApp()
    else:
        raise ValueError("Unknown UI: use playground or sdf")
    install_integrated_tools(window)
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", choices=("playground", "sdf"), default="playground")
    args = parser.parse_args(argv)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("AdaptiveCAD")
    app.setOrganizationName("AdaptiveCAD")
    app.setOrganizationDomain("adaptivecad.io")
    window = build_window(args.ui)
    if args.ui == "playground":
        return window.run() or 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
