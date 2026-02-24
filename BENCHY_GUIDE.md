# Making a Perfect Benchy in AdaptiveCAD

## Quick Start: Import & Slice 3DBenchy

### Step 1: Get the 3DBenchy STL

Download the official 3DBenchy from Thingiverse:
- **URL:** https://www.thingiverse.com/thing:763622
- **File:** `3DBenchy.stl` (standard version)
- **Size:** ~60mm long boat model

Alternative sources:
- Prusaprinters: https://www.prusaprinters.org/prints/3161-3dbenchy
- Direct download: Various 3D printing sites

### Step 2: Import into AdaptiveCAD

1. Launch AdaptiveCAD: `python run_adaptivecad.py`
2. **File > Import > Import STL/OBJ as SDF...** (or `Ctrl+I`)
3. Select `3DBenchy.stl`
4. Wait for mesh-to-SDF conversion (a few seconds)
5. The benchy appears in the viewport!

**What's happening:**
- Loads ~10,000-15,000 triangles from STL
- Converts to signed distance field
- Creates 64³ distance cache for fast queries
- Centers model at origin
- Ready to slice **without any triangles!**

### Step 3: Slice to G-Code (Triangle-Free!)

1. **File > Export > Export G-Code (Direct SDF)...**
2. Choose output file (e.g., `benchy.gcode`)
3. AdaptiveCAD samples the SDF directly:
   - Layer height: 0.2mm (default)
   - Marching squares on each slice plane
   - Generates toolpaths from SDF contours
   - **No mesh conversion** - pure SDF slicing!

### Step 4: Print Settings Optimization

For a perfect benchy, tune these in the slicer code:

**Layer Quality:**
- Layer height: 0.1mm - 0.2mm (lower = better detail)
- Infill: 15-20% (benchy needs support)
- Walls: 2-3 perimeters

**Speed:**
- Print speed: 40-60 mm/s
- First layer: 20 mm/s

**Cooling:**
- Cooling fan: 100% after layer 3

## Technical Details

### Mesh-to-SDF Conversion

AdaptiveCAD converts triangle meshes using:

1. **Unsigned Distance:** Point-to-triangle distance for all mesh faces
2. **Sign Determination:** Ray-casting for inside/outside test (6 rays, majority vote)
3. **Distance Field Cache:** Pre-computed 64³ grid for fast interpolation
4. **Trilinear Interpolation:** Smooth distance queries between grid points

**Performance:**
- Import: ~1-3 seconds for typical models
- Cache build: ~2-10 seconds depending on complexity
- Query speed: ~100,000+ points/second (cached)

### Why This Is Better

Traditional slicing:
1. Load STL triangles ✓
2. Keep triangles in memory ✗
3. Intersect triangles with planes ✗
4. Generate contours from intersections ✗

AdaptiveCAD slicing:
1. Load STL triangles ✓
2. **Convert to SDF once** ✓
3. **Sample SDF directly** ✓
4. **Marching squares for contours** ✓

**Benefits:**
- No triangle storage during slicing
- Consistent distance queries
- Handles non-manifold geometry
- CSG operations possible
- True "triangle-free" from import to G-code

## Troubleshooting

### Import is slow
- Large models (100k+ triangles) take longer
- Reduce cache resolution: Edit `mesh_import.py`, line with `cache_resolution=64` → use 48 or 32

### Model looks shifted
- Auto-centers at origin - this is intentional
- To preserve original position: Edit `mesh_import.py`, `center=True` → `center=False`

### G-code missing details
- Increase layer resolution in slicer settings
- Check model scale (benchy should be ~60mm)

### Import fails
- Ensure STL is valid (no errors)
- Try converting to binary STL
- Check file isn't corrupted

## Advanced: Modify Imported Benchy

Once imported as SDF, you can:

1. **Scale:** Select benchy, press `S`, drag
2. **Array:** `Edit > Array > Linear Array` - make a fleet of benchies!
3. **Boolean:** Add primitives and subtract/intersect
4. **Transform:** Rotate, move, mirror
5. **Measure:** `Tools > Analyze Volume` - check if dimensions are correct

## Comparison with Standard Slicers

| Feature | Traditional Slicer | AdaptiveCAD |
|---------|-------------------|-------------|
| Triangle storage | Full mesh in RAM | Converted to SDF |
| Slice method | Triangle intersection | SDF sampling |
| CSG operations | Limited | Native |
| Non-manifold | Often fails | Handles gracefully |
| Memory usage | High (large models) | Fixed (cache size) |
| Philosophy | Mesh-based | **Triangle-free!** |

## Example: Benchy with Modifications

```python
# Import benchy
# File > Import > STL/OBJ

# Add a sphere on the smokestack (boolean union)
# Create > Basic > Sphere
# Position at (0, 0, 8)  # Top of benchy
# Scale to 0.3

# Subtract a box from the hull (window)
# Create > Basic > Box
# Position at (-5, 0, 3)
# Set operation to "Subtract"

# Export modified benchy
# File > Export > G-Code
```

## Next Steps

- Try importing other models (figurines, mechanical parts)
- Combine imported meshes with parametric primitives
- Use arrays to create patterns of imported objects
- Measure volumes of imported models
- Create custom supports with boolean subtract

---

**Remember:** From STL to G-code, AdaptiveCAD maintains the triangle-free philosophy. The mesh is just an **input format** - internally, everything is SDF! 🎉
