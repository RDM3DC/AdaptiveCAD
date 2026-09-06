"""Render the derived inspection mesh; exact CAD files remain untouched."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT, help='Preview cache directory')
    parser.add_argument('--out', type=Path, default=ROOT)
    parser.add_argument('--view', default='all', choices=['all', 'front', 'rear', 'side', 'interior'])
    parser.add_argument('--width', default=1800, type=int)
    args = parser.parse_args(argv)
    if args.width < 320 or args.width > 8192:
        parser.error('--width must be between 320 and 8192 pixels')
    import numpy as np
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
    from PIL import Image,ImageDraw,ImageFont
    R=args.input.resolve();O=args.out.resolve();O.mkdir(parents=True,exist_ok=True);a=args
    M=json.loads((R/'preview_metadata.json').read_text(encoding='utf-8'));C=np.load(R/'preview_cache.npz');V=C['vertices'];I=C['indices'];W=a.width;H=round(W*.625)
    ren=vtk.vtkRenderer();ren.SetBackground(.91,.925,.935);ren.AutomaticLightCreationOff()
    win=vtk.vtkRenderWindow();win.AddRenderer(ren);win.SetSize(W,H);win.SetOffScreenRendering(1);win.SetMultiSamples(0)
    actors=[]
    for k,item in enumerate(M['parts']):
        inds=I[item['start']:item['start']+item['count']];lo=int(inds.min());hi=int(inds.max())+1
        xyz=(V[lo:hi,:3]*1000).astype('float64');nn=V[lo:hi,3:];ii=(inds-lo).astype('int64').reshape(-1,3)
        points=vtk.vtkPoints();points.SetData(numpy_to_vtk(xyz,deep=True));cells=vtk.vtkCellArray();cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,ii.size+1,3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(ii.ravel(),deep=True))
        poly=vtk.vtkPolyData();poly.SetPoints(points);poly.SetPolys(cells);poly.GetPointData().SetNormals(numpy_to_vtk(nn,deep=True))
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(poly);mapper.ScalarVisibilityOff();actor=vtk.vtkActor();actor.SetMapper(mapper);pr=actor.GetProperty();pr.SetInterpolationToPhong();pr.SetColor(*item['rgb']);pr.SetAmbient(.22);pr.SetDiffuse(.75);pr.SetSpecular(.28+item['metal']*.44);pr.SetSpecularPower(20+85*(1-item['rough']))
        if item['group']=='Glass':pr.SetSpecular(.92);pr.SetSpecularPower(105)
        if item['group']=='Lighting' and ('LED' in item['name']):pr.SetAmbient(.85);pr.SetDiffuse(.3)
        ren.AddActor(actor);actors.append((actor,item))
    for pos,intensity,col in [((-5000,-5500,7000),.95,(1,.98,.94)),((1800,3800,5300),.75,(.91,.96,1)),((5000,-2700,3500),.45,(1,1,1))]:
        light=vtk.vtkLight();light.SetLightTypeToSceneLight();light.SetPosition(*pos);light.SetFocalPoint(0,0,600);light.SetColor(*col);light.SetIntensity(intensity);ren.AddLight(light)
    plane=vtk.vtkPlaneSource();plane.SetOrigin(-20000,-20000,-4);plane.SetPoint1(20000,-20000,-4);plane.SetPoint2(-20000,20000,-4);plane.Update();pm=vtk.vtkPolyDataMapper();pm.SetInputConnection(plane.GetOutputPort());ground=vtk.vtkActor();ground.SetMapper(pm);ground.GetProperty().SetColor(.79,.81,.825);ground.GetProperty().SetAmbient(.3);ground.GetProperty().SetDiffuse(.7);ren.AddActor(ground)
    ssao=vtk.vtkSSAOPass();ssao.SetRadius(155);ssao.SetBias(1.5);ssao.SetKernelSize(64);ssao.BlurOn();ssao.SetDelegatePass(vtk.vtkRenderStepsPass());ren.SetPass(ssao);ren.UseFXAAOn()
    cam=ren.GetActiveCamera();cam.SetViewUp(0,0,1);cam.ParallelProjectionOn()
    views={'front':((-6700,-5900,3150),(-70,0,580),1710),'rear':((6800,-5900,2980),(100,0,570),1710),'side':((0,-9800,1400),(0,0,615),1640),'interior':((-3800,-4700,4600),(60,0,610),1720)}
    for name in (views if a.view=='all' else [a.view]):
        for actor,item in actors:actor.SetVisibility(not(name=='interior' and item['group'] in ('Body','Glass')))
        pos,focus,scale=views[name];cam.SetPosition(*pos);cam.SetFocalPoint(*focus);cam.SetParallelScale(scale);ren.ResetCameraClippingRange();win.Render()
        capture=vtk.vtkWindowToImageFilter();capture.SetInput(win);capture.SetInputBufferTypeToRGB();capture.ReadFrontBufferOff();capture.Update();out=O/f'ARP_GT01_{name}.png';writer=vtk.vtkPNGWriter();writer.SetFileName(str(out));writer.SetInputConnection(capture.GetOutputPort());writer.Write()
        im=Image.open(out).convert('RGB');draw=ImageDraw.Draw(im)
        try:title=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',round(W*.027));small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',round(W*.011))
        except OSError:title=small=ImageFont.load_default()
        draw.text((W*.039,H*.047),'ARP  /  GT—01',font=title,fill=(31,47,58));draw.text((W*.041,H*.112),'ADAPTIVECAD  ·  ORIGINAL PARAMETRIC COUPE',font=small,fill=(63,78,90));draw.text((W*.041,H*.943),'BÉZIER + B-REP SOURCE   /   '+name.upper()+' VIEW   /   DISPLAY-ONLY TESSELLATION',font=small,fill=(63,78,90));im.save(out);print(out,flush=True)
    win.Finalize()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
