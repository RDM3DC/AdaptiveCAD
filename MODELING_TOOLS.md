# Modeling Tools in AdaptiveCAD

This document describes the available modeling tools in AdaptiveCAD's playground interface.

## Basic Transformations

### Move
The Move tool allows you to translate (move) objects in 3D space along the X, Y, and Z axes.
- **Parameters**: 
  - Target shape to move
  - dx, dy, dz: distance along each axis (mm)

### Scale
The Scale tool lets you resize an object uniformly.
- **Parameters**:
  - Scale factor (where 1.0 is the original size)

## Boolean Operations

Boolean operations combine or modify shapes using set operations.

### Union
Combines two shapes, keeping the volume from both (A ∪ B).
- **Parameters**:
  - Target shape (A)
  - Tool shape (B)

### Cut
Subtracts one shape from another (A - B).
- **Parameters**:
  - Target shape (A) - the shape to cut from
  - Tool shape (B) - the shape used for cutting

### Intersect
Creates a new shape that represents the volume where two shapes overlap (A ∩ B).
- **Parameters**:
  - Target shape (A)
  - Tool shape (B)

## Other Modeling Operations

### Shell
Creates a shell by hollowing out a solid object with a specified wall thickness.
- **Parameters**:
  - Source shape
  - Thickness (mm)

## Tips for Effective Modeling

1. **Order Matters**: For boolean operations, the order of selection matters:
   - For Cut: first select the base object, then the cutting tool
   - For Union/Intersect: the order affects how the operation is recorded in the model tree

2. **Transformations**: Use Move after creating shapes to position them correctly before performing boolean operations

3. **Workflow Strategy**: 
   - Start with basic shapes
   - Position them using Move
   - Use boolean operations to combine or modify shapes
   - Apply Shell operations at the end if you want to hollow out your model

4. **Troubleshooting**: 
   - If a boolean operation fails, try adjusting the positions to ensure proper overlap
   - Complex boolean operations may fail if shapes have very thin features or non-manifold geometry
