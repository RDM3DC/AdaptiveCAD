# Mandelbulb Generator Documentation

## Overview
The `mandelbulb_make.py` script generates procedural Mandelbulb fractals from mathematical formulas, with swappable color fields and an Adaptive-π hook for experimentation. It exports both STL (geometry only) and PLY (with per-vertex colors) formats.

## Features
- **Pure mathematical generation** - No downloaded meshes, built from the distance estimator formula
- **Multiple color modes** - Smooth escape, orbit traps, angular/phase coloring
- **Adaptive-π experimentation** - Hook for πₐ field effects in fractal generation
- **Efficient marching cubes** - Converts distance field to polygonal mesh
- **Vertex color export** - PLY format preserves colors for visualization

## Installation

```bash
pip install numpy scikit-image trimesh networkx
```

## Basic Usage

```bash
# Quick test with default settings (resolution 160, power 8, orbit coloring)
python mandelbulb_make.py --res 160 --color orbit --power 8 --outfile bulb

# Higher quality render
python mandelbulb_make.py --res 256 --color orbit --power 8 --outfile bulb_hq

# Different fractal powers (changes structure)
python mandelbulb_make.py --res 150 --power 5 --outfile bulb_p5
python mandelbulb_make.py --res 150 --power 3 --outfile bulb_p3
```

## Color Modes

### 1. Normalized Iteration (`--color ni`)
Smooth escape-time coloring using an Inigo Quilez-style cosine palette. Creates rainbow-like gradients based on iteration count.

```bash
python mandelbulb_make.py --res 160 --color ni --outfile bulb_rainbow
```

### 2. Orbit Traps (`--color orbit`)
Colors based on how close the orbit gets to geometric traps:
- Plane trap: Distance to Y=0 plane
- Shell trap: Distance to radius=1 sphere
Creates yellow-blue gradients with structure-highlighting effects.

```bash
python mandelbulb_make.py --res 160 --color orbit --outfile bulb_traps
```

### 3. Angular/Phase (`--color angle`)
- Hue from azimuth angle (φ)
- Saturation from polar angle (θ)
Creates directionally-colored surfaces showing angular structure.

```bash
python mandelbulb_make.py --res 160 --color angle --outfile bulb_angular
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--res` | 160 | Grid resolution per axis (e.g., 128, 160, 256) |
| `--power` | 8.0 | Mandelbulb power (affects fractal structure) |
| `--bailout` | 8.0 | Escape radius for iteration |
| `--max-iter` | 14 | Maximum fractal iterations |
| `--bounds` | [-1.6,1.6,-1.6,1.6,-1.6,1.6] | Sampling volume (xmin xmax ymin ymax zmin zmax) |
| `--color` | orbit | Color mode: ni, orbit, or angle |
| `--outfile` | mandelbulb | Output base filename (no extension) |

## Adaptive-π Features

The script includes a hook for Adaptive-π experimentation, allowing dynamic π values during fractal generation:

```bash
# Enable adaptive π with parameters
python mandelbulb_make.py --res 160 --color orbit --power 8 \
    --pi-mode adaptive \
    --pi-base 3.1415926535 \
    --pi-alpha 0.01 \
    --pi-mu 0.05 \
    --outfile bulb_adaptive
```

### Adaptive-π Parameters
- `--pi-mode`: "fixed" (default) or "adaptive"
- `--pi-base`: Target π value (default: 3.1415926535...)
- `--pi-alpha`: Gradient term for πₐ adjustment (default: 0.0)
- `--pi-mu`: Decay rate toward base π (default: 0.05)

The adaptive system uses:
- A metric value (currently |z|) to adjust πₐ
- Gradient descent: `πₐ -= α * metric_val`
- Decay to base: `πₐ -= μ * (πₐ - π_base)`

## Output Files

The script generates two files:
1. **`{name}.stl`** - Geometry only, compatible with all 3D software
2. **`{name}_color.ply`** - Includes per-vertex RGB colors

## Performance Tips

### Resolution Guidelines
- **100-128**: Fast preview (1-2 minutes)
- **160**: Good quality/speed balance (2-5 minutes)
- **200-256**: High quality (5-15 minutes)
- **300+**: Very high quality (15+ minutes)

### Memory Usage
Resolution memory scales as O(n³):
- res=100: ~4MB field
- res=200: ~32MB field
- res=300: ~108MB field

### Optimization Suggestions
1. Start with low resolution for parameter tuning
2. Use `--bounds` to focus on interesting regions
3. Adjust `--max-iter` based on detail needs (10-20 typical)
4. Consider parallel processing for production renders

## Examples Gallery

```bash
# Classic Mandelbulb (power 8)
python mandelbulb_make.py --res 200 --power 8 --color orbit --outfile classic

# Lower power variants
python mandelbulb_make.py --res 180 --power 5 --color ni --outfile power5
python mandelbulb_make.py --res 180 --power 3 --color angle --outfile power3

# Zoomed detail
python mandelbulb_make.py --res 256 --bounds -0.8 0.8 -0.8 0.8 -0.8 0.8 --outfile detail

# High iteration detail
python mandelbulb_make.py --res 200 --max-iter 20 --color orbit --outfile detailed

# Adaptive-π experiment
python mandelbulb_make.py --res 160 --pi-mode adaptive --pi-alpha 0.02 --outfile adaptive
```

## Extending the Code

### Adding New Color Modes
Add a new case in `color_from_orbit()`:
```python
elif mode == 'mycolor':
    # Use orbit data: orbit['nu'], orbit['trapPlane'], orbit['lastZ'], etc.
    rgb = my_coloring_function(orbit)
    return (np.clip(rgb * 255.0, 0, 255)).astype(np.uint8)
```

### Modifying the Fractal Formula
Edit `mandelbulb_orbit()` to change the iteration:
- Adjust the power raising formula
- Add orbit traps for new geometric shapes
- Modify the distance estimator calculation

### Adaptive-π Integration
Replace the simple `pi_adaptive()` with your full implementation:
- Two-phase (near/far) regime detection
- Curvature-based adjustments
- Angle reduction modulo πₐ

## Troubleshooting

### "ValueError: math domain error"
- Already fixed in current version
- Occurs when r ≤ 1 in logarithm calculation

### Empty mesh (0 vertices)
- Increase `--max-iter` 
- Adjust `--bounds` to include the fractal
- Check `--bailout` isn't too small

### Slow generation
- Reduce `--res` for faster preview
- Use PyPy for ~2x speedup
- Consider GPU acceleration for production

### Color issues in viewers
- Some STL viewers ignore PLY colors
- Use MeshLab, Blender, or CloudCompare for color PLY viewing
- Convert to OBJ+MTL if needed for specific software

## Integration with AdaptiveCAD

This Mandelbulb generator can be integrated with AdaptiveCAD's:
- **Analytic viewport** - Import as SDF primitive
- **π-field system** - Use adaptive-π for field-based deformations  
- **Multi-scale engine** - Generate at multiple resolutions
- **Shape builder** - Combine with other primitives

## License
Part of AdaptiveCAD - see main LICENSE file.