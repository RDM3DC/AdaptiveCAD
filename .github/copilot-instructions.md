# AdaptiveCAD – AI Agent Field Guide

Windows-first Python project combining a PySide6 GUI, analytic SDF renderer, and optional OCC toolchain. Keep edits focused; user-facing panels persist state to `~/.adaptivecad_analytic.json`.

## Architecture & Key Files
- Flow: `adaptivecad/gui` widgets → `adaptivecad/aacore/sdf.py` (scene graph, transforms, packing) → `adaptivecad/analytic/shaders/*.glsl` (GPU ray marcher).
- `adaptivecad/gui/playground.py` hosts the main window; `adaptivecad/gui/analytic_viewport.py` is the analytic control panel/QOpenGLWidget. One-off demos live under `examples/`.
- CPU/GPU parity is critical: every primitive or uniform added in `sdf.py` must be mirrored in `analytic/shaders/sdf.frag` (same param order, kind enums).

## Conventions That Matter
- PySide6 only; no PyQt mix. OpenGL views subclass `QOpenGLWidget`.
- Geometry data uses numpy `float32`. Affine transforms store translation in `M[:3,3]` and are uploaded column-major.
- Boolean ops are string-labelled (`solid`/`subtract`); respect `MAX_PRIMS` limits in panels.
- Settings merges, don’t overwrite: load JSON, update known keys, keep unknown keys intact.

## Working With the Analytic Stack
- `Scene.to_gpu_structs()` returns packed arrays (kinds, ops, params, xforms) sent straight to GLSL uniforms—validate shapes/dtypes when extending.
- Adding SDF/fractal support requires three touchpoints: enum+distance in `sdf.py`, GLSL dispatch + helper in `analytic/shaders/sdf.frag`, GUI wiring (buttons/default params) in `analytic_viewport.py`.
- Viewport debug keys 0–5 swap beauty and analytic buffers; `_save_settings()` persists toggles.

## Dev & Test Workflow (PowerShell)
- Launch playground: `python -m adaptivecad.gui.playground`; standalone viewport: `python analytic_viewport_launcher.py`.
- Diagnostics: `check_environment.ps1` covers Qt/OCC; `check_qt.py` is a quick smoke test.
- Tests: `python -m pytest -q` (some suites expect OCC). Narrow scope with e.g. `pytest tests/test_gui_startup.py -q`.

## Non-Obvious Patterns
- Sketch overlay tools (polyline/circle/rect) live inside `analytic_viewport.py`; grid snap radius (`SNAP_PX`) is defined near their class stubs.
- Optional integrations: FreeCAD modules under `freecad/`, Blender add-ons under `blender_addons/`; treat imports as optional.
- Rendering defaults favor foveated + analytic AA; keep those uniforms in sync when touching shader packs.

## Pitfalls & Gotchas
- Don’t revive legacy modules like `adaptivecad.core.backends`; all active SDF work is under `adaptivecad/aacore`.
- Keep primitive `params` vectors ≤4 floats; push extra data through transforms/colors/uniform structs.
- Stick to ASCII UI labels unless a file already relies on UTF-8 glyphs; previous mojibake came from smart quotes.

## Helpful Utilities
- Scripts: `run_full_playground.py`, `run_enhanced_playground.py`, `run_analytic_viewport.py`, `debug_qt_launch.py`.
- VS Code task “Run AdaptiveCAD GUI Playground” boots the correct environment automatically.

## When Stuck
- Compare CPU and GLSL implementations—naming stays consistent (`KIND_*`, `sd_*`).
- Look at similar primitives (e.g., Mandelbulb) to mirror state plumbing, shader uniforms, and persistence handling.