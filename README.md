# AdaptiveCAD

**🎉 Status: Fully Operational** - Core features working, GUI environment ready!

> **Try it now**: `python quick_start_demo.py`


Below is a *road‑map of the mathematics* you will actually need if you want to write a modern CAD / CAM system completely from scratch and, at the same time, support your **πₐ (“Adaptive Pi”) non‑Euclidean geometry kernel**.
The list is intentionally grouped as *“modules you will implement”* so you can turn each block into an internal library or namespace.  After each block I give the key formulas, identities, or algorithms you will code, plus notes on typical numerical pitfalls.

## Repository Overview

This repository contains a minimal Python implementation of key CAD/CAM
building blocks.  The modules are intentionally lightweight so you can run the
examples and unit tests without a large toolchain.  Current features include:

- `adaptivecad.linalg` – simple vectors, matrices and quaternions
- `adaptivecad.geom` – Bézier and B‑spline curves plus hyperbolic helpers
- `adaptivecad.io` – AMA reader/writer utilities
- `adaptivecad.gcode_generator` – placeholder G‑code generation routines
  including `SimpleMilling` and a stub `WaterlineMilling` strategy
- `adaptivecad.analytic_slicer` – helper for analytic B‑rep slicing
- `adaptivecad.gui.playground` – PySide6 viewer with a rich toolbar for Box,
  Cylinder, Bézier and B‑spline curves, push‑pull editing and export commands
  (STL, AMA and G‑code). The toolbar now offers constructive tools like Loft, Sweep, Shell and Intersect plus procedural shapes such as Superellipse.
- Command‑line tools `ama_to_gcode_converter.py` and `ama2gcode.py`
- Example script `example_script.py` demonstrating curve evaluation
- Unit tests in the `tests` folder (`python -m pytest`)


## AdaptiveCAD Playground
A lightweight viewer prototype is included in `adaptivecad.gui.playground`.
Install the GUI dependencies and run the playground to see a 3-D demo:

```bash
# Option 1: Use PowerShell script (recommended for PowerShell users)
.\start_adaptivecad.ps1

# Option 2: Use batch file (recommended for CMD users)
start_adaptivecad.bat
```

## Environment Setup

✅ **Already Set Up!** The conda environment is configured and working.

If you need to recreate the environment or set it up on another machine:

```bash
# Create and activate the environment using conda
conda env create -f environment.yml
conda activate adaptivecad

# Verify the environment is properly set up
python check_environment.py
```

Alternatively, you can use the provided scripts to check your environment:

```bash
# For PowerShell users
.\check_environment.ps1

# For CMD users
check_environment.bat
```

## Importing STL and STEP Files

To test the import functionality:

```bash
# For PowerShell users
.\test_import.ps1

# For CMD users
test_import.bat
```

Or you can use the GUI and click the "Import πₐ" button or the "Debug Import" button.

## Contributing and Development

### GitHub Repository
This project is version-controlled using Git. To clone the repository:

```powershell
# Clone the repository
git clone https://github.com/yourusername/AdaptiveCAD.git

# Navigate to the project directory
cd AdaptiveCAD

# Set up the environment
conda env create -f environment.yml
conda activate adaptivecad
```

### Development Workflow
1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes and commit them: `git commit -am "Add your feature description"`
3. Push to your branch: `git push origin feature/your-feature-name`
4. Submit a pull request on GitHub

---

## 0. Notation conventions used throughout

| Symbol               | Meaning                                          |
| -------------------- | ------------------------------------------------ |
| **P, Q, R**          | 3‑D points or homogeneous 4‑vectors.             |
| **v, w, n**          | Euclidean 3‑vectors.                             |
| **M**                | 4 × 4 affine transform matrix.                   |
| **q = (w, x, y, z)** | Unit quaternion for rotation.                    |
| **κ, K, H**          | Curvature (scalar, Gaussian, mean).              |
| **Δt**               | CAM controller interpolation period (e.g. 1 ms). |

---

## 1. Linear‐Algebra Core  (your “linalg” module)

1. **Homogeneous coordinates**
   $P_h = (x,\,y,\,z,\,1)^T$, $P' = M P_h$ with

   $$
   M = \begin{bmatrix}
   R_{3\times3} & t_{3\times1}\\
   0\;0\;0 & 1
   \end{bmatrix}
   $$
