# AdaptiveCAD Tools Reference

## New Tools Added

### 🔢 Array Tools (`Edit > Array`)
Create parametric patterns of primitives:

- **Linear Array** - Duplicate objects along a vector
  - Parameters: Count, X/Y/Z offset per step
  - Use case: Create rows, columns, or diagonal patterns
  
- **Circular Array** - Arrange objects around a circle
  - Parameters: Count, Radius, Axis (X/Y/Z)
  - Use case: Create gears, mandala patterns, radial duplicates
  
- **Grid Array** - 3D grid of objects
  - Parameters: Count X/Y/Z, Spacing X/Y/Z
  - Use case: Lattices, structured patterns, voxel grids

### 📐 Alignment Tools (`Edit > Align`)
Precisely position multiple selected objects:

- **Align** - Align edges or centers
  - Left/Center/Right (X axis)
  - Top/Center/Bottom (Y axis)
  - Front/Center/Back (Z axis)
  
- **Distribute** - Space objects evenly
  - Distribute X/Y/Z
  - Maintains order, equalizes spacing

### 🔄 Transform Tools (`Edit > Transform`)
Geometric transformations:

- **Mirror X/Y/Z** - Create mirrored copies across axes
- **Snap to Grid** (`Ctrl+Shift+G`) - Snap positions to grid
- **Center at Origin** - Move selection center to (0,0,0)

### 🔗 Boolean Operations (`Operations`)
Set CSG operations on selected primitives:

- **Union** (`Ctrl+U`) - Solid/additive (default)
- **Subtract** (`Ctrl+Shift+B`) - Remove from previous objects
- **Intersect** (`Ctrl+I`) - Keep only overlapping volume
- **Boolean Dialog** - Visual picker with explanations

### 📏 Measurement Tools (`Tools`)
Analyze geometry:

- **Measure Distance** (`M`) - Distance between 2 selected objects
- **Analyze Volume** - Estimate volume and surface area via SDF sampling
  - Uses marching-squares-like SDF sampling
  - Resolution: 30³ samples
  - Triangle-free measurement!

### 🎥 Camera Presets (`View`)
Standard orthographic and perspective views:

| View | Shortcut | Description |
|------|----------|-------------|
| **Front** | `Numpad 1` | Look along -Z |
| **Back** | `Ctrl+Numpad 1` | Look along +Z |
| **Right** | `Numpad 3` | Look along -X |
| **Left** | `Ctrl+Numpad 3` | Look along +X |
| **Top** | `Numpad 7` | Look along -Y |
| **Bottom** | `Ctrl+Numpad 7` | Look along +Y |
| **Isometric** | `Numpad 0` | Classic 3/4 view |

**Fit Commands:**
- `F` - Fit all objects in view
- `Shift+F` - Fit selected objects

## New Primitives

### 🧿 Hydrogenic Orbital (`Create > Mathematical`)
Analytic quantum mechanical orbital isosurfaces:

- **Parameters:**
  - `n` (principal quantum number): 1-6
  - `l` (angular momentum): 0 to n-1 (s/p/d/f)
  - `m` (magnetic): -l to +l
  - `iso` - Density threshold for isosurface (|ψ|² = iso)
  - `thickness` - Shell thickness around surface

- **Examples:**
  - `n=2, l=1, m=0` → 2p orbital (dumbbell)
  - `n=3, l=2, m=0` → 3d orbital (cloverleaf)
  - `n=1, l=0, m=0` → 1s orbital (sphere)

- **Technical:**
  - CPU & GPU: Distance-estimate via `|F|/|∇F|` (finite diff)
  - Real spherical harmonics
  - Generalized Laguerre polynomials
  - Fully triangle-free!

## Keyboard Shortcuts Summary

### Selection & Transform
| Key | Action |
|-----|--------|
| `Q` | Select mode |
| `G` | Move mode |
| `R` | Rotate mode |
| `S` | Scale mode |

### Edit
| Key | Action |
|-----|--------|
| `Delete` | Delete selected |
| `Ctrl+D` | Duplicate |
| `Ctrl+M, X/Y/Z` | Mirror across axis |
| `Ctrl+Shift+G` | Snap to grid |

### View
| Key | Action |
|-----|--------|
| `F` | Fit all |
| `Shift+F` | Fit selected |
| `Numpad 1/3/7` | Front/Right/Top |
| `Numpad 0` | Isometric |

### Operations
| Key | Action |
|-----|--------|
| `Ctrl+U` | Union (solid) |
| `Ctrl+Shift+B` | Boolean subtract |
| `Ctrl+I` | Boolean intersect |

### Tools
| Key | Action |
|-----|--------|
| `M` | Measure distance |

## Implementation Notes

All new features maintain the **triangle-free philosophy**:
- Array tools duplicate `Prim` objects directly
- Alignment operates on transform matrices
- Measurements use SDF sampling (no mesh generation)
- Camera tools manipulate view matrices
- Boolean ops set SDF operation flags (`op` field)

## Files Added

- `adaptivecad/app/array_tools.py` - Array and mirror operations
- `adaptivecad/app/align_tools.py` - Alignment and distribution
- `adaptivecad/app/boolean_ops.py` - Boolean operation UI
- `adaptivecad/app/measurement_tools.py` - Distance and volume analysis
- `adaptivecad/app/camera_tools.py` - View presets and framing
- Updated `adaptivecad/app/main_window.py` - Menu integration
- Updated `adaptivecad/aacore/sdf.py` - Added `KIND_ORBITAL`
- Updated `adaptivecad/analytic/shaders/sdf.frag` - GPU orbital raymarch
- Updated `adaptivecad/app/shape_creation.py` - Orbital UI

## Usage Examples

### Creating a circular gear pattern:
1. Create a box: `Create > Basic > Box`
2. `Edit > Array > Circular Array`
3. Set Count=12, Radius=3.0, Axis=Z

### Aligning multiple objects:
1. Select 3+ objects (Ctrl+click in scene tree)
2. `Edit > Align > Align Center X`
3. `Edit > Align > Distribute Y`

### Creating a mirrored pair:
1. Select object
2. `Edit > Transform > Mirror X` (or press `Ctrl+M, X`)

### Measuring an orbital:
1. Create `Hydrogenic Orbital` with n=2, l=1, m=0
2. Select it
3. `Tools > Analyze Volume`
4. Wait for SDF sampling (30³ grid)

---

**Triangle Count: Still ZERO! 🎉**
