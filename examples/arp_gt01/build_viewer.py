"""Build a self-contained inspection viewer from display-only BREP tessellation."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_viewer(template: Path, payload: dict, destination: Path) -> None:
    """Embed JSON safely inside a script, including arbitrary component names."""
    html = template.read_text(encoding='utf-8')
    if html.count('__MODEL_JSON__') != 1:
        raise ValueError('Viewer template must contain exactly one model placeholder')
    data = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html.replace('__MODEL_JSON__', data), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=ROOT / 'model')
    parser.add_argument('--out', type=Path, default=ROOT, help='Viewer and preview-cache directory')
    args = parser.parse_args(argv)
    import numpy as np
    import cadquery as cq
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray,vtk_to_numpy
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    R=args.out.resolve();D=args.model.resolve()
    meta=json.loads((D/'ARP_GT01.design.json').read_text(encoding='utf-8'));scale=float(meta['scale'])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Manifest scale must be positive and finite')
    if not meta['parts']:
        raise ValueError('Manifest contains no parts')
    R.mkdir(parents=True,exist_ok=True)
    vs=[];fs=[];parts=[];nv=0;nf=0
    for k,p in enumerate(meta['parts']):
        part_path=(D/p['brep']).resolve()
        if not part_path.is_relative_to(D):
            raise ValueError('Part path escapes the model directory')
        shape=cq.Shape.importBrep(str(part_path))
        BRepMesh_IncrementalMesh(shape.wrapped,.75*scale,False,.18,True)
        verts,tris=shape.tessellate(.8*scale,.18)
        xyz=np.array([v.toTuple() for v in verts],dtype=np.float64)
        ids=np.array(tris,dtype=np.int64)
        if not len(xyz) or not len(ids) or not np.isfinite(xyz).all():
            raise ValueError(f"Empty/nonfinite display mesh: {p['name']}")
        pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(xyz,deep=True))
        cells=vtk.vtkCellArray();cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,ids.size+1,3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(ids.ravel(),deep=True))
        raw=vtk.vtkPolyData();raw.SetPoints(pts);raw.SetPolys(cells)
        # Optimize only the derived display representation, never the source solid.
        name=p['name']
        if 'shutline' in name: cap=7000
        elif 'Tire' in name: cap=18500
        elif p['group']=='Body': cap=35000
        elif p['group']=='Glass': cap=18000
        elif 'rim_lip' in name: cap=5500
        elif 'Drilled_brake' in name: cap=9000
        elif 'Sidewall_ring' in name: cap=2400
        else: cap=4500
        clean=vtk.vtkCleanPolyData();clean.SetInputData(raw);clean.SetTolerance(1e-8);clean.Update()
        poly=clean.GetOutput()
        if poly.GetNumberOfPolys()>cap:
            dec=vtk.vtkQuadricDecimation();dec.SetInputData(poly)
            dec.SetTargetReduction(1-cap/poly.GetNumberOfPolys());dec.VolumePreservationOn();dec.Update()
            poly=dec.GetOutput()
        norms=vtk.vtkPolyDataNormals();norms.SetInputData(poly);norms.SetFeatureAngle(40)
        norms.SplittingOn();norms.ConsistencyOn();norms.Update()
        out=norms.GetOutput();points=vtk_to_numpy(out.GetPoints().GetData())/(1000*scale)
        normals=vtk_to_numpy(out.GetPointData().GetNormals())
        offsets=vtk_to_numpy(out.GetPolys().GetOffsetsArray())
        if not np.all(np.diff(offsets)==3):
            raise ValueError('Preview pipeline returned non-triangle display cells')
        tri=vtk_to_numpy(out.GetPolys().GetConnectivityArray()).reshape(-1,3)
        vertex=np.column_stack([points,normals]).astype('<f4')
        indices=(tri+nv).astype('<u4').ravel()
        vs.append(vertex);fs.append(indices)
        m=meta['palette'][p['material']]
        parts.append({'name':p['name'],'group':p['group'],'rgb':m['rgb'],'metal':m['metallic'],'rough':m['roughness'],'start':nf,'count':len(indices),'center':points.mean(axis=0).tolist()})
        nv+=len(points);nf+=len(indices)
    vertex_data=np.concatenate(vs);index_data=np.concatenate(fs)
    if not np.isfinite(vertex_data).all() or int(index_data.max()) >= len(vertex_data):
        raise ValueError('Invalid preview vertex/index data')
    np.savez_compressed(R/'preview_cache.npz',vertices=vertex_data,indices=index_data)
    verts=vertex_data.tobytes();inds=index_data.tobytes()
    blob=base64.b64encode(gzip.compress(verts+inds,compresslevel=6)).decode()
    payload={'vertexBytes':len(verts),'vertexCount':nv,'triangleCount':nf//3,'parts':parts,'binary':blob,
        'stats':{'components':len(meta['parts']),'solids':sum(p['solids'] for p in meta['parts']),
                 'spans':len(meta['curves']),'length_mm':meta['bounds_mm'][0],
                 'width_mm':meta['bounds_mm'][1],'scale':scale},
        'display_only':True,'coordinate_note':'Preview normalized to unscaled design metres for camera framing'}
    (R/'preview_metadata.json').write_text(json.dumps({k:v for k,v in payload.items() if k!='binary'}),encoding='utf-8')
    write_viewer(ROOT/'viewer_template.html',payload,R/'ARP_GT01_Viewer.html')
    print('display vertices',nv,'triangles',nf//3,'HTML MB',(R/'ARP_GT01_Viewer.html').stat().st_size/1e6)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