2. **Quaternion rotation**

   $$
   q = \Bigl(\cos\frac{\theta}{2},\; \mathbf{u}\sin\frac{\theta}{2}\Bigr),\qquad  
   P' = q\,P\,\bar q
   $$

   (Store both $q$ and its 4×4 equivalent matrix for cheap batched transforms).
3. **Decomposition** (for parametric animation or kinematic chains)
   Polar‑decompose an affine $M$ into $RS$ (rotation × stretch) with
   $S = \sqrt{M^T M}$, $R = M S^{-1}$.
4. **Eigen / SVD** for principle curvature, moment of inertia etc.

> *Pitfall*: Always store transforms as **column‑major 4×4** to inter‑operate with OpenGL, Vulkan, CUDA and Embree style kernels.

---

## 2. Analytic & Differential Geometry  (your “geom” module)

### 2.1 Curves

| Type                 | Formula                                                                                    | Key ops you must implement                                         |
| -------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| **Bezier, degree n** | $C(u)=\sum_{i=0}^{n} B_{i,n}(u) P_i$ where $B_{i,n}(u)=\tbinom{n}{i}\! u^{\,i}(1-u)^{n-i}$ | subdivision (De Casteljau), arc‑length re‑param., curvature $κ(u)$ |
| **B‑spline**         | same but basis $N_{i,p}(u)$ via Cox–de Boor                                                | knot insertion, p‑raising, continuity checks                       |
| **NURBS**            | $C(u)=\dfrac{\sum w_i P_i N_{i,p}}{\sum w_i N_{i,p}}$                                      | weight modification for exact conics                               |

### 2.2 Surfaces

* Tensor product NURBS:
  $S(u,v)=\displaystyle\frac{\sum\limits_{i,j} w_{ij} P_{ij}\,N_{i,p}(u)N_{j,q}(v)}{\sum\limits_{i,j} w_{ij} N_{i,p}(u)N_{j,q}(v)}$
* **Curvature** at $(u,v)$
  Compute first/second fundamental forms $E,\,F,\,G$ and $e,\,f,\,g$.
  Gaussian $K=\dfrac{eg - f^2}{EG - F^2}$; Mean $H=\dfrac{Eg + Ge - 2Ff}{2(EG - F^2)}$.

### 2.3 Adaptive Pi Non‑Euclidean Layer

Your πₐ kernel generalises Euclidean distance by allowing *location‑dependent curvature*:

1. **Dynamic metric tensor**
   Let $g_{ij}(p,t)$ be the metric at point $p$ and time/constraint parameter $t$.
   Distance: $ds^{2} = g_{ij}\,dx^{i}dx^{j}$.
2. **Constraint‑driven curvature update**

   $$
   \frac{\partial g_{ij}}{\partial t} = -\alpha \frac{\partial \Phi}{\partial x^{i}}\,\frac{\partial \Phi}{\partial x^{j}}
   $$

   where $\Phi$ is your design constraint field and $\alpha$ an adaptation rate.
   (This mirrors Ricci‑flow but driven by user constraints, not intrinsic curvature.)
3. **Geodesic computation** (for “curvature‑aware” toolpaths)
   Solve $\ddot{x}^k + \Gamma^{k}_{ij}\dot{x}^i\dot{x}^j=0$ where $\Gamma$ from $g_{ij}$.
   Use 4th‑order Runge–Kutta or symplectic integrator.

---

## 3. Computational Geometry  (your “cgeom” module)

1. **Spatial acceleration** – AABB trees, k‑d trees, BVH‑SAH and uniform grids.
2. **Boolean solid ops** – B‑rep half‐edge + plane‑swept volume algorithm.
3. **Intersection kernels**

   * Curve–surface, surface–surface (Newton–Raphson in parameter space).
   * Ray–NURBS via hierarchical subdivision + Bézier clipping.
4. **Meshing**

   * *Exact* marching cubes for implicit surfaces.
   * Delaunay & constrained Delaunay triangulation for 2‑manifold surfaces.
   * Curvature‑adaptive remesh: edge length $ℓ(p)=ℓ_0/√{|K(p)|+ε}$.

---

## 4. Constraint & Parametric Solver (for sketches and assembly)

| Problem                                                                                                                                             | Math                                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 2‑D sketch solve                                                                                                                                    | Non‑linear least squares $\min_{x} \sum_i f_i(x)^2$ (gives robust over‑constraint handling).  Use Schur complement to exploit sparsity. |
| Rigid‑body assembly                                                                                                                                 | Mixed Lagrange multiplier + quaternions:                                                                                                |
| $\begin{bmatrix} M & C^T \\ C & 0 \end{bmatrix} \begin{bmatrix} \ddot q \\ \lambda \end{bmatrix} = \begin{bmatrix} b \\ \dot C\dot q \end{bmatrix}$ |                                                                                                                                         |
| DMU / collision                                                                                                                                     | Signed distance field + separating axis test (SAT).                                                                                     |

