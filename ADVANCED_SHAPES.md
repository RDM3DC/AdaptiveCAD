# AdaptiveCAD Advanced Shape Playground

This enhanced version of the AdaptiveCAD playground includes several advanced parametric shape features, including N-dimensional geometry and πₐ-based shapes.

## Advanced Shapes Available

### Superellipse

The superellipse is a generalization of an ellipse, defined by the equation:

|x/a|^n + |y/b|^n = 1

where:
- a and b are the semi-major and semi-minor axes
- n is the "roundness" parameter that controls the shape
- When n = 2, it's a regular ellipse
- When n < 2, it has a more star-like shape
- When n > 2, it has a more square-like shape (squircle)

### Pi Curve Shell (πₐ)

The Pi Curve Shell is a cylindrical surface deformed by the πₐ (adaptive pi) function, which applies sine-based modifications to the radius depending on the angle. This creates wave-like patterns around the cylinder's circumference.

The πₐ function introduces periodic variations in radius as a function of angle, allowing for:
- Controllable frequency
- Adjustable amplitude
- Phase shifting
- Parameterized height

### Helix / Spiral

A parametric helix shape where:
- Radius controls the diameter of the spiral
- Pitch controls how steep the spiral is
- Height determines the total vertical distance
- Points parameter controls the smoothness

### Tapered Cylinder

A cone-like shape where you can independently control:
- Height
- Bottom radius
- Top radius

This allows creating cylinders, cones, or truncated cones as needed.

### Capsule / Pill

A cylindrical body with hemispherical ends, creating a pill-like shape where:
- Height controls the total length
- Radius controls the thickness
- Useful for character modeling, ergonomic designs, and more

### Ellipsoid

A 3D generalization of an ellipse, where you can independently control:
- X-axis radius
- Y-axis radius
- Z-axis radius

This allows creating spheres, oblate spheroids (disc-like), prolate spheroids (cigar-like), and triaxial ellipsoids.

## Running the Advanced Playground

To run the playground with all advanced features:

```bash
python run_advanced_playground.py
```

## Development Notes

- All advanced shapes are defined at the module level for easy import
- The MainWindow class properly handles both GUI and non-GUI environments
- Each shape provides a dialog for parameter input

## Controls

- **Left mouse button**: Rotate the view
- **Right mouse button**: Pan the view
- **Scroll wheel**: Zoom in/out
