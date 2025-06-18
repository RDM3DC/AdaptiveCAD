# Cosmic Curve Tools for AdaptiveCAD

This document describes the new cosmic curve tools that have been added to AdaptiveCAD's Advanced Shapes and Cosmic Exploration menus.

## New Features Added

### 1. Bizarre Curve
A mathematically complex curve with hyperbolic and transcendental distortions.

**Features:**
- Uses the adaptive pi function (πₐ) for hyperbolic distortions
- Incorporates chaotic perturbations for organic appearance  
- Transcendental mathematical transformations
- Configurable frequency, distortion, and segment count

**Parameters:**
- Base Radius: The fundamental radius of the curve
- Height: Overall height of the curve
- Frequency: Controls the number of oscillations
- Distortion: Strength of hyperbolic/chaotic effects
- Segments: Number of points for curve resolution

### 2. Cosmic Spline
A spline curve that follows spacetime curvature patterns.

**Features:**
- Applies Schwarzschild-like metric transformations
- Uses cosmic curvature parameters
- Automatic control point generation with cosmic effects
- Integration with AdaptiveCAD's hyperbolic geometry

**Parameters:**
- Control Points: Number of control points (3-20)
- Curve Degree: Mathematical degree of the spline (1-5)
- Cosmic Curvature: Strength of spacetime effects (0.0-2.0)
- Point Spread: Spatial distribution of control points

### 3. ND Field Explorer
N-dimensional field visualization and exploration tool.

**Features:**
- Support for 2-8 dimensional fields
- Multiple field types: scalar waves, quantum fields, cosmic web structures
- 3D visualization of higher-dimensional data
- Integration with AdaptiveCAD's NDField system

**Parameters:**
- Dimensions: Number of field dimensions (2-8)
- Grid Size: Resolution of the field grid (2-20)
- Field Type: Type of field to generate
  - `scalar_wave`: Multi-dimensional wave patterns
  - `quantum_field`: Quantum vacuum fluctuations
  - `cosmic_web`: Large-scale structure patterns
  - `random`: Random field values

### 4. Light Cone Display Box
A comprehensive spacetime visualization tool featuring light cones within a display box.

**Features:**
- Interactive light cone geometry creation
- Spacetime coordinate grid overlay
- Configurable display box with wireframe
- Future and past light cone visualization
- Real-time parameter adjustment

**Parameters:**
- Display Box Size: Overall size of the visualization container (10-500 units)
- Light Cone Radius: Radius of the light cone geometry (1-50 units)
- Grid Spacing: Spacing between grid lines (1-20 units)
- Show Spacetime Grid: Toggle coordinate grid display
- Show Coordinates: Toggle coordinate system display

## How to Access

### Method 1: Advanced Shapes Menu
1. Open AdaptiveCAD: `python -m adaptivecad.gui.playground`
2. Click "Advanced Shapes" in the menu bar
3. Find the new tools after the separator:
   - Bizarre Curve
   - Cosmic Spline  
   - ND Field Explorer

### Method 2: Cosmic Exploration Menu
1. Open AdaptiveCAD: `python -m adaptivecad.gui.playground`
2. Click "Cosmic Exploration" in the menu bar
3. Navigate to submenus:
   - **"Spacetime & Relativity"** → Light Cone Display Box
   - **"Cosmic Curve Tools"** → Bizarre Curve, Cosmic Spline, ND Field Explorer
4. Select the desired tool

## Technical Implementation

### File Structure
```
adaptivecad/
├── cosmic/
│   ├── __init__.py           # Updated with new commands
│   ├── curve_tools.py        # New: All curve tool implementations
│   ├── spacetime_viz.py      # Existing
│   ├── quantum_geometry.py   # Existing
│   └── ...
└── gui/
    └── playground.py         # Updated: Added menu integrations
```

### Key Classes
- `BizarreCurveFeature`: Feature class for bizarre curves
- `CosmicSplineFeature`: Feature class for cosmic splines
- `NDFieldExplorerFeature`: Feature class for ND field exploration
- `BizarreCurveCmd`: GUI command for bizarre curves
- `CosmicSplineCmd`: GUI command for cosmic splines
- `NDFieldExplorerCmd`: GUI command for ND field explorer
- `LightConeDisplayBoxCmd`: GUI command for light cone display box
- `SpacetimeVisualizationCmd`: Enhanced spacetime visualization with 3D geometry

### Dependencies
- PySide6 (for GUI dialogs)
- NumPy (for mathematical computations)
- OpenCascade (for 3D geometry creation)
- AdaptiveCAD's ndfield module
- AdaptiveCAD's hyperbolic geometry module

## Mathematical Background

### Bizarre Curve Mathematics
The bizarre curve uses several mathematical transformations:

1. **Hyperbolic Distortion**: Uses `pi_a_over_pi(t * distortion)` 
2. **Transcendental Functions**: Combines sin, cos, exp for organic shapes
3. **Chaotic Perturbations**: Adds small-scale noise for natural appearance

### Cosmic Spline Mathematics  
The cosmic spline applies spacetime metric effects:

1. **Metric Transformation**: `scale = 1.0 + cosmic_curvature * exp(-r/10.0)`
2. **Curvature Factor**: Uses adaptive pi function for warping
3. **Schwarzschild-like Effects**: Distance-dependent scaling

### ND Field Mathematics
The field explorer generates various field types:

1. **Scalar Waves**: `sum(sin(coord_i * (i+1)))`
2. **Quantum Fields**: `sqrt(real^2 + imag^2)` from Gaussian noise
3. **Cosmic Web**: `product(1 + 0.5*sin(coord_i * π * (i+2)))`

## Testing

Run the test suite to verify everything works:
```bash
python test_cosmic_curve_tools.py
```

This will test:
- Import functionality
- Cosmic module integration
- Feature creation without GUI

## Future Enhancements

Potential improvements:
1. Interactive parameter adjustment in 3D view
2. Animation of curve evolution over time
3. Export to various CAD formats
4. Integration with physics simulation
5. Real-time field visualization updates
