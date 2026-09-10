"""Exercise the metric dock inside a real existing app; run under a desktop/Xvfb.

No OCC geometry or machine output is certified by this smoke test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from adaptivecad.gui.metric_launch import build_window


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui', choices=('sdf', 'playground'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([sys.argv[0]])

    def unexpected_dialog(*values, **kwargs):
        raise RuntimeError('Unexpected application dialog: ' + str(values[1:3]))

    QMessageBox.warning = unexpected_dialog
    QMessageBox.critical = unexpected_dialog
    window = build_window(args.ui)
    host = getattr(window, 'win', window)
    dock = host._metric_workbench
    menu_names = [a.text() for a in host.menuBar().actions()]
    if len(menu_names) < 2 or 'Metric tools' not in menu_names:
        raise AssertionError('Existing application menus were not preserved')
    if args.ui == 'sdf':
        scene = window.scene
        before = [id(p) for p in scene.prims]
    else:
        from adaptivecad.command_defs import DOCUMENT
        before = [id(p) for p in DOCUMENT]
    dock.show()
    dock.raise_()
    host.resize(1700, 1000)
    host.show()
    app.processEvents()
    dock.preset.setCurrentIndex(1)
    dock.use_preset()
    dock.new_curve()
    dock.apply_editors()
    dock.measure_curve()
    if dock.last_report['result']['length']['value'] <= 0:
        raise AssertionError('Invalid curve measurement')
    dock.run_trace()
    dock.heatmap.setChecked(True)
    dock.tabs.setCurrentIndex(3)
    app.processEvents()
    if args.ui == 'sdf':
        after = [id(p) for p in scene.prims]
    else:
        after = [id(p) for p in DOCUMENT]
    if before != after:
        raise AssertionError('Metric edits changed existing CAD scene membership')
    project_path = args.output / (args.ui + '.acmetric.json')
    dock.history.current.save(project_path, overwrite=True)
    if not host.grab().save(str(args.output / (args.ui + '.png'))):
        raise AssertionError('Screenshot failed')
    report = {'status': 'PASS', 'ui': args.ui, 'menus': menu_names,
              'scene_object_count': len(before), 'scene_membership_unchanged': True,
              'trace_status': dock.trace.status,
              'project_sha256': hashlib.sha256(project_path.read_bytes()).hexdigest(),
              'limitations': 'Startup/dock integration only; not full CAD, OCC or GPU rendering validation.'}
    (args.output / (args.ui + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    dock.history.mark_saved()
    host.removeEventFilter(dock)
    host.close()
    app.processEvents()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
