# AdaptiveCAD

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Sponsor RDM3DC](https://img.shields.io/badge/Sponsor-RDM3DC-ff69b4?logo=github-sponsors)](https://github.com/sponsors/RDM3DC)

AdaptiveCAD is a next-gen modeling toolkit built on Adaptive π (π₀). It delivers node-free smooth curves, hyperbolic geometry tools, fast STL repair, and 3D-print exports—wrapped in a friendly Playground app, a FreeCAD Workbench, and a starter Blender add-on.

**TL;DR:** Import messy meshes → repair → generate smooth π₀ curves/shapes → preview toolpaths → export STL/3MF/G-code. Works great for printable organic shells, architectural panels, and smooth-stress brackets.

## ✨ Highlights

### Playground App (Standalone)
### Analytic HUD Wheel
![Radial tool wheel demo](docs/assets/radial_wheel_demo.gif)

All analytic viewports now share a single radial tool wheel overlay with sketch + transform tools, quick utility segments (Center, Reset, Undo), and idle-spin polish. Configure it under *HUD Wheel* in the Analytic panel (enable, edge fit, overshoot, thickness, opacity, text size, auto-spin), and the choices persist via `~/.adaptivecad_analytic.json`.

Parametric editors (superellipse, rounded-rect, π₀ splines), live viewport, STL→π₀ import & repair, toolpath preview, and one-click exports.

### Curve/Shape Libraries
Superellipse, π₀ splines, advanced shapes, and hyperbolic families (geodesics, horocycles, tilings).

### STL Repair & Smoothing
Fix non-manifold edges, normals, degenerate faces; optional smoothing with π₀-aware operations.

### 3D Printing Ready
Export STL / 3MF / G-code with layer previews and basic time estimates.

### FreeCAD Workbench + Blender Add-on
Generate π₀ objects, import/export, and hand off assets to your DCC/CAD pipeline.

## 📦 What’s where (top-level)

Key launchers and modules live at repo root and under `adaptivecad/`:

- `run_enhanced_playground.py` / `run_full_playground.py` — launch the Playground
- `adaptivecad/gui/playground.py` — main GUI implementation
- `adaptivecad/gui/analytic_viewport.py` — Analytic SDF viewport + panel (Mandelbulb etc.)
- `adaptivecad/aacore/sdf.py` — CPU SDFs and scene packing (kept in sync with shaders)
- `environment.yml` — conda env (PySide6 + pythonocc-core)
- `check_environment.ps1|.py`, `check_qt.py` — diagnostics (optional)

## 🖥️ Requirements

- Windows 10/11 (primary target)
- Python 3.10+ (3.12 works fine in venv path)
- OpenGL-capable GPU/driver (for Analytic viewport)
- Optional: Miniconda/Conda if you want OCC (`pythonocc-core`)

## 🚀 Quick Start (Windows-first, no OCC required)

### ⚡ Fastest Path: Analytic Viewport Only

**Want just the 3D analytic shapes viewer? Start here:**

1) Create a virtual environment (navigate to repo first):

```powershell
cd AdaptiveCAD  # Navigate to project directory
python -m venv .venv
```

2) Install minimal dependencies (skip activation if blocked by execution policy):

```powershell
..\.venv\Scripts\python.exe -m pip install -U pip wheel
..\.venv\Scripts\python.exe -m pip install PySide6 numpy PyOpenGL Pillow mpmath
```

3) Launch the Analytic Viewport directly:

```cmd
cmd /c "cd /d YOUR_PATH\AdaptiveCAD && ..\.venv\Scripts\python.exe analytic_viewport_launcher.py"
```

**Or create a batch file** `launch_analytic.bat` in the AdaptiveCAD directory:
```batch
@echo off
cd /d "%~dp0"
call ..\.venv\Scripts\activate.bat
python analytic_viewport_launcher.py
pause
```

**What you get:** Standalone 3D analytic shapes viewer with Mandelbulb, Klein Bottle, Gyroid, Trefoil, Sphere, Torus, and more - all with real-time OpenGL rendering.

---

### Full Playground Options

Pick A (simple venv) if you want parametric editors plus analytic shapes. Pick B (conda) if you also want OCC-based modeling/import.

### A) Simple venv (Full playground with analytic shapes)

1) Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -U pip wheel
# Minimal deps for the Enhanced/Full Playground analytic path
pip install PySide6 numpy PyOpenGL
# Optional but nice: Pillow (textures), mpmath (high-precision math)
pip install Pillow mpmath
```

2) Launch the Enhanced or Full Playground (repo root):

```powershell
# Enhanced UI with all analytic shapes
./.venv/Scripts/python.exe run_enhanced_playground.py

