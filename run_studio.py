"""Launch the optional AdaptiveCAD Studio GUI from a repository checkout."""
from __future__ import annotations
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="AdaptiveCAD Studio native CAD workspace")
    parser.add_argument("file", nargs="?", help="Native .acstudio document")
    parser.add_argument("--safe-mode", action="store_true", help="Disable OpenGL; keep document and sketch tools")
    parser.add_argument("--demo", action="store_true", help="Open the editable analytic bearing demo")
    parser.add_argument("--no-recovery", action="store_true", help="Do not offer recovery snapshots at startup")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from adaptivecad.studio.window import StudioWindow
    except ImportError as exc:
        print(f"Studio dependencies are missing: {exc}\nInstall with: python -m pip install -r requirements-studio.txt", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("AdaptiveCAD")
    app.setApplicationName("Studio")
    window = StudioWindow(safe_mode=args.safe_mode)
    if args.file:
        window.guarded(lambda: window.open_path(args.file))
    if args.demo:
        window.guarded(window.add_demo)
    window.show()
    if not args.no_recovery:
        QTimer.singleShot(0, window.offer_recovery)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
