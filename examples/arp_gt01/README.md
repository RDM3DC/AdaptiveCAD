# ARP GT-01: reproducible AdaptiveCAD car example

A detailed original sports-coupe **styling assembly**, built from AdaptiveCAD
Bezier curves through an optional CadQuery/OCP solid-modeling bridge. The baseline
recipe creates 345 named components, 348 solids and 203 Bezier spans. No generated
STEP, BREP, HTML payload, render or preview cache belongs in this directory's Git
history; regenerate those assets with the commands below.

## Run from the repository root

Use a separate Python 3.11+ environment rather than changing the existing
`pythonocc-core`/Playground environment. The example imports the current checkout;
there is no vendored duplicate of the AdaptiveCAD kernel and no editable package
installation is required.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv-car
.\.venv-car\Scripts\python.exe -m pip install -r examples/arp_gt01/requirements.txt
.\.venv-car\Scripts\python.exe examples/arp_gt01/build_car.py
.\.venv-car\Scripts\python.exe examples/arp_gt01/validate_car.py
.\.venv-car\Scripts\python.exe examples/arp_gt01/build_viewer.py
Start-Process examples/arp_gt01/ARP_GT01_Viewer.html
```

Linux/macOS:

```sh
python3 -m venv .venv-car
. .venv-car/bin/activate
python -m pip install -r examples/arp_gt01/requirements.txt
python examples/arp_gt01/build_car.py
python examples/arp_gt01/validate_car.py
python examples/arp_gt01/build_viewer.py
```

Open the generated `examples/arp_gt01/ARP_GT01_Viewer.html` in a desktop browser
with WebGL 2 and `DecompressionStream`. It contains its geometry and makes no
network requests. Orbit, zoom, pan, group/component visibility, interior inspection
and exploded viewing are display operations, not CAD feature edits.

To generate PNG views after building the viewer cache:

```sh
python examples/arp_gt01/render_car.py --view all --width 1800
```

The rendering path needs a working VTK offscreen graphics backend. Font fallback
is provided; no font files are distributed. Importing any of the four scripts is
side-effect-free; optional dependencies load only when its `main()` runs.

## Alternate outputs and scale

```sh
python examples/arp_gt01/build_car.py --scale 0.1 --out output/car/model
python examples/arp_gt01/validate_car.py --model output/car/model
python examples/arp_gt01/build_viewer.py --model output/car/model --out output/car/preview
python examples/arp_gt01/render_car.py --input output/car/preview --out output/car/renders
```

`--scale 0.1` means 1:10. CAD coordinates, volumes, dimensions and validation
thresholds account for the scale. Control points in the manifest remain **unscaled
source millimetres**, explicitly labeled. Preview camera coordinates are normalized
to the nominal design, while the displayed dimensions come from the scaled manifest.
Extreme scales can still exceed OpenCascade's modeling tolerances.

The builder refuses a nonempty output directory unless `--overwrite` is supplied.
That flag authorizes replacing generated files. `--skip-step` omits STEP; when
combined with overwrite it removes a stale `ARP_GT01.step` so the old export cannot
masquerade as the current one. Validate such a build with `--skip-step`; its report
says `PASS_BREP_ONLY`, not that a STEP round trip passed.

Default output is `examples/arp_gt01/model/`. Each part has a named BREP file;
`ARP_GT01.design.json` records dimensions, materials, source control points and
hashes of the curve modules used. A source-hash mismatch requires rebuilding from
the current checkout or validating with the original checkout via `--repo`.
A failing validation replaces a stale PASS report and returns a nonzero exit code.

## What is reusable

`adaptivecad.geom.cadquery_bridge` provides:

- `bezier_edge` and `bezier_wire`: direct pole transfer, ordered connectivity checks
  and sampled parameter-space comparisons without constructing a mesh.
- `bezier_bridge_error`: an explicitly sampled check, not a certified global bound.
- `export_brep_clean` and `triangulated_face_count`: mesh-free serialization of a
  geometry copy without stripping the original object's display triangulation.

```python
from adaptivecad.geom.bezier import BezierCurve
from adaptivecad.geom.cadquery_bridge import bezier_edge
from adaptivecad.linalg import Vec3

curve = BezierCurve([
    Vec3(0, 0, 0), Vec3(20, 40, 0), Vec3(60, 40, 0), Vec3(80, 0, 0),
])
edge = bezier_edge(curve)
```

The bridge does not replace the existing kernel or GUI and does not introduce
CadQuery into the base dependencies. A stationary tangent is not rejected merely
because its derivative vanishes at a sample; a truly constant curve is rejected.

## Checks

```sh
python -m pip install "pytest>=8,<10"
python -m pytest -q tests/test_cadquery_bridge.py tests/test_arp_gt01_tools.py
```

The accompanying workflow runs these focused tests and a full 1:10 CAD build and
validation. It does not run the full repository suite or launch the Playground GUI.

Local integration verification: 36 focused tests passed; the 1:10 recipe rebuilt
345 components and 348 solids, all of which survived STEP round-trip validation.
The BREP exports carried zero stored display triangulations; all four nominal
tire/body intersections had zero volume. New-file tests used the unchanged curve,
base-curve and vector sources matching the inspected repository blob hashes. This
is not a claim that every existing repository module or GUI path was tested.

## Geometry boundary

Authoritative construction and STEP/BREP exports use curves and BREP surfaces,
not a triangle mesh. Viewer and PNG generation deliberately tessellate copies for
display, and may simplify that display mesh. Do not use the display mesh as the
manufacturing master. Floating-point and modeling tolerances still apply.

This is ordinary Euclidean styling geometry, not a validated adaptive-pi metric
deformation. Doors are represented by shut-lines rather than hinged parts;
glazing is a solid styling volume overlapping the cabin. No powertrain, suspension
kinematics, crash validation, production surfacing certification, print-preparation
or manufacturing tolerances are supplied. STEP/BREP preserve geometry, not the
procedural feature history; edit `build_car.py` and regenerate to change the design.