# Or the Full variant
./.venv/Scripts/python.exe run_full_playground.py
```

3) In the app, open the Analytic panel and add shapes:
    - View → "Show Analytic Viewport (Panel)"
    - In "Primitives", click: "Add Mandelbulb" (and others)

Notes:
- OCC features (B-Rep modeling/import) are optional and will be stubs in this path.
- If you see a blank/black view, update your GPU driver; the viewport uses OpenGL via PyOpenGL.

### B) Conda env (adds optional OCC integration)

1) Create the environment from the provided `environment.yml` (Windows):

```powershell
conda env create -f environment.yml
conda activate adaptivecad
```

2) Launch the Playground:

```powershell
python run_enhanced_playground.py
```

This installs `pythonocc-core` alongside PySide6/numpy for the OCC viewer and modeling commands. Analytic shapes still work the same via the View → Analytic Viewport (Panel).

### Troubleshooting

- **PowerShell execution policy blocks Activate.ps1:**
   - Use the direct Python executable path as shown above: `..\.venv\Scripts\python.exe`
   - Or use `cmd.exe` with `..\.venv\Scripts\activate.bat`
   
- **"Can't open file" errors:**
   - Make sure you're in the correct directory (AdaptiveCAD subfolder, not root)
   - Use `cd AdaptiveCAD` first, then run commands with `..\.venv\...` paths
   
- **Qt platform plugin error:**
   - Ensure you're using the venv's Python: `..\.venv\Scripts\python.exe -c "import PySide6; print('OK')"`
   - Try upgrading: `..\.venv\Scripts\python.exe -m pip install -U PySide6`
   
- **No OpenGL context / black viewport:**
   - Update graphics drivers; try running on your discrete GPU if you have both iGPU/dGPU
   - For analytic viewport only: Use the direct launcher `analytic_viewport_launcher.py`
   
- **OCC features missing:**
   - That's expected on the venv path. Use the conda path (B) to add `pythonocc-core`
   
- **Path confusion:**
   - Repository structure: `YOUR_PATH\AdaptiveCAD\` (venv here) and `YOUR_PATH\AdaptiveCAD\AdaptiveCAD\` (scripts here)
   - Always run from the inner AdaptiveCAD directory for script execution

## 🔑 API keys (OpenAI)

AdaptiveCAD reads the OpenAI API key from the `OPENAI_API_KEY` environment variable (see `adaptivecad/ai/openai_client.py`). Keys should never be committed to the repo.

### Local (Windows PowerShell)

Temporary for the current terminal session:

```powershell
$env:OPENAI_API_KEY = 'sk-your-key'
```

Persist for new terminals (User environment variables):

```powershell
setx OPENAI_API_KEY "sk-your-key"
# Close and reopen the terminal to take effect
```

Notes:
- `.gitignore` already excludes `.env`, `.env.*`, and common secret folders.
- If a key may have leaked, rotate it in your OpenAI account and update your env/secrets.

### CI (GitHub Actions)

Store the key as a repository Secret named `OPENAI_API_KEY` (Settings → Secrets and variables → Actions), then reference it in workflow steps that need it:

```yaml
- name: Run tests that require OpenAI
   if: ${{ secrets.OPENAI_API_KEY != '' }}
   env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
   run: |
      pytest -q tests/test_ai_bridge.py
```

Prefer mocking network calls in CI; gate any live calls behind the `if:` check above so the pipeline still passes when the secret isn’t present.

## 🧪 Try it quickly

```powershell
./.venv/Scripts/python.exe run_enhanced_playground.py
# View → Show Analytic Viewport (Panel) → Add Mandelbulb
```

Optional diagnostics (PowerShell):

```powershell
python check_qt.py     # simple Qt smoke test
python check_environment.py  # broader environment check
```

### Radial Tool Wheel (overlay)

A new holographic radial tool wheel overlay is included for quick tool access. It’s auto-wired into the Playground’s main viewport. You can also run the minimal demo:

```powershell
./.venv/Scripts/python.exe examples/demo_radial_wheel.py
```

Current mappings focus on existing 3D commands (Move, Sphere, etc.) with placeholders for upcoming 2D sketch tools. The wheel fades near the cursor center and allows right-drag to rotate.

### Anisotropic Distance (plugin)

A compact anisotropic fast-marching (FMM-lite) demo is included as a plugin and CLI.

- In the Playground GUI: Plugins → "Anisotropic Distance (FMM-lite)" → "Compute Demo" or "Trace Geodesic".
- From the command line (repo root):

```powershell
./.venv/Scripts/python.exe plugins/aniso_distance_plugin.py --mode demo
./.venv/Scripts/python.exe plugins/aniso_distance_plugin.py --mode trace
```

See `README_ANISO_DISTANCE.md` for details and Blender/FreeCAD hooks.
## 🧩 Key Workflows

1. **Parametric shapes → export**
   - Open Playground → Shapes panel.
   - Pick Superellipse or π₀ Spline, tweak parameters (a, b, n, points).
## 🧰 FreeCAD / Blender (optional)

- FreeCAD workbench lives under `freecad/AdaptiveCADPIToolpath/`.
- Blender add-on starter lives under `blender_addons/`.

These are optional; the Playground runs standalone.
   - Click Export to save STL/3MF, or Generate G-code for printing.

2. **STL → repair → π₀ smoothing**
   - Import a messy STL.
   - Run Repair (non-manifold, normals, decimate).
   - Enable π₀ Smooth (optional) and preview the toolpath.
   - Export ready-to-print output.

3. **Hyperbolic families**
   - Open Hyperbolic tab: create geodesics/horocycles, or tiling presets.
   - Convert curves to meshes, combine with param shapes, and export.

## 🧪 Examples

```powershell
# Rebuild a param sweep and export STL
python quick_start_demo.py --shape superellipse --a 40 --b 25 --n 3.2 --out ./examples/superellipse.stl

