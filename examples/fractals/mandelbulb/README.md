# Mandelbulb Shader Viewer

This example hosts a turnkey Mandelbulb distance-estimator shader inside a
PySide6/OpenGL viewer.  It mirrors the reference fragment shader that can be
copied directly into engines such as Three.js, Godot, Unity (URP/HDRP custom
pass), or Shadertoy.

## Run the viewer

```powershell
python examples/fractals/mandelbulb/mandelbulb_viewer.py
```

The window exposes:

- **Color mode** toggle (Smooth NI, Orbit Trap, Angular/phase)
- **Fractal power** (`uPower`) spin box
- **Orbit-shell radius** (`uOrbitShellR`) spin box

The viewer streams time into the shader (`uTime`) and normalises the light
vector (`uLightDir`) for you.  Resize the window to update the `uResolution`
uniform automatically.

## Shader files

- `fullscreen_quad.vert` – simple full-screen triangle strip
- `mandelbulb.frag` – Mandelbulb DE ray-marcher with the three color-field
  modes baked in

The fragment shader keeps the same uniform layout used in the README notes, so
you can lift it straight into your preferred renderer.  The only alteration is
switching to `#version 330 core` with a guarded precision qualifier so that it
compiles both on desktop GL and GLES/WebGL backends.