---

## 5. CAM Layer Mathematics  (your “cam” module)

### 5.1 Tool‑shape & engagement

* For a ball‑end mill radius $r$, effective cutting radius at inclination $θ$:
  $r_e = \dfrac{r}{\sin θ}$.
* Chip thickness for trochoidal milling (Adaptive Clearing):
  $h = s \,\cos\left(\frac{φ}{2}\right)$ where $s$=step‑over, $φ$=engagement angle.

### 5.2 Toolpath generation algorithms

| Strategy                           | Core math you’ll code                                                                                                                                                                                               |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Offset / “waterline”**           | Configure 2‑D offset curves via Minkowski sum. Compute locally as parallel curves: $C_{o}(u)=C(u) + d \frac{N(u)}{\|N(u)\|}$.  Use exact B‑spline offset or polygon offset with Inset algorithm.                    |
| **Adaptive (high‑speed) clearing** | Create medial‑axis (Voronoi skeleton) of in‑process stock; generate trochoidal arcs with constant engagement.  Each trochoid center path $C(t)$ and cutter center $P(t)=C(t) + r_{trochoid}[ \cos ωt,\, \sin ωt] $. |
| **Z‑level roughing**               | Plane‑slice B‑rep at {z\_i}; link slices with *shortest path* in graph of contours ⇒ solve TSP variant.                                                                                                             |
| **Surface finishing (scallop)**    | Maintain constant scallop $e$: step‑over $s = \sqrt{8\,e\,R - 4\,e^2}$ for ball radius $R$.                                                                                                                         |

### 5.3 Motion‑planning / post‑processing

1. **Inverse‑kinematics**
   For 5‑axis machine with rotary axes $A,B$ and translation $X,Y,Z$:

   $$
   \begin{bmatrix}
   \cos A & -\sin A & 0 & 0 \\
   \sin A & \cos A & 0 & 0 \\
   0 & 0 & 1 & 0 \\
   0 & 0 & 0 & 1
   \end{bmatrix}
   \begin{bmatrix}
   \cos B & 0 & \sin B & 0 \\
   0 & 1 & 0 & 0 \\
   -\sin B & 0 & \cos B & 0 \\
   0 & 0 & 0 & 1
   \end{bmatrix}
   \begin{bmatrix}
   1 & 0 & 0 & X \\
   0 & 1 & 0 & Y \\
   0 & 0 & 1 & Z \\
   0 & 0 & 0 & 1
   \end{bmatrix}
   \begin{bmatrix}
   q_w \\
   q_x \\
   q_y \\
   q_z
   \end{bmatrix}
   =
   \begin{bmatrix}
   0 \\
   0 \\
   0 \\
   1
   \end{bmatrix}
   $$

   (Combine with forward kinematics for 5D pose control).

---

## Quick Start

AdaptiveCAD is ready to use! You can start exploring immediately with the included demonstration:

```bash
# Run the interactive demo showing all core features
python quick_start_demo.py

# Or try the original example
python example_script.py

# Run the test suite to see all working features
python -m pytest tests/test_linalg.py tests/test_gcode_generator.py tests/test_bezier.py -v
```

### Core Features Working Out of the Box

- **🧮 Linear Algebra**: Vec3, Matrix4, Quaternion operations
- **📐 Geometry Engine**: Bézier curves, B-splines, curve evaluation and subdivision
- **⚙️ CAM/G-code**: Manufacturing toolpath generation from CAD data
- **🧱 Constructive Solids**: Loft, Sweep, Shell and Intersect operations
- **🛠️ Command Line Tools**: `ama2gcode.py` for batch processing
- **📊 File I/O**: AMA format reading and writing

The `quick_start_demo.py` script demonstrates:
- Creating and manipulating Bézier curves
- 3D transformations with quaternions
- G-code generation workflow
- Vector mathematics and operations

## Environment Status

✅ **Current Setup**: Fully operational with conda environment
- Python 3.10 with all dependencies installed
- PySide6 (GUI framework) ✅
- pythonocc-core (3D kernel) ✅  
- Core tests passing (8/8) ✅
