# AdaptiveCAD Playground

This directory contains the main GUI playground for AdaptiveCAD, a curvature-first CAD/CAM system based on Adaptive Pi Geometry.

## Quick Start

### Option 1: Enhanced Launcher (Recommended)
```bash
python run_playground_enhanced.py
```

### Option 2: Direct Module Execution
```bash
python -m adaptivecad.gui.playground
```

### Option 3: Demo Mode (for testing/CI)
```bash
python -m adaptivecad.gui.playground --demo
```

## Environment Setup

### Required Dependencies
- `numpy` - Mathematical computations
- `pyside6` - Qt GUI framework

### Optional Dependencies
- `pythonocc-core` - OpenCASCADE integration (for advanced 3D features)

### Install Dependencies
```bash
pip install numpy pyside6
```

## Platform Support

### Desktop (Windows/Linux/macOS)
The playground runs as a full GUI application with 3D viewer and all modeling tools.

### Headless/CI Environments
The playground automatically detects headless environments and runs in offscreen mode, allowing for:
- Automated testing
- Continuous integration
- Server deployments

### Display Issues
If you encounter display issues, try:
```bash
# Use offscreen rendering
QT_QPA_PLATFORM=offscreen python -m adaptivecad.gui.playground

# Use enhanced launcher with automatic environment detection
python run_playground_enhanced.py
```

## Features

### 3D Modeling Tools
- Basic primitives (box, cylinder, sphere, cone, torus)
- Advanced shapes (superellipse, pi-curve shell, helix)
- Boolean operations (union, cut, intersect)
- Transformations (move, scale, mirror)

### Analytic Viewport
- Real-time SDF (Signed Distance Field) rendering
- GPU-accelerated raymarching
- Interactive scene manipulation

### Import/Export
- STL import/export
- AMA (Adaptive Math Archive) format
- G-code generation for 3D printing

## Testing

Run the comprehensive test suite:
```bash
python test_playground_comprehensive.py
```

Run specific pytest tests:
```bash
pytest tests/test_playground.py -v
```

## Architecture

The playground follows a modular architecture:

- `playground.py` - Main application window and GUI logic
- `analytic_viewport.py` - Real-time SDF rendering panel
- `viewcube_widget.py` - 3D navigation cube
- `nd_chess_widget.py` - Multi-dimensional chess demo (optional)

## Troubleshooting

### Common Issues

1. **Import Errors**: Install missing dependencies with `pip install numpy pyside6`
2. **Display Issues**: Use the enhanced launcher or set `QT_QPA_PLATFORM=offscreen`
3. **GUI Hanging**: Use demo mode `--demo` for automated testing

### Environment Validation
```bash
python check_environment.py
```

### Debug Mode
```bash
python -m adaptivecad.gui.playground --demo
```

## Development

### Adding New Features
1. Add command classes following the existing pattern
2. Register commands in `_create_menus_and_toolbar()`
3. Add tests in `tests/test_playground.py`

### Code Style
- Follow existing patterns for consistency
- Use logging instead of print statements
- Handle errors gracefully with fallbacks

For more information, see the main project documentation.