#!/usr/bin/env python3
"""ARP GT-01: AdaptiveCAD Bezier curves -> OpenCascade B-rep concept-car assembly.

The authoritative construction contains no surface meshes. CadQuery is used only
as an OCP/OpenCascade topology/solid API bridge. Display tessellation is separate.
"""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT.parents[1], help='AdaptiveCAD checkout (default: this repository)')
    parser.add_argument('--out', type=Path, default=ROOT/'model')
    parser.add_argument('--scale', type=float, default=1.0, help='Uniform scale; base design is millimetres')
    parser.add_argument('--skip-step', action='store_true')
    parser.add_argument('--overwrite', action='store_true', help='Allow replacing generated outputs')
    args = parser.parse_args(argv)
    if not math.isfinite(args.scale) or args.scale <= 0:
        parser.error('--scale must be positive and finite')
    if args.repo and not (args.repo/'adaptivecad/geom/bezier.py').is_file():
        parser.error('--repo must contain adaptivecad/geom/bezier.py')
    sys.path.insert(0, str(args.repo.resolve()))
    try:
        from adaptivecad.geom.bezier import BezierCurve
        from adaptivecad.linalg import Vec3
        from adaptivecad.geom.curve import Curve
        from adaptivecad.geom.cadquery_bridge import bezier_edge, bezier_bridge_error, export_brep_clean, triangulated_face_count
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
        from OCP.gp import gp_Pnt, gp_Dir, gp_Lin
    except ImportError as exc:
        raise SystemExit('Missing dependency. Use a separate environment: python -m pip install -r examples/arp_gt01/requirements.txt\n'+str(exc))

    OUT=args.out.resolve()
    if OUT.exists() and any(OUT.iterdir()) and not args.overwrite:
        parser.error('Output directory is not empty; choose --out or pass --overwrite')
    OUT.mkdir(parents=True, exist_ok=True)
    if args.skip_step and (OUT/'ARP_GT01.step').exists():
        (OUT/'ARP_GT01.step').unlink()
    (OUT/'parts').mkdir(exist_ok=True)
    T0=time.time()
    PALETTE={
     'paint':((0.13,0.30,0.39),0.75,0.24),
     'carbon':((0.035,0.047,0.054),0.15,0.33),
     'rubber':((0.028,0.031,0.034),0.0,0.76),
     'glass':((0.085,0.13,0.16),0.48,0.10),
     'chrome':((0.65,0.72,0.76),0.95,0.19),
     'wheel':((0.55,0.44,0.28),0.90,0.24),
     'rotor':((0.30,0.34,0.36),0.85,0.41),
     'red':((0.80,0.055,0.028),0.30,0.27),
     'tail':((0.98,0.025,0.015),0.25,0.18),
     'led':((0.82,0.94,1.0),0.20,0.18),
     'leather':((0.23,0.10,0.05),0.0,0.59),
     'screen':((0.055,0.20,0.28),0.10,0.20),
    }
    PARTS=[]; CURVES=[]; LOG=[]
    assembly=cq.Assembly(name='ARP_GT01')

    def log(s):
        print(f'[{time.time()-T0:6.1f}s] {s}', flush=True); LOG.append(s)

    def bezier(points, tag='section'):
        """Construct the real AdaptiveCAD curve and transfer its exact poles to OCC."""
        curve=BezierCurve([Vec3(*map(float,p)) for p in points])
        edge=bezier_edge(curve)
        midpoint=curve.evaluate(0.5)
        ep=edge.positionAt(0.5, mode='parameter')
        err=math.dist((ep.x, ep.y, ep.z), (midpoint.x, midpoint.y, midpoint.z))
        CURVES.append({'tag':tag, 'control_points':points,
            'midpoint_bridge_error_mm':err,
            'sampled_bridge_error_mm':bezier_bridge_error(curve,edge)})
        return edge

    def wire_beziers(segments,tag):
        return cq.Wire.assembleEdges([bezier(p,tag) for p in segments])

    def add(name, shape, material, group):
        if not shape.isValid():
            shape=shape.fix()
        if not shape.isValid():
            raise RuntimeError(f'Invalid B-rep: {name}')
        if args.scale != 1:
            shape=shape.scale(args.scale)
        color=PALETTE[material][0]
        assembly.add(shape,name=name,color=cq.Color(*color))
        PARTS.append({'name':name,'shape':shape,'material':material,'group':group})
        return shape

    def box(size,center,r=0):
        w=cq.Workplane('XY').box(*size)
        if r: w=w.edges().fillet(min(r,min(size)*0.49))
        return w.val().translate(center)

    def cyl(r,length,origin,axis=(0,1,0)):
        return cq.Solid.makeCylinder(r,length,cq.Vector(*origin),cq.Vector(*axis))

    def ring(ro,ri,length,origin,axis=(0,1,0)):
        return cyl(ro,length,origin,axis).cut(cyl(ri,length+2,tuple(origin[i]-axis[i] for i in range(3)),axis))

    def tube(points,r=3,closed=False):
        edge=cq.Edge.makeSpline([cq.Vector(*p) for p in points],periodic=closed,tol=1e-5)
        def sweep(e):
            profile=cq.Wire.makeCircle(r,e.startPoint(),e.tangentAt(0))
            shape=cq.Solid.sweep(profile,[],e,True,True,transitionMode='round')
            if not shape.isValid(): shape=shape.fix()
            if not shape.isValid() or not shape.Solids():
                raise RuntimeError('Sweep did not produce a valid solid')
            return shape
        if closed:
            # Two capped segments avoid the closed-periodic pipe seam limitation.
            first=edge._geomAdaptor().FirstParameter(); last=edge._geomAdaptor().LastParameter()
            mid=(first+last)/2
            return cq.Compound.makeCompound([sweep(edge.trim(first,mid)),sweep(edge.trim(mid,last))])
        return sweep(edge)

    def poly_prism(points,vec):
        wire=cq.Wire.makePolygon([cq.Vector(*p) for p in points],close=True)
        return cq.Solid.extrudeLinear(wire,[],cq.Vector(*vec))

    # x, half-width, centre hood/deck height, fender shoulder height, underside height.
    STATIONS=[
     (-2300,735,648,675,250),(-2180,870,704,744,190),
     (-1870,930,775,828,167),(-1420,974,814,882,163),
     (-980,945,815,865,155),(-530,909,796,826,151),
     (0,902,794,817,151),(570,934,822,853,153),
     (1110,978,849,893,160),(1460,995,850,907,173),
     (1840,972,809,869,182),(2160,898,754,800,198),
     (2300,829,709,749,221),
    ]

    def body_section(x,w,h,hs,lo):
        # Five cubic spans per half; mirrored poles preserve bilateral symmetry.
        p=[[(0,h),(.22*w,h),(.47*w,hs),(.65*w,hs)],
           [(.65*w,hs),(.85*w,hs),(w,hs-24),(w,hs-83)],
           [(w,hs-83),(w,hs-185),(w,lo+163),(.979*w,lo+110)],
           [(.979*w,lo+110),(.96*w,lo+51),(.855*w,lo),(.76*w,lo)],
           [(.76*w,lo),(.50*w,lo),(.25*w,lo),(0,lo)]]
        q=p+[[(-y,z) for y,z in seg[::-1]] for seg in p[::-1]]
        return wire_beziers([[(x,y,z) for y,z in seg] for seg in q],f'body_x_{x}')

    log('Building sculpted body from exact AdaptiveCAD cubic Bezier sections')
    body_raw=cq.Solid.makeLoft([body_section(*s) for s in STATIONS])
    body=body_raw
    for x in (-1420,1420):
        body=body.cut(cyl(402,2600,(x,-1300,355)))
    # Interior recess has a floor; this is a styling assembly, not a thin manufactured shell.
    body=body.cut(box((1650,1300,650),(240,0,800),60))
    # Real cut-outs in the fascia.
    body=body.cut(box((400,1120,240),(-2290,0,426),68))
    body=body.cut(box((310,1390,200),(2330,0,431),45))
    add('Body_sculpted_Bezier_loft',body,'paint','Body')
    log('Body and four wheel arches complete')

    # Project seams onto the true B-rep, not onto a fitted mesh.
    inter=IntCurvesFace_ShapeIntersector(); inter.Load(body_raw.wrapped,1e-6)
    def cast(point,direction):
        inter.Perform(gp_Lin(gp_Pnt(*point),gp_Dir(*direction)),0,6000)
        if not inter.IsDone() or inter.NbPnt()<1: raise RuntimeError('Body projection missed')
        hits=[inter.Pnt(i) for i in range(1,inter.NbPnt()+1)]
        p=min(hits,key=lambda p:(p.X()-point[0])**2+(p.Y()-point[1])**2+(p.Z()-point[2])**2)
        return (p.X(),p.Y(),p.Z())
    def top(x,y,dz=2):
        p=cast((x,y,2400),(0,0,-1)); return (p[0],p[1],p[2]+dz)
    def side(x,z,sign=1,dy=2):
        p=cast((x,sign*1600,z),(0,-sign,0));return (p[0],p[1]+sign*dy,p[2])

    for sign in (-1,1):
        # Continuous door shut-line and flush handle.
        xz=[(-705,756),(-731,654),(-692,439),(-573,302),(-299,274),
            (86,274),(535,286),(804,415),(852,638),(774,784),(347,786),(-171,768)]
        add(f'Door_shutline_{sign}',tube([side(x,z,sign) for x,z in xz],2.6,True),'carbon','Trim')
        p=side(523,722,sign,5)
        add(f'Flush_door_handle_{sign}',box((148,14,24),p,6),'chrome','Trim')
        add(f'Rocker_aero_blade_{sign}',box((1950,130,50),(40,sign*892,203),17),'carbon','Aero')
        for j in range(3):
            # Slender gills behind each front wheel.
            x=-868+j*45
            pp=side(x,592,sign,5)
            add(f'Fender_gill_{sign}_{j}',box((19,11,116),pp,4).rotate(pp,(pp[0],pp[1]+1,pp[2]),-18),'carbon','Trim')

    hoodxy=[(-2080,-360),(-1970,-437),(-1580,-480),(-1120,-478),(-827,-399),
            (-785,0),(-827,399),(-1120,478),(-1580,480),(-1970,437),(-2080,360),(-2125,0)]
    add('Hood_perimeter_shutline',tube([top(x,y) for x,y in hoodxy],2.4,True),'carbon','Trim')
    for sign in (-1,1):
        for j in range(5):
            x=-1730+j*48
            p=top(x,sign*565,5)
            add(f'Hood_extractor_{sign}_{j}',box((19,163,13),p,5),'carbon','Trim')

    # Canopy sections retain Bezier control points; no polygonal roof approximation.
    CANOPY=[(-780,714,816,784),(-578,704,1005,786),(-195,661,1270,790),
            (212,645,1310,799),(570,669,1287,816),(916,716,1108,838),
            (1190,755,913,842),(1390,771,859,839)]
    def canopy_section(x,w,hi,lo):
        d20=min(20,0.12*(hi-lo)); d30=min(30,0.20*(hi-lo))
        d42=min(42,0.32*(hi-lo)); d11=min(11,0.15*(hi-lo)); d4=min(4,0.05*(hi-lo))
        p=[[(0,hi),(.24*w,hi),(.48*w,hi-2),(.70*w,hi-d20)],
           [(.70*w,hi-d20),(.86*w,hi-d30),(.94*w,lo+d42),(w,lo+d11)],
           [(w,lo+d11),(w,lo+d4),(.99*w,lo),(.97*w,lo)],
           [(.97*w,lo),(.66*w,lo),(.33*w,lo),(0,lo)]]
        q=p+[[(-y,z) for y,z in seg[::-1]] for seg in p[::-1]]
        return wire_beziers([[(x,y,z) for y,z in seg] for seg in q],f'canopy_x_{x}')
    log('Building greenhouse, roof, pillars and cabin interior')
    canopy=cq.Solid.makeLoft([canopy_section(*s) for s in CANOPY])
    # Styling glazing volume, kept solid to avoid offset/inner-loft openings.
    # Hide this component to inspect the separately modeled cabin. Not production glass.
    glass=canopy
    add('Continuous_tinted_glazing',glass,'glass','Glass')
    roof=canopy.intersect(box((868,1088,450),(244,0,1230))).translate((0,0,2.5))
    add('Carbon_roof_panel',roof,'carbon','Body')
    for sign in (-1,1):
        rail=[(-577,sign*492,985),(-193,sign*463,1250),(212,sign*452,1290),
              (570,sign*468,1267),(916,sign*501,1088),(1188,sign*529,893)]
        add(f'Roof_edge_rail_{sign}',tube(rail,12),'paint','Body')
        add(f'A_pillar_{sign}',tube([(-720,sign*706,810),(-502,sign*643,960),(-194,sign*466,1248)],22),'paint','Body')
        add(f'C_pillar_{sign}',tube([(1176,sign*751,857),(991,sign*664,976),(670,sign*486,1224)],34),'paint','Body')
        add(f'Window_divider_{sign}',tube([(632,sign*669,843),(620,sign*558,1072),(584,sign*474,1251)],11),'carbon','Trim')
        add(f'Window_sill_{sign}',tube([(-724,sign*715,808),(-190,sign*716,810),(510,sign*738,842),(1140,sign*766,865)],9),'chrome','Trim')
        # Mirror stalk and sculpted solid housing.
        stalk=[(-483,sign*716,912),(-500,sign*847,909),(-470,sign*930,948)]
        add(f'Mirror_stalk_{sign}',tube(stalk,15),'carbon','Trim')
        house=box((208,140,72),(-460,sign*1004,968),28)
        add(f'Mirror_housing_{sign}',house,'paint','Trim')
        add(f'Mirror_glass_{sign}',box((11,112,49),(-351,sign*1004,967),5),'chrome','Glass')

    # Two individual bucket seats, headrests, harness slots, stitching strips.
    for s in (-1,1):
        y=s*337
        add(f'Seat_cushion_{s}',box((467,409,122),(222,y,577),43),'leather','Interior')
        back=box((132,398,430),(476,y,821),41).rotate((476,y,821),(476,y+1,821),-13)
        add(f'Seat_back_{s}',back,'leather','Interior')
        add(f'Seat_headrest_{s}',box((121,228,138),(505,y,1082),31),'carbon','Interior')
        for h in (-1,1):
            add(f'Seat_bolster_{s}_{h}',box((399,64,113),(228,y+h*180,651),25),'carbon','Interior')
            add(f'Seat_harness_slot_{s}_{h}',box((8,60,26),(404,y+h*69,942),3),'carbon','Interior')
        for j in range(4):
            add(f'Seat_stitch_{s}_{j}',box((283,3.5,2),(187,y-93+j*62,640),0),'chrome','Interior')
    add('Dashboard',box((269,1240,167),(-445,0,897),40),'carbon','Interior')
    add('Center_console',box((635,206,214),(120,0,615),30),'carbon','Interior')
    add('Center_touchscreen',box((28,227,139),(-297,0,968),8).rotate((-297,0,968),(-297,1,968),-14),'screen','Interior')
    add('Instrument_binnacle',box((53,295,93),(-311,-337,1011),20),'carbon','Interior')
    add('Instrument_display',box((3,261,63),(-283,-337,1014),1),'screen','Interior')
    steer_center=(-154,-337,983)
    add('Steering_wheel_rim',cq.Solid.makeTorus(136,16,steer_center,(1,0,0)),'carbon','Interior')
    add('Steering_hub',cyl(46,26,(-171,-337,983),(1,0,0)),'carbon','Interior')
    for t in (0,120,240):
        a=math.radians(t)
        add(f'Steering_spoke_{t}',tube([steer_center,(-154,-337+120*math.cos(a),983+120*math.sin(a))],9),'chrome','Interior')

    # Aero surfaces.
    log('Adding fascia, lighting, grilles, diffuser, exhaust and rear wing')
    add('Front_splitter',box((434,1760,31),(-2125,0,174),14),'carbon','Aero')
    add('Front_lower_bumper',box((203,1610,98),(-2211,0,230),32),'carbon','Aero')
    add('Front_grille_recess',box((18,1055,183),(-2188,0,423),8),'carbon','Trim')
    for j in range(19):
        y=-477+j*53
        add(f'Front_grille_slat_{j:02}',box((70,8,157),(-2243,y,424),3),'rotor','Trim')
    for s in (-1,1):
        y=s*606
        add(f'Headlight_housing_{s}',box((67,272,71),(-2285,y,624),22),'carbon','Lighting')
        for j in (-1,1):
            add(f'Headlight_LED_{s}_{j}',box((8,229,8),(-2320,y,625+j*15),3.7),'led','Lighting')
        add(f'Headlight_outer_tick_{s}',box((8,7,39),(-2320,y+s*117,625),3),'led','Lighting')
        add(f'Front_corner_intake_{s}',box((40,173,122),(-2267,s*710,416),19),'carbon','Trim')
        for j in range(3):
            add(f'Corner_intake_bar_{s}_{j}',box((9,142,7),(-2290,s*710,386+j*29),3),'rotor','Trim')
        add(f'Front_canard_{s}',box((273,92,16),(-2078,s*871,272),6).rotate((-2078,s*871,272),(-2078,s*871+1,272),-7),'carbon','Aero')

    add('Tail_lamp_black_band',box((32,1549,61),(2295,0,669),15),'carbon','Lighting')
    for s in (-1,1):
        add(f'Tail_LED_signature_{s}',box((9,689,15),(2314,s*405,676),6),'tail','Lighting')
        add(f'Tail_LED_lower_{s}',box((9,278,7),(2314,s*610,658),3),'tail','Lighting')
    add('Rear_grille_recess',box((22,1340,160),(2190,0,434),10),'carbon','Trim')
    for j in range(23):
        add(f'Rear_grille_slat_{j:02}',box((72,7,145),(2250,-617+j*56,434),2.8),'rotor','Trim')
    add('Rear_diffuser_floor',box((503,1590,40),(2070,0,185),10),'carbon','Aero')
    for j in range(7):
        y=-612+j*204
        p=[(1810,y,180),(2323,y,173),(2298,y,283),(2170,y,266)]
        add(f'Diffuser_strake_{j}',poly_prism(p,(0,12,0)),'carbon','Aero')
    for s in (-1,1):
        for j in (-1,1):
            y=s*600+j*56
            add(f'Exhaust_tip_{s}_{j}',ring(45,36,115,(2220,y,300),(1,0,0)),'chrome','Trim')
            add(f'Exhaust_dark_core_{s}_{j}',cyl(35,3,(2295,y,300),(1,0,0)),'carbon','Trim')

    for s in (-1,1):
        add(f'Wing_pylon_{s}',poly_prism([(1857,s*566,823),(1980,s*566,822),(2074,s*566,1000),(2015,s*566,1000)],(0,22,0)),'carbon','Aero')
    # Closed cubic airfoil; extruded spanwise. All spans use upstream Bezier code.
    wseg=[[(1840,-953,1000),(1840,-953,1020),(2070,-953,1052),(2210,-953,1028)],
          [(2210,-953,1028),(2220,-953,1026),(2221,-953,1018),(2210,-953,1016)],
          [(2210,-953,1016),(2040,-953,1006),(1910,-953,984),(1840,-953,1000)]]
    wing_wire=wire_beziers(wseg,'rear_wing_airfoil')
    add('Rear_wing_airfoil',cq.Solid.extrudeLinear(wing_wire,[],(0,1906,0)),'carbon','Aero')
    for s in (-1,1):
        add(f'Wing_endplate_{s}',box((306,15,100),(2075,s*960,1028),6),'paint','Aero')
    for s in (-1,1):
        for j in range(7):
            x=1480+j*47
            p=top(x,s*440,7)
            add(f'Rear_deck_vent_{s}_{j}',box((18,285,12),p,4),'carbon','Trim')

    # Wheel geometry is authored once at the origin and instanced at each corner.
    log('Building revolved tires, split-spoke wheels and cross-drilled brake rotors')
    # Cross-section in XY: x is radial, y is axle direction. Revolve about the Y axis.
    tire_segments=[
     [(241,-126,0),(260,-142,0),(326,-140,0),(345,-112,0)],
     [(345,-112,0),(355,-97,0),(355,-88,0),(355,-73,0)],
     [(355,-73,0),(355,-24,0),(355,24,0),(355,73,0)],
     [(355,73,0),(355,89,0),(355,99,0),(345,112,0)],
     [(345,112,0),(326,140,0),(260,142,0),(241,126,0)],
     [(241,126,0),(237,105,0),(237,-105,0),(241,-126,0)],
    ]
    tw=wire_beziers(tire_segments,'tire_meridian')
    tire=cq.Solid.revolve(tw,[],360,(0,0,0),(0,1,0))
    for y in (-73,-25,25,73):
        tire=tire.cut(cq.Solid.makeTorus(354,4.7,(0,y,0),(0,1,0)))
    # Fine diagonal tread sipes: real toroidal arcs would be costly; shallow sidewall
    # ridges and circumferential grooves are explicit geometry, not a bump map.
    barrel=ring(260,230,246,(0,-123,0))
    rotor=ring(213,63,18,(0,87,0))
    holes=[]
    for rad,num in ((157,18),(188,24)):
        for j in range(num):
            a=2*math.pi*(j+0.22)/num
            holes.append(cyl(7,22,(rad*math.cos(a),85,rad*math.sin(a))))
    rotor=rotor.cut(*holes)
    # Five pairs of tapered spokes, each an independent solid.
    spokes=[]
    for j in range(5):
        for branch in (-1,1):
            a=2*math.pi*j/5+branch*.105
            def rp(r,t,y): return (r*math.cos(t),y,r*math.sin(t))
            pts=[rp(51,a-.14,125),rp(246,a+branch*.04-.032,125),
                 rp(246,a+branch*.04+.032,125),rp(51,a+.14,125)]
            sp=poly_prism(pts,(0,19,0))
            spokes.append(sp)
    for ix,x in enumerate((-1420,1420)):
        for s in (-1,1):
            c=(x,s*855,355); prefix=('F' if ix==0 else 'R')+('L' if s==1 else 'R')
            def loc(shape):
                if s==-1: shape=shape.rotate((0,0,0),(1,0,0),180)
                return shape.translate(c)
            add(prefix+'_Tire_grooved',loc(tire),'rubber','Wheels')
            add(prefix+'_Wheel_barrel',loc(barrel),'carbon','Wheels')
            add(prefix+'_Outer_rim_lip',loc(cq.Solid.makeTorus(250,9,(0,135,0),(0,1,0))),'chrome','Wheels')
            add(prefix+'_Inner_rim_lip',loc(cq.Solid.makeTorus(248,5,(0,-124,0),(0,1,0))),'wheel','Wheels')
            add(prefix+'_Drilled_brake_rotor',loc(rotor),'rotor','Brakes')
            add(prefix+'_Brake_hat',loc(ring(97,49,23,(0,100,0))),'carbon','Brakes')
            for j,sp in enumerate(spokes):add(prefix+f'_Split_spoke_{j:02}',loc(sp),'wheel','Wheels')
            add(prefix+'_Center_hub',loc(cyl(61,29,(0,117,0))),'wheel','Wheels')
            add(prefix+'_Center_cap',loc(cyl(32,3,(0,148,0))),'carbon','Wheels')
            for j in range(5):
                a=2*math.pi*j/5
                p=(43*math.cos(a),148,43*math.sin(a))
                add(prefix+f'_Lug_bolt_{j}',loc(cyl(6.5,7,p)),'chrome','Wheels')
            caliper=box((85,64,182),(-170,84,33),18)
            add(prefix+'_Red_brake_caliper',loc(caliper),'red','Brakes')
            for j in (-1,1):
                add(prefix+f'_Caliper_bridge_{j}',loc(box((22,10,139),(-169+j*24,122,33),4)),'red','Brakes')
            for sideval in (-1,1):
                add(prefix+f'_Sidewall_ring_{sideval}',loc(cq.Solid.makeTorus(308,1.3,(0,sideval*135,0),(0,1,0))),'rubber','Wheels')
            # Tire lettering as raised radial bars, an original non-brand sidewall motif.
            for j in range(12):
                a=math.radians(35+j*4)
                p=(311*math.cos(a),136,311*math.sin(a))
                bar=box((13,2,3),p,.8).rotate(p,(p[0],p[1]+1,p[2]),-math.degrees(a))
                add(prefix+f'_Sidewall_mark_{j:02}',loc(bar),'rubber','Wheels')
            a=math.radians(211)
            add(prefix+'_Valve_stem',loc(cyl(4,15,(228*math.cos(a),130,228*math.sin(a)))),'carbon','Wheels')

    # Badges use simple original geometry, not an automaker trademark.
    p=top(-1920,0,8)
    add('Hood_badge_base',box((58,49,5),p,2),'chrome','Trim')
    add('Hood_badge_inlay',box((42,33,2),(p[0],p[1],p[2]+3),.8),'carbon','Trim')
    # Front/rear number plates kept blank to avoid font dependencies.
    add('Rear_plate_plinth',box((20,290,80),(2320,0,543),7),'carbon','Trim')

    log(f'Validating and exporting {len(PARTS)} named components')
    manifest=[]
    for i,p in enumerate(PARTS):
        shape=p['shape']; bb=shape.BoundingBox()
        valid=bool(BRepCheck_Analyzer(shape.wrapped).IsValid())
        if not valid:raise RuntimeError('Final check failed: '+p['name'])
        f=OUT/'parts'/(p['name']+'.brep');export_brep_clean(shape,f)
        manifest.append({'name':p['name'],'group':p['group'],'material':p['material'],
            'brep':'parts/'+f.name,'valid_brep':valid,'solids':len(shape.Solids()),
            'faces':len(shape.Faces()),'volume_mm3':shape.Volume(),
            'bbox_mm':[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]})
    compound=cq.Compound.makeCompound([p['shape'] for p in PARTS])
    # Remove all triangulations before authoritative serialization.
    export_brep_clean(compound,OUT/'ARP_GT01.brep')
    if not args.skip_step:
        assembly.export(str(OUT/'ARP_GT01.step'),'STEP')
    bb=compound.BoundingBox()
    metadata={'name':'ARP GT-01','description':'Original sports-coupe styling assembly',
     'schema_version':1,'units':'mm','scale':args.scale,'step_exported':not args.skip_step,
     'source_coordinates':'Control points and station data are unscaled design millimetres','coordinate_frame':'X length (front negative), Y width, Z up; ground Z=0',
     'construction':'AdaptiveCAD BezierCurve poles -> CadQuery/OCP OpenCascade B-rep lofts, revolutions and booleans',
     'native_representation':'analytic and spline B-rep; no model mesh',
     'adaptive_metric_note':'Ordinary Euclidean design; no unvalidated adaptive-pi deformation applied',
     'body_stations':STATIONS,'canopy_stations':CANOPY,'wheelbase_mm':2840*args.scale,
     'body_nominal_width_mm':1990*args.scale,'tire_diameter_mm':710*args.scale,
     'bounds_mm':[bb.xlen,bb.ylen,bb.zlen],
     'palette':{k:{'rgb':v[0],'metallic':v[1],'roughness':v[2]} for k,v in PALETTE.items()},
     'parts':manifest,'curves':CURVES,
     'limits':['Styling model, not a roadworthy or manufacturing-engineered vehicle',
     'Doors are represented by surface shut-lines, not independently opening panels',
     'Glazing is a styling volume overlapping the cabin; not a production optical shell',
     'No powertrain, suspension kinematics, crash analysis or production surfacing certification',
     'STEP/BREP import does not reconstruct the procedural feature history; use build_car.py'],
     'source_files':{
        'adaptivecad/geom/bezier.py': None,
        'adaptivecad/geom/curve.py': None,
        'adaptivecad/linalg.py': None},
    }

    for name, obj in [('adaptivecad/geom/bezier.py',BezierCurve),
                      ('adaptivecad/geom/curve.py',Curve), ('adaptivecad/linalg.py',Vec3)]:
        raw=Path(inspect.getfile(obj)).read_bytes()
        metadata['source_files'][name]=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    (OUT/'ARP_GT01.design.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    audit={'named_components':len(PARTS),'solids':sum(p['solids'] for p in manifest),
     'faces':sum(p['faces'] for p in manifest),'all_breps_valid':all(p['valid_brep'] for p in manifest),
     'adaptivecad_bezier_spans':len(CURVES),
     'max_bezier_bridge_midpoint_error_mm':max(c['midpoint_bridge_error_mm'] for c in CURVES),
     'max_bezier_bridge_sampled_error_mm':max(c['sampled_bridge_error_mm'] for c in CURVES),
     'source_mesh_created':False,
     'native_brep_faces_with_display_triangulation':triangulated_face_count(cq.Shape.importBrep(str(OUT/'ARP_GT01.brep'))),
     'preview_note':'Optional viewer/render uses derived display-only tessellation',
     'bounds_mm':metadata['bounds_mm'],'build_seconds':time.time()-T0}
    (OUT/'validation.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    log(json.dumps(audit))
    (OUT/'build_log.txt').write_text('\n'.join(LOG),encoding='utf-8')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
