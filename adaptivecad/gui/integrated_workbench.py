"""One launch for the existing mesh-free window and independent metric dock.

No implicit chart/world conversion, shared undo history, or automatic file migration.
Qt is loaded only when a window is constructed, not on module import.
"""
from __future__ import annotations

import argparse
import sys


def install_integrated_tools(window):
    """Add both tools once to an existing QMainWindow or Playground controller."""
    from .curve_transfer import install_curve_transfer
    from .meshfree_workbench import install_meshfree_tools
    from .metric_dock_layout import prepare_metric_dock
    from .metric_workbench import install_metric_workbench

    host = getattr(window, "win", window)
    dock = install_metric_workbench(host)
    if not getattr(host, "_integrated_metric_layout_ready", False):
        prepare_metric_dock(host, dock)
        dock.setStyleSheet(dock.styleSheet() + "\nQDockWidget::title { background: #303c4c; color: #dce5ef; padding: 4px; }")
        host._integrated_metric_layout_ready = True
    action = install_meshfree_tools(host, guard_unsaved=True)
    if not getattr(host, "_curve_transfer_child_hook", None):
        def attach_transfer():
            install_curve_transfer(host._meshfree_window, dock)
        action.triggered.connect(attach_transfer)
        host._curve_transfer_child_hook = attach_transfer
    child = getattr(host, "_meshfree_window", None)
    if child is not None:
        install_curve_transfer(child, dock)
    return dock


def create_integrated_workbench(document=None, metric_project=None):
    """Reuse the stable modeling window as host; the dock owns its own project."""
    from .curve_transfer import install_curve_transfer
    from .meshfree_workbench import create_workbench
    from .metric_dock_layout import prepare_metric_dock
    from .metric_workbench import install_metric_workbench

    window = create_workbench(document=document, guard_unsaved=True)
    dock = install_metric_workbench(window)
    prepare_metric_dock(window, dock)
    dock.setStyleSheet(dock.styleSheet() + "\nQDockWidget::title { background: #303c4c; color: #dce5ef; padding: 4px; }")
    # Give extra height to the modeling area, not the header label or button bar.
    window.centralWidget().layout().setStretch(2, 1)
    window._integrated_metric_layout_ready = True
    if metric_project is not None:
        dock.history.reset(metric_project)
        dock._refresh()
    install_curve_transfer(window, dock)
    # No second modeling child window is installed into the modeling window.
    window.resize(1520, 860)
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", help="Existing mesh-free document JSON")
    parser.add_argument("--metric-project", help="Existing .acmetric.json project")
    parser.add_argument("--demo", action="store_true", help="Load an in-memory modeling demo; writes no files")
    args = parser.parse_args(argv)
    if args.demo and args.document:
        parser.error("Use --demo or --document, not both")
    try:
        from adaptivecad.geom.tool_document import ToolDocument
        from adaptivecad.metric_project import MetricProject
        # Validate inputs before constructing any windows or replacing state.
        document = ToolDocument.load(args.document) if args.document else None
        project = MetricProject.load(args.metric_project) if args.metric_project else None
        if args.demo:
            from examples.meshfree_toolkit_demo import demo_session
            document = demo_session().document
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([sys.argv[0]])
        window = create_integrated_workbench(document, project)
        if args.demo:
            window._saved_document = ToolDocument()
            window.refresh()
        window.show()
        return app.exec()
    except (ImportError, RuntimeError, ValueError, OSError, TypeError) as exc:
        print(f"Cannot launch integrated workbenches: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
