"""Validate saved ARP GT-01 geometry independently of the construction process."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent


def require(condition: bool, message: str) -> None:
    """Do not use assert: these checks must survive python -O."""
    if not condition:
        raise ValueError(message)


def validate(model: Path, repo: Path, *, skip_step: bool = False) -> dict:
    sys.path.insert(0, str(repo.resolve()))
    import cadquery as cq
    from adaptivecad.geom.bezier import BezierCurve
    from adaptivecad.geom.cadquery_bridge import triangulated_face_count
    from adaptivecad.linalg import Vec3

    t0 = time.time()
    meta = json.loads((model / 'ARP_GT01.design.json').read_text(encoding='utf-8'))
    scale = float(meta['scale'])
    require(math.isfinite(scale) and scale > 0, 'Invalid manifest scale')
    parts = meta['parts']
    require(bool(parts), 'Manifest has no parts')
    require(len({p['name'] for p in parts}) == len(parts), 'Duplicate part names')
    expected_solids = sum(p['solids'] for p in parts)
    expected_volume = sum(p['volume_mm3'] for p in parts)
    require(expected_solids > 0 and expected_volume > 0, 'Empty assembly')
    result = {'expected_solids': expected_solids, 'scale': scale}
    hashes = {}
    for relative, expected in meta['source_files'].items():
        source = (repo / relative).resolve()
        require(source.is_relative_to(repo.resolve()), 'Source path escapes the repository')
        raw = source.read_bytes()
        actual = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        hashes[relative] = actual
        require(actual == expected, f'Source version differs from build: {relative}')
    result['upstream_source_hashes'] = hashes
    error = 0.0
    for data in meta['curves']:
        curve = BezierCurve([Vec3(*p) for p in data['control_points']])
        left, right = curve.subdivide(0.37)
        for j in range(21):
            t = j / 20
            error = max(error, (left.evaluate(t) - curve.evaluate(.37*t)).norm(),
                        (right.evaluate(t) - curve.evaluate(.37+.63*t)).norm())
    require(error < 1e-8, 'Bezier subdivision check failed')
    result['max_subdivision_error_unscaled_mm'] = error
    native = cq.Shape.importBrep(str(model / 'ARP_GT01.brep'))
    require(native.isValid(), 'Invalid native BREP')
    require(len(native.Solids()) == expected_solids, 'BREP solid count mismatch')
    require(all(s.isValid() and s.Volume() > 0 for s in native.Solids()), 'Invalid native solid')
    triangles = triangulated_face_count(native)
    require(triangles == 0, 'Native BREP contains display triangulations')
    result['native_brep_faces_with_display_triangulation'] = triangles
    result['native_solids'] = len(native.Solids())
    volume_error = abs(sum(s.Volume() for s in native.Solids())-expected_volume)/expected_volume
    require(volume_error < 1e-8, 'BREP volume sum mismatch')
    result['brep_volume_sum_relative_error'] = volume_error
    shapes = {}
    for part in parts:
        path = (model / part['brep']).resolve()
        require(path.is_relative_to(model.resolve()), 'Part path escapes model directory')
        shape = cq.Shape.importBrep(str(path))
        require(shape.isValid(), f"Invalid part: {part['name']}")
        require(len(shape.Solids()) == part['solids'], f"Part solid count mismatch: {part['name']}")
        require(triangulated_face_count(shape) == 0, f"Part has a display mesh: {part['name']}")
        shapes[part['name']] = shape
    result['validated_parts'] = len(shapes)
    if not skip_step:
        require(meta.get('step_exported', True), 'Build omitted STEP; explicitly use --skip-step')
        path = model / 'ARP_GT01.step'
        text = path.read_text(encoding='utf-8', errors='replace')
        keywords = ('TRIANGULATED_FACE', 'TESSELLATED_SHELL', 'TESSELLATED_FACE', 'TRIANGULATED_FACE_SET')
        counts = {word: text.count(word) for word in keywords}
        require(not any(counts.values()), 'STEP contains tessellated geometry entities')
        step = cq.importers.importStep(str(path)).val()
        require(step.isValid(), 'Invalid STEP round trip')
        require(len(step.Solids()) == expected_solids, 'STEP solid count mismatch')
        require(all(s.isValid() for s in step.Solids()), 'Invalid STEP solid')
        error = abs(sum(s.Volume() for s in step.Solids())-expected_volume)/expected_volume
        require(error < 1e-6, 'STEP volume sum mismatch')
        bb = step.BoundingBox()
        bounds = [bb.xlen, bb.ylen, bb.zlen]
        require(all(abs(a-b) < max(1e-7, .001*scale) for a, b in zip(bounds, meta['bounds_mm'])),
                'STEP bounds mismatch')
        result.update(step_roundtrip_valid=True, step_roundtrip_solids=len(step.Solids()),
                      step_volume_sum_relative_error=error, step_mesh_entity_counts=counts)
    else:
        result['step_roundtrip_valid'] = None
        result['step_check'] = 'Explicitly skipped; not a verified STEP round trip'
    body = shapes['Body_sculpted_Bezier_loft']
    collisions = {}
    for name, shape in shapes.items():
        if name.endswith('Tire_grooved'):
            volume = body.intersect(shape).Volume()
            require(abs(volume) < max(1e-12, 1e-5*scale**3), f'Tire/body overlap: {name}')
            collisions[name] = volume
    result['nominal_body_tire_overlap_mm3'] = collisions
    result['status'] = 'PASS_BREP_ONLY' if skip_step else 'PASS'
    result['seconds'] = time.time() - t0
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=ROOT / 'model')
    parser.add_argument('--repo', type=Path, default=ROOT.parents[1])
    parser.add_argument('--skip-step', action='store_true', help='Report BREP-only validation explicitly')
    args = parser.parse_args(argv)
    model = args.model.resolve()
    report = model / 'independent_validation.json'
    try:
        result = validate(model, args.repo.resolve(), skip_step=args.skip_step)
    except Exception as exc:
        # Replace a stale PASS report on failure. Keep the original exception visible.
        if model.is_dir():
            report.write_text(json.dumps({'status': 'FAIL', 'error': str(exc)}, indent=2), encoding='utf-8')
        parser.exit(1, f'Validation failed: {exc}\n')
    report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
