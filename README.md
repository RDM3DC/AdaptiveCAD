# AdaptiveCAD

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Sponsor RDM3DC](https://img.shields.io/badge/Sponsor-RDM3DC-ff69b4?logo=github-sponsors)](https://github.com/sponsors/RDM3DC)

AdaptiveCAD is a next-gen modeling toolkit built on Adaptive π (πₐ). It delivers node-free smooth curves, hyperbolic geometry tools, fast STL repair, and 3D-print exports—wrapped in a friendly Playground app, a FreeCAD Workbench, and a starter Blender add-on.

**TL;DR:** Import messy meshes → repair → generate smooth πₐ curves/shapes → preview toolpaths → export STL/3MF/G-code. Works great for printable organic shells, architectural panels, and smooth-stress brackets.

## ✨ Highlights

### Playground App (Standalone)
Parametric editors (superellipse, rounded-rect, πₐ splines), live viewport, STL→πₐ import & repair, toolpath preview, and one-click exports.

### Curve/Shape Libraries
Superellipse, πₐ splines, advanced shapes, and hyperbolic families (geodesics, horocycles, tilings).

### STL Repair & Smoothing
Fix non-manifold edges, normals, degenerate faces; optional smoothing with πₐ-aware operations.

### 3D Printing Ready
Export STL / 3MF / G-code with layer previews and basic time estimates.

### FreeCAD Workbench + Blender Add-on
Generate πₐ objects, import/export, and hand off assets to your DCC/CAD pipeline.

## 📦 Components in this Repo

```
AdaptiveCAD/
├─ playground/                       # Main app (UI & ops)
│  ├─ run_advanced_playground.py
│  ├─ quick_start_demo.py
│  ├─ adaptivecad_shapes_builder.py
│  ├─ import_stl_to_pi.py
│  └─ ... (export_slices.py, ama_to_gcode_converter.py, etc.)
├─ freecad/AdaptiveCADPIToolpath/    # FreeCAD Workbench (v0.1)
├─ blender_addons/adaptivecad_pia/   # Blender add-on (starter)
├─ docs/
│  ├─ PLAYGROUND_GUIDE.md
│  ├─ MODELING_TOOLS.md
│  ├─ IMPORT_SYSTEM_COMPLETE.md
│  ├─ HYPERBOLIC_GEOMETRY_IMPLEMENTATION.md
│  └─ MATH_REFERENCE.md
├─ examples/                         # Sample models, scripts, projects
├─ gifs_lite_pack/                   # Short loops for README/Kickstarter
└─ LICENSE
```

## 🖥️ System Requirements

- **OS:** Windows 10/11 (primary). Linux/macOS planned post-1.0.
- **Python:** 3.10+ (for source runs).
- **GPU:** Optional; CPU-only is fine for typical models.
- **CAD/DCC (optional):** FreeCAD 0.21+ / Blender 4.x for the integrations.

## 🚀 Quick Start (Playground App)

### Option A — Run from source (recommended for dev)

Create an environment and install deps:

```bash
# from repo root
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -r requirements.txt
```

Launch the Playground:

```bash
cd playground
python run_advanced_playground.py
```

Try the demo:

```bash
python quick_start_demo.py
```

### Option B — Use the Windows installer (when available)

Download the latest Playground MSIX from Releases and double-click to install. (We sign builds at each tagged version; see Releases page.)

## 🧩 Key Workflows

1. **Parametric shapes → export**
   - Open Playground → Shapes panel.
   - Pick Superellipse or πₐ Spline, tweak parameters (a, b, n, points).
   - Click Export to save STL/3MF, or Generate G-code for printing.

2. **STL → repair → πₐ smoothing**
   - Import a messy STL.
   - Run Repair (non-manifold, normals, decimate).
   - Enable πₐ Smooth (optional) and preview the toolpath.
   - Export ready-to-print output.

3. **Hyperbolic families**
   - Open Hyperbolic tab: create geodesics/horocycles, or tiling presets.
   - Convert curves to meshes, combine with param shapes, and export.

## 🧪 Examples

```bash
# Rebuild a param sweep and export STL
python playground/quick_start_demo.py --shape superellipse --a 40 --b 25 --n 3.2 --out ./examples/superellipse.stl

# Repair an STL and export G-code
python playground/import_stl_to_pi.py --in ./examples/janky_part.stl --repair --gcode ./examples/janky_part_fixed.gcode
```

More in `examples/` and `docs/PLAYGROUND_GUIDE.md`.

## 📐 Scaling & Smoothness

AdaptiveCAD stores geometry as πₐ splines and parametric surfaces, then tessellates at export with adaptive error bounds.

- Set `max_angle_err` and `max_chord_err` to control smoothness independently of model size.
- Re-slice large prints with locked nozzle width/layer height to preserve surface quality.
- Use Curvature Preview to see where the tessellator adds triangles at larger scales.

Example (CLI exports):

```bash
# High-fidelity STL regardless of size
python playground/export_slices.py \
  --in ./examples/smooth_panel.acproj \
  --stl ./out/smooth_panel_scaled.stl \
  --max_angle_err 0.5 --max_chord_err 0.05

# Scale model and keep physical print params consistent
python playground/quick_start_demo.py \
  --shape superellipse --a 40 --b 25 --n 3.2 --scale 10 \
  --out ./out/superellipse_x10.3mf --lock_print_params
```

## 🧰 FreeCAD Workbench (v0.1)

Copy the folder `freecad/AdaptiveCADPIToolpath/` into your FreeCAD Mod directory.

Launch FreeCAD → enable the workbench → AdaptiveCADPI Toolpath.

Generate πₐ objects and toolpaths; export to STL/3MF.

See `docs/PLAYGROUND_GUIDE.md` for a quick tour.

## 🎬 Blender Add-on (starter)

1. `Edit → Preferences → Add-ons → Install…`
2. Select the zip in `blender_addons/adaptivecad_pia/`.
3. Enable “AdaptiveCAD πₐ” and use `Add → Mesh → πₐ Object`.

## 🧱 Roadmap (Scope B)

- **v0.1-alpha:** Playground core + param editors + basic repair + STL export
- **Alpha updates:** Hyperbolic library v1, GIF export, preset save/load
- **Beta:** 3MF export, G-code v2 (infill presets), Undo/Redo, FreeCAD parity
- **1.0:** Signed installers, docs site, examples pack
- **Stretch (post-1.0):** GPU kernels, constraint solver, expanded CAM finishing

Follow progress on the Issues and Projects tabs. We post short GIF updates every 1–2 weeks.

## 🧮 Math & Design Notes

Adaptive π (πₐ) removes saw-tooth artifacts by operating directly on smooth curve families and πₐ splines.

Hyperbolic geometry tooling includes geodesics/horocycles and basic tilings for curvature-aware designs.

Repair focuses on non-manifold edges, flipped normals, zero-area faces, and optional decimation before smoothing.

Detailed references: `docs/MATH_REFERENCE.md`, `docs/HYPERBOLIC_GEOMETRY_IMPLEMENTATION.md`.

## 🏗️ Building & Packaging

### Dev build

```bash
pip install -r requirements-dev.txt
pytest  # run unit tests (if present)
```

### Windows packaging (maintainers)

```bash
# Example: PyInstaller (adjust spec as needed)
pyinstaller playground/run_advanced_playground.py -n AdaptiveCAD-Playground --noconsole --onefile

# Or MSIX packaging (recommended for signed installs)
# See scripts/msix/ and CI workflow in .github/workflows/build.yml
```

## 🤝 Contributing

We welcome issues, pull requests, and test models:

- File an issue with a minimal repro (attach STL if relevant).
- Style: keep functions small, document edge cases, and add a GIF where possible.
- PRs: include before/after screenshots or GIFs for UI/repair changes.

See `CONTRIBUTING.md` (or open an issue if you don’t see it yet).

## 🧾 License

This project’s licensing is in [LICENSE](LICENSE). If you’re unsure about commercial use, open a discussion.

## 🆘 Support

- Discussions / Q&A: GitHub Discussions
- Bugs: GitHub Issues (attach sample files)
- Commercial / pilots: email (listed in repo profile)

## 🚀 Kickstarter (Scope B)

We’re preparing a Kickstarter to accelerate the Playground Suite to 1.0 (Windows first, Linux/macOS next), expand hyperbolic tools, and polish FreeCAD/Blender integrations. Interested? Watch the repo and star it; teaser GIFs live in `gifs_lite_pack/`.

## 📣 Changelog (snippet)

- **v0.1-alpha** — Playground launch: param editors, STL repair, STL export, basic toolpath preview
- **v0.1.1** — Hyperbolic presets, GIF export, save/load presets
- **v0.2-beta** — 3MF export, G-code v2, Undo/Redo, FreeCAD parity, Blender panel updates

(See Releases for signed builds and hashes.)

## 🙌 Credits

AdaptiveCAD by Ryan McKenna (RDM3DC) and collaborators. Thanks to the open-source CAD/geometry community and everyone testing early builds.
