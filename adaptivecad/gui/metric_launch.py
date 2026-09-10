"""Launch the existing CAD application with the integrated metric-tools dock.

No second demo application is created. Both backends keep their existing scene,
menus and commands. Importing this module does not import Qt or start a GUI.
"""
from __future__ import annotations

import argparse
import sys


def build_window(ui="playground"):
    from .metric_workbench import install_metric_workbench
    if ui == "playground":
        from .playground import MainWindow
        window = MainWindow()
        install_metric_workbench(window)
        return window
    if ui == "sdf":
        from adaptivecad.app.main_window import AdaptiveCADApp
        window = AdaptiveCADApp()
        install_metric_workbench(window)
        return window
    raise ValueError("Unknown UI: use playground or sdf")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui",choices=("playground","sdf"),default="playground")
    args=parser.parse_args(argv)
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("AdaptiveCAD")
    app.setOrganizationName("AdaptiveCAD")
    app.setOrganizationDomain("adaptivecad.io")
    window=build_window(args.ui)
    if args.ui=="playground":
        return window.run() or 0
    window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
