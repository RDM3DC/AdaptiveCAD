"""Export exact line, circle, rectangle and cubic-Bezier definitions to SVG."""
from __future__ import annotations
import html
import math
from .document import atomic_write, validate_entity


def sketch_svg(sketch):
    items, xs, ys = [], [], []
    for entity in sketch["entities"]:
        validate_entity(entity)
        points, kind = entity["points"], entity["kind"]
        for x,y in points:
            xs.append(x)
            ys.append(y)
        a,b = points[:2]
        if kind == "circle":
            r = math.dist(a,b)
            xs.extend([a[0]-r,a[0]+r])
            ys.extend([a[1]-r,a[1]+r])
            items.append(f'<circle cx="{a[0]:.17g}" cy="{a[1]:.17g}" r="{r:.17g}"/>')
        elif kind == "rectangle":
            items.append(f'<rect x="{min(a[0],b[0]):.17g}" y="{min(a[1],b[1]):.17g}" width="{abs(a[0]-b[0]):.17g}" height="{abs(a[1]-b[1]):.17g}"/>')
        elif kind == "line":
            items.append(f'<path d="M {a[0]:.17g} {a[1]:.17g} L {b[0]:.17g} {b[1]:.17g}"/>')
        else:
            coords = ' '.join(f'{p[0]:.17g} {p[1]:.17g}' for p in points[1:])
            items.append(f'<path d="M {a[0]:.17g} {a[1]:.17g} C {coords}"/>')
    if not xs:
        raise ValueError("The sketch is empty.")
    margin = max(1., .03*max(max(xs)-min(xs), max(ys)-min(ys)))
    x,y = min(xs)-margin, -max(ys)-margin
    width,height = max(xs)-min(xs)+2*margin, max(ys)-min(ys)+2*margin
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.17g}mm" height="{height:.17g}mm" viewBox="{x:.17g} {y:.17g} {width:.17g} {height:.17g}">\n'
            f'<title>{html.escape(sketch["name"])}</title>\n'
            '<g transform="scale(1,-1)" fill="none" stroke="#173c63" stroke-width="0.25">\n'
            + '\n'.join(items) + '\n</g>\n</svg>\n')


def export_sketch(sketch,path):
    atomic_write(path,sketch_svg(sketch))
