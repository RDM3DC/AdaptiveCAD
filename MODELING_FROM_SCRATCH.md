## Building Models from Scratch - Complete Guide

This guide shows you how to create complex 3D models from basic primitives using AdaptiveCAD's professional modeling tools.

## Table of Contents

1. [Philosophy](#philosophy)
2. [Quick Start - Simple Box](#quick-start)
3. [2D Sketching](#2d-sketching)
4. [3D Modeling](#3d-modeling)
5. [Edge Modification](#edge-modification)
6. [Surface Operations](#surface-operations)
7. [Construction Geometry](#construction-geometry)
8. [Complete Example: Building a Custom Part](#complete-example)
9. [Tools Reference](#tools-reference)

---

## Philosophy

AdaptiveCAD uses **Signed Distance Fields (SDFs)** instead of triangular meshes. This means:
- ✅ **No triangulation errors** - surfaces are mathematically perfect
- ✅ **Infinite resolution** - zoom in as much as you want
- ✅ **Direct slicing** - no STL conversion needed
- ✅ **Smooth operations** - fillet, offset, shell work perfectly

**Build Workflow:**
1. **Sketch** - Create 2D profiles (rectangles, circles, polygons)
2. **Extrude/Revolve** - Turn 2D into 3D
3. **Modify** - Add fillets, chamfers, shells
4. **Boolean** - Combine, subtract, intersect shapes
5. **Export** - Direct to G-code, no triangles!

---

## Quick Start - Simple Box

**Goal:** Create a rounded box with filleted edges.

```
1. Sketch → Rectangle
   - Width: 20mm
   - Height: 10mm
   
2. Model → Extrude (or press E)
   - Depth: 15mm
   - Result: 20×10×15mm box
   
3. Modify → Fillet
   - Select box
   - Radius: 2mm
   - Result: Smooth rounded edges!
```

**Time:** ~30 seconds  
**Primitives:** 1 (the SDF handles rounding automatically!)

---

## 2D Sketching

### Rectangle Sketch
**Hotkey:** `R`  
**Menu:** Sketch → Rectangle

Creates a thin rectangular profile in the XY plane.

```
Width: 10.0
Height: 5.0
→ Thin rectangle at origin
```

**Tips:**
- Always starts at Z=0 (XY plane)
- Very thin (0.01mm) - designed for extrusion
- Use Move tool (G) to reposition

### Circle Sketch
**Hotkey:** `C`  
**Menu:** Sketch → Circle

Creates a circular profile.

```
Radius: 5.0
→ Thin circle at origin
```

### Ellipse Sketch
**Menu:** Sketch → Ellipse

```
X Radius: 5.0
Y Radius: 3.0
→ Thin ellipse
```

### Polygon Sketch
**Menu:** Sketch → Polygon

```
Radius: 5.0
Sides: 6
→ Hexagon (approximated with cylinder for now)
```

**Note:** Lines and arcs coming soon!

---

## 3D Modeling

### Extrude
**Hotkey:** `E`  
**Menu:** Model → Extrude

Pulls a 2D sketch into 3D along the Z-axis.

```
1. Create rectangle (10×5)
2. Select it
3. Press E
4. Depth: 15mm
→ 10×5×15mm box!
```

**Options:**
- **Centered:** Extrudes equally in +Z and -Z
- **From Base:** Starts at Z=0 and goes up

### Revolve
**Menu:** Model → Revolve

Spins a profile around an axis (creates cylinders, cones, spheres).

```
1. Create rectangle (positioned at X=5)
2. Select it
3. Model → Revolve
4. Axis: Z, Angle: 360°
→ Hollow cylinder!
```

**Use Cases:**
- Bottle shapes
- Rounded forms
- Shafts and tubes

### Loft
**Menu:** Model → Loft

Smoothly transitions between two profiles.

```
1. Create small circle at Z=0
2. Create large circle at Z=20
3. Select both
4. Model → Loft
→ Cone/funnel shape!
```

**Steps:** 10 interpolation layers (configurable)

---

## Edge Modification

### Fillet (Round Edges)
**Menu:** Modify → Fillet

Adds smooth rounded edges.

```
Radius: 2.0mm
→ Edges become rounded with R=2mm
```

**SDF Implementation:**
- Uses offset operation: `d' = d - radius`
- Perfect mathematical roundness
- No faceting or approximation

**Examples:**
- Small radius (0.2mm): Slight edge break
- Medium radius (2mm): Smooth chamfered look
- Large radius (5mm): Heavily rounded, soft edges

### Chamfer (Bevel Edges)
**Menu:** Modify → Chamfer

Adds flat beveled edges.

```
Distance: 1.5mm
→ Edges beveled at 45° angle
```

**Use Cases:**
- Sharp mechanical parts
- 3D printing ease (no sharp corners)
- Aesthetic flat bevels

---

## Surface Operations

### Shell (Hollow Out)
**Menu:** Modify → Shell

Creates a thin-walled hollow version of a solid.

```
Wall Thickness: 2.0mm
→ Hollow interior, 2mm walls
```

**Perfect For:**
- Vases
- Containers
- Lightweight parts
- Saving material

**SDF Implementation:**
```python
inner_sdf = base_sdf + thickness
shell_sdf = max(-base_sdf, inner_sdf)
```

### Offset Surface
**Menu:** Modify → Offset Surface

Expands or shrinks the entire shape.

```
Distance: +2.0mm → Expands outward
Distance: -2.0mm → Shrinks inward
```

**Use Cases:**
- Adding clearance
- Scaling without changing proportions
- Creating molds (negative offset)

### Thicken Surface
**Menu:** Modify → Thicken Surface

Adds thickness to thin surfaces.

```
Thickness: 1.0mm
→ Creates 0.5mm on each side
```

---

## Construction Geometry

Construction geometry provides reference frames for precise modeling.

### Work Plane (Datum Plane)
**Menu:** Model → Work Plane

Creates a reference plane for sketching.

```
Orientation: XY
Offset: 10.0mm
Size: 20.0mm
→ XY plane at Z=10
```

**Orientations:**
- **XY** - Horizontal plane (adjust Z)
- **XZ** - Front/back plane (adjust Y)
- **YZ** - Left/right plane (adjust X)

**Appearance:** Semi-transparent gray

### Datum Axis
**Menu:** Model → Axis

Reference line for revolve/alignment.

```
Axis: Z
→ Z-axis through origin
```

**Appearance:** Orange line

### Reference Point
**Menu:** Model → Reference Point

Marks a specific coordinate.

```
X: 10, Y: 5, Z: 15
→ Red sphere at (10, 5, 15)
```

---

## Complete Example: Building a Custom Part

**Goal:** Create a mechanical bracket with mounting holes.

### Step 1: Base Plate
```
1. Sketch → Rectangle
   Width: 40mm, Height: 30mm

2. Model → Extrude (E)
   Depth: 5mm
   
→ 40×30×5mm base plate
```

### Step 2: Vertical Support
```
1. Sketch → Rectangle
   Width: 30mm, Height: 20mm

2. Move (G) to position:
   Y: +15mm (back of base)
   Z: +2.5mm (centered on base)

3. Model → Extrude (E)
   Depth: 25mm
   
4. Move (G) result:
   Z: +12.5mm (standing up)

→ Vertical wall attached to base
```

### Step 3: Add Mounting Holes
```
1. Sketch → Circle
   Radius: 2mm

2. Move (G) to corner:
   X: +15mm, Y: +12mm

3. Copy (Ctrl+C, Ctrl+V) and move:
   X: -15mm (other corner)

4. Model → Extrude
   Depth: 6mm (through base + margin)

5. Select both holes
6. Operations → Subtract (Ctrl+Shift+B)

→ Two mounting holes
```

### Step 4: Add Fillets
```
1. Select base+support (Ctrl+A)
2. Modify → Fillet
   Radius: 2mm
   
→ Smooth rounded edges everywhere
```

### Step 5: Lightweight Shell
```
1. Select bracket
2. Modify → Shell
   Thickness: 2mm
   
→ Hollow bracket, saves material!
```

### Step 6: Export
```
File → Export → Export G-Code
→ Direct to G-code, no STL, no triangles!
```

**Total Time:** ~5 minutes  
**Primitives Used:** ~6  
**Triangle Count:** ZERO! (SDF-based)

---

## Tools Reference

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Q` | Select mode |
| `G` | Move/Grab |
| `R` | Rotate (tool) / Rectangle (sketch menu) |
| `S` | Scale |
| `C` | Circle sketch |
| `E` | Extrude |
| `L` | Line sketch |
| `M` | Measure distance |
| `F` | Fit all in view |
| `Shift+F` | Fit selected |
| `Ctrl+U` | Union |
| `Ctrl+Shift+B` | Boolean subtract |
| `Ctrl+A` | Select all |
| `Ctrl+D` | Duplicate |
| `Del` | Delete selected |

### View Controls
| Key | View |
|-----|------|
| `Numpad 1` | Front view |
| `Numpad 3` | Right view |
| `Numpad 7` | Top view |
| `Numpad 0` | Isometric |

### Menu Organization

**File** - Project management, import/export  
**Edit** - Undo, copy, paste, select  
**View** - Camera presets, fit view  
**Create** - Add primitives directly  
**Operations** - Boolean operations  
**Modify** - Fillet, chamfer, shell, offset  
**Sketch** - 2D drawing tools  
**Model** - Extrude, revolve, loft, construction  
**Tools** - Measurement, analysis

---

## Advanced Techniques

### Smooth Blending
Select multiple primitives that share edges:
```
Edit → Array → Circular Array
→ Creates radial pattern
Then apply small fillet to blend
```

### Parametric Patterns
```
1. Create single feature
2. Edit → Array → Grid Array
   Count: 5×3, Spacing: 10mm
→ Instant pattern!
```

### Multi-Profile Lofts
```
1. Create circle at Z=0, radius=5
2. Create square at Z=10, size=8
3. Create circle at Z=20, radius=3
4. Select all, Model → Loft
→ Organic smooth transition!
```

---

## Tips & Best Practices

### 1. Start with Sketches
Always begin with 2D profiles, then extrude. This is how professional CAD works.

### 2. Use Construction Geometry
Datum planes help you align features precisely.

### 3. Boolean Order Matters
- **Union first** - combine all positive geometry
- **Subtract last** - remove holes/voids

### 4. Fillet at the End
Add fillets/chamfers after main geometry is complete. Easier to edit.

### 5. Test Slice Early
Export a test slice (single layer) to verify dimensions before full print.

### 6. Save Iterations
Use "Save As" to keep versions: `bracket_v1.acad`, `bracket_v2.acad`

### 7. Measure Often
Press `M` to measure distances between features - catch errors early!

---

## Troubleshooting

**Problem:** Extrude doesn't work  
**Solution:** Make sure you selected a 2D sketch first (thin primitive)

**Problem:** Fillet makes shape disappear  
**Solution:** Radius too large - try smaller value (< 50% of feature size)

**Problem:** Boolean subtraction doesn't cut through  
**Solution:** Make cutting primitive larger - it must fully intersect

**Problem:** Shell creates weird artifacts  
**Solution:** Reduce wall thickness, or simplify base shape first

---

## What's Next?

You now have all the tools to build ANY shape from scratch!

**Next Steps:**
1. Try the complete bracket example above
2. Build a simple vase (circle + extrude + shell)
3. Create a gear (circle array + boolean)
4. Design your own custom part!

**Advanced Topics:**
- Parametric constraints (coming soon)
- Sketch relations (coming soon)
- Pattern along path (coming soon)
- Surface sculpting (coming soon)

---

## Comparison: Triangle vs SDF Workflow

### Traditional (Triangle-Based):
```
1. Model in CAD
2. Export to STL (triangulation)
3. Import to slicer
4. Repair mesh errors
5. Slice
6. G-code
→ 6 steps, lossy conversion
```

### AdaptiveCAD (SDF-Based):
```
1. Model with sketches/primitives
2. Export G-code
→ 2 steps, mathematically perfect!
```

**No triangles = No problems!** 🎉

---

## Resources

- **TOOLS_REFERENCE.md** - Complete tool descriptions
- **BENCHY_GUIDE.md** - Import existing models
- **PLAYGROUND_GUIDE.md** - Programming interface
- **Examples/** - Sample projects

Happy modeling! 🚀
