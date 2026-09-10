"""Run the mesh-free toolkit and write a document, report and HTML wireframe.

python -m examples.meshfree_toolkit_demo --out meshfree_demo_output
Files are never overwritten. The HTML is a display approximation, not geometry.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from adaptivecad.geom.directional_metric import balanced_directional_patch
from adaptivecad.geom.meshfree_tools import Surface, wireframe
from adaptivecad.geom.metric_tools import disk_area, trace_geodesic
from adaptivecad.geom.tool_document import ToolSession


def demo_session():
    session = ToolSession()
    session.execute_many([
        {'op': 'arc', 'name': 'circle', 'radius': 10},
        {'op': 'line', 'name': 'line', 'start': [10, 0, 0], 'end': [10, 0, 20]},
        {'op': 'bezier', 'name': 'profile', 'points': [[0, 0, 0], [8, 0, 2], [10, 0, 10], [3, 0, 20]]},
        {'op': 'extrude', 'name': 'extrusion', 'source': 'circle', 'vector': [0, 0, 20]},
        {'op': 'revolve', 'name': 'partial_revolution', 'source': 'line', 'axis': [0, 0, 1], 'angle': 1.5*math.pi},
        {'op': 'scale', 'name': 'small_circle', 'source': 'circle', 'factor': .5},
        {'op': 'move', 'name': 'circle_top', 'source': 'small_circle', 'delta': [3, 0, 20]},
        {'op': 'loft', 'name': 'ruled_loft', 'source': 'circle', 'target': 'circle_top'},
        {'op': 'sweep', 'name': 'translation_sweep', 'source': 'circle', 'path': 'profile'},
        {'op': 'set_metric', 'metric': json.loads(balanced_directional_patch().to_json())},
    ])
    return session


def preview_html(document):
    cards = []
    for name, entity in document.entities:
        if not isinstance(entity, Surface):
            continue
        projected = [[(.8660254*(x-y), .5*(x+y)-z) for x, y, z in path]
                     for path in wireframe(entity)]
        values = [p for path in projected for p in path]
        xmin, xmax = min(x for x, _ in values), max(x for x, _ in values)
        ymin, ymax = min(y for _, y in values), max(y for _, y in values)
        scale = max(xmax-xmin, ymax-ymin, 1e-100)
        paths = []
        for poly in projected:
            pts = ' '.join(f'{25+(x-xmin)*350/scale:.4f},{25+(y-ymin)*350/scale:.4f}' for x, y in poly)
            paths.append(f'<polyline points="{pts}"/>')
        cards.append(f'<section><h2>{html.escape(name)}</h2><svg viewBox="0 0 400 400" role="img" '
                     f'aria-label="{html.escape(name, quote=True)} wireframe">{"".join(paths)}</svg>'
                     f'<p>Evaluated {html.escape(entity.kind)} sheet. Unit: {html.escape(document.unit)}.</p></section>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AdaptiveCAD — mesh-free toolkit</title><style>
body{font:16px system-ui,sans-serif;max-width:1200px;margin:36px auto;padding:0 22px;background:#f5f6f8;color:#192333}
h1{font-size:32px;margin-bottom:8px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:20px}
section{background:white;border:1px solid #cdd4dc;border-radius:12px;padding:22px}h2{font-size:20px}
svg{width:100%;max-height:360px}polyline{fill:none;stroke:#194e83;stroke-width:1.1;stroke-linejoin:round}
p{line-height:1.55}footer{margin-top:24px;padding:18px;border-top:1px solid #cdd4dc}</style>
<header><h1>AdaptiveCAD | Mesh-free tool set</h1><p>Four surfaces evaluated from coefficients and construction rules.
No triangle mesh is stored in the accompanying JSON document.</p></header><main>''' + ''.join(cards) + '''</main>
<footer>This preview samples isoparametric curves for display. It is not exact display geometry, a watertight solid,
a manufacturing path, or a claim of zero numerical error. The editable model is in document.json.
Launch the separate desktop workbench with <code>python -m adaptivecad.gui.meshfree_workbench</code>.</footer></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('meshfree_demo_output'))
    args = parser.parse_args(argv)
    out = args.out
    paths = [out/n for n in ('document.json', 'preview.html', 'report.json')]
    if any(p.exists() for p in paths):
        parser.error('Output files already exist; select a new --out directory')
    session = demo_session()
    document = session.document
    patch = document.metric
    path = trace_geodesic(patch, (-.2, .2), (1, .1), .5, transport=(0, 1))
    report = {'status': 'numerical demonstration, not manufacturing validation', 'unit': document.unit,
              'surfaces': {}, 'metric': {'circle_pi_at_0.75': patch.circle_pi(.75).value,
                  'disk_area_at_0.75': disk_area(patch, .75).value,
                  'geodesic_endpoint': path.positions[-1], 'geodesic_completed_length': path.length,
                  'geodesic_max_speed_drift': path.max_speed_drift}}
    for name, entity in document.entities:
        if isinstance(entity, Surface):
            report['surfaces'][name] = {'parameter_area': entity.area().value,
                                       'midpoint': entity.differential(.4, .4)}
    text = preview_html(document)
    out.mkdir(parents=True, exist_ok=True)
    document.save(paths[0])
    with paths[1].open('x', encoding='utf-8') as f:
        f.write(text)
    with paths[2].open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, allow_nan=False)
    print(f'Wrote {out}: document.json, preview.html, report.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
