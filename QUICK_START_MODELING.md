# Quick Reference - Build from Scratch

## The 3-Step Workflow

```
1. SKETCH (2D) → 2. MODEL (3D) → 3. EXPORT (G-code)
```

## Essential Shortcuts

### Sketching
- `R` - Rectangle
- `C` - Circle  
- `L` - Line

### Modeling
- `E` - Extrude selected

### Tools
- `G` - Move/Grab
- `S` - Scale
- `M` - Measure

### Boolean
- `Ctrl+U` - Union
- `Ctrl+Shift+B` - Subtract

## Common Workflows

### Simple Box
```
R → 10×10 → E → 15mm
```

### Rounded Box
```
R → 10×10 → E → 15mm → Modify → Fillet → 1mm
```

### Hollow Container
```
C → radius 8 → E → 20mm → Modify → Shell → 2mm
```

### Bracket
```
R → 20×10 → E → 5mm (base)
R → 10×8 → Move → E → 15mm (wall)
Operations → Union
```

### Mounting Hole
```
C → radius 2 → Move to position → E → 6mm
Operations → Subtract
```

## Menu Organization

```
File ─┬─ New/Open/Save
      ├─ Import (STL/OBJ)
      └─ Export (G-code)

Edit ─┬─ Undo/Copy/Paste
      ├─ Array (Linear/Circular/Grid)
      ├─ Align (Min/Center/Max)
      └─ Transform (Mirror/Snap)

Sketch ─┬─ Rectangle (R)
        ├─ Circle (C)  
        ├─ Ellipse
        ├─ Polygon
        └─ Line (L)

Model ─┬─ Extrude (E)
       ├─ Revolve
       ├─ Loft
       ├─ Work Plane
       ├─ Axis
       └─ Reference Point

Modify ─┬─ Fillet (round)
        ├─ Chamfer (bevel)
        ├─ Shell (hollow)
        ├─ Offset (expand/shrink)
        └─ Thicken

Operations ─┬─ Union (Ctrl+U)
            ├─ Subtract (Ctrl+Shift+B)
            └─ Intersect

Tools ─┬─ Measure (M)
       └─ Analyze Volume
```

## Tips

1. **Always sketch first** - Rectangle/Circle → Extrude
2. **Fillet last** - Add after main features
3. **Shell for hollow** - Vases, containers, lightweight
4. **Array for patterns** - Bolt holes, gears
5. **Measure often** - Press M to check distances

## Example: Complete Part in 2 Minutes

```
1. R → 40×30 (base)
2. E → 5mm
3. R → 30×20 (wall)  
4. Move → Y+15, Z+2.5
5. E → 25mm
6. C → r=2 (hole)
7. Move → corner position
8. Copy → other corner
9. E → 6mm
10. Select holes → Ctrl+Shift+B (subtract)
11. Select all → Modify → Fillet → 2mm
12. Modify → Shell → 2mm
13. File → Export → G-code
```

**Done! Professional bracket, zero triangles!** 🎉

---

For detailed tutorials, see **MODELING_FROM_SCRATCH.md**
