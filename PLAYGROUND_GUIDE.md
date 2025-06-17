# AdaptiveCAD Playground - User Guide

This guide explains how to use the AdaptiveCAD Playground interface, including all available basic shapes, advanced shapes, and modeling tools.

## Getting Started

You can start the AdaptiveCAD Playground in several ways:

1. Using the VS Code task:
   - Run the "Run AdaptiveCAD GUI Playground" task

2. Using one of the provided scripts:
   - `run_full_playground.py` - Python script to run the full playground
   - `run_full_playground.bat` - Windows batch file to run the full playground
   - `run_full_playground.ps1` - PowerShell script to run the full playground

## Interface Overview

The AdaptiveCAD Playground interface consists of:

- **Menubar**: Contains menus for Basic Shapes, Advanced Shapes, and Modeling Tools
- **Toolbar**: Quick access to common shapes and modeling operations
- **3D Viewer**: Main area showing the 3D scene
- **Status Bar**: Shows messages and current operations

## Basic Shapes

The following basic shapes are available:

- **Box**: Create a rectangular box by specifying width, depth, and height
- **Cylinder**: Create a cylinder by specifying radius and height
- **Ball**: Create a sphere by specifying radius
- **Torus**: Create a torus (donut) by specifying major and minor radii
- **Cone**: Create a cone by specifying base radius and height

## Advanced Shapes

The following advanced parametric shapes are available:

- **Superellipse**: Create a superellipse shape (rounded rectangle with adjustable roundness)
  - Parameters: X radius, Y radius, exponent (n), segments

- **Pi Curve Shell (πₐ)**: Create a parametric surface based on πₐ curves
  - Parameters: Base radius, height, frequency, amplitude, phase

- **Helix/Spiral**: Create a helical or spiral shape
  - Parameters: Base radius, height, pitch, turns, wire radius

- **Tapered Cylinder**: Create a cylinder with different top and bottom radii
  - Parameters: Bottom radius, top radius, height

- **Capsule/Pill**: Create a pill/capsule shape (cylinder with hemispherical ends)
  - Parameters: Radius, height

- **Ellipsoid**: Create an ellipsoid (stretched sphere)
  - Parameters: X radius, Y radius, Z radius

For detailed documentation on advanced shapes, see [ADVANCED_SHAPES.md](ADVANCED_SHAPES.md)

## Modeling Tools

The following modeling tools are available:

### Transformation Tools

- **Move**: Translate a shape in 3D space
  - Select a shape, then enter X, Y, Z translation values

- **Scale**: Resize a shape uniformly
  - Select a shape, then enter a scale factor

### Boolean Operations

- **Union**: Combine two shapes (Boolean OR)
  - Select two shapes to combine them into one

- **Cut**: Subtract one shape from another (Boolean difference)
  - First select the base shape, then select the shape to subtract

- **Intersect**: Create the common volume between two shapes (Boolean AND)
  - Select two shapes to create their intersection

### Other Operations

- **Shell**: Create a hollow version of a solid with specified wall thickness
  - Select a shape and specify the wall thickness

For detailed documentation on modeling tools, see [MODELING_TOOLS.md](MODELING_TOOLS.md)

## Workflow Tips

1. **Create Basic Shapes First**: Start by creating the basic primitive shapes you need

2. **Position Shapes**: Use the Move tool to position shapes correctly before applying boolean operations

3. **Apply Boolean Operations**: Use Union, Cut, and Intersect to combine shapes

4. **Add Advanced Shapes**: Add advanced parametric shapes for more complex geometries

5. **Apply Finishing Operations**: Use Shell to hollow out shapes if needed

## Troubleshooting

- **If shapes don't appear**: Make sure the view is properly zoomed (use mouse wheel)

- **If boolean operations fail**: Check that shapes properly overlap or intersect

- **If the application crashes**: Check that you have all dependencies installed by running `check_environment.py`

## Getting Help

For additional help, refer to:
- [README.md](README.md) - General overview of the project
- [ADVANCED_SHAPES.md](ADVANCED_SHAPES.md) - Details on advanced shape parameters
- [MODELING_TOOLS.md](MODELING_TOOLS.md) - Details on modeling operations