# Repair an STL and export G-code
python import_stl_to_pi.py --in ./examples/janky_part.stl --repair --gcode ./examples/janky_part_fixed.gcode
```

More in `examples/` and `docs/PLAYGROUND_GUIDE.md`.

## 📐 Scaling & Smoothness

AdaptiveCAD stores geometry as π₀ splines and parametric surfaces, then tessellates at export with adaptive error bounds.

- Set `max_angle_err` and `max_chord_err` to control smoothness independently of model size.
- Re-slice large prints with locked nozzle width/layer height to preserve surface quality.
- Use Curvature Preview to see where the tessellator adds triangles at larger scales.

Example (CLI exports):

```powershell
# High-fidelity STL regardless of size
python export_slices.py \
   --in ./examples/smooth_panel.acproj \
   --stl ./out/smooth_panel_scaled.stl \
   --max_angle_err 0.5 --max_chord_err 0.05

# Scale model and keep physical print params consistent
python quick_start_demo.py \
   --shape superellipse --a 40 --b 25 --n 3.2 --scale 10 \
   --out ./out/superellipse_x10.3mf --lock_print_params
```

## 🧰 FreeCAD Workbench (v0.1)

Copy the folder `freecad/AdaptiveCADPIToolpath/` into your FreeCAD Mod directory.

Launch FreeCAD → enable the workbench → AdaptiveCADPI Toolpath.

Generate π₀ objects and toolpaths; export to STL/3MF.

See `docs/PLAYGROUND_GUIDE.md` for a quick tour.

## 🎬 Blender Add-on (starter)

1. `Edit → Preferences → Add-ons → Install…`
2. Select the zip in `blender_addons/adaptivecad_pia/`.
3. Enable “AdaptiveCAD π₀” and use `Add → Mesh → π₀ Object`.

## 🧱 Roadmap (Scope B)

- **v0.1-alpha:** Playground core + param editors + basic repair + STL export
- **Alpha updates:** Hyperbolic library v1, GIF export, preset save/load
- **Beta:** 3MF export, G-code v2 (infill presets), Undo/Redo, FreeCAD parity
- **1.0:** Signed installers, docs site, examples pack
- **Stretch (post-1.0):** GPU kernels, constraint solver, expanded CAM finishing

Follow progress on the Issues and Projects tabs. We post short GIF updates every 1–2 weeks.

## 🧮 Math & Design Notes

Adaptive π (π₀) removes saw-tooth artifacts by operating directly on smooth curve families and π₀ splines.

Hyperbolic geometry tooling includes geodesics/horocycles and basic tilings for curvature-aware designs.

Infinity Root geometry is available as a descriptor layer with reconstructible root-jet data,
canonical integer pages, explicitly tagged fractional gauge views, a curvature-survival audit,
and a quad-only Infinity Book demo. See [`INFINITY_ROOT_ADAPTIVECAD.md`](INFINITY_ROOT_ADAPTIVECAD.md).

Repair focuses on non-manifold edges, flipped normals, zero-area faces, and optional decimation before smoothing.

Detailed references: `docs/MATH_REFERENCE.md`, `docs/HYPERBOLIC_GEOMETRY_IMPLEMENTATION.md`.

## 🏗️ Building & Packaging

### Dev build

```bash
pip install -r requirements-dev.txt
pytest  # run unit tests (if present)
```

### Windows packaging (maintainers)

```powershell
# Example: PyInstaller (adjust spec as needed)
pyinstaller run_enhanced_playground.py -n AdaptiveCAD-Playground --noconsole --onefile

# Or MSIX packaging (recommended for signed installs)
# See scripts/msix/ and CI workflow in .github/workflows/build.yml
```

## 🤝 Contributing

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
